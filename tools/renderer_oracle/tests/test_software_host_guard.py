"""CPU-only controls for isolated discovery and retained failure evidence.

Synthetic discovery output never qualifies a native renderer or device.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import sdvk010_sun_native as guard
from tools.renderer_oracle.common import EvidenceError, pin


SUMMARY = b"""Devices:
========
GPU0:
    deviceType = PHYSICAL_DEVICE_TYPE_CPU
    deviceName = llvmpipe (synthetic unit fixture)
    driverName = llvmpipe
    driverID = DRIVER_ID_MESA_LLVMPIPE
"""


class SoftwareHostGuard(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sdvk-host-guard-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.icd = self.root / "lvp_icd.json"
        self.icd.write_text(json.dumps({"ICD": {"library_path": "libvulkan_lvp.so"}}))
        self.out = self.root / "qualification"
        self.environment = {
            "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_NAME": "synthetic-unit-host", "VK_DRIVER_FILES": str(self.icd),
            "VK_ICD_FILENAMES": str(self.icd), "DISPLAY": ":99",
            "WAYLAND_DISPLAY": "wayland-unit", "SDL_VIDEODRIVER": "x11",
            "LD_LIBRARY_PATH": "/synthetic/unit/lib",
        }

    @contextmanager
    def discovery(self, *, output=SUMMARY, errors=b"", outcome=0, environment=None):
        def launch(argv, *, stdout, stderr, env, check, timeout):
            stdout.write(output)
            stderr.write(errors)
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(argv, outcome)

        with patch.dict(os.environ, {**self.environment, **(environment or {})}, clear=True), \
                patch.object(sys, "platform", "linux"), \
                patch.object(os, "sched_getaffinity", return_value={0, 1}, create=True), \
                patch.object(guard.subprocess, "run", side_effect=launch) as command:
            yield command

    def receipt(self):
        evidence = self.out / "software-host"
        value = json.loads((evidence / "discovery.json").read_text())
        self.assertEqual(value["stdout"], pin(evidence / "vulkaninfo-summary.txt", relative_to=evidence))
        self.assertEqual(value["stderr"], pin(evidence / "vulkaninfo-summary.stderr.txt", relative_to=evidence))
        self.assertEqual(value["automatic_retries"], 0)
        self.assertEqual(value["command"]["timeout_seconds"], 30)
        return value

    def test_headless_device_query_preserves_renderer_environment_and_raw_evidence(self):
        with self.discovery(errors=b"retained synthetic warning\n") as command:
            host = guard.software_host_guard(self.out)
            command.assert_called_once()
            child = command.call_args.kwargs["env"]
            self.assertNotIn("DISPLAY", child)
            self.assertNotIn("WAYLAND_DISPLAY", child)
            for key in ("VK_DRIVER_FILES", "VK_ICD_FILENAMES", "SDL_VIDEODRIVER", "LD_LIBRARY_PATH"):
                self.assertEqual(child[key], self.environment[key])
            self.assertEqual(os.environ["DISPLAY"], ":99")
            self.assertEqual(os.environ["WAYLAND_DISPLAY"], "wayland-unit")
            self.assertEqual(command.call_args.kwargs["timeout"], 30)
            self.assertFalse(command.call_args.kwargs["check"])
        value = self.receipt()
        self.assertEqual(value["status"], "PASS")
        self.assertFalse(value["presentation_surface"])
        self.assertEqual(value["command"]["returncode"], 0)
        self.assertEqual(value["command"]["outcome"], "completed")
        self.assertEqual(value["identity"]["device_types"], ["PHYSICAL_DEVICE_TYPE_CPU"])
        self.assertEqual(host["discovery"], pin(self.out / "software-host/discovery.json", relative_to=self.out))
        self.assertEqual((self.out / "software-host/vulkaninfo-summary.txt").read_bytes(), SUMMARY)
        self.assertEqual((self.out / "software-host/vulkaninfo-summary.stderr.txt").read_bytes(),
                         b"retained synthetic warning\n")

    def test_missing_extra_physical_or_wrong_device_still_fails_closed(self):
        variants = {
            "empty": b"",
            "extra": SUMMARY + SUMMARY.replace(b"GPU0:", b"GPU1:"),
            "physical": SUMMARY.replace(b"PHYSICAL_DEVICE_TYPE_CPU", b"PHYSICAL_DEVICE_TYPE_DISCRETE_GPU"),
            "wrong-name": SUMMARY.replace(b"deviceName = llvmpipe", b"deviceName = physical-unit-device"),
            "missing-name": SUMMARY.replace(b"deviceName =", b"unknownName ="),
        }
        for name, output in variants.items():
            with self.subTest(name=name):
                self.out = self.root / name
                with self.discovery(output=output) as command:
                    with self.assertRaisesRegex(EvidenceError, "exactly one CPU llvmpipe"):
                        guard.software_host_guard(self.out)
                    command.assert_called_once()
                value = self.receipt()
                self.assertEqual(value["status"], "FAIL")
                self.assertEqual(value["command"]["returncode"], 0)
                self.assertEqual(value["error_type"], "EvidenceError")
                self.assertEqual((self.out / "software-host/vulkaninfo-summary.txt").read_bytes(), output)

    def test_nonzero_exit_with_valid_device_text_is_rejected_and_distinguished(self):
        for code in (1, -11):
            with self.subTest(returncode=code):
                self.out = self.root / ("exit-" + str(code))
                with self.discovery(outcome=code, errors=b"synthetic WSI failure\n") as command:
                    with self.assertRaisesRegex(EvidenceError, "exited with return code " + str(code)):
                        guard.software_host_guard(self.out)
                    command.assert_called_once()
                value = self.receipt()
                self.assertEqual(value["status"], "FAIL")
                self.assertEqual(value["command"]["returncode"], code)
                self.assertNotIn("identity", value)

    def test_timeout_retains_partial_streams_without_retry(self):
        timeout = subprocess.TimeoutExpired(["vulkaninfo", "--summary"], 30)
        with self.discovery(output=b"partial summary\n", errors=b"partial error\xff\n", outcome=timeout) as command:
            with self.assertRaises(subprocess.TimeoutExpired):
                guard.software_host_guard(self.out)
            command.assert_called_once()
        value = self.receipt()
        self.assertEqual(value["status"], "FAIL")
        self.assertTrue(value["command"]["attempted"])
        self.assertEqual(value["command"]["outcome"], "timed-out")
        self.assertIsNone(value["command"]["returncode"])
        self.assertEqual(value["error_type"], "TimeoutExpired")
        self.assertEqual((self.out / "software-host/vulkaninfo-summary.txt").read_bytes(), b"partial summary\n")
        self.assertEqual((self.out / "software-host/vulkaninfo-summary.stderr.txt").read_bytes(), b"partial error\xff\n")

    def test_launch_error_retains_empty_output_and_explicit_status(self):
        with self.discovery(output=b"", outcome=FileNotFoundError("synthetic missing vulkaninfo")) as command:
            with self.assertRaises(FileNotFoundError):
                guard.software_host_guard(self.out)
            command.assert_called_once()
        value = self.receipt()
        self.assertEqual(value["status"], "FAIL")
        self.assertEqual(value["command"]["outcome"], "launch-error")
        self.assertIsNone(value["command"]["returncode"])
        self.assertEqual(value["error_type"], "FileNotFoundError")
        self.assertEqual(value["stdout"]["bytes"], 0)
        self.assertEqual(value["stderr"]["bytes"], 0)

    def test_host_rejections_retain_unattempted_evidence_and_never_discover(self):
        variants = {
            "not-actions": {"GITHUB_ACTIONS": "false"},
            "not-hosted": {"RUNNER_ENVIRONMENT": "self-hosted"},
            "multiple-icds": {"VK_DRIVER_FILES": str(self.icd) + os.pathsep + str(self.icd)},
            "override": {"MESA_LOADER_DRIVER_OVERRIDE": "synthetic-physical-driver"},
        }
        for name, environment in variants.items():
            with self.subTest(name=name):
                self.out = self.root / name
                with self.discovery(environment=environment) as command:
                    with self.assertRaises(EvidenceError):
                        guard.software_host_guard(self.out)
                    command.assert_not_called()
                value = self.receipt()
                self.assertEqual(value["status"], "FAIL")
                self.assertFalse(value["command"]["attempted"])
                self.assertEqual(value["command"]["outcome"], "not-attempted")
                self.assertEqual(value["stdout"]["bytes"], 0)
                self.assertEqual(value["stderr"]["bytes"], 0)

    def test_invalid_text_fails_with_raw_bytes_preserved(self):
        with self.discovery(output=b"\xff") as command:
            with self.assertRaises(UnicodeDecodeError):
                guard.software_host_guard(self.out)
            command.assert_called_once()
        value = self.receipt()
        self.assertEqual(value["status"], "FAIL")
        self.assertEqual(value["command"]["returncode"], 0)
        self.assertEqual(value["error_type"], "UnicodeDecodeError")
        self.assertEqual((self.out / "software-host/vulkaninfo-summary.txt").read_bytes(), b"\xff")

    def test_a_second_call_cannot_replace_first_attempt_evidence(self):
        with self.discovery() as command:
            guard.software_host_guard(self.out)
            previous = (self.out / "software-host/discovery.json").read_bytes()
            with self.assertRaises(FileExistsError):
                guard.software_host_guard(self.out)
            command.assert_called_once()
        self.assertEqual((self.out / "software-host/discovery.json").read_bytes(), previous)


if __name__ == "__main__":
    unittest.main(verbosity=2)
