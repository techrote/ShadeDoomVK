"""Isolated frozen-oracle adapter; only registered suspended targets may run.

The accepted renderer source is imported from a separately pinned checkout.
The --version subprocess is never executed: its packet-declared bytes are
labelled as such, and the real renderer's native build record must agree.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import os
from pathlib import Path
import subprocess
import sys
import time
import types

from .common import Gate, Stop, canonical, digest, exclusive, normalized, pin, read_json, require, utc, verify_pin, verify_roots, sealed_environment, verify_registry, future, source_check_requests,verify_oracle_python_pins
from .windows import FileLock, Process, RootGuard, reject_unowned_renderer
from .integrity import boundary_request, valid_proof, responsive_gate, proof_deadline


class ParentGuard:
    def __init__(self, packet, control, stage):
        self.packet, self.control, self.stage = packet, control, stage
        self.expected = read_json(control / "supervisor-identity.json")
        self.parent = Process.open(self.expected["pid"])
        self.parent.verify(self.expected)

    def check(self):
        require(self.parent.poll() is None, "Supervisor died; observer protection unavailable")
        paths = sorted(self.control.glob("heartbeat-*.json"))
        require(paths, "Supervisor heartbeat missing")
        heartbeat = read_json(paths[-1])
        require(heartbeat["packet_sha256"] == self.packet["packet_sha256"] and heartbeat["supervisor"] == self.expected,
                "Supervisor heartbeat identity changed")
        age = time.monotonic() - heartbeat["monotonic"]
        require(0 <= age < 2, "Supervisor heartbeat/observers stalled")
        receipt=heartbeat["integrity_generation"]
        require(Path(receipt["path"]).parent==self.control,"Heartbeat integrity proof path differs")
        verify_pin(receipt)
        proof=read_json(receipt["path"])
        require(Path(receipt["path"]).name==f"integrity-{proof['generation']:06d}.json","Heartbeat generation name differs")
        valid_proof(proof,self.packet,self.stage,self.expected)

    def close(self):
        self.parent.close()


def gated_target(packet, stage, control, argv, cwd, stdout, stderr, *, env=None):
    """One attempt only; collector remains the target's actual native parent."""
    require(argv == stage["expected_argv"] and normalized(cwd) == normalized(stage["capture"]["out"]),
            "Oracle target argv/cwd differs from approved packet")
    gate = Gate(packet["stop_root"], packet["packet_sha256"])
    locks, child, identity, guard, roots = [], None, None, None, None
    try:
        guard = ParentGuard(packet, control, stage)
        guard.check()
        expected_env = sealed_environment(packet)
        require(env is None or env == expected_env, "Oracle requested an unreviewed renderer environment")
        for row in stage["generated_pins"]:
            verify_pin(row)
            locks.append(FileLock(row))
        roots=RootGuard(packet)
        proof,proof_request=boundary_request(packet,stage,control,guard,roots)
        mutable_lock=None;mutable_release_monotonic=None
        def final_boundary():
            nonlocal mutable_release_monotonic
            gate.check();guard.check();roots.check();verify_registry(packet)
            valid_proof(proof,packet,stage,guard.expected,request=proof_request,boundary=True)
            if mutable_lock is not None and mutable_lock.handle:
                mutable_lock.verify()
                valid_proof(proof,packet,stage,guard.expected,request=proof_request,boundary=True)
                mutable_lock.close()
                mutable_release_monotonic=time.monotonic()
                gate.check();guard.check();roots.check();verify_registry(packet)
                valid_proof(proof,packet,stage,guard.expected,request=proof_request,boundary=True)
            return proof_deadline(proof)
        def health():guard.check();roots.check()
        with responsive_gate(gate,health):
            gate.check()
            future(packet["expires_utc"])
            reject_unowned_renderer(packet["renderer"])
            guard.check();roots.check()
            valid_proof(proof,packet,stage,guard.expected,request=proof_request,boundary=True)
            verify_registry(packet)
            gate.check()
            require(not (control / "target-request.json").exists(), "No retry/second renderer allowed")
            child = Process.spawn(argv, cwd, stdout, stderr, env=expected_env,before_create=final_boundary)
            identity = child.identity()
            require(identity["path"] == normalized(packet["renderer"]) and
                    identity["sha256"] == packet["renderer_sha256"], "Renderer identity mismatch")
            owner = Process.open(os.getpid())
            try:
                owner_identity = owner.identity()
            finally:
                owner.close()
            require(identity["parent_pid"] == owner_identity["pid"] and
                    identity["parent_creation_ticks"] == owner_identity["creation_ticks"], "Target parent mismatch")
            request = {"packet_sha256": packet["packet_sha256"], "stage": stage["name"],
                       "collector": owner_identity, "target": identity, "argv": argv, "cwd": str(cwd),
                       "generated_pins": stage["generated_pins"], "created_utc": utc(), "state": "SUSPENDED"}
            request["integrity_generation"]=proof
            request["create_native_call_attempt_monotonic"]=child.create_native_call_attempt_monotonic
            exclusive(control / "target-request.json", request)
        until = time.monotonic() + 10
        while not (control / "target-ack.json").exists():
            guard.check()
            sealed_environment(packet)
            verify_registry(packet)
            with responsive_gate(gate,health):
                gate.check()
            require(time.monotonic() < until, "Parent registration/handshake timed out")
            time.sleep(.02)
        ack = read_json(control / "target-ack.json")
        require(ack == {"request_sha256": digest(control / "target-request.json"), "packet_sha256": packet["packet_sha256"]},
                "Parent registration acknowledgement mismatch")
        until = time.monotonic() + stage["deadline_seconds"]
        # All generated assets were authenticated/locked before the generation
        # request. Only the exact live mutable config needs a final byte check.
        with responsive_gate(gate,health):
            gate.check()
            guard.check()
            future(packet["expires_utc"])
            reject_unowned_renderer(packet["renderer"], [identity])
            roots.check()
            valid_proof(proof,packet,stage,guard.expected,request=proof_request,boundary=True)
            verify_registry(packet)
            mutable = stage.get("mutable_runtime_config")
            if mutable is not None:
                require(Path(mutable["path"]) == Path(stage["capture"]["out"]) / "fixture.ini" and
                        mutable in stage["generated_pins"], "Unexpected mutable runtime exemption")
                for lock in locks:
                    if lock.row == mutable:
                        lock.verify()
                        # GZDoom normally persists the live -config on exit.
                        # Original input/fixture.ini remains locked. Release the
                        # exact live copy only after its final under-gate check.
                        mutable_lock=lock
                require(mutable_lock is not None,"Mutable configuration lock missing")
                exclusive(control / "mutable-config-release-ready.json", {"initial": mutable,
                    "state":"PLANNED_ONLY; live configuration remains locked until final native resume callback","utc":utc()})
            gate.check()
            guard.check()
            child.resume(identity,before_resume=final_boundary)
            if mutable is not None:
                exclusive(control / "mutable-config-released.json", {"initial": mutable,
                    "policy": "only live fixture.ini may be persisted by the owned renderer after resume",
                    "immutable_original": str(Path(stage["capture"]["out"]) / "input/fixture.ini"),"utc":utc(),
                    "release_monotonic":mutable_release_monotonic,
                    "resume_native_call_attempt_monotonic":child.resume_native_call_attempt_monotonic})
            exclusive(control / "target-resumed.json", {"identity": identity, "utc": utc(),
                "resume_native_call_attempt_monotonic":child.resume_native_call_attempt_monotonic})
        while child.poll() is None:
            guard.check()
            def running_health():
                health()
                require(time.monotonic()<until,"Renderer process deadline exceeded")
            with responsive_gate(gate,running_health):
                gate.check()
            require(time.monotonic() < until, "Renderer process deadline exceeded")
            time.sleep(.05)
        code = child.poll()
        exclusive(control / "target-exit.json", {"identity": identity, "returncode": code, "utc": utc()})
        require(code == 0, "Renderer exited unsuccessfully")
        return subprocess.CompletedProcess(argv, code)
    except BaseException as error:
        problems = [str(error)]
        # Containment does not wait for a potentially wedged gate or disk.
        # The retained target handle is already authenticated and no new spawn
        # is permitted from this failed call.
        termination = None
        try:
            if child is not None and identity is not None:
                termination = {"identity": identity, "terminated": child.kill(identity), "utc": utc()}
        except BaseException as termination_error:
            problems.append("Termination withheld: " + str(termination_error))
        try:
            with gate:
                gate.stop(error)
        except BaseException as stop_error:
            problems.append("STOP write failed: " + str(stop_error))
        try:
            if termination:
                exclusive(control / "collector-target-termination.json", {**termination, "errors": problems})
            else:
                exclusive(control / "collector-termination-withheld.json", {"errors": problems, "utc": utc()})
        except OSError:
            pass  # no receipt can be persisted; re-raise the original failure
        raise
    finally:
        if child:
            child.close()
        for lock in locks:
            lock.close()
        if guard:
            guard.close()
        if roots:
            roots.close()


