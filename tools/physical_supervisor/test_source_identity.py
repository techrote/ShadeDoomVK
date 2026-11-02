"""Pure CPU source/proof controls; all Git subprocess calls are mocked."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from .collector import prepare_subprocess_adapter, source_proof
from .common import Stop, exclusive, pin, source_check_requests, verify_source


class SeparatedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.renderer = self.root / "renderer"
        self.oracle = self.root / "oracle"
        self.renderer.mkdir()
        self.oracle.mkdir()
        self.git = self.root / "SYNTHETIC_NOT_EXECUTED_git"
        self.git.write_bytes(b"CPU fixture; no executable")
        self.packet = {"git": str(self.git), "oracle_source_root": str(self.renderer),
                       "source": {"commit": "a" * 40, "tree": "b" * 40},
                       "packet_sha256": "c" * 64, "stop_root": str(self.root / "stop"),
                       "expires_utc": "2999-01-01T00:00:00+00:00"}
        Path(self.packet["stop_root"]).mkdir()

    def separated(self):
        return {**self.packet, "renderer_source_root": str(self.renderer),
                "oracle_source_root": str(self.oracle),
                "oracle_source": {"commit": "d" * 40, "tree": "e" * 40}}

    def test_legacy_packet_retains_exact_three_queries(self):
        requests = source_check_requests(self.packet)
        prefix = [str(self.git), "--no-optional-locks", "-C", str(self.renderer)]
        self.assertEqual(requests, [(prefix + ["rev-parse", "HEAD", "HEAD^{tree}"], ["a" * 40, "b" * 40]),
                                    (prefix + ["status", "--porcelain", "--untracked-files=all"], []),
                                    (prefix + ["cat-file", "-e", "a" * 40 + "^{commit}"], [])])

    def test_renderer_and_oracle_head_checks_are_distinct(self):
        packet = self.separated()
        requests = source_check_requests(packet)
        self.assertEqual(len(requests), 6)
        self.assertEqual(requests[0][0][3], str(self.renderer))
        self.assertEqual(requests[0][1], ["a" * 40, "b" * 40])
        self.assertEqual(requests[3][0][3], str(self.oracle))
        self.assertEqual(requests[3][1], ["d" * 40, "e" * 40])
        for index in (2, 5):
            self.assertEqual(requests[index][0][-3:], ["cat-file", "-e", "a" * 40 + "^{commit}"])

    def test_missing_paired_field_bad_oracle_identity_and_relative_root_fail(self):
        packet = self.separated()
        mutations = [lambda p: p.pop("oracle_source"), lambda p: p.pop("renderer_source_root"),
                     lambda p: p["oracle_source"].update(commit="bad"),
                     lambda p: p["oracle_source"].update(extra="unreviewed"),
                     lambda p: p.update(renderer_source_root="relative-source"),
                     lambda p: p.update(oracle_source_root=str(self.root / "missing"))]
        for mutate in mutations:
            changed = copy.deepcopy(packet)
            mutate(changed)
            with self.subTest(packet=changed), self.assertRaises(Stop):
                source_check_requests(changed)

    def test_both_checkout_identities_cleanliness_and_existence_are_enforced(self):
        packet = self.separated()
        requests = source_check_requests(packet)
        def result(index, invalid=None):
            stdout = ("\n".join(requests[index][1]) + ("\n" if requests[index][1] else "")).encode()
            if invalid == index:
                stdout = b"changed HEAD, tree, dirty state or existence\n"
            return subprocess.CompletedProcess(requests[index][0], 0, stdout=stdout, stderr=b"")
        with patch("tools.physical_supervisor.common.sealed_environment", return_value={}), \
             patch("tools.physical_supervisor.common.subprocess.run", side_effect=[result(i) for i in range(6)]) as run:
            self.assertEqual(len(verify_source(packet)), 6)
            self.assertEqual(run.call_count, 6)
        for invalid in range(6):
            with self.subTest(check=invalid), \
                 patch("tools.physical_supervisor.common.sealed_environment", return_value={}), \
                 patch("tools.physical_supervisor.common.subprocess.run", side_effect=[result(i, invalid) for i in range(6)]), \
                 self.assertRaises(Stop):
                verify_source(packet)

    def test_collector_consumes_only_exact_renderer_commit_fact_in_oracle_root(self):
        packet = self.separated()
        stage = {"name": "compositing"}
        control = self.root / "control"
        control.mkdir()
        owner = {"synthetic_cpu_supervisor": True}
        exclusive(control / "supervisor-identity.json", owner)
        checks = [{"argv": argv, "returncode": 0, "stdout_utf8": "\n".join(expected), "stderr_utf8": ""}
                  for argv, expected in source_check_requests(packet)]
        proof = {"schema": "physical-supervisor/source-preflight-v1", "packet_sha256": packet["packet_sha256"],
                 "stage": stage["name"], "source": packet["source"], "root": packet["oracle_source_root"],
                 "supervisor": owner, "git": pin(self.git), "checks": checks}
        exclusive(control / "source-preflight.json", proof)
        receipt = pin(control / "source-preflight.json")
        source_proof(packet, stage, control, receipt)
        adapter = prepare_subprocess_adapter(packet, stage, control, receipt)
        expected = ["git", "cat-file", "-e", packet["source"]["commit"] + "^{commit}"]
        with patch("subprocess.Popen", side_effect=AssertionError("No native process permitted")) as native, \
             patch("tools.physical_supervisor.collector.Gate"):
            with self.assertRaises(Stop):
                adapter.run(["git", "cat-file", "-e", packet["oracle_source"]["commit"] + "^{commit}"],
                            cwd=packet["oracle_source_root"], capture_output=True, check=True)
            self.assertEqual(adapter.run(expected, cwd=packet["oracle_source_root"], capture_output=True, check=True).returncode, 0)
            with self.assertRaises(Stop):
                adapter.run(expected, cwd=packet["oracle_source_root"], capture_output=True, check=True)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
