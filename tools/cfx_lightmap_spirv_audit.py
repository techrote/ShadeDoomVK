#!/usr/bin/env python3
"""CPU-only extraction of named lightmap guards from recorded shader-cache hits.

This recognizes the ordinary direct-index lightmap pattern in ShadeDoomVK's
cached SPIR-V. It is neither a SPIR-V validator nor a driver/SASS analyzer.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

MAX_CACHE = 64 * 1024 * 1024
MAX_TIMELINE = 128 * 1024 * 1024
TIMELINE_FIELDS = ('ms_utc', 'thread', 'frame', 'tic', 'submission', 'stage',
                   'event', 'detail', 'result')
OP_NAMES = {5: 'OpName', 15: 'OpEntryPoint', 21: 'OpTypeInt', 43: 'OpConstant',
            50: 'OpSpecConstant', 54: 'OpFunction', 56: 'OpFunctionEnd',
            61: 'OpLoad', 62: 'OpStore', 65: 'OpAccessChain', 71: 'OpDecorate',
            83: 'OpCopyObject', 87: 'OpImageSampleImplicitLod',
            110: 'OpConvertFToS', 128: 'OpIAdd', 132: 'OpIMul',
            171: 'OpINotEqual', 190: 'OpFOrdGreaterThanEqual',
            247: 'OpSelectionMerge', 248: 'OpLabel', 249: 'OpBranch',
            250: 'OpBranchConditional'}


def identity(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def read_cache(path):
    if path.stat().st_size > MAX_CACHE:
        raise ValueError('cache exceeds 64 MiB bound')
    data = path.read_bytes()
    pos = 0

    def take(size):
        nonlocal pos
        if size < 0 or pos + size > len(data):
            raise ValueError('truncated shader cache')
        result = data[pos:pos + size]
        pos += size
        return result

    def number(fmt):
        return struct.unpack(fmt, take(struct.calcsize(fmt)))[0]

    def string():
        size = number('<I')
        if size > 4096:
            raise ValueError('cache string exceeds 4096-byte bound')
        return take(size).decode('utf-8')

    if take(11) != b'shadercache' or number('<I') != 2:
        raise ValueError('expected shadercache version 2')
    count = number('<I')
    if count > 16384:
        raise ValueError('too many shader-cache entries')
    entries = {}
    for _ in range(count):
        key = string()
        if key in entries:
            raise ValueError('duplicate shader-cache key')
        last_used = number('<Q')
        words = number('<I')
        if words > 8 * 1024 * 1024:
            raise ValueError('SPIR-V module exceeds 32 MiB bound')
        code = take(words * 4)
        include_count = number('<I')
        if include_count > 4096:
            raise ValueError('too many shader includes')
        includes = []
        for _ in range(include_count):
            lump = string()
            private = number('<B')
            if private not in (0, 1):
                raise ValueError('invalid private-lump flag')
            includes.append(dict(lump=lump, private=bool(private), checksum=string()))
        entries[key] = dict(code=code, last_used=last_used, includes=includes)
    if pos != len(data):
        raise ValueError('trailing shader-cache bytes')
    return entries


def read_timeline(path):
    if path.stat().st_size > MAX_TIMELINE:
        raise ValueError('timeline exceeds 128 MiB bound')
    text = path.read_text(encoding='utf-8')
    if not text.endswith('\n'):
        raise ValueError('incomplete final timeline record')
    lines = text.splitlines()
    prefix = '# CFX-002 trace v1 run='
    if not lines or not lines[0].startswith(prefix):
        raise ValueError('expected CFX CPU timeline')
    run = lines[0][len(prefix):]
    if run.endswith(' (rotated tail)'):
        raise ValueError('rotated timeline cannot establish complete shader-creation coverage')
    reader = csv.DictReader(lines[1:], delimiter='\t')
    if tuple(reader.fieldnames or ()) != TIMELINE_FIELDS:
        raise ValueError('unknown timeline columns')
    rows = list(reader)
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('malformed timeline row')
    return run, rows


def spirv_string(words):
    raw = struct.pack('<' + 'I' * len(words), *words)
    if b'\0' not in raw:
        raise ValueError('unterminated SPIR-V string')
    return raw.split(b'\0', 1)[0].decode('utf-8')


def parse_spirv(data):
    if len(data) < 20 or len(data) % 4:
        raise ValueError('invalid SPIR-V byte length')
    words = struct.unpack('<' + 'I' * (len(data) // 4), data)
    if words[0] != 0x07230203 or words[4] != 0:
        raise ValueError('invalid SPIR-V header')
    result, names, function, block = [], {}, None, None
    pos = 5
    while pos < len(words):
        size, opcode = words[pos] >> 16, words[pos] & 0xffff
        if not size or pos + size > len(words):
            raise ValueError('zero-length or truncated SPIR-V instruction')
        operands = list(words[pos + 1:pos + size])
        if opcode == 5:
            if len(operands) < 2:
                raise ValueError('malformed OpName')
            names[operands[0]] = spirv_string(operands[1:])
        elif opcode == 54:
            if function is not None or len(operands) != 4:
                raise ValueError('malformed OpFunction')
            function, block = operands[1], None
        elif opcode == 248:
            if function is None or len(operands) != 1:
                raise ValueError('malformed OpLabel')
            block = operands[0]
        result.append(dict(op=opcode, args=operands, byte_offset=pos * 4,
                           function=function, block=block))
        if opcode == 56:
            if function is None:
                raise ValueError('unmatched OpFunctionEnd')
            function, block = None, None
        pos += size
    if function is not None:
        raise ValueError('unterminated SPIR-V function')
    return words[1], names, result


def site(ins):
    return dict(op=OP_NAMES.get(ins['op'], 'Op' + str(ins['op'])),
                byte_offset=ins['byte_offset'], hex_offset=hex(ins['byte_offset']),
                operands=ins['args'])


def audit_module(data):
    version, names, instructions = parse_spirv(data)
    named = {value: key for key, value in names.items()}
    lightmap = named.get('vLightmapIndex')
    textures = named.get('textures')
    signed32 = {i['args'][0] for i in instructions
                if i['op'] == 21 and len(i['args']) == 3 and i['args'][1:] == [32, 1]}
    minus_one = {i['args'][1] for i in instructions if i['op'] == 43 and len(i['args']) == 3
                 and i['args'][0] in signed32 and i['args'][2] == 0xffffffff}
    # Track only direct OpLoad/OpCopyObject chains; arithmetic and probe gather
    # are deliberately outside the ordinary textures[vLightmapIndex] scope.
    input_ids = set()
    input_loads = {}
    for ins in instructions:
        args = ins['args']
        if ins['op'] == 61 and len(args) >= 3 and args[2] == lightmap:
            input_ids.add(args[1])
            input_loads[args[1]] = ins
        elif ins['op'] == 83 and len(args) == 3 and args[2] in input_ids:
            input_ids.add(args[1])
    guards = []
    for index, ins in enumerate(instructions):
        args = ins['args']
        if ins['op'] != 171 or len(args) != 4:
            continue
        lhs, rhs = args[2:]
        if not ((lhs in input_ids and rhs in minus_one) or (rhs in input_ids and lhs in minus_one)):
            continue
        if index + 2 >= len(instructions):
            continue
        merge, branch = instructions[index + 1:index + 3]
        if (merge['op'] == 247 and len(merge['args']) == 2 and branch['op'] == 250
                and len(branch['args']) == 3 and branch['args'][0] == args[1]
                and branch['args'][2] == merge['args'][0]
                and branch['function'] == ins['function']):
            guards.append((ins, merge, branch))
    samples, unmatched = [], []
    for chain in instructions:
        args = chain['args']
        if chain['op'] != 65 or len(args) != 4 or args[2] != textures or args[3] not in input_ids:
            continue
        loads = [i for i in instructions if i['op'] == 61 and len(i['args']) >= 3
                 and i['args'][2] == args[1]]
        image_samples = [(load, sample) for load in loads for sample in instructions
                         if sample['op'] == 87 and len(sample['args']) >= 4
                         and sample['args'][2] == load['args'][1]]
        guard = next(((compare, merge, branch) for compare, merge, branch in guards
                      if chain['function'] == branch['function']
                      and chain['block'] == branch['args'][1]
                      and branch['byte_offset'] < chain['byte_offset']), None)
        valid_samples = [(load, sample) for load, sample in image_samples
                         if load['function'] == chain['function'] == sample['function']
                         and load['block'] == chain['block'] == sample['block']
                         and chain['byte_offset'] < load['byte_offset'] < sample['byte_offset']]
        if guard and valid_samples and len(valid_samples) == len(image_samples):
            compare, merge, branch = guard
            for load, sample in valid_samples:
                samples.append(dict(function_id=chain['function'],
                                    function_name=names.get(chain['function'], ''),
                                    true_block_id=chain['block'],
                                    compare=site(compare), selection_merge=site(merge),
                                    branch=site(branch), descriptor_access=site(chain),
                                    descriptor_load=site(load), image_sample=site(sample)))
        else:
            unmatched.append(dict(descriptor_access=site(chain),
                                  reason='direct named lightmap access does not match the immediate true-block sample pattern',
                                  loads=[site(i) for i in loads], samples=[site(s) for _, s in image_samples]))
    decorations = {i['args'][0]: i['args'][2] for i in instructions
                   if i['op'] == 71 and len(i['args']) == 3 and i['args'][1] == 1}
    specialization = [dict(id=i['args'][1], name=names.get(i['args'][1], ''),
                           constant_id=decorations[i['args'][1]], literal_words=i['args'][2:],
                           instruction=site(i)) for i in instructions if i['op'] == 50
                      and len(i['args']) >= 3 and i['args'][1] in decorations]
    stores = []
    for index, ins in enumerate(instructions):
        if ins['op'] == 62 and len(ins['args']) >= 2 and ins['args'][0] == lightmap:
            stores.append(dict(function_id=ins['function'], function_name=names.get(ins['function'], ''),
                               block_id=ins['block'], store=site(ins),
                               nearby_instructions=[site(i) for i in instructions[max(0, index - 6):index + 1]
                                                    if i['function'] == ins['function']]))
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), spirv_version=hex(version),
                entry_models=sorted({i['args'][0] for i in instructions if i['op'] == 15}),
                named_ids={name: named[name] for name in ('vLightmapIndex', 'textures', 'aPosition') if name in named},
                ordinary_sample_guards=samples, unmatched_direct_accesses=unmatched,
                specialization_defaults=specialization, vertex_lightmap_stores=stores)


def audit(cache, timeline, source_sha):
    if not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('source SHA must be exact lowercase 40-character identity')
    entries = read_cache(cache)
    run, rows = read_timeline(timeline)
    hits = [row for row in rows if row['event'] == 'shader-cache-hit']
    keys = sorted({row['detail'] for row in hits})
    missing = sorted(set(keys) - set(entries))
    if missing:
        raise ValueError('recorded cache hits absent from cache: ' + ', '.join(missing))
    modules = {}
    for key in keys:
        entry = entries[key]
        digest = hashlib.sha256(entry['code']).hexdigest()
        if digest not in modules:
            modules[digest] = audit_module(entry['code'])
            modules[digest]['cache_keys'] = []
        modules[digest]['cache_keys'].append(key)
    records = [modules[digest] for digest in sorted(modules)]
    guard_count = sum(len(m['ordinary_sample_guards']) for m in records)
    unmatched_count = sum(len(m['unmatched_direct_accesses']) for m in records)
    last_hits = {model: next((row for row in reversed(hits) if row['detail'].startswith(model + '-')), None)
                 for model in ('0', '4')}
    for row in last_hits.values():
        if row:
            row['module_sha256'] = hashlib.sha256(entries[row['detail']]['code']).hexdigest()
    return dict(schema='cfx-009-lightmap-spirv-guards-v1', run_id=run, source_sha=source_sha,
                tool=identity(Path(__file__)), cache=identity(cache), timeline=identity(timeline),
                scope='Named ordinary textures[vLightmapIndex] direct-index OpImageSampleImplicitLod sites; structural binary extraction only.',
                evidence_kind='Recorded shader-cache/module-creation evidence, not executed shader or SASS evidence.',
                limitations=[
                    'Not a general CFG/dominance proof or full SPIR-V validation; unmatched patterns are reported explicitly.',
                    'Does not audit uintTextures probe-gather arithmetic or arbitrary descriptor-index calculations.',
                    'Does not prove submitted GPU input bytes, interpolants, dynamic descriptor use, pipeline pairing, or driver compilation behavior.',
                    'Cache-hit order identifies shader creation; the last recorded fragment is not necessarily the failing draw.',
                    'No instruction-pointer-to-SPIR-V/SASS mapping and no unique root-cause claim.'
                ],
                summary=dict(cache_entries=len(entries), unique_recorded_cache_hits=len(keys),
                             unique_module_hashes=len(records), modules_with_ordinary_samples=sum(bool(m['ordinary_sample_guards']) for m in records),
                             recognized_ordinary_sample_guards=guard_count, unmatched_direct_accesses=unmatched_count,
                             shader_compile_events=sum(row['event'].startswith('shader-compile-') for row in rows)),
                last_recorded_cache_hits=last_hits, modules=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--timeline', required=True, type=Path)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', required=True, action='append', type=Path,
                        help='new JSON path; repeat for identical public/private metadata')
    args = parser.parse_args()
    for path in args.output:
        if path.exists():
            parser.error('refusing to overwrite an existing report: ' + str(path))
    try:
        report = audit(args.cache, args.timeline, args.source_sha)
    except (ValueError, UnicodeError, OSError, struct.error) as error:
        parser.error(str(error))
    serialized = json.dumps(report, indent=2) + '\n'
    for path in args.output:
        with path.open('x', encoding='utf-8', newline='\n') as output:
            output.write(serialized)
    print(json.dumps(report['summary'], sort_keys=True))
    return 1 if report['summary']['unmatched_direct_accesses'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
