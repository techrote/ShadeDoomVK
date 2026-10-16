"""Fail-closed SDVK-014 durable-identity audit, not software acceptance.

The immutable assessed counterexamples are REQUIRED to fail their clean invariant in the child
process (exit 11). The unittest pass means evidence was reproduced, not repaired.
No Vulkan device is created. After the SDVK-153 repair candidate, the filter,
lookup and reset fragments are explicitly retained baseline bytes. Current
production is qualified separately by test_sdvk153_descriptor_lifetime.py.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block
from tools.pf_oracle.tests.sdvk153_source import retained

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DATA = ROOT / 'src/common/rendering/hwrenderer/data'
DESCRIPTORS = ROOT / 'src/common/rendering/vulkan/descriptorsets'
SOURCES = {
    'reset': ('src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp',
              'void VkDescriptorSetManager::ResetHWTextureSets()'),
    'lookup': ('src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp',
               'int VkDescriptorSetManager::GetLightProbeTextureIndex('),
    'filter': ('src/common/rendering/vulkan/vk_renderdevice.cpp',
               'void VulkanRenderDevice::SetTextureFilterMode()'),
    'upload': ('src/common/rendering/vulkan/vk_lightmapper.cpp',
               'int VkLightmapper::UploadProbeSelection()'),
}
CASES = {
    'atlas-live-control': (0, 'PASS'),
    'atlas-coordinate-negative': (0, 'PASS'),
    'atlas-free-reuse': (11, 'stale-atlas-receipt-accepted'),
    'atlas-clear-reuse': (11, 'stale-atlas-receipt-accepted'),
    'probe-no-reset-control': (0, 'PASS'),
    'probe-filter-reset': (11, 'retained-probemap-texel-rebound-to-other-owner'),
    'reserved-page-control': (0, 'PASS'),
}


def source(key: str) -> str:
    path, signature = SOURCES[key]
    return block((ROOT / path).read_text(), signature)


def build(directory: Path, preserve_probe_slots: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    # Preserve the original audit as historical negative evidence. Do not
    # pretend candidate code is still expected to demonstrate the old defect.
    fragments = {key: retained()['functions'][key]['content'] for key in SOURCES}
    if preserve_probe_slots:
        # Counterfactual CPU control only. This is NOT a published renderer fix.
        old = '\tfor (int index : LightProbes)\n\t\tFreeBindlessSlot(index);\n\tLightProbes.clear();'
        if fragments['reset'].count(old) != 1:
            raise AssertionError('Expected one probe retirement boundary')
        fragments['reset'] = fragments['reset'].replace(old, '')
    (directory / 'audit_producer_methods.cpp').write_text('\n\n'.join(fragments.values()))
    bounds = (ROOT / 'src/common/utility/bounds.cpp').read_text()
    (directory / 'audit_bounds.cpp').write_text('#define M_INFINITY 1e30f\n' + '\n'.join(
        block(bounds, signature) for signature in ('BBox::BBox()', 'void BBox::Clear()')))
    (directory / 'audit_rectpacker.cpp').write_bytes((DATA / 'hw_rectpacker.cpp').read_bytes())
    return compile_fixture(HERE / 'sdvk014_identity_audit_fixture.cpp', output_dir=directory,
                           includes=[directory, DATA, DESCRIPTORS, ROOT / 'src/common/rendering',
                                     ROOT / 'src/common/utility', ROOT / 'src/common/thirdparty'])


class DurableIdentityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sdvk014-identity-audit-')
        cls.directory = Path(cls.temp.name)
        cls.exe = build(cls.directory / 'retained-baseline')
        cls.control = build(cls.directory / 'counterfactual', preserve_probe_slots=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_retained_controls_and_named_blocking_counterexamples(self):
        for case, (code, reason) in CASES.items():
            with self.subTest(case=case):
                result = subprocess.run([str(self.exe), case], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertIn(reason, result.stdout + result.stderr)

    def test_counterfactual_stable_pair_identity_removes_descriptor_counterexample(self):
        result = subprocess.run([str(self.control), 'probe-preserve-control'],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('retained_texel_owner=0', result.stdout)

    def test_production_user_setting_route_and_persistent_raw_shader_consumer(self):
        cvars = (DATA / 'hw_cvars.cpp').read_text()
        for signature in ('CUSTOM_CVARD(Float, gl_texture_filter_anisotropic,',
                          'CUSTOM_CVARD(Int, gl_texture_filter,'):
            self.assertIn('screen->SetTextureFilterMode();', block(cvars, signature))
        self.assertNotIn('Lightmap', source('reset'))
        self.assertNotIn('LightProbeEpoch', source('reset'))
        self.assertNotIn('levelMesh', source('filter'))
        sampler = (ROOT / 'src/common/rendering/vulkan/samplers/vk_samplers.cpp').read_text()
        reset = block(sampler, 'void VkSamplerManager::ResetHWSamplers()')
        self.assertIn('DeleteHWSamplers();', reset)
        self.assertIn('CreateHWSamplers();', reset)
        self.assertNotIn('Irradiance', reset)
        self.assertNotIn('Prefilter', reset)
        shader = (ROOT / 'wadsrc/static/shaders/lightmap/frag_copy.glsl').read_text()
        self.assertIn('closestTextureIndex = candidate.textureIndex;', shader)
        self.assertIn('FragProbe = uvec4(probeIndex, 0u, 0u, 0u);', shader)
        consumer = (ROOT / 'wadsrc/static/shaders/scene/lightmodel_pbr.glsl').read_text()
        self.assertIn('textureGather(uintTextures[nonuniformEXT(vLightmapIndex + 1)]', consumer)
        self.assertIn('SampleProbeIrradiance(probeIndexes.x, N)', consumer)
        self.assertIn('SampleProbePrefiltered(probeIndexes.x, R, roughness * MAX_REFLECTION_LOD)', consumer)

    def test_tile_release_invalidates_real_surface_before_slot_reuse(self):
        doom = (ROOT / 'src/rendering/hwrenderer/doom_levelmesh.cpp').read_text()
        release = block(doom, 'void DoomLevelMesh::ReleaseTiles(')
        self.assertLess(release.index('Lightmap.AtlasPacker->Free('), release.index('FreeTile(tileIndex);'))
        self.assertIn('tile.AtlasLocation.Item = nullptr;', release)
        self.assertIn('tileIndex = -1;', release)
        mesh = (DATA / 'hw_levelmesh.h').read_text()
        retire = block(mesh, 'inline void LevelMesh::FreeTile(')
        self.assertLess(retire.index('tile = LightmapTile();'), retire.index('Lightmap.FreeTiles.Push(index);'))
        # FullRefresh is queued surface rebuilding, NOT a claimed atomic atlas repack.
        full = block((ROOT / 'src/rendering/hwrenderer/doom_levelmesh.h').read_text(),
                     'void FullRefresh() override')
        self.assertIn('UpdateSide(', full)
        self.assertIn('UpdateFlat(', full)
        self.assertNotIn('Reset()', full)
        self.assertNotIn('AtlasPacker', full)

    def test_retained_lightmap_has_semantic_bindings_not_runtime_slot_or_freshness_digest(self):
        load = block((ROOT / 'src/maploader/maploader.cpp').read_text(), 'bool MapLoader::LoadLightmap(')
        entry = block(load, 'struct TileEntry')
        for name in ('typeIndex', 'controlSector', 'pixelsOffset', 'translateWorldToLocal'):
            self.assertIn(name, entry)
        for name in ('generation', 'epoch', 'digest', 'checksum', 'PageIndex'):
            self.assertNotIn(name, entry)
        self.assertLess(load.index('std::map<LightmapTileBinding, LightmapTile*> levelTiles'),
                        load.index('Level->levelMesh->PackLightmapAtlas();'))
        self.assertIn('const TileEntry* entry = binding.first;', load)
        self.assertIn('tile->AtlasLocation.ArrayIndex', load)


if __name__ == '__main__':
    unittest.main()
