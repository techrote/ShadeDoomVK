#!/usr/bin/env python3
"""Focused PF-006 source and boundary coverage for Vulkan renderer keys."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class PipelineKeyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shader_h = source("src/common/rendering/vulkan/shaders/vk_shader.h")
        cls.renderpass_h = source("src/common/rendering/vulkan/pipelines/vk_renderpass.h")
        cls.renderpass_cpp = source("src/common/rendering/vulkan/pipelines/vk_renderpass.cpp")
        cls.key_h = source("src/common/rendering/vulkan/vk_keyidentity.h")
        cls.renderstyle_h = source("src/common/engine/renderstyle.h")

    def test_named_keys_no_longer_use_whole_object_memcmp(self) -> None:
        self.assertNotIn("memcmp(this", self.shader_h)
        self.assertNotIn("memcmp(this", self.renderpass_h)
        self.assertIn("VkKeyIdentity::ShaderState CanonicalState() const", self.shader_h)
        self.assertIn("VkKeyIdentity::PipelineState CanonicalState() const", self.renderpass_h)
        self.assertIn("VkKeyIdentity::RenderPassState CanonicalState() const", self.renderpass_h)

    def test_obsolete_padding_and_size_contracts_are_removed(self) -> None:
        self.assertNotIn("Padding1", self.renderpass_h)
        self.assertNotIn("Padding2", self.renderpass_h)
        self.assertNotIn("Padding3", self.renderpass_h)
        self.assertNotIn("sizeof(VkShaderKey)", self.shader_h)
        self.assertNotIn("sizeof(VkPipelineKey)", self.renderpass_h)

    def test_shader_specialization_word_remains_abi_but_not_cache_identity(self) -> None:
        self.assertIn("uint64_t AsQWORD = 0;", self.shader_h)
        self.assertIn("builder.AddConstant(0, (uint32_t)key.ShaderKey.AsQWORD);", self.renderpass_cpp)
        self.assertIn("builder.AddConstant(1, (uint32_t)(key.ShaderKey.AsQWORD >> 32));", self.renderpass_cpp)
        self.assertIn("return CanonicalState().GeneralizedCacheKey();", self.shader_h)

    def test_canonical_shader_state_names_every_meaningful_field(self) -> None:
        fields = [
            "Simple2D", "TextureMode", "ClampY", "Brightmap", "Detailmap", "Glowmap",
            "UseShadowmap", "UseRaytrace", "ShadowmapFilter", "FogBeforeLights",
            "FogAfterLights", "FogRadial", "SWLightRadial", "SWLightBanded",
            "LightMode", "LightBlendMode", "LightAttenuationMode", "PaletteMode",
            "FogBalls", "NoFragmentShader", "DepthFadeThreshold", "AlphaTestOnly",
            "LightNoNormals", "UseSpriteCenter", "SpecialEffect", "EffectState",
            "VertexFormat", "AlphaTest", "Simple", "Simple3D", "GBufferPass",
            "UseLevelMesh", "ShadeVertex", "UseRaytracePrecise",
        ]
        for field in fields:
            self.assertIn(field, self.key_h)
            self.assertIn(f"state.{field}", self.shader_h)

    def test_pipeline_and_renderpass_state_are_explicit(self) -> None:
        for field in [
            "DrawType", "CullMode", "ColorMask", "DepthWrite", "DepthTest",
            "DepthClamp", "DepthBias", "DepthFunc", "StencilTest", "StencilPassOp",
            "DrawLine", "IsGeneralized", "RenderStyle",
        ]:
            self.assertIn(f"state.{field}", self.renderpass_h)
        for field in ["DepthStencil", "Samples", "DrawBuffers", "DrawBufferFormat"]:
            self.assertIn(f"state.{field}", self.renderpass_h)

    def test_render_style_identity_is_named_not_union_representation(self) -> None:
        # Repository-local FRenderStyle defines exactly four named byte fields
        # over AsDWORD. Pipeline identity must name those fields rather than
        # promoting the union representation into the cache contract.
        for declaration in [
            "uint8_t BlendOp;", "uint8_t SrcAlpha;", "uint8_t DestAlpha;", "uint8_t Flags;",
        ]:
            self.assertIn(declaration, self.renderstyle_h)
        self.assertIn("uint32_t AsDWORD;", self.renderstyle_h)
        self.assertIn("struct RenderStyleState", self.key_h)
        for field in ["BlendOp", "SrcAlpha", "DestAlpha", "Flags"]:
            self.assertIn(f"state.RenderStyle.{field} = RenderStyle.{field};", self.renderpass_h)
        self.assertNotIn("state.RenderStyle = RenderStyle.AsDWORD", self.renderpass_h)

    def test_pipeline_library_worker_and_driver_cache_routes_are_preserved(self) -> None:
        for token in [
            "PipelineCache = builder.Create(fb->GetDevice())",
            "builder.InitialData(data.data(), data.size())",
            "PipelineCache->GetCacheData()",
            "RunOnWorkerThread",
            "PrecompileFragmentShaderLibrary",
            "GetVertexShaderLibrary",
            "GetFragmentShaderLibrary",
            "GetFragmentOutputLibrary",
            "GeneralizedPipelines",
            "SpecializedPipelines",
        ]:
            self.assertIn(token, self.renderpass_cpp + self.renderpass_h)

    def test_compiled_old_new_partition_and_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "pipeline-key-contract-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering",
                    "tools/pf_oracle/tests/pipeline_key_contract_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
