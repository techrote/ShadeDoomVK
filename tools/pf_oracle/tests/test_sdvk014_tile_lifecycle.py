"""Exact production CPU lightmap ownership/serialization counterexamples.

No device, image or renderer is created. Readback/upload are explicit sinks;
WAD compression/replacement and native lightmap pixels remain unqualified.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk156_source import RETAINED, retain_atlas_headers
from tools.pf_oracle.tests.sdvk014_source import block,current
HERE=Path(__file__).resolve().parent
DATA=ROOT/'src/common/rendering/hwrenderer/data'
OLD=HERE/'fixtures/sdvk014_lightmap_pre_fix.json'
CASES=('shared-retirement','background','stats','save-bindings','readback-isolation',
       'upload-consumption','failed-upload-retained','invalid-owner','live-free',
       'region-negatives','bounded-retirement')


def build(directory: Path,original: bool=False) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    retained=json.loads(OLD.read_text())['functions']
    def source(key):
        return retained[key]['content'] if original else current(key)
    # Real bbox constructors, real tile/vector/TArray headers, entire RectPacker.
    bounds=(ROOT/'src/common/utility/bounds.cpp').read_text()
    (directory/'sdvk014_bounds_under_test.cpp').write_text('#define M_INFINITY 1e30f\n'+
        '\n'.join(block(bounds,s) for s in ('BBox::BBox()','BBox::BBox(const FVector3','void BBox::Clear()')))
    if original:
        retain_atlas_headers(directory)
    (directory/'sdvk014_rectpacker_under_test.cpp').write_text(((RETAINED if original else DATA)/'hw_rectpacker.cpp').read_text())
    doom=(ROOT/'src/rendering/hwrenderer/doom_levelmesh.cpp').read_text()
    # Preserve actual encoding; expose completed bytes, omit filesystem/compression.
    writer=doom[doom.index('class LumpWriter'):doom.index('\tTArray<uint8_t> DeflateCompress()')]
    writer+='\n const TArray<uint8_t>& Bytes() const {return buffer;}\nprivate:\n size_t pos=0;\n TArray<uint8_t> buffer;\n};\n'
    save=source('save')
    assert save.count('\tFString fullpath = GetMapFilename(doomMap);')==1
    save=save.split('\tFString fullpath = GetMapFilename(doomMap);')[0]
    save=save.replace('void DoomLevelMesh::SaveLightmapLump(FLevelLocals& doomMap)',
                      'void DoomLevelMesh::SavePrefix()')
    if not original:
        save=save.replace('{\n\t/*', '{\n\tFLevelLocals doomMap{};\n\t/*', 1)
    save+='saved.assign(lumpFile.Bytes().begin(),lumpFile.Bytes().end());\n}'
    frame='void VulkanRenderDevice::PublishMesh() {\n'+block(source('frame'),'if (levelMeshChanged)')+'\n}'
    methods='\n'.join(source(k) for k in ('alloc','free','stats','release','invalidate','update'))
    (directory/'sdvk014_tile_methods.cpp').write_text(writer+methods+'\n'+save+'\n'+frame)
    fixture = (RETAINED if original else HERE)/'sdvk014_tile_fixture.cpp'
    if original:
        local_fixture = directory / fixture.name
        local_fixture.write_bytes(fixture.read_bytes())
        fixture = local_fixture
    return compile_fixture(fixture,output_dir=directory,
        includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


class TileLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk014-tiles-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_current_ownership_serialization_and_mutation_controls(self):
        for case in CASES:
            with self.subTest(case=case):
                p=subprocess.run([str(self.current),case],text=True,capture_output=True,timeout=15)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertIn('PASS '+case,p.stdout)

    def test_retained_actual_defects_are_falsifiable(self):
        pins=json.loads(OLD.read_text())
        for entry in pins['functions'].values():
            self.assertEqual(hashlib.sha256(entry['content'].encode()).hexdigest(),entry['sha256'])
        failures={
            'shared-retirement':'retired-tile-still-publishable',
            'background':'retired-background-binding',
            'stats':'retired-statistics',
            'save-bindings':'ghost-binding-serialized',
            'readback-isolation':'readback-overwrote-upload-shape',
            'upload-consumption':'successful-upload-not-consumed',
            'invalid-owner':'invalid-owner-reached-readback',
            'live-free':'live-tile-retired',
            'bounded-retirement':'retired-stress-update',
        }
        for case,reason in failures.items():
            with self.subTest(case=case):
                p=subprocess.run([str(self.original),case],text=True,capture_output=True,timeout=15)
                self.assertEqual(p.returncode,11,p.stdout+p.stderr)
                self.assertIn(reason,p.stderr)


if __name__=='__main__':
    unittest.main()
