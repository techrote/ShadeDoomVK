"""CPU-only supervised continuation: preserve evidence, scope and causal gates."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import cfx_capture as capture
import cfx008_gate as gate
import cfx007_execute as execute


class AdaptiveScope(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.exe = self.root / 'new.exe'
        self.exe.write_bytes(b'candidate diagnostic executable')
        self.exe.with_suffix('.pdb').write_bytes(b'matching symbols')
        self.source = 'a' * 40
        self.path = self.root / 'lane-opening.json'
        self.evidence = self.root / 'old-trace.tsv'
        self.evidence.write_bytes(b'preserved complete trace')
        self.guards = []
        for i in range(13):
            p = self.root / f'old-stop-{i}.txt'
            p.write_bytes(b'preserved')
            self.guards.append(self.record(p))
        self.previous = {}
        previous_data = {
            'opening': dict(schema='cfx-009-lane-v1', issue=102, max_launches=6, max_loss_episodes=2,
                            historical_guards=self.guards),
            'state': dict(status='OPEN', launches=2, loss_episodes=1, pending_attempt=None,
                          attempts=[dict(attempt_id='old-target')]),
            'analysis': dict(analysis_complete=True, source_analysis_pending=False,
                             attempt_id='old-target', conclusion='Old image retired before device loss.',
                             files=[self.record(self.evidence)]),
            'artifact_index': dict(files=[self.record(self.evidence)]),
            'control_proof': dict(accepted=True, files=[self.record(self.evidence)]),
        }
        for name, data in previous_data.items():
            p = self.root / ('previous-' + name + '.json')
            p.write_text(json.dumps(data))
            self.previous[name] = self.record(p)
        runtime = {p.name: {'sha256': capture.digest(p)} for p in (self.exe, self.exe.with_suffix('.pdb'))}
        build = self.root / 'build-proof.json'
        build.write_text(json.dumps(dict(source_sha=self.source, exe_sha256=capture.digest(self.exe),
                                        pdb_sha256=capture.digest(self.exe.with_suffix('.pdb')), runtime_files=runtime)))
        self.lane = dict(schema='cfx-009-lane-v2', issue=102, status='OPEN',
                         testing_policy='supervised-adaptive-20261002',
                         substrate_merge='d7ebce43449e9f347dccf399999832e11ea7c105',
                         renderer_source=self.source, exe_sha256=capture.digest(self.exe),
                         pdb_sha256=capture.digest(self.exe.with_suffix('.pdb')),
                         runtime_files=runtime, build_proof=self.record(build),
                         historical_guards=self.guards, previous_epoch=self.previous,
                         baseline_boot_utc='same-boot', health_since_utc='previous-result')
        self.state = dict(status='OPEN', launches=2, loss_episodes=1, pending_attempt=None,
                          last_analysis=self.previous['analysis'])
        self.save()
        self.ancestry = mock.patch.object(capture.subprocess, 'run', return_value=SimpleNamespace(returncode=0)).start()
        self.addCleanup(mock.patch.stopall)

    def record(self, path): return dict(path=str(path), sha256=capture.digest(path))

    def save(self):
        self.path.write_text(json.dumps(self.lane))
        (self.root / 'state.json').write_text(json.dumps(self.state))

    def check(self): return capture.check_cfx009_lane(self.path, self.root / 'target/runs', self.exe)

    def plan(self, risky=True, retention=True):
        attempt = self.root / 'target'
        (attempt / 'inputs').mkdir(parents=True, exist_ok=True)
        script = attempt / 'inputs/capture.cfg'
        script.write_text('screenshot "' + (attempt / 'scene.png').as_posix() + '"; quit')
        args = ['--exe', str(self.exe), '--run-root', str(attempt / 'runs'),
                '--cfx009-lane-plan', str(self.path), '--mode', 'capture', '--timeout', '60',
                '--approved-cfx009', '--resource-trace', '--address-bindings', '--launch',
                '--arg=+exec', '--arg=' + str(script)]
        if retention: args.append('--retain-replaced-lightmaps')
        return dict(schema='cfx-009-attempt-v2', issue=102, status='PLANNED',
                    attempt_id='new-target', discriminator='Does the retired atlas lifetime change the loss?',
                    hypothesis='The submitted work references the retired atlas.',
                    single_change='Retain replaced lightmaps through process lifetime.',
                    predicted_outcomes={'same-loss': 'Lifetime alone is insufficient.',
                                        'success': 'Lifetime remains a candidate, not a demonstrated repair.'},
                    analysis_prerequisite=self.previous['analysis'], risky=risky,
                    retain_replaced_lightmaps=retention, exe=str(self.exe), renderer_source=self.source,
                    runner_source=self.source, inputs={}, run_arguments=args)

    def control(self, retention=True):
        p = self.root / 'control-proof.json'
        p.write_text(json.dumps(dict(schema='cfx-009-control-proof-v1', accepted=True,
                                    renderer_source=self.source, retain_replaced_lightmaps=retention,
                                    files=[self.record(self.evidence)])))
        self.state.update(control_proof_sha256=capture.digest(p), safe_controls_passed=True)
        self.save()

    def test_adaptive_counts_do_not_reuse_old_finite_ceiling(self):
        self.state.update(launches=100, loss_episodes=20)
        self.save()
        self.assertEqual(self.check()['schema'], 'cfx-009-lane-v2')
        for change in ({'launches': 1}, {'loss_episodes': 0}, {'launches': -1},
                       {'launches': True}, {'loss_episodes': 101}, {'status': 'STOPPED'}):
            self.state = dict(status='OPEN', launches=100, loss_episodes=20)
            self.state.update(change)
            self.save()
            with self.assertRaises(ValueError): self.check()

    def test_exact_policy_ancestry_and_build_proof(self):
        self.check()
        self.ancestry.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, 'descend'): self.check()
        self.ancestry.return_value.returncode = 0
        for change in ({'issue': 99}, {'testing_policy': 'unlimited'}, {'renderer_source': 'wrong'},
                       {'max_launches': 6}, {'renderer_source': 'b' * 40}):
            old = self.lane.copy()
            self.lane.update(change)
            self.save()
            with self.assertRaises(ValueError): self.check()
            self.lane = old
        self.save()
        self.exe.write_bytes(b'other binary')
        with self.assertRaises(ValueError): self.check()

    def test_previous_evidence_and_all_guards_are_immutable(self):
        for path in [Path(r['path']) for r in self.previous.values()] + [self.evidence,
                     Path(self.guards[0]['path']), Path(self.lane['build_proof']['path'])]:
            old = path.read_bytes()
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): self.check()
            path.write_bytes(old)
        self.lane['historical_guards'] = self.guards[:-1]
        self.save()
        with self.assertRaises(ValueError): self.check()
        self.lane['historical_guards'] = [self.guards[0], *self.guards[:-1]]
        self.save()
        with self.assertRaises(ValueError): self.check()

    def test_guard_count_cannot_replace_a_previous_guard(self):
        other = self.root / 'unrelated-stop.txt'
        other.write_bytes(b'another stop')
        self.lane['historical_guards'] = [self.record(other), *self.guards[1:]]
        self.save()
        with self.assertRaisesRegex(ValueError, 'guard set'): self.check()

    def test_stopped_previous_epoch_requires_its_own_sibling_stop(self):
        prior = self.root / 'stopped-prior'
        prior.mkdir()
        old_state = prior / 'state.json'
        old_state.write_text(json.dumps(dict(status='STOPPED', launches=2, loss_episodes=1,
                                            pending_attempt=None)))
        stop = prior / 'STOP-LAUNCHES.txt'
        stop.write_bytes(b'failed safe equivalence; preserve this stop')
        self.previous['state'] = self.record(old_state)
        self.save()
        with self.assertRaisesRegex(ValueError, 'stopped epoch STOP'): self.check()
        self.lane['historical_guards'] = [*self.guards, self.record(stop)]
        self.save()
        self.check()
        stop.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.check()

    def test_active_stop_and_outside_root_still_block(self):
        with self.assertRaises(ValueError): capture.check_cfx009_lane(self.path, self.root.parent / 'outside', self.exe)
        (self.root / 'STOP-LAUNCHES.txt').write_text('STOP')
        with self.assertRaises(ValueError): self.check()

    def test_incomplete_source_analysis_cannot_open_epoch(self):
        p = Path(self.previous['analysis']['path'])
        for change in ({'source_analysis_pending': True}, {'analysis_complete': False}, {'conclusion': ''}, {'files': []}):
            p.write_text(json.dumps(dict(analysis_complete=True, source_analysis_pending=False,
                                        conclusion='Completed.', files=[self.record(self.evidence)]) | change))
            self.previous['analysis'] = self.record(p)
            self.save()
            with self.assertRaises(ValueError): self.check()

    def test_risky_plan_requires_one_change_predictions_and_matching_activation(self):
        plan = self.plan()
        attempt = self.root / 'target'
        gate.validate_plan(plan, self.lane, attempt, 'cfx009')
        for change in ({'hypothesis': ''}, {'single_change': ''}, {'predicted_outcomes': {}},
                       {'analysis_prerequisite': None}, {'retain_replaced_lightmaps': False},
                       {'schema': 'cfx-009-attempt-v1'}):
            with self.assertRaises(ValueError): gate.validate_plan(plan | change, self.lane, attempt, 'cfx009')
        with self.assertRaises(ValueError):
            gate.validate_plan(plan | {'run_arguments': plan['run_arguments'] + ['--skip-dump-on-timeout']}, self.lane, attempt, 'cfx009')

    def test_new_candidate_and_retention_require_their_own_control(self):
        self.control()
        gate.require_control(self.root, self.state, 'cfx-009', self.lane, True)
        for opening, retention in ((self.lane | {'renderer_source': 'b' * 40}, True), (self.lane, False)):
            with self.assertRaises(ValueError): gate.require_control(self.root, self.state, 'cfx-009', opening, retention)

    def test_control_requires_actual_retention_activation_and_replacement(self):
        from PIL import Image
        attempt = self.root / 'safe-control'
        run = attempt / 'runs/fixture'
        (run / 'work').mkdir(parents=True)
        manifest = dict(status='EXITED', exit_status=0, run_id='fixture',
                        failure=dict(application_observation=None),
                        environment=dict(validation_or_capture_mode='capture',
                                         address_bindings=dict(hardware_activation_verified=True),
                                         retain_replaced_lightmaps=dict(requested=True)),
                        run=dict(renderer_source=self.source))
        (run / 'manifest.json').write_text(json.dumps(manifest))
        for name in ('health-before.json', 'health-after.json'):
            (attempt / name).write_text(json.dumps({'pass': True}))
        (attempt / 'plan.json').write_text('{}')
        (run / 'address-bindings.tsv').write_text('already tested by activation gate')
        image = attempt / 'scene.png'
        Image.new('RGBA', (1, 1), (12, 34, 56, 255)).save(image)
        mesh = run / 'work/levelmesh.obj'
        mesh.write_text('v 0 0 0\nf 1 1 1\n')
        opening = self.lane | {'control_reference': {'image': self.record(image), 'mesh': self.record(mesh)}}
        timeline = run / 'timeline.tsv'
        with mock.patch.object(gate, 'activation', return_value={'teardown': {'flushed': 1, 'cutoff': 1}}):
            for cpu in ('', '1\tlightmap-retention-enabled\t1\n'):
                timeline.write_text(cpu)
                with self.assertRaisesRegex(ValueError, 'activation/replacement'):
                    gate.accept_control(attempt, opening, 'cfx-009')
            timeline.write_text('1\tlightmap-retention-enabled\t1\n2\tlightmap-retained\timage\n')
            proof = gate.accept_control(attempt, opening, 'cfx-009')
            self.assertTrue(proof['retain_replaced_lightmaps'])
            self.assertEqual(proof['renderer_source'], self.source)

    def test_each_risk_requires_latest_completed_registered_analysis(self):
        plan = self.plan()
        gate.require_analysis(self.state, self.lane, plan)
        for change in ({'analysis_pending': 'new-target'}, {'last_informative_attempt': 'another-target'}):
            with self.assertRaises(ValueError): gate.require_analysis(self.state | change, self.lane, plan)
        with self.assertRaises(ValueError):
            gate.require_analysis(self.state, self.lane, plan | {'analysis_prerequisite': {}})

    def test_runner_preflight_accepts_supervised_counts_and_rejects_reused_ids(self):
        self.state.update(launches=100, loss_episodes=20)
        self.control()
        plan = self.plan()
        p = self.root / 'target/plan.json'
        p.write_text(json.dumps(plan))
        health = dict(windows=dict(boot='same-boot'), **{'pass': True})
        with mock.patch.object(sys, 'argv', ['runner', '--plan', str(p)]), \
                mock.patch.object(execute.subprocess, 'check_output', return_value=self.source), \
                mock.patch.object(execute, 'collect', return_value=health):
            self.assertEqual(execute.main('CFX-009'), 0)
            p.write_text(json.dumps(plan | {'attempt_id': 'old-target'}))
            with self.assertRaises(SystemExit): execute.main('CFX-009')


class RetentionEnvironment(unittest.TestCase):
    def test_inherited_experiment_is_removed_and_only_explicit_capture_scope_enables(self):
        base = dict(CFX_RETAIN_REPLACED_LIGHTMAPS='1')
        for mode in ('off', 'capture', 'sync', 'gpu-assisted'):
            env = capture.capture_environment(base, mode, 'id', Path('trace'), Path('fault'), True, Path('address'))
            self.assertNotIn('CFX_RETAIN_REPLACED_LIGHTMAPS', env)
        for mode, resources, address in (('off', True, Path('address')), ('sync', True, Path('address')),
                                         ('capture', False, Path('address')), ('capture', True, None)):
            env = capture.capture_environment(base, mode, 'id', Path('trace'), Path('fault'), resources, address, True)
            self.assertNotIn('CFX_RETAIN_REPLACED_LIGHTMAPS', env)
        self.assertEqual(capture.capture_environment(base, 'capture', 'id', Path('trace'), Path('fault'),
                                                    True, Path('address'), True)['CFX_RETAIN_REPLACED_LIGHTMAPS'], '1')


if __name__ == '__main__': unittest.main()
