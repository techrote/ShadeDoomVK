"""Execute real constructor lifetime identity without changing legacy epochs."""
from pathlib import Path
import subprocess
import json
import hashlib
import tempfile
import unittest
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block

DATA=ROOT/'src/common/rendering/hwrenderer/data'
HERE=Path(__file__).resolve().parent

# Exact original resource builder at published6ed; retained as a CPU control.
ORIGINAL_RESOURCE_BLOCK='if (level.levelMesh)\n        {\n            const auto& epochs = level.levelMesh->GetMutationEpochs();\n            result.Raw("levelmesh", Object().Int("epoch", level.levelMesh->GetResourceEpoch().Generation)\n                .Int("geometry", epochs.Geometry).Int("surface", epochs.Surface).Int("lights", epochs.Lights).Int("query", epochs.Query)\n                .Int("portals", epochs.Portals).Int("lightmap_probe", epochs.LightmapProbe).Int("resets", epochs.Resets).Json())\n                .Raw("lightmap_state", LightmapLifecycle(level.levelMesh, textures->Lightmaps.size(),\n                    device->GetFrameTileUpdates(), device->GetFrameTileCompletions()));\n        }'
ORIGINAL_RESOURCE_SHA256='fc88ecd82045c62e1c96af150dd5e2ee990da54a534eb08ba156a98322e048b0'


class MeshOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk161-mesh-owner-')
        directory=Path(cls.temp.name)
        source=(DATA/'hw_levelmesh.cpp').read_text()
        header=(DATA/'hw_levelmesh.h').read_text()
        selections={
            'constructor':block(source,'LevelMesh::LevelMesh()'),
            # Reset contains a C++ digit separator that this shared lexical helper
            # treats as a character literal; retain its exact top-level source.
            'reset':source[source.index('void LevelMesh::Reset()'):].split('\n}\n',1)[0]+'\n}',
            'getter':block(header,'uint64_t GetResourceOwner()'),
            'member':next(line for line in header.splitlines() if 'const uint64_t ResourceOwner;' in line),
            'mutations':block(header,'const LevelMeshMutationEpochSnapshot& GetMutationEpochs()'),
            'sequence':'std::atomic<uint64_t> LevelMeshOwnerSequence{0};\n'+block(source,'uint64_t NextLevelMeshOwner()'),
        }
        for name,content in selections.items():
            (directory/f'mesh_owner_{name}.inc').write_text(content)
        resource=(ROOT/'src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp').read_text()
        (directory/'mesh_owner_resource.inc').write_text(block(resource,'if (level.levelMesh)\n        {'))
        if hashlib.sha256(ORIGINAL_RESOURCE_BLOCK.encode()).hexdigest()!=ORIGINAL_RESOURCE_SHA256:
            raise AssertionError('Retained original6ed resource builder changed')
        (directory/'mesh_owner_resource_original.inc').write_text(ORIGINAL_RESOURCE_BLOCK)
        cls.binary=compile_fixture(HERE/'sdvk161_mesh_owner_fixture.cpp',output_dir=directory,includes=[DATA,directory,ROOT/'src/rendering/hwrenderer/diagnostics'])

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_actual_lifetime_allocator_and_reset_reject_reused_address_with_equal_local_epoch(self):
        result=subprocess.run([str(self.binary)],check=True,capture_output=True,text=True,timeout=10)
        self.assertIn('same-address epoch3 negative / 128 ordinary resets / 512 concurrent constructor identities',result.stdout)

    def test_actual_owner_allocator_exhaustion_cannot_wrap_or_reissue(self):
        result=subprocess.run([str(self.binary),'exhaustion'],check=True,capture_output=True,text=True,timeout=10)
        self.assertIn('fails closed without wrapping',result.stdout)

    def test_passive_resource_and_both_actual_surface_paths_pair_member_with_legacy_epoch(self):
        source=(ROOT/'src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp').read_text()
        for signature in ('static void LevelMeshSurfaces(', 'static void ImmediateSpecialSurface('):
            actual=block(source,signature)
            self.assertIn('Int("mesh_owner", mesh',actual)
            self.assertIn('GetResourceOwner()',actual)
            self.assertIn('Int("mesh_epoch", mesh',actual)
            self.assertNotIn('NextLevelMeshOwner',actual)
        actual=block(source,'void VulkanResources(')
        self.assertIn('Int("owner", level.levelMesh->GetResourceOwner())',actual)
        self.assertIn('Int("epoch", level.levelMesh->GetResourceEpoch().Generation)',actual)
        self.assertIn('if (SpecialSurfaceEnabled()) meshState.Int("owner", level.levelMesh->GetResourceOwner())',actual)

    def test_actual_resource_emission_preserves_ordinary_bytes_and_scopes_lifetime_to_161(self):
        result=subprocess.run([str(self.binary),'serialization'],check=True,capture_output=True,text=True,timeout=10)
        value=json.loads(result.stdout)
        self.assertEqual(value['ordinary_json'],value['original_json'])
        self.assertEqual(value['other_ordinary_json'],value['original_json'])
        ordinary=json.loads(value['ordinary_json'])
        self.assertNotIn('owner',ordinary['levelmesh'])
        previous=0
        for name in ('special_json','other_special_json'):
            special=json.loads(value[name])
            owner=special['levelmesh'].pop('owner')
            self.assertGreater(owner,previous)
            previous=owner
            self.assertEqual(special,ordinary)


if __name__=='__main__':unittest.main()
