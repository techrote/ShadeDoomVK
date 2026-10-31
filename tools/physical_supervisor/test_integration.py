"""Actual native supervisor/collector integration with a synthetic CPU oracle.

The copied, uniquely named Python executable is the ONLY target. The fixture
oracle synthesizes test records and is never advertised as renderer evidence.
"""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from .common import canonical, exclusive, pin, read_json, utc, environment_policy, source_check_requests, INTEGRITY_POLICY
from .readers import BoundedReaders,bounded_host_identity
from .test_supervisor import EXPECTED, baseline, batch, raw


FAKE_ORACLE = '''import json, subprocess, os, threading, time
import types
from pathlib import Path
_preparation=types.SimpleNamespace(subprocess=subprocess)
def preparation_module():return _preparation
def write_json(path, value):
    Path(path).write_text(json.dumps(value))
def version_identity(value):
    return value.decode().split("Commit: ")[1].splitlines()[0], "clean"
def validate_run(path):
    path = Path(path)
    result = json.loads((path / "run.json").read_text())
    if result.get("observer") != "PASS": raise ValueError("synthetic observer validation failure")
    if not (path / "marker.txt").is_file(): raise ValueError("synthetic native output missing")
    return result
def compare_runs(left, right):
    if (Path(left)/"marker.txt").read_bytes() != (Path(right)/"marker.txt").read_bytes():
        return {"status":"FAIL"}
    return {"status":"PASS"}
def capture(args):
    out = Path(args.out); out.mkdir(parents=True)
    (out/"fixture.txt").write_bytes(b"pinned synthetic fixture")
    (out/"input").mkdir()
    (out/"fixture.ini").write_bytes(b"pinned synthetic fixture")
    (out/"input"/"fixture.ini").write_bytes(b"pinned synthetic fixture")
    if args.cpu_fault == "config-changed": (out/"fixture.ini").write_bytes(b"changed before spawn")
    (out/"cache").mkdir(); (out/"cache"/"cpu-cache.txt").write_text("synthetic cache")
    version = subprocess.run([str(args.exe), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if args.cpu_fault == "collector-die":
        def suicide():
            while not (out/"started.txt").exists(): time.sleep(.01)
            os._exit(17)
        threading.Thread(target=suicide, daemon=True).start()
    with (out/"stdout.log").open("wb") as stdout, (out/"stderr.log").open("wb") as stderr:
        subprocess.run([str(args.exe), "-I", "-B", "-c", args.cpu_script], cwd=out,
                       stdout=stdout, stderr=stderr, timeout=180, check=False)
    build = {"commit":args.expected_commit,"working_tree":"clean", "vulkan":{
        "available":True,"device_type":2,"vendor_id":1,"device_id":2,"driver_version_raw":3}}
    write_json(out/"native.renderer.json", {"build":build})
    (out/"native.png").write_bytes(b"synthetic CPU image, not renderer evidence")
    result = {"status":"COLLECTED", "build":build,"observer":"FAIL" if args.cpu_fault=="observer" else "PASS"}
    write_json(out/"run.json",result)
    write_json(out/"request.json",{"synthetic_cpu_only":True})
    return result
'''


def synthetic_source_checks(packet):
    """Explicitly synthetic provenance for the CPU-only fake oracle controls."""
    return [{"argv":argv,"returncode":0,"stdout_utf8":"\n".join(expected)+("\n" if expected else ""),"stderr_utf8":""}
            for argv,expected in source_check_requests(packet)]


