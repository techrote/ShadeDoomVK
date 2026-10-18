"""Serial no-retry supervisor with concurrent bounded hardware observation."""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import queue
import re
import threading
import time

from .common import Gate, Journal, Stop, approve, canonical, digest, exclusive, future, normalized, pin, read_json, require, utc, validate_packet, verify_pin, verify_roots, verify_source, linklike, sealed_environment, verify_registry, root_expectations
from .readers import BoundedReaders, NativeEvents, continuity, gpu_reader, telemetry,bounded_host_identity,check_host_identity
from .windows import FileLock, Job, Process, RootGuard, platform_check, reject_unowned_renderer
from .integrity import IntegrityWatch, valid_proof, collector_boundary, proof_deadline, GATE_BUSY_LIMIT

GRACE_SECONDS = 15  # Tests shorten only the synthetic CPU clock; CLI policy is fixed.

FAULT = re.compile(rb"\[fault\]|\[vulkan error\]|Validation Error\s*:|VK_ERROR_DEVICE_LOST|\bdevice[ -]lost\b|SDVK_OBSERVATION_(?:FAILED|REJECTED|WRITE_FAILED)|Fatal error|Execution could not continue|Script error|Unknown command", re.I)


class LogScanner:
    def __init__(self):
        self.offsets, self.tails, self.identities, self.prefixes = {}, {}, {}, {}

    def check(self, paths):
        for path in paths:
            path = Path(path)
            if not path.exists():
                continue
            require(path.is_file() and not linklike(path), "Output log replaced by link")
            offset = self.offsets.get(path, 0)
            metadata = path.stat()
            identity = (metadata.st_dev, metadata.st_ino)
            require(path not in self.identities or self.identities[path] == identity, "Output log file identity replaced")
            self.identities[path] = identity
            require(metadata.st_size >= offset, "Output log truncated")
            with path.open("rb") as stream:
                hasher=hashlib.sha256();remaining=offset
                while remaining:
                    chunk=stream.read(min(remaining,1024*1024))
                    require(chunk,"Output log truncated during prefix audit")
                    hasher.update(chunk);remaining-=len(chunk)
                previous = hasher.hexdigest()
                require(path not in self.prefixes or previous == self.prefixes[path], "Output log prefix overwritten")
                data = stream.read(16 * 1024 * 1024 + 1)
                require(len(data) <= 16 * 1024 * 1024, "Unread log evidence budget exceeded")
                self.offsets[path] = stream.tell()
                hasher.update(data)
                self.prefixes[path] = hasher.hexdigest()
            text = self.tails.get(path, b"") + data
            require(not FAULT.search(text), "Renderer/collector fault marker")
            self.tails[path] = text[-512:]


