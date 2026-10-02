"""Fresh #102 six/two scope; historical guards and actual control proof remain mandatory."""
import json
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools"))
import cfx_capture as capture
import cfx008_gate as gate


class QueuedScope(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.exe = self.root / 'new.exe'; self.exe.write_bytes(b'accepted-PR98')
        self.exe.with_suffix('.pdb').write_bytes(b'matching')
        self.path = self.root / 'lane-opening.json'
        guards = []
        for i in range(12):
            p = self.root / f'old-stop-{i}.txt'; p.write_bytes(b'preserved')
            guards.append({'path': str(p), 'sha256': capture.digest(p)})
        merge = 'd7ebce43449e9f347dccf399999832e11ea7c105'
        self.lane = dict(schema='cfx-009-lane-v1', issue=102, status='OPEN', substrate_merge=merge,
                         renderer_source=merge, exe_sha256=capture.digest(self.exe),
                         pdb_sha256=capture.digest(self.exe.with_suffix('.pdb')),
                         historical_guards=guards, max_launches=6, max_loss_episodes=2)
        self.state = dict(status='OPEN', launches=0, loss_episodes=0)
        self.save()

    def tearDown(self): self.temp.cleanup()
    def save(self):
        self.path.write_text(json.dumps(self.lane)); (self.root / 'state.json').write_text(json.dumps(self.state))
    def check(self): return capture.check_cfx009_lane(self.path, self.root / 'control/runs', self.exe)
    def test_new_scope_only(self):
        self.assertEqual(self.check()['issue'], 102)
        for change in ({'schema': 'cfx-007-lane-v1'}, {'issue': 97}, {'renderer_source': 'wrong'}, {'max_launches': 16}):
            old = self.lane.copy(); self.lane.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
            self.lane = old
    def test_spent_stopped_negative_budgets(self):
        for change in ({'launches': 6}, {'loss_episodes': 2}, {'status': 'STOPPED'}, {'launches': -1}):
            self.state = dict(status='OPEN', launches=0, loss_episodes=0, **{})
            self.state.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
        self.state = dict(status='OPEN', launches=6, loss_episodes=0, pending_attempt='reserved')
        self.save(); self.check()  # final already-reserved child may prepare its manifest
    def test_guards_identities_and_root(self):
        for p in (Path(self.lane['historical_guards'][0]['path']), self.exe, self.exe.with_suffix('.pdb')):
            old = p.read_bytes(); p.write_bytes(b'changed')
            with self.assertRaises(ValueError): self.check()
            p.write_bytes(old)
        with self.assertRaises(ValueError): capture.check_cfx009_lane(self.path, self.root.parent / 'outside', self.exe)
        (self.root / 'STOP-LAUNCHES.txt').write_text('stop')
        with self.assertRaises(ValueError): self.check()
    def test_missing_or_duplicate_guard(self):
        self.lane['historical_guards'][0] = self.lane['historical_guards'][1]; self.save()
        with self.assertRaises(ValueError): self.check()
    def test_target_requires_hashed_control_evidence(self):
        with self.assertRaises(ValueError): gate.require_control(self.root, self.state, protocol="cfx-009")
        p = self.root / 'evidence'; p.write_bytes(b'actual')
        proof = self.root / 'control-proof.json'
        proof.write_text(json.dumps(dict(schema='cfx-009-control-proof-v1', accepted=True,
                                        files=[dict(path=str(p), sha256=capture.digest(p))])))
        self.state['control_proof_sha256'] = capture.digest(proof); gate.require_control(self.root, self.state, protocol="cfx-009")
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError): gate.require_control(self.root, self.state, protocol="cfx-009")
    def test_arguments_cannot_change_scope_or_drop_address_capture(self):
        attempt = self.root / 'control'
        args = ['--exe', str(self.exe), '--run-root', str(attempt / 'runs'), '--cfx009-lane-plan', str(self.path),
                '--mode', 'capture', '--timeout', '60', '--approved-cfx009', '--resource-trace', '--address-bindings', '--launch']
        plan = dict(schema='cfx-009-attempt-v1', exe=str(self.exe), renderer_source=self.lane['renderer_source'], run_arguments=args)
        gate.validate_plan(plan, self.lane, attempt, protocol="cfx009")
        for bad in ([s for s in args if s != '--address-bindings'], args + ['--skip-dump-on-timeout'], args + ['--mode', 'sync'], args + ['--approved-cfx007']):
            with self.assertRaises(ValueError): gate.validate_plan({**plan, 'run_arguments': bad}, self.lane, attempt, protocol='cfx009')

