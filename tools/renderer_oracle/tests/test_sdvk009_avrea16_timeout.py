"""CPU-only tests for the Avrea 16-vCPU SDVK-009 guard."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.renderer_oracle import sdvk009_avrea16_timeout as avrea
from tools.renderer_oracle.common import EvidenceError


class Avrea16GuardTests(unittest.TestCase):
    def environment(self, manifest):
        return {
            "GITHUB_ACTIONS": "true",
            "RUNNER_NAME": "synthetic-avrea",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "SDVK_REQUESTED_RUNNER": avrea.RUNNER_LABEL,
            "VK_DRIVER_FILES": str(manifest),
            "VK_ICD_FILENAMES": str(manifest),
        }

    def test_exact_label_affinity_and_lavapipe_are_required(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-avrea16-") as temporary:
            manifest = Path(temporary) / "lvp_icd.x86_64.json"
            manifest.write_text(json.dumps({"ICD": {"library_path": "libvulkan_lvp.so"}}))
            env = self.environment(manifest)
            with patch.dict(os.environ, env, clear=True), patch.object(avrea.sys, "platform", "linux"),                     patch.object(avrea.os, "sched_getaffinity", return_value=set(range(16))),                     patch.object(avrea.os, "cpu_count", return_value=16):
                result = avrea.avrea16_software_guard()
            self.assertEqual(result["requested_runner"], avrea.RUNNER_LABEL)
            self.assertEqual(result["expected_vcpus"], 16)
            self.assertEqual(len(result["allowed_cpus"]), 16)
            self.assertEqual(result["provider"], "avrea")

            variants = [
                ({**env, "SDVK_REQUESTED_RUNNER": "avrea-ubuntu-24.04-32-vcpu"}, set(range(16))),
                (env, set(range(4))),
                ({**env, "VK_LOADER_DRIVERS_SELECT": "*"}, set(range(16))),
            ]
            for changed, affinity in variants:
                with self.subTest(changed=changed, affinity=len(affinity)),                         patch.dict(os.environ, changed, clear=True), patch.object(avrea.sys, "platform", "linux"),                         patch.object(avrea.os, "sched_getaffinity", return_value=affinity),                         patch.object(avrea.os, "cpu_count", return_value=16), self.assertRaises(EvidenceError):
                    avrea.avrea16_software_guard()

    def test_hardware_icd_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-avrea16-hardware-") as temporary:
            manifest = Path(temporary) / "lvp_icd.x86_64.json"
            manifest.write_text(json.dumps({"ICD": {"library_path": "libvulkan_intel.so"}}))
            with patch.dict(os.environ, self.environment(manifest), clear=True),                     patch.object(avrea.sys, "platform", "linux"),                     patch.object(avrea.os, "sched_getaffinity", return_value=set(range(16))),                     patch.object(avrea.os, "cpu_count", return_value=16), self.assertRaises(EvidenceError):
                avrea.avrea16_software_guard()


if __name__ == "__main__":
    unittest.main()
