#!/usr/bin/env python3
"""Bounded, read-only rendezvous for exactly three immutable native probe packets.

This transfers evidence only. The renderer harness independently validates each
probe, chooses the compatible cohort and authorizes the original full captures.
Missing artifacts may be polled; a network error or invalid packet is never retried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

WORKERS = ('controls', 'witness-1', 'witness-2')
SCHEMA = 'sdvk009-cohort-artifacts/v1'
MAX_SECONDS = 600
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 4096
CHUNK = 1024 * 1024


class CohortError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CohortError(message)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON member')
        result[key] = value
    return result


def invalid_constant(value):
    raise CohortError('Nonfinite JSON value')


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def sha256(path, *, deadline=None, clock=time.monotonic):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(CHUNK):
            if deadline is not None:
                remaining(deadline, clock)
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def remaining(deadline, clock):
    seconds = deadline - clock()
    require(seconds > 0, 'Cohort artifact barrier exceeded its 600-second maximum')
    return min(seconds, 30)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def storage_url(value):
    parsed = urllib.parse.urlsplit(value)
    host = parsed.hostname or ''
    require(parsed.scheme == 'https' and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and (host.endswith('.blob.core.windows.net') or host.endswith('.githubusercontent.com')),
            'Artifact download redirect is not approved HTTPS storage')
    return value


class ArtifactAPI:
    def __init__(self, repository, run_id, token, *, clock=time.monotonic, opener=None):
        require(bool(token), 'Read-only GITHUB_TOKEN is required for artifact download')
        self.base = 'https://api.github.com/repos/' + repository
        self.run_id, self.token, self.clock = run_id, token, clock
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def request(self, url, deadline, *, authenticated):
        headers = {'User-Agent': 'ShadeDoomVK-cohort-artifact-reader'}
        if authenticated:
            require(url.startswith(self.base + '/'), 'Refusing authenticated request outside repository API')
            headers.update({'Authorization': 'Bearer ' + self.token,
                            'Accept': 'application/vnd.github+json',
                            'X-GitHub-Api-Version': '2022-11-28'})
        try:
            return self.opener.open(urllib.request.Request(url, headers=headers),
                                    timeout=remaining(deadline, self.clock)), None
        except urllib.error.HTTPError as error:
            code, location = error.code, error.headers.get('Location')
            error.close()
            if code in (301, 302, 303, 307, 308) and location:
                return None, location
            raise CohortError('Artifact HTTP request failed with status ' + str(code)) from None
        except (OSError, urllib.error.URLError):
            raise CohortError('Artifact network request failed; no retry is permitted') from None

    def read(self, response, deadline, maximum, output=None):
        total, pieces = 0, []
        with response:
            read = getattr(response, 'read1', response.read)
            while True:
                remaining(deadline, self.clock)
                block = read(min(CHUNK, maximum - total + 1))
                if not block:
                    break
                total += len(block)
                require(total <= maximum, 'Artifact response exceeds its byte limit')
                if output is None:
                    pieces.append(block)
                else:
                    output.write(block)
        return b''.join(pieces) if output is None else total

    def list(self, deadline):
        response, redirect = self.request(self.base + '/actions/runs/' + self.run_id +
                                          '/artifacts?per_page=100', deadline, authenticated=True)
        require(redirect is None, 'Unexpected artifact-list API redirect')
        return decode(self.read(response, deadline, 2 * CHUNK))

    def download(self, artifact_id, destination, expected_size, deadline):
        response, redirect = self.request(self.base + '/actions/artifacts/' + str(artifact_id) + '/zip',
                                          deadline, authenticated=True)
        redirects = 0
        while redirect is not None:
            redirects += 1
            require(redirects <= 3, 'Too many artifact storage redirects')
            # A fresh request carries no Authorization header to signed storage.
            response, redirect = self.request(storage_url(redirect), deadline, authenticated=False)
        with destination.open('xb') as output:
            size = self.read(response, deadline, expected_size, output)
        require(size == expected_size, 'Downloaded artifact size differs from API metadata')


def expected_names(run_id, attempt):
    prefix = 'sdvk-cohort-probe-' + run_id + '-' + attempt + '-'
    return {worker: prefix + worker for worker in WORKERS}


def expected_artifact(worker, row):
    # Deliberately omit archive_download_url and every other API URL/header.
    return {'worker': worker, 'artifact_id': row['id'], 'name': row['name'],
            'expected_archive_sha256': row['digest'][7:], 'expected_archive_bytes': row['size_in_bytes']}


def select_artifacts(payload, names, run_id, commit):
    require(isinstance(payload, dict) and isinstance(payload.get('artifacts'), list)
            and type(payload.get('total_count')) is int
            and payload['total_count'] == len(payload['artifacts']) <= 100,
            'Artifact listing is incomplete or exceeds the fixed page bound')
    selected = {}
    prefix = names['controls'][:-len('controls')]
    for row in payload['artifacts']:
        require(isinstance(row, dict) and isinstance(row.get('name'), str), 'Malformed artifact metadata')
        if not row['name'].startswith(prefix):
            continue
        require(row['name'] in names.values(), 'Unknown cohort probe artifact')
        worker = next(worker for worker, name in names.items() if row['name'] == name)
        require(worker not in selected, 'Duplicated cohort probe artifact')
        require(type(row.get('id')) is int and row['id'] > 0
                and type(row.get('size_in_bytes')) is int and 0 < row['size_in_bytes'] <= MAX_ARCHIVE
                and row.get('expired') is False and isinstance(row.get('digest'), str)
                and re.fullmatch(r'sha256:[0-9a-f]{64}', row['digest']), 'Invalid immutable artifact identity')
        workflow = row.get('workflow_run', {})
        require(isinstance(workflow, dict) and type(workflow.get('id')) is int and str(workflow['id']) == run_id
                and workflow.get('head_sha') == commit, 'Probe artifact comes from a different source or run')
        selected[worker] = row
    require(len({row['id'] for row in selected.values()}) == len(selected), 'Reused probe artifact ID')
    require(len({row['digest'] for row in selected.values()}) == len(selected), 'Reused probe artifact archive')
    return selected


def restore_archive(archive, destination, worker, *, deadline=None, clock=time.monotonic):
    require(not destination.exists() and not destination.is_symlink(), 'Peer evidence destination must be fresh')
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        require(0 < len(infos) <= MAX_FILES, 'Probe ZIP has an invalid entry count')
        members, total = {}, 0
        for info in infos:
            raw = info.filename
            require(raw == info.orig_filename and '\x00' not in raw and '\\' not in raw
                    and ':' not in raw and not raw.startswith('/'), 'Unsafe probe ZIP path')
            name = raw[:-1] if raw.endswith('/') else raw
            path = PurePosixPath(name)
            require(name and str(path) == name and not any(part in ('.', '..') for part in path.parts)
                    and name not in members, 'Unsafe or duplicate probe ZIP member')
            mode = (info.external_attr >> 16) & 0xffff
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)
                    and (stat.S_IFMT(mode) != stat.S_IFDIR or info.is_dir())
                    and (stat.S_IFMT(mode) != stat.S_IFREG or not info.is_dir())
                    and not (info.flag_bits & 1)
                    and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    'Probe ZIP contains unsupported or nonregular evidence')
            require(not info.is_dir() or info.file_size == 0, 'Probe ZIP directory contains payload')
            total += info.file_size
            require(0 <= info.file_size <= MAX_ARCHIVE and total <= MAX_EXPANDED,
                    'Probe ZIP expands beyond its fixed byte budget')
            members[name] = info
        # upload-artifact normally emits root contents. Also accept its single
        # explicit directory wrapper, never mixed layouts or arbitrary prefixes.
        wrapper = 'renderer-sdvk009-probe-' + worker
        wrapped = all(name == wrapper or name.startswith(wrapper + '/') for name in members)
        require(not wrapped or wrapper not in members or members[wrapper].is_dir(), 'Probe ZIP wrapper is not a directory')
        names = {name[len(wrapper) + 1:] if wrapped else name: info
                 for name, info in members.items() if not (wrapped and name == wrapper)}
        require(all(names.get(name) is not None and not names[name].is_dir() for name in
                    ('probe.json', 'probe-start.json', 'probe-registration.json', 'manifest.json', 'manifest.json.sha256')),
                'Probe ZIP lacks mandatory evidence at its declared root')
        for name in names:
            require(all(str(parent) not in names or names[str(parent)].is_dir()
                        for parent in PurePosixPath(name).parents if str(parent) != '.'),
                    'Probe ZIP has conflicting file and directory paths')
        destination.mkdir(parents=True)
        for name, info in names.items():
            target = destination / name
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as src, target.open('xb') as dst:
                actual = 0
                while block := src.read(CHUNK):
                    if deadline is not None:
                        remaining(deadline, clock)
                    actual += len(block)
                    require(actual <= info.file_size, 'Expanded probe ZIP member exceeds declared length')
                    dst.write(block)
                require(actual == info.file_size, 'Incomplete probe ZIP member')
        digest = sha256(destination / 'manifest.json', deadline=deadline, clock=clock)
        require((destination / 'manifest.json.sha256').read_text(encoding='ascii') ==
                digest + '  manifest.json\n', 'Probe manifest SHA-256 differs from its seal')
        manifest = decode((destination / 'manifest.json').read_bytes())
        probe = decode((destination / 'probe.json').read_bytes())
        require(manifest.get('worker') == probe.get('worker') == worker
                and manifest.get('status') == probe.get('status') == 'PASS',
                'Probe worker failed, cancelled or is cross-wired')
        return digest


def collect(args, client=None, *, clock=time.monotonic, sleep=time.sleep):
    started = clock()
    archives = None
    report = {'schema': 'sdvk009-cohort-artifact-barrier/v1', 'status': 'FAIL',
              'automatic_retries': 0, 'deadline_seconds': MAX_SECONDS, 'polls': 0,
              'expected_workers': list(WORKERS), 'selected_artifacts': [], 'received_archives': [],
              'downloaded': [], 'error': 'Barrier did not finish'}
    try:
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository)
                and re.fullmatch(r'[1-9][0-9]*', args.run_id)
                and re.fullmatch(r'[1-9][0-9]*', args.run_attempt), 'Invalid workflow identity')
        require(re.fullmatch('[0-9a-f]{40}', args.expected_commit)
                and re.fullmatch('[0-9a-f]{64}', args.plan_sha256), 'Malformed source or plan digest')
        require(not args.out.exists() and not args.out.is_symlink()
                and not args.artifact_set.exists() and not args.artifact_set.is_symlink(),
                'Cohort rendezvous output must be fresh')
        archives = args.out.with_name(args.out.name + '-archives')
        require(not archives.exists() and not archives.is_symlink(), 'Probe ZIP download directory must be fresh')
        if client is None:
            client = ArtifactAPI(args.repository, args.run_id, os.environ.get('GITHUB_TOKEN'), clock=clock)
        archives.mkdir(parents=True)
        names = expected_names(args.run_id, args.run_attempt)
        deadline = started + MAX_SECONDS
        while True:
            remaining(deadline, clock)
            selected = select_artifacts(client.list(deadline), names, args.run_id, args.expected_commit)
            report['polls'] += 1
            report['selected_artifacts'] = [expected_artifact(worker, selected[worker])
                                           for worker in WORKERS if worker in selected]
            report['missing_workers'] = [worker for worker in WORKERS if worker not in selected]
            if not report['missing_workers']:
                break
            sleep(min(5, remaining(deadline, clock)))
        artifacts = []
        for worker in WORKERS:
            row = selected[worker]
            archive = archives / (worker + '.zip')
            report['active_artifact'] = expected_artifact(worker, row)
            report['phase'] = 'download'
            client.download(row['id'], archive, row['size_in_bytes'], deadline)
            report['phase'] = 'authenticate-archive'
            require(archive.stat().st_size == row['size_in_bytes']
                    and sha256(archive, deadline=deadline, clock=clock) == row['digest'][7:],
                    'Probe ZIP SHA-256 or byte count differs from API identity')
            remaining(deadline, clock)
            report['phase'] = 'restore-evidence'
            manifest = restore_archive(archive, args.out / worker, worker, deadline=deadline, clock=clock)
            artifact = {'worker': worker, 'artifact_id': row['id'], 'name': row['name'],
                        'archive_sha256': row['digest'][7:], 'archive_bytes': row['size_in_bytes'],
                        'manifest_sha256': manifest}
            artifacts.append(artifact)
            report['downloaded'].append(artifact)
        result = {'schema': SCHEMA, 'github_run_id': args.run_id, 'github_run_attempt': args.run_attempt,
                  'source_commit': args.expected_commit, 'plan_sha256': args.plan_sha256, 'artifacts': artifacts}
        remaining(deadline, clock)
        write_json(args.artifact_set, result)
        report.update(status='PASS', error='', phase='complete', artifact_set_sha256=sha256(args.artifact_set))
        return result
    except BaseException as error:
        # Do not record HTTP objects, signed URLs, request headers or credentials.
        report['error'] = str(error) if isinstance(error, CohortError) else 'Artifact rendezvous failed: ' + type(error).__name__
        raise
    finally:
        # Preserve actual received identities even if a transfer stopped midway
        # or a digest/ZIP check failed. The failure-only workflow upload retains
        # these bounded files; successful peers are not duplicated in the final
        # evidence archive. No acceptance work occurs after the barrier deadline.
        if archives is not None:
            for worker in WORKERS:
                path = archives / (worker + '.zip')
                if not path.is_file() or path.is_symlink():
                    continue
                item = {'worker': worker, 'archive_file': path.name}
                try:
                    item['actual_archive_bytes'] = path.stat().st_size
                    if item['actual_archive_bytes'] <= MAX_ARCHIVE:
                        item['actual_archive_sha256'] = sha256(path)
                    else:
                        item['error'] = 'Received archive exceeds its fixed byte budget'
                except OSError as error:
                    item['error'] = 'Could not read received archive: ' + type(error).__name__
                report['received_archives'].append(item)
        report['elapsed_seconds'] = round(clock() - started, 3)
        write_json(args.report, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'run-id', 'run-attempt', 'expected-commit', 'plan-sha256'):
        parser.add_argument('--' + name, required=True)
    for name in ('out', 'artifact-set', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        collect(args)
    except BaseException as error:
        message = str(error) if isinstance(error, CohortError) else type(error).__name__
        print('FAIL: ' + message, flush=True)
        return 1
    print('PASS: exactly three immutable probe artifacts authenticated', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
