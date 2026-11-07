"""Execute production material reset -> live dirty ranges -> uploader on the CPU.

Descriptor image/sampler lookup and transfer execution are symbolic services;
reset, retirement, allocation/range merging, refresh and staging writers are
extracted unchanged from production. No renderer or Vulkan device is launched.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DATA = ROOT / 'src/common/rendering/hwrenderer/data'
VK = ROOT / 'src/common/rendering/vulkan'
RETAINED = HERE / 'fixtures/sdvk161-material-reset-pre-fix.json'
RETAINED_SHA256 = 'c4c922cf5bbcd2146fee68c1d6b90415ed7c6c9816af823eb59b8d5c4023c7a7'


def fragments():
    selections = {
        'reset': (VK / 'descriptorsets/vk_descriptorset.cpp', 'void VkDescriptorSetManager::ResetHWTextureSets()'),
        'filter': (VK / 'vk_renderdevice.cpp', 'void VulkanRenderDevice::SetTextureFilterMode()'),
        'precache': (VK / 'vk_renderdevice.cpp', 'void VulkanRenderDevice::StartPrecaching()'),
        'device': (VK / 'vk_renderdevice.cpp', 'void VulkanRenderDevice::InvalidateMaterialBindings()'),
        'dirty': (DATA / 'hw_levelmesh.cpp', 'void LevelMesh::InvalidateMaterialBindings()'),
        'clear': (DATA / 'hw_levelmesh.cpp', 'void MeshBufferUploads::Clear()'),
        'merge': (DATA / 'hw_levelmesh.cpp', 'void MeshBufferUploads::Add('),
        'alloc_uniforms': (DATA / 'hw_levelmesh.h', 'inline UniformsAllocInfo LevelMesh::AllocUniforms('),
        'alloc_surface': (DATA / 'hw_levelmesh.h', 'inline SurfaceAllocInfo LevelMesh::AllocSurface('),
        'free_uniforms': (DATA / 'hw_levelmesh.h', 'inline void LevelMesh::FreeUniforms('),
        'free_surface': (DATA / 'hw_levelmesh.h', 'inline void LevelMesh::FreeSurface('),
        'retire': (VK / 'textures/vk_hwtexture.cpp', 'void VkMaterial::DeleteDescriptors()'),
    }
    for name in ('UploadSurfaces', 'UploadUniforms', 'ClearRanges', 'GetTransferSize',
                 'GetUploadPtr', 'UploadData', 'EndTransfer'):
        selections[name] = (VK / 'vk_levelmesh.cpp', {
            'GetTransferSize': 'size_t ', 'GetUploadPtr': 'void* '
        }.get(name, 'void ') + 'VkLevelMeshUploader::' + name + '(')
    return {key: block(path.read_text()[path.read_text().index(signature):], signature)
            for key, (path, signature) in selections.items()}


def retained_reset():
    raw = RETAINED.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RETAINED_SHA256:
        raise AssertionError('SDVK-161 historical material reset receipt changed')
    receipt = json.loads(raw)
    if hashlib.sha256(receipt['content'].encode()).hexdigest() != receipt['sha256']:
        raise AssertionError('SDVK-161 historical material reset fragment changed')
    return receipt['content']


def build(directory, *, original=False, mutate=None):
    directory.mkdir(parents=True, exist_ok=True)
    source = fragments()
    if original:
        source['reset'] = retained_reset()
    if mutate:
        mutate(source)
    (directory / 'material_reset_production.inc').write_text('\n\n'.join(source.values()))
    declarations = [
        block((DATA / 'hw_levelmesh.h').read_text(), 'class MeshBufferUploads') + ';',
        block((DATA / 'hw_levelmesh.h').read_text(), 'struct UniformsAllocInfo') + ';',
        block((DATA / 'hw_levelmesh.h').read_text(), 'struct SurfaceAllocInfo') + ';',
        block((DATA / 'hw_surfaceuniforms.h').read_text(), 'struct SurfaceUniforms') + ';',
        block((VK / 'vk_levelmesh.h').read_text(), 'struct SurfaceInfo') + ';',
    ]
    (directory / 'material_reset_declarations.inc').write_text('\n\n'.join(declarations))
    return compile_fixture(HERE / 'sdvk161_material_reset_fixture.cpp', output_dir=directory,
        includes=[directory, DATA, VK / 'descriptorsets', ROOT / 'src/common/rendering',
                  ROOT / 'src/common/utility', ROOT / 'src/common/thirdparty'])


class MaterialResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sdvk161-material-reset-')
        cls.directory = Path(cls.temp.name)
        cls.current = build(cls.directory / 'current')
        cls.original = build(cls.directory / 'pre-fix', original=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, executable, case, reason='PASS', code=0):
        result = subprocess.run([str(executable), case], text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn(reason, result.stdout + result.stderr)

    def test_current_production_reset_refreshes_both_consumers(self):
        for case in ('no-reset', 'filter', 'precache', 'holes', 'repeat', 'owner', 'no-owner'):
            with self.subTest(case=case):
                self.run_case(self.current, case)

    def test_retained_actual_pre_fix_reset_keeps_stale_indices(self):
        self.run_case(self.original, 'no-reset')
        for case in ('filter', 'precache'):
            with self.subTest(case=case):
                self.run_case(self.original, case, 'raster-material-index-stale', 11)

    def test_independent_refresh_and_lifetime_mutants_fail(self):
        mutations = {
            'missing-raster': ('dirty', 'markLive(FreeLists.Uniforms, UploadRanges.Uniforms);', '',
                               'filter', 'raster-material-index-stale'),
            'missing-tracer': ('dirty', 'markLive(FreeLists.Surface, UploadRanges.Surface);', '',
                               'filter', 'tracer-material-index-stale'),
            'missing-height': ('UploadUniforms',
                'surfaceUniforms.uHeightTextureIndex = Mesh->fb->GetBindlessHeightLayerIndex(material.mMaterial, material.mClampMode, material.mTranslation, false);',
                'surfaceUniforms.uHeightTextureIndex = -1;', 'filter', 'height-semantic-not-refreshed'),
            'capacity-holes': ('dirty',
                'markLive(FreeLists.Uniforms, UploadRanges.Uniforms);',
                'markLive(FreeLists.Uniforms, UploadRanges.Uniforms);\nUploadRanges.Uniforms.Add(0, Mesh.Uniforms.Size());',
                'holes', 'retired-uniform-hole-uploaded'),
            'lagged-owner': ('device', 'levelMesh->InvalidateMaterialBindings();',
                'mirrorMesh->InvalidateMaterialBindings();', 'owner', 'wrong-mesh-owner-dirtied'),
        }
        for name, (key, old, new, case, reason) in mutations.items():
            def mutate(source, key=key, old=old, new=new):
                self.assertEqual(source[key].count(old), 1)
                source[key] = source[key].replace(old, new)
            with self.subTest(mutation=name):
                exe = build(self.directory / name, mutate=mutate)
                self.run_case(exe, case, reason, 11)

    def test_production_consumption_precedes_draw_and_does_not_rebuild_owners(self):
        device = (VK / 'vk_renderdevice.cpp').read_text()
        begin = block(device, 'void VulkanRenderDevice::BeginFrame()')
        self.assertLess(begin.index('mLevelMesh->SetLevelMesh(levelMesh);'), begin.index('mLevelMesh->BeginFrame();'))
        self.assertLess(begin.index('mLevelMesh->BeginFrame();'), begin.index('mRenderState->BeginFrame();'))
        self.assertLess(begin.index('mLevelMesh->BeginFrame();'), begin.index('mLightmapper->BeginFrame();'))
        main = (ROOT / 'src/d_main.cpp').read_text()
        self.assertIn('screen->BeginFrame();\n\n\t\t\tviewsec = RenderView(', main)
        mesh_source = (VK / 'vk_levelmesh.cpp').read_text()
        self.assertIn('UploadMeshes();', block(mesh_source, 'void VkLevelMesh::BeginFrame()'))
        self.assertIn('uploader.Upload();', block(mesh_source, 'void VkLevelMesh::UploadMeshes()'))
        renderstate = (VK / 'vk_renderstate.cpp').read_text()
        self.assertIn('mMaterial.Reset();', block(renderstate, 'void VkRenderState::BeginFrame()'))
        upload = block(mesh_source, 'void VkLevelMeshUploader::Upload()')
        self.assertLess(upload.index('UploadSurfaces();'), upload.index('UploadUniforms();'))
        self.assertLess(upload.index('UploadUniforms();'), upload.index('ClearRanges();', upload.index('UploadUniforms();')))
        for key in ('device', 'dirty'):
            source = fragments()[key]
            for forbidden in ('SetLevelMesh(', 'CreateLightmap(', 'ResetLightProbes(', 'AllocTile(', 'ResetAccelStruct('):
                self.assertNotIn(forbidden, source)
        reset = fragments()['reset']
        self.assertNotIn('LightProbes.clear();', reset)
        self.assertNotIn('for (int index : LightProbes)', reset)


if __name__ == '__main__':
    unittest.main()
