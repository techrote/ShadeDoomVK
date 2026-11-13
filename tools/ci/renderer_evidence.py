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
import stat
import subprocess
import tarfile
import time

SCHEMA = 'sdvk-software-vulkan-evidence/v1'
ROOTS = {
    'corpus': ('renderer-native', 'renderer-sdvk008-control', 'renderer-sdvk008-preflight'),
    'publication': ('renderer-sdvk009-content', 'renderer-sdvk009-publication',
                    'renderer-sdvk010', 'renderer-sdvk150', 'renderer-sdvk153',
                    'renderer-sdvk158', 'renderer-sdvk161', 'renderer-sdvk014-controlled'),
}
OPTIONAL = {'publication': ('renderer-ci-timings',), 'corpus': ()}


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


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


def pack(build, suite):
    t0 = time.monotonic()
    roots, files = scan(build, ROOTS[suite] + OPTIONAL[suite])
    archive = build / f'renderer-{suite}.tar'
    command = ['tar', '--hard-dereference', '-cf', str(archive), '-C', str(build)]
    if roots:
        command += roots
    else:
        command += ['--files-from=/dev/null']
    subprocess.run(command, check=True)
    manifest = {'schema': SCHEMA, 'suite': suite, 'roots': roots, 'files': files}
    atomic_json(build / f'renderer-{suite}.manifest.json', manifest)
    (build / f'renderer-{suite}.tar.sha256').write_text(
        f'{sha256(archive)}  {archive.name}\n', encoding='ascii')
    print(f'pack {suite}: {len(files)} files, {archive.stat().st_size} tar bytes, '
          f'{time.monotonic()-t0:.2f}s', flush=True)
    return manifest


def valid_path(path, allowed):
    p = PurePosixPath(path)
    require(bool(path) and not path.startswith('/') and not path.startswith('./') and
            '\\' not in path and '..' not in p.parts and p.parts[0] in allowed,
            f'Unsafe/unrecognised tar member: {path}')
    return str(p)


def verify_suite(parts, suite):
    archive = parts / f'renderer-{suite}.tar'
    manifest_path = parts / f'renderer-{suite}.manifest.json'
    sidecar = parts / f'renderer-{suite}.tar.sha256'
    require(all(p.is_file() and not p.is_symlink() for p in (archive, manifest_path, sidecar)),
            f'Missing suite artifact or manifest: {suite}')
    fields = sidecar.read_text(encoding='ascii').strip().split()
    require(len(fields) == 2 and fields[1] == archive.name and fields[0] == sha256(archive),
            f'Suite archive SHA-256 mismatch: {suite}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(set(manifest) == {'schema', 'suite', 'roots', 'files'} and
            manifest['schema'] == SCHEMA and manifest['suite'] == suite,
            f'Invalid suite manifest: {suite}')
    allowed = ROOTS[suite] + OPTIONAL[suite]
    roots, files = manifest['roots'], manifest['files']
    require(isinstance(roots, list) and len(roots) == len(set(roots)) and
            all(root in allowed for root in roots) and isinstance(files, dict),
            f'Invalid suite directory inventory: {suite}')
    require(all(valid_path(k, allowed) and k.split('/')[0] in roots and
                isinstance(v, dict) and set(v) == {'size', 'sha256'} and
                type(v['size']) is int and v['size'] >= 0 and
                isinstance(v['sha256'], str) and len(v['sha256']) == 64
                for k, v in files.items()), f'Invalid suite file manifest: {suite}')
    seen = set()
    with tarfile.open(archive, 'r:') as src:
        for member in src:
            name = valid_path(member.name.rstrip('/'), allowed)
            require(name.split('/')[0] in roots, f'Undeclared tar root: {name}')
            if member.isdir():
                continue
            require(member.isfile() and name not in seen and name in files,
                    f'Unexpected/duplicate/nonregular tar member: {name}')
            require(member.size == files[name]['size'], f'Tar file size mismatch: {name}')
            with src.extractfile(member) as stream:
                require(sha256(stream) == files[name]['sha256'],
                        f'Tar member SHA-256 mismatch: {name}')
            seen.add(name)
    require(seen == set(files), f'Incomplete suite archive: {suite}')
    return manifest


def merge(parts, output, *, complete):
    output.mkdir(parents=True, exist_ok=True)
    all_files, all_roots = {}, []
    seen_suite = []
    for suite in ROOTS:
        if not any(parts.glob(f'renderer-{suite}.*')):
            continue
        manifest = verify_suite(parts, suite)
        seen_suite.append(suite)
        if complete:
            require(set(ROOTS[suite]).issubset(manifest['roots']),
                    f'Successful suite missing a required evidence root: {suite}')
        require(not set(all_files).intersection(manifest['files']), 'Evidence path collision')
        all_files.update(manifest['files'])
        all_roots.extend(manifest['roots'])
        subprocess.run(['tar', '-xf', str(parts / f'renderer-{suite}.tar'),
                        '-C', str(output)], check=True)
    if complete:
        require(set(seen_suite) == set(ROOTS), 'Successful matrix has missing suite evidence')
    require(all_roots, 'No valid evidence directories were recovered')
    for path, expected in all_files.items():
        actual = output / path
        require(actual.is_file() and not actual.is_symlink() and
                actual.stat().st_size == expected['size'] and
                sha256(actual) == expected['sha256'],
                f'Extracted file changed: {path}')
    atomic_json(output.parent / 'renderer-evidence-manifest.json',
                {'schema': SCHEMA, 'roots': all_roots, 'files': all_files,
                 'suites_present': seen_suite, 'complete': complete})
    (output.parent / 'renderer-evidence-directories.txt').write_text(
        '\n'.join(all_roots) + '\n', encoding='utf-8')
    print(f'merge: {len(all_files)} verified files, {len(all_roots)} roots', flush=True)


def verify_final(archive, manifest_path):
    expected = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(expected['schema'] == SCHEMA, 'Wrong final manifest schema')
    files, roots = expected['files'], expected['roots']
    seen = set()
    with tarfile.open(archive, mode='r|xz') as src:
        for member in src:
            name = valid_path(member.name.rstrip('/'), roots)
            if member.isdir():
                continue
            require(member.isfile() and name not in seen and name in files,
                    f'Unexpected/duplicate final member: {name}')
            require(member.size == files[name]['size'], f'Final size mismatch: {name}')
            with src.extractfile(member) as stream:
                require(sha256(stream) == files[name]['sha256'],
                        f'Final SHA-256 mismatch: {name}')
            seen.add(name)
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
    m = cmd.add_parser('merge')
    m.add_argument('--parts', type=Path, required=True)
    m.add_argument('--out', type=Path, required=True)
    m.add_argument('--complete', action='store_true')
    v = cmd.add_parser('verify-final')
    v.add_argument('--archive', type=Path, required=True)
    v.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'pack':
        pack(args.build.resolve(), args.suite)
    elif args.command == 'merge':
        merge(args.parts.resolve(), args.out.resolve(), complete=args.complete)
    else:
        verify_final(args.archive, args.manifest)


if __name__ == '__main__':
    main()
