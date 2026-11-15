"""Native production allocator regression: bounds, concurrent ranges and ABI."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compilation_command, is_msvc, select_compiler

ROOT = Path(__file__).resolve().parents[3]


class ActorShadowBufferNative(unittest.TestCase):
    def test_actual_concurrent_allocator_and_record_abi(self):
        compiler = select_compiler()
        with tempfile.TemporaryDirectory(prefix="actor-shadowbuffer-") as directory:
            output = Path(directory) / ("fixture.exe" if is_msvc(compiler) else "fixture")
            includes = [ROOT / path for path in (
                "src/common/rendering/vulkan", "src/common/rendering/hwrenderer/data",
                "src/common/utility", "src/common/thirdparty", "src/common/engine", "src",
            )]
            command = compilation_command(compiler,
                ROOT / "tools/pf_oracle/tests/actor_shadowbuffer_fixture.cpp", includes, output)
            if not is_msvc(compiler):
                command.insert(1, "-pthread")
            subprocess.run(command, cwd=directory, check=True, timeout=120)
            result = subprocess.run([str(output)], check=True, timeout=30,
                capture_output=True, text=True)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["status"], "PASS")
        self.assertEqual(actual["capacity"], actual["concurrent_slots"])
        self.assertEqual(actual["buffer_bytes"], actual["capacity"] * actual["record_stride_bytes"])
        self.assertEqual(actual["capacity"], 4096)
        self.assertEqual(actual["record_stride_bytes"], 1072)


if __name__ == "__main__":
    unittest.main()
