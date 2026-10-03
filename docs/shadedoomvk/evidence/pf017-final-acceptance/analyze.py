import csv,hashlib,json,pathlib,statistics,struct
from PIL import Image,ImageChops
root=pathlib.Path(__file__).parent
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def dist(values):
 values=sorted(values)
 def q(p):
  n=(len(values)-1)*p;i=int(n);return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(n-i)
 return {'n':len(values),'min':min(values),'p05':q(.05),'median':statistics.median(values),'p95':q(.95),'max':max(values),'samples':values}
def verify_run(run):
 result=read(run/'result.json');assert result['pass'] and result['exit_code']==0 and not result['watchdog_fired'] and result['cache_restored']
 for name in ('health-before.json','health-after.json'):
  h=read(run/name);assert h['pass'] and not h['windows']['events']
 for p,h in read(run/'artifact-index.json').items():assert sha(run/p)==h,(run,p)
 return result
pooled={v:{'sprite_setup_ms':[],'all_ms':[]} for v in ('baseline','candidate')};pairs=[]
for p,order in enumerate(read(root/'opening.json')['pairs'],1):
 item={'pair':p,'order':order};results={}
 for v in order:
  run=root/'runs'/f'{v}-pair{p:02d}';results[v]=verify_run(run)
  data=read(run/'samples.json')['warmed_frozen_samples'];assert len(data)==4
  assert all(x['camera']==[-1850.,0.,41.,0.,0.] and x['sprites']==832 for x in data)
  item[v]={k:dist([x[k] for x in data]) for k in pooled[v]}
  for k in pooled[v]:pooled[v][k].extend(x[k] for x in data)
  prereg=read(run/'preregister.json');assert prereg['runtime']['source_sha']==read(root/'opening.json')[v+'_sha']
 assert results[order[0]]['finished_utc']<results[order[1]]['started_utc']
 imgs=[Image.open(root/'runs'/f'{v}-pair{p:02d}'/'scene.png').convert('RGB') for v in ('baseline','candidate')]
 assert imgs[0].size==imgs[1].size==(1904,1001)
 item['image_exact']=ImageChops.difference(*imgs).getbbox() is None
 item['pixel_sha256']=[hashlib.sha256(i.tobytes()).hexdigest() for i in imgs]
 item['setup_change_percent']=(item['candidate']['sprite_setup_ms']['median']/item['baseline']['sprite_setup_ms']['median']-1)*100
 item['frame_change_percent']=(item['candidate']['all_ms']['median']/item['baseline']['all_ms']['median']-1)*100
 pairs.append(item)
summary={v:{k:dist(values) for k,values in metrics.items()} for v,metrics in pooled.items()}
analysis={'schema':'pf017-final-production-v1','baseline':read(root/'baseline/identity.json'),'candidate':read(root/'candidate/identity.json'),'pairs':pairs,'pooled':summary,'setup_change_percent':(summary['candidate']['sprite_setup_ms']['median']/summary['baseline']['sprite_setup_ms']['median']-1)*100,'frame_change_percent':(summary['candidate']['all_ms']['median']/summary['baseline']['all_ms']['median']-1)*100,'all_images_exact':all(p['image_exact'] for p in pairs),'candidate_setup_winning_pairs':sum(p['setup_change_percent']<0 for p in pairs),'physical_decision':'REJECT / LIGHT-PATH NO-GO','warmups_excluded':True,'timing_source':'existing CheckBench CPU clocks, four snapshots per run; no standalone GPU timestamp claim'}
assert analysis['candidate_setup_winning_pairs']==0
(root/'production-analysis.json').write_text(json.dumps(analysis,indent=2))
diagnostics={}
for v in ('baseline','candidate'):
 run=root/'runs'/(v+'-diag-checkpoints')
 if not (run/'result.json').exists():continue
 verify_run(run)
 rows=list(csv.DictReader((run/'counters.csv').open()))
 assert rows and all(int(x['packing_mismatches'])==int(x['buffer_mismatches'])==0 for x in rows)
 selected=[x for x in rows if 100<=int(x['tic'])<=299 and int(x['calls'])>0]
 assert selected
 diagnostics[v]={'rows':len(rows),'selected_rows':len(selected),'selection':'map tics 100..299 before pause','median_counters':{k:statistics.median(int(x[k]) for x in selected) for k in rows[0] if k not in ('frame','tic')},'packing_mismatches':sum(int(x['packing_mismatches']) for x in rows),'buffer_mismatches':sum(int(x['buffer_mismatches']) for x in rows),'runtime':read(root/(v+'-diag')/'identity.json')}
if len(diagnostics)==2:
 checkpoints=[]
 for tic in (45,105,165):
  row={'tic':tic}
  for kind in ('buffer','identities'):
   paths=[root/'runs'/(v+'-diag-checkpoints')/f'{kind}-tic-{tic:03d}.bin' for v in ('baseline','candidate')]
   row[kind+'_exact']=paths[0].read_bytes()==paths[1].read_bytes();row[kind+'_bytes']=paths[0].stat().st_size;row[kind+'_sha256']=[sha(p) for p in paths]
   assert row[kind+'_exact'] and row[kind+'_bytes']>0,row
   if kind=='buffer':row['range_count'],row['record_count']=struct.unpack('<ii',paths[0].read_bytes()[:8])
  checkpoints.append(row)
 diagnostics['checkpoints']=checkpoints
 diagnostics['identity_protocol']='24-byte diagnostic incarnation/TID/source-group/render-group/attenuate-trace record followed by exact 80-byte packed record in each ordered consumer/class; GetLight assigns a new diagnostic incarnation after every allocation/freelist reset; not a production or serialized identity'
 (root/'diagnostic-analysis.json').write_text(json.dumps(diagnostics,indent=2))
print(json.dumps({'setup_change_percent':analysis['setup_change_percent'],'frame_change_percent':analysis['frame_change_percent'],'images_exact':analysis['all_images_exact'],'diagnostic_variants':len(diagnostics),'decision':analysis['physical_decision']}))
