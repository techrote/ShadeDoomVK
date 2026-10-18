"""Bounded deep audits, separate from the sole supervisor control heartbeat.

Immutable file handles protect bytes; terminal native root guards protect audit
generations against namespace changes. A successful audit alone is insufficient
authority to create or resume a process.
"""
from __future__ import annotations

import queue
import math
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .common import Stop, INTEGRITY_POLICY, canonical, exclusive, pin, read_json, require, utc, verify_pin, verify_roots
from .readers import BoundedReaders

TIMEOUT = 10
BOUNDARY_FRESHNESS = .5
GATE_BUSY_LIMIT = 1
POLICY=INTEGRITY_POLICY


def proof_deadline(proof):
    return min(proof["finished_monotonic"]+BOUNDARY_FRESHNESS,
               proof["started_monotonic"]+TIMEOUT,
               proof["request"]["requested_monotonic"]+TIMEOUT)


@contextmanager
def responsive_gate(gate, health):
    """Never suspend control/parent-liveness checks while awaiting a gate."""
    started=time.monotonic()
    while True:
        health()
        require(0 <= time.monotonic()-started < GATE_BUSY_LIMIT,"Shared gate critical section stalled")
        if gate.acquire(timeout=0):break
        time.sleep(.01)
    try:
        health()
        yield gate
    finally:gate.__exit__()


def valid_proof(value, packet, stage, supervisor, *, request=None, boundary=False):
    require(set(value)=={"schema","packet_sha256","stage","supervisor","generation","started_monotonic",
                         "finished_monotonic","utc","request","status","checks","policy"},"Incomplete integrity generation")
    require(value["schema"] == "physical-supervisor/integrity-generation-v1" and
            value["packet_sha256"] == packet["packet_sha256"] and value["stage"] == stage["name"] and
            value["supervisor"] == supervisor and value["status"] == "PASS", "Integrity generation identity differs")
    require(value["request"] is None or isinstance(value["request"],dict),"Invalid integrity request type")
    require(type(value["generation"]) is int and value["generation"]>=0 and
            canonical(value["policy"])==canonical(POLICY)==canonical(packet["integrity_policy"]) and
            type(value["checks"]["closed_roots"]) is int and
            type(value["checks"]["generated_pins"]) is int and
            value["checks"]=={"closed_roots":len(packet["runtime_roots"]),"log_append_only":"PASS",
                "generated_pins":len(stage.get("generated_pins",[])) if value["request"] is not None and value["request"].get("role")=="target" else 0},
            "Integrity generation coverage/policy differs")
    require(all(type(value[key]) in (int,float) and math.isfinite(value[key]) for key in
                ("started_monotonic","finished_monotonic")),"Invalid integrity timestamps")
    now = time.monotonic()
    require(0 <= value["finished_monotonic"] - value["started_monotonic"] <= TIMEOUT and
            0 <= now-value["finished_monotonic"] and
            0 <= now - value["started_monotonic"] <= TIMEOUT, "Integrity generation stale/invalid")
    if value["request"] is not None:
        item=value["request"]
        require(set(item)=={"schema","packet_sha256","stage","supervisor","collector","role","source_preflight",
                            "nonce","requested_monotonic"} and item["schema"]=="physical-supervisor/integrity-request-v1" and
                item["packet_sha256"]==packet["packet_sha256"] and item["stage"]==stage["name"] and
                item["supervisor"]==supervisor and item["role"] in ("collector","target") and
                isinstance(item["nonce"],str) and re.fullmatch(r"[0-9a-f]{32}",item["nonce"]) and
                type(item["requested_monotonic"]) in (int,float) and math.isfinite(item["requested_monotonic"]) and
                0 <= item["requested_monotonic"] <= value["started_monotonic"],"Integrity request binding differs")
        require((item["collector"] is None) == (item["role"]=="collector"),"Integrity request owner role differs")
    if boundary:
        require(request is not None and value["request"] == request and
                0 <= now-request["requested_monotonic"] <= TIMEOUT and
                value["started_monotonic"] >= request["requested_monotonic"] and
                0 <= now-value["finished_monotonic"] < BOUNDARY_FRESHNESS,
                "Boundary integrity generation missing/stale/reused")