def source_proof(packet,stage,control,receipt_pin):
    require(Path(receipt_pin["path"])==control/"source-preflight.json","Source preflight receipt path differs")
    verify_pin(receipt_pin)
    proof=read_json(receipt_pin["path"])
    require(proof["schema"]=="physical-supervisor/source-preflight-v1" and proof["packet_sha256"]==packet["packet_sha256"] and
            proof["stage"]==stage["name"] and proof["source"]==packet["source"] and
            normalized(proof["root"])==normalized(packet["oracle_source_root"]),"Stale/wrong source preflight proof")
    require(proof["supervisor"]==read_json(control/"supervisor-identity.json"),"Source preflight supervisor identity differs")
    require(proof["git"]==pin(packet["git"]),"Source preflight Git identity differs")
    requests=source_check_requests(packet)
    require(len(proof["checks"])==len(requests),"Incomplete source preflight proof")
    for check,(argv,expected) in zip(proof["checks"],requests):
        require(check["argv"]==argv and check["returncode"]==0 and check["stdout_utf8"].splitlines()==expected,
                "Source preflight transcript differs")
    return proof


def prepare_subprocess_adapter(packet,stage,control,receipt_pin):
    source_proof(packet,stage,control,receipt_pin)
    used=False
    def preverified(argv,**kwargs):
        nonlocal used
        expected=["git","cat-file","-e",packet["source"]["commit"]+"^{commit}"]
        require(not used and argv==expected and set(kwargs)=={"cwd","capture_output","check"} and
                normalized(kwargs["cwd"])==normalized(packet["oracle_source_root"]) and
                kwargs["capture_output"] is True and kwargs["check"] is True,
                "Unapproved preparation subprocess; no child created")
        with Gate(packet["stop_root"],packet["packet_sha256"]) as gate:
            gate.check();future(packet["expires_utc"])
            source_proof(packet,stage,control,receipt_pin)
            exclusive(control/"prepared-commit-existence.json",{
                "provenance":"DECLARED_FROM_SEALED_PARENT_GIT_CHECK","argv":argv,"cwd":str(kwargs["cwd"]),
                "source_preflight":receipt_pin,"actual_collector_git_process_created":False})
        used=True
        return subprocess.CompletedProcess(argv,0,stdout=b"",stderr=b"")
    def denied(*args,**kwargs):
        raise Stop("Unapproved preparation subprocess API; no child created")
    return types.SimpleNamespace(run=preverified,SubprocessError=subprocess.SubprocessError,
        CalledProcessError=subprocess.CalledProcessError,TimeoutExpired=subprocess.TimeoutExpired,
        PIPE=subprocess.PIPE,STDOUT=subprocess.STDOUT,DEVNULL=subprocess.DEVNULL,
        Popen=denied,call=denied,check_call=denied,check_output=denied,getoutput=denied,getstatusoutput=denied)


