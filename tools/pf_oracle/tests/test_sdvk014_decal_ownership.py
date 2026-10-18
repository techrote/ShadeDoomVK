"""Execute the actual decal resolver against current live receiver surfaces.

TileBindings is deliberately transient/empty, as after BeginFrame. Current side
surfaces and checked tile receipts survive unchanged frames and change on rebuild.
No renderer/device or decal-owned tile allocation participates.
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
#include <stdexcept>
#include <string>
#include <vector>
enum DoomLevelMeshSurfaceType { ST_NONE, ST_MIDDLESIDE, ST_UPPERSIDE, ST_LOWERSIDE };
struct side_t { uint32_t id; uint32_t Index() const { return id; } };
struct sector_t { uint32_t id; uint32_t Index() const { return id; } };
struct seg_t { side_t* sidedef; };
struct HWDecalCreateInfo
{
    seg_t* seg;
    DoomLevelMeshSurfaceType lightmapType;
    sector_t* lightmapControlSector;
    int lightmaptile = -1; // original cached value: counterfactual only
};
@BINDING@;
template<class T> struct Array : std::vector<T>
{
    using std::vector<T>::vector;
    size_t Size() const { return this->size(); }
};
struct SideSurfaceBlock { int FirstSurface = -1; };
struct Surface { int LightmapTileIndex = -1; };
struct SurfaceInfo
{
    DoomLevelMeshSurfaceType Type;
    uint32_t TypeIndex;
    sector_t* ControlSector;
    int NextSurface;
};
struct Tile { LightmapTileBinding Binding; bool current = true; };
void I_FatalError(const char* message) { throw std::runtime_error(message); }
class DoomLevelMesh
{
public:
    // This map is only a rebuild deduplication table, never live ownership.
    std::map<LightmapTileBinding, int> TileBindings;
    Array<SideSurfaceBlock> Sides{15};
    Array<SurfaceInfo> DoomSurfaceInfos;
    struct { Array<Surface> Surfaces; } Mesh;
    Array<Tile> Tiles{60};
    const Tile& GetLightmapTile(int index) const
    {
        if (index < 0 || size_t(index) >= Tiles.Size() || !Tiles[index].current)
            throw std::runtime_error("stale-current-atlas-receipt");
        return Tiles[index];
    }
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
    mesh.Sides[13].FirstSurface = 0; mesh.Sides[14].FirstSurface = 4;
    mesh.DoomSurfaceInfos = {{ST_MIDDLESIDE,13,nullptr,1}, {ST_MIDDLESIDE,13,&control,2},
        {ST_MIDDLESIDE,13,&sibling,3}, {ST_UPPERSIDE,13,nullptr,-1}, {ST_MIDDLESIDE,14,nullptr,-1}};
    mesh.Mesh.Surfaces = {{7},{31},{37},{41},{43}};
    mesh.Tiles[7].Binding = ordinary;
    mesh.Tiles[31].Binding = key(ST_MIDDLESIDE,13,21);
    mesh.Tiles[37].Binding = key(ST_MIDDLESIDE,13,22);
    mesh.Tiles[41].Binding = key(ST_UPPERSIDE,13,0xffffffffu);
    mesh.Tiles[43].Binding = key(ST_MIDDLESIDE,14,0xffffffffu);
    int expected = 7;
    std::string expectedError;
    if (test == "ordinary" || test == "unchanged-frame") { mesh.TileBindings.clear(); }
    else if (test == "control-owner") { decal.lightmapControlSector = &control; expected = 31; }
    else if (test == "sibling-control") { decal.lightmapControlSector = &sibling; expected = 37; }
    else if (test == "upper") { decal.lightmapType = ST_UPPERSIDE; expected = 41; }
    else if (test == "other-side") { decal.seg = &otherSeg; expected = 43; }
    else if (test == "missing") { decal.lightmapType = ST_LOWERSIDE; expected = -1; }
    else if (test == "no-binding") { decal.lightmapType = ST_NONE; expected = -1; }
    else if (test == "no-seg") { decal.seg = nullptr; expected = -1; }
    else if (test == "no-side") { decal.seg = &missingSide; expected = -1; }
    else if (test == "rebuild" || test == "reload")
    {
        // An old numeric slot is now another live semantic owner. The receiver
        // surface, not a persistent decal or transient builder map, names 59.
        mesh.Mesh.Surfaces[0].LightmapTileIndex = 59;
        mesh.Tiles[7].Binding = key(ST_LOWERSIDE,14,22);
        mesh.Tiles[59].Binding = ordinary;
        mesh.TileBindings.emplace(key(ST_LOWERSIDE,14,22), 7);
        expected = 59;
    }
    else if (test == "removed") { mesh.Mesh.Surfaces[0].LightmapTileIndex = -1; expected = -1; }
    else if (test == "retired") { mesh.Tiles[7].current = false; expectedError = "stale-current-atlas-receipt"; }
    else if (test == "wrong-tile-binding")
    { mesh.Tiles[7].Binding = key(ST_MIDDLESIDE,13,21); expectedError = "Decal receiver references another lightmap binding"; }
    else return 3;
    const auto oldCount = mesh.Tiles.Size();
    int resolved = -999;
    try { resolved = mesh.ResolveDecalLightmapTile(decal); }
    catch (const std::exception& error)
    {
        if (expectedError == error.what()) { std::cout << "PASS " << test << '\n'; return 0; }
        std::cerr << error.what() << '\n'; return 11;
    }
    if (!expectedError.empty() || resolved != expected) { std::cerr << "current-semantic-decal-receiver\n"; return 11; }
    if (mesh.Tiles.Size() != oldCount) { std::cerr << "decal-allocated-own-tile\n"; return 11; }
    std::cout << "PASS " << test << '\n';
}
"""


class DecalOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-decal-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        cls.doom = (ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text()
        cls.decal = (ROOT / "src/rendering/hwrenderer/scene/hw_decal.cpp").read_text()
        cls.walls = (ROOT / "src/rendering/hwrenderer/scene/hw_walls.cpp").read_text()
        resolver = block(cls.doom, "int DoomLevelMesh::ResolveDecalLightmapTile(")
        binding = block((ROOT / "src/common/rendering/hwrenderer/data/hw_lightmaptile.h").read_text(),
                        "struct LightmapTileBinding\n")
        def build(name, definition):
            source = root / (name + ".cpp")
            source.write_text(ADAPTER.replace("@BINDING@", binding).replace("@RESOLVER@", definition))
            return compile_fixture(source, output_dir=root, name=name)
        cls.current = build("current", resolver)
        signature = resolver[:resolver.index("{")]
        cls.cached = build("cached-preconstruction", signature + "{ return decal.lightmaptile; }")
        cls.transient = build("transient-builder-table", signature + r"""{
            LightmapTileBinding binding;
            binding.Type = decal.lightmapType; binding.TypeIndex = decal.seg->sidedef->Index();
            binding.ControlSector = decal.lightmapControlSector ? decal.lightmapControlSector->Index() : 0xffffffffu;
            auto found = TileBindings.find(binding);
            return found == TileBindings.end() ? -1 : found->second;
        }""")
        owner = "decal.lightmapControlSector ? decal.lightmapControlSector->Index() : (uint32_t)0xffffffffUL"
        cls.wrong_control = build("wrong-control", resolver.replace(owner, "(uint32_t)0xffffffffUL"))

    def execute(self, executable, case, error=None):
        result = subprocess.run([str(executable), case], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0 if error is None else 11, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip() if error is None else result.stderr.strip(),
                         "PASS " + case if error is None else error)

    def test_current_semantic_receiving_tiles(self):
        for case in ("ordinary", "unchanged-frame", "control-owner", "sibling-control", "upper", "other-side",
                     "missing", "no-binding", "no-seg", "no-side", "rebuild", "reload", "removed", "retired", "wrong-tile-binding"):
            with self.subTest(case=case): self.execute(self.current, case)

    def test_preconstruction_and_transient_builder_counterfactuals_fail(self):
        for executable in (self.cached, self.transient):
            for case in ("ordinary", "unchanged-frame", "control-owner", "rebuild", "reload"):
                with self.subTest(executable=executable, case=case):
                    self.execute(executable, case, "current-semantic-decal-receiver")

    def test_control_owner_cannot_alias_other_floor(self):
        for case in ("control-owner", "sibling-control"):
            self.execute(self.wrong_control, case, "current-semantic-decal-receiver")
        self.execute(self.wrong_control, "ordinary")

    def test_all_producer_and_actual_consumer_calls_keep_semantics_and_checked_uv(self):
        producer = block(self.decal, "void HWWall::ProcessDecals(")
        self.assertIn("info.lightmapType = LevelMeshInfo.Type;", producer)
        self.assertIn("info.lightmapControlSector = LevelMeshInfo.ControlSector;", producer)
        self.assertNotIn("info.lightmaptile =", producer)
        draw = block(self.doom, "void DoomLevelMesh::AddSidesToDrawLists(")
        self.assertIn("info.ProcessDecal(di, state, dynlightindex, ResolveDecalLightmapTile(info));", draw)
        self.assertIn("TileBindings.clear();", block(self.doom, "void DoomLevelMesh::BeginFrame("))
        resolver = block(self.doom, "int DoomLevelMesh::ResolveDecalLightmapTile(")
        self.assertIn("Sides[sideIndex].FirstSurface", resolver)
        self.assertNotIn("TileBindings.find", resolver)
        self.assertNotIn("AllocTile", resolver)
        for signature in ("void HWDecalCreateInfo::ProcessDecal(", "void HWWall::ProcessDecal("):
            consumer = block(self.decal, signature)
            self.assertIn("!(decal->RenderFlags & RF_FULLBRIGHT) && lightmaptile >= 0", consumer)
            self.assertLess(consumer.index("GetLightmapTile(lightmaptile)"), consumer.index("tile->ToUV("))
        # Audit both dispatch routes and mirror decal processing, rather than
        # assuming only the cached main-view producer exists.
        self.assertIn("ProcessDecal(di->di, state, decal, normal);", producer)
        self.assertIn("ProcessDecals(di, state);", block(self.walls, "void HWWall::PutWall("))
        mirror = (ROOT / "src/rendering/hwrenderer/scene/hw_drawlistadd.cpp").read_text()
        self.assertIn("newwall->ProcessDecals(di, state);", block(mirror, "void HWDrawInfo::AddMirrorSurface("))


if __name__ == "__main__": unittest.main()