class IntegrityWatch:
    """One audit at a time; worker never emits a heartbeat or touches a process."""
    def __init__(self, packet, stage, control, supervisor, expectations, scanner, logs, journal):
        self.packet,self.stage,self.control,self.supervisor=packet,stage,Path(control),supervisor
        self.expectations,self.scanner,self.logs,self.journal=expectations,scanner,logs,journal
        self.done=threading.Event();self.messages=queue.Queue(maxsize=64)
        self.failure=None;self.failure_evidence=None;self.latest=None;self.inflight=None;self.sequence=0;self.processed=set()
        self.audit_request=None
        self.reader=BoundedReaders(self.audit,None,timeout=TIMEOUT)
        self.thread=threading.Thread(target=self.loop,daemon=True)

    def audit(self):
        verify_roots(self.packet,self.expectations)
        self.scanner.check(self.logs)
        generated=0
        if self.audit_request is not None and self.audit_request["role"]=="target":
            for row in self.stage["generated_pins"]:verify_pin(row)
            generated=len(self.stage["generated_pins"])
        return {"closed_roots":len(self.expectations),"log_append_only":"PASS","generated_pins":generated}

    def loop(self):
        try:
            while not self.done.is_set():
                request=None
                role=next((role for role in ("collector","target") if
                           (self.control/f"integrity-{role}-request.json").exists() and role not in self.processed),None)
                path=self.control/f"integrity-{role}-request.json"
                if role is not None:
                    request=read_json(path)
                    require(request["schema"]=="physical-supervisor/integrity-request-v1" and
                            request["packet_sha256"]==self.packet["packet_sha256"] and
                            request["stage"]==self.stage["name"] and request["supervisor"]==self.supervisor and
                            request["role"]==role and
                            isinstance(request["nonce"],str) and re.fullmatch(r"[0-9a-f]{32}",request["nonce"]),
                            "Invalid integrity boundary request")
                    require(0 <= time.monotonic()-request["requested_monotonic"] <= TIMEOUT,"Stale integrity request")
                    # Authenticate the actual requesting collector against its
                    # retained supervisor identity before issuing its proof.
                    if role=="target":
                        require(request["collector"]==read_json(self.control/"collector-identity.json"),
                                "Integrity request is not the registered collector")
                        from .windows import Process
                        process=Process.open(request["collector"]["pid"])
                        try:process.verify(request["collector"])
                        finally:process.close()
                        require(request["collector"]["parent_pid"]==self.supervisor["pid"] and
                                request["collector"]["parent_creation_ticks"]==self.supervisor["creation_ticks"],
                                "Integrity request collector parent differs")
                    else:require(request["collector"] is None,"Precollector request has unexpected owner")
                    require(request["source_preflight"]==pin(self.control/"source-preflight.json"),
                            "Integrity request source proof differs")
                    self.processed.add(role)
                self.inflight=time.monotonic()
                self.audit_request=request
                result=self.reader.call("telemetry")
                value={"schema":"physical-supervisor/integrity-generation-v1","packet_sha256":self.packet["packet_sha256"],
                       "stage":self.stage["name"],"supervisor":self.supervisor,"generation":self.sequence,
                       "started_monotonic":self.inflight,"finished_monotonic":time.monotonic(),"utc":utc(),
                       "request":request,"status":"PASS","checks":result,
                       "policy":POLICY}
                valid_proof(value,self.packet,self.stage,self.supervisor,request=request,boundary=request is not None)
                path=self.control/f"integrity-{self.sequence:06d}.json"
                exclusive(path,value)
                receipt=pin(path)
                self.messages.put_nowait((value,receipt))
                if request:exclusive(self.control/f"integrity-{role}-proof.json",{"receipt":receipt,"request":request})
                self.latest=(value,receipt);self.inflight=None;self.sequence+=1
                if self.done.wait(.1):return
        except BaseException as error:
            self.failure=str(error) or type(error).__name__
            self.failure_evidence={"schema":"physical-supervisor/integrity-failure-v1","packet_sha256":self.packet["packet_sha256"],
                                   "stage":self.stage["name"],"supervisor":self.supervisor,"generation":self.sequence,
                                   "started_monotonic":self.inflight,"failed_monotonic":time.monotonic(),"request":request,
                                   "error":str(error),"partial_evidence":getattr(error,"evidence",None)}

    def start(self):self.thread.start()

    def check(self, *, require_ready=True):
        while True:
            try:value,receipt=self.messages.get_nowait()
            except queue.Empty:break
            self.journal.append("integrity-generation",{"receipt":receipt,"generation":value})
        if self.failure is not None:
            error=Stop(self.failure);error.evidence=self.failure_evidence
            raise error
        require(self.thread.is_alive(),"Integrity worker died unexpectedly")
        if self.inflight is not None:
            require(0 <= time.monotonic()-self.inflight <= TIMEOUT,"Integrity check exceeded timeout")
        if self.latest is None:
            require(not require_ready,"Integrity generation missing")
            return None
        value,receipt=self.latest
        valid_proof(value,self.packet,self.stage,self.supervisor)
        return receipt

    def finish(self):
        self.done.set();self.thread.join(timeout=TIMEOUT+.2)
        require(not self.thread.is_alive(),"Integrity worker did not finish")
        require(self.failure is None,self.failure or "Integrity worker failed")
        while True:
            try:value,receipt=self.messages.get_nowait()
            except queue.Empty:break
            self.journal.append("integrity-generation",{"receipt":receipt,"generation":value})


