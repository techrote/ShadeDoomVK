"""CPU-only tests for the SDVK-009 timeout discriminator.

No renderer, Vulkan loader, device, ptrace attach or network access is used.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.renderer_oracle import sdvk009_timeout_discriminator as discriminator
from tools.renderer_oracle.common import EvidenceError


class TimeoutDiscriminatorTests(unittest.TestCase):
    def exact_argv(self):
        return ["/tmp/vkdoom", "-width", "640", "-height", "480", "+map", "SDVSHDW",
                "-sdvkobserveframes", "1", "-sdvkobservewarmup", "120",
                "-sdvkobservemode", "state", "-sdvkobservequit"]

    def test_exact_workload_and_deadline_are_locked(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(discriminator.validate_renderer_argv(self.exact_argv(), 600, {}))
        wrong_warmup = self.exact_argv()
        wrong_warmup[wrong_warmup.index("-sdvkobservewarmup") + 1] = "119"
        variants = [
            (self.exact_argv(), 601),
            (wrong_warmup, 600),
            ([*self.exact_argv(), "-sdvkcollisionsnapshot", "/tmp/collision"], 600),
        ]
        for argv, timeout in variants:
            with self.subTest(argv=argv, timeout=timeout), patch.dict(os.environ, {}, clear=True), self.assertRaises(EvidenceError):
                discriminator.validate_renderer_argv(argv, timeout, {})

    def test_cfx_environment_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(EvidenceError):
            discriminator.validate_renderer_argv(self.exact_argv(), 600, {"CFX_RESOURCE_TRACE": "1"})

    def test_proc_sample_and_thread_snapshot_are_bounded_cpu_only(self):
        sample = discriminator.process_sample(os.getpid(), 0.0, Path.cwd())
        self.assertEqual(sample["pid"], os.getpid())
        self.assertTrue(sample["alive"])
        self.assertIn("cpu_seconds", sample["stat"])
        self.assertIn("stdout.log", sample["output_progress"])
        with tempfile.TemporaryDirectory(prefix="sdvk009-timeout-proc-") as temporary:
            result = discriminator.collect_proc_snapshot(os.getpid(), Path(temporary) / "snapshot")
            self.assertGreaterEqual(len(result["threads"]), 1)
            self.assertLessEqual(len(result["threads"]), discriminator.MAX_THREADS)
            self.assertLessEqual(len(result["fds"]), discriminator.MAX_FDS)
            self.assertTrue((Path(temporary) / "snapshot/manifest.json").is_file())

    def test_preregistration_constants_cannot_grant_acceptance(self):
        self.assertEqual(discriminator.DEADLINE_SECONDS, 600)
        self.assertEqual(discriminator.WARMUP_FRAMES, 120)
        self.assertEqual(discriminator.RETAINED_FRAMES, 1)
        self.assertEqual(discriminator.EXTENT, [640, 480])
        self.assertEqual(discriminator.RENDERER_COMMIT, "14c2ecefad41374d39a8fb9d369d510251b9dd6e")


if __name__ == "__main__":
    unittest.main()
