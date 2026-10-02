"""CPU-only #105 gates: scope, prior evidence, single attempts and capture limits."""
import json
import pathlib
import sys
import tempfile
import unittest
import contextlib
import io
from types import SimpleNamespace, ModuleType
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import cfx_capture as capture
import cfx010_gate as gate
import cfx010_execute as execute
import cfx010_foreground as foreground
from cfx_address_correlate import FIELDS


class CrossCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve(); self.lane = self.root / 'new'; self.lane.mkdir()
        self.old = self.root / 'old'; self.old.mkdir()
        self.exe = self.lane / 'engine.exe'; self.exe.write_bytes(b'accepted renderer'); self.exe.with_suffix('.pdb').write_bytes(b'pdb')
        self.evidence = self.old / 'evidence.tsv'; self.evidence.write_bytes(b'immutable capture')
        guards = []
        for i in range(15):
            p = self.old / f'stop{i}.txt'; p.write_bytes(b'preserved'); guards.append(self.record(p))
        stop = self.old / 'STOP-LAUNCHES.txt'; stop.write_bytes(b'saturated'); guards.append(self.record(stop))
        previous = {}
        for name, data in {
            'opening': {'issue': 102, 'historical_guards': guards[:-1]},
            'state': {'status': 'VALIDATION_SATURATED', 'launches': 14, 'loss_episodes': 2,
                      'pending_attempt': None, 'analysis_pending': None, 'last_informative_attempt': 'old-target'},
            'analysis': {'analysis_complete': True, 'source_analysis_pending': False,
                         'attempt_id': 'old-target', 'conclusion': 'Retirement repair validated.', 'files': [self.record(self.evidence)]},
            'artifact_index': {'files': [self.record(self.evidence)]},
            'control_proof': {'accepted': True, 'renderer_source': gate.RENDERER,
                              'retain_replaced_lightmaps': False, 'files': [self.record(self.evidence)]},
            'closure_proof': {'status': 'VALIDATION_SATURATED'},
        }.items():
            p = self.old / (name + '.json'); p.write_text(json.dumps(data)); previous[name] = self.record(p)
        runtime = {p.name: {'sha256': capture.digest(p)} for p in (self.exe, self.exe.with_suffix('.pdb'))}
        build = self.lane / 'build.json'; build.write_text(json.dumps({'source_sha': gate.RENDERER,
            'exe_sha256': capture.digest(self.exe), 'pdb_sha256': capture.digest(self.exe.with_suffix('.pdb')), 'runtime_files': runtime}))
        equivalent = self.lane / 'equivalent.json'; equivalent.write_text(json.dumps({'accepted_baseline': gate.BASELINE,
            'renderer_source': gate.RENDERER, 'renderer_source_equivalent': True}))
        self.iwad = self.lane / 'Doom2.wad'; self.iwad.write_bytes(b'iwad')
        self.wad = self.lane / 'DBP50.wad'; self.wad.write_bytes(b'original')
        self.content = [{'role': 'IWAD', **self.record(self.iwad)}, {'role': 'PWAD', **self.record(self.wad)}]
        self.settings = {'resolution': [1264, 681], 'cap': True, 'maxfps': 60, 'vsync': False, 'msaa': 4, 'gl_levelmesh': False}
        template = self.lane / 'approved-route.cfg'; template.write_text('wait 120; screenshot "scene.png"; wait 2; quit')
        self.profile = {'map': 'MAP08', 'content_order': self.content, 'settings': self.settings,
                        'config_values': {'gl_levelmesh': 'false', 'vid_maxfps': '60'},
                        'pre_arguments': [], 'target_script_sha256': gate.script_hash(template), 'control_script_sha256': gate.script_hash(template),
                        'route': {'skill': None, 'seed': None, 'camera': None, 'completion': 'finite screenshot and quit',
                                  'completion_markers': ['ROUTE_BEGIN', 'ROUTE_COMPLETE']},
                        'control_completion_markers': ['CONTROL_BEGIN', 'CONTROL_COMPLETE'],
                        'historical_incident_ids': ['original-1824'], 'known_differences': ['accepted PR104 binary']}
        self.opening = {'schema': 'cfx-010-lane-v1', 'issue': 105, 'status': 'OPEN',
            'testing_policy': 'supervised-adaptive-cross-case-20261002', 'accepted_baseline': gate.BASELINE,
            'renderer_source': gate.RENDERER, 'exe_sha256': capture.digest(self.exe),
            'pdb_sha256': capture.digest(self.exe.with_suffix('.pdb')), 'runtime_files': runtime,
            'build_proof': self.record(build), 'source_equivalence': self.record(equivalent),
            'historical_guards': guards, 'previous_epoch': previous,
            'case_profiles': {case: self.profile | {'map': mapname} for case, mapname in gate.CASES.items()}}
        self.state = {'status': 'OPEN', 'launches': 14, 'loss_episodes': 2, 'pending_attempt': None,
                      'analysis_pending': None, 'last_analysis': previous['analysis'], 'attempts': []}
        self.save()
        self.diff = mock.patch.object(gate.subprocess, 'run', return_value=SimpleNamespace(returncode=0)).start()
        self.addCleanup(mock.patch.stopall)

    def record(self, p): return {'path': str(p), 'sha256': capture.digest(p)}
    def save(self):
        (self.lane / 'lane-opening.json').write_text(json.dumps(self.opening))
        (self.lane / 'state.json').write_text(json.dumps(self.state))
    def check(self): return gate.check_lane(self.lane / 'lane-opening.json', self.lane / 'target/runs', self.exe)

    def plan(self, risky=False):
        attempt = self.lane / 'target'; (attempt / 'inputs').mkdir(parents=True, exist_ok=True)
        script = attempt / 'inputs/capture.cfg'; image = attempt / 'scene.png'
        script.write_text('wait 120; screenshot "' + image.as_posix() + '"; wait 2; quit')
        config = attempt / 'inputs/vkdoom.ini'; config.write_text('[GlobalSettings]\ngl_levelmesh=false\nvid_maxfps=60\n')
        cache = pathlib.Path.home() / 'AppData/Local/zdoom/cache'
        args = ['--exe', str(self.exe), '--run-root', str(attempt / 'runs'), '--iwad', str(self.iwad),
                '--config', str(config), '--pipeline-cache', str(cache / 'pipelinecache.zdpc'),
                '--shader-cache', str(cache / 'shadercache.zdsc'), '--map', 'MAP08' if risky else 'MAP01',
                '--mode', 'capture', '--timeout', '25', '--approved-cfx010', '--cfx010-lane-plan', str(self.lane / 'lane-opening.json'),
                '--resource-trace', '--address-bindings', '--launch', '--isolate-workdir', '--arg=+exec', '--arg=' + str(script)]
        inputs = {str(p): capture.digest(p) for p in (config, script, self.iwad)}
        if risky: args += ['--pwad', str(self.wad)]; inputs[str(self.wad)] = capture.digest(self.wad)
        plan = {'schema': 'cfx-010-attempt-v1', 'issue': 105, 'status': 'PLANNED', 'attempt_id': 'CFX10-ORIGINAL-001',
                'case': 'dbp50-original', 'risky': risky, 'exe': str(self.exe), 'renderer_source': gate.RENDERER,
                'runner_source': 'a' * 40, 'settings': self.settings, 'route': self.profile['route'], 'inputs': inputs,
                'cache_inputs': {'pipelinecache.zdpc': None, 'shadercache.zdsc': None}, 'run_arguments': args,
                'completion_artifacts': [str(image)], 'discriminator': 'Does the selected historical route complete?',
                'hypothesis': 'PR104 may cover this distinct case.', 'single_change': 'Accepted production source versus historical binary.',
                'predicted_outcomes': {'success': 'Practical qualification; no shared-cause claim.', 'failure': 'PR104 insufficient.'},
                'analysis_prerequisite': self.opening['previous_epoch']['analysis']}
        return attempt, plan

    def control(self):
        p = self.lane / 'control-proof.json'
        p.write_text(json.dumps({'schema': 'cfx-010-control-proof-v1', 'accepted': True, 'renderer_source': gate.RENDERER,
            'settings': self.settings, 'control_content_order': [self.content[0]], 'files': [self.record(self.evidence)]}))
        self.state['control_proofs'] = {gate.settings_key(self.settings): self.record(p)}; self.save()

    def test_new_scope_carries_saturation_without_reopening_it(self):
        self.check(); self.state.update(launches=90, loss_episodes=20); self.save(); self.check()
        for change in ({'launches': 13}, {'loss_episodes': 1}, {'launches': True}, {'status': 'STOPPED'}):
            old = self.state.copy(); self.state.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
            self.state = old
        self.save()
        (self.lane / 'STOP-LAUNCHES.txt').write_text('operator stop')
        with self.assertRaisesRegex(ValueError, 'active STOP'): self.check()

    def test_all_guards_previous_final_evidence_and_binary_are_pinned(self):
        for p in [self.evidence, self.exe, pathlib.Path(self.opening['historical_guards'][0]['path']),
                  pathlib.Path(self.opening['previous_epoch']['closure_proof']['path'])]:
            old = p.read_bytes(); p.write_bytes(b'changed')
            with self.assertRaises(ValueError): self.check()
            p.write_bytes(old)
        self.opening['historical_guards'] = self.opening['historical_guards'][:-1]; self.save()
        with self.assertRaises(ValueError): self.check()

    def test_baseline_equivalence_and_finite_old_limits_cannot_be_changed(self):
        self.diff.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, 'equivalence'): self.check()
        self.diff.return_value.returncode = 0
        for change in ({'issue': 102}, {'renderer_source': 'b' * 40}, {'max_launches': 16}, {'case_profiles': {}}):
            old = self.opening.copy(); self.opening.update(change); self.save()
            with self.assertRaises(ValueError): self.check()
            self.opening = old

    def test_actual_content_config_output_and_watchdog_are_bound(self):
        attempt, plan = self.plan(); gate.validate_plan(plan, self.opening, attempt)
        for extra in (['--approved-cfx009'], ['--skip-dump-on-timeout'], ['--retain-replaced-lightmaps'], ['--timeout', '61']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises((ValueError, SystemExit)):
                gate.validate_plan(plan | {'run_arguments': plan['run_arguments'] + extra}, self.opening, attempt)
        for change in ({'case': 'unregistered'}, {'settings': {'resolution': [1, 1]}}, {'completion_artifacts': [str(self.root / 'outside.png')]}, {'inputs': {}}):
            with self.assertRaises(ValueError): gate.validate_plan(plan | change, self.opening, attempt)
        (attempt / 'inputs/vkdoom.ini').write_text('gl_levelmesh=true\nvid_maxfps=60\n')
        with self.assertRaisesRegex(ValueError, 'config'): gate.validate_plan(plan, self.opening, attempt)

    def test_each_target_requires_matching_control_and_complete_analysis(self):
        attempt, plan = self.plan(True)
        with self.assertRaises(ValueError): gate.validate_plan(plan, self.opening, attempt)
        self.control(); gate.validate_plan(plan, self.opening, attempt)
        for change in ({'analysis_pending': 'previous'}, {'pending_attempt': 'previous'}, {'last_analysis': None, 'last_informative_attempt': 'later-target'}):
            old = self.state.copy(); self.state.update(change); self.save()
            with self.assertRaises(ValueError): gate.validate_plan(plan, self.opening, attempt)
            self.state = old
        self.save()
        with self.assertRaises(ValueError): gate.validate_plan(plan | {'analysis_prerequisite': None}, self.opening, attempt)

    def test_executable_commands_and_stale_completion_cannot_undermine_preregistration(self):
        attempt, plan = self.plan()
        with self.assertRaisesRegex(ValueError, 'console arguments'):
            gate.validate_plan(plan | {'run_arguments': plan['run_arguments'] + ['--arg=+gl_levelmesh', '--arg=true']}, self.opening, attempt)
        with self.assertRaisesRegex(ValueError, 'process arguments'):
            gate.validate_plan(plan | {'run_arguments': plan['run_arguments'] + ['--pre-arg=-width', '--pre-arg=1']}, self.opening, attempt)
        script = attempt / 'inputs/capture.cfg'; original = script.read_text()
        script.write_text(original.replace('wait 120', 'gl_levelmesh true; wait 1'))
        plan['inputs'][str(script)] = capture.digest(script)
        with self.assertRaisesRegex(ValueError, 'approved route'): gate.validate_plan(plan, self.opening, attempt)
        script.write_text(original); plan['inputs'][str(script)] = capture.digest(script)
        pathlib.Path(plan['completion_artifacts'][0]).write_bytes(b'historical screenshot')
        with self.assertRaisesRegex(ValueError, 'already exist'): gate.validate_plan(plan, self.opening, attempt)

    def test_no_repeat_attempt_or_fourth_success(self):
        attempt, plan = self.plan(True); self.control()
        self.state['attempts'] = [{'attempt_id': plan['attempt_id']}]; self.save()
        with self.assertRaisesRegex(ValueError, 'already recorded'): gate.validate_plan(plan, self.opening, attempt)
        self.state['attempts'] = [{'risky': True, 'case': plan['case'], 'classification': 'route-completed'}] * 3; self.save()
        with self.assertRaisesRegex(ValueError, 'saturated'): gate.validate_plan(plan, self.opening, attempt)
        self.state['attempts'] = [{'risky': False, 'case': plan['case'], 'classification': 'route-completed'}] * 3; self.save()
        gate.validate_plan(plan, self.opening, attempt)

    def coverage_fixture(self, records=2, omitted=0, writer=1, flushed=None, rotated=False):
        run = self.lane / 'fixture'; run.mkdir(exist_ok=True)
        lines = ['# CFX address bindings v1 run=fixture', '\t'.join(FIELDS)]
        for i in range(1, records + 1):
            row = [str(i), '0', '1', str(i), '0', '1', 'snapshot' if i == records and not omitted else 'bind',
                   '0x1000', '16', '0', '9', '0x42', '0', '1', 'device-teardown' if i == records and not omitted else 'buffer']
            lines.append('\t'.join(row))
        (run / 'address-bindings.tsv').write_text('\n'.join(lines) + '\n')
        detail = f'reason=device-teardown records={records} omitted={omitted} contended=0 writer_ok={writer} limit=32768 flushed={records if flushed is None else flushed} cutoff={0 if omitted else records}'
        (run / 'timeline.tsv').write_text('# CFX-002 trace v1 run=fixture' + (' (rotated tail)' if rotated else '') +
            '\ncolumns\n0\t1\t1\t0\t1\tpresent\taddress-binding-summary\t' + detail + '\t0\n')
        return run

    def test_bounded_prefix_is_explicit_limitation_but_writer_gap_is_failure(self):
        report = gate.capture_coverage(self.coverage_fixture(), 'fixture')
        self.assertTrue(report['address_complete_through_snapshot'])
        report = gate.capture_coverage(self.coverage_fixture(32768, 1234, rotated=True), 'fixture')
        self.assertFalse(report['address_complete_through_snapshot']); self.assertEqual(len(report['limitations']), 2)
        for options in ({'writer': 0}, {'flushed': 1}, {'omitted': 1}):
            with self.assertRaises(ValueError): gate.capture_coverage(self.coverage_fixture(**options), 'fixture')

    def test_failure_classification_never_uses_cap_as_proof_of_cause(self):
        image = self.lane / 'scene.png'; image.write_bytes(b'image')
        good = {'status': 'EXITED', 'exit_status': 0, 'failure': {'application_observation': None}}
        self.assertEqual(gate.classify(good, False, [image]), 'route-completed')
        image.unlink(); self.assertEqual(gate.classify(good, False, [image]), 'route-incomplete')
        self.assertEqual(gate.classify(good, True, []), 'correlated-TDR')
        self.assertEqual(gate.classify(good | {'failure': {'application_observation': 'VK_ERROR_DEVICE_LOST'}}, True, []), 'application-device-loss')
        self.assertEqual(gate.classify(good | {'status': 'TIMEOUT'}, False, []), 'watchdog-no-return')
        self.assertEqual(gate.classify(good, False, [], driver_fault=True), 'driver-fault-evidence')

    def test_one_target_reserves_count_restores_cache_and_demands_analysis(self):
        attempt, plan = self.plan(True); self.control()
        self.opening.update(health_since_utc='opening', baseline_boot_utc='same-boot'); self.save()
        (attempt / 'plan.json').write_text(json.dumps(plan))
        cache = self.lane / 'test-cache'; cache.mkdir(); (cache / 'pipelinecache.zdpc').write_bytes(b'prior global cache')
        health = {'pass': True, 'stop_reasons': [], 'windows': {'boot': 'same-boot', 'events': [], 'wer': []}}
        def child(*args, **kwargs):
            pending = json.loads((self.lane / 'state.json').read_text())
            self.assertEqual(pending['launches'], 15); self.assertEqual(pending['pending_attempt'], plan['attempt_id'])
            self.assertTrue((attempt / 'execution-start.json').is_file())
            self.assertFalse((cache / 'pipelinecache.zdpc').exists())
            run = attempt / 'runs/fixture'; run.mkdir(parents=True)
            (run / 'manifest.json').write_text(json.dumps({'run_id': 'fixture', 'status': 'EXITED', 'exit_status': 0,
                'failure': {'application_observation': None}, 'artifact_files': []}))
            pathlib.Path(plan['completion_artifacts'][0]).write_bytes(b'screenshot')
            (cache / 'pipelinecache.zdpc').write_bytes(b'new pipeline cache')
            return SimpleNamespace(returncode=0, stdout='captured', stderr='')
        with mock.patch.object(execute, 'check_lane', return_value=self.opening), \
             mock.patch.object(execute, 'collect', return_value=health), \
             mock.patch.object(execute, 'CACHE', cache), \
             mock.patch.object(execute.subprocess, 'check_output', return_value=plan['runner_source']), \
             mock.patch.object(execute.subprocess, 'run', side_effect=child), \
             mock.patch.object(execute, 'verify_completion', return_value=None), \
             mock.patch.object(execute, 'capture_coverage', return_value={'limitations': ['bounded startup prefix']}), \
             mock.patch.object(sys, 'argv', ['cfx010_execute', '--plan', str(attempt / 'plan.json'), '--launch']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute.main(), 0)
        state = json.loads((self.lane / 'state.json').read_text())
        self.assertEqual((state['launches'], state['loss_episodes']), (15, 2))
        self.assertEqual(state['analysis_pending'], plan['attempt_id']); self.assertIsNone(state['pending_attempt'])
        self.assertEqual((cache / 'pipelinecache.zdpc').read_bytes(), b'prior global cache')
        self.assertEqual(state['attempts'][0]['classification'], 'route-completed')
        self.assertTrue(json.loads((attempt / 'artifact-index.json').read_text())['files'])

    def test_safe_nv153_evidence_stops_without_claiming_confirmed_tdr(self):
        attempt, plan = self.plan(False)
        self.opening.update(health_since_utc='opening', baseline_boot_utc='same-boot'); self.save()
        (attempt / 'plan.json').write_text(json.dumps(plan)); cache = self.lane / 'test-cache'; cache.mkdir()
        before = {'pass': True, 'stop_reasons': [], 'windows': {'boot': 'same-boot', 'events': [], 'wer': []}}
        after = {'pass': True, 'stop_reasons': [], 'windows': {'boot': 'same-boot', 'events': [
            {'Provider': 'nvlddmkm', 'Id': 153, 'Time': '2099-01-01T00:00:00+00:00'}], 'wer': []}}
        def child(*args, **kwargs):
            run = attempt / 'runs/fixture'; run.mkdir(parents=True)
            (run / 'manifest.json').write_text(json.dumps({'run_id': 'fixture', 'status': 'EXITED', 'exit_status': 0,
                'failure': {'application_observation': None}, 'artifact_files': []}))
            pathlib.Path(plan['completion_artifacts'][0]).write_bytes(b'screenshot')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(execute, 'check_lane', return_value=self.opening), \
             mock.patch.object(execute, 'collect', side_effect=[before, after]), \
             mock.patch.object(execute, 'CACHE', cache), \
             mock.patch.object(execute.subprocess, 'check_output', return_value=plan['runner_source']), \
             mock.patch.object(execute.subprocess, 'run', side_effect=child), \
             mock.patch.object(execute, 'capture_coverage', return_value={'limitations': []}), \
             mock.patch.object(sys, 'argv', ['cfx010_execute', '--plan', str(attempt / 'plan.json'), '--launch']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute.main(), 1)
        state = json.loads((self.lane / 'state.json').read_text())
        self.assertEqual(state['status'], 'STOPPED'); self.assertEqual(state['loss_episodes'], 2)
        self.assertEqual(state['attempts'][0]['classification'], 'driver-fault-evidence')
        self.assertTrue((self.lane / 'STOP-LAUNCHES.txt').is_file())

    def test_completed_route_requires_actual_viewport_and_readable_correct_images(self):
        attempt, plan = self.plan()
        manifest = {'run': {'actual_resolution': '1264 x 681'}}
        run = attempt / 'runs/fixture'; run.mkdir(parents=True)
        console = run / 'stdout.log'; console.write_text('CONTROL_BEGIN\nCONTROL_COMPLETE\n')
        decoded = SimpleNamespace(size=(1264, 681), load=lambda: None)
        pillow = ModuleType('PIL'); pillow.Image = SimpleNamespace(open=lambda path: contextlib.nullcontext(decoded))
        with mock.patch.dict(sys.modules, {'PIL': pillow}):
            gate.verify_completion(manifest, plan, run, self.opening)
            for actual in ('1902 x 993', None, 'unavailable'):
                with self.assertRaisesRegex(ValueError, 'actual renderer resolution'):
                    gate.verify_completion({'run': {'actual_resolution': actual}}, plan, run, self.opening)
            decoded.size = (1, 1)
            with self.assertRaisesRegex(ValueError, 'screenshot dimensions'): gate.verify_completion(manifest, plan, run, self.opening)
            decoded.size = (1264, 681)
            def unreadable(): raise OSError('truncated image')
            decoded.load = unreadable
            with self.assertRaises(OSError): gate.verify_completion(manifest, plan, run, self.opening)
            decoded.load = lambda: None
            for contents in ('CONTROL_BEGIN\n', 'CONTROL_COMPLETE\nCONTROL_BEGIN\n'):
                console.write_text(contents)
                with self.assertRaisesRegex(ValueError, 'missing/out of order'):
                    gate.verify_completion(manifest, plan, run, self.opening)

    def drain_fixture(self):
        attempt, plan = self.plan(True)
        script = attempt / 'inputs/capture.cfg'
        original = 'echo CFX010_ROUTE_BEGIN; screenshot "phase1.png"; screenshot "phase2.png"; screenshot "phase3.png"; echo CFX010_PHASE4; map MAP24; screenshot "phase4.png"; wait 2; echo CFX010_ROUTE_COMPLETE; quit'
        profile = self.profile | {'map': 'MAP24', 'target_script_sha256': gate.script_text_hash(original)}
        p = self.lane / 'manual-missing-phase3-analysis.json'
        p.write_text(json.dumps({'analysis_complete': True, 'source_analysis_pending': False,
            'case': 'sunlust-champions', 'attempt_id': 'CFX10-TARGET-SUNLUST-001', 'conclusion': 'Deferred screenshot overwritten by immediate map action.',
            'missing_phase3_explained': True, 'repair_unchanged': True, 'original_target_script_sha256': profile['target_script_sha256'],
            'files': [self.record(self.evidence)]}))
        record = self.record(p)
        plan.update(case='sunlust-champions', analysis_prerequisite=record,
            capture_adjustment={'kind': 'deferred-screenshot-before-map-v1', 'diagnostic_wait_tics': 2,
                                'placement': 'after-third-screenshot-before-phase4-map', 'analysis': record})
        adjusted = original.replace('; echo CFX010_PHASE4;', '; wait 2; echo CFX010_PHASE4;')
        script.write_text(adjusted)
        return plan, profile, script, original, adjusted

    def test_reviewed_sunlust_drain_preserves_every_other_command_and_advances_proof(self):
        plan, profile, script, original, adjusted = self.drain_fixture()
        self.assertEqual(gate.approved_script_hash(plan, profile, script), profile['target_script_sha256'])
        next_analysis = self.lane / 'adjusted-success-analysis.json'
        next_analysis.write_text(json.dumps({'analysis_complete': True, 'source_analysis_pending': False,
            'attempt_id': 'CFX10-TARGET-SUNLUST-002', 'conclusion': 'Adjusted route completed; unchanged renderer.',
            'capture_adjustment_authorization': plan['capture_adjustment']['analysis'], 'files': [self.record(self.evidence)]}))
        self.assertEqual(gate.approved_script_hash(plan | {'analysis_prerequisite': self.record(next_analysis)}, profile, script), profile['target_script_sha256'])
        for changed in (adjusted.replace('wait 2; echo CFX010_PHASE4', 'wait 3; echo CFX010_PHASE4'),
                        adjusted.replace('wait 2; echo CFX010_PHASE4', 'wait 2; wait 2; echo CFX010_PHASE4'),
                        adjusted.replace('map MAP24', 'map MAP30'), adjusted.replace('wait 2; echo CFX010_ROUTE_COMPLETE', 'wait 3; echo CFX010_ROUTE_COMPLETE')):
            script.write_text(changed)
            with self.assertRaises(ValueError): gate.approved_script_hash(plan, profile, script)

    def test_drain_cannot_be_used_without_exact_manual_explanation_or_on_another_case(self):
        plan, profile, script, original, adjusted = self.drain_fixture()
        for changed in ({'case': 'dbp50-original'}, {'risky': False}, {'analysis_prerequisite': self.opening['previous_epoch']['analysis']},
                        {'capture_adjustment': plan['capture_adjustment'] | {'diagnostic_wait_tics': 3}},
                        {'capture_adjustment': plan['capture_adjustment'] | {'placement': 'after-phase1'}}):
            with self.assertRaises(ValueError): gate.approved_script_hash(plan | changed, profile, script)
        self.assertNotEqual(gate.approved_script_hash(plan | {'capture_adjustment': None}, profile, script), profile['target_script_sha256'])
        p = pathlib.Path(plan['capture_adjustment']['analysis']['path'])
        original_proof = json.loads(p.read_text())
        for changed in ({'missing_phase3_explained': False}, {'repair_unchanged': False}, {'original_target_script_sha256': '0' * 64}, {'analysis_complete': False}):
            p.write_text(json.dumps(original_proof | changed))
            record = self.record(p)
            with self.assertRaises(ValueError): gate.approved_script_hash(plan | {'analysis_prerequisite': record,
                'capture_adjustment': plan['capture_adjustment'] | {'analysis': record}}, profile, script)

    def stopped_phase(self):
        phase = self.root / 'stopped-cfx010'; phase.mkdir()
        for profile in self.opening['case_profiles'].values():
            profile['config_source'] = {'path': str(self.evidence), 'sha256': capture.digest(self.evidence)}
        old_opening = json.loads(json.dumps(self.opening))
        old = {'status': 'STOPPED', 'launches': 21, 'loss_episodes': 2, 'pending_attempt': None,
               'analysis_pending': 'confounded-target', 'last_informative_attempt': 'confounded-target',
               'attempts': [{'attempt_id': 'confounded-target', 'classification': 'watchdog-no-return'}]}
        data = {'opening': old_opening, 'state': old,
                'analysis': {'analysis_complete': True, 'source_analysis_pending': False, 'attempt_id': 'confounded-target',
                    'conclusion': 'Operator focus delay, completed normal exit, healthy recovery; preserve STOP.',
                    'operator_focus_confounded': True, 'normal_exit_verified': True, 'hardware_recovery_verified': True,
                    'stop_not_renderer_hang': True, 'files': [self.record(self.evidence)]},
                'artifact_index': {'files': [self.record(self.evidence)]}}
        prior = {}
        for name, value in data.items():
            p = phase / (name + '.json'); p.write_text(json.dumps(value)); prior[name] = self.record(p)
        stop = phase / 'STOP-LAUNCHES.txt'; stop.write_bytes(b'preserve timeout/focus stop')
        self.opening.update(prior_phase=prior, foreground_policy='one-shot-verified-monitored-v1')
        self.opening['historical_guards'].append(self.record(stop))
        self.state.update(launches=21, loss_episodes=2, attempts=old['attempts'], last_analysis=prior['analysis'])
        self.save()
        return prior

    def test_new_foreground_phase_preserves_stop_counts_attempts_and_actual_profiles(self):
        prior = self.stopped_phase(); self.check()
        for changes in ({'launches': 20}, {'attempts': []}):
            old = self.state.copy(); self.state.update(changes); self.save()
            with self.assertRaises(ValueError): self.check()
            self.state = old
        self.save()
        self.opening['case_profiles']['sunlust-champions']['settings'] = self.settings | {'vsync': True}; self.save()
        with self.assertRaisesRegex(ValueError, 'historical renderer'): self.check()
        self.opening['case_profiles']['sunlust-champions']['settings'] = self.settings; self.save()
        p = pathlib.Path(prior['analysis']['path']); data = json.loads(p.read_text()); data['stop_not_renderer_hang'] = False
        p.write_text(json.dumps(data)); prior['analysis'] = self.record(p); self.save()
        with self.assertRaisesRegex(ValueError, 'operator-focus'): self.check()

    def test_foreground_policy_requires_explicit_flag_and_control_reuses_content_hash_only(self):
        self.stopped_phase()
        attempt, plan = self.plan(False)
        with self.assertRaisesRegex(ValueError, 'foreground proof'): gate.validate_plan(plan, self.opening, attempt)
        gate.validate_plan(plan | {'run_arguments': plan['run_arguments'] + ['--verify-foreground']}, self.opening, attempt)
        self.control()
        copied = self.lane / 'isolated-copy.wad'; copied.write_bytes(self.iwad.read_bytes())
        self.opening['case_profiles']['dbp50-original']['content_order'][0] = {'role': 'IWAD', **self.record(copied)}
        gate.require_control(self.state, self.opening, plan)
        copied.write_bytes(b'changed'); self.opening['case_profiles']['dbp50-original']['content_order'][0] = {'role': 'IWAD', **self.record(copied)}
        with self.assertRaises(ValueError): gate.require_control(self.state, self.opening, plan)

    def test_empty_failed_dump_is_explicit_index_exclusion_not_successful_capture(self):
        attempt = self.lane / 'dump-index'; attempt.mkdir()
        dump = attempt / 'process.dmp'; dump.write_bytes(b'')
        trace = attempt / 'timeline.tsv'; trace.write_bytes(b'usable')
        manifest = {'status': 'TIMEOUT', 'failure': {'watchdog_action': {'status': 'failed'}}}
        original_digest = execute.digest
        def unreadable_empty(path):
            if path == dump: raise PermissionError('empty comsvcs dump cannot be read')
            return original_digest(path)
        with mock.patch.object(execute, 'digest', side_effect=unreadable_empty):
            index = execute.artifact_index(attempt, manifest)
            timed = dict(manifest, failure={'watchdog_action': {'status': 'dump timeout'}})
            self.assertEqual(execute.artifact_index(attempt, timed)['excluded_failed_files'][0]['reason'],
                             'failed-empty-watchdog-dump')
        self.assertEqual(index['excluded_failed_files'][0]['reason'], 'failed-empty-watchdog-dump')
        gate.verify_files(index, 'usable index')
        self.assertEqual(gate.classify(manifest, False, []), 'watchdog-no-return')
        dump.write_bytes(b'nonempty dump')
        with self.assertRaises(ValueError): gate.verify_files(index, 'usable index')

    def test_one_foreground_request_and_bounded_monitor_no_input_calls(self):
        api = SimpleNamespace(windows=lambda pid: [7], activate=mock.Mock(return_value=True), foreground=lambda: 7,
            install_events=lambda pid, callback: 'hooks', pump_events=lambda: None, remove_events=mock.Mock(),
            owner=lambda window: (42, 1), inspect=lambda window: {'alive': True, 'visible': True, 'minimized': False,
                'thread_info_ok': True, 'in_move_size': False})
        def fake_thread(target, daemon):
            def start():
                target.__self__.report['event_hooks_installed'] = True; target.__self__.ready.set()
            return SimpleNamespace(start=start, join=lambda timeout: None, is_alive=lambda: False)
        proc = SimpleNamespace(pid=42, poll=lambda: None)
        with mock.patch.object(foreground.threading, 'Thread', side_effect=fake_thread), mock.patch.object(foreground.time, 'time', return_value=.05):
            session = foreground.ForegroundSession(proc, api=api)
            session.stop.wait = mock.Mock(side_effect=[False, True])
            session.monitor(); report = session.finish()
        self.assertEqual(api.activate.call_count, 1); self.assertTrue(report['verified']); self.assertEqual(report['checks'], 1)
        timeline = self.lane / 'focus-timeline.tsv'
        timeline.write_text('# fixture\ncolumns\n100\t1\t1\t0\t0\tstartup\tframe\tbegin\t0\n')
        foreground.verify(report, timeline)
        for changed in ({'verified_at_ms': 101}, {'checks': 0}, {'events': [{'kind': 'focus-or-modal-interference', 'ms': 101}]}):
            with self.assertRaises(ValueError): foreground.verify(report | changed, timeline)
        self.assertEqual(api.remove_events.call_count, 1)
        # A restored foreground sampled as normal cannot erase a transient native event.
        session.receive_event(3, 8, 75, 150); session.receive_event(10, 7, 80, 150)
        self.assertEqual(session.report['events'][0]['ms'], 75)
        with self.assertRaises(ValueError): foreground.verify(session.report, timeline)

    def test_failed_or_late_foreground_start_stops_child_immediately_without_watchdog(self):
        timeline = self.lane / 'startup-timeline.tsv'
        timeline.write_text('# fixture\ncolumns\n100\t1\t1\t0\t0\tstartup\tframe\tbegin\t0\n')
        proc = SimpleNamespace(poll=mock.Mock(return_value=None), kill=mock.Mock(), wait=mock.Mock(return_value=-1))
        for report in ({'verified': False}, {'verified': True, 'event_hooks_installed': True, 'verified_at_ms': 101}):
            self.assertIsNotNone(foreground.abort_failed_start(proc, report, timeline))
        self.assertEqual(proc.kill.call_count, 2); proc.wait.assert_called_with(timeout=15)
        proc.kill.reset_mock()
        self.assertIsNone(foreground.abort_failed_start(proc, {'verified': True, 'event_hooks_installed': True, 'verified_at_ms': 99}, timeline))
        proc.kill.assert_not_called()

    def test_native_focus_event_time_cannot_be_relabelled_as_later_teardown(self):
        timeline = self.lane / 'event-timeline.tsv'
        timeline.write_text('# fixture\ncolumns\n100\t1\t1\t0\t0\tstartup\tframe\tbegin\t0\n'
            '150\t1\t1\t0\t0\tstartup\taddress-binding-summary\treason=device-teardown records=0\t0\n')
        report = {'verified': True, 'focus_requests': 1, 'pid': 42, 'foreground_pid': 42, 'monitor_stopped': True,
            'event_hooks_installed': True, 'event_hooks_removed': True, 'checks': 1, 'verified_at_ms': 50,
            'events': [{'kind': 'native-foreground-change', 'ms': 120, 'delivered_ms': 180, 'alive': False, 'visible': False}]}
        with self.assertRaises(ValueError): foreground.verify(report, timeline)
        report['events'][0]['ms'] = 160
        foreground.verify(report, timeline)

    def test_single_foreground_request_settles_transient_zero_without_retry_or_input(self):
        def fake_thread(target, daemon):
            def start():
                target.__self__.report['event_hooks_installed'] = True; target.__self__.ready.set()
            return SimpleNamespace(start=start, join=lambda timeout: None, is_alive=lambda: False)
        proc = SimpleNamespace(pid=42, poll=lambda: None)
        normal = {'alive': True, 'visible': True, 'minimized': False, 'thread_info_ok': True, 'in_move_size': False}
        api = SimpleNamespace(windows=lambda pid: [7], activate=mock.Mock(return_value=False),
            foreground=mock.Mock(side_effect=[0, 7]), owner=lambda window: (42 if window else 0, 1), inspect=lambda window: normal)
        with mock.patch.object(foreground.threading, 'Thread', side_effect=fake_thread):
            session = foreground.ForegroundSession(proc, api=api)
        self.assertTrue(session.report['verified']); self.assertFalse(session.report['set_foreground_returned'])
        self.assertEqual(len(session.report['readback_observations']), 2); api.activate.assert_called_once_with(7)
        for changed in ({'foreground': lambda: 0}, {'owner': lambda window: (43, 1)},
                        {'inspect': lambda window: normal | {'in_move_size': True}},
                        {'inspect': lambda window: normal | {'minimized': True}}):
            api.foreground = lambda: 7; api.owner = lambda window: (42, 1); api.inspect = lambda window: normal
            for name, value in changed.items(): setattr(api, name, value)
            with mock.patch.object(foreground.threading, 'Thread', side_effect=fake_thread):
                failed = foreground.ForegroundSession(proc, api=api)
            self.assertFalse(failed.report['verified']); self.assertLessEqual(len(failed.report['readback_observations']), 26)
            self.assertEqual(failed.report['focus_requests'], 1)

    def test_host_abort_is_typed_invalid_qualification_not_game_crash(self):
        aborted = {'status': 'HOST_ABORT', 'exit_status': 1, 'failure': {'application_observation': None}}
        self.assertEqual(gate.classify(aborted, False, []), 'invalid-host-activation')
        self.assertEqual(gate.classify(aborted, True, []), 'correlated-TDR')

    def test_host_abort_metadata_explains_forced_exit_and_preserves_real_errors(self):
        trace, out, err = (self.root / name for name in ('trace.tsv', 'stdout.log', 'stderr.log'))
        for path in (trace, out, err): path.write_text('')
        abort = ('owned foreground startup proof failed', 1)
        data = capture.failure_metadata(trace, out, err, False, 1, host_abort=abort)
        self.assertEqual(data, {'application_observation': None, 'first_observed_failure': abort[0]})
        self.assertEqual(capture.failure_metadata(trace, out, err, False, 1)['application_observation'],
                         'nonzero application exit; inspect stdout/stderr')
        for text, code, expected in (('1\t1\t0\t0\t0\tstartup\tvk-error\tvkCreateDevice\t-4\n', 1, 'VK_ERROR_DEVICE_LOST'),
                                     ('vk-error other failure', 1, 'other Vulkan error'),
                                     ('', 0xC0000005, 'application CPU exception status; inspect Windows Application event')):
            trace.write_text(text)
            data = capture.failure_metadata(trace, out, err, False, code, host_abort=abort)
            self.assertEqual(data['application_observation'], expected); self.assertEqual(data['first_observed_failure'], expected)
        trace.write_text('')
        self.assertEqual(capture.failure_metadata(trace, out, err, True, 1, safe_stop=True),
                         {'application_observation': 'controlled safe stop', 'first_observed_failure': None})

    def test_stopped_startup_host_abort_requires_indexed_pre_frame_healthy_proof(self):
        prior = self.stopped_phase(); phase = pathlib.Path(prior['state']['path']).parent
        attempt = phase / 'aborted'; run = attempt / 'runs' / 'run'; run.mkdir(parents=True)
        manifest_path = run / 'manifest.json'; timeline = run / 'timeline.tsv'; health = attempt / 'health-after.json'
        manifest = {'status': 'HOST_ABORT', 'failure': {'watchdog_action': None, 'host_abort': {'bounded_child_stop': True}},
            'environment': {'foreground': {'verified': False, 'focus_requests': 1, 'event_hooks_installed': True,
                'event_hooks_removed': True, 'monitor_stopped': True}}}
        manifest_path.write_text(json.dumps(manifest)); health.write_text(json.dumps({'pass': True}))
        timeline.write_text('# fixture\ncolumns\n100\t1\t0\t0\t0\tstartup\tcapability\tdebug-utils-enabled\t0\n')
        oldpath = pathlib.Path(prior['state']['path']); old = json.loads(oldpath.read_text())
        old['attempts'][0].update(classification='application-error', manifest=str(manifest_path),
                                  loss_episode=False, correlated_nv153=[]); oldpath.write_text(json.dumps(old))
        self.state['attempts'] = old['attempts']; prior['state'] = self.record(oldpath)
        analysis_path = pathlib.Path(prior['analysis']['path']); analysis = json.loads(analysis_path.read_text())
        analysis.pop('operator_focus_confounded'); analysis.pop('normal_exit_verified')
        analysis.update(host_startup_abort_verified=True, no_render_frame_or_submission_verified=True, readback_only_settle_justified=True)
        analysis_path.write_text(json.dumps(analysis)); prior['analysis'] = self.record(analysis_path)
        index_path = pathlib.Path(prior['artifact_index']['path'])
        def refresh():
            index_path.write_text(json.dumps({'files': [self.record(p) for p in (manifest_path, timeline, health)]}))
            prior['artifact_index'] = self.record(index_path); self.save()
        refresh(); self.check()
        for change in ({'loss_episode': True}, {'correlated_nv153': [{'Id': 153}]}):
            changed = dict(old['attempts'][0]); old['attempts'][0].update(change)
            oldpath.write_text(json.dumps(old)); prior['state'] = self.record(oldpath); self.state['attempts'] = old['attempts']; self.save()
            with self.assertRaisesRegex(ValueError, 'GPU/driver fault'): self.check()
            old['attempts'][0] = changed
        oldpath.write_text(json.dumps(old)); prior['state'] = self.record(oldpath); self.state['attempts'] = old['attempts']; self.save()
        manifest['failure']['application_observation'] = 'VK_ERROR_DEVICE_LOST'; manifest_path.write_text(json.dumps(manifest)); refresh()
        with self.assertRaisesRegex(ValueError, 'pre-frame'): self.check()
        manifest['failure']['application_observation'] = None; manifest_path.write_text(json.dumps(manifest))
        for event in ('device-lost-observed', 'vk-error'):
            timeline.write_text('# fixture\ncolumns\n100\t1\t0\t0\t0\tstartup\t' + event + '\tobserved\t0\n'); refresh()
            with self.assertRaisesRegex(ValueError, 'pre-frame'): self.check()
        timeline.write_text('# fixture\ncolumns\n100\t1\t0\t0\t0\tstartup\tresult\tvkCreateDevice\t-4\n'); refresh()
        with self.assertRaisesRegex(ValueError, 'pre-frame'): self.check()
        timeline.write_text('# fixture\ncolumns\n100\t1\t1\t0\t0\tstartup\tframe\tbegin\t0\n'); refresh()
        with self.assertRaisesRegex(ValueError, 'pre-frame'): self.check()
        timeline.write_text('# fixture\ncolumns\n100\t1\t0\t0\t0\tstartup\tcapability\tdebug-utils-enabled\t0\n')
        health.write_text(json.dumps({'pass': False})); refresh()
        with self.assertRaisesRegex(ValueError, 'pre-frame'): self.check()


if __name__ == '__main__': unittest.main()