def boundary_request(packet,stage,control,guard,roots):
    from .windows import Process
    owner=Process.open(__import__("os").getpid())
    try:identity=owner.identity()
    finally:owner.close()
    roots.check();guard.check()
    request={"schema":"physical-supervisor/integrity-request-v1","packet_sha256":packet["packet_sha256"],
             "stage":stage["name"],"supervisor":guard.expected,"collector":identity,
             "role":"target","source_preflight":pin(control/"source-preflight.json"),
             "nonce":uuid.uuid4().hex,"requested_monotonic":time.monotonic()}
    exclusive(control/"integrity-target-request.json",request)
    until=time.monotonic()+TIMEOUT
    path=control/"integrity-target-proof.json"
    while not path.exists():
        guard.check();roots.check()
        require(time.monotonic()<until,"Boundary integrity generation timed out")
        time.sleep(.02)
    proof=read_json(path)
    require(proof["request"]==request,"Boundary proof request replaced")
    require(Path(proof["receipt"]["path"]).parent==control,"Boundary proof path differs")
    verify_pin(proof["receipt"])
    value=read_json(proof["receipt"]["path"])
    require(Path(proof["receipt"]["path"]).name==f"integrity-{value['generation']:06d}.json","Boundary proof name differs")
    valid_proof(value,packet,stage,guard.expected,request=request,boundary=True)
    return value,request


def collector_boundary(packet,stage,control,supervisor,pump):
    request={"schema":"physical-supervisor/integrity-request-v1","packet_sha256":packet["packet_sha256"],
             "stage":stage["name"],"supervisor":supervisor,"collector":None,"role":"collector",
             "source_preflight":pin(control/"source-preflight.json"),
             "nonce":uuid.uuid4().hex,"requested_monotonic":time.monotonic()}
    exclusive(control/"integrity-collector-request.json",request)
    until=time.monotonic()+TIMEOUT
    while not (control/"integrity-collector-proof.json").exists():
        pump()
        require(time.monotonic()<until,"Collector boundary generation timed out")
        time.sleep(.02)
    evidence=read_json(control/"integrity-collector-proof.json")
    require(evidence["request"]==request,"Collector boundary request replaced")
    require(Path(evidence["receipt"]["path"]).parent==control,"Collector boundary proof path differs")
    verify_pin(evidence["receipt"])
    proof=read_json(evidence["receipt"]["path"])
    require(Path(evidence["receipt"]["path"]).name==f"integrity-{proof['generation']:06d}.json","Collector boundary proof name differs")
    valid_proof(proof,packet,stage,supervisor,request=request,boundary=True)
    return proof,request