class Watch:
    """Separate cadence loops; a blocked event reader does not suspend GPU polls."""
    def __init__(self, packet, baseline, journal, readers=None):
        self.packet, self.baseline, self.journal = packet, baseline, journal
        self.readers = readers or BoundedReaders(gpu_reader(packet["nvidia_smi"]), NativeEvents().snapshot)
        self.messages, self.done = queue.Queue(maxsize=64), threading.Event()
        self.failure = None
        self.failure_records=queue.Queue(maxsize=64)
        self.threads = []

    def fail(self, error):
        self.failure = str(error)
        try:
            self.failure_records.put_nowait({"error":str(error),"partial_evidence":getattr(error,"evidence",None)})
        except queue.Full:
            self.failure += "; failure evidence queue overflow (incomplete evidence)"
        try:
            # Serialize STOP publication with native create/resume. The failure
            # flag is already visible to the control loop, which authenticates
            # and contains owned handles before waiting on this gate.
            with Gate(self.packet["stop_root"], self.packet["packet_sha256"]) as gate:
                gate.stop(error)
        except BaseException as latch_error:
            self.failure += "; durable STOP write failed: " + str(latch_error)
        self.done.set()

    def loop(self, name, cadence):
        next_at = time.monotonic()
        try:
            while not self.done.is_set():
                if self.done.wait(max(0, next_at - time.monotonic())):
                    return
                started = time.monotonic()
                target_registered_at = None
                require(started - next_at < .5, "Observer scheduling cadence missed")
                if name == "telemetry":
                    raw = self.readers.call(name)
                    value = {"raw_utf8": raw.decode("utf-8", errors="replace"),
                             "readback": telemetry(raw, self.packet["telemetry"], self.packet["temperature_limit_c"])}
                else:
                    value = self.readers.call(name, self.baseline)
                self.messages.put_nowait((name, {"started_monotonic": started, "finished_monotonic": time.monotonic(), **value}))
                if name == "event":
                    self.baseline = continuity(self.baseline, value)
                # A read taking longer than the sampling interval is retained;
                # loss of the reviewed cadence fails closed, never overlaps or
                # silently slows a reader to compensate for a slow command.
                next_at += cadence
                require(time.monotonic() - started <= cadence, "Reader missed reviewed polling cadence")
        except BaseException as error:
            self.fail(error)

    def start(self):
        for name, cadence in (("telemetry", 1), ("event", 5)):
            thread = threading.Thread(target=self.loop, args=(name, cadence), daemon=True)
            self.threads.append(thread)
            thread.start()

    def check(self):
        while True:
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            self.journal.append(kind, value)
        while True:
            try:failure=self.failure_records.get_nowait()
            except queue.Empty:break
            self.journal.append("partial-reader-evidence",failure)
        require(self.failure is None, self.failure or "Reader failure")
        require(all(thread.is_alive() for thread in self.threads) or self.done.is_set(), "Observer thread died unexpectedly")

    def finish(self):
        self.done.set()
        for thread in self.threads:
            thread.join(timeout=10.1)
            require(not thread.is_alive(), "Observer did not finish within bounded read timeout")
        self.check()


class ModuleWatch:
    """Actual loaded DLL readback, bounded off the heartbeat/control thread."""
    def __init__(self,packet,target,identity,journal,health,*,target_deadline=None):
        self.packet,self.target,self.identity,self.journal,self.health=packet,target,identity,journal,health
        self.policy=packet["module_policy"]
        self.done=threading.Event();self.messages=queue.Queue(maxsize=1024)
        self.observed={};self.locks=[];self.failure=None;self.samples=0
        self.inflight_paths=[];self.inflight_additions=[];self.completed=False
        self.target_deadline=target_deadline
        self.expected={normalized(row["path"]):row for row in packet["files"]}
        self.readers=BoundedReaders(self.sample,None,timeout=10)
        self.thread=threading.Thread(target=self.loop,daemon=True)

    def sample(self):
        started=time.monotonic()
        settle_deadline=min(started+10,self.target_deadline) if self.target_deadline is not None else started+10
        if self.target.poll() is not None:
            require(self.target.exited_owned(self.identity),"Actual module target exit identity differs")
            return {"state":"EXITED"}
        try:paths=self.target.modules(self.identity)
        except BaseException as error:
            if self.target.exited_owned(self.identity,error=error,operation="actual-module-authentication",
                                        settle_deadline=settle_deadline):
                return {"state":"EXITED","exit_observations":self.target.take_exit_observations()}
            raise
        self.inflight_paths=list(paths);self.inflight_additions=[]
        additions=[]
        system=Path(os.environ.get("SystemRoot",os.environ.get("SYSTEMROOT","C:\\Windows"))).resolve()
        for path in paths:
            if path in self.observed:continue
            row=pin(path)
            if path in self.expected:
                require(row["sha256"]==self.expected[path]["sha256"] and row["size"]==self.expected[path]["size"],"Actual module differs from preregistration")
                provenance="PREREGISTERED_AND_OBSERVED"
            else:
                name=Path(path).name.casefold()
                require(Path(path).is_relative_to(system) and not name.startswith(("nv","vulkan","graphics-hook")),
                        "Unreviewed driver/layer/external module loaded")
                provenance="SYSTEM_MODULE_OBSERVED_POST_LAUNCH; not a prelaunch selection claim"
            lock=FileLock(row)
            self.locks.append(lock)
            actual={**row,"provenance":provenance}
            self.observed[path]=actual;additions.append(actual)
            self.inflight_additions.append(actual)
        self.samples+=1
        return {"state":"OBSERVED","module_paths":paths,"new_module_pins":additions,"sample":self.samples,"utc":utc()}

    def loop(self):
        try:
            while not self.done.is_set():
                value=self.readers.call("telemetry")
                self.messages.put_nowait(value)
                if value["state"]=="EXITED":return
                if self.done.wait(.25):return
        except BaseException as error:
            self.failure=str(error)
            failure=Stop("Actual module reader: "+str(error))
            failure.evidence={"module_paths":self.inflight_paths,"new_module_pins":self.inflight_additions,
                              "previously_observed_pins":list(self.observed.values()),"error":str(error),
                              "error_evidence":getattr(error,"evidence",None)}
            self.health.fail(failure)
        finally:self.completed=True

    def start(self):self.thread.start()

    def check(self):
        while True:
            try:value=self.messages.get_nowait()
            except queue.Empty:break
            self.journal.append("actual-modules",value)
        require(self.failure is None,self.failure or "Actual module reader failed")
        require(self.thread.is_alive() or self.completed,"Actual module observer thread died silently")

    def finish(self,*,require_complete):
        self.done.set();self.thread.join(timeout=10.1)
        require(not self.thread.is_alive(),"Actual module reader did not stop")
        try:
            self.check()
            if require_complete:
                require(self.samples > 0,"Actual target module evidence missing")
                required={normalized(path) for path in self.policy["required_paths"]}
                require(required <= set(self.observed),"Required actual Vulkan/ICD module not observed")
        finally:
            for lock in self.locks:lock.close()


