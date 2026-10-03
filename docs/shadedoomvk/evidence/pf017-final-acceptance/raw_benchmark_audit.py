import pathlib,re,json,shutil
r=pathlib.Path(__file__).parent
out=pathlib.Path(r'C:\ShadeDoomVK\worktrees\pf017-final\docs\shadedoomvk\evidence\pf017-final-acceptance')
checked=[]
for pair in range(1,6):
 for variant in ('baseline','candidate'):
  run=r/'runs'/f'{variant}-pair{pair:02d}'
  text=(run/'work/benchmarks.txt').read_text()
  # Separate extraction from capture runner: identify individual lines, not block regex.
  ss=[float(x) for x in re.findall(r'^S: Render=[0-9.]+, Setup=([0-9.]+)',text,re.M)]
  aa=[float(x) for x in re.findall(r'^All=([0-9.]+),',text,re.M)]
  expected=json.loads((run/'samples.json').read_text())['warmed_frozen_samples']
  assert len(ss)==len(aa)==5,(run,ss,aa)
  assert ss[1:]==[x['sprite_setup_ms'] for x in expected]
  assert aa[1:]==[x['all_ms'] for x in expected]
  shutil.copyfile(run/'work/benchmarks.txt',out/'runs'/run.name/'benchmarks.txt')
  checked.append(run.name)
(out/'raw-benchmark-audit.json').write_text(json.dumps({'all_10_raw_benchmark_files_match_sample_extraction':True,'excluded_initial_snapshot_each_run':True,'runs':checked},indent=2)+'\n')
for name in ('run.py','exclusive_focus.py','raw_benchmark_audit.py'):
 shutil.copyfile(r/name,out/name)
print('PASS: all 10 raw benchmark files independently match all warmed samples')