@unittest.skipUnless(os.name == "nt", "Native Windows supervisor/collector integration")
class EngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="physical-supervisor-integration-")
        self.root = Path(self.temp.name)
        runtime = self.root / "cpu-runtime"
        runtime.mkdir()
        self.cpu = runtime / "qualification_benign_cpu.exe"
        shutil.copyfile(sys.executable, self.cpu)
        for path in Path(sys.executable).parent.glob("python*.dll"):
            shutil.copyfile(path, runtime / path.name)
        # A private _pth pins the copied interpreter to the actual CPU stdlib.
        (runtime / "qualification_benign_cpu._pth").write_text("\n".join(sys.path) + "\n")
        source = self.root / "synthetic-source"
        oracle = source / "tools/renderer_oracle"
        oracle.mkdir(parents=True)
        (oracle / "run.py").write_text(FAKE_ORACLE)
        pf=source/"tools/pf_oracle";pf.mkdir()
        (pf/"__init__.py").write_text("# Synthetic CPU-only dependency package\n")
        (pf/"run_freeze_dense_runtime.py").write_text("# Synthetic decoder, never imported\n")
        fixture = self.root / "fixture-original.txt"
        fixture.write_bytes(b"pinned synthetic fixture")
        stop = self.root / "stop"
        stop.mkdir()
        exclusive(stop / "HELD.json", {"status": "HELD"})
        expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
        self.packet = {"schema": "physical-supervisor/packet-v1", "experiment_id": "CPU-DIAG-TEST", "kind": "diagnostic",
            "integrity_policy":dict(INTEGRITY_POLICY),
            "source": {"commit": "1"*40,"tree":"2"*40}, "created_utc": utc(), "expires_utc": expires,
            "host_identity":bounded_host_identity(),
            "stop_root": str(stop), "python": sys.executable, "renderer":str(self.cpu),
            "git":sys.executable,
            "renderer_sha256":pin(self.cpu)["sha256"], "nvidia_smi":sys.executable,"oracle_source_root":str(source),
            "declared_version_utf8":"ShadeDoomVK synthetic CPU declaration\nCommit: " + "1"*40 + "\nWorking tree: clean\n",
            "native_device":{"device_type":2,"vendor_id":1,"device_id":2,"driver_version_raw":3},
            "telemetry":EXPECTED,"temperature_limit_c":80,"event_baseline":baseline(),"automatic_retries":0,
            "environment_policy":environment_policy(),
            "registry_policy":[],
            "runtime_roots":[{"path":str(runtime),"files":[str(p) for p in runtime.iterdir()]},
                             {"path":str(oracle),"files":[str(oracle/"run.py")]}]}
        self.packet["runtime_roots"].append({"path":str(pf),"files":[str(p) for p in pf.iterdir()]})
        self.packet["files"] = [pin(p) for p in [*runtime.iterdir(), oracle/"run.py",*pf.iterdir(), fixture, Path(sys.executable)]]
        self.stages = []
        for name in ("compositing","shadow-boundary-1","shadow-boundary-2"):
            out = self.root / "captures" / name
            script = "from pathlib import Path;Path('marker.txt').write_text('CPU benign success')"
            capture = {"exe":str(self.cpu),"iwad":str(fixture),"prepared":str(source),"out":str(out),
                       "expected_commit":"1"*40,"cpu_script":script,"cpu_fault":"none"}
            self.stages.append({"name":name,"mode":"oracle","deadline_seconds":5,"capture":capture,
                "expected_argv":[str(self.cpu),"-I","-B","-c",script],
                "generated_pins":[{**pin(fixture),"path":str(out/"fixture.txt")}],
                "required_outputs":["run.json","native.renderer.json","native.png","marker.txt"]})
        self.packet["stages"] = self.stages

    def tearDown(self):
        # Native containment has completed before cleanup; failure leaves a
        # diagnostic traceback rather than deleting a live process's artifacts.
        self.doCleanups()
        evidence_root = os.environ.get("SDVK_CPU_FAILURE_EVIDENCE_ROOT")
        outcome = getattr(self, "_outcome", None)
        result = getattr(outcome, "result", None)
        failed = result is not None and any(test is self for test, _ in (*result.failures, *result.errors))
        if evidence_root and failed:
            # Only explicitly synthetic CPU fixtures live in this directory.
            # Copy before TemporaryDirectory cleanup; keep failed receipts,
            # journals, native errors and output together for investigation.
            destination = Path(evidence_root) / (self.id() + "-" + str(time.time_ns()))
            shutil.copytree(self.root, destination)
            print("Retained failed CPU fixture: " + str(destination), flush=True)
        self.temp.cleanup()

    def run_engine(self, *, event_function=None,telemetry_function=None):
        from . import supervisor
        packet_sha = hashlib.sha256(canonical(self.packet)).hexdigest()
        approval = {"schema":"physical-supervisor/approval-v1","experiment_id":self.packet["experiment_id"],
                    "packet_sha256":packet_sha,"phrase":"AUTHORIZE CPU-DIAG-TEST (three diagnostic processes only)",
                    "decided_utc":utc(),"expires_utc":self.packet["expires_utc"]}
        readers = BoundedReaders(telemetry_function or (lambda:raw()), event_function or (lambda previous:batch()))
        # Only provenance is synthetic. Actual engine, collector, locks, handles,
        # registration, heartbeat, job inventory and target execution are real.
        with patch.object(supervisor,"validate_packet",return_value=packet_sha), \
             patch.object(supervisor,"verify_source",side_effect=synthetic_source_checks), patch.object(supervisor,"GRACE_SECONDS",.05):
            return supervisor.execute(self.packet, approval, self.root/"control",readers=readers)

    def spawn_count(self):
        return len(list((self.root/"control/journal").glob("*-collector-spawn.json")))

    def fault(self, kind, script=None):
        self.stages[0]["capture"]["cpu_fault"] = kind
        if script:
            self.stages[0]["capture"]["cpu_script"] = script
            self.stages[0]["expected_argv"][-1] = script

    def test_three_serial_stages_and_independent_validation(self):
        result = self.run_engine()
        self.assertEqual(result["status"],"COLLECTED_PENDING_ACCEPTANCE",result)
        self.assertEqual(self.spawn_count(),3)
        self.assertEqual(len(list((self.root/"control/journal").glob("*-independent-stage-validation.json"))),3)
        manifest = read_json(self.root/"control/manifest.json")
        self.assertEqual(len(manifest["stage_artifacts"]),3)
        self.assertTrue(any(row["path"].endswith("cpu-cache.txt") for row in manifest["stage_artifacts"][0]["files"]))

    def test_preflight_bad_telemetry_retained_before_any_collector(self):
        bad=b"\xff\x00synthetic invalid telemetry\n"
        result=self.run_engine(telemetry_function=lambda:bad)
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)
        rows=[read_json(p) for p in (self.root/"control/journal").glob("*-failure.json")]
        evidence=rows[0]["value"]["partial_reader_evidence"]["raw_stdout"]
        self.assertEqual(base64.b64decode(evidence["base64"]),bad)

    def test_reboot_before_approval_release_creates_no_release_claim_or_collector(self):
        from . import supervisor
        actual={**self.packet["host_identity"],"boot_time_100ns":self.packet["host_identity"]["boot_time_100ns"]+1}
        with patch.object(supervisor,"bounded_host_identity",return_value=actual):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)
        root=Path(self.packet["stop_root"])
        self.assertFalse(list(root.glob("release-*")));self.assertFalse(list(root.glob("claim-*")))
        rows=[read_json(p) for p in (self.root/"control/journal").glob("*-failure.json")]
        self.assertEqual(rows[0]["value"]["partial_reader_evidence"]["actual"],actual)

    def test_changed_boot_identity_before_next_collector_blocks_continuation(self):
        from . import supervisor
        expected=self.packet["host_identity"]
        changed={**expected,"boot_time_100ns":expected["boot_time_100ns"]+1}
        with patch.object(supervisor,"bounded_host_identity",side_effect=[expected,expected,changed]):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)

    def test_stage_fence_bad_telemetry_retained_before_next_collector(self):
        from . import supervisor
        bad=b"synthetic bad fence CSV\xff\n";calls=[]
        def samples():
            calls.append(1)
            return raw() if len(calls)==1 else bad
        # Keep synthetic observation threads idle so the second read is exactly
        # the independent stage fence. Actual native child/control paths remain.
        def idle(self,name,cadence):self.done.wait(5)
        with patch.object(supervisor.Watch,"loop",new=idle):result=self.run_engine(telemetry_function=samples)
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        rows=[read_json(p) for p in (self.root/"control/journal").glob("*-failure.json")]
        evidence=rows[0]["value"]["partial_reader_evidence"]["raw_stdout"]
        self.assertEqual(base64.b64decode(evidence["base64"]),bad)

    def test_observer_failure_blocks_every_later_capture(self):
        self.fault("observer")
        result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)

    def test_output_fault_blocks_every_later_capture(self):
        self.fault("output","import time;print('[fault] synthetic CPU control',flush=True);time.sleep(20)")
        result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)

    def test_failed_collector_owned_orphan_is_terminated(self):
        self.fault("collector-die","from pathlib import Path;import time;Path('started.txt').write_text('CPU');time.sleep(20)")
        result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)
        terminations = [read_json(p) for p in (self.root/"control/journal").glob("*-termination.json")]
        self.assertTrue(any(p["value"]["role"]=="target" and p["value"]["terminated"] for p in terminations))

    def test_native_target_deadline_is_independent(self):
        self.stages[0]["deadline_seconds"] = .3
        self.fault("timeout","import time;time.sleep(20)")
        result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)

    def test_late_event_stage_fence_blocks_next_collector(self):
        calls = []
        def events(previous):
            calls.append(1)
            current = batch()
            # Initial preflight + asynchronous read pass; the stage fence fails.
            if len(calls)>=3:
                current = batch(1)
                current["events"][0]["provider"]="Display"
            return current
        result = self.run_engine(event_function=events)
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)

    def test_missing_and_stale_stage_result_block_next_spawn(self):
        # Both mutations run against the real supervisor after a real benign
        # target exited; no alternate stage result is accepted as fresh.
        from . import supervisor
        original = supervisor.read_json
        def changed(path):
            value = original(path)
            if Path(path).name == "stage-result.json":
                value["packet_sha256"] = "0"*64
            return value
        with patch.object(supervisor,"read_json",side_effect=changed):
            result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)

    def test_registration_receipt_failure_retains_and_contains_suspended_target(self):
        from . import supervisor
        original=supervisor._registration
        def inject(packet,stage,control,collector,identity,journal,before_ack=lambda:None):
            def failure():raise OSError("synthetic registration fsync failure")
            return original(packet,stage,control,collector,identity,journal,failure)
        with patch.object(supervisor,"_registration",side_effect=inject):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        rows=[read_json(p) for p in (self.root/"control/journal").glob("*-termination.json")]
        self.assertTrue(any(row["value"]["role"]=="target" and row["value"]["terminated"] for row in rows))
        self.assertFalse(list((self.root/"control").rglob("target-resumed.json")))

    def test_stop_after_collector_before_target_prevents_native_resume(self):
        from . import supervisor
        original = supervisor.Process.resume
        def stop_before_resume(process, identity, **kwargs):
            # Collector starts, but its first target gate sees durable STOP.
            original(process,identity,**kwargs)
            exclusive(Path(self.packet["stop_root"])/"STOP-synthetic.json",{"status":"STOP"})
        with patch.object(supervisor.Process,"resume",new=stop_before_resume):
            result = self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)
        self.assertFalse(list((self.root/"control").rglob("target-resumed.json")))

    def config_pins(self):
        for stage in self.stages:
            original = stage["generated_pins"][0]
            out = Path(stage["capture"]["out"])
            live = {**original,"path":str(out/"fixture.ini")}
            stage["generated_pins"] += [live,{**original,"path":str(out/"input/fixture.ini")}]
            stage["mutable_runtime_config"] = live

    def test_owned_cpu_child_can_persist_only_live_config(self):
        self.config_pins()
        script="from pathlib import Path;Path('marker.txt').write_text('CPU benign success');Path('fixture.ini').write_text('normal persisted CPU config')"
        for stage in self.stages:
            stage["capture"]["cpu_script"]=script
            stage["expected_argv"][-1]=script
        result=self.run_engine()
        self.assertEqual(result["status"],"COLLECTED_PENDING_ACCEPTANCE",result)
        for stage in self.stages:
            out=Path(stage["capture"]["out"])
            self.assertEqual((out/"input/fixture.ini").read_bytes(),b"pinned synthetic fixture")
            self.assertEqual((out/"fixture.ini").read_text(),"normal persisted CPU config")

    def test_changed_live_config_before_spawn_is_rejected(self):
        self.config_pins()
        self.fault("config-changed")
        result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)
        self.assertFalse(list((self.root/"control").rglob("target-request.json")))

    def test_owned_child_cannot_rewrite_immutable_original_config(self):
        self.config_pins()
        self.fault("immutable-config","from pathlib import Path;Path('input/fixture.ini').write_text('forbidden immutable rewrite')")
        result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP")
        self.assertEqual(self.spawn_count(),1)
        self.assertEqual((Path(self.stages[0]["capture"]["out"])/"input/fixture.ini").read_bytes(),b"pinned synthetic fixture")

    def test_supervisor_abrupt_death_collector_kills_owned_target(self):
        from .windows import Process
        self.fault("supervisor-die","from pathlib import Path;import time;Path('started.txt').write_text('CPU');time.sleep(20)")
        packet_path = self.root/"synthetic-packet.json"
        exclusive(packet_path,self.packet)
        source = str(Path(__file__).resolve().parents[2])
        driver = f'''import sys,json,hashlib
sys.path.insert(0,{source!r})
from pathlib import Path
from unittest.mock import patch
from tools.physical_supervisor import supervisor
from tools.physical_supervisor.common import canonical,utc
from tools.physical_supervisor.readers import BoundedReaders
from tools.physical_supervisor.test_supervisor import raw,batch
from tools.physical_supervisor.test_integration import synthetic_source_checks
p=json.loads(Path({str(packet_path)!r}).read_text()); sha=hashlib.sha256(canonical(p)).hexdigest()
a={{"schema":"physical-supervisor/approval-v1","experiment_id":p["experiment_id"],"packet_sha256":sha,"phrase":"AUTHORIZE CPU-DIAG-TEST (three diagnostic processes only)","decided_utc":utc(),"expires_utc":p["expires_utc"]}}
with patch.object(supervisor,"validate_packet",return_value=sha),patch.object(supervisor,"verify_source",side_effect=synthetic_source_checks),patch.object(supervisor,"GRACE_SECONDS",.05):
 supervisor.execute(p,a,{str(self.root/"control")!r},readers=BoundedReaders(lambda:raw(),lambda previous:batch()))
'''
        with (self.root/"driver-out.log").open("wb") as stdout, (self.root/"driver-err.log").open("wb") as stderr:
            owner = Process.spawn([sys.executable,"-I","-B","-c",driver],self.root,stdout,stderr)
            owner_identity = owner.identity()
            self.addCleanup(owner.close)
            self.addCleanup(lambda:owner.kill(owner_identity) if owner.handle else None)
            owner.resume(owner_identity)
            started = Path(self.stages[0]["capture"]["out"])/"started.txt"
            until=time.monotonic()+8
            while not started.exists() and owner.poll() is None and time.monotonic()<until:
                time.sleep(.02)
            if not started.exists():
                # On a hostile/loaded CI host, a fail-closed supervisor may exit
                # before the synthetic target's marker is written. Preserve its
                # real source-matched failure, not just a blank driver stderr:
                # supervisor.execute() deliberately returns FAILED_STOP without
                # writing a traceback to the embedding driver's stderr.
                control = self.root/"control"
                evidence = {"supervisor_exit_code":owner.poll(),"started_marker_present":False}
                for path in (
                    self.root/"driver-out.log", self.root/"driver-err.log",
                    control/"result.json", control/"manifest.json",
                    control/"00-compositing/collector-stdout.log",
                    control/"00-compositing/collector-stderr.log",
                    control/"00-compositing/stage-failed.json",
                    control/"00-compositing/target-request.json",
                ):
                    if path.is_file():
                        evidence[str(path.relative_to(self.root))] = path.read_text(
                            encoding="utf-8",errors="replace")[-5000:]
                journal = control/"journal"
                if journal.is_dir():
                    recent = sorted(journal.glob("*.json"))[-12:]
                    evidence["journal"] = {
                        path.name:path.read_text(encoding="utf-8",errors="replace")[-1500:]
                        for path in recent
                    }
                evidence["stop_filenames"] = sorted(
                    path.name for path in Path(self.packet["stop_root"]).glob("STOP-*.json"))
                self.fail("Native benign supervisor-death fixture did not reach target start; "
                          +json.dumps(evidence,sort_keys=True))
            request = read_json(self.root/"control/00-compositing/target-request.json")
            target = Process.open(request["target"]["pid"])
            target.verify(request["target"])
            collector = Process.open(request["collector"]["pid"])
            collector.verify(request["collector"])
            self.addCleanup(target.close)
            self.addCleanup(collector.close)
            self.addCleanup(lambda:target.kill(request["target"]) if target.handle else None)
            self.addCleanup(lambda:collector.kill(request["collector"]) if collector.handle else None)
            owner.kill(owner_identity)
            until=time.monotonic()+5
            while (target.poll() is None or collector.poll() is None) and time.monotonic()<until:
                time.sleep(.02)
            self.assertIsNotNone(target.poll(),"Collector did not contain target after supervisor death")
            self.assertIsNotNone(collector.poll(),"Collector did not finalize STOP")
            self.assertTrue(list(Path(self.packet["stop_root"]).glob("STOP-*.json")))
            self.assertEqual(self.spawn_count(),1)


if __name__ == "__main__":
    unittest.main()
