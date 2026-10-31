"""Durable finite-budget controls; every child is a benign Python process."""
import copy
import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from .common import Gate, Stop, exclusive, pin, read_json, utc
from .conditional_grant import (Ledger, STAGES, authority, digest, initialize_ledger,
                               validate_conditional_review)
from . import test_integration as integration
from .readers import BoundedReaders
from .test_supervisor import raw, batch


def fixture(root):
    grant = {"schema": "sdvk009-conditional-renderer-grant/v1", "grant_id": "CPU-GRANT-ONLY", "owner": "CPU fixture",
             "max_renderer_launches": 24, "max_retries_per_test": 3,
             "user_instruction_verbatim": "Synthetic CPU allowance", "user_addendum_verbatim": "Synthetic CPU retries",
             "tests": STAGES, "ledger_root": str(root / "ledger"), "recorded_utc": utc(),
             "expires_utc": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(),
             "conditions": ["source", "review"]}
    return grant


class AtomicAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdvk009-cpu-budget-")
        self.root = Path(self.temp.name)
        self.grant = fixture(self.root)
        self.grant_pin = initialize_ledger(self.grant)

    def tearDown(self):
        self.temp.cleanup()

    def finish(self, ledger, sha, status="FAILED_STOP"):
        result = self.root / (sha + ".json")
        exclusive(result, {"status": status})
        ledger.finish(sha, status, pin(result))

    def review(self, ledger):
        return {"assessed_predecessors": [digest(r) for r in ledger.rows if r["kind"] == "finish"],
                "retry_assessment": "Synthetic failure retained and assessed; CPU-only successor"}

    def test_failed_create_is_consumed_and_three_retries_are_the_limit(self):
        for attempt in range(4):
            sha = digest(attempt)
            with Ledger(self.grant) as ledger:
                ledger.start(sha, str(self.root / f"stop-{attempt}"), self.review(ledger))
                charge = ledger.reserve(sha, STAGES[0], str(self.root / f"stop-{attempt}"))
                self.assertEqual(charge["attempt"], attempt)
                # Simulated CreateProcess failure: no completion, no refund.
                self.finish(ledger, sha)
        with Ledger(self.grant) as ledger:
            sha = digest(5); stop = str(self.root / "stop-5")
            ledger.start(sha, stop, self.review(ledger))
            with self.assertRaises(Stop): ledger.reserve(sha, STAGES[0], stop)
            self.assertEqual(len(ledger.charges()), 4)

    def test_caps_order_fences_replay_and_unresolved_failure(self):
        # A smaller cap proves the global constraint independently of the
        # three-test, four-attempt-per-test limit (which permits at most 12).
        root = self.root / "small"; root.mkdir()
        grant = {**fixture(root), "max_renderer_launches": 2}
        initialize_ledger(grant); sha = digest("small"); stop = str(root / "stop")
        with Ledger(grant) as ledger:
            ledger.start(sha, stop, {})
            with self.assertRaises(Stop): ledger.reserve(sha, STAGES[1], stop)
            ledger.reserve(sha, STAGES[0], stop)
            with self.assertRaises(Stop): ledger.reserve(sha, STAGES[1], stop)
            with self.assertRaises(Stop): ledger.reserve(sha, STAGES[0], stop)
            ledger.complete(sha, STAGES[0])
            ledger.reserve(sha, STAGES[1], stop); ledger.complete(sha, STAGES[1])
            with self.assertRaises(Stop): ledger.reserve(sha, STAGES[2], stop)
            with self.assertRaises(Stop): ledger.start(digest("other"), str(root / "next"), {})
            self.finish(ledger, sha)
            with self.assertRaises(Stop): ledger.start(digest("other"), str(root / "next"), {})
            with self.assertRaises(Stop): ledger.start(sha, stop, self.review(ledger))

    def test_native_concurrent_reservation_has_exactly_one_winner(self):
        sha = digest("race"); stop = str(self.root / "stop")
        with Ledger(self.grant) as ledger: ledger.start(sha, stop, {})
        code = ("import sys\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parents[2])) + ")\n"
                "from tools.physical_supervisor.conditional_grant import Ledger\n"
                "from tools.physical_supervisor.common import read_json\n"
                "g=read_json(" + repr(self.grant_pin["path"]) + ")\n"
                "with Ledger(g) as ledger:\n ledger.reserve(" + repr(sha) + ", 'compositing', " + repr(stop) + ")\n")
        children = [subprocess.Popen([sys.executable, "-I", "-B", "-c", code], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE) for _ in range(6)]
        results = [p.communicate(timeout=20) for p in children]
        self.assertEqual(sum(p.returncode == 0 for p in children), 1, results)
        self.assertTrue(all(p.returncode in (0, 1) for p in children))
        with Ledger(self.grant) as ledger: self.assertEqual(len(ledger.charges()), 1)

    def test_interrupted_publication_and_chain_change_fail_closed(self):
        pending = Path(self.grant["ledger_root"]) / ".pending-cpu-crash"
        pending.write_text("interrupted CPU publication")
        with self.assertRaises(Stop):
            with Ledger(self.grant): pass
        pending.unlink()  # Only this disposable synthetic fixture is repaired.
        with Ledger(self.grant) as ledger: ledger.start(digest("gap"), "synthetic-stop", {})
        path = Path(self.grant["ledger_root"]) / "event-000000.json"
        row = read_json(path); row["previous_sha256"] = "1" * 64
        path.write_text(__import__("json").dumps(row))
        with self.assertRaises(Stop):
            with Ledger(self.grant): pass

    def test_conditional_release_rejects_forged_decision_and_missing_prerequisites(self):
        from .common import approve
        packet = {"conditional_grant": self.grant_pin, "files": [self.grant_pin], "kind": "diagnostic",
                  "automatic_retries": 0, "created_utc": utc(), "experiment_id": "CPU-V2-APPROVAL",
                  "native_device": {"vendor_id": 1, "device_id": 2, "device_type": 2, "driver_version_raw": 3},
                  "stages": [{"name": name} for name in STAGES]}
        sha = digest(packet)
        review = {"schema": "sdvk009-conditional-plan-review/v2", "grant_sha256": digest(self.grant),
                  "packet_sha256": sha, "expires_utc": self.grant["expires_utc"], "plan_reviewed_utc": utc(),
                  "blocking_findings": [], "accepted_supervisor_source": True, "conditions_satisfied": self.grant["conditions"],
                  "reviewer_provenance": "CPU fixture", "source_acceptance_evidence": [self.grant_pin],
                  "cpu_evidence": [self.grant_pin], "supervisor_source": {}}
        approval = {"schema": "physical-supervisor/conditional-approval-v2", "experiment_id": packet["experiment_id"],
                    "packet_sha256": sha, "expires_utc": self.grant["expires_utc"], "plan_review": review}
        root = self.root / "stop"; root.mkdir(); exclusive(root / "HELD.json", {"status": "HELD"})
        variants = [{**approval, "decided_utc": utc()}, {**approval, "phrase": "fabricated later human quote"}]
        for key, value in [("blocking_findings", ["fault"]), ("accepted_supervisor_source", False),
                           ("conditions_satisfied", []), ("packet_sha256", "f" * 64), ("cpu_evidence", []),
                           ("source_acceptance_evidence", []), ("plan_reviewed_utc", "2999-01-01T00:00:00+00:00")]:
            variants.append({**approval, "plan_review": {**review, key: value}})
        with patch("tools.physical_supervisor.conditional_grant.verify_supervisor_source"):
            for candidate in variants:
                with self.subTest(candidate=candidate), self.assertRaises(Stop):
                    approve(packet, candidate, sha, Gate(root, sha))
        self.assertFalse(list(root.glob("release-*")))
        with Ledger(self.grant) as ledger: self.assertFalse(ledger.rows)