def _registration(packet, stage, control, collector, collector_identity, journal, before_ack=lambda:None):
    path = control / "target-request.json"
    if not path.exists():
        return None, None
    request = read_json(path)
    require(request["packet_sha256"] == packet["packet_sha256"] and request["stage"] == stage["name"] and
            request["state"] == "SUSPENDED", "Stale/invalid target registration")
    collector.verify(collector_identity)
    require(request["collector"] == collector_identity, "Collector registration identity changed")
    require(request["argv"] == stage["expected_argv"] and normalized(request["cwd"]) == normalized(stage["capture"]["out"]),
            "Registered argv/cwd differs")
    require(request["generated_pins"] == stage["generated_pins"], "Generated assets changed")
    proof=request["integrity_generation"]
    sealed=read_json(control/"integrity-target-proof.json")
    require(Path(sealed["receipt"]["path"])==control/f"integrity-{proof['generation']:06d}.json",
            "Registered generation receipt path differs")
    verify_pin(sealed["receipt"])
    require(proof==read_json(sealed["receipt"]["path"]) and proof["request"]==sealed["request"] and
            proof["request"]==read_json(control/"integrity-target-request.json") and proof["request"]["role"]=="target",
            "Registered target generation differs from sealed worker proof")
    valid_proof(proof,packet,stage,read_json(control/"supervisor-identity.json"),request=proof["request"],boundary=True)
    require(proof["request"]["collector"]==collector_identity,"Target generation collector differs")
    target = Process.open(request["target"]["pid"])
    authenticated=False
    try:
        target.verify(request["target"])
        identity = request["target"]
        require(identity["parent_pid"] == collector_identity["pid"] and
                identity["parent_creation_ticks"] == collector_identity["creation_ticks"] and
                identity["path"] == normalized(packet["renderer"]) and identity["sha256"] == packet["renderer_sha256"],
                "Target ownership differs")
        authenticated=True
        journal.append("target-registered", request)
        before_ack()
        valid_proof(proof,packet,stage,read_json(control/"supervisor-identity.json"),request=proof["request"],boundary=True)
        exclusive(control / "target-ack.json", {"request_sha256": digest(path), "packet_sha256": packet["packet_sha256"]})
        return target, identity
    except BaseException as error:
        if authenticated:
            error.owned_target=(target,request["target"])
        else:target.close()
        raise


