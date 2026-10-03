"""CPU-only CFX-007 scope/budget/identity negative preflight cases."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('capture',ROOT/'tools/cfx_capture.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Gate(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
        self.exe=self.root/'new.exe';self.exe.write_bytes(b'merged-CFX006');self.exe.with_suffix('.pdb').write_bytes(b'matching')
        self.plan=self.root/'lane.json'
        self.guards=[]
        for i in range(6):
            p=self.root/f'historical{i}.txt';p.write_bytes(b'preserved');self.guards.append({'path':str(p),'sha256':m.digest(p)})
        self.lane={'schema':'cfx-007-lane-v1','issue':97,'status':'OPEN','substrate_merge':'a6880fdb22e2f3d9ee85f3a86384b48ad7af9373','exe_sha256':m.digest(self.exe),'pdb_sha256':m.digest(self.exe.with_suffix('.pdb')),'historical_guards':self.guards,'max_launches':16,'max_loss_episodes':6}
        self.state={'status':'OPEN','launches':0,'loss_episodes':0}
        self.save()
    def tearDown(self):self.t.cleanup()
    def save(self):
        self.plan.write_text(json.dumps(self.lane));(self.root/'state.json').write_text(json.dumps(self.state))
    def run_gate(self):return m.check_cfx007_lane(self.plan,self.root/'runs',self.exe)
    def test_valid_cpu_plan(self):self.assertEqual(self.run_gate()['issue'],97)
    def test_validation_scope_preserves_old_campaigns(self):
        for mode in ('core','sync','gpu-assisted'):
            self.assertTrue(m.crash_mode_allowed(mode,True))
            self.assertFalse(m.crash_mode_allowed(mode,False))
        self.assertFalse(m.crash_mode_allowed('off',True))
        self.assertTrue(m.crash_mode_allowed('capture',False))
    def test_budget_or_status_stops(self):
        for changes in ({'launches':16},{'loss_episodes':6},{'status':'STOPPED'},{'launches':-1}):
            self.state={'status':'OPEN','launches':0,'loss_episodes':0,**changes};self.save()
            with self.assertRaises(ValueError):self.run_gate()
    def test_historical_guard_and_new_guard(self):
        Path(self.guards[0]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_gate()
        Path(self.guards[0]['path']).write_bytes(b'preserved')
        (self.root/'STOP-LAUNCHES.txt').write_text('stop')
        with self.assertRaises(ValueError):self.run_gate()
    def test_binary_or_pdb_changed(self):
        self.exe.with_suffix('.pdb').write_bytes(b'wrong')
        with self.assertRaises(ValueError):self.run_gate()
    def test_wrong_scope_or_root(self):
        self.lane['issue']=92;self.save()
        with self.assertRaises(ValueError):self.run_gate()
        self.lane['issue']=97;self.save()
        with self.assertRaises(ValueError):m.check_cfx007_lane(self.plan,self.root.parent/'outside',self.exe)

health_spec=importlib.util.spec_from_file_location('health',ROOT/'tools/cfx007_health.py')
h=importlib.util.module_from_spec(health_spec);health_spec.loader.exec_module(h)
class RecoveryEvents(unittest.TestCase):
    def baseline(self):return {'adapters':[{'Name':'NVIDIA GeForce GTX 1650 SUPER','ConfigManagerErrorCode':0,'DriverVersion':'32.0.16.1692'}],'games':[],'explorer':[{'Responding':True}],'events':[],'wer':[]}
    def test_clean_recovered_tdr_permitted(self):
        d=self.baseline();d['events']=[{'Provider':'nvlddmkm','Id':153,'RecordId':1},{'Provider':'Display','Id':4101,'RecordId':2}]
        self.assertEqual(h.windows_reasons(d),[])
    def test_hardware_os_events_stop(self):
        for provider,event in [('Microsoft-Windows-WHEA-Logger',17),('Microsoft-Windows-Kernel-Power',41),('BugCheck',1001),('EventLog',6008)]:
            d=self.baseline();d['events']=[{'Provider':provider,'Id':event,'RecordId':6}]
            self.assertTrue(h.windows_reasons(d))
    def test_process_desktop_or_gpu_failure_stop(self):
        for key,value in [('games',[{'Id':12}]),('explorer',[{'Responding':False}]),('adapters',[])]:
            d=self.baseline();d[key]=value;self.assertTrue(h.windows_reasons(d))
        d=self.baseline();d['adapters'][0]['ConfigManagerErrorCode']=31;self.assertTrue(h.windows_reasons(d))
    def test_bluescreen_not_livekernel_event(self):
        d=self.baseline();d['wer']=[{'Xml':'<EventType>LiveKernelEvent</EventType><Code>141</Code>','RecordId':2}]
        self.assertEqual(h.windows_reasons(d),[])
        d['wer'][0]['Xml']='<EventType>BlueScreen</EventType>';self.assertTrue(h.windows_reasons(d))
    def test_module_path_isolation(self):
        from unittest.mock import patch
        import subprocess
        with patch.dict(h.os.environ,{'PSMODULEPATH':'incompatible'},clear=True),patch.object(h.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')) as run:
            h.command(['powershell','-Command','CPU-only mock'])
            self.assertFalse(any(k.lower()=='psmodulepath' for k in run.call_args.kwargs['env']))

    def test_utc_cursor_excludes_old_includes_new_anomaly(self):
        d=self.baseline();d['events']=[{'Provider':'Microsoft-Windows-Kernel-Power','Id':41,'RecordId':1,'Time':'2026-10-01T22:33:26Z'},{'Provider':'Microsoft-Windows-WHEA-Logger','Id':17,'RecordId':2,'Time':'2026-10-01T23:00:01Z'}]
        filtered=h.events_since(d,'2026-10-01T23:00:00+00:00')
        self.assertEqual([e['RecordId'] for e in filtered['events']],[2])
        self.assertTrue(h.windows_reasons(filtered))
        self.assertIn('StartTime=$since.ToLocalTime()', (ROOT/'tools/cfx007_health.py').read_text())

class ManifestInventory(unittest.TestCase):
    def test_final_manifest_not_self_sized(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'manifest.json').write_text('{}');(root/'timeline.tsv').write_bytes(b'complete')
            records=m.artifact_inventory(root,['manifest.json','timeline.tsv','missing.dmp'])
            (root/'manifest.json').write_text(json.dumps({'artifact_files':records}))
            self.assertEqual(records,[{'path':str(root/'timeline.tsv'),'size':8}])
            self.assertIn('artifact_inventory(run_dir, manifest["artifacts"])',(ROOT/'tools/cfx_capture.py').read_text())
