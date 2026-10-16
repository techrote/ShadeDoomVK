"""Adversarial native-gate controls; CPU only, no renderer or Vulkan device.

Synthetic native rows are independently authored. The opt-in native fixture
driver is source-audited independently from the acceptance records it drives.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.renderer_oracle import prepare, sdvk153_probe_reset as gate
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests.test_corpus import scene_named, unpack_wad, parse_udmf

ROOT=Path(__file__).resolve().parents[3]


def sample(reset=True):
    native=copy.deepcopy(scene_named('probe-sampler-reset' if reset else 'probe-sampler-reset-control')['native'])
    records=[]
    # These explicit retained-frame phase boundaries do not call the gate's
    # expectation helper: reset after rendered views 40/48/56/64, warmup 32.
    for frame in range(1,49):
        filtering=4 if reset and 9<=frame<=24 else 0
        anisotropy=2 if reset and 17<=frame<=32 else 1
        records.append({'kind':'frame','frame':frame,'count':1,'data':{'settings':{
            'gl_texture_filter':filtering,'gl_texture_filter_anisotropic':anisotropy}}})
        for ordinal,base in ((0,259),(1,261)):
            records.append({'kind':'probe','frame':frame,'count':1,'data':{
                'material':'SDVOA0','context':{'type':'main'},'actor_selection':{'available':True},
                'authored_index':ordinal,'fallback':False,'runtime_irradiance_index':base,
                'probe_epoch':3,'resource':{'available':True,'index':base,'generation':1,'epoch':1,'span':2},
                'irradiance_sampler':{'available':True,'min_filter':1,'mag_filter':1},
                'prefilter_sampler':{'available':True,'min_filter':1,'mag_filter':1}}})
        records.append({'kind':'material','frame':frame,'count':1,'data':{
            'name':'SDVW','context':{'type':'main'},'layers':[{'semantic':'albedo','sampler':{
                'available':True,'min_filter':int(filtering==4),'mag_filter':int(filtering==4),
                'anisotropy':filtering==4,'max_anisotropy':anisotropy if filtering==4 else 1}}]}})
    stdout=('SDVK153_SETTING gl_texture_filter=4 after_main_views=40\n'
            'SDVK153_SETTING gl_texture_filter_anisotropic=2 after_main_views=48\n'
            'SDVK153_SETTING gl_texture_filter=0 after_main_views=56\n'
            'SDVK153_SETTING gl_texture_filter_anisotropic=1 after_main_views=64\n') if reset else ''
    return {'observed_frames':48,'records':records},stdout,native


def probe(raw,frame=9):
    return next(r['data'] for r in raw['records'] if r['kind']=='probe' and r['frame']==frame)


class ProbeSamplerResetTests(unittest.TestCase):
    def test_independent_frame_phases_and_stable_tokens_pass(self):
        for reset in (False,True):
            with self.subTest(reset=reset):
                raw,stdout,native=sample(reset)
                result=gate.validate_reset_records(raw,stdout,native)
                self.assertEqual(result['status'],'PASS')
                self.assertEqual(result['frames'],48)
                self.assertEqual(result['settings_resets'],4 if reset else 0)
                self.assertEqual(result['unchanged_pair_tokens'],{0:(259,1,1,2,3),1:(261,1,1,2,3)})
                self.assertFalse(result['physical_gpu_qualified'])

    def test_no_raw_within_process_identity_normalization(self):
        for component in ('index','generation','epoch','span','probe_epoch','fallback'):
            raw,stdout,native=sample()
            row=probe(raw)
            if component=='probe_epoch':row[component]+=1
            elif component=='fallback':row[component]=True
            elif component=='index':
                row['resource']['index']=411
                row['runtime_irradiance_index']=411
            else:row['resource'][component]+=1
            reason='missing live complete pair' if component in ('span','fallback') else 'changed retained pair'
            with self.subTest(component=component),self.assertRaisesRegex(EvidenceError,reason):
                gate.validate_reset_records(raw,stdout,native)

    def test_missing_ordinal_frame_or_dedicated_sampler_change_rejects(self):
        for mutate,reason in (
            (lambda raw:raw['records'].remove(next(r for r in raw['records'] if r['kind']=='probe')),'both live authored probes'),
            (lambda raw:raw['records'].remove(next(r for r in raw['records'] if r['kind']=='frame')),'missing/duplicate frame'),
            (lambda raw:probe(raw)['irradiance_sampler'].update(min_filter=0),'Dedicated probe sampler'),
            (lambda raw:probe(raw)['resource'].update(available=False),'missing live complete pair'),
            (lambda raw:raw.update(observed_frames=47),'frame budget'),
        ):
            raw,stdout,native=sample();mutate(raw)
            with self.subTest(reason=reason),self.assertRaisesRegex(EvidenceError,reason):
                gate.validate_reset_records(raw,stdout,native)

    def test_setting_change_must_reach_actual_material_draw(self):
        for mutation,reason in (
            (lambda r:r['data']['layers'][0]['sampler'].update(min_filter=0,mag_filter=0),'filter change was suppressed'),
            (lambda r:r['data']['layers'][0]['sampler'].update(anisotropy=False),'anisotropy change was suppressed'),
        ):
            raw,stdout,native=sample()
            mutation(next(r for r in raw['records'] if r['kind']=='material' and r['frame']==17))
            with self.subTest(reason=reason),self.assertRaisesRegex(EvidenceError,reason):
                gate.validate_reset_records(raw,stdout,native)
        raw,stdout,native=sample()
        next(r for r in raw['records'] if r['kind']=='frame' and r['frame']==9)['data']['settings']['gl_texture_filter']=0
        with self.assertRaisesRegex(EvidenceError,'actual frame setting differs'):
            gate.validate_reset_records(raw,stdout,native)

    def test_marker_and_phase_schedule_are_exact_not_completion_driven(self):
        raw,stdout,native=sample()
        for altered in ('',stdout+stdout,stdout.replace('40','41'),'\n'.join(reversed(stdout.splitlines()))):
            with self.subTest(log=altered),self.assertRaisesRegex(EvidenceError,'driver order/count'):
                gate.validate_reset_records(raw,altered,native)
        scene=scene_named('probe-sampler-reset')
        for change in (lambda s:s['native']['sampler_reset_schedule'][0].update(after_main_views=2),
                       lambda s:s['native'].update(recommended_warmup_frames=0)):
            changed=copy.deepcopy(scene);change(changed)
            with self.assertRaises(EvidenceError):gate.validate_recipe(changed)

    def test_geometry_probe_material_bytes_equal_between_reset_and_control(self):
        pairs=[prepare.authored_members(scene_named(name)) for name in gate.SCENES]
        a,ma=pairs[0];b,mb=pairs[1]
        self.assertEqual(set(a),set(b))
        self.assertEqual([key for key in a if a[key]!=b[key]],[])
        self.assertNotIn('CVARINFO',a)
        self.assertNotIn(b'SDVKProbeSamplerReset',a['ZSCRIPT'])
        rows=parse_udmf(unpack_wad(a['maps/SDV153.wad'])['TEXTMAP'])
        self.assertEqual([[t['x'],t['y'],t['height']] for t in rows['thing'] if t['type']==9892],
                         [[-80,-72,88],[112,72,120]])
        self.assertEqual([t['id'] for t in rows['thing'] if t['type']==32203],[5200,5201])
        self.assertEqual(ma['counts'],{key:len(value) for key,value in rows.items()})
        self.assertEqual(ma['boundary_signed_areas'],[-196608.0])
        self.assertEqual(ma['counts'],mb['counts'])
        self.assertIn(b'material sprite SDVOA0',a['GLDEFS'])

    def test_native_driver_uses_fixed_presented_frame_schedule_and_console_path(self):
        import re
        source=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp').read_text()
        table=re.search(r'constexpr SamplerResetPhase SamplerResetPhases\[\] = \{(.*?)\};',source,re.S)
        self.assertIsNotNone(table)
        phases=[{'after_main_views':int(frame),'cvar':cvar,'value':int(value)}
                for frame,cvar,value in re.findall(r'\{(\d+), "([a-z0-9_]+)", "([0-9]+)"\}',table.group(1))]
        self.assertEqual(phases,gate.SCHEDULE)
        body=source[source.index('void DriveSamplerResetInput'):source.index('// The publication witness')]
        self.assertIn('observer.Seen != phase.AfterMainViews',body)
        self.assertIn('AddCommandString(command.c_str())',body)
        self.assertIn('SDVK153_SETTING %s=%s after_main_views=%u',body)
        for forbidden in ('ProbeBuilderEvents','GetProbeSetRevision','PassPublished','Irradiancemaps','Prefiltermaps'):
            self.assertNotIn(forbidden,body)
        self.assertIn('Args->CheckParm("-sdvk153samplerresetdriver")',source)
        frame_presented=source[source.index('void FramePresented()'):source.index('void SceneBegin(')]
        self.assertLess(frame_presented.index('WitnessObserverFrame("observer-frame-presented"'),
                        frame_presented.index('DriveSamplerResetInput(observer)'))

        run_source=(ROOT/'tools/renderer_oracle/run.py').read_text()
        self.assertIn('if native.get("sampler_reset_schedule"):',run_source)
        self.assertIn('argv.append("-sdvk153samplerresetdriver")',run_source)

    def test_retained_zscript_cvar_failure_is_classified_not_gpu_fault(self):
        failure=json.loads((ROOT/'tools/renderer_oracle/tests/fixtures/sdvk153-zscript-cvar-failure.json').read_text())
        self.assertEqual(failure['classification'],'INVALID_FIXTURE_INPUT_DRIVER_NOT_GPU_FAULT')
        self.assertEqual(failure['run'],38963610141)
        self.assertEqual(failure['job'],117185471214)
        self.assertEqual(failure['artifact'],12074328517)
        self.assertEqual(failure['stderr_bytes'],0)
        self.assertIn("Attempt to change CVAR 'gl_texture_filter' outside of menu code",failure['native_failure'])
        self.assertEqual(failure['completed_before_failure']['control'],'PASS')
        self.assertEqual(failure['completed_before_failure']['sdvk150'],'PASS')


    def test_unapproved_host_rejected_before_any_device_preflight(self):
        from tools.renderer_oracle import native_ci,sdvk010_sun_native
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(out=Path(directory)/'run',expected_commit='a'*40)
            with mock.patch.object(sdvk010_sun_native,'software_host_guard',side_effect=EvidenceError('host held')),\
                 mock.patch.object(native_ci,'preflight') as preflight:
                result=gate.qualify(args)
                self.assertEqual(result['status'],'FAIL')
                self.assertEqual(result['error'],'host held')
                preflight.assert_not_called()


if __name__=='__main__':unittest.main()
