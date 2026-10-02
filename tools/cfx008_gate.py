"""CPU-only #99 control acceptance. Missing evidence fails closed."""
import json
import pathlib
import re
from cfx_capture import digest
from cfx_address_correlate import read_bindings


def activation(bindings, timeline, run_id):
    run, rows = read_bindings(bindings)
    cpu = timeline.read_text(encoding='utf-8')
    if run != run_id or not cpu.startswith('# CFX-002 trace v1 run=' + run_id + '\n'):
        raise ValueError('address/CPU/manifest run identity mismatch or rotated CPU trace')
    if 'address-binding-messenger\tregistered\t0' not in cpu or '\tcapability\taddress-binding-report-enabled\t0' not in cpu:
        raise ValueError('address messenger/feature activation not proven')
    if not all(any(r['event'] == e for r in rows) for e in ('bind', 'unbind')):
        raise ValueError('actual bind and unbind callback coverage missing')
    if any(r['event'] not in ('bind', 'unbind', 'name', 'snapshot') for r in rows):
        raise ValueError('malformed or missing callback association')
    snapshots = [r for r in rows if r['event'] == 'snapshot' and r['name'] == 'device-teardown']
    summaries = [c[7] for line in cpu.splitlines()[2:] if len(c := line.split('\t')) == 9
                 and c[6] == 'address-binding-summary' and c[7].startswith('reason=device-teardown ')]
    if len(snapshots) != 1 or len(summaries) != 1:
        raise ValueError('exactly one intact teardown snapshot/summary required')
    summary = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', summaries[0])}
    if any(summary.get(k) != v for k, v in (('omitted', 0), ('contended', 0), ('writer_ok', 1), ('limit', 32768))):
        raise ValueError('callback omissions/contention/writer failure')
    if summary.get('records') != int(snapshots[0]['seq']):
        raise ValueError('teardown summary/snapshot disagreement')
    if 'flushed' in summary and (summary.get('cutoff') != int(snapshots[0]['seq']) or summary['flushed'] < summary['cutoff']):
        raise ValueError('queued address records not flushed through teardown cutoff')
    return {'run_id': run, 'records': len(rows), 'teardown': summary,
            'binds': sum(r['event'] == 'bind' for r in rows),
            'unbinds': sum(r['event'] == 'unbind' for r in rows)}


def mesh_state(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    return {'protected': [s for s in lines if not s.startswith(('v ', 'vt ', 'vn '))],
            'vertices': sum(s.startswith('v ') for s in lines),
            'uvs': sum(s.startswith('vt ') for s in lines),
            'normals': sum(s.startswith('vn ') for s in lines)}


def accept_control(attempt, opening):
    from PIL import Image
    manifests = list((attempt / 'runs').glob('*/manifest.json'))
    if len(manifests) != 1:
        raise ValueError('one completed control manifest required')
    mp = manifests[0]; run = mp.parent
    manifest = json.loads(mp.read_text(encoding='utf-8'))
    if manifest['status'] != 'EXITED' or manifest['exit_status'] != 0 or manifest['failure']['application_observation']:
        raise ValueError('safe control did not exit cleanly')
    if not manifest['environment']['address_bindings']['hardware_activation_verified']:
        raise ValueError('manifest address activation not verified')
    if manifest['environment']['validation_or_capture_mode'] != 'capture' or manifest['run']['renderer_source'] != opening['renderer_source']:
        raise ValueError('wrong control mode/renderer source')
    for name in ('health-before.json', 'health-after.json'):
        if not json.loads((attempt / name).read_text(encoding='utf-8'))['pass']:
            raise ValueError('control recovery failed')
    report = activation(run / 'address-bindings.tsv', run / 'timeline.tsv', manifest['run_id'])
    reference = opening['control_reference']
    for name in ('image', 'mesh'):
        if digest(pathlib.Path(reference[name]['path'])) != reference[name]['sha256']:
            raise ValueError('control reference identity changed')
    image = attempt / 'scene.png'; mesh = run / 'work/levelmesh.obj'
    with Image.open(image) as now, Image.open(reference['image']['path']) as old:
        pixels_equal = now.size == old.size and now.convert('RGBA').tobytes() == old.convert('RGBA').tobytes()
        dimensions = list(now.size)
    mesh_equal = mesh_state(mesh) == mesh_state(pathlib.Path(reference['mesh']['path']))
    if not pixels_equal or not mesh_equal:
        raise ValueError('safe image/protected mesh equivalence failed')
    files = [mp, run / 'address-bindings.tsv', run / 'timeline.tsv', image, mesh,
             attempt / 'health-before.json', attempt / 'health-after.json', attempt / 'plan.json',
             pathlib.Path(reference['image']['path']), pathlib.Path(reference['mesh']['path'])]
    return {'schema': 'cfx-008-control-proof-v1', 'accepted': True, 'run_id': manifest['run_id'],
            'activation': report, 'identical_pixels': True, 'dimensions': dimensions,
            'protected_mesh_equal': True, 'full_obj_bytes_asserted': False,
            'files': [{'path': str(p), 'sha256': digest(p)} for p in files]}


def require_control(lane, state):
    path = lane / 'control-proof.json'
    if not state.get('control_proof_sha256') or digest(path) != state['control_proof_sha256']:
        raise ValueError('accepted safe-control proof missing/changed')
    proof = json.loads(path.read_text(encoding='utf-8'))
    if proof.get('schema') != 'cfx-008-control-proof-v1' or not proof.get('accepted') or not proof.get('files'):
        raise ValueError('invalid safe-control proof')
    for record in proof['files']:
        if not record.get('sha256') or digest(pathlib.Path(record['path'])) != record['sha256']:
            raise ValueError('safe-control evidence changed')


def validate_plan(plan, opening, attempt):
    """Fix the entry point and scopes; neither arbitrary argv nor a boolean unlocks risk."""
    import argparse
    ap = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    for name in ('exe', 'run-root', 'cfx008-lane-plan', 'mode', 'timeout'):
        ap.add_argument('--' + name)
    for name in ('approved-cfx008', 'resource-trace', 'address-bindings', 'skip-dump-on-timeout', 'launch'):
        ap.add_argument('--' + name, action='store_true')
    a, rest = ap.parse_known_args(plan['run_arguments'])
    if (a.mode != 'capture' or a.timeout != '60' or not a.approved_cfx008 or
            not a.resource_trace or not a.address_bindings or not a.launch or a.skip_dump_on_timeout or
            pathlib.Path(a.exe or '').resolve() != pathlib.Path(plan['exe']).resolve() or
            pathlib.Path(a.run_root or '').resolve() != attempt / 'runs' or
            pathlib.Path(a.cfx008_lane_plan or '').resolve() != attempt.parent / 'lane-opening.json' or
            any(s.startswith(('--approved-cfx00', '--validation-layer-dir')) for s in rest) or
            plan.get('renderer_source') != opening['renderer_source'] or
            plan.get('schema') != 'cfx-008-attempt-v1'):
        raise ValueError('CFX-008 requires exact capture/address arguments and merged renderer')
