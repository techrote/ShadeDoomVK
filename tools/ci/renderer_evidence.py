#!/usr/bin/env python3
"""Lossless, fail-closed transfer of split hosted software-Vulkan evidence.

The raw suite tarballs are temporarily ZIP-deflated by upload-artifact. Only
one final high-compression XZ pass is used, preserving the legacy consumer.
These checks do not decide renderer acceptance or relax any native gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import time

SCHEMA = 'sdvk-software-vulkan-evidence/v2'
SHORT_PUBLICATION_ROOTS = ('renderer-sdvk010', 'renderer-sdvk150', 'renderer-sdvk153',
                           'renderer-sdvk158', 'renderer-sdvk161', 'renderer-sdvk014-controlled')
ROOTS = {
    'corpus': ('renderer-native', 'renderer-sdvk008-control', 'renderer-sdvk008-preflight'),
    'publication': (*SHORT_PUBLICATION_ROOTS, 'renderer-sdvk009-worker-publication'),
    # Shared authored input and the immutable registration travel exactly once.
    'controls': ('renderer-sdvk009-worker-controls', 'renderer-sdvk009-plan',
                 'renderer-sdvk009-content'),
    'witness-1': ('renderer-sdvk009-worker-witness-1',),
    'witness-2': ('renderer-sdvk009-worker-witness-2',),
}
OPTIONAL = {suite: ('renderer-ci-' + suite,) for suite in ROOTS}
PROBE_SUITES = ('controls', 'witness-1', 'witness-2')
COHORT_PROBE_SUITES = ('publication', *PROBE_SUITES)
# A cohort campaign requires these complete native probe packets in its
# assembler. Older fixed-placement campaigns do not have them. Transport keeps
# each original packet once, including partial failures; peer downloads remain
# outside the retained worker roots.
for _suite in PROBE_SUITES:
    OPTIONAL[_suite] += ('renderer-sdvk009-probe-' + _suite,)
GATES = {
    'corpus': {'renderer-native/native-ci.json': 'PASS',
               'renderer-native/collision-review.json': 'PASS',
               'renderer-sdvk008-control/sdvk008-software-fixture-control.json': 'SOFTWARE_FIXTURE_CONTROL_COLLECTED'},
    'publication': {**{root + '/qualification.json': 'PASS' for root in SHORT_PUBLICATION_ROOTS},
                    'renderer-sdvk009-worker-publication/worker.json': 'PASS'},
    'controls': {'renderer-sdvk009-content/content.json': 'PASS',
                 'renderer-sdvk009-worker-controls/worker.json': 'PASS'},
    'witness-1': {'renderer-sdvk009-worker-witness-1/worker.json': 'PASS'},
    'witness-2': {'renderer-sdvk009-worker-witness-2/worker.json': 'PASS'},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path_or_stream):
    digest = hashlib.sha256()
    if hasattr(path_or_stream, 'read'):
        stream = path_or_stream
        while block := stream.read(1024 * 1024):
            digest.update(block)
    else:
        with open(path_or_stream, 'rb') as stream:
            return sha256(stream)
    return digest.hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON member: ' + key)
        result[key] = value
    return result


def invalid_json_constant(value):
    raise ValueError('Nonfinite JSON constant: ' + value)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_json_pairs,
                      parse_constant=invalid_json_constant)


def identity(suite, expected_commit, runtime_sha256, plan_sha256, job_status):
    return {'worker': suite, 'source_sha': expected_commit, 'runtime_sha256': runtime_sha256,
            'plan_sha256': plan_sha256, 'job_status': job_status,
            'github_run_id': os.environ.get('GITHUB_RUN_ID'),
            'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}


def verify_identity(actual, suite, expected_commit, runtime_sha256, plan_sha256, *, complete):
    require(isinstance(actual, dict) and set(actual) ==
            {'worker', 'source_sha', 'runtime_sha256', 'plan_sha256', 'job_status',
             'github_run_id', 'github_run_attempt'}, 'Invalid worker identity: ' + suite)
    require(actual['worker'] == suite, 'Cross-wired worker identity: ' + suite)
    for key, expected, length in (('source_sha', expected_commit, 40),
                                  ('runtime_sha256', runtime_sha256, 64),
                                  ('plan_sha256', plan_sha256, 64)):
        if expected is not None:
            require(re.fullmatch('[0-9a-f]{' + str(length) + '}', expected) is not None,
                    'Malformed expected ' + key)
            require(actual[key] == expected, 'Mismatched worker ' + key + ': ' + suite)
    for key, environment in (('github_run_id', 'GITHUB_RUN_ID'),
                             ('github_run_attempt', 'GITHUB_RUN_ATTEMPT')):
        if os.environ.get(environment):
            require(actual[key] == os.environ[environment], 'Cross-run evidence: ' + suite)
    require(actual['job_status'] in ('success', 'failure', 'cancelled', 'unknown'),
            'Invalid worker job status: ' + suite)
    if complete:
        require(actual['job_status'] == 'success', 'Unsuccessful worker evidence: ' + suite)


def scan(build, names):
    entries = {}
    present = []
    for name in names:
        root = build / name
        if not root.exists():
            continue
        require(root.is_dir() and not root.is_symlink(), f'Invalid evidence root: {name}')
        present.append(name)
        for path in sorted(root.rglob('*')):
            mode = path.lstat().st_mode
            require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), f'Unsafe evidence entry: {path}')
            if stat.S_ISREG(mode):
                rel = path.relative_to(build).as_posix()
                entries[rel] = {'sha256': sha256(path), 'size': path.stat().st_size}
    return present, entries


def packaging_resources():
    """Bound compression by actual CPU/memory limits, not the runner label."""
    processors = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    memory = None
    try:
        memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (AttributeError, OSError, ValueError):
        pass
    limits = {'physical_memory_bytes': memory, 'affinity_processors': processors}
    for name in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        path = Path(name)
        if path.is_file():
            value = path.read_text().strip()
            limits[name] = value
            if value.isdigit() and int(value) > 0:
                memory = min(memory, int(value)) if memory is not None else int(value)
    quota = Path('/sys/fs/cgroup/cpu.max')
    if quota.is_file():
        limits['cpu_max'] = quota.read_text().strip()
        fields = limits['cpu_max'].split()
        if len(fields) == 2 and all(value.isdigit() for value in fields) and int(fields[1]) > 0:
            processors = min(processors, max(1, int(fields[0]) // int(fields[1])))
    limits.update(effective_memory_bytes=memory, effective_processors=processors)
    return limits


def compression_policy(resources):
    # The retained 3.068 GB #620 tar was byte-for-byte verified after this
    # bounded MT recipe: 87.50 MB, versus 47.28 MB for the original one block.
    # xz reports 6628 MiB maximum compression memory. Reserve at least 5 GiB
    # for the rest of a sufficiently large host; smaller hosts retain -T1.
    if (resources.get('effective_memory_bytes') or 0) >= 12 * 1024**3 and resources['effective_processors'] >= 3:
        return ['xz', '-6', '-T3', '--block-size=512MiB', '--lzma2=dict=64MiB',
                '--memlimit-compress=7GiB', '--no-adjust', '-c']
    return ['xz', '-6', '-T1', '--lzma2=dict=64MiB', '--memlimit-compress=1GiB', '--no-adjust', '-c']


def pack(build, suite, *, expected_commit=None, runtime_sha256=None, plan_sha256=None,
         job_status='unknown'):
    t0 = time.monotonic()
    build.mkdir(parents=True, exist_ok=True)
    roots, files = scan(build, ROOTS[suite] + OPTIONAL[suite])
    archive = build / f'renderer-{suite}.tar'
    command = ['tar', '--hard-dereference', '-cf', str(archive), '-C', str(build)]
    if roots:
        command += roots
    else:
        command += ['--files-from=/dev/null']
    subprocess.run(command, check=True)
    manifest = {'schema': SCHEMA, 'suite': suite, 'roots': roots, 'files': files,
                'identity': identity(suite, expected_commit, runtime_sha256, plan_sha256, job_status)}
    atomic_json(build / f'renderer-{suite}.manifest.json', manifest)
    (build / f'renderer-{suite}.tar.sha256').write_text(
        f'{sha256(archive)}  {archive.name}\n', encoding='ascii')
    print(f'pack {suite}: {len(files)} files, {archive.stat().st_size} tar bytes, '
          f'{time.monotonic()-t0:.2f}s', flush=True)
    return manifest


def valid_path(path, allowed):
    p = PurePosixPath(path)
    require(bool(path) and not path.startswith('/') and not path.startswith('./') and
            '\\' not in path and '..' not in p.parts and '.' not in p.parts and
            str(p) == path and p.parts[0] in allowed,
            f'Unsafe/unrecognised tar member: {path}')
    return str(p)


def verify_suite(parts, suite, *, expected_commit=None, runtime_sha256=None,
                 plan_sha256=None, complete=False):
    archive = parts / f'renderer-{suite}.tar'
    manifest_path = parts / f'renderer-{suite}.manifest.json'
    sidecar = parts / f'renderer-{suite}.tar.sha256'
    require(all(p.is_file() and not p.is_symlink() for p in (archive, manifest_path, sidecar)),
            f'Missing suite artifact or manifest: {suite}')
    fields = sidecar.read_text(encoding='ascii').strip().split()
    require(len(fields) == 2 and fields[1] == archive.name and fields[0] == sha256(archive),
            f'Suite archive SHA-256 mismatch: {suite}')
    manifest = read_json(manifest_path)
    require(set(manifest) == {'schema', 'suite', 'roots', 'files', 'identity'} and
            manifest['schema'] == SCHEMA and manifest['suite'] == suite,
            f'Invalid suite manifest: {suite}')
    verify_identity(manifest['identity'], suite, expected_commit, runtime_sha256, plan_sha256,
                    complete=complete)
    allowed = ROOTS[suite] + OPTIONAL[suite]
    roots, files = manifest['roots'], manifest['files']
    require(isinstance(roots, list) and len(roots) == len(set(roots)) and
            all(root in allowed for root in roots) and isinstance(files, dict),
            f'Invalid suite directory inventory: {suite}')
    require(all(valid_path(k, allowed) and k.split('/')[0] in roots and
                isinstance(v, dict) and set(v) == {'size', 'sha256'} and
                type(v['size']) is int and v['size'] >= 0 and
                isinstance(v['sha256'], str) and re.fullmatch('[0-9a-f]{64}', v['sha256'])
                for k, v in files.items()), f'Invalid suite file manifest: {suite}')
    seen, members = set(), set()
    with tarfile.open(archive, 'r:') as src:
        for member in src:
            name = valid_path(member.name.rstrip('/'), allowed)
            require(name.split('/')[0] in roots, f'Undeclared tar root: {name}')
            require(name not in members, f'Duplicate tar member: {name}')
            members.add(name)
            if member.isdir():
                continue
            require(member.isfile() and name not in seen and name in files,
                    f'Unexpected/duplicate/nonregular tar member: {name}')
            require(member.size == files[name]['size'], f'Tar file size mismatch: {name}')
            with src.extractfile(member) as stream:
                require(sha256(stream) == files[name]['sha256'],
                        f'Tar member SHA-256 mismatch: {name}')
            seen.add(name)
        if complete:
            for name, status in GATES[suite].items():
                require(name in files, 'Successful worker missing qualification receipt: ' + name)
                require(files[name]['size'] <= 64 * 1024 * 1024, 'Oversized qualification receipt: ' + name)
                with src.extractfile(name) as stream:
                    gate = json.load(stream, object_pairs_hook=unique_json_pairs,
                                     parse_constant=invalid_json_constant)
                require(isinstance(gate, dict) and gate.get('status') == status,
                        'Worker qualification receipt did not pass: ' + name)
        src.fileobj.seek(src.offset)
        while block := src.fileobj.read(1024 * 1024):
            require(not any(block), 'Nonzero bytes after suite tar terminator')
    require(seen == set(files), f'Incomplete suite archive: {suite}')
    return manifest


def merge(parts, output, *, complete, suites=None, expected_commit=None,
          runtime_sha256=None, plan_sha256=None):
    suites = tuple(ROOTS) if suites is None else tuple(suites)
    require(suites in (tuple(ROOTS), PROBE_SUITES, COHORT_PROBE_SUITES), 'Unknown or reordered worker set')
    require(not output.exists(), 'Evidence assembly output must be fresh')
    output.mkdir(parents=True)
    all_files, all_roots = {}, []
    seen_suite = []
    identities, artifacts = {}, {}
    # Unknown, duplicate or cross-wired downloads must not disappear in a merge.
    expected_leaves = {f'renderer-{suite}.{suffix}' for suite in suites
                       for suffix in ('tar', 'tar.sha256', 'manifest.json')}
    require(parts.is_dir(), 'Missing evidence download directory')
    downloads = list(parts.iterdir())
    nested = any(path.is_dir() for path in downloads)
    if nested:
        # download-artifact must preserve namespaces, so duplicate leaves from
        # differently named artifacts cannot silently overwrite one another.
        expected_artifacts = {'renderer-software-vulkan-' + suite for suite in suites}
        require(all(path.is_dir() and not path.is_symlink() and path.name in expected_artifacts
                    for path in downloads), 'Unexpected or duplicated worker artifact')
    else:
        # Also accept a directly exported set of suite files for offline tools.
        require(all(path.is_file() and not path.is_symlink() and path.name in expected_leaves
                    for path in downloads), 'Unexpected or duplicated worker artifact')
    for suite in suites:
        suite_parts = parts / ('renderer-software-vulkan-' + suite) if nested else parts
        if not suite_parts.exists():
            continue
        if nested:
            leaves = {f'renderer-{suite}.{suffix}' for suffix in ('tar', 'tar.sha256', 'manifest.json')}
            require(all(path.is_file() and not path.is_symlink() and path.name in leaves
                        for path in suite_parts.iterdir()), 'Cross-wired artifact namespace: ' + suite)
        elif not any(suite_parts.glob(f'renderer-{suite}.*')):
            continue
        manifest = verify_suite(suite_parts, suite, expected_commit=expected_commit,
                                runtime_sha256=runtime_sha256, plan_sha256=plan_sha256,
                                complete=complete)
        seen_suite.append(suite)
        if complete:
            require(set(ROOTS[suite]).issubset(manifest['roots']),
                    f'Successful suite missing a required evidence root: {suite}')
        require(not set(all_files).intersection(manifest['files']), 'Evidence path collision')
        all_files.update(manifest['files'])
        all_roots.extend(manifest['roots'])
        identities[suite] = manifest['identity']
        artifacts[suite] = {suffix: {'sha256': sha256(suite_parts / f'renderer-{suite}.{suffix}'),
                                     'size': (suite_parts / f'renderer-{suite}.{suffix}').stat().st_size}
                            for suffix in ('tar', 'tar.sha256', 'manifest.json')}
        subprocess.run(['tar', '-xf', str(suite_parts / f'renderer-{suite}.tar'),
                        '-C', str(output)], check=True)
    if complete:
        require(tuple(seen_suite) == suites, 'Successful matrix has missing suite evidence')
    require(all_roots, 'No valid evidence directories were recovered')
    for path, expected in all_files.items():
        actual = output / path
        require(actual.is_file() and not actual.is_symlink() and
                actual.stat().st_size == expected['size'] and
                sha256(actual) == expected['sha256'],
                f'Extracted file changed: {path}')
    atomic_json(output.parent / 'renderer-transport-manifest.json',
                {'schema': SCHEMA, 'roots': all_roots, 'files': all_files,
                 'suites_present': seen_suite, 'complete': complete,
                 'identities': identities, 'artifacts': artifacts})
    (output.parent / 'renderer-evidence-directories.txt').write_text(
        '\n'.join(all_roots) + '\n', encoding='utf-8')
    print(f'merge: {len(all_files)} verified files, {len(all_roots)} roots', flush=True)


def finalize(root, archive):
    """Authenticate every transported byte after bounded path relocation, then seal.

    Publication assembly moves raw captures into their legacy consumer paths.
    Nothing may vanish or change during that move. Derived comparisons and
    reports are inventoried in addition to, never instead of, original evidence.
    Partial failure evidence can be packaged without awarding qualification.
    """
    beginning = time.monotonic()
    transport = read_json(root.parent / 'renderer-transport-manifest.json')
    require(transport['schema'] == SCHEMA, 'Wrong transport schema')
    relocation_path = root / 'renderer-sdvk009-publication' / 'relocation.json'
    relocations = {}
    if relocation_path.is_file():
        relocation = read_json(relocation_path)
        require(relocation.get('schema') == 'sdvk009-publication-relocation/v1'
                and isinstance(relocation.get('files'), dict), 'Invalid relocation manifest')
        relocations = relocation['files']
    original = transport['files']
    require(set(relocations).issubset(original), 'Relocation contains unknown source evidence')
    destinations = set()
    for name, expected in original.items():
        destination = name
        if name in relocations:
            mapping = relocations[name]
            require(isinstance(mapping, dict) and set(mapping) == {'destination', 'sha256', 'bytes'},
                    'Invalid file relocation: ' + name)
            require(mapping['sha256'] == expected['sha256'] and mapping['bytes'] == expected['size'],
                    'Relocation source identity differs: ' + name)
            destination = valid_path(mapping['destination'], ('renderer-sdvk009-publication',))
        require(destination not in destinations, 'Duplicate relocated destination: ' + destination)
        destinations.add(destination)
        actual = root / destination
        require(actual.is_file() and not actual.is_symlink() and
                actual.stat().st_size == expected['size'] and sha256(actual) == expected['sha256'],
                'Transported evidence lost or altered during assembly: ' + name)
    allowed = {name for names in ROOTS.values() for name in names}
    allowed.update(name for names in OPTIONAL.values() for name in names)
    allowed.update(('renderer-sdvk009-publication', 'renderer-ci-timings', 'renderer-ci-aggregation'))
    require(all(path.is_dir() and not path.is_symlink() and path.name in allowed
                for path in root.iterdir()), 'Unknown final evidence root')
    roots, files = scan(root, sorted(path.name for path in root.iterdir()))
    require(destinations <= set(files), 'Final inventory omitted original evidence')
    for name in set(files) - destinations:
        require(name.split('/')[0] in ('renderer-sdvk009-publication', 'renderer-ci-timings',
                                       'renderer-ci-aggregation'),
                'Unregistered additional worker evidence: ' + name)
    provenance = root / 'renderer-ci-aggregation'
    atomic_json(provenance / 'transport-manifest.json', transport)
    resources = packaging_resources()
    compression = compression_policy(resources)
    atomic_json(provenance / 'packaging-policy.json', {
        'schema': 'sdvk-software-vulkan-packaging/v1', 'compression_argv': compression,
        'host_resources': resources,
        'lossless': True, 'native_workloads_changed': False,
        'transported_files_verified': len(original), 'relocated_files': len(relocations)})
    roots, files = scan(root, sorted(path.name for path in root.iterdir()))
    manifest = {**transport, 'roots': roots, 'files': files,
                'transported_files_verified': len(original), 'relocated_files': len(relocations)}
    manifest_path = archive.parent / 'renderer-evidence-manifest.json'
    atomic_json(manifest_path, manifest)
    (archive.parent / 'renderer-evidence-directories.txt').write_text('\n'.join(roots) + '\n', encoding='utf-8')
    require(not archive.exists(), 'Final archive must be fresh')
    started = time.monotonic()
    with archive.open('xb') as output:
        tar = subprocess.Popen(['tar', '--hard-dereference', '-cf', '-', '-C', str(root), *roots],
                               stdout=subprocess.PIPE)
        try:
            xz = subprocess.run(compression, stdin=tar.stdout, stdout=output, check=False)
        finally:
            tar.stdout.close()
            tar_code = tar.wait()
    require(tar_code == 0 and xz.returncode == 0, 'Final archive compression failed')
    compressed = time.monotonic()
    verify_final(archive, manifest_path)
    finished = time.monotonic()
    report = {'schema': 'sdvk-software-vulkan-packaging-timing/v1',
              'compression_argv': compression, 'compression_seconds': round(compressed-started, 3),
              'host_resources': resources,
              'verification_seconds': round(finished-compressed, 3),
              'assembly_verification_seconds': round(started-beginning, 3),
              'total_seconds': round(finished-beginning, 3),
              'archive_bytes': archive.stat().st_size,
              'uncompressed_file_bytes': sum(item['size'] for item in files.values()),
              'files': len(files), 'transport_artifacts': transport['artifacts'],
              'physical_gpu_qualified': False, 'performance_accepted': False}
    atomic_json(archive.parent / 'renderer-evidence-packaging.json', report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return report


def verify_final(archive, manifest_path):
    expected = read_json(manifest_path)
    require(expected['schema'] == SCHEMA, 'Wrong final manifest schema')
    files, roots = expected['files'], expected['roots']
    seen = set()
    members = set()
    # tarfile's r|xz adapter repeatedly copies very large decompressed buffers
    # for these highly repetitive captures. Stream external xz instead, while
    # retaining every per-member SHA/size/type check and the XZ CRC exit check.
    decoder = subprocess.Popen(['xz', '-dc', '--', str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=decoder.stdout, mode='r|', bufsize=1024 * 1024) as src:
            for member in src:
                name = valid_path(member.name.rstrip('/'), roots)
                require(name not in members, f'Duplicate final member: {name}')
                members.add(name)
                if member.isdir():
                    continue
                require(member.isfile() and name not in seen and name in files,
                        f'Unexpected/duplicate final member: {name}')
                require(member.size == files[name]['size'], f'Final size mismatch: {name}')
                with src.extractfile(member) as stream:
                    require(sha256(stream) == files[name]['sha256'],
                            f'Final SHA-256 mismatch: {name}')
                seen.add(name)
            require(not any(src.fileobj.buf), 'Nonzero bytes after final tar terminator')
        # Consume through the stream trailer: an early tar end marker must not
        # hide an invalid XZ checksum or an appended second tar archive.
        while block := decoder.stdout.read(1024 * 1024):
            require(not any(block), 'Nonzero bytes after final tar terminator')
        require(decoder.wait() == 0, 'Final XZ integrity check failed')
    finally:
        decoder.stdout.close()
        if decoder.poll() is None:
            decoder.terminate()
        decoder.wait()
    require(seen == set(files), 'Final archive has missing files')
    archive.with_suffix(archive.suffix + '.sha256').write_text(
        f'{sha256(archive)}  {archive.name}\n', encoding='ascii')
    print(f'final: {len(files)} verified files, {archive.stat().st_size} bytes', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest='command', required=True)
    p = cmd.add_parser('pack')
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--suite', choices=ROOTS, required=True)
    p.add_argument('--job-status', choices=('success', 'failure', 'cancelled', 'unknown'), required=True)
    m = cmd.add_parser('merge')
    m.add_argument('--parts', type=Path, required=True)
    m.add_argument('--out', type=Path, required=True)
    m.add_argument('--complete', action='store_true')
    m.add_argument('--suites', type=lambda text: tuple(text.split(',')))
    for command in (p, m):
        command.add_argument('--expected-commit', required=True)
        command.add_argument('--runtime-sha256', required=True)
        command.add_argument('--plan-sha256', required=True)
    f = cmd.add_parser('finalize')
    f.add_argument('--root', type=Path, required=True)
    f.add_argument('--archive', type=Path, required=True)
    v = cmd.add_parser('verify-final')
    v.add_argument('--archive', type=Path, required=True)
    v.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'pack':
        pack(args.build.resolve(), args.suite, expected_commit=args.expected_commit,
             runtime_sha256=args.runtime_sha256, plan_sha256=args.plan_sha256,
             job_status=args.job_status)
    elif args.command == 'merge':
        merge(args.parts.resolve(), args.out.resolve(), complete=args.complete, suites=args.suites,
              expected_commit=args.expected_commit, runtime_sha256=args.runtime_sha256,
              plan_sha256=args.plan_sha256)
    elif args.command == 'finalize':
        finalize(args.root.resolve(), args.archive.resolve())
    else:
        verify_final(args.archive, args.manifest)


if __name__ == '__main__':
    main()
