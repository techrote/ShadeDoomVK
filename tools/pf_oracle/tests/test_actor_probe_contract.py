#!/usr/bin/env python3
"""SDVK-010 source/compiled actor probe, PF-012/113 and shader regressions."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class ActorProbeContract(unittest.TestCase):
    def test_compiled_spatial_transition_radius_portal_missing_and_negative_cases(self):
        run_fixture("tools/pf_oracle/tests/actor_probe_selection_fixture.cpp",
                    includes=("src/rendering/hwrenderer/scene",), root=ROOT)

    def test_canonical_source_coordinates_and_movement_not_sector_centroid(self):
        sprite = read("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        draw = sprite.split("void HWSprite::DrawSprite", 1)[1].split("void HWSprite::UpdateRenderSurfaceState", 1)[0]
        self.assertIn("actor->InterpolatedPosition(vp.TicFrac)", draw)
        self.assertIn("probes.Size(), [&](std::size_t i)", draw)
        self.assertIn("HWActorProbeSelection::Resolve(", draw)
        self.assertIn("p.position.X, p.position.Y, p.position.Z, p.index", draw)
        self.assertIn("RenderSurface.sourcePortalGroup != RenderSurface.renderPortalGroup", draw)
        self.assertIn("RenderSurface.throughPortalMode != 0", draw)
        self.assertIn("if (modelframe)", draw)
        self.assertIn("state.SetLightProbeIndex(authoredProbe)", draw)
        self.assertNotIn("SetLightProbeIndex(actor && actor->Sector", draw)
        self.assertIn("SdvkDiagnostics::ClearActorProbeSelection();", draw)
        self.assertIn("SdvkDiagnostics::ActorProbeSelected(selection", draw)

    def test_runtime_no_probe_sentinel_guards_unbounded_negative_and_stale(self):
        # PF-113's hashed descriptor producer is unchanged; guard its caller
        # before any negative/stale ordinal can resize a GPU descriptor cache.
        state = read("src/common/rendering/vulkan/vk_renderstate.cpp")
        body = state.split("void VkRenderState::ApplySurfaceUniforms()", 1)[1].split("if (mMaterial.mChanged)", 1)[0]
        self.assertIn("mLightProbeIndex >= 0", body)
        self.assertIn("static_cast<size_t>(mLightProbeIndex) < level.lightProbes.Size()", body)
        self.assertIn("GetLightProbeTextureIndex(mLightProbeIndex) : 0", body)
        descriptor = read("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
        self.assertIn("SetBindlessTexture(bindIndex + 1", descriptor)
        self.assertIn("Irradiancemaps[probeIndex].View", descriptor)
        self.assertIn("Prefiltermaps[probeIndex].View", descriptor)

    def test_no_pf_probe_rebake_shadow_or_pbr_recalibration(self):
        shader = read("wadsrc/static/shaders/scene/lightmodel_pbr.glsl")
        self.assertIn("if (base == 0u)\n\t\treturn vec3(0.0)", shader)
        self.assertIn("cubeTextures[nonuniformEXT(base + 1u)]", shader)
        self.assertIn("vec3 R = reflect(-V, N);", shader)
        self.assertIn("sunlightAttenuation *= clamp(dot(N, L), 0.0, 1.0)", shader)
        self.assertIn("shadowAttenuation(", shader)
        lighting = read("src/rendering/hwrenderer/scene/hw_spritelight.cpp")
        for symbol in ("TraceSunVisibility(", "PortalGroup", "CurrentWorldQueryEpoch",
                       "HWCheckVisibilityCacheValidity("):
            self.assertIn(symbol, lighting)

    def test_emitted_probe_selection_is_state_only_not_a_second_selector(self):
        source = read("src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp")
        draw = read("src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp")
        self.assertIn("if (!StateEnabled()) return;", source)
        self.assertIn('"sdvk-010-actor-ordinal/v1"', source)
        self.assertIn('"source-level-doom-xyz"', source)
        self.assertIn("CurrentActorProbeSelectionJson()", draw)
        self.assertIn('.Raw("actor_selection", actorProbe.empty()', draw)
        self.assertIn("state->mSurfaceUniforms.uLightProbeIndex", draw)
        self.assertIn("GetBindlessIdentity(runtimeProbe)", draw)


if __name__ == "__main__":
    unittest.main()
