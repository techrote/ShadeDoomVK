"""SDVK-008 retained prepass oracle, draw/surface ABI and fail-closed evidence tests.

These are CPU/source contracts; hardware cost remains unqualified.
"""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.renderer_oracle import validate, common
from tools.prepass.sdvk008 import reference as ref, fixtures


def source(path):
    return (ROOT/path).read_text(encoding="utf-8")


def row():
    ctx={"available":True,"semantic_key":"main","producer":"root","map":"SDVROT",
         "type":"main","root_type":"main","epoch":1,"identity":1,"parent_identity":0,
         "depth":0,"angle_space":"hardware-view","mirrored":False,"line_mirror":False,
         "plane_mirror":False,"history_eligible":True,"postprocess_eligible":True,
         "position":[0,0,64],"angles":[0,0,0],"fraction":0.5}
    return {"uniform_scope":"emitted-vulkan-draw-after-apply-surface-uniforms",
            "measurement":"shader-sample-upper-bound-not-actual-fragment-work",
            "material":"SDVRA1","shader":3,"height_texture_index":6,
            "quality":2,"height_reads_max":15,"depth":0.012,"uv_bounds":[1,0,0,1],
            "candidate":True,"eligible_draw":True,"basis_valid":True,
            "surface":{"contract":"sdvk-007-final-quad/v1","orientation_source":"pf-009-calculate-vertices",
                       "uv":[1,0,0,1],"basis_valid":True},"context":ctx}


class SpriteReliefOffGpuTests(unittest.TestCase):
    def test_prepass_reference_still_bounds_hardware_independent_oracle(self):
        self.assertEqual(ref.POLICIES["low"],(8,1))
        self.assertEqual(ref.POLICIES["medium"],(12,2))
        self.assertEqual(ref.POLICIES["high"],(20,2))
        self.assertEqual(ref.MAX_HEIGHT_SAMPLES,23)
        h=fixtures.height_grid("constant_0")
        out=ref.resolve(h,(.5,.5),(.6,0,.8),.012,"high")
        self.assertTrue(out.relief_applied)
        self.assertAlmostEqual(out.uv[0],.491,places=3)
        self.assertLessEqual(out.height_samples,23)
        for kwargs in ({"scale":0},{"height":None},{"view":(.5,0,-.5)},
                       {"policy":"off"},{"scale":1e9}):
            params={"height":h,"uv":(.5,.5),"view":(.6,0,.8),"scale":.012}
            params.update(kwargs)
            self.assertEqual(ref.resolve(**params).uv,(.5,.5))

    def test_sprite_only_ubo_and_reset(self):
        cpu=source("src/common/rendering/hwrenderer/data/hw_surfaceuniforms.h")
        gl=source("wadsrc/static/shaders/binding_struct_definitions.glsl")
        for s in (cpu,gl):
            self.assertLess(s.index("uHeightTextureIndex"),s.index("uSpriteTangent"))
            self.assertLess(s.index("uSpriteNormal"),s.index("uSpriteReliefParams"))
            self.assertLess(s.index("uSpriteReliefParams"),s.index("uSpriteReliefBounds"))
        render=source("src/common/rendering/hwrenderer/data/hw_renderstate.h")
        sprite=source("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        self.assertIn("ClearSpriteRelief();",render)
        self.assertIn("state.ClearSpriteRelief();",sprite)
        self.assertIn("ResolveHWSpriteTangentBasis(quad, ul, ur, vt, vb)",sprite)
        self.assertIn("state.SetSpriteRelief(depth, quality, ul, vt, ur, vb)",sprite)
        self.assertIn("materialShader == 0 || materialShader == 3 || materialShader == 4",sprite)
        self.assertIn("CUSTOM_CVAR(Float, gl_sprite_relief_depth, 0.0f",sprite)
        self.assertIn("CUSTOM_CVAR(Int, gl_sprite_relief_quality, 2,",sprite)

    def test_height_only_custom_shader_and_palette_fallback(self):
        m=source("wadsrc/static/shaders/scene/material.glsl")
        h=source("wadsrc/static/shaders/scene/material_relief.glsl")
        self.assertIn("HasMaterialHeightMap()",m)
        self.assertIn("uHeightTextureIndex < 0",h)
        self.assertIn("uSpriteNormal.w < 0.5",h)
        self.assertIn("PALETTEMODE",h)
        self.assertIn("NO_LAYERS",h)
        self.assertIn("uNpotEmulation.y != 0.0",h)
        self.assertIn("TextureMatrix[0][0] <= 0.0",h)
        self.assertIn("bool reliefApplied = false",m)
        self.assertIn("vec4(reliefTexel.rgb, baseTexel.a)",m)
        self.assertIn("if (reliefTexel.a > uAlphaThreshold)",m)
        self.assertIn("material.Normal = ApplyNormalMap(texCoord.st)",m)
        self.assertIn("material.Metallic = texture(metallictexture, texCoord.st)",m)
        self.assertIn("material.Specular = texture(speculartexture, texCoord.st)",m)

    def test_bounded_shader_math_and_no_geometry_or_depth_write(self):
        s=source("wadsrc/static/shaders/scene/material_relief.glsl")
        for v in ("uSpriteReliefParams.w < 0.5","TextureMatrix","textureSize(uHeightTextureIndex, 0)",
                  "textureLod(uHeightTextureIndex, original, lod)","textureLod(uHeightTextureIndex, uv, lod)",
                  "for (int i = 1; i <= 20; ++i)","for (int j = 0; j < 2; ++j)",
                  "rayLength > 0.0500","view.z <= 0.20","safeLo", "safeHi"):
            self.assertIn(v,s)
        for forbidden in ("gl_FragDepth", "gl_Position", "imageStore", "atomicAdd", "discard", "traceShadow"):
            self.assertNotIn(forbidden,s)
        self.assertIn("uSpriteTangent.w",s)
        self.assertIn("uCameraPos.xyz - pixelpos.xyz",s)

    def test_emitted_draw_validator_positive_and_negative(self):
        good=row()
        validate._sprite_relief(good)
        candidates=[("depth",.021),("depth",-1),("depth",float("nan")),
                    ("quality",4),("height_reads_max",16),("candidate",False),
                    ("eligible_draw",False),("basis_valid",False),("uv_bounds",[0,0,1,1]),
                    ("measurement","measured-gpu-performance"),
                    ("uniform_scope","CPU-generated-only")]
        for field,value in candidates:
            bad=copy.deepcopy(good);bad[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(common.EvidenceError):
                validate._sprite_relief(bad)
        no_height=copy.deepcopy(good)
        no_height.update(height_texture_index=-1,eligible_draw=False,height_reads_max=0)
        validate._sprite_relief(no_height)
        disabled=copy.deepcopy(good)
        disabled.update(candidate=False,eligible_draw=False,depth=0,quality=0,
                        height_reads_max=0,uv_bounds=[0,0,0,0])
        validate._sprite_relief(disabled)


if __name__ == "__main__": unittest.main()
