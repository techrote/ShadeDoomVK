"""Stable raw probe bases across material resets; exact-source CPU qualification.

Not native Vulkan/fence/image evidence. Original producer fragments are immutable
and must reject the documented clean invariants for independent named reasons.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block, current as builder_source
from tools.pf_oracle.tests.sdvk153_source import ROOT, fragments, retained
from tools.pf_oracle.tests import pf113_source_extract

HERE=Path(__file__).resolve().parent
DATA=ROOT/'src/common/rendering/hwrenderer/data'
DESCRIPTORS=ROOT/'src/common/rendering/vulkan/descriptorsets'
CASES=('no-reset','filter','anisotropy','precache','reverse-lookup','material-pressure',
       'fixed-samplers','material-retirement','admission','bounded-ordinal','stress','exhaustion')
NEGATIVES={
    'filter':'retained-probemap-texel-rebound-to-other-owner',
    'precache':'retained-probemap-texel-rebound-to-other-owner',
    'reverse-lookup':'probe-pair-token-retired',
    'material-pressure':'retained-probe-mapped-to-material',
    'fixed-samplers':'fixed-descriptor-retired-hw-sampler',
    'bounded-ordinal':'out-of-range-grew-persistent-cache',
}


def build(directory: Path, original: bool=False, mutate=None) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    source=fragments(original)
    if mutate is not None:
        mutate(source)
    (directory/'sdvk153_producers.cpp').write_text('\n\n'.join(source.values()))
    (directory/'sdvk153_builder.cpp').write_text('\n\n'.join(builder_source(key) for key in ('probe_step','probe_full')))
    return compile_fixture(HERE/'sdvk153_descriptor_lifetime_fixture.cpp',output_dir=directory,
        includes=[directory,DATA,DESCRIPTORS,ROOT/'src/common/rendering',
                  ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


class DescriptorLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk153-lifetime-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, executable, case, code=0, reason='PASS'):
        result=subprocess.run([str(executable),case],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr)
        self.assertIn(reason,result.stdout+result.stderr)
        return result

    def test_current_production_owners_and_bounded_stress(self):
        for case in CASES:
            with self.subTest(case=case):self.run_case(self.current,case)

    def test_original_independent_clean_invariants_fail(self):
        for case,reason in NEGATIVES.items():
            with self.subTest(case=case):self.run_case(self.original,case,11,reason)
        self.run_case(self.original,'no-reset')

    def test_current_mutants_are_rejected_without_changing_workload(self):
        # Counterfactual production mutations, not expected fixture payloads.
        mutations={
            'retire-probes':(lambda source:source.update(reset=retained()['functions']['reset']['content']),
                             'filter','retained-probemap-texel-rebound-to-other-owner'),
            'old-sampler-order':(lambda source:source.update(filter=source['filter'].replace(
                'mSamplerManager->ResetHWSamplers();\n\t\tmDescriptorSetManager->UpdateFixedTextureDescriptors();',
                'mDescriptorSetManager->UpdateFixedTextureDescriptors();\n\t\tmSamplerManager->ResetHWSamplers();')),
                'fixed-samplers','fixed-descriptor-retired-hw-sampler'),
            'early-sampler-rebuild':(lambda source:source.update(filter=source['filter'].replace(
                'mDescriptorSetManager->ResetHWTextureSets();\n\t\tmSamplerManager->ResetHWSamplers();',
                'mSamplerManager->ResetHWSamplers();\n\t\tmDescriptorSetManager->ResetHWTextureSets();')),
                'material-retirement','sampler-rebuilt-before-consumer-retirement'),
            'unbounded-cache':(lambda source:source.update(lookup=retained()['functions']['lookup']['content']),
                               'bounded-ordinal','out-of-range-grew-persistent-cache'),
        }
        for name,(mutate,case,reason) in mutations.items():
            with self.subTest(mutation=name):
                exe=build(self.directory/name,mutate=mutate)
                self.run_case(exe,case,11,reason)

    def test_source_owner_lifetimes_match_stable_cache_policy(self):
        texture=(ROOT/'src/common/rendering/vulkan/textures/vk_texture.cpp').read_text()
        # Prefix image/view identities are grow-only until texture-manager teardown.
        for family in ('Irradiance','Prefilter'):
            body=block(texture,'void VkTextureManager::Check'+family+'mapSize(')
            array=family+'maps'
            self.assertIn('int createStart = '+array+'.size();',body)
            self.assertIn('if ('+array+'.size() <= (size_t)cubeCount)',body)
            self.assertIn('for (int i = createStart; i < cubeCount; i++)',body)
            self.assertEqual(texture.count(array+'.resize('),1)
            self.assertNotIn(array+'.clear(',texture)
        reset=block(texture,'void VkTextureManager::ResetLightProbes()')
        self.assertIn('LightProbeEpoch.Invalidate();',reset)
        self.assertIn('clearColorImage',reset)
        self.assertNotIn('.reset(',reset)
        self.assertNotIn('.View =',reset)
        samplers=(ROOT/'src/common/rendering/vulkan/samplers/vk_samplers.cpp').read_text()
        hwreset=block(samplers,'void VkSamplerManager::ResetHWSamplers()')
        self.assertIn('DeleteHWSamplers();',hwreset)
        self.assertIn('CreateHWSamplers();',hwreset)
        for scope in ('CreateHWSamplers','DeleteHWSamplers','ResetHWSamplers'):
            body=block(samplers,'void VkSamplerManager::'+scope+'()')
            self.assertNotIn('IrradiancemapSampler',body)
            self.assertNotIn('PrefiltermapSampler',body)
        self.assertEqual(samplers.count('IrradiancemapSampler ='),1)
        self.assertEqual(samplers.count('PrefiltermapSampler ='),1)
        reset=fragments()['reset']
        # Ignore comments: no executable pair retirement in the material boundary.
        self.assertNotIn('for (int index : LightProbes)',reset)
        self.assertNotIn('LightProbes.clear();',reset)
        device=(ROOT/'src/common/rendering/vulkan/vk_renderdevice.cpp').read_text()
        death=block(device,'VulkanRenderDevice::~VulkanRenderDevice()')
        self.assertLess(death.index('vkDeviceWaitIdle'),death.index('mDescriptorSetManager->Deinit();'))
        self.assertLess(death.index('mDescriptorSetManager->Deinit();'),death.index('mTextureManager->Deinit();'))
        header=(ROOT/'src/common/rendering/vulkan/vk_renderdevice.h').read_text()
        self.assertLess(header.index('std::unique_ptr<VkTextureManager>'),header.index('std::unique_ptr<VkDescriptorSetManager>'))
        # Reverse member destruction: descriptor manager dies before its image owners.
        desc=(DESCRIPTORS/'vk_descriptorset.cpp').read_text()
        self.assertEqual(desc.count('CreateBindlessSet();'),1)
        self.assertNotIn('LightProbes.clear();',desc)

    def test_live_cvar_routes_and_semantic_material_sampling_are_preserved(self):
        cvars=(DATA/'hw_cvars.cpp').read_text()
        for signature in ('CUSTOM_CVARD(Float, gl_texture_filter_anisotropic,','CUSTOM_CVARD(Int, gl_texture_filter,'):
            self.assertIn('screen->SetTextureFilterMode();',block(cvars,signature))
        current=fragments(); old=retained()['functions']
        self.assertIn('mDescriptorSetManager->ResetHWTextureSets();',current['precache'])
        self.assertIn('mDescriptorSetManager->UpdateFixedTextureDescriptors();',current['precache'])
        self.assertNotIn('ResetHWSamplers',current['precache'])
        self.assertEqual(current['upload'],old['upload']['content'])
        # Material invalidation still precedes use; changing filtering is not disabled.
        self.assertIn('mat->DeleteDescriptors();',current['reset'])
        for slot in (0,1,2):self.assertIn(f'SetBindlessTexture({slot},',current['fixed'])
        self.assertNotIn('SetBindlessTexture(',current['reset'])
        self.assertLess(current['filter'].index('mDescriptorSetManager->ResetHWTextureSets();'),
                        current['filter'].index('mSamplerManager->ResetHWSamplers();'))
        self.assertLess(current['filter'].index('mSamplerManager->ResetHWSamplers();'),
                        current['filter'].index('mDescriptorSetManager->UpdateFixedTextureDescriptors();'))

    def test_pf113_preservation_rejects_unrelated_lookup_changes(self):
        pf113_source_extract.extract_current()
        original=(DESCRIPTORS/'vk_descriptorset.cpp').read_text()
        changed=original.replace('int bindIndex = AllocBindlessSlot(2);','int bindIndex = AllocBindlessSlot(1);')
        self.assertNotEqual(changed,original)
        with self.assertRaisesRegex(AssertionError,'outside SDVK-153 admission'):
            pf113_source_extract.extract_current(overrides={'descriptors':changed})


if __name__=='__main__':unittest.main()
