#!/usr/bin/env python3
"""SDVK-007 explicit sprite final-quad tangent correctness and ownership."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class SpriteTangentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sprite = read("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        cls.header = read("src/rendering/hwrenderer/scene/hw_sprite_tangent.h")
        cls.shader = read("wadsrc/static/shaders/scene/material_normalmap.glsl")
        cls.state = read("src/common/rendering/hwrenderer/data/hw_renderstate.h")
        cls.cpp_uniform = read("src/common/rendering/hwrenderer/data/hw_surfaceuniforms.h")
        cls.glsl_uniform = read("wadsrc/static/shaders/binding_struct_definitions.glsl")
        cls.macros = read("wadsrc/static/shaders/scene/layout_shared.glsl")
        cls.material = read("wadsrc/static/shaders/scene/material.glsl")
        cls.draw = read("src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp")

    def test_native_directional_rotations_flip_and_fallback_fixture(self):
        run_fixture("tools/pf_oracle/tests/sprite_tangent_basis_fixture.cpp",
                    includes=("src/rendering/hwrenderer/scene",), root=ROOT)

    def test_pf009_final_quad_and_unmodified_uv_identity_authority(self):
        section = self.sprite.split("void HWSprite::CreateVertices(", 1)[1].split(
            "void HWSprite::SplitSprite(", 1)[0]
        self.assertIn("polyoffset = CalculateVertices(di, v, &di->Viewpoint.Pos)", section)
        self.assertIn("ResolveHWSpriteTangentBasis(quad, ul, ur, vt, vb)", section)
        self.assertIn("state.SetSpriteTangentBasis(", section)
        self.assertIn("SdvkDiagnostics::SpriteBasisSelected(RenderSurface, basis)", section)
        # No new UV identity, positional edits or actor/gameplay orientation writes.
        self.assertEqual(len(re.findall(r"vp\[[0-3]\]\.Set\(", section)), 4)
        self.assertNotIn("thing->", section)
        self.assertNotIn("portalState", section)
        self.assertIn("RenderSurface.frameMirrored = mirror", self.sprite)
        self.assertIn("RenderSurface.uvMirrorX = mirror ^ !!(thing->renderflags & RF_XFLIP)", self.sprite)
        self.assertIn("RenderSurface.uvMirrorY = !!(thing->renderflags & RF_YFLIP)", self.sprite)
        self.assertIn("RenderSurface.portalMirrored = di->drawctx->portalState.isMirrored()", self.sprite)

    def test_explicit_world_tbn_is_only_selected_for_sprite_normalmaps(self):
        self.assertIn("if (uSpriteNormal.w > 0.5)", self.shader)
        self.assertIn("cross(normal, tangent) * uSpriteTangent.w", self.shader)
        self.assertIn("tbn = mat3(tangent, bitangent, normal)", self.shader)
        self.assertIn("cotangent_frame(interpolatedNormal, pixelpos.xyz, vTexCoord.st)", self.shader)
        self.assertIn("map.y = -map.y", self.shader)
        self.assertIn("vec3 ApplyNormalMap(vec2 texcoord)", self.shader)
        self.assertIn("return normalize(vWorldNormal.xyz)", self.shader)
        self.assertIn("material.Normal = ApplyNormalMap(texCoord.st)", self.material)
        self.assertIn("SampleMaterialHeight", self.material)
        self.assertNotIn("SampleMaterialHeight(texCoord.st)", self.material)

    def test_append_only_height_and_uniform_binding_identity(self):
        for src in (self.cpp_uniform, self.glsl_uniform):
            self.assertLess(src.index("uHeightTextureIndex"), src.index("uMaterialSemanticPad2"))
            self.assertLess(src.index("uMaterialSemanticPad2"), src.index("uSpriteTangent"))
            self.assertLess(src.index("uSpriteTangent"), src.index("uSpriteNormal"))
        for name in ("uSpriteTangent", "uSpriteNormal"):
            self.assertIn(f"#define {name} data[uDataIndex].{name}", self.macros)
        self.assertIn("ClearSpriteTangentBasis();", self.state)
        self.assertIn("mSurfaceUniforms.uSpriteTangent =", self.state)
        self.assertIn("mSurfaceUniforms.uSpriteNormal =", self.state)
        self.assertIn("mSurfaceUniforms.uHeightTextureIndex = -1", self.state)

    def test_draw_scope_and_nonsprite_fallback(self):
        start = self.sprite.index("void HWSprite::DrawSprite")
        end = self.sprite.index("void HWSprite::UpdateRenderSurfaceState", start)
        body = self.sprite[start:end]
        self.assertIn("state.ClearSpriteTangentBasis();", body)
        self.assertIn("SdvkDiagnostics::ClearSpriteBasis();", body)
        self.assertIn("state.SetNormal(0, 0, 0);", body)
        self.assertIn("state.Draw(DT_TriangleStrip, vertexindex, 4);", body)
        self.assertIn("state.SetLightNoNormals(false);", body)
        self.assertIn("RenderModel(&renderer", body)
        # Nothing in the model or world source is modified by this contract.
        self.assertNotIn("tangent", read("src/rendering/hwrenderer/scene/hw_sprite_surface.h").lower())
        self.assertIn('"sprite-basis"', self.draw)
        self.assertIn("state->mSurfaceUniforms.uSpriteTangent", self.draw)
        self.assertIn("state->mSurfaceUniforms.uSpriteNormal", self.draw)

    def test_nonfinite_nondegenerate_mirror_and_handedness_guard(self):
        for clause in ("std::isfinite", "degenerate texture coordinate span",
                       "degenerate sprite right edge", "nonplanar sprite quad",
                       "result.handedness = -result.uSign * result.vSign",
                       "result.reason = result.valid ?"):
            self.assertIn(clause, self.header)


if __name__ == "__main__":
    unittest.main()
