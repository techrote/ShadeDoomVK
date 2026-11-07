from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


class ViewmodelContractTests(unittest.TestCase):
    def test_modes_projection_fallback_and_mirror_basis(self):
        run_fixture('tools/pf_oracle/tests/viewmodel_policy_fixture.cpp',
                    includes=('src/rendering/hwrenderer/scene',), root=ROOT)

    def test_lighting_sample_is_shared_but_geometry_is_unchanged(self):
        scene = ROOT / 'wadsrc/static/shaders/scene'
        layout = (scene / 'layout_shared.glsl').read_text()
        self.assertIn('uViewmodelSample.w > 0.5 ? uViewmodelSample.xyz : pixelpos.xyz', layout)
        for filename in ('lightmodel_normal.glsl', 'lightmodel_specular.glsl', 'lightmodel_pbr.glsl', 'light_spot.glsl', 'light_shadow.glsl'):
            shader = (scene / filename).read_text()
            self.assertIn('SDVK_LIGHTING_POSITION', shader)
            self.assertNotIn('pixelpos.xyz', shader)
        for filename in ('vert_main.glsl', 'material_relief.glsl', 'frag_main.glsl'):
            self.assertNotIn('SDVK_LIGHTING_POSITION', (scene / filename).read_text())

    def test_both_preparation_paths_and_draw_state_isolation(self):
        source = (ROOT / 'src/rendering/hwrenderer/scene/hw_weapon.cpp').read_text()
        self.assertEqual(source.count('PrepareViewmodelLighting(this, hudsprite);'), 2)
        self.assertIn('hudsprite.viewmodelSample.X, hudsprite.viewmodelSample.Z, hudsprite.viewmodelSample.Y, nullptr, lightdata, false', source)
        draw = source.split('void HWDrawInfo::DrawPSprite(', 1)[1].split('void HWDrawInfo::DrawPlayerSprites(', 1)[0]
        for clear in ('ClearSpriteTangentBasis', 'ClearSpriteRelief', 'ClearActorProbeSelection', 'ClearActorSun', 'ClearViewmodelLighting'):
            self.assertIn(clear, draw)
        self.assertIn('CVAR_ARCHIVE', source)
        self.assertIn('viewmodelFallback = HWViewmodel::InvalidBasis;', source)

if __name__ == '__main__':
    unittest.main()
