import hashlib,json,pathlib,shutil,subprocess,statistics
from PIL import Image
root=pathlib.Path(__file__).parent
repo=pathlib.Path(r'C:\ShadeDoomVK\worktrees\pf017-final')
out=repo/'docs/shadedoomvk/evidence/pf017-final-acceptance'
out.mkdir(parents=True,exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x): p.write_text(json.dumps(x,indent=2)+'\n')
analysis=read(root/'production-analysis.json')
audit={'method':'Second CPU-only audit independent of analyze.py: raw samples, direct RGB byte equality, all indexed artifacts and health receipts, chronological non-overlap, exact source diff and immutable guards.'}
times=[]; samples={v:{k:[] for k in ('sprite_setup_ms','all_ms')} for v in ('baseline','candidate')}
for pair in range(1,6):
 imgs=[]
 for v in ('baseline','candidate'):
  run=root/'runs'/f'{v}-pair{pair:02d}'
  r=read(run/'result.json'); assert r['pass'] and r['exit_code']==0 and r['cache_restored'] and not r['watchdog_fired']
  times.append((r['started_utc'],r['finished_utc']))
  for name,h in read(run/'artifact-index.json').items(): assert sha(run/name)==h
  for name in ('health-before.json','health-after.json'):
   h=read(run/name); assert h['pass'] and not h['windows']['events']
  ss=read(run/'samples.json')['warmed_frozen_samples'];assert len(ss)==4
  for k in samples[v]: samples[v][k].extend(x[k] for x in ss)
  img=Image.open(run/'scene.png').convert('RGB');assert img.size==(1904,1001);imgs.append(img.tobytes())
  dest=out/'runs'/run.name;dest.mkdir(parents=True,exist_ok=True)
  for name in ('samples.json','stdout.log','stderr.log','result.json','preregister.json','capture.cfg','health-before.json','health-after.json','artifact-index.json'):
   shutil.copyfile(run/name,dest/name)
 assert imgs[0]==imgs[1]
times.sort();assert all(a[1]<b[0] for a,b in zip(times,times[1:]))
audit['production_runs']=10;audit['serial']=True;audit['full_rgb_exact_pairs']=5
audit['medians']={v:{k:statistics.median(x) for k,x in mm.items()} for v,mm in samples.items()}
for v in samples:
 for k in samples[v]: assert audit['medians'][v][k]==analysis['pooled'][v][k]['median']
assert analysis['candidate_setup_winning_pairs']==0
guards=read(root/'historical-guards.json')
for p,h in guards.items(): assert sha(pathlib.Path(p))==h,p
guards[str(root/'STOP-LAUNCHES.txt')]=sha(root/'STOP-LAUNCHES.txt')
audit['immutable_stop_guards']=len(guards)
paths=['src','libraries','wadsrc','tools/pf_oracle/tests','.github']
diff=subprocess.check_output(['git','diff','2399d9455772c570e597a5960c626f3bf771baeb','--',*paths],cwd=repo)
assert not diff
audit['restored_source_diff_empty']=paths
assert (root/'restored-oracle-a.json').read_bytes()==(root/'restored-oracle-b.json').read_bytes()
audit['restored_deterministic_oracle_exact']=True
write(out/'independent-offline-audit.json',audit)
write(out/'stop-guards.json',guards)
for name in ('production-analysis.json','opening.json','inputs.json','integration-review.json','package-review.json','integrated-ci.json','test-result.json','restored-test-result.json','oracle-a.json','restored-oracle-a.json','restored-tests-isolated.log','diagnostic-metadata-cpu-proof.log','diagnostic_metadata_fixture.cpp','hw_pf17acceptance.h','instrument.py','analyze.py','finalize_evidence.py'):
 shutil.copyfile(root/name,out/name)
write(out/'diagnostic-disposition.json',{'status':'STOPPED; NO FURTHER PHYSICAL LAUNCHES','cause':'Baseline diagnostic identity vectors were not cleared by instrumentation in FDynLightData::Clear; Consumer labeled metadata alignment failures as buffer failures before memcmp. CPU ASan fixture reproduces and isolates this hook defect with identical mapped bytes.','candidate_diagnostic_launched':False,'candidate_mapped_bytes':None,'candidate_write_counts':None,'candidate_reuse_fallback_counters':None,'candidate_source_range_packed_checkpoint_equivalence':None,'full_candidate_physical_correctness_accepted':False,'baseline_copy_site_observations':{'mapped_bytes':3971280,'write_counts':2520,'logical_records':49473,'normal':42775,'subtractive':6698,'additive':0},'performance_no_go_sufficient':'Five complete clean integrated-source pairs independently reject benefit. No optimization is retained; final renderer, shaders, tests and CI configuration are identical to repaired master.','cpu_proof':'diagnostic_metadata_fixture.cpp and diagnostic-metadata-cpu-proof.log','physical_stop_sha256':sha(root/'STOP-LAUNCHES.txt')})
roots=[root.with_name('pf017-final-20261003'),root.with_name('pf017-final-20261003-exclusive'),root]
inventory=[]
for rr in roots:
 for p in sorted(rr.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:
   inventory.append({'root':rr.name,'path':p.relative_to(rr).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
write(out/'private-artifact-manifest.json',{'local_parent':str(root.parent),'note':'Complete preserved private file inventory at final offline seal. Runtime binaries, copyrighted inputs, full PNGs, caches and diagnostic dumps remain local; hashes and raw production timings/health/source identities are committed. No stopped scope or guard removed.','files':inventory})
print(json.dumps(audit))