def inventory(root):
    root = Path(root)
    rows = []
    for path in sorted(root.rglob("*")):
        require(not linklike(path), "Evidence contains a link/junction")
        if path.is_file():
            value = pin(path)
            value["path"] = str(path.relative_to(root))
            rows.append(value)
    return rows


def resume_receipt(control,identity):
    path=control/"target-resumed.json"
    if not path.exists():return None
    value=read_json(path)
    require(isinstance(value,dict) and set(value)=={"identity","utc","resume_native_call_attempt_monotonic"},
            "Malformed target resume receipt")
    attempt=value["resume_native_call_attempt_monotonic"]
    require(value["identity"]==identity and isinstance(value["utc"],str) and
            type(attempt) in (int,float) and math.isfinite(attempt) and 0<=attempt<=time.monotonic(),
            "Target resume receipt identity/time differs")
    return value


def terminate_owned(owned, journal):
    """Attempt every authenticated handle even when evidence storage has failed."""
    errors = []
    for role, process, identity in owned:
        if process is None or identity is None:
            continue
        try:
            terminated = process.kill(identity)
            kind, row = "termination", {"role": role, "identity": identity, "terminated": terminated}
        except BaseException as error:
            errors.append(role + ": " + str(error))
            kind, row = "termination-withheld", {"role": role, "error": str(error),"error_evidence":getattr(error,"evidence",None)}
        if hasattr(process,"take_exit_observations"):
            row["exit_observations"]=process.take_exit_observations()
        try:
            journal.append(kind, row)
        except BaseException as error:
            errors.append("termination receipt: " + str(error))
    return errors


def validate_stage(packet, stage, control, target_identity):
    """Second read-only validation in the supervisor, independent of collector."""
    from .prepare import frozen_oracle
    run = frozen_oracle(packet["oracle_source_root"])
    out = Path(stage["capture"]["out"])
    result = run.validate_run(out)
    for name in ("target-resumed.json", "target-exit.json"):
        receipt = read_json(control / name)
        require(receipt["identity"] == target_identity, "Target lifecycle identity changed")
    require(read_json(control / "target-exit.json")["returncode"] == 0, "Target lifecycle exit failed")
    raw = read_json(out / "native.renderer.json")
    require(raw["build"]["commit"] == packet["source"]["commit"] and raw["build"]["working_tree"] == "clean", "Actual native build changed")
    for key, expected in packet["native_device"].items():
        require(raw["build"]["vulkan"].get(key) == expected, "Independent native device mismatch")
    comparison = None
    if stage.get("compare_with"):
        comparison = run.compare_runs(Path(stage["compare_with"]), out)
        require(comparison["status"] == "PASS", "Independent exact state/RGB comparison failed")
    return {"validation": "PASS", "comparison": comparison}


