"""No-renderer regression tests for bounded hosted-CI coordination helpers.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / "tools" / "ci"


@unittest.skipUnless(shutil.which("bash"), "Bash is not installed")
class ParallelDependencies(unittest.TestCase):
    def exercise(self, *, system_failure: bool = False, fetch_failure: bool = False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            handshake = root / "handshake"
            handshake.mkdir()
            fake = binary / "python3"
            fake.write_text("#!/bin/sh\n"
                            "echo fetch-started\n"
                            "touch \"$TEST_HANDSHAKE_DIR/fetch\"\n"
                            "i=0; until test -f \"$TEST_HANDSHAKE_DIR/system\"; do\n"
                            "  i=$((i+1)); [ \"$i\" -lt 80 ] || exit 78; sleep 0.05\n"
                            "done\n"
                            "echo fetch-completed\n"
                            "exit \"$TEST_FETCH_EXIT\"\n", encoding="utf-8")
            fake.chmod(0o755)
            cmd = ('echo system-started; '
                   'touch "$TEST_HANDSHAKE_DIR/system"; '
                   'i=0; until test -f "$TEST_HANDSHAKE_DIR/fetch"; do '
                   'i=$((i+1)); [ "$i" -lt 80 ] || exit 79; sleep 0.05; done; '
                   'echo system-completed; exit "$TEST_SYSTEM_EXIT"')
            env = dict(os.environ, RUNNER_OS="Linux", RUNNER_TEMP=str(root),
                       SDVK_SYSTEM_DEPS_COMMAND=cmd, TEST_HANDSHAKE_DIR=str(handshake),
                       TEST_SYSTEM_EXIT="13" if system_failure else "0",
                       TEST_FETCH_EXIT="17" if fetch_failure else "0",
                       PATH=str(binary) + os.pathsep + os.environ["PATH"])
            return subprocess.run(["bash", str(CI / "parallel_hosted_deps.sh")],
                                  cwd=ROOT, env=env, text=True, capture_output=True,
                                  timeout=15)

    def test_tasks_actually_overlap_and_both_logs_are_retained(self):
        run = self.exercise()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        for event in ("system-started", "system-completed", "fetch-started", "fetch-completed"):
            self.assertIn(event, run.stdout)
        self.assertIn("exit status: 0; ZMusic exit status: 0", run.stdout)

    def test_system_failure_cannot_be_hidden_by_successful_fetch(self):
        run = self.exercise(system_failure=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("exit status: 13; ZMusic exit status: 0", run.stdout)
        self.assertIn("fetch-completed", run.stdout)

    def test_fetch_failure_cannot_be_hidden_by_successful_system_packages(self):
        run = self.exercise(fetch_failure=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("exit status: 0; ZMusic exit status: 17", run.stdout)
        self.assertIn("system-completed", run.stdout)

    def test_windows_does_not_start_unneeded_fetch(self):
        run = subprocess.run(["bash", str(CI / "parallel_hosted_deps.sh")], cwd=ROOT,
                             env=dict(os.environ, RUNNER_OS="Windows", RUNNER_TEMP=""),
                             text=True, capture_output=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "")


@unittest.skipUnless(shutil.which("bash") and shutil.which("tar") and shutil.which("xz"),
                     "Bash, tar and xz are required to prove the existing archive format")
class LosslessArchive(unittest.TestCase):
    def test_exact_allowlist_and_input_bytes_survive_xz_threads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "build"
            build.mkdir()
            originals = {}
            for subdir in ("renderer-native", "renderer-sdvk009-publication", "renderer-sdvk158"):
                directory = build / subdir / "captures"
                directory.mkdir(parents=True)
                for name, content in (("input.wad", (b"doom" * 8192) + bytes(range(256))),
                                      ("receipt.json", b'{"status":"PASS"}\n')):
                    path = directory / name
                    path.write_bytes(content)
                    originals[str(path.relative_to(build))] = hashlib.sha256(content).hexdigest()
            (build / "do-not-archive").mkdir()
            (build / "do-not-archive" / "secret").write_bytes(b"not a renderer packet")
            target = root / "renderer-software-vulkan.tar.xz"
            result = subprocess.run(["bash", str(CI / "package_renderer_evidence.sh"), str(build), str(target)],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(target.is_file())
            uncompressed = root / "unpacked"
            uncompressed.mkdir()
            subprocess.run(["tar", "-xJf", str(target), "-C", str(uncompressed)], check=True, timeout=30)
            self.assertEqual({str(p.relative_to(uncompressed)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in uncompressed.rglob("*") if p.is_file()}, originals)
            self.assertNotIn("do-not-archive", subprocess.run(["tar", "-tJf", str(target)],
                                   check=True, capture_output=True, text=True, timeout=30).stdout)
            self.assertEqual(hashlib.sha256((build / "renderer-native/captures/input.wad").read_bytes()).hexdigest(),
                             originals["renderer-native/captures/input.wad"])

    def test_failed_early_run_preserves_partial_evidence_and_empty_input_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / "build"
            build.mkdir()
            archive = Path(directory) / "partial.tar.xz"
            script = ["bash", str(CI / "package_renderer_evidence.sh"), str(build), str(archive)]
            subprocess.run(script, check=True, timeout=5)
            self.assertFalse(archive.exists())
            (build / "renderer-sdvk008-preflight").mkdir()
            (build / "renderer-sdvk008-preflight" / "vulkaninfo-summary.stderr.txt").write_text("failure evidence")
            subprocess.run(script, check=True, timeout=10)
            files = subprocess.run(["tar", "-tJf", str(archive)], check=True,
                                   text=True, capture_output=True, timeout=10).stdout
            self.assertIn("renderer-sdvk008-preflight/vulkaninfo-summary.stderr.txt", files)


class PublicationTimings(unittest.TestCase):
    def test_reports_all_four_unmodified_stage_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steps = root / "steps"
            steps.mkdir()
            start = datetime(2026, 10, 31, tzinfo=timezone.utc)
            stages = ("compositing-control", "shadow-control", "shadow-witness-1", "shadow-witness-2")
            before = {}
            for index, stage in enumerate(stages):
                receipt = steps / (stage + ".json")
                receipt.write_text(json.dumps({"name": stage, "status": "PASS",
                    "started_utc": start.isoformat(),
                    "finished_utc": (start + timedelta(minutes=index + 1)).isoformat()}), encoding="utf-8")
                before[stage] = receipt.read_bytes()
            summary = root / "summary.md"
            run = subprocess.run([sys.executable, str(CI / "renderer_publication_timings.py"), str(root)],
                env=dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)), text=True,
                capture_output=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("10.0 min", run.stdout)
            self.assertIn("4/4", run.stdout)
            self.assertIn("sharding profile", summary.read_text())
            for stage in stages:
                self.assertEqual((steps / (stage + ".json")).read_bytes(), before[stage])

    def test_missing_process_receipt_is_not_invented(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run([sys.executable, str(CI / "renderer_publication_timings.py"), directory],
                                 text=True, capture_output=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("0/4", run.stdout)
            self.assertEqual(run.stdout.count("Not reached"), 4)

    def test_invalid_timestamps_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steps = root / "steps"
            steps.mkdir()
            (steps / "shadow-control.json").write_text(json.dumps({
                "name": "shadow-control", "status": "PASS", "started_utc": "2026-10-31T02:00:00+00:00",
                "finished_utc": "2026-10-31T01:00:00+00:00"}), encoding="utf-8")
            run = subprocess.run([sys.executable, str(CI / "renderer_publication_timings.py"), str(root)],
                                 text=True, capture_output=True, timeout=5)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("finished before it started", run.stderr)


if __name__ == "__main__":
    unittest.main()
