"""Exact flat bake-target consumer rejects neighboring source-plane aliases."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


ADAPTER = r"""
#include <cstdint>
#include <iostream>
#include <vector>
template<class T> struct TArray : std::vector<T>
{
    using std::vector<T>::vector;
    void Push(const T& value) { this->push_back(value); }
};
enum DoomLevelMeshSurfaceType { ST_NONE, ST_MIDDLESIDE, ST_UPPERSIDE, ST_LOWERSIDE, ST_CEILING, ST_FLOOR };
struct sector_t { int id; int lightmapHeightGroup[2]{1,1}; int Index() const { return id; } };
struct subsector_t { sector_t* sector; };
struct Binding { uint32_t Type, TypeIndex, ControlSector; };
struct Plane { float X,Y,Z,W; };
struct LightmapTile { struct Binding Binding; struct Plane Plane; };
struct DoomSurfaceInfo
{
    DoomLevelMeshSurfaceType Type;
    sector_t* ControlSector;
    int NextSurface = -1, NextSubsectorSurface = -1;
};
struct { TArray<subsector_t> subsectors; } level;
class DoomLevelMesh
{
public:
    struct { struct Surface { struct Plane Plane; }; TArray<Surface> Surfaces; } Mesh;
    struct Side { int FirstSurface = -1; };
    TArray<Side> Sides;
    TArray<TArray<int>> VisibleSides, VisibleSubsectors;
    TArray<int> SubsectorSurfaces;
    TArray<DoomSurfaceInfo> DoomSurfaceInfos;
    void GetVisibleSurfaces(LightmapTile*, TArray<int>&);
};
@PRODUCTION@
int main()
{
    sector_t target{1}, otherHeight{2}, control{23}, sibling{24};
    otherHeight.lightmapHeightGroup[0] = 2;
    level.subsectors.Push({&target}); level.subsectors.Push({&otherHeight});
    DoomLevelMesh mesh;
    mesh.VisibleSubsectors.Push({0,1});
    mesh.SubsectorSurfaces = {0,4};
    mesh.Mesh.Surfaces = {{{0,0,1,80}}, {{0,0,1,32}}, {{0,0,1,80}}, {{0,0,1,80}}, {{0,0,1,80}}};
    mesh.DoomSurfaceInfos = {
        {ST_FLOOR,&control,-1,1}, {ST_FLOOR,&control,-1,2},
        {ST_FLOOR,&sibling,-1,3}, {ST_CEILING,&control,-1,-1}, {ST_FLOOR,&control,-1,-1}};
    LightmapTile tile{{ST_FLOOR,0,23},{0,0,1,80}};
    TArray<int> targets;
    mesh.GetVisibleSurfaces(&tile, targets);
    if (targets.size() != 1 || targets[0] != 0)
    { std::cerr << "cross-source-plane-bake-target\n"; return 11; }
    // The ordinary no-control height group intentionally includes nearby
    // different planes for bake seam/padding coverage. Do not narrow it.
    mesh.DoomSurfaceInfos[0].ControlSector = nullptr;
    mesh.DoomSurfaceInfos[1].ControlSector = nullptr;
    mesh.Mesh.Surfaces[1].Plane.W = 78;
    tile.Binding.ControlSector = 0xffffffffU;
    targets.clear();
    mesh.GetVisibleSurfaces(&tile, targets);
    if (targets.size() != 2 || targets[0] != 0 || targets[1] != 1)
    { std::cerr << "ordinary-neighbor-coverage-changed\n"; return 12; }
    std::cout << "PASS current-plane\n";
}
"""


class FlatBakePlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-bake-plane-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        production = block((ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text(),
                           "void DoomLevelMesh::GetVisibleSurfaces(")

        def build(name: str, function: str) -> Path:
            source = root / (name + ".cpp")
            source.write_text(ADAPTER.replace("@PRODUCTION@", function))
            return compile_fixture(source, output_dir=root, name=name)

        cls.current = build("current", production)
        guard = "if (tile->Binding.ControlSector == (uint32_t)0xffffffffUL ||\n\t\t\t\t\t\t(plane.X == tile->Plane.X && plane.Y == tile->Plane.Y &&\n\t\t\t\t\t\t plane.Z == tile->Plane.Z && plane.W == tile->Plane.W))"
        if guard not in production:
            raise AssertionError("exact bake target source-plane boundary changed")
        # Keep the plane read so warnings-as-errors does not mask the negative.
        cls.alias = build("old-control-only", production.replace(guard, "if ((void(plane), true))"))
        cls.overreach = build("ordinary-plane-overreach", production.replace(
            "tile->Binding.ControlSector == (uint32_t)0xffffffffUL ||", "false ||"))

    def test_current_flat_target_plane(self) -> None:
        result = subprocess.run([str(self.current)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS current-plane")

    def test_equal_control_and_facing_cannot_substitute_another_plane(self) -> None:
        result = subprocess.run([str(self.alias)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
        self.assertEqual(result.stderr.strip(), "cross-source-plane-bake-target")

    def test_ordinary_height_group_keeps_different_plane_neighbors(self) -> None:
        result = subprocess.run([str(self.overreach)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 12, result.stdout + result.stderr)
        self.assertEqual(result.stderr.strip(), "ordinary-neighbor-coverage-changed")


if __name__ == "__main__":
    unittest.main()
