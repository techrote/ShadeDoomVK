#!/usr/bin/env python3
"""Representative source-contract coverage for PF-004 LevelMesh mutations.

Hosted CI has no IWAD/GPU runtime, so PF-004 pairs the compiled allocator/range
fixture with focused source-route checks.  These checks deliberately inspect
only the mutation paths owned by PF-004; they are not broad defect discovery.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing function body: {signature}")

    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : index]
    raise AssertionError(f"unterminated function body: {signature}")


class LevelMeshMutationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doom = source("src/rendering/hwrenderer/doom_levelmesh.cpp")
        cls.levelmesh_h = source("src/common/rendering/hwrenderer/data/hw_levelmesh.h")
        cls.levelmesh_cpp = source("src/common/rendering/hwrenderer/data/hw_levelmesh.cpp")
        cls.collision = source("src/common/rendering/hwrenderer/data/hw_collision.cpp")
        cls.vulkan = source("src/common/rendering/vulkan/vk_levelmesh.cpp")

    def test_floor_and_ceiling_geometry_schedule_both_sides_and_shadow_membership(self) -> None:
        for signature in (
            "void DoomLevelMesh::OnFloorHeightChanged(sector_t* sector)",
            "void DoomLevelMesh::OnCeilingHeightChanged(sector_t* sector)",
        ):
            body = function_body(self.doom, signature)
            self.assertIn("UpdateFlat(sector->Index(), SurfaceUpdateType::Full);", body)
            self.assertIn("UpdateSide(line->sidedef[0]->Index(), SurfaceUpdateType::Full);", body)
            self.assertIn("UpdateSide(line->sidedef[1]->Index(), SurfaceUpdateType::Full);", body)
            self.assertIn("UpdateLightShadows(sector);", body)

    def test_texture_z_geometry_does_not_drop_second_sidedef(self) -> None:
        body = function_body(
            self.doom, "void DoomLevelMesh::OnSectorChangedTexZ(sector_t* sector)"
        )
        self.assertIn("UpdateFlat(sector->Index(), SurfaceUpdateType::Full);", body)
        self.assertIn("UpdateSide(line->sidedef[0]->Index(), SurfaceUpdateType::Full);", body)
        self.assertIn("UpdateSide(line->sidedef[1]->Index(), SurfaceUpdateType::Full);", body)
        self.assertNotIn("else if (line->sidedef[1])", body)

    def test_polyobject_path_forces_full_side_rebuild_each_frame(self) -> None:
        body = function_body(self.doom, "void DoomLevelMesh::BeginFrame(FLevelLocals& doomMap)")
        self.assertIn("for (side_t* side : PolySides)", body)
        self.assertIn("Sides[sideIndex].PolySegs.Clear();", body)
        self.assertIn("UpdateSide(sideIndex, SurfaceUpdateType::Full);", body)
        self.assertIn("Sides[line->sidedef->Index()].PolySegs.Push(line);", body)
        self.assertIn("Collision->Update();", body)

    def test_light_list_and_shadow_paths_mark_lightmap_dependencies(self) -> None:
        side = function_body(
            self.doom,
            "void DoomLevelMesh::UpdateSideLightList(FLevelLocals& doomMap, unsigned int sideIndex)",
        )
        flat = function_body(
            self.doom,
            "void DoomLevelMesh::UpdateFlatLightList(FLevelLocals& doomMap, unsigned int sectorIndex)",
        )
        side_shadow = function_body(
            self.doom,
            "void DoomLevelMesh::UpdateSideShadows(FLevelLocals& doomMap, unsigned int sideIndex)",
        )
        flat_shadow = function_body(
            self.doom,
            "void DoomLevelMesh::UpdateFlatShadows(FLevelLocals& doomMap, unsigned int sectorIndex)",
        )
        for body in (side, flat):
            self.assertIn("ReceivedNewLight = true", body)
            self.assertIn("LevelMeshMutationDomain::Lights", body)
            self.assertIn("LevelMeshMutationDomain::LightmapProbe", body)
        for body in (side_shadow, flat_shadow):
            self.assertIn("ReceivedNewLight = true", body)
            self.assertIn("LevelMeshMutationDomain::LightmapProbe", body)

    def test_portal_and_resource_reset_domains_are_explicit(self) -> None:
        upload_portals = function_body(self.levelmesh_h, "inline void LevelMesh::UploadPortals()")
        reset = function_body(self.levelmesh_cpp, "void LevelMesh::Reset()")
        self.assertIn("LevelMeshMutationDomain::Portals", upload_portals)
        self.assertIn("LevelMeshMutationDomain::Query", upload_portals)
        self.assertIn("ResourceEpoch.Invalidate();", reset)
        self.assertIn("MutationEpochs.Reset();", reset)

    def test_atlas_repack_uploads_rewritten_vertex_coordinates(self) -> None:
        body = function_body(self.levelmesh_cpp, "void LevelMesh::PackLightmapAtlas()")
        self.assertIn("vertex.lu = uv.X;", body)
        self.assertIn("vertex.lv = uv.Y;", body)
        self.assertIn("vertex.lindex = (float)tile.AtlasLocation.ArrayIndex;", body)
        self.assertIn("UploadRanges.Vertex.Add", body)
        self.assertIn("LevelMeshMutationDomain::LightmapProbe", body)

    def test_cpu_and_vulkan_query_paths_share_exclusive_chunk_mapping(self) -> None:
        cpu = function_body(self.collision, "void CPUAccelStruct::Update()")
        vk = function_body(self.vulkan, "void VkLevelMesh::BeginFrame()")
        for body in (cpu, vk):
            self.assertIn("MeshBufferChunkStart(range, IndexesPerBLAS)", body)
            self.assertIn("MeshBufferChunkEndExclusive(range, IndexesPerBLAS)", body)
        self.assertNotIn("int end = range.End / IndexesPerBLAS;", cpu)
        self.assertIn("DynamicBLAS.size()", vk)


if __name__ == "__main__":
    unittest.main()
