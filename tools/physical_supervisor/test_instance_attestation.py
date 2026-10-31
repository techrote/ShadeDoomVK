"""CPU-only review/readback/lifetime controls. Never invoke the live probe flag."""
import copy
import datetime as dt
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import unittest

from .common import Stop, pin
from .instance_attestation import LIMITS, device_readback, plan_digest, validate_review
from .test_supervisor import TempCase


class AttestationReviewTests(TempCase):
    def fixture(self):
        module = self.root / "CPU_ONLY_NEVER_LOADED.dll"
        module.write_bytes(b"CPU-only module identity, never loaded")
        plan = {"expected_device": {"vendor_id": 1, "device_id": 2, "device_type": 2,
                                   "pci": {"domain": 0, "bus": 7, "device": 0, "function": 0}},
                "module_policy": {"required_paths": [str(module)]}}
        result = {"schema": "sdvk009-instance-readback/v1", "status": "NATIVE_READBACK_ONLY_NOT_PHYSICAL_QUALIFICATION",
                  "instance_create_calls": 1, "logical_devices_created": 0, "queue_submissions": 0, "instance_destroyed": True,
                  "devices": [{**plan["expected_device"], "driver_version_raw": 123, "pci_bus_info_available": True}],
                  "modules_during_instance": [str(module)]}
        return plan, result

    def test_native_readback_is_scoped_and_keeps_only_four_expected_properties(self):
        plan, result = self.fixture()
        value = device_readback(plan, result)
        self.assertEqual(value["native_device"], {"vendor_id": 1, "device_id": 2, "device_type": 2, "driver_version_raw": 123})
        self.assertIn("NOT_RENDERER_DIAGNOSTIC", value["scope"])

    def test_scope_identity_missing_or_ambiguous_readback_is_rejected(self):
        plan, original = self.fixture()
        mutations = [lambda x: x.update(instance_create_calls=2), lambda x: x.update(instance_create_calls=True),
                     lambda x: x.update(logical_devices_created=1), lambda x: x.update(queue_submissions=1),
                     lambda x: x.update(instance_destroyed=False), lambda x: x["devices"].append(copy.deepcopy(x["devices"][0])),
                     lambda x: x["devices"][0].update(pci_bus_info_available=False),
                     lambda x: x["devices"][0]["pci"].update(bus=8),
                     lambda x: x["devices"][0]["pci"].update(domain=False),
                     lambda x: x["devices"][0].update(driver_version_raw=None),
                     lambda x: x["modules_during_instance"].clear(),
                     lambda x: x["modules_during_instance"].append(x["modules_during_instance"][0])]
        for mutation in mutations:
            changed = copy.deepcopy(original); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(Stop): device_readback(plan, changed)

    def test_held_or_different_plan_review_cannot_authorize_instance_attempt(self):
        plan, _ = self.fixture()
        proof = self.root / "CPU_EVIDENCE.txt"; proof.write_text("Explicitly synthetic CPU receipt")
        review = {"schema": "sdvk009-instance-attestation-review/v1", "plan_sha256": plan_digest(plan),
                  "decision": "REVIEWED_ONE_INSTANCE_ONLY_ATTEMPT", "blocking_findings": [],
                  "user_authorization_verbatim": "Synthetic CPU authorization fixture, not an owner decision",
                  "reviewer_provenance": "synthetic CPU control", "cpu_evidence": [pin(proof)],
                  "expires_utc": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()}
        validate_review(plan, review)
        for key, value in [("decision", "HOLD"), ("plan_sha256", "0" * 64), ("blocking_findings", ["unfixed"]),
                           ("user_authorization_verbatim", ""), ("cpu_evidence", [])]:
            with self.subTest(key=key), self.assertRaises(Stop): validate_review(plan, {**review, key: value})


