"""Actual immediate producer/update functions preserve per-facing bake ownership."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


class ControlledVertexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-controlled-vertices-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        source = (ROOT / "src/rendering/hwrenderer/hw_vertexbuilder.cpp").read_text()
        tile = (ROOT / "src/common/rendering/hwrenderer/data/hw_lightmaptile.h").read_text()
        template = Path(__file__).with_name("sdvk014_controlled_vertex_fixture.cpp").read_text()
        for marker, signature in (
            ("FIND_3D_FLOOR", "static F3DFloor *Find3DFloor("),
            ("UPDATE_PLANE_VERTICES", "static void UpdatePlaneVertices("),
            ("UPDATE_PLANE_LIGHTMAP", "static void UpdatePlaneLightmap("),
        ):
            template = template.replace("// @PRODUCTION_" + marker + "@", block(source, signature))
        template = template.replace("// @PRODUCTION_TO_UV@", block(tile, "FVector2 ToUV(const FVector3& vert, float textureSize) const"))
        current = block(source, "static int CreateIndexedVertices(")
        retained = json.loads(Path(__file__).with_name("fixtures").joinpath("sdvk014-controlled-plane-pre-fix.json").read_text())
        old = retained["functions"]["vertices"]
        if hashlib.sha256(old["content"].encode()).hexdigest() != old["sha256"]:
            raise AssertionError("retained immediate producer source changed")

        def build(name, function, prelude=""):
            path = root / (name + ".cpp")
            path.write_text(prelude + template.replace("// @PRODUCTION_CREATE_INDEXED_VERTICES@", function))
            return compile_fixture(path, output_dir=root, name=name)

        cls.current = build("current", current)
        cls.old = build("retained-pre-fix", old["content"], "#define SDVK014_LEGACY_VERTEX\n")

    def execute(self, executable, case, error=None):
        result = subprocess.run([str(executable), case], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0 if error is None else 11, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip() if error is None else result.stderr.strip(), "PASS " + case if error is None else error)

    def test_actual_both_faces_have_distinct_sampled_UVs_pages_and_current_height_spans(self):
        for case in ("both", "normal", "inverted", "inverted-both", "unlightmapped-both", "self-source-height-span"):
            with self.subTest(case=case):
                self.execute(self.current, case)

    def test_retained_pre_fix_shared_stream_samples_the_wrong_actual_tile(self):
        self.execute(self.old, "both", "opposite-facing-tile-overwrite")
        self.execute(self.old, "unlightmapped-both")


if __name__ == "__main__":
    unittest.main()