def execute(packet, approval, output, *, readers=None):
    platform_check()
    packet_sha = validate_packet(packet)
    output = Path(output).resolve()
    require(not output.exists(), "Output must be a fresh exclusive directory")
    output.mkdir(parents=True)
    journal = Journal(output / "journal")
    journal.append("preregistration", packet)
    journal.append("approval", approval)
    packet = {**packet, "packet_sha256": packet_sha}
    exclusive(output / "packet.json", packet)
    gate = Gate(packet["stop_root"], packet_sha)
    locks, collector, target, job, watch,modules,integrity,roots = [], None, None, None, None,None,None,None
    collector_identity = target_identity = None
    status, error = "FAILED_STOP", "Incomplete supervisor"
    claim = gate.root / ("claim-" + packet_sha + ".json")
    try:
        for row in packet["files"]:
            locks.append(FileLock(row))
        roots=RootGuard(packet)
        expectations=root_expectations(packet)
        current_host=bounded_host_identity()
        journal.append("host-preflight",current_host)
        check_host_identity(packet["host_identity"],current_host)
        approve(packet, approval, packet_sha, gate)
        with gate:
            gate.check()
            require(not list(gate.root.glob("claim-*.json")), "Experiment already attempted or another supervisor owns gate")
            exclusive(claim, {"packet_sha256": packet_sha, "pid": os.getpid(), "utc": utc(), "automatic_retries": 0})
        baseline = packet["event_baseline"]
        watch = Watch(packet, baseline, journal, readers)
        # Complete both fresh preflight reads before any collector spawn.
        raw = watch.readers.call("telemetry")
        journal.append("preflight-telemetry", {"raw_utf8": raw.decode(errors="replace"), "readback": telemetry(raw, packet["telemetry"], packet["temperature_limit_c"])})
        snapshot = watch.readers.call("event", baseline)
        journal.append("preflight-events", snapshot)
        watch.baseline = continuity(baseline, snapshot)
        job = Job()
        watch.start()
        scanner = LogScanner()
        for index, stage in enumerate(packet["stages"]):
            control = output / f"{index:02d}-{stage['name']}"
            control.mkdir(exist_ok=False)
            self_process = Process.open(os.getpid())
            try:
                supervisor_identity = self_process.identity()
            finally:
                self_process.close()
            exclusive(control / "supervisor-identity.json", supervisor_identity)
            logs = [control / "collector-stdout.log", control / "collector-stderr.log",
                    Path(stage["capture"]["out"]) / "stdout.log", Path(stage["capture"]["out"]) / "stderr.log"]
            integrity=IntegrityWatch(packet,stage,control,supervisor_identity,expectations,scanner,logs,journal)
            integrity.start()
            while integrity.latest is None:
                watch.check();roots.check();integrity.check(require_ready=False)
                time.sleep(.02)
            heartbeat_index, next_heartbeat, heartbeat_stamp = 0, 0, 0
            collector_active=False
            def heartbeat():
                nonlocal heartbeat_index, next_heartbeat, heartbeat_stamp
                if time.monotonic() >= next_heartbeat:
                    receipt=integrity.check()
                    watch.check();roots.check()
                    stamp=time.monotonic()
                    if collector_active and collector.poll() is None:
                        require(0<=stamp-heartbeat_stamp<2,"Supervisor control heartbeat budget expired before publication")
                    exclusive(control / f"heartbeat-{heartbeat_index:06d}.json", {"packet_sha256": packet_sha,
                        "supervisor": supervisor_identity, "monotonic": stamp, "utc": utc(),"integrity_generation":receipt})
                    heartbeat_stamp=stamp
                    heartbeat_index += 1
                    next_heartbeat = time.monotonic() + .5
            heartbeat()
            require(not Path(stage["capture"]["out"]).exists(), "Stage output already exists/stale")
            with (control / "collector-stdout.log").open("xb") as stdout, (control / "collector-stderr.log").open("xb") as stderr:
                # Isolated interpreter; explicit new tooling path, then frozen
                # oracle import in collector. Never use the historical launcher.
                tooling_root = str(Path(__file__).resolve().parents[2])
                for lock in locks:
                    lock.verify()
                checks=verify_source(packet)
                current_host=bounded_host_identity()
                journal.append("host-stage-preflight",{"stage":stage["name"],"identity":current_host})
                check_host_identity(packet["host_identity"],current_host)
                source_proof={"schema":"physical-supervisor/source-preflight-v1","packet_sha256":packet_sha,
                              "stage":stage["name"],"source":packet["source"],"root":packet["oracle_source_root"],
                              "git":pin(packet["git"]),"supervisor":supervisor_identity,"checks":checks,"utc":utc()}
                exclusive(control/"source-preflight.json",source_proof)
                source_proof_pin=pin(control/"source-preflight.json")
                locks.append(FileLock(source_proof_pin))
                journal.append("source-preflight",{"receipt":source_proof_pin,"checks":checks})
                code = ("import sys;sys.path.insert(0," + repr(tooling_root) + ");"
                        "from tools.physical_supervisor.collector import main;"
                        "raise SystemExit(main(" + repr(str(output / "packet.json")) + "," + str(index) + "," + repr(str(control)) + ","+repr(source_proof_pin)+"))")
                argv = [packet["python"], "-I", "-B", "-c", code]
                watch.check()
                def pump():
                    watch.check();integrity.check();roots.check();heartbeat()
                spawn_proof,spawn_request=collector_boundary(packet,stage,control,supervisor_identity,pump)
                def final_collector_boundary():
                    gate.check();watch.check();roots.check();verify_registry(packet)
                    valid_proof(spawn_proof,packet,stage,supervisor_identity,request=spawn_request,boundary=True)
                    return proof_deadline(spawn_proof)
                with gate:
                    gate.check()
                    future(packet["expires_utc"])
                    roots.check();integrity.check()
                    valid_proof(spawn_proof,packet,stage,supervisor_identity,request=spawn_request,boundary=True)
                    verify_registry(packet)
                    require(not job.pids(), "Previous collector/target remains")
                    reject_unowned_renderer(packet["renderer"])
                    gate.check()
                    collector = Process.spawn(argv, tooling_root, stdout, stderr, job=job, env=sealed_environment(packet),before_create=final_collector_boundary)
                    collector_identity = collector.identity()
                    exclusive(control/"collector-identity.json",collector_identity)
                    journal.append("collector-spawn", {"argv": argv, "identity": collector_identity, "state": "SUSPENDED",
                        "create_native_call_attempt_monotonic":collector.create_native_call_attempt_monotonic})
                    require(not hasattr(collector, "assignment_error"), getattr(collector, "assignment_error", "Job assignment failed"))
                    require(collector_identity["path"] == normalized(packet["python"]), "Collector executable changed")
                    next_heartbeat = 0
                    heartbeat()
                    watch.check()
                    gate.check()
                    roots.check()
                    valid_proof(spawn_proof,packet,stage,supervisor_identity,request=spawn_request,boundary=True)
                    collector.resume(collector_identity,before_resume=final_collector_boundary)
                    collector_active=True
                    journal.append("collector-resumed", {"identity": collector_identity,
                        "resume_native_call_attempt_monotonic":collector.resume_native_call_attempt_monotonic})
                started = time.monotonic()
                target, target_identity = None, None
                gate_busy=None
                while True:
                    watch.check()
                    if modules:modules.check()
                    integrity.check();roots.check()
                    if gate.acquire(timeout=0):
                        try:
                            gate_entered=time.monotonic()
                            gate_busy=None
                            gate.check()
                            if target is None:
                                watch.check()
                                def registration_health():
                                    watch.check();integrity.check();roots.check();verify_registry(packet)
                                target, target_identity = _registration(packet, stage, control, collector, collector_identity, journal,registration_health)
                                if target is not None:
                                    target_registered_at = time.monotonic()
                            allowed = {collector.pid} | ({target.pid} if target else set())
                            require(job.pids() <= allowed, "Unregistered/orphan process in containment job")
                            resumed=resume_receipt(control,target_identity) if target is not None else None
                            settle_deadline=min(heartbeat_stamp+2,gate_entered+GATE_BUSY_LIMIT,
                                                started+stage["deadline_seconds"]+30,
                                                target_registered_at+stage["deadline_seconds"]) if resumed else None
                            observations=reject_unowned_renderer(packet["renderer"], [target_identity] if target_identity else [],
                                owned=[target] if resumed else [],settle_deadline=settle_deadline)
                            if observations:journal.append("owned-exit-observation",{"stage":stage["name"],"observations":observations})
                            require(time.monotonic()-gate_entered<GATE_BUSY_LIMIT,"Shared gate critical section stalled")
                            require(time.monotonic()-heartbeat_stamp<2,"Supervisor control heartbeat budget expired")
                            roots.check()
                            verify_registry(packet)
                        finally:
                            gate.__exit__()
                    else:
                        if gate_busy is None:gate_busy=time.monotonic()
                        require(time.monotonic()-gate_busy < GATE_BUSY_LIMIT,"Shared gate critical section stalled")
                    code = collector.poll()
                    if target is not None and modules is None and packet.get("module_policy") and resume_receipt(control,target_identity):
                        modules=ModuleWatch(packet,target,target_identity,journal,watch,
                            target_deadline=target_registered_at+stage["deadline_seconds"]);modules.start()
                    if target is not None and target.poll() is None:
                        require(time.monotonic() - target_registered_at <= stage["deadline_seconds"], "Independent renderer deadline exceeded")
                        require((control / "target-resumed.json").exists() or time.monotonic() - target_registered_at <= 2,
                                "Target resume receipt stalled/missing")
                    require(time.monotonic() - started <= stage["deadline_seconds"] + 30,
                            "Collector deadline/hang (includes bounded preparation/finalization)")
                    if target is None:
                        require(time.monotonic() - started <= 30, "Collector failed to register target")
                    heartbeat()
                    if code is not None:
                        require(code == 0 and target is not None, "Collector failed/exited without target")
                        require(target.poll() == 0, "Renderer remained/orphaned or exited with error")
                        if packet.get("module_policy"):
                            require(modules is not None,"Actual module observer never started")
                            modules.finish(require_complete=True);modules=None
                        result = read_json(control / "stage-result.json")
                        require(result["packet_sha256"] == packet_sha and result["stage"] == stage["name"] and
                                result["status"] == "COLLECTED_PENDING_ACCEPTANCE", "Stale/failed stage result")
                        require((control / "target-exit.json").is_file() and (control / "target-resumed.json").is_file(),
                                "Missing target lifecycle receipts")
                        for row in (result["run"], result["native"]):
                            verify_pin(row)
                        for relative in stage["required_outputs"]:
                            require((Path(stage["capture"]["out"]) / relative).is_file(), "Missing required native evidence")
                        independent = validate_stage(packet, stage, control, target_identity)
                        journal.append("independent-stage-validation", independent)
                        journal.append("collector-exit", {"identity": collector_identity, "returncode": code, "result": result})
                        break
                    time.sleep(.05)
                # Continue observing after every stage, including the final one,
                # so late-arriving native events/fault output invalidate success.
                until = time.monotonic() + GRACE_SECONDS
                while time.monotonic() < until:
                    watch.check()
                    heartbeat()
                    integrity.check();roots.check()
                    with gate:
                        gate.check()
                        require(not job.pids(), "Orphan child after collector exit")
                    time.sleep(.05)
                # Fence every stage, not only the last: finish in-flight async
                # reads, then complete a new read whose watermark is after grace.
                watch.finish()
                fence = watch.readers.call("event", watch.baseline)
                journal.append("stage-event-fence", fence)
                fence_baseline = continuity(watch.baseline, fence)
                raw = watch.readers.call("telemetry")
                journal.append("stage-telemetry-fence", {"raw_utf8": raw.decode(errors="replace"), "readback": telemetry(raw, packet["telemetry"], packet["temperature_limit_c"])})
                with gate:
                    gate.check()
                    roots.check();integrity.check();verify_registry(packet)
                    for lock in locks:
                        lock.verify()
                    journal.append("stage-complete", {"stage": stage["name"], "late_event_grace_seconds": 15})
                    journal.append("stage-artifacts", {"root": stage["capture"]["out"], "files": inventory(stage["capture"]["out"])})
                integrity.finish();last_integrity=integrity;integrity=None
                watch = Watch(packet, fence_baseline, journal, watch.readers)
                watch.start()
                target.close()
                target = None
                collector.close()
                collector = None
        watch.finish()
        # No process can launch again. Fence observers outside the spawn lock;
        # the final serialized native checks still reject any intervening STOP.
        final = watch.readers.call("event", watch.baseline)
        watch.baseline = continuity(watch.baseline, final)
        journal.append("final-events", final)
        raw = watch.readers.call("telemetry")
        journal.append("final-telemetry", {"raw_utf8": raw.decode(errors="replace"), "readback": telemetry(raw, packet["telemetry"], packet["temperature_limit_c"])})
        # No target/collector remains. Complete an explicit bounded fresh deep
        # audit after the final asynchronous observers before final acceptance.
        final_integrity_start=time.monotonic()
        last_integrity.audit_request=None
        final_integrity_checks=last_integrity.reader.call("telemetry")
        journal.append("integrity-final-fence",{"schema":"physical-supervisor/integrity-final-fence-v1","packet_sha256":packet_sha,"stage":stage["name"],
            "supervisor":supervisor_identity,"started_monotonic":final_integrity_start,
            "finished_monotonic":time.monotonic(),"checks":final_integrity_checks,"status":"PASS","policy":last_integrity.latest[0]["policy"]})
        with gate:
            gate.check()
            require(not job.pids(), "Final orphan process")
            roots.check();verify_registry(packet)
            status, error = "COLLECTED_PENDING_ACCEPTANCE", ""
    except BaseException as caught:
        status = "FAILED_STOP"
        error = str(caught)
        if target is None and hasattr(caught,"owned_target"):
            target,target_identity=caught.owned_target
        # Contain authenticated handles before waiting on a gate/disk that may
        # itself be the failure. No collector in this design may launch twice.
        termination_errors = terminate_owned((("target", target, target_identity), ("collector", collector, collector_identity)), journal)
        try:
            with gate:
                gate.stop(error)
        except BaseException as latch_error:
            error += "; STOP write failure: " + str(latch_error)
        # Kill target first while its authenticated collector parent is retained.
        error += ("; " + "; ".join(termination_errors)) if termination_errors else ""
        try:
            journal.append("failure", {"error": error, "partial_reader_evidence": getattr(caught, "evidence", None)})
        except BaseException as receipt_error:
            error += "; failure receipt: " + str(receipt_error)
    finally:
        if integrity:
            try:integrity.finish()
            except BaseException as integrity_error:
                status,error="FAILED_STOP",error+"; integrity completion: "+str(integrity_error)
                try:
                    with gate:gate.stop(error)
                except BaseException:pass
        if modules:
            try:modules.finish(require_complete=False)
            except BaseException as module_error:
                status,error="FAILED_STOP",error+"; actual module completion: "+str(module_error)
                try:
                    with gate:gate.stop(error)
                except BaseException:pass
        if watch:
            try:
                watch.finish()
            except BaseException as observer_error:
                status, error = "FAILED_STOP", error + "; observer completion: " + str(observer_error)
                with gate:
                    gate.stop(error)
        if job:
            try:
                remaining = sorted(job.pids())
                if remaining:
                    status, error = "FAILED_STOP", error + "; owned/unidentified processes remain; termination withheld"
                    with gate:
                        gate.stop(error)
                journal.append("final-job-inventory", {"remaining_pids": remaining})
            except BaseException as inventory_error:
                status, error = "FAILED_STOP", error + "; final containment inventory: " + str(inventory_error)
                try:
                    with gate:
                        gate.stop(error)
                except BaseException:
                    pass  # containment was already attempted; report storage failure below
            finally:
                job.close()
        for process in (target, collector):
            if process:
                process.close()
        for lock in locks:
            lock.close()
        if roots:roots.close()
        journal.append("final", {"status": status, "error": error, "physical_gpu_qualified": False,
                                  "performance_accepted": False, "automatic_retries": 0})
        phase_artifacts = [{"root": stage["capture"]["out"], "files": inventory(stage["capture"]["out"])}
                           for stage in packet["stages"] if Path(stage["capture"]["out"]).is_dir()]
        exclusive(output / "manifest.json", {"schema": "physical-supervisor/artifacts-v1", "files": inventory(output), "stage_artifacts": phase_artifacts,
                                               "journal_head_sha256": Journal.audit(output / "journal")})
        exclusive(output / "result.json", {"status": status, "error": error, "manifest": pin(output / "manifest.json"),
                                             "physical_gpu_qualified": False, "performance_accepted": False})
    return read_json(output / "result.json")