@unittest.skipUnless(os.name == "nt", "Native CPU-only worker lifetime control")
class NativeProbeLifetimeTests(TempCase):
    def test_controller_death_ends_cpu_worker_without_loading_vulkan(self):
        # A configured native probe path is required only for the explicit local
        # build review. Normal repo CI does not build or execute the live probe.
        executable = os.environ.get("SDVK_CPU_PROBE_CONTROL_EXE")
        if not executable: self.skipTest("Probe build not supplied for native CPU lifetime control")
        from .windows import Process
        owner = self.root / "owner.py"
        child_result = self.root / "worker-result.json"
        owner.write_text('''import json,os,subprocess,sys
from pathlib import Path
from tools.physical_supervisor.windows import Process
p=Process.open(os.getpid())
try: identity=p.identity()
finally:p.close()
with open(sys.argv[2]+'.stdout','wb') as out,open(sys.argv[2]+'.stderr','wb') as err:
 child=subprocess.Popen([sys.argv[1],'--cpu-parent-watch-control',str(identity['pid']),str(identity['creation_ticks'])],stdout=out,stderr=err)
 Path(sys.argv[2]).write_text(json.dumps({'pid':child.pid}))
 import time;time.sleep(20)
''')
        # subprocess Python gets an explicit source path, not an ambient import.
        argv = [sys.executable, "-B", "-c", "import runpy,sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[2])) + ");script=sys.argv.pop(1);runpy.run_path(script,run_name='__main__')", str(owner), executable, str(child_result)]
        logs = [self.root / "owner.stdout", self.root / "owner.stderr"]
        with logs[0].open("wb") as stdout, logs[1].open("wb") as stderr:
            parent = Process.spawn(argv, self.root, stdout, stderr)
            identity = parent.identity()
            self.addCleanup(parent.close)
            self.addCleanup(lambda: parent.kill(identity) if parent.handle and parent.poll() is None else None)
            parent.resume(identity)
            until = time.monotonic() + 5
            worker = None
            while time.monotonic() < until:
                if child_result.exists() and Path(str(child_result) + '.stdout').exists() and b'CPU_PARENT_WATCH_STARTED' in Path(str(child_result) + '.stdout').read_bytes():
                    import json
                    worker = Process.open(json.loads(child_result.read_text())["pid"])
                    break
                if parent.poll() is not None: break
                time.sleep(.02)
            self.assertIsNotNone(worker, logs[1].read_text())
            self.addCleanup(worker.close)
            worker_identity = worker.identity()
            self.addCleanup(lambda: worker.kill(worker_identity) if worker.handle and worker.poll() is None else None)
            self.assertEqual(worker_identity["parent_pid"], identity["pid"])
            parent.kill(identity)
            until = time.monotonic() + 3
            while worker.poll() is None and time.monotonic() < until: time.sleep(.02)
            self.assertEqual(worker.poll(), 125, "CPU-only worker did not self-contain after its controller died")