def run_oracle(packet, stage, control,receipt_pin):
    verify_oracle_python_pins(packet)
    # Do not let current tooling source shadow the frozen oracle package.
    for name in list(sys.modules):
        if name in ("tools.renderer_oracle","tools.pf_oracle") or name.startswith(("tools.renderer_oracle.","tools.pf_oracle.")):
            del sys.modules[name]
    tools_package = importlib.import_module("tools")
    tools_package.__path__ = [str(Path(packet["oracle_source_root"]) / "tools")]
    run = importlib.import_module("tools.renderer_oracle.run")
    require(normalized(run.__file__) == normalized(Path(packet["oracle_source_root"]) / "tools/renderer_oracle/run.py"),
            "Wrong frozen oracle module")
    version = packet["declared_version_utf8"].encode("utf-8")
    require(run.version_identity(version) == (packet["source"]["commit"], "clean"), "Declared build identity invalid")
    original_subprocess = run.subprocess
    preparation=run.preparation_module()
    original_prepare_subprocess=preparation.subprocess
    preparation.subprocess=prepare_subprocess_adapter(packet,stage,control,receipt_pin)
    original_write = run.write_json
    def labelled_write(path, value):
        if Path(path).name in ("run.json", "request.json"):
            value = {**value, "version_provenance": "DECLARED_NOT_EXECUTED",
                     "version_declaration": "version.txt contains packet-declared expected bytes, not executed --version output; actual native build must agree"}
        return original_write(path, value)
    run.write_json = labelled_write
    calls = 0
    def intercepted(argv, **kwargs):
        nonlocal calls
        with Gate(packet["stop_root"], packet["packet_sha256"]) as gate:
            gate.check()
        if argv == [packet["renderer"], "--version"]:
            require(calls == 0, "Repeated version request")
            exclusive(control / "declared-version.json", {"provenance": "DECLARED_NOT_EXECUTED",
                "sha256": hashlib.sha256(version).hexdigest(), "actual_native_build_required": True})
            return subprocess.CompletedProcess(argv, 0, stdout=version, stderr=b"")
        calls += 1
        require(calls == 1, "Collector attempted additional renderer/subprocess; no retry")
        require(kwargs.get("timeout") == 180 and kwargs.get("check") is False, "Oracle launch policy changed")
        require(kwargs.get("stdout") is not None and kwargs.get("stderr") is not None, "Missing raw output handles")
        return gated_target(packet, stage, control, list(argv), kwargs["cwd"], kwargs["stdout"], kwargs["stderr"], env=kwargs.get("env"))
    # Keep both shadows module-local. The sole preparation Git fact was checked
    # by the supervisor before this collector entered the containment job.
    # Pure source/member/recipe regeneration checks still execute unmodified.
    run.subprocess = types.SimpleNamespace(**{**vars(subprocess), "run": intercepted})
    try:
        args = argparse.Namespace(**stage["capture"])
        for field in ("exe", "iwad", "prepared", "out"):
            setattr(args, field, Path(getattr(args, field)))
        result = run.capture(args)
        require(calls == 1 and result["status"] == "COLLECTED", "Capture did not collect one target")
        require(result["build"]["commit"] == packet["source"]["commit"] and
                result["build"]["working_tree"] == "clean", "Actual native renderer build mismatch")
        vulkan = result["build"]["vulkan"]
        require(vulkan["available"] and vulkan["device_type"] in (1, 2), "Actual physical Vulkan identity absent")
        for key, expected in packet["native_device"].items():
            require(vulkan.get(key) == expected, "Native device identity differs: " + key)
        run.validate_run(Path(stage["capture"]["out"]))
        comparison = None
        if stage.get("compare_with"):
            comparison = run.compare_runs(Path(stage["compare_with"]), Path(stage["capture"]["out"]))
            require(comparison["status"] == "PASS", "Exact state/RGB comparison failed")
        return {"status": "COLLECTED_PENDING_ACCEPTANCE", "run": pin(Path(stage["capture"]["out"]) / "run.json"),
                "native": pin(Path(stage["capture"]["out"]) / "native.renderer.json"), "comparison": comparison,
                "version_provenance": "DECLARED_NOT_EXECUTED; actual native build checked independently"}
    finally:
        run.subprocess = original_subprocess
        preparation.subprocess=original_prepare_subprocess
        run.write_json = original_write


def main(packet_path, stage_index, control_path,receipt_pin):
    packet = read_json(packet_path)
    supplied_sha = packet.pop("packet_sha256")
    require(hashlib.sha256(canonical(packet)).hexdigest() == supplied_sha, "Collector packet changed")
    packet["packet_sha256"] = supplied_sha
    stage = packet["stages"][int(stage_index)]
    control = Path(control_path)
    gate = Gate(packet["stop_root"], supplied_sha)
    try:
        with gate:
            gate.check()
        result = run_oracle(packet, stage, control,receipt_pin)
        with gate:
            gate.check()
            exclusive(control / "stage-result.json", {"packet_sha256": supplied_sha, "stage": stage["name"],
                                                       "finished_utc": utc(), **result})
        return 0
    except BaseException as error:
        with gate:
            gate.stop(error)
        exclusive(control / "stage-failed.json", {"packet_sha256": supplied_sha, "stage": stage["name"],
                                                  "status": "FAILED_STOP", "error": str(error), "utc": utc()})
        return 1
