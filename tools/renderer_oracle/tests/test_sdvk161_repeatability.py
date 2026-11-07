"""Synthetic complete SDVK161 packet clocks through the actual comparator.

Raw receipts/PNGs are synthetic; native process receipt admission is the only
service double. Production structural and full161 semantic validation, projection,
comparison and exact RGB decode execute unchanged. No renderer is launched.
"""
import copy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from tools.renderer_oracle import common, prepare, run, sdvk161_special_surfaces as gate
from tools.renderer_oracle.tests.test_evidence import png
from tools.renderer_oracle.tests.test_validation import observation, context, recount
from tools.renderer_oracle.tests.test_sdvk161_special_surfaces import full_raw, stdout

SCENE='special-surface-lifecycle'
CLOCK='ordinary_engine_clock_with_fixed_presented-view_input_schedule'


def recipe():
    return next(s for s in prepare.load_catalog()['scenes'] if s['id']==SCENE)


def envelope(start=100, pace=1, fraction=.125):
    native=recipe()['native'];result=observation();template=copy.deepcopy(result['records'][-1]['data'])
    result.update(requested_frames=96,observed_frames=96,warmup_frames=32,records=full_raw()['records'])
    def clocks(value, frame):
        if isinstance(value,list):
            for item in value:clocks(item,frame)
        elif isinstance(value,dict):
            if value.get('available') is True and 'root_type' in value:
                defaults=context();defaults.update(value);value.clear();value.update(defaults)
                value.update(gametic=start+((frame-1)%24+1)*pace,fraction=fraction)
                value['mirrored']=value['line_mirror']!=value['plane_mirror']
            for item in list(value.values()):clocks(item,frame)
    for frame in range(1,97):
        rows=[r for r in result['records'] if r['frame']==frame]
        if not any(r['kind']=='context' for r in rows):
            camera=native['map_cameras']['SDV161A' if frame<=48 else 'SDV161B']
            c=context();c.update(map='SDV161A' if frame<=48 else 'SDV161B',
                position=camera['position'],angles=[270-camera['yaw'],0,0],portal_group=0 if frame<=48 else 2)
            extra={'kind':'context','frame':frame,'count':1,'data':{'context':c}}
            result['records'].append(extra);rows.append(extra)
        for r in rows:
            value=r['data']
            if r['kind']=='frame':
                saved=copy.deepcopy(value);value.update(copy.deepcopy(template));value.update(saved)
                value.update(gametic=start+((frame-1)%24+1)*pace,width=640,height=480)
                value['camera']['fraction']=fraction
                value['settings']=gate.settings_for_frame(native,frame)
            if r['kind']=='resource':value.update(descriptor_capacity=1024,descriptor_current=1,
                descriptor_high_water=1,descriptor_dynamic_start=259,texture_epoch=1,async_upload_epoch=1)
            clocks(value,frame)
    result['limits']['retained_bytes']=sum(len(common.canonical(r['data']))+len(r['kind']) for r in result['records'])
    return recount(result)


