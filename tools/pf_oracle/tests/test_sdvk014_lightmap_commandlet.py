"""Execute the real lightmap commandlet with bounded CPU-only services."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


class LightmapCommandletTests(unittest.TestCase):
    def test_build_only_saves_after_completion_and_targets_requested_map(self):
        source = (ROOT / "src/commandlets/lightmapcmd.cpp").read_text()
        methods = [
            block(source, signature)
            for signature in (
                "DoomLevelMesh& LoadLightmapCommandMap(",
                "void LightmapBuildCmdlet::OnCommand(",
                "void LightmapDeleteCmdlet::OnCommand(",
            )
        ]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "commandlet_methods.inc").write_text("\n".join(methods))
            executable = compile_fixture(
                "tools/pf_oracle/tests/sdvk014_lightmap_commandlet_fixture.cpp",
                output_dir=directory,
                includes=[directory],
            )
            subprocess.run([str(executable)], check=True, timeout=10)