@unittest.skipUnless(os.name == "nt", "Native containment with benign Python only")
class ContainedProbeControllerTests(TempCase):
    def fixture(self, *, sleeping=False):
        from . import instance_attestation as runner
        from .common import environment_policy
        from .readers import bounded_host_identity
        from .test_supervisor import EXPECTED
        from .windows import Process
        owned = Process.open(os.getpid())
        try: modules = owned.modules(owned.identity())
        finally: owned.close()
        kernel = next(p for p in modules if Path(p).name.casefold() == "kernel32.dll")
        fake_inputs = self.root / "cpu-inputs"; fake_inputs.mkdir()
        dummy = fake_inputs / "CPU_ONLY_DATA"; dummy.write_text("Never a renderer or Vulkan library")
        pins = [pin(p) for p in modules] + [pin(dummy)]
        plan = {"schema": "sdvk009-instance-attestation-plan/v1", "limits": dict(LIMITS),
                "probe": sys.executable, "nvidia_smi": str(dummy),
                "physical_gate": "HELD / NOT ACCEPTED", "host_identity": bounded_host_identity(),
                "expires_utc": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(),
                "claim_root": str(self.root / "cpu-attempt-claim"),
                "files": pins, "runtime_roots": [{"path": str(fake_inputs), "files": [str(dummy)]}],
                "registry_policy": [], "registry_enumeration_policy": [],
                "environment_policy": environment_policy(), "telemetry": EXPECTED,
                "module_policy": {"required_paths": [kernel], "optional_paths": [], "sample_seconds": .25,
                                  "reader_timeout_seconds": 10, "unknown_policy": "record-system-only"},
                "expected_device": {"vendor_id": 1, "device_id": 2, "device_type": 2,
                                    "pci": {"domain": 0, "bus": 7, "device": 0, "function": 0}}}
        result = {"schema": "sdvk009-instance-readback/v1", "status": "NATIVE_READBACK_ONLY_NOT_PHYSICAL_QUALIFICATION",
                  "instance_create_calls": 1, "logical_devices_created": 0, "queue_submissions": 0, "instance_destroyed": True,
                  "devices": [{**plan["expected_device"], "driver_version_raw": 123, "pci_bus_info_available": True}],
                  "modules_during_instance": modules}
        import json
        script = "import time;print(" + repr(json.dumps(result)) + ",flush=True);time.sleep(" + ("60" if sleeping else ".1") + ")"
        plan["argv"] = [sys.executable, "-I", "-B", "-c", script]
        proof = self.root / "cpu-proof"; proof.write_text("SYNTHETIC CPU CONTROL; NOT OWNER EVIDENCE")
        review = {"schema": "sdvk009-instance-attestation-review/v1", "plan_sha256": plan_digest(plan),
                  "decision": "REVIEWED_ONE_INSTANCE_ONLY_ATTEMPT", "blocking_findings": [],
                  "user_authorization_verbatim": "SYNTHETIC CPU CONTROL ONLY", "reviewer_provenance": "CPU fixture",
                  "cpu_evidence": [pin(proof)], "expires_utc": plan["expires_utc"]}
        return runner, plan, review

    def run_cpu(self, *, sleeping=False, fail_stop_receipt=False):
        runner, plan, review = self.fixture(sleeping=sleeping)
        from .readers import BoundedReaders
        from .test_supervisor import raw, batch, baseline
        plan["event_baseline"] = baseline()
        review["plan_sha256"] = plan_digest(plan)
        real_exclusive = runner.exclusive
        def write(path, value):
            if fail_stop_receipt and Path(path).name == "STOP.json": raise OSError("CPU synthetic receipt failure")
            return real_exclusive(path, value)
        with patch.object(runner, "validate_plan", return_value=plan_digest(plan)), \
             patch.dict(runner.LIMITS, {"deadline_seconds": .25 if sleeping else 3, "completion_grace_seconds": .05}), \
             patch.object(runner, "exclusive", side_effect=write):
            result = runner.execute_probe(plan, review, self.root / "cpu-control",
                readers=BoundedReaders(lambda: raw(), lambda previous: batch()))
        return result, plan

    def test_owned_cpu_worker_positive_and_no_second_attempt_for_same_plan(self):
        result, plan = self.run_cpu()
        self.assertEqual(result["status"], "NATIVE_ATTESTATION_RETAINED_PENDING_REVIEW", result)
        self.assertTrue((self.root / "cpu-control/native-attestation.json").is_file())
        with self.assertRaises(FileExistsError): Path(plan["claim_root"]).mkdir(exist_ok=False)

    def test_deadline_contains_owned_cpu_worker_even_when_stop_receipt_fails(self):
        result, plan = self.run_cpu(sleeping=True, fail_stop_receipt=True)
        self.assertEqual(result["status"], "FAILED_STOP", result)
        self.assertIn("deadline", result.get("error", ""))
        self.assertIn("receipt", result.get("stop_receipt_error", ""))
        from .common import read_json
        from .windows import Process
        records = list((self.root / "cpu-control/journal").glob("*-suspended-probe-identity.json"))
        identity = read_json(records[0])["value"]
        # An exited PID may already be gone; no PID/name based termination.
        try: owned = Process.open(identity["pid"])
        except Stop: return
        try:
            if owned.identity() == identity: self.assertIsNotNone(owned.poll())
        finally: owned.close()
