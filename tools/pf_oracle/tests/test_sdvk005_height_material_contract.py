#!/usr/bin/env python3
"""SDVK-005 optional height semantic and compatibility contract."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class Sdvk005HeightMaterialTests(unittest.TestCase):
    def test_compiled_binding_identity_model(self):
        run_fixture("tools/pf_oracle/tests/sdvk005_height_material_fixture.cpp",
                    includes=("src/common/textures",), root=ROOT)

    def test_height_is_appended_without_renumbering_custom_bindings(self):
        semantics = source("src/common/textures/material_layer_semantics.h")
        material = source("src/common/textures/hw_material.cpp")
        parser = source("src/r_data/gldefs.cpp")
        self.assertLess(semantics.index("Custom,"), semantics.index("Height,"))
        self.assertLess(material.index("for (auto& texture : tx->Layers->CustomShaderTextures)"),
                        material.index("MaterialLayerSemantic::Height"))
        for value in ("firstUserTexture = 5;", "firstUserTexture = 7;", "firstUserTexture = 9;"):
            self.assertIn(value, parser)

    def test_authoring_has_height_and_per_semantic_filter_policy(self):
        parser = source("src/r_data/gldefs.cpp")
        game = source("src/common/textures/gametexture.h")
        self.assertIn('"height", nullptr', parser)
        self.assertIn("HeightSampling = MaterialLayerSampling::LinearMipLinear", game)
        self.assertIn('sc.Compare("nearest")', parser)
        self.assertIn('sc.Compare("linear")', parser)
        self.assertIn('sc.Compare("default")', parser)
        self.assertIn("Unknown semantic-layer property", parser)
        self.assertIn("materials/heightmaps/", source("src/common/textures/gametexture.cpp"))

    def test_height_is_shader_available_but_not_default_rendering(self):
        uniform = source("src/common/rendering/hwrenderer/data/hw_surfaceuniforms.h")
        material = source("wadsrc/static/shaders/scene/material.glsl")
        self.assertIn("uHeightTextureIndex", uniform)
        self.assertIn("HasMaterialHeightMap", material)
        self.assertIn("SampleMaterialHeight", material)
        set_props = material.split("void SetMaterialProps", 1)[1]
        self.assertNotIn("SampleMaterialHeight", set_props)
        self.assertNotIn("parallax", material.lower())
        self.assertNotIn("displacement", material.lower())

    def test_palette_routes_do_not_reinterpret_height_as_indexed_colour(self):
        vk = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
        self.assertIn("!state.mPaletteMode && !indexedMaterial", vk)
        self.assertIn("heightLayerIndex", vk)
        self.assertIn("GetLayer(materialHeightLayer", vk)

    def test_native_observer_proves_height_binding_matches_shader_index(self):
        observer = source("src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp")
        validator = source("tools/renderer_oracle/validate.py")
        self.assertIn('Str("semantic", "height")', observer)
        self.assertIn('Int("height_texture_index"', observer)
        self.assertIn("Height semantic binding and shader-visible index disagree", validator)

    def test_scope_excludes_relief_and_tbn(self):
        combined = source("docs/shadedoomvk/issues/SDVK-005.md") + source("src/common/textures/hw_material.cpp")
        self.assertNotIn("ParallaxMapping", combined)
        self.assertNotIn("TangentBasis", combined)


if __name__ == "__main__":
    unittest.main()