class SpecialSurfaceRepeatabilityTests(unittest.TestCase):
    def compare(self,left,right,*,scene=SCENE,clock=CLOCK,changed_image=False):
        for data in (left,right):
            run.validate.observation(data,required_kinds=['context','resource'],expected_frames=96)
            owners=tuple(next(r['data']['levelmesh']['owner'] for r in data['records'] if r['kind']=='resource' and r['frame']==frame) for frame in (1,25,49,73))
            gate.validate_transition_records(data,stdout(owners),recipe()['native'])
        with tempfile.TemporaryDirectory(prefix='sdvk161-compare-') as d:
            roots=[Path(d)/name for name in ('left','right')]
            for i,root in enumerate(roots):
                root.mkdir();(root/'native.png').write_bytes(png(bytes([int(changed_image and i)])+bytes(5)))
                common.write_json(root/'run.json',{'synthetic':True});common.write_json(root/'request.json',{'cwd':str(root)})
            receipt={'scene':scene,'mode':'state','reproduction':{'clock':clock,'image_policy':{'metric':'exact-rgb8'}},
                     'build':left['build'],'executable':{'sha256':'a'*64},'loaded_packages':[]}
            with mock.patch.object(run,'validate_run',side_effect=[(roots[0],receipt,left,{}),(roots[1],receipt,right,{})]):
                return run.compare_runs(*roots)

    def test_complete_161_only_incidental_clock_labels_differ_before_fix(self):
        left=envelope();right=envelope(300,4,.875)
        # This is the original current predicate, not a changed global projector.
        old_static=SCENE=='lightmap-retained-transition' and recipe()['native']['clock']['state']==CLOCK
        self.assertFalse(old_static)
        a=run.validate.state_projection(left,static_scene=old_static)
        b=run.validate.state_projection(right,static_scene=old_static)
        changes=run.differences(a,b,maximum=100000)
        self.assertTrue(changes)
        # Nested portal parent identities hash the unnormalized parent context,
        # so their pre-fix digests also differ solely because of those labels.
        raw_changes=run.differences(left,right,maximum=100000)
        self.assertTrue(raw_changes)
        self.assertTrue(all(c['path'].endswith(('/gametic','/fraction')) for c in raw_changes))
        self.assertTrue(all(c['path'].endswith(('/gametic','/fraction','/parent_context_sha256')) for c in changes))
        self.assertTrue(any(c['path'].endswith('/parent_context_sha256') for c in changes))
        self.assertEqual(run.validate.state_projection(left,static_scene=True),
                         run.validate.state_projection(right,static_scene=True))
        raw=copy.deepcopy((left,right));result=self.compare(left,right)
        self.assertEqual(result['status'],'PASS');self.assertTrue(result['state_equal'])
        self.assertIn('SDVK-161 fixed-presented-view schedule',result['normalization'])
        self.assertEqual((left,right),raw)

    def test_actual_mesh_instance_labels_are_bijective_and_local_epochs_remain_exact(self):
        left=envelope();right=envelope(300,4,.875)
        labels={70:900,71:903,72:908,73:912}
        for record in right['records']:
            value=record['data']
            if record['kind']=='resource':value['levelmesh']['owner']=labels[value['levelmesh']['owner']]
            elif record['kind']=='surface':value['mesh_owner']=labels[value['mesh_owner']]
        original=copy.deepcopy((left,right))
        old_left=run.validate.state_projection(left,static_scene=True)
        old_right=run.validate.state_projection(right,static_scene=True)
        self.assertNotEqual(old_left,old_right)
        changes=run.differences(old_left,old_right,maximum=100000)
        self.assertTrue(all(item['path'].endswith(('/levelmesh/owner','/mesh_owner')) for item in changes))
        result=self.compare(left,right)
        self.assertEqual(result['status'],'PASS');self.assertTrue(result['state_equal'])
        self.assertIn('actual mesh-instance labels normalized bijectively',result['normalization'])
        self.assertEqual((left,right),original)
        self.assertEqual(run._sdvk161_repeatability_projection(old_right,'lights-zero'),old_right)
        # The projection must retain resource/draw alias relationships, rather
        # than deleting the instance fields once admission has checked them.
        projected=run._sdvk161_repeatability_projection(old_right,SCENE)
        stale=copy.deepcopy(old_right)
        next(record['data'] for record in stale if record['kind']=='surface' and record['frame']==32)['mesh_owner']=900
        stale_projected=run._sdvk161_repeatability_projection(stale,SCENE)
        self.assertNotEqual(projected,stale_projected)
        self.assertTrue(all(item['path'].endswith('/mesh_owner')
                            for item in run.differences(projected,stale_projected)))

        # Coherent local resource-epoch differences remain individually valid
        # instance states, and must still fail the independent state comparison.
        for record in right['records']:
            if not 25<=record['frame']<=48:continue
            if record['kind']=='resource':record['data']['levelmesh']['epoch']+=1
            elif record['kind']=='surface':record['data']['mesh_epoch']+=1
        result=self.compare(left,right)
        self.assertEqual(result['status'],'FAIL');self.assertFalse(result['state_equal'])
        self.assertTrue(all(item['path'].endswith(('/levelmesh/epoch','/mesh_epoch')) for item in result['first_state_differences']))
        self.assertTrue(result['image']['passed'])

    def test_wrong_clock_and_ordinary_dynamic_scene_do_not_get_161_policy(self):
        left=envelope();right=envelope(300,4,.875)
        for scene,clock in ((SCENE,'ordinary_engine_clock'),(SCENE,CLOCK+'-wrong'),
                            ('lights-zero',CLOCK),('lights-zero','ordinary_engine_clock')):
            with self.subTest(scene=scene,clock=clock):
                result=self.compare(left,right,scene=scene,clock=clock)
                self.assertEqual(result['status'],'FAIL');self.assertFalse(result['state_equal'])
                self.assertNotIn('SDVK-161 fixed-presented-view schedule',result['normalization'])

    def test_semantic_and_rgb_differences_remain_exact(self):
        errors={
            'owner':'SDVK-161 tile belongs to another side/sector/control namespace',
            'receipt':'SDVK-161 submitted surface uses a stale page/allocation incarnation',
            'sampler':'SDVK-161 actual per-layer sampler differs from semantic/reset policy',
            'uv':'Submitted receiver UVs do not match its current atlas allocation',
            'portal':'SDVK-161 material receiver inherited a portal destination/sky-only identity',
            'camera':'SDVK-161 retained frame camera position differs from its authored view',
            'mesh-instance':'SDVK-161 submitted surface references another LevelMesh instance/local epoch',
            'mesh-epoch':'SDVK-161 submitted surface references another LevelMesh instance/local epoch',
        }
        paths={
            'completion':['/17/data/lightmap_state/frame_tile_completions',
                          '/17/data/lightmap_state/frame_tile_updates'],
            'phase':['/17/data/lightmap_state/frame_tile_completions',
                     '/17/data/lightmap_state/frame_tile_updates',
                     '/19/data/lightmap_state/frame_tile_completions',
                     '/19/data/lightmap_state/frame_tile_updates'],
            'range-count':['/196/data/draw_count','/196/data/index_count'],
        }
        for change in (*paths,*errors):
            left=envelope();right=envelope(300,4,.875)
            if change in ('completion','phase'):
                resources={r['frame']:r['data'] for r in right['records'] if r['kind']=='resource'}
                if change=='completion':resources[9]['lightmap_state'].update(frame_tile_updates=2,frame_tile_completions=2)
                else:resources[9]['lightmap_state'],resources[10]['lightmap_state']=resources[10]['lightmap_state'],resources[9]['lightmap_state']
            else:
                value=next(r['data'] for r in right['records'] if r['kind']=='surface' and r['frame']==8 and r['data'].get('material',{}).get('name')=='S161PH')
                if change=='range-count':value['index_count']=value['draw_count']=3
                if change=='owner':value['owner']['control_sector']=4
                if change=='receipt':value['lightmap']['receipt']['incarnation']+=1
                if change=='sampler':value['material']['layers'][0]['sampler']['min_filter']=1
                if change=='uv':value['geometry']['current_uv_valid']=False
                if change=='portal':value['geometry']['portal_index']=1
                if change=='mesh-instance':value['mesh_owner']+=1000
                if change=='mesh-epoch':value['mesh_epoch']+=1
                if change=='camera':next(r['data'] for r in right['records'] if r['kind']=='frame' and r['frame']==56)['camera']['position'][0]+=1
            with self.subTest(change=change):
                if change in errors:
                    with self.assertRaisesRegex(common.EvidenceError,'^'+errors[change]+'$'):
                        self.compare(left,right)
                else:
                    result=self.compare(left,right)
                    self.assertEqual(result['status'],'FAIL');self.assertFalse(result['state_equal'])
                    self.assertEqual([item['path'] for item in result['first_state_differences']],paths[change])
                    self.assertTrue(result['image']['passed'])
        result=self.compare(envelope(),envelope(300,4,.875),changed_image=True)
        self.assertEqual(result['status'],'FAIL');self.assertTrue(result['state_equal'])
        self.assertFalse(result['image']['passed']);self.assertEqual(result['image']['changed_pixels'],1)


if __name__=='__main__':unittest.main()
