"""Execute one preregistered #105 attempt. Default is preflight; never retry."""
import argparse
import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys

from cfx_capture import digest
from cfx007_execute import CACHE, ROOT, save, stop
from cfx007_health import collect
from cfx010_gate import accept_control, capture_coverage, check_lane, classify, settings_key, validate_plan, verify_completion


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=pathlib.Path, required=True)
    ap.add_argument('--launch', action='store_true')
    args = ap.parse_args()
    pp = args.plan.resolve(); attempt = pp.parent; lane = attempt.parent
    try:
        plan = json.loads(pp.read_text(encoding='utf-8'))
        opening = check_lane(lane / 'lane-opening.json', attempt / 'runs', pathlib.Path(plan['exe']))
        validate_plan(plan, opening, attempt)
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != plan['runner_source']:
            raise ValueError('CFX010 runner source changed')
    except (OSError, ValueError, KeyError, TypeError) as e:
        ap.error(str(e))
    state = json.loads((lane / 'state.json').read_text(encoding='utf-8'))
    health = collect(attempt, opening['health_since_utc'])
    if health['windows'].get('boot') != opening['baseline_boot_utc']:
        health['pass'] = False; health['stop_reasons'].append('unexpected machine reboot')
    save(attempt / 'health-before.json', health)
    if not health['pass']:
        stop(lane, state, health['stop_reasons'], 'CFX-010'); ap.error('CFX010 prelaunch health failed')
    print('preflight PASS', plan['attempt_id'], flush=True)
    if not args.launch: return 0
    prior = {}; restored = {}; faults = []; result = None
    backup = attempt / 'cache-backup'; after = attempt / 'cache-after'
    try:
        backup.mkdir(); after.mkdir()
        for name in plan['cache_inputs']:
            prior[name] = digest(CACHE / name)
            if (CACHE / name).is_file(): shutil.copy2(CACHE / name, backup / name)
    except OSError as e:
        stop(lane, state, ['cache backup/storage failed before launch: ' + str(e)], 'CFX-010')
        return 1
    state['launches'] += 1; state['pending_attempt'] = plan['attempt_id']
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    save(lane / 'state.json', state)
    save(attempt / 'execution-start.json', {'attempt_id': plan['attempt_id'], 'started_at_utc': started,
         'plan_sha256': digest(pp), 'counted_launch': state['launches'], 'original_cache': prior})
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        for name, source in plan['cache_inputs'].items():
            if source: shutil.copy2(source, CACHE / name)
            elif (CACHE / name).is_file(): (CACHE / name).unlink()
        result = subprocess.run([sys.executable, str(ROOT / 'tools/cfx_capture.py'), *plan['run_arguments']],
                                cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=150)
        (attempt / 'runner.stdout.txt').write_text(result.stdout, encoding='utf-8')
        (attempt / 'runner.stderr.txt').write_text(result.stderr, encoding='utf-8')
        for name in plan['cache_inputs']:
            if (CACHE / name).is_file(): shutil.copy2(CACHE / name, after / name)
    except (OSError, subprocess.TimeoutExpired) as e:
        faults.append('capture wrapper/storage failed: ' + str(e))
    finally:
        for name in prior:
            try:
                if (backup / name).is_file(): shutil.copy2(backup / name, CACHE / name)
                elif (CACHE / name).is_file(): (CACHE / name).unlink()
                restored[name] = digest(CACHE / name) == prior[name]
            except OSError as e:
                restored[name] = False; faults.append('cache restore error: ' + str(e))
    manifests = list((attempt / 'runs').glob('*/manifest.json'))
    manifest = None
    try:
        if len(manifests) == 1: manifest = json.loads(manifests[0].read_text(encoding='utf-8'))
    except (OSError, ValueError) as e: faults.append('manifest unreadable: ' + str(e))
    health = collect(attempt, opening['health_since_utc']); save(attempt / 'health-after.json', health)
    if not all(restored.values()): faults.append('global cache restore failed')
    if not manifest or manifest.get('status') in ('PREPARED', 'RUNNING'): faults.append('missing/incomplete manifest')
    loss = bool(manifest and manifest['failure']['application_observation'] == 'VK_ERROR_DEVICE_LOST')
    display_tdr = any(e['Provider'] == 'Display' and e['Id'] == 4101 for e in health['windows'].get('events', []) if e['Time'] >= started)
    wer_tdr = any('LiveKernelEvent' in e.get('Xml', '') and any('>' + code + '<' in e.get('Xml', '') for code in ('141', '117'))
                  for e in health['windows'].get('wer', []) if e['Time'] >= started)
    episode = loss or display_tdr or wer_tdr
    driver_faults = [e for e in health['windows'].get('events', [])
                     if e['Time'] >= started and e['Provider'] == 'nvlddmkm' and e['Id'] == 153]
    if episode: state['loss_episodes'] += 1
    if manifest and manifest['status'] == 'TIMEOUT':
        if not loss: faults.append('hard/no-return renderer hang')
        if manifest['failure'].get('watchdog_action', {}).get('status') != 'captured': faults.append('required pre-kill process dump not captured')
    if health['windows'].get('boot') != opening['baseline_boot_utc']: faults.append('unexpected machine reboot')
    if not health['pass']: faults.extend(health['stop_reasons'])
    coverage = None
    if manifest:
        for artifact in manifest.get('artifact_files', []):
            p = pathlib.Path(artifact['path'])
            if not p.is_file() or p.stat().st_size != artifact['size']: faults.append('artifact missing/changed')
        try:
            coverage = capture_coverage(manifests[0].parent, manifest['run_id'])
        except (OSError, ValueError, KeyError, TypeError) as e: faults.append('capture integrity failed: ' + str(e))
    classification = classify(manifest, episode, [pathlib.Path(p) for p in plan['completion_artifacts']], bool(driver_faults))
    if classification == 'route-completed':
        try:
            verify_completion(manifest, plan, manifests[0].parent, opening)
        except (OSError, ValueError, KeyError, TypeError) as e:
            classification = 'route-incomplete'; faults.append('uninterpretable route completion evidence: ' + str(e))
    if not plan['risky'] and classification != 'route-completed': faults.append('safe control failed')
    if not plan['risky'] and not faults:
        try:
            proof = accept_control(attempt, opening, plan, manifest, manifests[0].parent)
            path = attempt / 'control-proof.json'; save(path, proof)
            state.setdefault('control_proofs', {})[settings_key(plan['settings'])] = {'path': str(path), 'sha256': digest(path)}
        except (OSError, ValueError, KeyError, TypeError) as e: faults.append('safe activation/settings gate: ' + str(e))
    state['pending_attempt'] = None
    if plan['risky']:
        state['analysis_pending'] = plan['attempt_id']; state['last_informative_attempt'] = plan['attempt_id']
    state.setdefault('attempts', []).append({'attempt_id': plan['attempt_id'], 'case': plan['case'], 'risky': plan['risky'],
         'plan': str(pp), 'manifest': str(manifests[0]) if len(manifests) == 1 else None, 'loss_episode': episode,
         'classification': classification, 'correlated_nv153': driver_faults, 'capture_coverage': coverage, 'discriminator': plan['discriminator']})
    if faults: stop(lane, state, faults, 'CFX-010')
    else: save(lane / 'state.json', state)
    try:
        save(attempt / 'execution-result.json', {'ended_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
             'runner_exit_code': result.returncode if result else None, 'global_cache_restored': restored,
             'loss_episode': episode, 'recovery_pass': health['pass'], 'classification': classification,
             'correlated_nv153': driver_faults, 'capture_coverage': coverage, 'stop_reasons': faults,
             'counts': {'launches': state['launches'], 'loss_episodes': state['loss_episodes']}})
        files = [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in attempt.rglob('*')
                 if p.is_file() and p.name != 'artifact-index.json']
        save(attempt / 'artifact-index.json', {'schema': 'cfx-010-artifacts-v1', 'files': files})
    except OSError as e:
        faults.append('artifact index/storage failed: ' + str(e)); stop(lane, state, faults, 'CFX-010')
    print(json.dumps({'attempt': plan['attempt_id'], 'classification': classification, 'status': state['status'], 'stop_reasons': faults}), flush=True)
    return 1 if faults else 0


if __name__ == '__main__': sys.exit(main())
