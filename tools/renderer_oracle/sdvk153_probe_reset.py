#!/usr/bin/env python3
"""SDVK-153 live sampler-reset qualification; hosted isolated llvmpipe only.

Uses existing emitted-draw diagnostics plus an explicit outcome-blind native
fixture-input scheduler. The scheduler queues ordinary console CVAR commands
after fixed main-view ordinals and never reads acceptance state. CPU validation
requires raw within-process tokens to remain unchanged across scheduled material
resets. No per-texel image readback or physical performance claim.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess

from tools.renderer_oracle.common import require, pin, write_json

WARMUP=32
FRAMES=48
DEADLINE=300
SCENES=('probe-sampler-reset-control','probe-sampler-reset')
SCHEDULE=[
    {'after_main_views':40,'cvar':'gl_texture_filter','value':4},
    {'after_main_views':48,'cvar':'gl_texture_filter_anisotropic','value':2},
    {'after_main_views':56,'cvar':'gl_texture_filter','value':0},
    {'after_main_views':64,'cvar':'gl_texture_filter_anisotropic','value':1},
]


def validate_recipe(scene: dict) -> None:
    native=scene['native']
    require(scene['id'] in SCENES and native.get('map')=='SDV153', 'Unknown sampler-reset scene/map')
    expected=[] if scene['id']==SCENES[0] else SCHEDULE
    require(native.get('sampler_reset_schedule')==expected, 'Sampler-reset schedule differs from preregistration')
    require(native.get('recommended_warmup_frames')==WARMUP, 'Sampler-reset warmup differs')
    require(native['settings'].get('gl_texture_filter')==0 and native['settings'].get('gl_texture_filter_anisotropic')==1,
            'Sampler-reset baseline settings differ')



def authored_members(scene: dict, author) -> tuple[dict[str,bytes],dict]:
    validate_recipe(scene)
    native=scene['native']; members=author._base_members()
    author._material_layers(members)
    members['GLDEFS']=(author._pbr('SDVW')+author._pbr('SDVFL','flat')+author._pbr('SDVOA0',kind='sprite')).encode()
    camera=native['camera']['position'];yaw=math.radians(native['camera']['yaw'])
    player=[camera[0]-round(48*math.cos(yaw)),camera[1]-round(48*math.sin(yaw))]
    model=author._Map(floor=32,ceiling=160,sky=False)
    model.thing(1,player[0],player[1],tid=2001)
    model.thing(32200,camera[0],camera[1],camera[2]-32,tid=2002)
    model.boundary([(-256,-192),(-256,192),(256,192),(256,-192)],['SDVW']*4)
    for x,y,z in ((-80,-72,88),(112,72,120)):model.thing(9892,x,y,z)
    for index,(x,y) in enumerate(((-64,-64),(96,64))):model.thing(32203,x,y,0,tid=5200+index)
    model.thing(9800,0,0,64,tid=3000,arg0=160,arg1=160,arg2=160,arg3=96)
    members['maps/SDV153.wad']=author.pf_indexed.wad([('SDV153',b''),('TEXTMAP',model.text().encode()),('ENDMAP',b'')])
    members['MAPINFO']=('map SDV153 "SDVK probe sampler reset" { nointermission }\n'
        'DoomEdNums { 32200 = SDVKFixedCamera\n 32203 = SDVKMarker\n }\n').encode()
    return members, {'geometry':'authored_udmf','textures':'generated_rgba_only','native_executed':False,
        'camera_actor_tid':2002,'camera_position_world':camera,'player_start_world':player,'monsters':0,
        'counts':{kind:len(rows) for kind,rows in model.records.items()},
        'boundary_signed_areas':model.polygon_areas,
        'sampler_reset_schedule':copy.deepcopy(native['sampler_reset_schedule']),
        'identity_scope':'actual uniform pair emission; no probe-map texel readback'}


def settings_for_frame(native: dict, frame: int) -> dict:
    result=dict(native['settings'])
    for phase in native['sampler_reset_schedule']:
        if phase['after_main_views'] < WARMUP+frame:result[phase['cvar']]=phase['value']
    return result


def validate_reset_records(raw: dict, stdout: str, native: dict) -> dict:
    require(raw.get('observed_frames')==FRAMES, 'Sampler-reset capture frame budget differs')
    schedule=native['sampler_reset_schedule']
    expected=[f"SDVK153_SETTING {s['cvar']}={s['value']} after_main_views={s['after_main_views']}" for s in schedule]
    actual=[line for line in stdout.splitlines() if line.startswith('SDVK153_SETTING')]
    require(actual==expected, 'Sampler-reset driver order/count/readback marker differs')
    identities={}; sampler_policies={}; material_phases=[]
    for frame in range(1,FRAMES+1):
        records=[r for r in raw['records'] if r['frame']==frame]
        frames=[r['data'] for r in records if r['kind']=='frame']
        require(len(frames)==1,'Sampler-reset missing/duplicate frame state')
        phase=settings_for_frame(native,frame)
        for key in ('gl_texture_filter','gl_texture_filter_anisotropic'):
            require(frames[0]['settings'].get(key)==phase[key], 'Sampler-reset actual frame setting differs')
        draws=[r['data'] for r in records if r['kind']=='probe' and r['data'].get('material')=='SDVOA0'
               and r['data'].get('context',{}).get('type')=='main'
               and r['data'].get('actor_selection',{}).get('available') is True]
        require({d.get('authored_index') for d in draws}=={0,1}, 'Sampler-reset did not emit both live authored probes')
        for draw in draws:
            ordinal=draw['authored_index']; token=draw.get('resource',{})
            require(draw.get('fallback') is False and token.get('available') is True and token.get('span')==2
                    and token.get('index',0)>0 and token['index']==draw.get('runtime_irradiance_index'),
                    'Sampler-reset missing live complete pair identity')
            identity=(token['index'],token['generation'],token['epoch'],token['span'],draw['probe_epoch'])
            if ordinal not in identities:identities[ordinal]=identity
            require(identity==identities[ordinal], 'Sampler-reset changed retained pair base/generation/epoch')
            policies=(draw.get('irradiance_sampler'),draw.get('prefilter_sampler'))
            require(all(p and p.get('available') is True for p in policies),'Probe sampler policy unavailable')
            if ordinal not in sampler_policies:sampler_policies[ordinal]=policies
            require(policies==sampler_policies[ordinal], 'Dedicated probe sampler policy changed')
        # This is actual selected material policy, not only the fixture's CVar log.
        walls=[r['data'] for r in records if r['kind']=='material' and r['data'].get('name')=='SDVW'
               and r['data'].get('context',{}).get('type')=='main']
        albedo=[l['sampler'] for d in walls for l in d['layers'] if l.get('semantic')=='albedo']
        require(albedo and all(p.get('available') is True for p in albedo),'Material sampler phase not observed')
        expected_filter=1 if phase['gl_texture_filter']==4 else 0
        require(all(p.get('min_filter')==expected_filter and p.get('mag_filter')==expected_filter for p in albedo),
                'Material filter change was suppressed or mistimed')
        if phase['gl_texture_filter']==4 and phase['gl_texture_filter_anisotropic']==2:
            require(all(p.get('anisotropy') is True and p.get('max_anisotropy')==2 for p in albedo),
                    'Material anisotropy change was suppressed')
        material_phases.append(expected_filter)
    require(identities[0][0]!=identities[1][0], 'Distinct authored probes collapsed to one pair')
    return {'status':'PASS','frames':FRAMES,'settings_resets':len(schedule),'unchanged_pair_tokens':identities,
            'material_filter_phases':sorted(set(material_phases)),
            'scope':'actual immediate actor pair identities through live sampler resets; not per-texel readback',
            'physical_gpu_qualified':False}


def qualify(args) -> dict:
    from tools.renderer_oracle import native_ci, prepare, run, images, sdvk010_sun_native
    out=run.fresh_directory(args.out)
    result={'schema':'sdvk153-live-sampler-qualification/v1','status':'FAIL','steps':[],
            'physical_stop_active':True,'physical_gpu_qualified':False,'performance_accepted':False,
            'historical_physical_root_cause':'UNDETERMINED','automatic_retries':0}
    try:
        require(re.fullmatch(r'[0-9a-f]{40}',args.expected_commit) is not None,'Expected exact build commit required')
        require(not any(k.startswith('CFX_') and v for k,v in os.environ.items()),'No CFX experiments in this gate')
        result['software_host']=sdvk010_sun_native.software_host_guard()
        result['preflight']=native_ci.preflight(args,out)
        prepared=out/'prepared';manifest=prepare.prepare(prepared,list(SCENES))
        captures=[]
        for name,scene_id in (('control',SCENES[0]),('reset-1',SCENES[1]),('reset-2',SCENES[1])):
            target=out/name
            options=argparse.Namespace(exe=args.exe,iwad=args.iwad,prepared=prepared,out=target,scene=scene_id,
                mode='state',frames=FRAMES,warmup=WARMUP,timeout=DEADLINE,gpu=False,include_stress=True,
                image_policy='exact',extent=None,collision_snapshot=False,publication_witness=False,
                expected_commit=args.expected_commit,require_clean=True)
            step=native_ci.attempt(out,name,lambda a=options:run.capture(a),('COLLECTED',))
            result['steps'].append(step)
            require(step['status']=='PASS','Native sampler-reset attempt failed; no retry/dependent run')
            captures.append(target)
        comparison=run.compare_runs(captures[1],captures[2]);write_json(out/'repeatability.json',comparison)
        require(comparison['status']=='PASS','Sampler-reset exact state/RGB repeatability failed')
        control=images.compare(captures[0]/'native.png',captures[1]/'native.png',
                               run.image_policy(manifest['scenes'][0],'exact'))
        write_json(out/'control-image.json',control)
        require(control['passed'] and control['changed_pixels']==0,'Final RGB differs from unchanged-setting control')
        result.update(status='PASS',captures=[pin(p/'run.json',relative_to=out) for p in captures],
                      comparison=pin(out/'repeatability.json',relative_to=out),
                      control_image=pin(out/'control-image.json',relative_to=out))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:result['error']=str(error)
    finally:write_json(out/'qualification.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('exe','iwad','iwad-license','out'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-commit',required=True)
    result=qualify(parser.parse_args(argv));print(json.dumps({k:result.get(k) for k in ('schema','status','error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
