"""CPU-only approved #99 scope, callback completeness and exact identity gates."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import cfx_capture as capture
import cfx008_gate as gate
import cfx_address_correlate as address


class Scope(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.exe = self.root / 'new.exe'; self.exe.write_bytes(b'accepted-PR98')
        self.exe.with_suffix('.pdb').write_bytes(b'matching')
        self.path = self.root / 'lane-opening.json'
        guards = []
        for i in range(11):
            p = self.root / f'old-stop-{i}.txt'; p.write_bytes(b'preserved')
            guards.append({'path': str(p), 'sha256': capture.digest(p)})
        merge = 'c6a7197ae48b8d163df9f72783c177ca427505f5'
        self.lane = dict(schema='cfx-008-lane-v1', issue=99, status='OPEN', substrate_merge=merge,
                         renderer_source=merge, exe_sha256=capture.digest(self.exe),
                         pdb_sha256=capture.digest(self.exe.with_suffix('.pdb')),
                         historical_guards=guards, max_launches=2, max_loss_episodes=1)
        self.state = dict(status='OPEN', launches=0, loss_episodes=0)
        self.save()

    def tearDown(self): self.temp.cleanup()
    def save(self):
        self.path.write_text(json.dumps(self.lane)); (self.root / 'state.json').write_text(json.dumps(self.state))
    def check(self): return capture.check_cfx008_lane(self.path, self.root / 'control/runs', self.exe)
    def test_new_scope_only(self):
        self.assertEqual(self.check()['issue'], 99)
        for change in ({'schema': 'cfx-007-lane-v1'}, {'issue': 97}, {'renderer_source': 'wrong'}, {'max_launches': 16}):
            old = self.lane.copy(); self.lane.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
            self.lane = old
    def test_spent_stopped_negative_budgets(self):
        for change in ({'launches': 2}, {'loss_episodes': 1}, {'status': 'STOPPED'}, {'launches': -1}):
            self.state = dict(status='OPEN', launches=0, loss_episodes=0, **{})
            self.state.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
        self.state = dict(status='OPEN', launches=2, loss_episodes=0, pending_attempt='reserved')
        self.save(); self.check()  # final already-reserved child may prepare its manifest
    def test_guards_identities_and_root(self):
        for p in (Path(self.lane['historical_guards'][0]['path']), self.exe, self.exe.with_suffix('.pdb')):
            old = p.read_bytes(); p.write_bytes(b'changed')
            with self.assertRaises(ValueError): self.check()
            p.write_bytes(old)
        with self.assertRaises(ValueError): capture.check_cfx008_lane(self.path, self.root.parent / 'outside', self.exe)
        (self.root / 'STOP-LAUNCHES.txt').write_text('stop')
        with self.assertRaises(ValueError): self.check()
    def test_missing_or_duplicate_guard(self):
        self.lane['historical_guards'][0] = self.lane['historical_guards'][1]; self.save()
        with self.assertRaises(ValueError): self.check()
    def test_target_requires_hashed_control_evidence(self):
        with self.assertRaises(ValueError): gate.require_control(self.root, self.state)
        p = self.root / 'evidence'; p.write_bytes(b'actual')
        proof = self.root / 'control-proof.json'
        proof.write_text(json.dumps(dict(schema='cfx-008-control-proof-v1', accepted=True,
                                        files=[dict(path=str(p), sha256=capture.digest(p))])))
        self.state['control_proof_sha256'] = capture.digest(proof); gate.require_control(self.root, self.state)
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError): gate.require_control(self.root, self.state)
    def test_arguments_cannot_change_scope_or_drop_address_capture(self):
        attempt = self.root / 'control'
        args = ['--exe', str(self.exe), '--run-root', str(attempt / 'runs'), '--cfx008-lane-plan', str(self.path),
                '--mode', 'capture', '--timeout', '60', '--approved-cfx008', '--resource-trace', '--address-bindings', '--launch']
        plan = dict(schema='cfx-008-attempt-v1', exe=str(self.exe), renderer_source=self.lane['renderer_source'], run_arguments=args)
        gate.validate_plan(plan, self.lane, attempt)
        for bad in ([s for s in args if s != '--address-bindings'], args + ['--skip-dump-on-timeout'], args + ['--mode', 'sync'], args + ['--approved-cfx007']):
            with self.assertRaises(ValueError): gate.validate_plan({**plan, 'run_arguments': bad}, self.lane, attempt)


class Activation(unittest.TestCase):
    def fixture(self, root):
        bindings = root / 'bindings'; cpu = root / 'cpu'
        rows = []
        for n, event, name in ((1, 'bind', 'buffer'), (2, 'unbind', 'buffer'), (3, 'snapshot', 'device-teardown')):
            rows.append(f'{n}\t1\t2\t7\t18\t11\t{event}\t0x1000\t16\t0\t9\t0xab\t0\t1\t{name}')
        bindings.write_text('# CFX address bindings v1 run=fixture\n' + '\t'.join(address.FIELDS) + '\n' + '\n'.join(rows) + '\n')
        cpu.write_text('# CFX-002 trace v1 run=fixture\nheader\n'
                       '1\t2\t7\t18\t11\tworld\taddress-binding-messenger\tregistered\t0\n'
                       '2\t2\t7\t18\t11\tworld\tcapability\taddress-binding-report-enabled\t0\n'
                       '3\t2\t7\t18\t11\tworld\taddress-binding-summary\treason=device-teardown records=3 omitted=0 contended=0 writer_ok=1 limit=32768\t0\n')
        return bindings, cpu
    def test_complete_and_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            b, c = self.fixture(Path(temp)); self.assertEqual(gate.activation(b, c, 'fixture')['binds'], 1)
            original = c.read_text()
            for old, new in (('contended=0', 'contended=1'), ('omitted=0', 'omitted=1'), ('writer_ok=1', 'writer_ok=0'), ('records=3', 'records=4'), ('report-enabled', 'report-unavailable')):
                c.write_text(original.replace(old, new))
                with self.assertRaises(ValueError): gate.activation(b, c, 'fixture')
            c.write_text(original); b.write_text(b.read_text().replace('\tbind\t', '\tbinding-no-object\t'))
            with self.assertRaises(ValueError): gate.activation(b, c, 'fixture')
    def test_unflushed_queue_is_not_complete_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            b, c = self.fixture(Path(temp)); original = c.read_text()
            c.write_text(original.replace('limit=32768', 'limit=32768 flushed=2 cutoff=3'))
            with self.assertRaises(ValueError): gate.activation(b, c, 'fixture')
            c.write_text(original.replace('limit=32768', 'limit=32768 flushed=3 cutoff=3'))
            gate.activation(b, c, 'fixture')
    def test_prefix_run_id_is_not_same_run(self):
        with tempfile.TemporaryDirectory() as temp:
            b, c = self.fixture(Path(temp)); c.write_text(c.read_text().replace('run=fixture', 'run=fixture-other'))
            with self.assertRaises(ValueError): gate.activation(b, c, 'fixture')
            with self.assertRaises(ValueError): address.correlate(b, c, 0x1000, 16)
    def test_truncated_sequence_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            b, c = self.fixture(Path(temp)); b.write_text(b.read_text().rstrip())
            with self.assertRaises(ValueError): gate.activation(b, c, 'fixture')
