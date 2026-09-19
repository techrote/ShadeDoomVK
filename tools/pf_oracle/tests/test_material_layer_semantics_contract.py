#!/usr/bin/env python3
"""PF-008 material semantic identity, binding-equivalence, and boundary coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class MaterialLayerSemanticsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.semantic_h = source("src/common/textures/material_layer_semantics.h")
        cls.material_h = source("src/common/textures/hw_material.h")
        cls.material_cpp = source("src/common/textures/hw_material.cpp")
        cls.game_texture_h = source("src/common/textures/gametexture.h")
        cls.vk_material_cpp = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")

    def test_existing_channels_have_explicit_semantic_names(self) -> None:
        for token in [
            "MaterialLayerSemantic::Albedo",
            "MaterialLayerSemantic::Normal",
            "MaterialLayerSemantic::LegacySpecular",
            "MaterialLayerSemantic::Metallic",
            "MaterialLayerSemantic::Roughness",
            "MaterialLayerSemantic::AmbientOcclusion",
            "MaterialLayerSemantic::Brightmap",
            "MaterialLayerSemantic::Detail",
            "MaterialLayerSemantic::Glow",
            "MaterialLayerSemantic::Custom",
        ]:
            self.assertIn(token, self.material_cpp)
        self.assertNotIn("Height", self.semantic_h)
        self.assertNotIn("Parallax", self.semantic_h)
        self.assertNotIn("POM", self.semantic_h)

    def test_material_layer_metadata_is_diagnostic_not_second_order_truth(self) -> None:
        self.assertIn("MaterialLayerSemantic semantic", self.material_h)
        self.assertIn("int customIndex", self.material_h)
        self.assertIn("int binding = -1", self.material_h)
        self.assertIn("FTexture* sourceTexture", self.material_h)
        self.assertIn("MaterialLayerSampling sampling", self.material_h)
        self.assertIn("int FindLayer(MaterialLayerSemantic semantic", self.material_h)
        self.assertIn("key.Matches(layer.semantic, layer.customIndex)", self.material_h)
        self.assertIn("bool GetLayerDiagnostic(int binding", self.material_h)
        self.assertIn("result.binding = binding", self.material_h)
        self.assertIn("result.sourceTexture = layer.layerTexture", self.material_h)
        self.assertIn("result.sampling = layer.layerFiltering", self.material_h)

    def test_legacy_specular_and_pbr_binding_order_is_preserved(self) -> None:
        specular_branch = self.material_cpp.index("tx->Layers->Normal.get() && tx->Layers->Specular.get()")
        specular_normal = self.material_cpp.index("MaterialLayerSemantic::Normal", specular_branch)
        legacy_specular = self.material_cpp.index("MaterialLayerSemantic::LegacySpecular", specular_normal)
        specular_shader = self.material_cpp.index("mShaderIndex = SHADER_Specular", legacy_specular)
        self.assertLess(specular_normal, legacy_specular)
        self.assertLess(legacy_specular, specular_shader)

        pbr_branch = self.material_cpp.index("tx->Layers->Metallic.get() && tx->Layers->Roughness.get()")
        pbr_normal = self.material_cpp.index("MaterialLayerSemantic::Normal", pbr_branch)
        metallic = self.material_cpp.index("MaterialLayerSemantic::Metallic", pbr_normal)
        roughness = self.material_cpp.index("MaterialLayerSemantic::Roughness", metallic)
        ao = self.material_cpp.index("MaterialLayerSemantic::AmbientOcclusion", roughness)
        pbr_shader = self.material_cpp.index("mShaderIndex = SHADER_PBR", ao)
        self.assertLess(pbr_normal, metallic)
        self.assertLess(metallic, roughness)
        self.assertLess(roughness, ao)
        self.assertLess(ao, pbr_shader)

    def test_optional_fixed_bindings_keep_placeholders_and_historical_order(self) -> None:
        bright = "placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Brightmap"
        detail = "placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Detail"
        glow = "placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Glow"
        self.assertIn(bright, self.material_cpp)
        self.assertIn(detail, self.material_cpp)
        self.assertIn(glow, self.material_cpp)
        self.assertLess(self.material_cpp.index(bright), self.material_cpp.index(detail))
        self.assertLess(self.material_cpp.index(detail), self.material_cpp.index(glow))
        self.assertLess(
            self.material_cpp.index("mNumNonMaterialLayers = mTextureLayers.Size()"),
            self.material_cpp.index("for (auto& texture : tx->Layers->CustomShaderTextures)"),
        )

    def test_custom_layers_keep_authoring_slot_and_sampling(self) -> None:
        tagged_custom = "MaterialLayerSemantic::Custom, static_cast<int>(i)"
        self.assertEqual(self.material_cpp.count(tagged_custom), 2)
        self.assertIn("tx->Layers->CustomShaderTextureSampling[i]", self.material_cpp)
        self.assertIn("globalshader->CustomShaderTextureSampling[i]", self.material_cpp)
        self.assertIn("MaterialLayerSampling CustomShaderTextureSampling[MAX_CUSTOM_HW_SHADER_TEXTURES]", self.game_texture_h)
        self.assertIn("MAX_CUSTOM_HW_SHADER_TEXTURES 15", self.game_texture_h)

    def test_vulkan_descriptor_path_remains_order_and_sampler_equivalent(self) -> None:
        # PF-008 only tags the inherited layer sequence. Vulkan descriptor
        # allocation still consumes that exact sequence and its existing
        # per-layer sampler override; semantic metadata does not sort/repack it.
        self.assertIn("textureCount = numLayersMat", self.vk_material_cpp)
        self.assertIn("for (int i = 1; i < numLayersMat; i++)", self.vk_material_cpp)
        self.assertIn("GetLayer(i, 0, &layer)", self.vk_material_cpp)
        self.assertIn("GetLayerFilter(i), clampmode", self.vk_material_cpp)
        self.assertNotIn("GetLayerSemantic(", self.vk_material_cpp)
        self.assertNotIn("FindLayer(", self.vk_material_cpp)

    def test_compiled_semantic_key_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "material-layer-semantics-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/textures",
                    "tools/pf_oracle/tests/material_layer_semantics_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
