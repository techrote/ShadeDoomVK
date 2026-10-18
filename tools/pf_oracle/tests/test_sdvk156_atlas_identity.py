"""Current allocation receipts, preserved ABA negatives and exact-source mutations."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.tests.legacy_msvc_fixture import (
    compile_legacy_fixture as compile_fixture, extracted_legacy_scope)
from tools.pf_oracle.tests.sdvk014_source import block
from tools.pf_oracle.tests.sdvk156_source import ROOT, RETAINED, retained_files, retain_atlas_headers

HERE=Path(__file__).resolve().parent
DATA=ROOT/'src/common/rendering/hwrenderer/data'
CASES=('copied-free-aba','copied-clear-aba','owner-recreation','foreign-malformed',
       'stale-free','coalesced-reuse','multiple-pages','incremental-pack',
       'copied-tile-admission','malformed-region','scratch-repack','pending-destination',
       'repack-requires-retirement','duplicate-pending','scratch-region','selected-tile-mismatch',
       'owner-switch-pending','incarnation-exhaustion','owner-exhaustion','bounded-rebuild')


def build(directory: Path, mutate=None) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    sources={
        'rect':(DATA/'hw_rectpacker.cpp').read_text(),
        'mesh_h':(DATA/'hw_levelmesh.h').read_text(),
        'mesh':(DATA/'hw_levelmesh.cpp').read_text(),
        'doom':(ROOT/'src/rendering/hwrenderer/doom_levelmesh.cpp').read_text(),
        'mapper':(ROOT/'src/common/rendering/vulkan/vk_lightmapper.cpp').read_text(),
    }
    if mutate:mutate(sources)
    (directory/'sdvk156_rectpacker.cpp').write_text(sources['rect'])
    bounds=(ROOT/'src/common/utility/bounds.cpp').read_text()
    (directory/'sdvk156_bounds.cpp').write_text('#define M_INFINITY 1e30f\n'+
        '\n'.join(block(bounds,s) for s in ('BBox::BBox()','void BBox::Clear()')))
    methods=[block(sources['mesh_h'],s) for s in ('inline int LevelMesh::AllocTile(', 'inline void LevelMesh::FreeTile(')]
    for signature, name in (
            ('void ValidateLightmapTile(', 'ValidateLightmapTile'),
            ('const LightmapTile& GetLightmapTile(int index) const', 'GetLightmapTile'),
            ('LightmapTile& GetLightmapTile(int index)\n', 'GetLightmapTile')):
        definition=block(sources['mesh_h'],signature)
        methods.append(definition.replace(name+'(', 'LevelMesh::'+name+'(', 1))
    methods += [block(sources['mesh'],'void LevelMesh::PackLightmapAtlas('),
                block(sources['doom'],'void DoomLevelMesh::ReleaseTiles('),
                block(sources['mapper'],'void VkLightmapper::SetLevelMesh('),
                block(sources['mapper'],'void VkLightmapper::SelectTiles('),
                block(sources['mapper'],'void VkLightmapper::ValidateSelectedTile(')]
    # Unchanged SelectTiles has nested loop-variable shadowing under MSVC /W4.
    (directory/'sdvk156_methods.cpp').write_text(extracted_legacy_scope('\n\n'.join(methods), (4456,)))
    mapper_h=(ROOT/'src/common/rendering/vulkan/vk_lightmapper.h').read_text()
    (directory/'sdvk156_selected_type.cpp').write_text(block(mapper_h,'struct SelectedTile')+';\n')
    return compile_fixture(HERE/'sdvk156_atlas_identity_fixture.cpp',output_dir=directory,
        includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


def build_geometry(directory: Path, historical: bool=False) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    if historical:retain_atlas_headers(directory)
    source=RETAINED/'hw_rectpacker.cpp' if historical else DATA/'hw_rectpacker.cpp'
    (directory/'sdvk156_geometry_allocator.cpp').write_bytes(source.read_bytes())
    (directory/'sdvk156_geometry_mode.h').write_text('#define SDVK156_CURRENT '+str(int(not historical))+'\n')
    return compile_fixture(HERE/'sdvk156_geometry_equivalence_fixture.cpp',output_dir=directory,
        includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


def change(key,old,new):
    def apply(sources):
        if sources[key].count(old)!=1:raise AssertionError('Mutation boundary changed: '+old)
        sources[key]=sources[key].replace(old,new)
    return apply


MUTANTS={
    'repeat-incarnation':(change('rect','item->Incarnation = ++LastIncarnation;',
                                     'item->Incarnation = 1; ++LastIncarnation;'),
                          'copied-free-aba','stale-atlas-receipt-accepted'),
    'omit-incarnation':(change('rect','item->Incarnation != allocation.Incarnation || ',''),
                         'copied-free-aba','stale-atlas-receipt-accepted'),
    'clear-restarts-incarnation':(change('rect','void RectPacker::Clear()\n{',
                                             'void RectPacker::Clear()\n{\n LastIncarnation = 0;'),
                                   'copied-clear-aba','stale-clear-receipt-accepted'),
    'omit-owner':(change('rect','allocation.Owner != Owner || ',''),
                   'owner-recreation','destroyed-owner-receipt-accepted'),
    'unchecked-free':(change('rect','RectPackerItem* item = FindAllocation(allocation);',
                                 'RectPackerItem* item = Items[allocation.Slot].get();'),
                       'stale-free','stale-free-mutated-live-owner'),
    'unguarded-consumer':(change('mesh_h','\t\tValidateLightmapTile(tile);',''),
                           'malformed-region','unguarded-tile-consumer'),
    'unchecked-selected-destination':(change('mapper',
        'selected.Tile->AtlasLocation.Allocation != selected.AtlasAllocation', 'false'),
        'selected-tile-mismatch','selected-tile-mismatch-accepted'),
    'wrapping-incarnation':(change('rect','if (LastIncarnation == std::numeric_limits<uint64_t>::max())',
                                       'if (false)'),
                             'incarnation-exhaustion','allocation-counter-wrapped'),
}


class AtlasIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk156-identity-')
        cls.directory=Path(cls.temp.name);cls.exe=build(cls.directory/'current')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_current_exact_producers_consumers_and_recycled_storage(self):
        for case in CASES:
            with self.subTest(case=case):
                result=subprocess.run([str(self.exe),case],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('PASS '+case,result.stdout)

    def test_compiled_mutants_fail_the_named_invariant(self):
        for name,(mutation,case,reason) in MUTANTS.items():
            with self.subTest(mutation=name):
                executable=build(self.directory/name,mutation)
                result=subprocess.run([str(executable),case],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,11,result.stdout+result.stderr)
                self.assertIn(reason,result.stdout+result.stderr)

    def test_valid_allocation_geometry_is_byte_identical(self):
        results=[]
        for historical in (True,False):
            exe=build_geometry(self.directory/('geometry-old' if historical else 'geometry-current'),historical)
            result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            results.append(result.stdout)
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(results[0].splitlines()),2592) # 2,560 regions + 32 page summaries

    def test_original_atlas_source_and_driver_pins(self):
        self.assertEqual(len(retained_files()),5)

    def test_all_production_receipts_have_checked_consumers(self):
        header=(DATA/'hw_rectpacker.h').read_text()
        self.assertIn('RectPackerAllocation Alloc(',header)
        self.assertIn('bool Free(const RectPackerAllocation&',header)
        self.assertNotIn('void Free(RectPackerItem*',header)
        self.assertIn('RectPacker(const RectPacker&) = delete;',header)
        self.assertIn('RectPacker(RectPacker&&) = delete;',header)
        for p in (ROOT/'src').rglob('*'):
            if p.suffix not in ('.h','.cpp'):continue
            self.assertNotIn('AtlasLocation.Item',p.read_text(errors='replace'),str(p))
        consumers={
            'src/rendering/hwrenderer/scene/hw_drawinfo.h':1,
            'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp':1,
            'src/rendering/hwrenderer/scene/hw_decal.cpp':2,
            'src/rendering/hwrenderer/hw_vertexbuilder.cpp':1,
            'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp':1,
        }
        for path,count in consumers.items():
            self.assertEqual((ROOT/path).read_text().count('GetLightmapTile('),count,path)
        mapper=(ROOT/'src/common/rendering/vulkan/vk_lightmapper.cpp').read_text()
        copy=block(mapper,'void VkLightmapper::CopyResult(')
        self.assertLess(copy.index('ValidateSelectedTile(selected);'),copy.index('selected.Tile->AtlasLocation.ArrayIndex'))
        render=block(mapper,'void VkLightmapper::Render(')
        self.assertLess(render.index('ValidateSelectedTile(selected)'),render.index('GetTransferCommands()'))
        selected=block(mapper,'void VkLightmapper::ValidateSelectedTile(')
        self.assertLess(selected.index('IsLive(selected.AtlasAllocation)'),selected.index('selected.Tile->'))
        self.assertIn('IsLive(selected.ScratchAllocation)',selected)
        self.assertIn('selected.Tile->AtlasLocation.Allocation != selected.AtlasAllocation',selected)
        load=block((ROOT/'src/maploader/maploader.cpp').read_text(),'bool MapLoader::LoadLightmap(')
        self.assertLess(load.index('ValidateLightmapTile(*tile)'),load.index('const uint16_t* src ='))


if __name__=='__main__':unittest.main()
