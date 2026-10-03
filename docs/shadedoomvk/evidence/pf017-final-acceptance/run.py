"""One serial PF-017 invocation. Any failure seals this independent scope."""
import datetime as dt, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time

root=pathlib.Path(__file__).parent
sys.path.insert(0,'C:/ShadeDoomVK/worktrees/pf017-final/tools')
from cfx007_health import collect
from cfx010_foreground import ForegroundSession
from exclusive_focus import ExclusiveForeground

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,data): pathlib.Path(p).write_text(json.dumps(data,indent=2))
def stop(reason):
    (root/'STOP-LAUNCHES.txt').write_text(dt.datetime.now(dt.timezone.utc).isoformat()+'\nPF-017 final acceptance stopped: '+reason+'\nNo further physical launches or automatic retry; offline analysis only.\n')
    raise RuntimeError(reason)

variant,label=sys.argv[1:3]
assert variant in ('baseline','candidate','baseline-diag','candidate-diag')
assert re.fullmatch(r'[a-z0-9-]+',label)
if (root/'STOP-LAUNCHES.txt').exists(): raise RuntimeError('Scope already stopped')
opening=json.loads((root/'opening.json').read_text())
# Fail before health probes or process creation unless both matched packages
# are present and pinned. This closes the observed packaging-order mistake.
for required in ('baseline','candidate'):
    package=root/required
    identity=json.loads((package/'identity.json').read_text())
    if identity['source_sha']!=opening[required+'_sha']: stop('Package source does not match opening')
    for filename,digest in identity['runtime_sha256'].items():
        if sha(package/filename)!=digest: stop('Matched package changed: '+required+'/'+filename)
for p,h in json.loads((root/'historical-guards.json').read_text()).items():
    if sha(p)!=h: stop('Historical guard changed: '+p)
run=root/'runs'/(variant+'-'+label)
run.mkdir(parents=True,exist_ok=False)
(run/'work').mkdir(); (run/'save').mkdir()
inputs=json.loads((root/'inputs.json').read_text())
for v in inputs.values():
    if sha(v['path'])!=v['sha256']: stop('Pinned input changed')
runtime=root/variant
manifest=json.loads((runtime/'identity.json').read_text())
for name,h in manifest['runtime_sha256'].items():
    if sha(runtime/name)!=h: stop('Runtime changed: '+name)
pre=collect(root,opening['opened_utc']); write(run/'health-before.json',pre)
if not pre['pass'] or pre['windows'].get('events'): stop('Preflight health/event gate failed')
cache=pathlib.Path('C:/Users/-/AppData/Local/zdoom/cache')
for name in ('pipelinecache.zdpc','shadercache.zdsc'): shutil.copy2(root/'inputs'/name,cache/name)
shutil.copy2(inputs['config']['path'],run/'config.ini')
shutil.copy2(run/'config.ini',run/'config-before.ini')
commands='use_mouse false; unbindall; vid_activeinbackground true; vid_lowerinbackground false; cl_capfps false; vid_maxfps 0; vid_vsync false; vid_fps true; stat rendertimes; bench; wait 350; pause; wait 60; '
commands += ' '.join('bench; wait 190;' for _ in range(4))
commands += ' stat rendertimes; vid_fps false; wait 40; screenshot "'+str(run/'scene.png').replace('\\','/')+'"; wait 2; echo PF017_COMPLETE; quit'
if variant.endswith('-diag'):
    commands=commands.replace('cl_capfps false; vid_maxfps 0;', 'cl_capfps true; vid_maxfps 35;')
(run/'capture.cfg').write_text(commands,encoding='ascii')
args=[str(runtime/'vkdoom.exe'),'-stdout','-noautoload','-nosound','-nojoy','-rngseed','12345','-width','1904','-height','1001','-config',str(run/'config.ini'),'-savedir',str(run/'save'),'-iwad',inputs['iwad']['path'],'-file',inputs['dense']['path'],'+map','PF16TST','+exec',str(run/'capture.cfg')]
env={k:v for k,v in os.environ.items() if not k.startswith(('PF16_','PF17_','CFX_','VK_INSTANCE_LAYERS','VK_LAYER_SETTINGS_PATH'))}
if variant.endswith('-diag'):
    env['PF17_ACCEPTANCE_DIR']=str(run)
