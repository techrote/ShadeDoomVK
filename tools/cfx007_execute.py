"""Execute ONE preregistered CFX-007 experiment with recovery and finite ledger.
No loops, driver/policy changes or automatic reboot. Large evidence stays local.
"""
import argparse,datetime as dt,hashlib,json,pathlib,shutil,subprocess,sys
from cfx_capture import check_cfx007_lane,check_cfx008_lane,digest
from cfx007_health import collect
ROOT=pathlib.Path(__file__).resolve().parents[1]
CACHE=pathlib.Path.home()/"AppData/Local/zdoom/cache"


def save(p,data):
    temp=p.with_suffix(p.suffix+".tmp")
    temp.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    temp.replace(p)


def stop(lane,state,reasons,protocol='CFX-007'):
    state["status"]="STOPPED";state["stop_reasons"]=reasons
    save(lane/"state.json",state)
    (lane/"STOP-LAUNCHES.txt").write_text(protocol+" stopped: "+"; ".join(reasons)+"\n",encoding="utf-8")


def main(protocol='CFX-007'):
    cfx008=protocol=='CFX-008'
    issue,max_launches,max_losses=(99,2,1) if cfx008 else (97,16,6)
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',type=pathlib.Path,required=True);ap.add_argument('--launch',action='store_true')
    a=ap.parse_args();pp=a.plan.resolve();attempt=pp.parent;lane=attempt.parent
    plan=json.loads(pp.read_text(encoding='utf-8'));state=json.loads((lane/'state.json').read_text(encoding='utf-8'))
    opening=json.loads((lane/'lane-opening.json').read_text(encoding='utf-8'))
    if state.get('pending_attempt') or state['launches']>=max_launches or state['loss_episodes']>=max_losses:ap.error('pending attempt or finite budget exhausted')
    if plan.get('issue')!=issue or not plan.get('discriminator') or plan.get('status')!='PLANNED':ap.error('missing new discriminator/plan')
    if (attempt/'execution-start.json').exists():ap.error('attempt ID already used')
    if any((parent/'STOP-LAUNCHES.txt').exists() for parent in (attempt,*attempt.parents)):ap.error('active new-scope STOP guard')
    exe=pathlib.Path(plan['exe'])
    (check_cfx008_lane if cfx008 else check_cfx007_lane)(lane/'lane-opening.json',attempt/'runs',exe)
    if cfx008:
        from cfx008_gate import validate_plan,require_control,accept_control
        validate_plan(plan,opening,attempt)
        if (not plan.get('risky') and state['launches']!=0) or (plan.get('risky') and state['launches']!=1):ap.error('CFX-008 requires one control then one target')
        if plan.get('risky'):require_control(lane,state)
    for path,expected in plan['inputs'].items():
        if digest(pathlib.Path(path))!=expected:ap.error('input identity changed: '+path)
    for name,identity in opening['runtime_files'].items():
        if digest(exe.parent/name)!=identity['sha256']:ap.error('runtime identity changed: '+name)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=plan['runner_source']:ap.error('runner source changed')
    if plan.get('risky'):
        if not state.get('safe_controls_passed'):ap.error('safe controls not accepted')
        if state.get('analysis_pending'):ap.error('previous informative target requires analysis before another risk')
    health=collect(attempt,opening['health_since_utc']);save(attempt/'health-before.json',health)
    if health['windows'].get('boot')!=opening['baseline_boot_utc']:
        health['pass']=False;health['stop_reasons'].append('unexpected machine reboot')
    if not health['pass']:
        stop(lane,state,health['stop_reasons'],protocol);ap.error('automatic prelaunch health gate failed')
    print('preflight PASS',plan['attempt_id'],flush=True)
    if not a.launch:return 0
    prior={};backup=attempt/'cache-backup';backup.mkdir();after=attempt/'cache-after';after.mkdir()
    for name in plan['cache_inputs']:
        p=CACHE/name;prior[name]=digest(p)
        if p.is_file():shutil.copy2(p,backup/name)
    state['launches']+=1;state['pending_attempt']=plan['attempt_id'];save(lane/'state.json',state)
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    save(attempt/'execution-start.json',{'attempt_id':plan['attempt_id'],'started_at_utc':started,'plan_sha256':digest(pp),'counted_launch':state['launches'],'original_cache':prior})
    result=None;restored={};error=None
    try:
        CACHE.mkdir(parents=True,exist_ok=True)
        for name,source in plan['cache_inputs'].items():
            p=CACHE/name
            if source:shutil.copy2(source,p)
            elif p.is_file():p.unlink()
        args=[sys.executable,str(ROOT/'tools/cfx_capture.py'),*plan['run_arguments']]
        result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,errors='replace',timeout=150)
        (attempt/'runner.stdout.txt').write_text(result.stdout,encoding='utf-8');(attempt/'runner.stderr.txt').write_text(result.stderr,encoding='utf-8')
        for name in plan['cache_inputs']:
            if (CACHE/name).is_file():shutil.copy2(CACHE/name,after/name)
    except (OSError,subprocess.TimeoutExpired) as e:error=str(e)
    finally:
        for name in plan['cache_inputs']:
            p=CACHE/name
            if (backup/name).is_file():shutil.copy2(backup/name,p)
            elif p.is_file():p.unlink()
            restored[name]=digest(p)==prior[name]
    paths=list((attempt/'runs').glob('*/manifest.json'))
    manifest=json.loads(paths[0].read_text(encoding='utf-8')) if len(paths)==1 else None
    health=collect(attempt,opening['health_since_utc']);save(attempt/'health-after.json',health)
    faults=[]
    if error:faults.append('capture wrapper error: '+error)
    if not all(restored.values()):faults.append('global cache restore failed')
    if not manifest or manifest.get('status') in ('PREPARED','RUNNING'):faults.append('missing/incomplete manifest')
    loss=bool(manifest and manifest['failure']['application_observation']=='VK_ERROR_DEVICE_LOST')
    expected_tdr=any(e['Provider']=='Display' and e['Id']==4101 for e in health['windows'].get('events',[]) if e['Time']>=started)
    wer_tdr=any('LiveKernelEvent' in e.get('Xml','') and any('>'+code+'<' in e.get('Xml','') for code in ('141','117')) for e in health['windows'].get('wer',[]) if e['Time']>=started)
    if loss or expected_tdr or wer_tdr:state['loss_episodes']+=1
    if manifest and manifest['status']=='TIMEOUT':
        dump=manifest['failure'].get('watchdog_action',{})
        if not loss:faults.append('hard/no-return renderer hang')
        if dump.get('status')!='captured':faults.append('required pre-kill process dump not captured')
    if health['windows'].get('boot')!=opening['baseline_boot_utc']:faults.append('unexpected machine reboot')
    if not health['pass']:faults.extend(health['stop_reasons'])
    if not plan.get('risky') and (loss or not manifest or manifest['status']!='EXITED' or manifest['exit_status']!=0):faults.append('safe control failed')
    if manifest:
        for artifact in manifest.get('artifact_files',[]):
            path=pathlib.Path(artifact['path'])
            if not path.is_file() or path.stat().st_size!=artifact['size']:faults.append('artifact missing/changed')
    if cfx008 and not plan.get('risky') and not faults:
        try:
            proof=accept_control(attempt,opening);save(lane/'control-proof.json',proof)
            state['control_proof_sha256']=digest(lane/'control-proof.json');state['safe_controls_passed']=True
        except (OSError,ValueError,KeyError,TypeError) as e:faults.append('safe activation/equivalence gate: '+str(e))
    state['pending_attempt']=None
    state['analysis_pending']=plan['attempt_id'] if plan.get('risky') else None
    state.setdefault('attempts',[]).append({'attempt_id':plan['attempt_id'],'plan':str(pp),'manifest':str(paths[0]) if paths else None,'loss_episode':loss or expected_tdr or wer_tdr,'discriminator':plan['discriminator']})
    if state['launches']>=max_launches or state['loss_episodes']>=max_losses:faults.append('finite campaign ceiling reached')
    if faults:stop(lane,state,faults,protocol)
    else:save(lane/'state.json',state)
    save(attempt/'execution-result.json',{'ended_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'runner_exit_code':result.returncode if result else None,'global_cache_restored':restored,'loss_episode':loss or expected_tdr or wer_tdr,'recovery_pass':health['pass'],'stop_reasons':faults,'counts':{'launches':state['launches'],'loss_episodes':state['loss_episodes']}})
    # Fingerprint immutable outputs after the complete manifest and health records.
    files=[]
    for path in attempt.rglob('*'):
        if path.is_file() and path.name!='artifact-index.json':files.append({'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)})
    save(attempt/'artifact-index.json',{'schema':'cfx-008-artifacts-v1' if cfx008 else 'cfx-007-artifacts-v1','files':files})
    print(json.dumps({'attempt':plan['attempt_id'],'loss':loss,'state':state['status'],'stop_reasons':faults,'counts':[state['launches'],state['loss_episodes']]}),flush=True)
    return 1 if faults else 0

if __name__=='__main__':sys.exit(main())
