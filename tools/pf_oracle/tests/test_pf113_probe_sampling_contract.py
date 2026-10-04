"""PF113 compiled actual-source regressions; no Vulkan or GPU execution.

The retained baseline is deliberately unsafe and must still fail --require-safe.
Candidate GLSL helper/consumer bodies run through bounded C++ scalar/vector and
sample logging services; this does not claim spatial filtering or GPU legality.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.pf_oracle.fixture_runner import compile_fixture
import pf113_source_extract as source

FIXTURE = Path(__file__).with_name('pf113_probe_fixture.cpp')


def restored_shader(candidate: str) -> str:
    """Reverse exactly the adopted ten calls/helper addition, not other PBR code."""
    start = candidate.index('// Runtime zero is no probe, not the fixed 2D null/BRDF pair.')
    stop = candidate.index('vec3 ProcessMaterialLight(', start)
    restored = candidate[:start] + candidate[stop:]
    for axis in 'xyzw':
        restored = restored.replace(f'SampleProbeIrradiance(probeIndexes.{axis}, N)',
                                    f'texture(cubeTextures[probeIndexes.{axis}], N).rgb')
        restored = restored.replace(f'SampleProbePrefiltered(probeIndexes.{axis}, R, roughness * MAX_REFLECTION_LOD)',
                                    f'textureLod(cubeTextures[probeIndexes.{axis} + 1], R, roughness * MAX_REFLECTION_LOD).rgb')
    restored = restored.replace('SampleProbeIrradiance(uint(uLightProbeIndex), N)',
                                'texture(cubeTextures[uLightProbeIndex], N).rgb')
    return restored.replace('SampleProbePrefiltered(uint(uLightProbeIndex), R, roughness * MAX_REFLECTION_LOD)',
                            'textureLod(cubeTextures[uLightProbeIndex + 1], R, roughness * MAX_REFLECTION_LOD).rgb')


def build_candidate(directory: Path, *, shader: str | None = None, name: str = 'candidate', overrides: dict[str, str] | None = None) -> Path:
    header, constants, metadata = source.extract_current(shader=shader, overrides=overrides)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'pf113_current_extracted.hpp').write_text(header, encoding='utf-8', newline='\n')
    (directory / 'source_constants.hpp').write_text(constants, encoding='utf-8', newline='\n')
    for kind, body in metadata['creation_structs'].items():
        (directory / (kind + '_creation.hpp')).write_text(body + '\n', encoding='utf-8', newline='\n')
    (directory / 'extraction.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return compile_fixture(FIXTURE, output_dir=directory, includes=[directory], name=name)


class SourcePreservationTests(unittest.TestCase):
    def test_original_hashes_and_namespace_provenance_are_pinned(self):
        manifest = source.pinned_original()
        self.assertEqual(manifest['schema'], 'pf113-disposable-original-extraction/v1')
        derivation = json.loads((source.ORIGINAL / 'namespace-derivation.json').read_text())
        self.assertTrue(derivation['exact_cpp_and_sampling_bodies_unchanged'])
        self.assertTrue(derivation['exact_selector_body_unchanged'])
        self.assertTrue(derivation['no_compiler_warning_suppression'])
        self.assertEqual(derivation['retained_failed_receipt_sha256'],
                         '9797e04ed3ae25f9e4532773a50f12f02732affd78f893d4c3087d02890de14d')

    def test_rest_pbr_is_exact_original_including_direct_ambient_and_brdf(self):
        shader = (ROOT / source.PATHS['shader']).read_text()
        original = (source.ORIGINAL / 'lightmodel_pbr.glsl').read_text()
        self.assertEqual(restored_shader(shader), original)

    def test_actual_extraction_contains_current_helpers_and_complete_consumer(self):
        header, constants, metadata = source.extract_current()
        self.assertIn('SampleProbeIrradiance(ObservedIndex base, vec3 N)', header)
        self.assertIn('SampleProbePrefiltered(ObservedIndex base, vec3 R, float lod)', header)
        self.assertIn('nonuniformEXT(base + 1u)', header)
        self.assertIn('roughness * MAX_REFLECTION_LOD', header)
        self.assertIn('static const int IrradiancemapSize = 32;', constants)
        self.assertEqual(sum(entry['name'] == 'current-pbr-sampling' for entry in metadata['extractions']), 1)

    def test_actual_builder_declared_defaults_match_compiled_service(self):
        header = (ROOT / source.PATHS['builder_header']).read_text()
        self.assertIn('Size(int width, int height, int miplevels = 1, int arrayLayers = 1)', header)
        self.assertIn('int mipLevel = 0, int arrayLayer = 0, int levelCount = 0, int layerCount = 0', header)
        self.assertRegex(header, r'VkImageCreateInfo imageInfo\s*=\s*\{\};')
        self.assertRegex(header, r'VkImageViewCreateInfo viewInfo\s*=\s*\{\};')
        self.assertRegex(header, r'VkSamplerCreateInfo samplerInfo\s*=\s*\{\};')

    def test_all_sampled_irradiance_creation_paths_use_actual_one_mip_views(self):
        text = (ROOT / source.PATHS['texture']).read_text()
        allocated = source.definition(text, 'void VkTextureManager::CheckIrradiancemapSize')
        self.assertIn('.Size(IrradiancemapSize, IrradiancemapSize, 1, 6)', allocated)
        self.assertIn('.Type(VK_IMAGE_VIEW_TYPE_CUBE)', allocated)
        prober = (ROOT / source.PATHS['prober']).read_text()
        generated = source.definition(prober, 'void VkLightprober::GenerateIrradianceMap(')
        self.assertIn('.Size(32, 32, 1, 6)', generated)

    def test_nonuniform_capability_is_an_existing_device_requirement(self):
        header = (ROOT / 'src/common/rendering/vulkan/vk_capabilities.h').read_text()
        device = (ROOT / 'src/common/rendering/vulkan/vk_renderdevice.cpp').read_text()
        self.assertIn('RuntimeDescriptorArray && SampledImageArrayNonUniformIndexing', header)
        self.assertIn('shaderSampledImageArrayNonUniformIndexing', device)


class CompiledProbeSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source.pinned_original()
        cls.temporary = tempfile.TemporaryDirectory(prefix='pf113-cpu-')
        cls.directory = Path(cls.temporary.name)
        cls.current = build_candidate(cls.directory / 'current')
        cls.original = compile_fixture(source.ORIGINAL / 'original_probe_fixture.cpp',
                                       output_dir=cls.directory / 'original', includes=[source.ORIGINAL], name='original')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_executable(self, executable: Path, argument: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(executable), argument], cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_current_uniform_zero_mixed_publication_live_sampler_and_view_controls(self):
        completed = self.run_executable(self.current, '--current')
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('CURRENT SOURCE PASS:', completed.stdout)
        self.assertIn('No Vulkan execution or spatial GPU filtering claim.', completed.stdout)

    def test_original_negative_still_observes_twenty_invalid_fixed_2d_attempts(self):
        completed = self.run_executable(self.original, '--observe-original')
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('20 incompatible sample attempts; 275 CPU service/source checks', completed.stdout)

    def test_original_require_safe_is_retained_expected_failure(self):
        completed = self.run_executable(self.original, '--require-safe')
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Original PBR attempts incompatible fixed 2D cube samples', completed.stderr)

    def mutation(self, name: str, before: str, after: str, failure: str):
        shader = (ROOT / source.PATHS['shader']).read_text()
        self.assertIn(before, shader)
        executable = build_candidate(self.directory / name, shader=shader.replace(before, after, 1), name=name)
        completed = self.run_executable(executable, '--current')
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn(failure, completed.stderr)

    def test_negative_zero_guard_bypass_reproduces_invalid_access(self):
        self.mutation('missing_guard', 'if (base == 0u)', 'if (base == 4095u)',
                      'Zero guard precedes descriptor lookup')

    def test_negative_missing_nonuniform_qualification_fails_actual_live_reads(self):
        self.mutation('unqualified', 'cubeTextures[nonuniformEXT(base)]', 'cubeTextures[base]',
                      'Every actual cube read is nonuniform qualified')

    def test_negative_early_pair_evaluation_is_observed_before_zero_return(self):
        self.mutation('early_pair', 'if (base == 0u)\n\t\treturn vec3(0.0);\n\treturn textureLod(cubeTextures[nonuniformEXT(base + 1u)]',
                      'ObservedIndex premature = base + 1u;\n\t(void)premature;\n\tif (base == 0u)\n\t\treturn vec3(0.0);\n\treturn textureLod(cubeTextures[nonuniformEXT(base + 1u)]',
                      'Zero guard precedes descriptor lookup')

    def test_negative_weight_change_is_not_masked_by_zero_policy(self):
        self.mutation('weights', 'float t00 = invt.x * invt.y;', 'float t00 = invt.x * invt.y * 2.0f;',
                      'Original all-live golden contribution')

    def test_negative_prefilter_lod_change_fails_actual_live_read_log(self):
        self.mutation('pref_lod', 'return textureLod(cubeTextures[nonuniformEXT(base + 1u)], R, lod).rgb;',
                      'return textureLod(cubeTextures[nonuniformEXT(base + 1u)], R, lod * 0.0f).rgb;',
                      'Original uniform order and roughness LOD')

    def test_negative_direction_change_fails_actual_live_read_log(self):
        self.mutation('direction', 'return textureLod(cubeTextures[nonuniformEXT(base)], N, 0.0).rgb;',
                      'return textureLod(cubeTextures[nonuniformEXT(base)], N * 0.0f, 0.0).rgb;',
                      'Four irradiance reads preserve order/N')

    def test_negative_metadata_wrong_lod_forwarding_is_detected(self):
        builder = (ROOT / source.PATHS['builder']).read_text()
        original = 'obj->Creation.MaxLod = samplerInfo.maxLod;'
        self.assertEqual(builder.count(original), 1)
        executable = build_candidate(self.directory / 'wrong_capture', name='wrong_capture',
                                     overrides={'builder': builder.replace(original, 'obj->Creation.MaxLod = samplerInfo.minLod;')})
        completed = self.run_executable(executable, '--current')
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Actual sampler builder captures the same successful API arguments', completed.stderr)

    def test_negative_dedicated_anisotropy_change_breaks_lod_equivalence_contract(self):
        builder = (ROOT / source.PATHS['builder']).read_text()
        executable = build_candidate(self.directory / 'anisotropy', name='anisotropy',
                                     overrides={'builder': builder.replace('samplerInfo.anisotropyEnable = VK_FALSE;', 'samplerInfo.anisotropyEnable = 1;', 1)})
        completed = self.run_executable(executable, '--current')
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Actual dedicated sampler preserves one-mip LOD0 filtering contract', completed.stderr)


if __name__ == '__main__':
    unittest.main()
