"""HUD model world-normal/projection regression; no renderer is launched."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import run_fixture, compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block

ROOT = Path(__file__).resolve().parents[3]


class ViewmodelModelContractTests(unittest.TestCase):
    def test_actual_skin_method_restores_supported_neighbors_and_preserves_legacy(self):
        source = (ROOT / 'src/rendering/hwrenderer/hw_models.cpp').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory(prefix='viewmodel-model-skin-') as directory:
            target = Path(directory)
            (target / 'model_skin_method.inc').write_text(block(source, 'void FHWModelRenderer::SetMaterial('), encoding='utf-8')
            executable = compile_fixture('tools/pf_oracle/tests/viewmodel_model_skin_fixture.cpp',
                                         output_dir=target, includes=(ROOT, target), root=ROOT)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_camera_inverse_and_inverse_transpose_preserve_model_basis(self):
        run_fixture('tools/pf_oracle/tests/viewmodel_model_matrix_fixture.cpp',
                    includes=('.', 'src/common/utility', 'src/common/thirdparty'), root=ROOT)

    def test_hud_model_keeps_actual_geometry_transform_and_admits_each_skin(self):
        model = (ROOT / 'src/r_data/models.cpp').read_text(encoding='utf-8')
        renderer = (ROOT / 'src/rendering/hwrenderer/hw_models.cpp').read_text(encoding='utf-8')
        self.assertIn('VSMatrix objectToWorldMatrix = renderer->GetViewToWorldMatrix();', model)
        self.assertIn('normalModelMatrix.computeNormalMatrix(objectToWorldMatrix);', renderer)
        skin = renderer.split('void FHWModelRenderer::SetMaterial(', 1)[1].split('void FHWModelRenderer::DrawArrays(', 1)[0]
        self.assertIn('viewmodel && viewmodel->viewmodelMode == HWViewmodel::Enhanced', skin)
        self.assertIn('shader == 0 || shader == 3 || shader == 4', skin)
        self.assertIn('supported ? HWViewmodel::Enhanced : HWViewmodel::Sector', skin)
        self.assertIn('else lightindex = -1;', skin)
        self.assertIn('state.SetUseSpriteCenter(supported);', skin)


if __name__ == '__main__':
    unittest.main()