@unittest.skipUnless(os.name == "nt", "Native CPU-only supervisor integration")
class ConditionalEngineTests(unittest.TestCase):
    setUp = integration.EngineIntegrationTests.setUp
    tearDown = integration.EngineIntegrationTests.tearDown

    def run_conditional(self, *, create_failure=False, observer_failure=False, crash_after_charge=False):
        from . import supervisor
        grant = fixture(self.root)
        row = initialize_ledger(grant)
        self.packet["conditional_grant"] = row
        self.packet["files"].append(row)
        if observer_failure: self.stages[0]["capture"]["cpu_fault"] = "observer"
        if create_failure:
            oracle = Path(self.packet["oracle_source_root"]) / "tools/renderer_oracle/run.py"
            with oracle.open("a") as stream:
                stream.write("\nimport _winapi\ndef fail_create(*a, **k): raise OSError('synthetic CPU CreateProcess failure')\n_winapi.CreateProcess=fail_create\n")
            self.packet["files"] = [pin(r["path"]) for r in self.packet["files"]]
        if crash_after_charge:
            oracle = Path(self.packet["oracle_source_root"]) / "tools/renderer_oracle/run.py"
            with oracle.open("a") as stream:
                stream.write("\nfrom tools.physical_supervisor import conditional_grant as budget\n_original_charge=budget.boundary_charge\ndef crash_charge(*a):\n _original_charge(*a)\n os._exit(25)\nbudget.boundary_charge=crash_charge\n")
            self.packet["files"] = [pin(r["path"]) for r in self.packet["files"]]
        sha = digest(self.packet)
        review = {"schema": "sdvk009-conditional-plan-review/v2", "grant_sha256": digest(grant),
                  "packet_sha256": sha, "expires_utc": grant["expires_utc"], "plan_reviewed_utc": utc(),
                  "blocking_findings": [], "accepted_supervisor_source": True, "conditions_satisfied": grant["conditions"],
                  "reviewer_provenance": "Explicitly synthetic CPU fixture", "source_acceptance_evidence": [row],
                  "cpu_evidence": [row], "supervisor_source": {}}
        approval = {"schema": "physical-supervisor/conditional-approval-v2", "experiment_id": self.packet["experiment_id"],
                    "packet_sha256": sha, "expires_utc": grant["expires_utc"], "plan_review": review}
        with patch.object(supervisor, "validate_packet", return_value=sha), \
             patch.object(supervisor, "verify_source", side_effect=integration.synthetic_source_checks), \
             patch.object(supervisor, "GRACE_SECONDS", .05), \
             patch("tools.physical_supervisor.conditional_grant.verify_supervisor_source"):
            result = supervisor.execute(self.packet, approval, self.root / "control",
                                        readers=BoundedReaders(lambda: raw(), lambda previous: batch()))
        with Ledger(grant) as ledger:
            return result, copy.deepcopy(ledger.rows)

    def test_native_three_stages_charge_once_each_and_keep_truthful_decision(self):
        result, rows = self.run_conditional()
        self.assertEqual(result["status"], "COLLECTED_PENDING_ACCEPTANCE", result)
        self.assertEqual([r["value"]["test"] for r in rows if r["kind"] == "charge"], STAGES)
        self.assertEqual(sum(r["kind"] == "stage-complete" for r in rows), 3)
        self.assertEqual(rows[-1]["kind"], "finish")
        release = read_json(next(Path(self.packet["stop_root"]).glob("release-*.json")))
        self.assertNotIn("decided_utc", release)
        self.assertNotIn("phrase", release)

    def test_native_failed_creation_consumes_one_and_stops(self):
        result, rows = self.run_conditional(create_failure=True)
        self.assertEqual(result["status"], "FAILED_STOP", result)
        self.assertEqual(sum(r["kind"] == "charge" for r in rows), 1, rows)
        self.assertEqual(sum(r["kind"] == "stage-complete" for r in rows), 0)
        self.assertFalse(list((self.root / "control").rglob("target-request.json")))
        self.assertEqual(rows[-1]["value"]["status"], "FAILED_STOP")

    def test_native_observer_failure_retained_without_later_charge(self):
        result, rows = self.run_conditional(observer_failure=True)
        self.assertEqual(result["status"], "FAILED_STOP", result)
        self.assertEqual(sum(r["kind"] == "charge" for r in rows), 1)
        self.assertEqual(rows[-1]["value"]["status"], "FAILED_STOP")

    def test_collector_crash_after_charge_never_refunds_or_creates_target(self):
        result, rows = self.run_conditional(crash_after_charge=True)
        self.assertEqual(result["status"], "FAILED_STOP", result)
        self.assertEqual(sum(r["kind"] == "charge" for r in rows), 1)
        self.assertFalse(list((self.root / "control").rglob("target-request.json")))
