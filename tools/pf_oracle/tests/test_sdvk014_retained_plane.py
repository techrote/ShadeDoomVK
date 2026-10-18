"""Corrected source-plane semantics cannot reuse indistinguishable wrong v5 RGB."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


class RetainedPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-retained-plane-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        data = ROOT / "src/common/rendering/hwrenderer/data"
        cls.loader = (ROOT / "src/maploader/maploader.cpp").read_text()
        cls.load = block(cls.loader, "bool MapLoader::LoadLightmap(")
        cls.header = (data / "hw_levelmesh.h").read_text()
        bounds = (ROOT / "src/common/utility/bounds.cpp").read_text()
        template = Path(__file__).with_name("sdvk014_retained_plane_fixture.cpp").read_text()
        template = template.replace("// @PRODUCTION_METHODS@", "\n".join(
            block(cls.header, signature) for signature in ("inline int LevelMesh::AllocTile(", "inline void LevelMesh::FreeTile(")))
        template = template.replace("// @PRODUCTION_BOUNDS@", "#define M_INFINITY 1e30f\n" + "\n".join(
            block(bounds, signature) for signature in ("BBox::BBox()", "void BBox::Clear()")))
        template = template.replace("// @PRODUCTION_SPAN@", block(cls.loader, "static bool IsValidLightmapPixelSpan("))
        admission = block(cls.load, "for (const TileEntry& entry : tileEntries)")
        mutation = block(cls.load[:cls.load.index("// Copy tile pixels to the texture")], "for (auto& binding : foundBindings)")
        template = template.replace("// @PRODUCTION_MUTATION@", mutation)

        def build(name: str, current: str) -> Path:
            source = root / (name + ".cpp")
            source.write_text(template.replace("// @PRODUCTION_ADMISSION@", current))
            return compile_fixture(source, output_dir=root,
                includes=(data, ROOT / "src/common/utility", ROOT / "src/common/thirdparty"), name=name)

        cls.current = build("current", admission)
        gate = block(admission, "if (tile->RuntimeBakeOnly)")
        cls.no_gate = build("old-admission", admission.replace(gate, ""))

    def execute(self, executable: Path, case: str, error: str | None = None) -> None:
        result = subprocess.run([str(executable), case], text=True, capture_output=True, timeout=10)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "PASS " + case)
        else:
            self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
            self.assertEqual(result.stderr.strip(), error)

    def test_current_admission_and_pool_retirement(self) -> None:
        for case in ("ordinary-v5", "inverted-v5", "pool-reset"):
            with self.subTest(case=case):
                self.execute(self.current, case)

    def test_old_wrong_plane_v5_rgb_is_not_a_current_bake(self) -> None:
        self.execute(self.no_gate, "inverted-v5", "wrong-plane-retained-payload-admitted")
        self.execute(self.no_gate, "ordinary-v5")

    def test_runtime_gate_precedes_all_retained_mutation(self) -> None:
        gate = self.load.index("if (tile->RuntimeBakeOnly)")
        self.assertLess(gate, self.load.index("!foundTiles.insert(tile).second"))
        self.assertLess(gate, self.load.index("tile->AtlasLocation.Width = entry->width;"))
        self.assertLess(gate, self.load.index("tile->NeedsInitialBake = false;"))
        self.assertLess(gate, self.load.index("const uint16_t* src ="))
        self.assertIn("runtimeBakeOnlyTiles++", self.load)
        self.assertIn("retained v5 RGB skipped", self.load)
        self.assertIn("tile = LightmapTile();", block(self.header, "inline void LevelMesh::FreeTile("))


if __name__ == "__main__":
    unittest.main()
