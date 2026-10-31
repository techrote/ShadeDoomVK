"""Pure CPU policy controls; no approvals, releases or processes are created."""
import copy
import datetime as dt
import unittest

from .common import Stop, approve
from .conditional_grant import check_budget, digest, resolve_for_review


class ConditionalGrantTests(unittest.TestCase):
    def fixture(self):
        now = dt.datetime.now(dt.timezone.utc)
        grant = {"schema": "sdvk009-conditional-renderer-grant/v1", "max_renderer_launches": 24,
                 "max_retries_per_test": 3, "user_instruction_verbatim": "Synthetic CPU owner instruction",
                 "user_addendum_verbatim": "Synthetic CPU retry addendum", "tests": ["a", "b", "c", "d", "e", "f"],
                 "recorded_utc": (now - dt.timedelta(hours=1)).isoformat(),
                 "expires_utc": (now + dt.timedelta(hours=1)).isoformat(), "conditions": ["source_pr", "plan_review"]}
        packet = {"experiment_id": "CPU-GRANT-TEST", "kind": "diagnostic", "automatic_retries": 0, "created_utc": now.isoformat(),
                  "native_device": {"vendor_id": 1, "device_id": 2, "device_type": 2, "driver_version_raw": 3}}
        review = {"schema": "sdvk009-conditional-plan-review/v1", "grant_sha256": digest(grant),
                  "packet_sha256": digest(packet), "expires_utc": grant["expires_utc"],
                  "plan_reviewed_utc": now.isoformat(), "blocking_findings": [], "accepted_supervisor_source": True,
                  "conditions_satisfied": ["source_pr", "plan_review"], "reviewed_retry": True}
        return grant, packet, review

    def test_finite_budget_counts_all_attempts_and_never_replays_packets(self):
        grant, _, _ = self.fixture(); charges = []
        for attempt in range(4):
            for test in grant["tests"]:
                sha = digest([test, attempt])
                row = check_budget(grant, charges, test, sha, reviewed_retry=attempt > 0)
                charges.append(row)
                with self.assertRaises(Stop): check_budget(grant, charges, test, sha, reviewed_retry=True)
        self.assertEqual(len(charges), 24)
        with self.assertRaises(Stop): check_budget(grant, charges, "a", "f" * 64, reviewed_retry=True)

    def test_per_test_retry_cap_and_review_are_independent_of_global_cap(self):
        grant, _, _ = self.fixture()
        charges = [check_budget(grant, [], "a", "1" * 64)]
        with self.assertRaises(Stop): check_budget(grant, charges, "a", "2" * 64)
        for index in range(1, 4): charges.append(check_budget(grant, charges, "a", str(index + 1) * 64, reviewed_retry=True))
        with self.assertRaises(Stop): check_budget(grant, charges, "a", "5" * 64, reviewed_retry=True)
        self.assertEqual(check_budget(grant, charges, "b", "5" * 64)["attempt"], 0)

    def test_truthful_resolution_is_not_an_executable_v1_approval(self):
        grant, packet, review = self.fixture()
        result = resolve_for_review(grant, packet, review, [], "a")
        self.assertFalse(result["execution_ready"])
        self.assertNotIn("decided_utc", result)
        self.assertEqual(result["grant_recorded_utc"], grant["recorded_utc"])
        with self.assertRaises(Stop): approve(packet, result, digest(packet), object())

    def test_changed_conditions_source_budget_and_bindings_fail_closed(self):
        grant, packet, review = self.fixture()
        for key, value in [("conditions_satisfied", []), ("accepted_supervisor_source", False),
                           ("blocking_findings", ["fault"]), ("packet_sha256", "0" * 64), ("grant_sha256", "0" * 64)]:
            with self.subTest(key=key), self.assertRaises(Stop): resolve_for_review(grant, packet, {**review, key: value}, [], "a")
        for key, value in [("max_renderer_launches", 25), ("max_renderer_launches", True),
                           ("max_retries_per_test", 4), ("max_retries_per_test", -1)]:
            with self.subTest(key=key), self.assertRaises(Stop): check_budget({**grant, key: value}, [], "a", "1" * 64)
