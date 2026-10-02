"""CPU gates for #105 cross-case qualification; historical scopes remain closed."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

from cfx_capture import ROOT, digest, verified_analysis, verified_record
from cfx008_gate import activation, mesh_state
from cfx_address_correlate import read_bindings

BASELINE = 'd0789c88f88049116022e7b904026cddeaba8ac4'
RENDERER = '3916c82f2f87f0173e1b9ad748faac19365a5415'
CASES = {'dbp50-original': 'MAP08', 'dbp50-v1.2': 'MAP08', 'sunlust-champions': 'MAP24'}


def settings_key(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def script_hash(script):
    """Only per-attempt screenshot paths vary; all executable commands stay fixed."""
    return script_text_hash(script.read_text(encoding='utf-8'))


def script_text_hash(text):
    ordinal = iter(range(64))
    text = re.sub(r'(\bscreenshot\s+)"[^"\n]+"', lambda m: m[1] + '"@CFX_OUTPUT_' + str(next(ordinal)) + '@"', text)
    return hashlib.sha256(text.encode()).hexdigest()


def approved_script_hash(plan, profile, script):
    """One reviewed diagnostic drain prevents a deferred screenshot/map collision."""
    adjustment = plan.get('capture_adjustment')
    if adjustment is None:
        return script_hash(script)
    if (plan.get('case') != 'sunlust-champions' or plan.get('risky') is not True or
            not isinstance(adjustment, dict) or adjustment.get('kind') != 'deferred-screenshot-before-map-v1' or
            type(adjustment.get('diagnostic_wait_tics')) is not int or adjustment['diagnostic_wait_tics'] != 2 or
            adjustment.get('placement') != 'after-third-screenshot-before-phase4-map'):
        raise ValueError('CFX010 only the reviewed Sunlust target screenshot drain is allowed')
    record = adjustment.get('analysis')
    explanation = verified_analysis(record)
    if (explanation.get('case') != 'sunlust-champions' or explanation.get('attempt_id') != 'CFX10-TARGET-SUNLUST-001' or
            explanation.get('missing_phase3_explained') is not True or explanation.get('repair_unchanged') is not True or
            explanation.get('original_target_script_sha256') != profile['target_script_sha256']):
        raise ValueError('CFX010 screenshot drain requires its complete original missing-phase3 explanation')
    prerequisite = plan.get('analysis_prerequisite')
    previous = verified_analysis(prerequisite)
    if prerequisite != record and previous.get('capture_adjustment_authorization') != record:
        raise ValueError('CFX010 drain authorization must match the registered analysis prerequisite')
    text = script.read_text(encoding='utf-8')
    screenshots = list(re.finditer(r'\bscreenshot\s+"[^"\n]+"', text))
    suffix = '; wait 2; echo CFX010_PHASE4; map MAP24'
    if len(screenshots) != 4 or not text[screenshots[2].end():].startswith(suffix):
        raise ValueError('CFX010 exact two-tic drain must follow the third screenshot immediately before phase4/map')
    end = screenshots[2].end()
    restored = text[:end] + text[end:].replace('; wait 2;', ';', 1)
    if script_text_hash(restored) != profile['target_script_sha256']:
        raise ValueError('CFX010 screenshot drain may not change another historical command')
    return script_text_hash(restored)


def verify_files(data, description):
    if not isinstance(data.get('files'), list) or not data['files']:
        raise ValueError(description + ' files missing')
    for item in data['files']:
        if not item.get('sha256') or digest(pathlib.Path(item['path'])) != item['sha256']:
            raise ValueError(description + ' evidence changed')
    for item in data.get('excluded_failed_files', []):
        path = pathlib.Path(item['path'])
        if (path.name != 'process.dmp' or item.get('bytes') != 0 or item.get('sha256') is not None or
                item.get('reason') != 'failed-empty-watchdog-dump' or not path.is_file() or path.stat().st_size != 0):
            raise ValueError(description + ' invalid failed-file exclusion')


def content_identity(content):
    return [{'role': c['role'], 'sha256': c['sha256']} for c in content]


def check_prior_phase(lane, state, guard_map):
    prior = lane.get('prior_phase')
    if not prior: return
    old_opening = verified_record(prior.get('opening'), 'CFX010 prior phase opening')
    old = verified_record(prior.get('state'), 'CFX010 stopped prior phase')
    if (old_opening.get('issue') != 105 or old.get('status') != 'STOPPED' or old.get('pending_attempt') or
            lane.get('foreground_policy') != 'one-shot-verified-monitored-v1'):
        raise ValueError('CFX010 continuation requires frozen stopped phase and foreground policy')
    analysis = verified_analysis(prior.get('analysis'))
    if (analysis.get('attempt_id') != old.get('last_informative_attempt') or any(analysis.get(k) is not True for k in (
            'operator_focus_confounded', 'normal_exit_verified', 'hardware_recovery_verified', 'stop_not_renderer_hang'))):
        raise ValueError('CFX010 stopped phase needs complete operator-focus/recovery explanation')
    verify_files(verified_record(prior.get('artifact_index'), 'CFX010 prior usable index'), 'CFX010 prior usable index')
    preserved = list(old_opening.get('historical_guards', []))
    stop = pathlib.Path(prior['state']['path']).resolve().parent / 'STOP-LAUNCHES.txt'
    preserved.append({'path': str(stop), 'sha256': digest(stop)})
    if any(not g.get('sha256') or guard_map.get(str(pathlib.Path(g['path']).resolve())) != g['sha256'] for g in preserved):
        raise ValueError('CFX010 prior phase STOP set must remain preserved')
    if any(type(old.get(k)) is not int or old[k] < 0 or state[k] < old[k] for k in ('launches', 'loss_episodes')):
        raise ValueError('CFX010 stopped phase counts must carry forward')
    for record in old.get('attempts', []):
        if record not in state.get('attempts', []):
            raise ValueError('CFX010 previous attempt records must remain carried')
    if old_opening.get('accepted_baseline') != lane['accepted_baseline'] or old_opening.get('renderer_source') != lane['renderer_source']:
        raise ValueError('CFX010 continuation renderer changed')
    for case, profile in lane['case_profiles'].items():
        before = old_opening['case_profiles'][case]
        if (any(profile.get(k) != before.get(k) for k in ('map', 'settings', 'config_values', 'route', 'pre_arguments',
                'target_script_sha256', 'control_script_sha256', 'control_completion_markers')) or
                content_identity(profile['content_order']) != content_identity(before['content_order']) or
                profile['config_source']['sha256'] != before['config_source']['sha256']):
            raise ValueError('CFX010 foreground continuation may not change historical renderer/route/content identity')


def check_lane(path, run_root, exe):
    if not path or not path.is_file():
        raise ValueError('CFX010 opening missing')
    lane = json.loads(path.read_text(encoding='utf-8'))
    if (lane.get('schema'), lane.get('issue'), lane.get('status'), lane.get('testing_policy'),
            lane.get('accepted_baseline'), lane.get('renderer_source')) != (
            'cfx-010-lane-v1', 105, 'OPEN', 'supervised-adaptive-cross-case-20261002', BASELINE, RENDERER):
        raise ValueError('CFX010 requires the separate supervised #105 accepted PR104 scope')
    if 'max_launches' in lane or 'max_loss_episodes' in lane:
        raise ValueError('CFX010 old finite ceilings remain in their historical ledgers')
    if not run_root.resolve().is_relative_to(path.parent.resolve()):
        raise ValueError('CFX010 run root outside new scope')
    if any((p / 'STOP-LAUNCHES.txt').exists() for p in (run_root.resolve(), *run_root.resolve().parents)):
        raise ValueError('CFX010 active STOP guard')
    guards = lane.get('historical_guards', [])
    guard_map = {str(pathlib.Path(g['path']).resolve()): g['sha256'] for g in guards}
    if len(guards) < 16 or len(guard_map) != len(guards):
        raise ValueError('CFX010 all16 distinct historical guards required')
    for item in guards:
        if not item.get('sha256') or digest(pathlib.Path(item['path'])) != item['sha256']:
            raise ValueError('CFX010 historical guard changed')
    prior = lane.get('previous_epoch', {})
    old_opening = verified_record(prior.get('opening'), 'CFX010 previous opening')
    old_state = verified_record(prior.get('state'), 'CFX010 previous state')
    if (old_opening.get('issue') != 102 or old_state.get('status') != 'VALIDATION_SATURATED' or
            old_state.get('pending_attempt') or old_state.get('analysis_pending') or
            old_state.get('launches') != 14 or old_state.get('loss_episodes') != 2):
        raise ValueError('CFX010 requires frozen CFX009 saturation14/2')
    old_stop = pathlib.Path(prior['state']['path']).resolve().parent / 'STOP-LAUNCHES.txt'
    preserved = list(old_opening.get('historical_guards', []))
    preserved.append({'path': str(old_stop), 'sha256': digest(old_stop)})
    if any(not g.get('sha256') or guard_map.get(str(pathlib.Path(g['path']).resolve())) != g['sha256'] for g in preserved):
        raise ValueError('CFX010 previous STOP set must remain preserved')
    analysis = verified_analysis(prior.get('analysis'))
    if analysis.get('attempt_id') != old_state.get('last_informative_attempt'):
        raise ValueError('CFX010 previous final analysis mismatch')
    verify_files(verified_record(prior.get('artifact_index'), 'CFX010 previous index'), 'previous index')
    proof = verified_record(prior.get('control_proof'), 'CFX010 previous control')
    if proof.get('accepted') is not True or proof.get('renderer_source') != RENDERER or proof.get('retain_replaced_lightmaps') is not False:
        raise ValueError('CFX010 accepted retention-OFF diagnostics proof missing')
    verify_files(proof, 'previous control')
    verified_record(prior.get('closure_proof'), 'CFX010 previous closure')
    equivalent = verified_record(lane.get('source_equivalence'), 'CFX010 source equivalence')
    if (equivalent.get('accepted_baseline'), equivalent.get('renderer_source'), equivalent.get('renderer_source_equivalent')) != (BASELINE, RENDERER, True):
        raise ValueError('CFX010 source equivalence assertion missing')
    diff = subprocess.run(['git', 'diff', '--exit-code', RENDERER, BASELINE, '--', 'src', 'libraries'], cwd=ROOT, capture_output=True)
    if diff.returncode != 0:
        raise ValueError('CFX010 accepted source/library equivalence changed')
    build = verified_record(lane.get('build_proof'), 'CFX010 build proof')
    if (build.get('source_sha') != RENDERER or build.get('exe_sha256') != lane.get('exe_sha256') or
            build.get('pdb_sha256') != lane.get('pdb_sha256') or not lane.get('runtime_files') or
            build.get('runtime_files') != lane['runtime_files']):
        raise ValueError('CFX010 build/runtime identity mismatch')
    for binary, key in ((exe, 'exe_sha256'), (exe.with_suffix('.pdb'), 'pdb_sha256')):
        if not lane.get(key) or digest(binary) != lane[key]:
            raise ValueError('CFX010 EXE/PDB changed')
    for name, item in lane['runtime_files'].items():
        if pathlib.Path(name).name != name or not item.get('sha256') or digest(exe.parent / name) != item['sha256']:
            raise ValueError('CFX010 runtime changed')
    profiles = lane.get('case_profiles', {})
    if set(profiles) != set(CASES):
        raise ValueError('CFX010 three distinct case profiles required')
    for case, profile in profiles.items():
        if (profile.get('map') != CASES[case] or not profile.get('settings') or not profile.get('config_values') or
                not profile.get('route') or not profile.get('content_order') or not profile.get('historical_incident_ids') or
                not isinstance(profile.get('known_differences'), list) or not isinstance(profile.get('pre_arguments'), list) or
                not profile.get('route', {}).get('completion_markers') or not profile.get('control_completion_markers') or
                not all(re.fullmatch('[0-9a-f]{64}', profile.get(k, '')) for k in ('target_script_sha256', 'control_script_sha256'))):
            raise ValueError('CFX010 case identity/settings/route/history incomplete')
    state = json.loads((path.parent / 'state.json').read_text(encoding='utf-8'))
    if (state.get('status') != 'OPEN' or any(type(state.get(k)) is not int or state[k] < old_state[k]
            for k in ('launches', 'loss_episodes')) or state['loss_episodes'] > state['launches']):
        raise ValueError('CFX010 cumulative counts must carry14/2 forward')
    check_prior_phase(lane, state, guard_map)
    return lane


def arguments(argv):
    ap = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    for name in ('exe', 'run-root', 'iwad', 'config', 'pipeline-cache', 'shader-cache', 'map', 'mode',
                 'timeout', 'resolution', 'cap-vsync-msaa', 'skill', 'seed', 'camera', 'cfx010-lane-plan'):
        ap.add_argument('--' + name)
    for name in ('pwad', 'addon', 'pre-arg', 'arg'):
        ap.add_argument('--' + name, action='append', default=[])
    for name in ('approved-cfx010', 'resource-trace', 'address-bindings', 'launch', 'isolate-workdir', 'verify-foreground'):
        ap.add_argument('--' + name, action='store_true')
    return ap.parse_args(argv)


def validate_plan(plan, opening, attempt, *, reservation=False):
    if (plan.get('schema'), plan.get('issue'), plan.get('status'), plan.get('renderer_source')) != (
            'cfx-010-attempt-v1', 105, 'PLANNED', RENDERER):
        raise ValueError('CFX010 attempt identity missing')
    if type(plan.get('risky')) is not bool or not re.fullmatch(r'[A-Za-z0-9_-]+', plan.get('attempt_id', '')):
        raise ValueError('CFX010 attempt/risk identity invalid')
    if any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in ('discriminator', 'hypothesis', 'single_change')) or not plan.get('predicted_outcomes'):
        raise ValueError('CFX010 concrete causal question/change/predictions required')
    profile = opening['case_profiles'].get(plan.get('case'))
    if not profile or plan.get('settings') != profile['settings'] or plan.get('route') != profile['route']:
        raise ValueError('CFX010 planned case/settings/route changed')
    state = json.loads((attempt.parent / 'state.json').read_text(encoding='utf-8'))
    if state.get('analysis_pending') or (state.get('pending_attempt') and not reservation):
        raise ValueError('CFX010 previous attempt or analysis pending')
    if not reservation and (attempt / 'execution-start.json').exists():
        raise ValueError('CFX010 attempt already used')
    prior_state = verified_record(opening['previous_epoch']['state'], 'CFX010 previous state')
    if any(a.get('attempt_id') == plan['attempt_id'] for a in state.get('attempts', []) + prior_state.get('attempts', [])):
        raise ValueError('CFX010 attempt ID already recorded')
    if plan['risky']:
        registered = state.get('last_analysis') or opening['previous_epoch']['analysis']
        if plan.get('analysis_prerequisite') != registered:
            raise ValueError('CFX010 risky plan must name registered complete analysis')
        analysis = verified_analysis(registered)
        if state.get('last_informative_attempt') and analysis.get('attempt_id') != state['last_informative_attempt']:
            raise ValueError('CFX010 analysis does not cover last target')
        require_control(state, opening, plan)
        done = sum(a.get('risky') is True and a.get('case') == plan['case'] and a.get('classification') == 'route-completed' for a in state.get('attempts', []))
        if done >= 3:
            raise ValueError('CFX010 case success validation saturated at three')
    a = arguments(plan['run_arguments'])
    if a.verify_foreground != (opening.get('foreground_policy') == 'one-shot-verified-monitored-v1'):
        raise ValueError('CFX010 foreground proof must match its new continuation policy')
    if (a.mode != 'capture' or not a.approved_cfx010 or not a.resource_trace or not a.address_bindings or
            not a.launch or not a.isolate_workdir or not 1 <= int(a.timeout or 0) <= 60 or
            pathlib.Path(a.exe or '').resolve() != pathlib.Path(plan['exe']).resolve() or
            pathlib.Path(a.run_root or '').resolve() != attempt / 'runs' or
            pathlib.Path(a.cfx010_lane_plan or '').resolve() != attempt.parent / 'lane-opening.json'):
        raise ValueError('CFX010 exact capture/address/isolated watchdog arguments required')
    expected_content = profile['content_order'] if plan['risky'] else profile.get('control_content_order', [profile['content_order'][0]])
    actual = [{'role': role, 'path': str(pathlib.Path(p).resolve()), 'sha256': digest(pathlib.Path(p))}
              for role, paths in (('IWAD', [a.iwad]), ('PWAD', a.pwad), ('addon', a.addon)) for p in paths]
    expected = [{'role': c['role'], 'path': str(pathlib.Path(c['path']).resolve()), 'sha256': c['sha256']} for c in expected_content]
    if actual != expected or a.map != (profile['map'] if plan['risky'] else profile.get('control_map', 'MAP01')):
        raise ValueError('CFX010 content/load order/map differs from case')
    if plan['risky'] and any(getattr(a, k) != profile['route'].get(k) for k in ('skill', 'seed', 'camera')):
        raise ValueError('CFX010 skill/seed/camera differs from route')
    config = pathlib.Path(a.config or '').resolve()
    script = attempt / 'inputs/capture.cfg'
    if config != attempt / 'inputs/vkdoom.ini' or not config.is_file() or not script.is_file():
        raise ValueError('CFX010 writable config/script must belong to new attempt')
    values = dict(re.findall(r'^([^\s=\[;#]+)=(.*?)\r?$', config.read_text(encoding='utf-8'), re.M))
    if any(values.get(k) != str(v) for k, v in profile['config_values'].items()):
        raise ValueError('CFX010 config differs from declared renderer settings')
    if a.arg != ['+exec', str(script)]:
        raise ValueError('CFX010 console arguments must be only the approved attempt script')
    expected_pre = [s.replace('@ATTEMPT@', str(attempt)) for s in profile['pre_arguments']]
    if a.pre_arg != expected_pre:
        raise ValueError('CFX010 process arguments differ from approved case')
    if approved_script_hash(plan, profile, script) != profile['target_script_sha256' if plan['risky'] else 'control_script_sha256']:
        raise ValueError('CFX010 executable console script differs from approved route')
    images = [pathlib.Path(p).resolve() for p in re.findall(r'\bscreenshot\s+"([^"\n]+)"', script.read_text(encoding='utf-8'))]
    expected_images = [pathlib.Path(p).resolve() for p in plan.get('completion_artifacts', [])]
    if not images or images != expected_images or len(set(images)) != len(images) or any(not p.is_relative_to(attempt) for p in images):
        raise ValueError('CFX010 finite screenshot completion outputs must belong to attempt')
    if any(p.exists() for p in images):
        raise ValueError('CFX010 completion outputs already exist; stale success prohibited')
    required = [config, script, *(pathlib.Path(c['path']) for c in actual)]
    cache_inputs = plan.get('cache_inputs', {})
    if set(cache_inputs) != {'pipelinecache.zdpc', 'shadercache.zdsc'}:
        raise ValueError('CFX010 exact cache baselines required')
    cache = (pathlib.Path.home() / 'AppData/Local/zdoom/cache').resolve()
    if pathlib.Path(a.pipeline_cache or '').resolve() != cache / 'pipelinecache.zdpc' or pathlib.Path(a.shader_cache or '').resolve() != cache / 'shadercache.zdsc':
        raise ValueError('CFX010 transactional global cache paths required')
    required += [pathlib.Path(p) for p in cache_inputs.values() if p]
    inputs = plan.get('inputs', {})
    if any(inputs.get(str(p)) != digest(p) or not digest(p) for p in required):
        raise ValueError('CFX010 input/cache/config/script identities missing/changed')
    for p, expected_hash in inputs.items():
        if not expected_hash or digest(pathlib.Path(p)) != expected_hash:
            raise ValueError('CFX010 preregistered input changed')
        if any((parent / 'STOP-LAUNCHES.txt').exists() for parent in (pathlib.Path(p).parent, *pathlib.Path(p).parents)):
            raise ValueError('CFX010 STOP guard applies to input; use new authorized isolated copy')
    return a


def require_control(state, opening, plan):
    record = state.get('control_proofs', {}).get(settings_key(plan['settings']))
    proof = verified_record(record, 'CFX010 matching-settings safe control')
    profile = opening['case_profiles'][plan['case']]
    content = profile.get('control_content_order', [profile['content_order'][0]])
    if (proof.get('schema') != 'cfx-010-control-proof-v1' or proof.get('accepted') is not True or
            proof.get('renderer_source') != RENDERER or proof.get('settings') != plan['settings'] or
            content_identity(proof.get('control_content_order', [])) != content_identity(content)):
        raise ValueError('CFX010 matching-settings control missing')
    verify_files(proof, 'CFX010 control')


def capture_coverage(run, run_id):
    """A healthy bounded prefix is a limit, never a claim of loss-time coverage."""
    stream_run, rows = read_bindings(run / 'address-bindings.tsv')
    cpu = (run / 'timeline.tsv').read_text(encoding='utf-8')
    header = cpu.splitlines()[0] if cpu else ''
    if stream_run != run_id or header != '# CFX-002 trace v1 run=' + run_id + (' (rotated tail)' if '(rotated tail)' in header else ''):
        raise ValueError('CFX010 manifest/address/CPU identity mismatch')
    summaries = [c[7] for line in cpu.splitlines()[2:] if len(c := line.split('\t')) == 9 and c[6] == 'address-binding-summary']
    if not summaries:
        raise ValueError('CFX010 capture writer/flush evidence missing')
    summary = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', summaries[-1])}
    if (summary.get('writer_ok') != 1 or summary.get('contended') != 0 or summary.get('limit') != 32768 or
            summary.get('records') != len(rows) or summary.get('flushed', -1) < len(rows) or
            any(r['event'] not in ('bind', 'unbind', 'name', 'snapshot') for r in rows)):
        raise ValueError('CFX010 callback/writer/flush failure')
    truncated = summary.get('omitted', -1) > 0
    cutoff = summary.get('cutoff')
    if (summary.get('omitted', -1) < 0 or cutoff is None or (truncated and len(rows) != 32768) or
            (not truncated and (not rows or cutoff != len(rows) or rows[-1]['event'] != 'snapshot'))):
        raise ValueError('CFX010 malformed bounded-prefix/cutoff evidence')
    limitations = []
    if truncated: limitations.append('address capture is a bounded startup prefix; later binding events omitted')
    if '(rotated tail)' in header: limitations.append('CPU timeline rotated; only its bounded tail survives')
    if '\tresource-trace-truncated\t' in cpu: limitations.append('resource event budget8192 exhausted')
    return {'run_id': run_id, 'address_summary': summary, 'address_prefix_last_frame': int(rows[-1]['frame']) if rows else None,
            'address_complete_through_snapshot': not truncated, 'limitations': limitations}


def accept_control(attempt, opening, plan, manifest, run):
    if (manifest.get('status') != 'EXITED' or manifest.get('exit_status') != 0 or
            manifest['failure'].get('application_observation') or manifest['run'].get('renderer_source') != RENDERER or
            manifest['environment'].get('validation_or_capture_mode') != 'capture' or
            manifest['environment'].get('retain_replaced_lightmaps', {}).get('requested') is not False):
        raise ValueError('CFX010 safe capture control failed or wrong build/mode')
    report = activation(run / 'address-bindings.tsv', run / 'timeline.tsv', manifest['run_id'])
    if not {'flushed', 'cutoff'} <= report['teardown'].keys():
        raise ValueError('CFX010 queued capture activation required')
    if not manifest['environment']['address_bindings'].get('hardware_activation_verified'):
        raise ValueError('CFX010 safe address capability not activated')
    verify_completion(manifest, plan, run, opening)
    from PIL import Image
    images = [pathlib.Path(p) for p in plan['completion_artifacts']]
    for image in images:
        with Image.open(image) as im:
            if list(im.size) != plan['settings']['resolution']:
                raise ValueError('CFX010 actual control image dimensions differ')
            im.verify()
    mesh = run / 'work/levelmesh.obj'
    if not mesh.is_file() or not mesh_state(mesh)['protected']:
        raise ValueError('CFX010 protected safe mesh evidence missing')
    files = [attempt / 'plan.json', run / 'manifest.json', run / 'timeline.tsv', run / 'address-bindings.tsv', mesh, *images,
             attempt / 'health-before.json', attempt / 'health-after.json']
    return {'schema': 'cfx-010-control-proof-v1', 'accepted': True, 'renderer_source': RENDERER,
            'settings': plan['settings'], 'activation': report, 'image_dimensions': plan['settings']['resolution'],
            'control_content_order': opening['case_profiles'][plan['case']].get('control_content_order',
                [opening['case_profiles'][plan['case']]['content_order'][0]]),
            'image_equivalence_asserted': False, 'protected_mesh_present': True,
            'files': [{'path': str(p), 'sha256': digest(p)} for p in files]}


def verify_completion(manifest, plan, run, opening):
    """Verify actual viewport and fresh readable output for a claimed route success."""
    expected = plan['settings']['resolution']
    actual = re.match(r'^(\d+)\s*x\s*(\d+)(?:\s|$)', manifest.get('run', {}).get('actual_resolution') or '')
    if not actual or [int(actual[1]), int(actual[2])] != expected:
        raise ValueError('CFX010 actual renderer resolution differs from approved case')
    if opening.get('foreground_policy') == 'one-shot-verified-monitored-v1':
        from cfx010_foreground import verify
        verify(manifest.get('environment', {}).get('foreground'), run / 'timeline.tsv')
    markers = plan['route']['completion_markers'] if plan['risky'] else opening['case_profiles'][plan['case']]['control_completion_markers']
    if (not isinstance(markers, list) or not 1 <= len(markers) <= 64 or len(set(markers)) != len(markers) or
            any(not isinstance(marker, str) or not marker.strip() for marker in markers)):
        raise ValueError('CFX010 finite unique route completion markers required')
    console = (run / 'stdout.log').read_text(encoding='utf-8', errors='replace')
    position = 0
    for marker in markers:
        found = console.find(marker, position)
        if found < 0: raise ValueError('CFX010 route completion marker missing/out of order: ' + marker)
        position = found + len(marker)
    from PIL import Image
    for name in plan['completion_artifacts']:
        with Image.open(name) as image:
            if list(image.size) != expected:
                raise ValueError('CFX010 route screenshot dimensions differ')
            image.load()


def classify(manifest, loss_episode, completion_paths, driver_fault=False):
    observation = manifest.get('failure', {}).get('application_observation') if manifest else None
    if not manifest: return 'invalid-incomplete-capture'
    if observation == 'VK_ERROR_DEVICE_LOST': return 'application-device-loss'
    if loss_episode: return 'correlated-TDR'
    if manifest.get('status') == 'TIMEOUT': return 'watchdog-no-return'
    if observation and 'CPU exception' in observation: return 'CPU-exception'
    if observation or manifest.get('exit_status') != 0: return 'application-error'
    if driver_fault: return 'driver-fault-evidence'
    if manifest.get('status') != 'EXITED' or any(not p.is_file() or not p.stat().st_size for p in completion_paths):
        return 'route-incomplete'
    return 'route-completed'
