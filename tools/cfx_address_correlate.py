#!/usr/bin/env python3
"""Offline binding-event overlap report. No GPU, replay or unique-cause inference."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

FIELDS = ('seq', 'ms_utc', 'thread', 'frame', 'tic', 'submission', 'event', 'base',
          'bytes', 'flags', 'object_type', 'handle', 'object_index', 'object_count', 'name')
U64 = (1 << 64) - 1


def fault_interval(address, precision):
    if not 0 <= address <= U64 or not 1 <= precision <= U64 or precision & (precision - 1):
        raise ValueError('fault address must be uint64; precision must be a nonzero power of two')
    return address & ~(precision - 1), address | (precision - 1)


def identity(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def read_bindings(path):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('binding input exceeds bounded collector capacity')
    # A bounded driver object-name hint may end midway through UTF-8. Numeric
    # fields/identities remain exact; replacement affects name hints only.
    text = path.read_text(encoding='utf-8', errors='replace')
    if not text.endswith('\n'):
        raise ValueError('incomplete final binding record')
    lines = text.splitlines()
    if not lines or not lines[0].startswith('# CFX address bindings v1 run='):
        raise ValueError('not a CFX address-binding stream')
    reader = csv.DictReader(lines[1:], delimiter='\t')
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError('unknown binding columns')
    rows = list(reader)
    if len(rows) > 32768:
        raise ValueError('too many binding records')
    for seq, row in enumerate(rows, 1):
        if None in row or any(v is None for v in row.values()) or int(row['seq']) != seq:
            raise ValueError('broken binding row or sequence')
        base, size = int(row['base'], 0), int(row['bytes'])
        if not 0 <= base <= U64 or not 0 <= size <= U64 or base + size > 1 << 64:
            raise ValueError('invalid binding range')
    return lines[0].split('run=', 1)[1], rows


def correlate(bindings, timeline, address, precision):
    lower, upper = fault_interval(address, precision)
    run, rows = read_bindings(bindings)
    if timeline.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('CPU timeline exceeds bounded trace capacity')
    cpu = timeline.read_text(encoding='utf-8')
    header = cpu.splitlines()[0] if cpu.splitlines() else ''
    cpu_run = header.removeprefix('# CFX-002 trace v1 run=').removesuffix(' (rotated tail)')
    if not header.startswith('# CFX-002 trace v1 run=') or cpu_run != run:
        raise ValueError('binding/CPU run identities differ')
    reasons = []
    cutoff = next((int(r['seq']) for r in rows if r['event'] == 'snapshot' and r['name'] == 'device-lost'), None)
    summaries = [line.split('\t')[7] for line in cpu.splitlines()[2:]
                 if len(line.split('\t')) == 9 and line.split('\t')[6] == 'address-binding-summary'
                 and 'reason=device-lost ' in line.split('\t')[7]]
    if cutoff is None:
        reasons.append('no device-loss callback-stream cutoff')
    if not summaries:
        reasons.append('no CPU loss summary; omissions and writer health unknown')
    else:
        summary = dict(re.findall(r'(\w+)=(\d+)', summaries[0]))
        if any(int(summary.get(k, '-1')) != v for k, v in (('omitted', 0), ('contended', 0), ('writer_ok', 1))):
            reasons.append('callback omission, contention or writer failure')
        if cutoff is not None and int(summary.get('records', '-1')) != cutoff:
            reasons.append('loss summary/cutoff record disagreement')
    before_loss = [r for r in rows if cutoff is None or int(r['seq']) <= cutoff]
    if any(r['event'] in ('binding-no-object', 'binding-payload-missing', 'unknown-binding') for r in before_loss):
        reasons.append('missing or malformed callback association')
    names = {}
    for row in before_loss:
        key = row['object_type'], row['handle']
        if row['name'] and row['event'] != 'snapshot':
            names.setdefault(key, set()).add(row['name'])
    matches = []
    for row in before_loss:
        if row['event'] not in ('bind', 'unbind', 'binding-no-object'):
            continue
        base, size = int(row['base'], 0), int(row['bytes'])
        if size and base <= upper and lower < base + size:
            matches.append({**row, 'name_history_hints': sorted(names.get((row['object_type'], row['handle']), ()))})
    handles = {m['handle'] for m in matches if m['object_type'] == '9'}  # VkBuffer
    related = {handle: [] for handle in handles}
    omitted_related = 0
    for line in cpu.splitlines()[2:]:
        columns = line.split('\t')
        if len(columns) != 9 or 'kind=buffer ' not in columns[7]:
            continue
        handle = re.search(r'\bhandle=(0x[0-9a-fA-F]+)\b', columns[7])
        if handle and handle[1] in related:
            if len(related[handle[1]]) < 32:
                related[handle[1]].append({'event': columns[6], 'detail': columns[7], 'ms_utc': columns[0]})
            else:
                omitted_related += 1
    return {
        'schema': 'cfx-address-overlap-v1', 'run_id': run,
        'inputs': {'bindings': identity(bindings), 'timeline': identity(timeline)},
        'fault': {'reported_address': hex(address), 'precision_bytes': precision,
                  'lower_inclusive': hex(lower), 'upper_inclusive': hex(upper)},
        'loss_cutoff_seq': cutoff, 'capture_gaps': reasons,
        'reported_binding_capture_complete_to_cutoff': not reasons,
        'overlapping_event_history': matches, 'related_buffer_identity_history': related,
        'related_history_omitted_rows': omitted_related,
        'cpu_timeline_rotated': '(rotated tail)' in cpu.splitlines()[0],
        'interpretation': 'Reported interval overlaps only. Aliases, partial/unmatched unbinds, '
                          'internal/pre-creation handles and handle reuse may occur. No unique '
                          'allocation generation, live-binding map, executed shader or crash cause '
                          'is inferred. No overlap does not establish that the address was unbound.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bindings', type=Path, required=True)
    ap.add_argument('--timeline', type=Path, required=True)
    ap.add_argument('--address', type=lambda s: int(s, 0), required=True)
    ap.add_argument('--precision', type=lambda s: int(s, 0), required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    try:
        result = correlate(args.bindings, args.timeline, args.address, args.precision)
    except (OSError, ValueError, KeyError) as exc:
        ap.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
