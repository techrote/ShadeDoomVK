"""CPU-only injected Vulkan queries/wrappers; no GPU or loader required."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class CfxInstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.exe = cls.directory / ("fixture.exe" if os.name == "nt" else "fixture")
        compiler = os.environ.get("CFX_CXX") or shutil.which("cl" if os.name == "nt" else "c++")
        if not compiler:
            raise RuntimeError("CFX fixture requires cl in a VS developer shell (Windows) or c++ (Linux)")
        fixture = str(ROOT / "tools/pf_oracle/tests/cfx_capture_fixture.cpp")
        includes = [ROOT / "libraries/ZVulkan/include", ROOT / "src/common/rendering"]
        if Path(compiler).name.lower() in ("cl", "cl.exe"):
            command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/W4", "/UNDEBUG", *(["/fsanitize=address"] if os.environ.get("CFX_TEST_ASAN") == "1" else []), fixture,
                       *["/I" + str(p) for p in includes], "/Fe:" + str(cls.exe), "/Fo:" + str(cls.directory / "fixture.obj")]
        else:
            command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers", "-Wno-unused-parameter",
                       "-UNDEBUG", fixture, *["-I" + str(p) for p in includes], "-o", str(cls.exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_fixture(self, scenario, traced=True, resources=True):
        path = self.directory / (scenario + ".tsv")
        env = os.environ.copy()
        for key in ("CFX_TRACE_FILE", "CFX_RUN_ID", "CFX_RESOURCE_TRACE"):
            env.pop(key, None)
        if traced:
            env.update(CFX_TRACE_FILE=str(path), CFX_RUN_ID="synthetic-cfx006", CFX_RESOURCE_TRACE="1" if resources else "0")
        subprocess.run([str(self.exe), scenario], env=env, check=True, timeout=10)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_fault_empty_error_incomplete_unavailable_and_caps(self):
        text = self.run_fixture("faults")
        for event in ("device-fault-unavailable", "device-fault-empty", "device-fault-cap-truncated", "device-fault-return-truncated"):
            self.assertIn(event, text)
        self.assertIn("device-fault-count-return\taddresses=0 vendors=0 binary_bytes=0\t-4", text)
        self.assertIn("device-fault-data-return\taddresses=1 vendors=0 binary_bytes=0\t-13", text)
        self.assertIn("device-fault-data-return\taddresses=900 vendors=900 binary_bytes=104857600\t5", text)
        self.assertIn("checkpoint-count-return\tgraphics queue=", text)
        self.assertIn("count=0 capacity=0 truncated=0 api=void", text)
        self.assertIn("returned=900 capacity=256 truncated=1 api=void", text)
        self.assertIn("returned=0 capacity=256 truncated=0 api=void", text)
        self.assertEqual(text.count("gpu-checkpoint-confirmed"), 512)

    def test_concurrent_tail_rotation_keeps_whole_records(self):
        text = self.run_fixture("parallel")
        self.assertIn("rotated tail", text)
        rows = text.splitlines()[2:]
        self.assertEqual(len(rows), 127)
        self.assertTrue(all(len(row.split("\t")) == 9 for row in rows))
        self.assertTrue(all("\tparallel\t" in row for row in rows))

    def test_logger_outlives_renderer_atexit_callback(self):
        text = self.run_fixture("teardown")
        self.assertIn("early-setup", text)
        self.assertIn("late-teardown", text)

    def test_collection_exception_keeps_original_failure(self):
        text = self.run_fixture("handler")
        self.assertIn("device-lost-observed\tsynthetic-submit\t-4", text)
        self.assertIn("fault-collection-exception", text)

    def test_record_copy_submit_identity_and_full_fingerprint(self):
        text = self.run_fixture("resources")
        self.assertIn("run=synthetic-cfx006", text)
        self.assertIn("coverage=complete fnv1a64=0xe71fa2190541574b", text)
        self.assertIn("cmd_id=3 cmd=", text)
        self.assertIn("src_id=1 dst_id=2 src_offset=2 dst_offset=4 bytes=3", text)
        self.assertIn("synthetic-submit-buffer\tkind=command id=3", text)
        self.assertEqual(text.count("resource-destroy"), 3)

    def test_caps_omit_hash_without_dereference_and_keep_failure(self):
        text = self.run_fixture("caps")
        self.assertEqual(text.count("coverage=omitted-budget"), 2)
        self.assertEqual(text.count("resource-trace-truncated"), 1)
        self.assertNotIn("must-be-omitted", text)
        self.assertIn("device-lost-observed", text)

    def test_disabled_wrappers_preserve_copy_and_do_not_hash(self):
        self.assertEqual(self.run_fixture("disabled", traced=False), "")
        self.assertEqual(self.run_fixture("resourceoff", resources=False).count("upload-packed"), 0)

    def test_integration_uses_actual_command_and_upload_bytes(self):
        source = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.cpp").read_text(encoding="utf-8")
        self.assertLess(source.index("memcpy(data + datapos, src, size)"), source.index("CfxTrace::Upload("))
        self.assertIn("data + datapos, size", source)
        commands = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text(encoding="utf-8")
        self.assertIn("commands[i]->diagnosticId", commands)
        wait = commands.split("void VkCommandBufferManager::WaitForCommands(bool finish, bool uploadOnly)")[1]
        self.assertNotIn("vkGetQueueCheckpointDataNV(", wait)
        handler = (ROOT / "libraries/ZVulkan/include/zvulkan/vulkandevice.h").read_text(encoding="utf-8")
        self.assertLess(handler.index("result == VK_ERROR_DEVICE_LOST"), handler.index("CfxFault::QueryNV("))
        pipeline = (ROOT / "src/common/rendering/vulkan/pipelines/vk_renderpass.cpp").read_text(encoding="utf-8")
        for field in ("Layout.AsDWORD", "SpecialEffect", "EffectState", "VertexFormat"):
            self.assertIn("key.ShaderKey." + field, pipeline)


class CfxManifestTests(unittest.TestCase):
    def test_prepare_records_resource_mode_without_gpu_probe(self):
        import contextlib
        import importlib.util
        import io
        import json
        import sys
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location("cfx_capture", ROOT / "tools/cfx_capture.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe, iwad = root / "synthetic.exe", root / "synthetic.wad"
            exe.write_bytes(b"CPU fixture")
            iwad.write_bytes(b"legal synthetic input")
            args = ["cfx_capture.py", "--exe", str(exe), "--iwad", str(iwad), "--run-root", str(root), "--map", "MAP02", "--resource-trace"]
            def fake_run(command, **kwargs):
                if command == ["git", "diff", "HEAD", "--binary"]:
                    return subprocess.CompletedProcess(command, 0, b"", b"")
                self.assertEqual(command, ["vulkaninfo", "--summary"])
                return subprocess.CompletedProcess(command, 0, "Synthetic probe; no GPU used", "")
            with patch.object(sys, "argv", args), patch.object(module, "git", return_value=""), patch.object(module.platform, "platform", return_value="synthetic OS"), patch.object(module.subprocess, "run", side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 0)
            manifest = json.loads(next(root.glob("cfx-*/manifest.json")).read_text())
            self.assertEqual(manifest["status"], "PREPARED")
            self.assertTrue(manifest["environment"]["resource_trace"]["enabled"])
            self.assertEqual(manifest["environment"]["resource_trace"]["record_limit"], 8192)
            self.assertEqual(manifest["schema"], "cfx-002-run-v1")

    def test_off_mode_rejects_resource_trace_before_probe(self):
        command = ["python", str(ROOT / "tools/cfx_capture.py"), "--exe", "fake", "--iwad", "fake", "--run-root", "fake", "--map", "MAP02", "--mode", "off", "--resource-trace"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--resource-trace requires an enabled diagnostic mode", result.stderr)

    def test_capture_environment_cannot_inherit_resource_enablement(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cfx_capture", ROOT / "tools/cfx_capture.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        inherited = {key: "stale" for key in ("CFX_RUN_ID", "CFX_TRACE_FILE", "CFX_FAULT_BIN", "CFX_RESOURCE_TRACE")}
        inherited["unrelated"] = "keep"
        off = module.capture_environment(inherited, "off", "new", "trace", "fault", False)
        self.assertEqual(off, {"unrelated": "keep"})
        capture = module.capture_environment(inherited, "capture", "new", "trace", "fault", False)
        self.assertEqual(capture["CFX_RESOURCE_TRACE"], "0")
        self.assertEqual(capture["CFX_RUN_ID"], "new")
        capture = module.capture_environment(inherited, "capture", "new", "trace", "fault", True)
        self.assertEqual(capture["CFX_RESOURCE_TRACE"], "1")
        self.assertEqual(inherited["CFX_RESOURCE_TRACE"], "stale")