write(run/'preregister.json',{'args':args,'runtime':manifest,'input_identities':inputs,'script_sha256':sha(run/'capture.cfg'),'environment':{k:v for k,v in env.items() if k.startswith(('PF','CFX','VK_'))},'watchdog_seconds':45})
started=dt.datetime.now(dt.timezone.utc).isoformat(); deadline=time.monotonic()+45
reason=None; timedout=False; report={}; proc=None
try:
    with (run/'stdout.log').open('w') as out,(run/'stderr.log').open('w') as err:
        proc=subprocess.Popen(args,cwd=run/'work',stdout=out,stderr=err,env=env)
        focus_api=ExclusiveForeground()
        focus=ForegroundSession(proc,api=focus_api)
        focus.report['exclusive_activation']=focus_api.activation
        if not focus.report.get('verified'):
            reason='HOST_ABORT: one owned foreground request failed'
            if proc.poll() is None: proc.kill()
        while proc.poll() is None:
            if time.monotonic()>=deadline:
                timedout=True; reason='watchdog: no-return/unfinished process'; proc.kill(); break
            text=(run/'stdout.log').read_text(errors='replace')+(run/'stderr.log').read_text(errors='replace')
            if re.search(r'VK_ERROR_DEVICE_LOST|device.?lost|Validation Error|VUID-|Fatal error|Execution could not continue',text,re.I):
                reason='unexpected renderer/device/validation failure'; proc.kill(); break
            time.sleep(.1)
        code=proc.wait(timeout=10); report=focus.finish()
        ended_ms=int(time.time()*1000)
        # Only the dying process's natural window/focus release is permitted.
        for event in report.get('events',[]):
            if event.get('kind')=='window-ended': continue
            if event.get('kind')=='native-foreground-change' and (not event.get('alive') or not event.get('visible')): continue
            reason=reason or 'Foreground/modal interference: '+event.get('kind','unknown')
        if report.get('omitted_events') or not report.get('monitor_stopped') or not report.get('event_hooks_removed'): reason=reason or 'Foreground capture incomplete'
        if code!=0: reason=reason or 'Nonzero process exit'
finally:
    for name in ('pipelinecache.zdpc','shadercache.zdsc'):
        if (cache/name).exists(): shutil.copy2(cache/name,run/(name+'-after'))
        shutil.copy2(root/'inputs'/name,cache/name)
    restored=all(sha(cache/name)==inputs[name]['sha256'] for name in ('pipelinecache.zdpc','shadercache.zdsc'))
    if not restored: reason=reason or 'Cache restore failed'
post=collect(root,opening['opened_utc']); write(run/'health-after.json',post)
if not post['pass'] or post['windows'].get('events'): reason=reason or 'Postflight health/event anomaly'
text=(run/'stdout.log').read_text(errors='replace')+(run/'stderr.log').read_text(errors='replace')
if not (run/'scene.png').exists() or 'PF017_COMPLETE' not in text: reason=reason or 'Incomplete image/route'
bench=run/'work'/'benchmarks.txt'
samples=[]
if bench.exists():
    blocks=bench.read_text().split('Map PF16TST:')[1:]
    for block in blocks:
        s=re.search(r'S: Render=([0-9.]+), Setup=([0-9.]+)',block)
        alltime=re.search(r'All=([0-9.]+), Render=([0-9.]+), Setup=([0-9.]+).*Finish=([0-9.]+)',block)
        camera=re.search(r'x = ([-0-9.]+), y = ([-0-9.]+), z = ([-0-9.]+), angle = ([-0-9.]+), pitch = ([-0-9.]+)',block)
        population=re.search(r'Sprites: ([0-9]+)',block)
        if s and alltime and camera and population:
            samples.append({'sprite_setup_ms':float(s[2]),'all_ms':float(alltime[1]),'process_setup_ms':float(alltime[3]),'finish_ms':float(alltime[4]),'camera':list(map(float,camera.groups())),'sprites':int(population[1])})
if len(samples)!=5: reason=reason or f'Expected 5 benchmark snapshots, got {len(samples)}'
if variant.endswith('-diag'):
    import csv
    counter_file=run/'counters.csv'
    rows=list(csv.DictReader(counter_file.open())) if counter_file.exists() else []
    if not rows: reason=reason or 'Diagnostic counters missing'
    elif any(int(x['packing_mismatches']) or int(x['buffer_mismatches']) for x in rows): reason=reason or 'Unexpected diagnostic packing/buffer oracle failure'
write(run/'samples.json',{'excluded_warm_snapshot':samples[:1],'warmed_frozen_samples':samples[1:]})
write(run/'result.json',{'variant':variant,'label':label,'started_utc':started,'finished_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'exit_code':code,'watchdog_fired':timedout,'stop_reason':reason,'foreground':report,'cache_restored':restored,'pass':reason is None})
write(run/'artifact-index.json',{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file()})
print(json.dumps({'run':str(run),'pass':reason is None,'reason':reason,'samples':len(samples)}),flush=True)
if reason: stop(reason)
