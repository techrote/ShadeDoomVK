"""Actual selected mesh observer must expose a coherent wrong bound material.

The parent hook, triangle grouping, ownership/current-UV calculation and output
serializers execute extracted production code. Bound descriptor/probe payloads
are explicit CPU services. These tests create no renderer or Vulkan device.
"""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block
from tools.renderer_oracle import sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests.test_sdvk161_special_surfaces import (
    full_raw, independent_receiver_tile, material, native_recipe, ordinary_a_ceiling, resource, stdout, surface)

HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp'
RETAINED=HERE/'fixtures/sdvk161-mesh-material-filter-pre-fix.json'
RETAINED_SHA256='0e3d4266a9f45338f1eef2e103f0f18807116a674c8756128b9bb6e8c9d89e9b'


def build(directory, original=False):
    directory.mkdir(parents=True,exist_ok=True)
    source=SOURCE.read_text()
    method=block(source,'static void LevelMeshSurfaces(')
    if original:
        raw=RETAINED.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=RETAINED_SHA256:
            raise AssertionError('Historical material-filter receipt changed')
        old=json.loads(raw)
        if hashlib.sha256(old['content'].encode()).hexdigest()!=old['sha256']:
            raise AssertionError('Historical material-filter observer changed')
        method=old['content']
        # Preserve the retained filter/traversal counterexample while adapting
        # only its additive lifetime metadata to the current witness schema.
        # The supplied owner belongs to the same explicit CPU mesh service as
        # its unchanged local epoch. This is not recovered native evidence.
        local_epoch='.Int("mesh_epoch", mesh->GetResourceEpoch().Generation)'
        assert method.count(local_epoch)==1
        method=method.replace(local_epoch,local_epoch+'.Int("mesh_owner", mesh->GetResourceOwner())')
    (directory/'mesh_witness_access.inc').write_text(method+'\n'+block(source,'static void LevelMeshDraw('))
    (directory/'mesh_witness_callback.inc').write_text(block(source,'void VulkanLevelMeshDraw('))
    (directory/'mesh_witness_serializers.inc').write_text('\n'.join(block(source,s) for s in (
        'std::string Receipt(', 'std::string SurfaceLightmap(', 'std::string PlaneJson(',
        'std::string Shader(', 'std::string Pipeline(')))
    tile=(ROOT/'src/common/rendering/hwrenderer/data/hw_lightmaptile.h').read_text()
    (directory/'mesh_witness_to_uv.inc').write_text(block(tile,'FVector2 ToUV(const FVector3& vert, float textureSize) const'))
    return compile_fixture(HERE/'sdvk161_mesh_material_witness_fixture.cpp',output_dir=directory,
        includes=[directory,ROOT/'src/rendering/hwrenderer/diagnostics',ROOT/'src/common/rendering/vulkan'])


class MeshMaterialWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk161-mesh-witness-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def fixture(self, *, wrong=False, cell='a-wall', executable=None, mode='color'):
        raw=full_raw();frame=8
        value=surface(raw,'S161NO',frame)
        if cell=='a-ceiling':
            value=ordinary_a_ceiling(raw)['data']
            value.update(first_index=600,batch_first_index=600)
        elif cell=='b-wall':
            frame=56
            value=copy.deepcopy(surface(raw,'SDVW',frame))
            value.update(producer='levelmesh-surface-range',indexed=True,draw_count=6,index_count=6)
            value['context']=copy.deepcopy(surface(raw,'S161PN',frame)['context'])
            value['key']['shader']['UseLevelMesh']=1
            value['probe']['authored_scope']='not stored in mesh; no authored target claim'
            value['owner'].update(side=10,type_index=10,sector=1,portal_group=2)
            value.update(first_index=600,batch_first_index=600)
            independent_receiver_tile(raw,value,frame)
            raw['records'].append(dict(kind='surface',frame=frame,count=1,data=value))
        # A second uniform selects an independently coherent default material.
        # Its owner, current receipt and geometric span stay the same.
        bad=copy.deepcopy(value['material'])
        if wrong:
            bad,_=material('SDVFL')
            bad['resource']['index']=4096
        r=resource(raw,frame);owner=value['owner'];allocation=value['lightmap']['receipt']
        numbers=[value['batch_first_index'],owner['type'],owner['side'],owner['sector'],owner['portal_group'],
                 value['lightmap']['tile'],r['levelmesh']['owner'],value['mesh_epoch'],value['lightmap']['epoch'],
                 allocation['owner'],allocation['incarnation'],allocation['slot'],
                 value['texture_index'],bad['resource']['index']]
        lines=[' '.join(map(str,numbers)),json.dumps(value['context'])]
        for bound in (value['material'],bad):lines += [bound['name'],json.dumps(bound)]
        lines.append(json.dumps(value['probe']))
        with tempfile.TemporaryDirectory(prefix='sdvk161-mesh-input-') as d:
            path=Path(d)/'input.txt';path.write_text('\n'.join(lines)+'\n')
            result=subprocess.run([str(executable or self.current),str(path),mode],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        emitted=json.loads(result.stdout)
        # Replace only the original row/parent for this one actually submitted
        # range. Correct neighboring obligations in the independent full packet
        # remain present; no material/ownership validator is mocked.
        raw['records']=[row for row in raw['records'] if row.get('data') is not value and not
                       (row.get('kind')=='pipeline' and row.get('frame')==frame and
                        row['data'].get('producer')=='levelmesh-indexed-range' and
                        row['data'].get('first_index')==value['batch_first_index'] and
                        row['data'].get('context')==value['context'])]
        for row in emitted:
            row.update(frame=frame,count=1)
            raw['records'].append(row)
        return raw,emitted

    def test_actual_observer_exposes_wrong_default_material_next_to_correct_owner(self):
        raw,emitted=self.fixture(wrong=True)
        children=[row['data'] for row in emitted if row['kind']=='surface']
        self.assertEqual([v['material']['name'] for v in children],['S161NO','SDVFL'])
        self.assertEqual([(v['first_index'],v['index_count']) for v in children],[(24,3),(27,3)])
        self.assertTrue(all(v['geometry']['current_uv_valid'] and v['geometry']['triangle_mapping_valid']
                            and v['lightmap']['valid'] for v in children))
        for v in children:gate.validate_surface_record(v)
        with self.assertRaisesRegex(EvidenceError,'ordinary wall owner/material'):
            gate.validate_transition_records(raw,stdout(),native_recipe())

    def test_historical_filter_with_current_owner_metadata_suppresses_wrong_binding_and_admits_neighbor(self):
        raw,emitted=self.fixture(wrong=True,executable=self.original)
        children=[row['data'] for row in emitted if row['kind']=='surface']
        self.assertEqual([v['material']['name'] for v in children],['S161NO'])
        self.assertEqual(children[0]['index_count'],3)
        self.assertEqual(gate.validate_transition_records(raw,stdout(),native_recipe())['status'],'PASS')

    def test_all_color_children_and_ordinary_a_b_owner_cells_are_admitted(self):
        for cell in ('a-wall','a-ceiling','b-wall'):
            with self.subTest(cell=cell):
                raw,emitted=self.fixture(cell=cell)
                children=[r for r in emitted if r['kind']=='surface']
                self.assertEqual(len(children),2)
                self.assertEqual(sum(r['data']['index_count'] for r in children),6)
                self.assertEqual(gate.validate_transition_records(raw,stdout(),native_recipe())['status'],'PASS')

    def test_existing_state_frame_color_and_depth_eligibility_guards_remain(self):
        for mode in ('off','unselected','ordinary','depth','masked','color-mask'):
            with self.subTest(mode=mode):
                _,rows=self.fixture(mode=mode)
                self.assertFalse(any(r['kind']=='surface' for r in rows))
                self.assertEqual(len(rows),0 if mode in ('off','unselected') else 1)


if __name__=='__main__':unittest.main()
