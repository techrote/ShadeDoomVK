"""Current semantic decal receiver lookup; CPU-only, no decal tile allocation.

The exact production resolver executes against changing current binding maps.
The old mesh-builder cached -1, wrong control owner and stale slot counterfactuals
must fail independently of the centralized atlas receipt validation contract.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


ADAPTER = r"""
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
enum DoomLevelMeshSurfaceType { ST_NONE, ST_MIDDLESIDE, ST_UPPERSIDE, ST_LOWERSIDE };
struct side_t { uint32_t id; uint32_t Index() const { return id; } };
struct sector_t { uint32_t id; uint32_t Index() const { return id; } };
struct seg_t { side_t* sidedef; };
struct HWDecalCreateInfo
{
    seg_t* seg;
    DoomLevelMeshSurfaceType lightmapType;
    sector_t* lightmapControlSector;
    int lightmaptile = -1; // original preconstruction cached value, negative only
};
@BINDING@;
class DoomLevelMesh
{
public:
    std::map<LightmapTileBinding, int> TileBindings;
    int ResolveDecalLightmapTile(const HWDecalCreateInfo&) const;
};
@RESOLVER@
int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    const std::string test = argv[1];
    side_t side{13}, otherSide{14};
    sector_t control{21}, sibling{22};
    seg_t seg{&side}, otherSeg{&otherSide}, missingSide{nullptr};
    HWDecalCreateInfo decal{&seg, ST_MIDDLESIDE, nullptr};
    DoomLevelMesh mesh;
    auto key = [](uint32_t type, uint32_t sideId, uint32_t owner)
    {
        LightmapTileBinding binding;
        binding.Type = type; binding.TypeIndex = sideId; binding.ControlSector = owner;
        return binding;
    };
    const auto ordinary = key(ST_MIDDLESIDE, 13, 0xffffffffu);
    mesh.TileBindings.emplace(ordinary, 7);
    mesh.TileBindings.emplace(key(ST_MIDDLESIDE, 13, 21), 31);
    mesh.TileBindings.emplace(key(ST_MIDDLESIDE, 13, 22), 37);
    mesh.TileBindings.emplace(key(ST_UPPERSIDE, 13, 0xffffffffu), 41);
    mesh.TileBindings.emplace(key(ST_MIDDLESIDE, 14, 0xffffffffu), 43);
    int expected = 7;
    if (test == "ordinary") {}
    else if (test == "control-owner") { decal.lightmapControlSector = &control; expected = 31; }
    else if (test == "sibling-control") { decal.lightmapControlSector = &sibling; expected = 37; }
    else if (test == "upper") { decal.lightmapType = ST_UPPERSIDE; expected = 41; }
    else if (test == "other-side") { decal.seg = &otherSeg; expected = 43; }
    else if (test == "missing") { decal.lightmapType = ST_LOWERSIDE; expected = -1; }
    else if (test == "no-binding") { decal.lightmapType = ST_NONE; expected = -1; }
    else if (test == "no-seg") { decal.seg = nullptr; expected = -1; }
    else if (test == "no-side") { decal.seg = &missingSide; expected = -1; }
    else if (test == "rebuild")
    {
        if (mesh.ResolveDecalLightmapTile(decal) != 7) { std::cerr << "initial-receiver\n"; return 11; }
        mesh.TileBindings.erase(ordinary);
        // The old numeric slot can now mean a different semantic owner.
        mesh.TileBindings.emplace(key(ST_LOWERSIDE, 14, 22), 7);
        mesh.TileBindings.emplace(ordinary, 59);
        expected = 59;
    }
    else if (test == "removed") { mesh.TileBindings.erase(ordinary); expected = -1; }
    else return 3;
    const auto oldCount = mesh.TileBindings.size();
    const int resolved = mesh.ResolveDecalLightmapTile(decal);
    if (resolved != expected) { std::cerr << "current-semantic-decal-receiver\n"; return 11; }
    if (mesh.TileBindings.size() != oldCount) { std::cerr << "decal-allocated-own-tile\n"; return 11; }
    std::cout << "PASS " << test << '\n';
}
"""


class DecalOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-decal-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        cls.doom = (ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text()
        cls.decal = (ROOT / "src/rendering/hwrenderer/scene/hw_decal.cpp").read_text()
        cls.walls = (ROOT / "src/rendering/hwrenderer/scene/hw_walls.cpp").read_text()
        resolver = block(cls.doom, "int DoomLevelMesh::ResolveDecalLightmapTile(")
        binding = block((ROOT / "src/common/rendering/hwrenderer/data/hw_lightmaptile.h").read_text(),
                        "struct LightmapTileBinding\n")

        def build(name: str, definition: str) -> Path:
            source = root / (name + ".cpp")
            source.write_text(ADAPTER.replace("@BINDING@", binding).replace("@RESOLVER@", definition))
            return compile_fixture(source, output_dir=root, name=name)

        cls.current = build("current", resolver)
        signature = resolver[:resolver.index("{")]
        cls.cached = build("cached-preconstruction", signature + "{ return decal.lightmaptile; }")
        owner = "decal.lightmapControlSector ? decal.lightmapControlSector->Index() : (uint32_t)0xffffffffUL"
        if owner not in resolver:
            raise AssertionError("exact control-owner lookup boundary changed")
        cls.wrong_control = build("wrong-control", resolver.replace(owner, "(uint32_t)0xffffffffUL"))

    def execute(self, executable: Path, case: str, error: str | None = None) -> None:
        result = subprocess.run([str(executable), case], capture_output=True, text=True, timeout=10)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "PASS " + case)
        else:
            self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
            self.assertEqual(result.stderr.strip(), error)

    def test_current_semantic_receiving_tiles(self) -> None:
        for case in ("ordinary", "control-owner", "sibling-control", "upper", "other-side", "missing",
                     "no-binding", "no-seg", "no-side", "rebuild", "removed"):
            with self.subTest(case=case):
                self.execute(self.current, case)

    def test_original_preconstruction_minus_one_is_not_a_receiver(self) -> None:
        for case in ("ordinary", "control-owner", "sibling-control", "upper"):
            with self.subTest(case=case):
                self.execute(self.cached, case, "current-semantic-decal-receiver")

    def test_control_owner_cannot_alias_other_floor(self) -> None:
        self.execute(self.wrong_control, "control-owner", "current-semantic-decal-receiver")
        self.execute(self.wrong_control, "sibling-control", "current-semantic-decal-receiver")
        self.execute(self.wrong_control, "ordinary")

    def test_producer_capture_and_actual_consumer_are_joined(self) -> None:
        producer = block(self.decal, "void HWWall::ProcessDecals(")
        self.assertIn("info.lightmapType = LevelMeshInfo.Type;", producer)
        self.assertIn("info.lightmapControlSector = LevelMeshInfo.ControlSector;", producer)
        self.assertNotIn("info.lightmaptile =", producer)
        draw = block(self.doom, "void DoomLevelMesh::AddSidesToDrawLists(")
        self.assertIn("info.ProcessDecal(di, state, dynlightindex, ResolveDecalLightmapTile(info));", draw)
        consumer = block(self.decal, "void HWDecalCreateInfo::ProcessDecal(")
        self.assertIn("int lightmaptile) const", consumer)
        self.assertIn("!(decal->RenderFlags & RF_FULLBRIGHT) && lightmaptile >= 0", consumer)
        self.assertLess(consumer.index("GetLightmapTile(lightmaptile)"), consumer.index("tile->ToUV("))
        # The original mesh construction precondition is still real: tiles do
        # not exist yet, so caching this numeric value cannot be made correct.
        for signature in ("void HWWall::DoTexture(", "void HWWall::BuildFFBlock("):
            self.assertIn("lightmaptile = -1;", block(self.walls, signature))


if __name__ == "__main__":
    unittest.main()
