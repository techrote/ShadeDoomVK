#!/usr/bin/env python3
"""PF-013 texture/material correctness source and boundary contract coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class MaterialCorrectnessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.texture_cpp = source("src/common/textures/texture.cpp")
        cls.material_state_h = source("src/common/rendering/hwrenderer/data/hw_materialstate.h")
        cls.material_cpp = source("src/common/textures/hw_material.cpp")
        cls.vk_texture_h = source("src/common/rendering/vulkan/textures/vk_hwtexture.h")
        cls.vk_texture_cpp = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
        cls.precache_cpp = source("src/rendering/hwrenderer/hw_precache.cpp")
        cls.sprite_cpp = source("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        cls.draw2d_cpp = source("src/common/rendering/hwrenderer/hw_draw2d.cpp")
        cls.gettexel_glsl = source("wadsrc/static/shaders/scene/material_gettexel.glsl")
        cls.frag_main_glsl = source("wadsrc/static/shaders/scene/frag_main.glsl")
        cls.lightmode_glsl = source("wadsrc/static/shaders/scene/lightmode.glsl")
        cls.pbr_glsl = source("wadsrc/static/shaders/scene/lightmodel_pbr.glsl")

    def test_red_is_alpha_producer_semantics_are_luminance_not_palette_index(self) -> None:
        self.assertIn("flags & (CTF_Indexed | CTF_IndexedRedIsAlpha)", self.texture_cpp)
        self.assertIn("bool alpha = !!(flags & CTF_IndexedRedIsAlpha)", self.texture_cpp)
        self.assertIn("Get8BitPixels(alpha)", self.texture_cpp)

    def test_material_state_carries_interpretation_at_the_existing_binding_boundary(self) -> None:
        self.assertIn("bool mRedIsAlpha = false", self.material_state_h)
        self.assertGreaterEqual(self.material_state_h.count("mRedIsAlpha = false"), 2)
        self.assertIn(
            "mMaterial.mRedIsAlpha = mPaletteMode && mTextureMode == TM_ALPHATEXTURE",
            self.material_cpp,
        )

        sprite_mode = self.sprite_cpp.index("state.SetTextureMode(RenderStyle)")
        sprite_material = self.sprite_cpp.index("state.SetMaterial(texture", sprite_mode)
        self.assertLess(sprite_mode, sprite_material)

        draw_mode = self.draw2d_cpp.index("state.SetTextureMode(cmd.mDrawMode)")
        draw_material = self.draw2d_cpp.index("state.SetMaterial(cmd.mTexture", draw_mode)
        self.assertLess(draw_mode, draw_material)

    def test_vulkan_r8_storage_and_descriptor_identity_do_not_alias_palette_indices(self) -> None:
        self.assertIn("mImage, mPaletteImage, mAlphaImage", self.vk_texture_h)
        self.assertIn("mAlphaImage.Reset(fb)", self.vk_texture_cpp)
        self.assertLess(
            self.vk_texture_cpp.index("if (flags & CTF_IndexedRedIsAlpha)"),
            self.vk_texture_cpp.index("else if (flags & CTF_Indexed)"),
        )
        self.assertIn(
            "bool indexed = (flags & (CTF_Indexed | CTF_IndexedRedIsAlpha)) != 0",
            self.vk_texture_cpp,
        )
        self.assertEqual(
            self.vk_texture_cpp.count(
                "bool indexed = (flags & (CTF_Indexed | CTF_IndexedRedIsAlpha)) != 0"
            ),
            2,
        )
        self.assertIn(
            "indexedRedIsAlpha ? CTF_IndexedRedIsAlpha : CTF_Indexed",
            self.vk_texture_cpp,
        )
        self.assertIn("set.redIsAlpha == indexedRedIsAlpha", self.vk_texture_cpp)
        self.assertIn("bool redIsAlpha", self.vk_texture_h)

    def test_red_is_alpha_shader_path_preserves_continuous_alpha(self) -> None:
        self.assertIn("float gray = PALETTEMODE ? texel.r : grayscale(texel)", self.gettexel_glsl)
        self.assertIn("if (PALETTEMODE && !TM_ALPHATEXTURE)", self.frag_main_glsl)
        self.assertIn("if (PALETTEMODE && !TM_ALPHATEXTURE)", self.lightmode_glsl)
        self.assertNotIn("if (PALETTEMODE)\n\t{\n\t\tmaterial.Base.a", self.frag_main_glsl)

    def test_sprite_precache_uses_the_computed_variant_flags(self) -> None:
        self.assertIn("int scaleflags = CTF_Expand", self.precache_cpp)
        self.assertIn("if (shouldUpscale(tex, UF_Sprite)) scaleflags |= CTF_Upscale", self.precache_cpp)
        self.assertGreaterEqual(
            self.precache_cpp.count("FMaterial::ValidateTexture(tex, scaleflags"),
            4,
        )
        self.assertNotIn("FMaterial::ValidateTexture(tex, true, true)", self.precache_cpp)

    def test_descriptor_cleanup_and_pf_generation_guards_remain_intact(self) -> None:
        delete_begin = self.vk_texture_cpp.index("void VkMaterial::DeleteDescriptors()")
        delete_end = self.vk_texture_cpp.index("int VkMaterial::GetBindlessIndex", delete_begin)
        delete_body = self.vk_texture_cpp[delete_begin:delete_end]
        self.assertIn("FreeBindlessSlot(set.bindlessIndex)", delete_body)
        self.assertIn("mDescriptorSets.clear()", delete_body)

        self.assertIn("mUploadEpoch.Invalidate()", self.vk_texture_cpp)
        self.assertIn("mUploadEpoch.Validate(uploadTicket.TargetEpoch)", self.vk_texture_cpp)
        self.assertIn("CheckUploadTicket(uploadTicket)", self.vk_texture_cpp)

    def test_ggx_zero_boundary_is_finite_without_recalibrating_normal_roughness(self) -> None:
        distribution_begin = self.pbr_glsl.index("float DistributionGGX")
        distribution_end = self.pbr_glsl.index("float GeometrySchlickGGX", distribution_begin)
        distribution = self.pbr_glsl[distribution_begin:distribution_end]
        self.assertIn("if (a2 <= 0.0)", distribution)
        self.assertIn("return 0.0", distribution)
        self.assertIn("(1.0 - NdotH2) + NdotH2 * a2", distribution)
        self.assertIn("return (a2 / denomBase) / (PI * denomBase)", distribution)

        # PF-011 calibration constants and all other PBR compatibility scales
        # remain consumers, not PF-013 tuning knobs.
        for token in [
            "LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE",
            "LIGHT_COMPAT_PBR_AMBIENT_SCALE",
            "LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE",
        ]:
            self.assertIn(token, self.pbr_glsl)

    def test_compiled_adversarial_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "material-correctness-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/material_correctness_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
