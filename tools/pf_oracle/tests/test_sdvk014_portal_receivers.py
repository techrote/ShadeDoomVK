"""Exact wall/flat tile-admission branches preserve portal trace ownership."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


ADAPTER = r"""
#include <iostream>
#include <string>
#include <vector>
enum class LevelMeshDrawType { Opaque, Portal };
constexpr int SECF_LM_DYNAMIC = 1;
struct Level { bool lightmaps = true; };
struct Sector { int Flags = SECF_LM_DYNAMIC; };
struct Side { Sector* sector; };
struct Dispatcher { struct Level* Level; };
struct Surface { bool IsSky = false; int LightmapTileIndex = -9; };
struct Array : std::vector<int> { void Push(int value) { push_back(value); } };
struct { Array AddedSurfaces; } Lightmap;
int allocations = 0;
int AddSurfaceToTile(int, const Surface&, int, bool) { ++allocations; return 37; }
void wall(Dispatcher& disp, Surface* surface, LevelMeshDrawType drawType)
{
    Sector sector; Side sideObject{&sector}; Side* side = &sideObject;
    const int info = 5, sampleDimension = 8;
    struct { int Index = 19; } sinfo;
    @WALL@
}
void flat(Dispatcher& disp, Surface& surf)
{
    Sector sector;
    struct { Sector* sector; } flatpart{&sector};
    const int info = 5, sampleDimension = 8;
    struct { int Index = 23; } sinfo;
    @FLAT@
}
int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    std::string test = argv[1];
    Level level; Dispatcher disp{&level}; Surface surface;
    bool receives = false;
    if (test == "ordinary-wall") { receives = true; wall(disp, &surface, LevelMeshDrawType::Opaque); }
    else if (test == "portal-wall") { wall(disp, &surface, LevelMeshDrawType::Portal); }
    else if (test == "sky-wall") { surface.IsSky = true; wall(disp, &surface, LevelMeshDrawType::Portal); }
    else if (test == "disabled-wall") { level.lightmaps = false; wall(disp, &surface, LevelMeshDrawType::Opaque); }
    else if (test == "non-sky-flat-portal") { receives = true; flat(disp, surface); }
    else if (test == "sky-flat-portal") { surface.IsSky = true; flat(disp, surface); }
    else return 3;
    if (surface.LightmapTileIndex != (receives ? 37 : -1) || allocations != int(receives) ||
        Lightmap.AddedSurfaces.size() != static_cast<unsigned int>(receives))
    { std::cerr << "portal-receiver-policy\n"; return 11; }
    std::cout << "PASS " << test << '\n';
}
"""


class PortalReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-portal-receiver-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        doom = (ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text()
        cls.wall = block(doom, "void DoomLevelMesh::CreateWallSurface(")
        cls.flat = block(doom, "void DoomLevelMesh::CreateFlatSurface(")
        start = cls.wall.index("if (disp.Level->lightmaps && !surface->IsSky")
        wall = cls.wall[start:cls.wall.index("SetSideLightmap(sinfo.Index);", start)]
        start = cls.flat.index("if (disp.Level->lightmaps && !surf.IsSky")
        flat = cls.flat[start:cls.flat.index("surf.LightList.Pos =", start)]

        def build(name: str, wall_branch: str) -> Path:
            source = root / (name + ".cpp")
            source.write_text(ADAPTER.replace("@WALL@", wall_branch).replace("@FLAT@", flat))
            return compile_fixture(source, output_dir=root, name=name)

        cls.current = build("current", wall)
        guard = " && drawType != LevelMeshDrawType::Portal"
        if wall.count(guard) != 1:
            raise AssertionError("exact portal wall receiver boundary changed")
        # Mark drawType used after removing the branch term under -Werror.
        cls.old = build("old-portal-tile", "(void)drawType;\n" + wall.replace(guard, ""))

    def test_wall_and_flat_receiver_boundaries(self) -> None:
        for case in ("ordinary-wall", "portal-wall", "sky-wall", "disabled-wall", "non-sky-flat-portal", "sky-flat-portal"):
            with self.subTest(case=case):
                result = subprocess.run([str(self.current), case], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pre_fix_portal_wall_tile_is_rejected(self) -> None:
        result = subprocess.run([str(self.old), "portal-wall"], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
        self.assertEqual(result.stderr.strip(), "portal-receiver-policy")

    def test_portal_trace_geometry_and_draw_ranges_remain_generated(self) -> None:
        portal = block(self.wall, "if (drawType == LevelMeshDrawType::Portal)")
        for statement in ("wallpart.MakeVertices(state, false);", "wallpart.RenderWall(state, HWWall::RWF_BLANK);",
                          "wallpart.LevelMeshInfo.Type = ST_NONE;", "wallpart.LevelMeshInfo.ControlSector = nullptr;"):
            self.assertIn(statement, portal)
        for statement in (
            "GeometryAllocInfo ginfo = AllocGeometry(numVertices, numIndexes);",
            "surface->PortalIndex = (drawType == LevelMeshDrawType::Portal) ? linePortals[side->linedef->Index()] : 0;",
            "surface->MeshLocation.NumElements = ginfo.IndexCount;",
            "Mesh.SurfaceIndexes[i] = sinfo.Index;",
            "Sides[sideIndex].Geometries.Push(ginfo);",
            "AddToDrawList(Sides[sideIndex].DrawRanges, drawType, pipelineID, ginfo.IndexStart, ginfo.IndexCount);",
        ):
            self.assertIn(statement, self.wall)
        admission = self.wall.index("if (disp.Level->lightmaps && !surface->IsSky")
        self.assertLess(self.wall.index("surface->PortalIndex ="), admission)
        self.assertGreater(self.wall.index("Mesh.SurfaceIndexes[i] = sinfo.Index;"), admission)
        self.assertGreater(self.wall.index("Sides[sideIndex].Geometries.Push(ginfo);"), admission)
        self.assertNotIn("drawType != LevelMeshDrawType::Portal", self.flat)


if __name__ == "__main__":
    unittest.main()
