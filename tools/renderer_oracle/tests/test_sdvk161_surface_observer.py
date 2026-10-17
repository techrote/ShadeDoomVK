"""Submitted surface identity bounds and default-off source joins, CPU only."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VULKAN = ROOT / "src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp"


class SubmittedSurfaceObserverTests(unittest.TestCase):
    def test_actual_uv_helper_rejects_stale_region_on_same_page_and_accepts_current_writer(self):
        production = (ROOT / "src/common/rendering/hwrenderer/data/hw_lightmaptile.h").read_text()
        transform = block(production, "FVector2 ToUV(const FVector3& vert, float textureSize) const")
        with tempfile.TemporaryDirectory(prefix="sdvk161-uv-") as directory:
            (Path(directory) / "current_to_uv.inc").write_text(transform)
            binary = compile_fixture(HERE / "sdvk161_current_uv_fixture.cpp", output_dir=directory,
                                     includes=[ROOT, Path(directory)])
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    def test_actual_immediate_scope_restores_nested_parent_and_stays_inert_when_disabled(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        adapter = r'''
#include <stdexcept>
#include "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.h"
namespace { thread_local SdvkDiagnostics::SpecialSurfaceMetadata ImmediateSurface; bool Selected = false; }
namespace SdvkDiagnostics {
bool SpecialSurfaceFrameSelected() { return Selected; }
@CONSTRUCTOR@
@DESTRUCTOR@
}
int main() {
    using namespace SdvkDiagnostics;
    SpecialSurfaceMetadata parent, child;
    parent.Class = "decal"; parent.Side = 3;
    child.Class = "horizon"; child.Side = 2;
    { SpecialSurfaceScope disabled(parent); if (ImmediateSurface.Class) return 1; }
    Selected = true;
    {
        SpecialSurfaceScope first(parent);
        if (ImmediateSurface.Side != 3) return 2;
        { SpecialSurfaceScope second(child); if (ImmediateSurface.Side != 2) return 3; }
        if (ImmediateSurface.Side != 3) return 4;
        { SpecialSurfaceScope cleared({}); if (ImmediateSurface.Class) return 5; }
        if (ImmediateSurface.Side != 3) return 6;
        // Scope cleanup remains valid if the last selected frame closes
        // observation before destruction; metadata must not escape its draw.
        Selected = false;
    }
    return ImmediateSurface.Class ? 7 : 0;
}
'''
        adapter = adapter.replace("@CONSTRUCTOR@", block(source, "SpecialSurfaceScope::SpecialSurfaceScope("))
        adapter = adapter.replace("@DESTRUCTOR@", block(source, "SpecialSurfaceScope::~SpecialSurfaceScope()"))
        with tempfile.TemporaryDirectory(prefix="sdvk161-scope-") as directory:
            path = Path(directory) / "scope.cpp"
            path.write_text(adapter)
            binary = compile_fixture(path, output_dir=directory, includes=[ROOT])
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    def test_real_triangle_owner_helper_rejects_original_multisubsector_and_corrupt_mapping(self):
        with tempfile.TemporaryDirectory(prefix="sdvk161-surface-") as directory:
            binary = compile_fixture(HERE / "sdvk161_surface_mapping_fixture.cpp",
                                     output_dir=directory, includes=[ROOT])
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    def test_surface_reads_actual_range_uniform_and_existing_descriptor_without_allocating(self):
        source = VULKAN.read_text()
        mesh = block(source, "static void LevelMeshSurfaces(")
        for expression in ("ResolveTriangle(data, cursor, start)", "ResolveTriangle(data, end, next)",
                           "data.Materials[start.Uniform]", "data.Uniforms[start.Uniform]",
                           "data.LightUniforms[start.Uniform].uVertexColor.W",
                           "GetSurfaceInfoForObservation(start.Surface)",
                           'Int("batch_first_index", firstIndex)', 'Int("first_index", cursor)',
                           "state->fb->GetLevelMesh()->GetMesh() != mesh"):
            self.assertIn(expression, mesh)
        self.assertIn("CurrentVertexUV(*currentTile, mesh->Lightmap.TextureSize, vertex)", mesh)
        self.assertIn('Bool("current_uv_valid", currentUV)', mesh)
        self.assertIn("vertexZMin = std::min(vertexZMin, vertex.z)", mesh)
        self.assertIn("vertexZMax = std::max(vertexZMax, vertex.z)", mesh)
        self.assertIn('Num("vertex_z_min", vertexZMin).Num("vertex_z_max", vertexZMax)', mesh)
        serializer = block(source, "static std::string Material(")
        self.assertIn("candidate.bindlessIndex == uniforms.uTextureIndex", serializer)
        self.assertIn("GetLayerDiagnostic(i, layer)", serializer)
        for forbidden in ("GetDescriptorEntry(", "GetBindlessTextureIndex(", "GetBindlessHeightLayerIndex(",
                          "GetImage(", "ValidateTexture(", "AllocTile(", "GetLightProbeTextureIndex("):
            self.assertNotIn(forbidden, mesh + serializer)
        ordinary = block(source, "static void Draw(")
        self.assertIn('Emit("material", Material(fb, state->mMaterial, state->mSurfaceUniforms, context)', ordinary)

    def test_extra_work_and_census_are_default_off_and_complete_or_fail(self):
        source = VULKAN.read_text()
        for signature in ("void VulkanDraw(", "void VulkanLevelMeshDraw("):
            wrapper = block(source, signature)
            self.assertIn("if (!StateEnabled()) return;", wrapper)
            self.assertIn("if (SpecialSurfaceEnabled() && !SpecialSurfaceFrameSelected()) return;", wrapper)
        lifecycle = block(source, "std::string LightmapLifecycle(")
        self.assertIn("if (SdvkDiagnostics::SpecialSurfaceEnabled())", lifecycle)
        self.assertIn('result.Raw("tile_receipts", TileCensus(', lifecycle)
        self.assertIn('Int("authored_probe_count", level.lightProbes.Size())', lifecycle)
        census = block(source, "std::string TileCensus(")
        self.assertIn("if (++count > 64) throw", census)
        self.assertNotIn("break;", census)
        self.assertIn("tile.HasValidAtlasRegion", census)
        self.assertIn('Raw("receipt", Receipt(tile.AtlasLocation.Allocation))', census)
        self.assertIn("tile.Binding.ControlSector == 0xffffffff ? -1", census)
        immediate = block(source, "static void ImmediateSpecialSurface(")
        self.assertIn("firstIndex >= source.VertexFirst", immediate)
        self.assertIn('Bool("triangle_mapping_valid", mapping)', immediate)
        self.assertNotIn('Bool("triangle_mapping_valid", true)', immediate)

    def test_immediate_scopes_reach_actual_draw_and_preserve_checked_decal_consumer(self):
        decal = (ROOT / "src/rendering/hwrenderer/scene/hw_decal.cpp").read_text()
        draw = block(decal, "void HWDecal::DrawDecal(")
        self.assertIn("SpecialSurfaceFrameSelected()", draw)
        self.assertIn('value.Class = "decal"', draw)
        self.assertIn("value.Tile = sdvkTile", draw)
        self.assertIn("observedSurface.emplace(value)", draw)
        self.assertEqual(decal.count("GetLightmapTile("), 2)
        # Both producer branches retain the page only from the current,
        # centrally receipt-checked tile actually used to author vertex UVs.
        self.assertEqual(decal.count("gldecal->sdvkPage = int(lightmapindex)"), 2)
        self.assertEqual(decal.count("= verts.first[vertex].lu"), 2)
        self.assertEqual(decal.count("= verts.first[vertex].lv"), 2)
        self.assertIn("sdvkHasUVSnapshot", draw)
        self.assertIn("sdvkActualLightmapUV[2 * i]", draw)
        self.assertIn("value.UvVertices[i] = {dv[i].x, dv[i].y, dv[i].z", draw)
        precise_draw = block(VULKAN.read_text(), "static void ImmediateSpecialSurface(")
        self.assertIn("SdvkSurfaceObservation::CurrentVertexUV(tile,", precise_draw)
        self.assertIn("source.UvVertexCount == 4", precise_draw)
        walls = (ROOT / "src/rendering/hwrenderer/scene/hw_walls.cpp").read_text()
        draw_wall = block(walls, "void HWWall::DrawWall(")
        self.assertLess(draw_wall.index("MakeVertices("), draw_wall.index("value.VertexLightmapPage = int(lindex)"))
        portal = block((ROOT / "src/rendering/hwrenderer/scene/hw_portal.cpp").read_text(),
                       "void HWPortal::DrawPortalStencil(")
        self.assertIn("const auto& line = lines[i / 2]", portal)
        self.assertIn('strcmp(name, "Horizon")', portal)
        self.assertIn("value.Side = line.seg->sidedef->Index()", portal)
        self.assertLess(portal.index("observedSurface.emplace(value)"), portal.index("state.Draw(DT_TriangleFan"))
        contents = block((ROOT / "src/rendering/hwrenderer/scene/hw_portal.cpp").read_text(),
                         "void HWHorizonPortal::DrawContents(")
        self.assertIn('value.Class = "horizon-contents"', contents)
        self.assertIn("value.FirstDrawOnly = true", contents)
        self.assertIn("value.Plane[3] = -sp->plane.D", contents)
        self.assertLess(contents.index("state.SetMaterial(texture"), contents.index("observedSurface.emplace(value)"))
        self.assertLess(contents.index("observedSurface.emplace(value)"), contents.index("state.Draw(DT_TriangleStrip"))


if __name__ == "__main__":
    unittest.main()
