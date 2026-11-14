"""CPU-only rendezvous, immutable identity and hostile-archive controls."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import urllib.error
import zipfile

import renderer_cohort_artifacts as cohort


SOURCE = '1' * 40
PLAN = '2' * 64


def json_bytes(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def packet(worker, *, status='PASS', wrapper='', extra=()):
    files = {'probe.json': json_bytes({'worker': worker, 'status': status}),
             'probe-start.json': b'{"status":"FAIL"}\n',
             'probe-registration.json': b'{"status":"FAIL"}\n',
             'captures/independent.bin': worker.encode()}
    manifest = json_bytes({'worker': worker, 'status': status, 'files': {
        name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        for name, data in files.items()}})
    files['manifest.json'] = manifest
    files['manifest.json.sha256'] = (hashlib.sha256(manifest).hexdigest() + '  manifest.json\n').encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in files.items():
            zipped.writestr(wrapper + name, data)
        for name, data in extra:
            zipped.writestr(name, data)
    return output.getvalue()


def metadata(worker, artifact_id, raw, *, attempt='1'):
    return {'id': artifact_id, 'name': cohort.expected_names('123', attempt)[worker],
            'size_in_bytes': len(raw), 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
            'expired': False, 'workflow_run': {'id': 123, 'head_sha': SOURCE}}


class Clock:
    def __init__(self):
        self.seconds = 0

    def __call__(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


class Client:
    def __init__(self):
        self.raw = {index: packet(worker) for index, worker in enumerate(cohort.WORKERS, 1)}
        self.rows = [metadata(worker, index, self.raw[index])
                     for index, worker in enumerate(cohort.WORKERS, 1)]
        self.list_calls, self.downloads = 0, []

    def list(self, deadline):
        self.list_calls += 1
        return {'total_count': len(self.rows), 'artifacts': copy.deepcopy(self.rows)}

    def download(self, artifact_id, destination, size, deadline):
        self.downloads.append(artifact_id)
        destination.write_bytes(self.raw[artifact_id])


class ArtifactBarrierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.args = SimpleNamespace(repository='owner/repo', run_id='123', run_attempt='1',
            expected_commit=SOURCE, plan_sha256=PLAN, out=self.root / 'peers',
            artifact_set=self.root / 'artifacts.json', report=self.root / 'diagnostics/barrier.json')
        self.client, self.clock = Client(), Clock()

    def collect(self):
        return cohort.collect(self.args, self.client, clock=self.clock, sleep=self.clock.sleep)

    def report(self):
        return json.loads(self.args.report.read_text())

    def test_three_immutable_peers_restore_in_canonical_order(self):
        self.client.rows.reverse()
        result = self.collect()
        self.assertEqual(result['schema'], 'sdvk009-cohort-artifacts/v1')
        self.assertEqual(result['source_commit'], SOURCE)
        self.assertEqual(result['plan_sha256'], PLAN)
        self.assertEqual([item['worker'] for item in result['artifacts']], list(cohort.WORKERS))
        self.assertEqual(self.client.downloads, [1, 2, 3])
        self.assertEqual(sorted(path.name for path in self.args.out.iterdir()), sorted(cohort.WORKERS))
        for item in result['artifacts']:
            root = self.args.out / item['worker']
            self.assertEqual(item['manifest_sha256'], cohort.sha256(root / 'manifest.json'))
            self.assertEqual(item['archive_sha256'], hashlib.sha256(self.client.raw[item['artifact_id']]).hexdigest())
            self.assertEqual((root / 'captures/independent.bin').read_text(), item['worker'])
        self.assertEqual(self.report()['status'], 'PASS')
        self.assertEqual(self.report()['automatic_retries'], 0)
        self.assertEqual(self.clock.seconds, 15)
        self.assertEqual(self.client.list_calls, 4)
        self.assertEqual(self.report()['settlement_requested_seconds'], 15)
        self.assertEqual(self.report()['settlement_actual_seconds'], 15)

    def test_changed_disappeared_or_duplicated_complete_pins_fail_without_download(self):
        mutations = (lambda rows: rows[0].update(id=999), lambda rows: rows.pop(),
                     lambda rows: rows.append(copy.deepcopy(rows[0])))
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                self.args.out = Path(folder) / 'peers'
                self.args.artifact_set = Path(folder) / 'set.json'
                self.client, self.clock = Client(), Clock()
                original = self.client.list

                def listing(deadline):
                    if self.client.list_calls == 1:
                        mutate(self.client.rows)
                    return original(deadline)

                self.client.list = listing
                with self.assertRaises(cohort.CohortError):
                    self.collect()
                self.assertEqual(self.clock.seconds, 5)
                self.assertEqual(self.client.downloads, [])
                self.assertFalse(self.args.artifact_set.exists())
                self.assertEqual(self.report()['settlement_actual_seconds'], 5)

    def test_settlement_is_inside_the_existing_six_hundred_second_deadline(self):
        original = self.client.list

        def late_complete(deadline):
            payload = original(deadline)
            if self.clock.seconds < 590:
                payload['artifacts'].pop()
                payload['total_count'] -= 1
            return payload

        self.client.list = late_complete
        with self.assertRaisesRegex(cohort.CohortError, '600-second maximum'):
            self.collect()
        self.assertEqual(self.clock.seconds, 600)
        self.assertEqual(self.client.downloads, [])
        self.assertEqual(self.report()['settlement_actual_seconds'], 10)
        self.assertFalse(self.args.artifact_set.exists())

    def test_first_http_error_after_settlement_is_fatal_and_records_safe_stage(self):
        for stage in ('github-api', 'artifact-storage'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as folder:
                self.args.out = Path(folder) / 'peers'
                self.args.artifact_set = Path(folder) / 'set.json'
                self.clock = Clock()
                opener = mock.Mock()
                failure = urllib.error.HTTPError('https://hidden/?token=secret', 404, '', {}, io.BytesIO())
                replies = [failure]
                if stage == 'artifact-storage':
                    replies.insert(0, urllib.error.HTTPError('https://api.github.com', 302, '',
                        {'Location': 'https://example.blob.core.windows.net/file?signature=secret'}, io.BytesIO()))
                opener.open.side_effect = replies
                self.client = cohort.ArtifactAPI('owner/repo', '123', 'token', opener=opener, clock=self.clock)
                listing = Client()
                self.client.list = listing.list
                with self.assertRaises(cohort.CohortHTTPError):
                    self.collect()
                self.assertEqual(self.clock.seconds, 15)
                self.assertEqual(listing.list_calls, 4)
                self.assertEqual(opener.open.call_count, len(replies))
                self.assertEqual(self.report()['http_error'], {'status_code': 404, 'stage': stage})
                self.assertEqual(self.report()['received_archives'], [])
                self.assertNotIn('secret', self.args.report.read_text())
                self.assertFalse(self.args.artifact_set.exists())

    def test_missing_peer_exhausts_one_bounded_barrier_without_execution_or_download(self):
        self.client.rows.pop()
        with self.assertRaisesRegex(cohort.CohortError, '600-second maximum'):
            self.collect()
        self.assertEqual(self.clock.seconds, 600)
        self.assertEqual(self.client.list_calls, 120)
        self.assertEqual(self.client.downloads, [])
        self.assertFalse(self.args.artifact_set.exists())
        self.assertEqual(self.report()['missing_workers'], ['witness-2'])
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_one_failed_or_crosswired_probe_cannot_release_a_partial_cohort(self):
        for status, identity in (('FAIL', 'witness-1'), ('CANCELLED', 'witness-1'), ('PASS', 'controls')):
            with self.subTest(status=status, identity=identity), tempfile.TemporaryDirectory() as folder:
                self.args.out = Path(folder) / 'peers'
                self.args.artifact_set = Path(folder) / 'set.json'
                self.client = Client()
                self.client.raw[2] = packet(identity, status=status)
                self.client.rows[1] = metadata('witness-1', 2, self.client.raw[2])
                with self.assertRaisesRegex(cohort.CohortError, 'failed, cancelled or is cross-wired|Reused probe artifact archive'):
                    self.collect()
                self.assertFalse(self.args.artifact_set.exists())
                self.assertEqual(self.report()['status'], 'FAIL')
                self.assertLessEqual(len(self.report()['downloaded']), 1)

    def test_corrupt_archive_is_rejected_before_extraction_and_retains_partial_progress(self):
        self.client.raw[2] = b'corrupt retained download'
        with self.assertRaisesRegex(cohort.CohortError, 'SHA-256 or byte count'):
            self.collect()
        self.assertFalse((self.args.out / 'witness-1').exists())
        self.assertTrue((self.args.out / 'controls/manifest.json').is_file())
        self.assertFalse(self.args.artifact_set.exists())
        self.assertEqual([item['worker'] for item in self.report()['downloaded']], ['controls'])
        report = self.report()
        self.assertEqual(report['active_artifact'], cohort.expected_artifact('witness-1', self.client.rows[1]))
        self.assertEqual(len(report['selected_artifacts']), 3)
        actual = report['received_archives'][1]
        self.assertEqual(actual['worker'], 'witness-1')
        self.assertEqual(actual['actual_archive_bytes'], len(self.client.raw[2]))
        self.assertEqual(actual['actual_archive_sha256'], hashlib.sha256(self.client.raw[2]).hexdigest())
        self.assertNotEqual(actual['actual_archive_sha256'], report['active_artifact']['expected_archive_sha256'])
        self.assertEqual(report['phase'], 'authenticate-archive')

    def test_interrupted_download_retains_received_bytes_and_safe_expected_identity(self):
        original = self.client.download

        def interrupted(artifact_id, destination, size, deadline):
            if artifact_id == 2:
                destination.write_bytes(b'partial')
                raise urllib.error.URLError('https://storage.invalid/?token=secret')
            return original(artifact_id, destination, size, deadline)

        self.client.download = interrupted
        with self.assertRaises(urllib.error.URLError):
            self.collect()
        report = self.report()
        self.assertEqual(report['phase'], 'download')
        self.assertEqual(report['active_artifact']['artifact_id'], 2)
        self.assertEqual(report['received_archives'][1]['actual_archive_bytes'], 7)
        self.assertEqual(report['received_archives'][1]['actual_archive_sha256'], hashlib.sha256(b'partial').hexdigest())
        self.assertNotIn('secret', self.args.report.read_text())
        self.assertFalse(self.args.artifact_set.exists())

    def test_network_failure_is_never_retried_or_logged_with_credentials(self):
        self.client.list = mock.Mock(side_effect=urllib.error.URLError('https://signed.invalid/?token=secret'))
        with self.assertRaises(urllib.error.URLError):
            self.collect()
        self.client.list.assert_called_once()
        self.assertEqual(self.report()['elapsed_seconds'], 0)
        self.assertEqual(self.report()['status'], 'FAIL')
        self.assertNotIn('secret', self.args.report.read_text())
        self.assertNotIn('signed.invalid', self.args.report.read_text())

    def test_missing_token_and_invalid_source_write_failure_report(self):
        with mock.patch.dict(cohort.os.environ, {}, clear=True):
            with self.assertRaisesRegex(cohort.CohortError, 'GITHUB_TOKEN'):
                cohort.collect(self.args, clock=self.clock)
        self.assertEqual(self.report()['status'], 'FAIL')
        self.args.expected_commit = 'unknown'
        with self.assertRaisesRegex(cohort.CohortError, 'Malformed source'):
            self.collect()
        self.assertEqual(self.client.list_calls, 0)

    def test_existing_or_symlinked_peer_output_is_never_reused(self):
        self.args.out.symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(cohort.CohortError, 'must be fresh'):
            self.collect()
        self.assertEqual(self.client.list_calls, 0)

    def test_source_run_attempt_expiration_duplicate_and_page_limits_fail_closed(self):
        mutations = [
            lambda rows: rows[0]['workflow_run'].update(id=999),
            lambda rows: rows[0]['workflow_run'].update(head_sha='9' * 40),
            lambda rows: rows[0].update(expired=True),
            lambda rows: rows[0].update(digest=''),
            lambda rows: rows[0].update(id=True),
            lambda rows: rows[0].update(size_in_bytes=cohort.MAX_ARCHIVE + 1),
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows[1].update(id=rows[0]['id']),
            lambda rows: rows[0].update(name='sdvk-cohort-probe-123-1-unknown'),
        ]
        for mutate in mutations:
            rows = copy.deepcopy(self.client.rows)
            mutate(rows)
            with self.subTest(rows=rows), self.assertRaises(cohort.CohortError):
                cohort.select_artifacts({'total_count': len(rows), 'artifacts': rows},
                                        cohort.expected_names('123', '1'), '123', SOURCE)
        old = copy.deepcopy(self.client.rows[0])
        old['name'] = cohort.expected_names('123', '2')['controls']
        self.assertEqual(cohort.select_artifacts({'total_count': 1, 'artifacts': [old]},
                         cohort.expected_names('123', '1'), '123', SOURCE), {})
        with self.assertRaisesRegex(cohort.CohortError, 'page bound'):
            cohort.select_artifacts({'total_count': 101, 'artifacts': self.client.rows},
                                    cohort.expected_names('123', '1'), '123', SOURCE)

    def test_probe_wrapper_and_plain_zip_are_both_lossless(self):
        for index, wrapper in enumerate(('', 'renderer-sdvk009-probe-controls/')):
            path = self.root / ('archive' + str(index) + '.zip')
            path.write_bytes(packet('controls', wrapper=wrapper))
            destination = self.root / ('restore' + str(index))
            cohort.restore_archive(path, destination, 'controls')
            self.assertEqual((destination / 'captures/independent.bin').read_bytes(), b'controls')

    def test_hostile_zip_members_cannot_escape_or_alias_evidence(self):
        link = zipfile.ZipInfo('link')
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        wrong_kind = zipfile.ZipInfo('directory-without-slash')
        wrong_kind.external_attr = (stat.S_IFDIR | 0o755) << 16
        bad = [('../escape', b'x'), ('/absolute', b'x'), ('dir\\escape', b'x'), ('x:drive', b'x'),
               ('probe.json', b'{}'), (link, b'../escape'), (wrong_kind, b''),
               ('captures', b'file-parent-conflict')]
        for index, entry in enumerate(bad):
            with self.subTest(member=str(entry[0])):
                archive = self.root / ('bad' + str(index) + '.zip')
                with mock.patch('warnings.warn'):
                    archive.write_bytes(packet('controls', extra=[entry]))
                with self.assertRaises(cohort.CohortError):
                    cohort.restore_archive(archive, self.root / ('bad-out' + str(index)), 'controls')
        self.assertFalse((self.root / 'escape').exists())

    def test_zip_budget_and_manifest_seal_are_enforced(self):
        archive = self.root / 'zip.zip'
        archive.write_bytes(packet('controls'))
        with mock.patch.object(cohort, 'MAX_EXPANDED', 1), self.assertRaisesRegex(cohort.CohortError, 'byte budget'):
            cohort.restore_archive(archive, self.root / 'oversized', 'controls')
        with zipfile.ZipFile(io.BytesIO(archive.read_bytes())) as source, zipfile.ZipFile(self.root / 'bad-seal.zip', 'w') as target:
            for info in source.infolist():
                target.writestr(info.filename, b'wrong\n' if info.filename.endswith('.sha256') else source.read(info))
        with self.assertRaisesRegex(cohort.CohortError, 'manifest SHA-256'):
            cohort.restore_archive(self.root / 'bad-seal.zip', self.root / 'bad-seal', 'controls')

    def test_json_duplicate_members_are_not_accepted(self):
        with self.assertRaisesRegex(cohort.CohortError, 'Duplicate JSON'):
            cohort.decode(b'{"status":"FAIL","status":"PASS"}')


class ArtifactHTTPTests(unittest.TestCase):
    def test_authorization_never_follows_storage_redirect(self):
        storage = 'https://example.blob.core.windows.net/container/file?signature=redacted'
        redirect = urllib.error.HTTPError('https://api.github.com', 302, '', {'Location': storage}, io.BytesIO())
        opener = mock.Mock()
        opener.open.side_effect = [redirect, io.BytesIO(b'zip-bytes')]
        client = cohort.ArtifactAPI('owner/repo', '123', 'private-token', opener=opener, clock=lambda: 0)
        with tempfile.TemporaryDirectory() as folder:
            client.download(7, Path(folder) / 'artifact.zip', 9, 600)
        first, second = [call.args[0] for call in opener.open.call_args_list]
        self.assertEqual(first.get_header('Authorization'), 'Bearer private-token')
        self.assertIsNone(second.get_header('Authorization'))
        self.assertEqual(second.full_url, storage)
        for call in opener.open.call_args_list:
            self.assertLessEqual(call.kwargs['timeout'], 30)

    def test_unapproved_redirect_and_http_error_are_not_retried(self):
        for url in ('http://example.blob.core.windows.net/x', 'https://evil.example/x',
                    'https://user:password@example.blob.core.windows.net/x',
                    'https://example.blob.core.windows.net:8443/x'):
            with self.subTest(url=url), self.assertRaises(cohort.CohortError):
                cohort.storage_url(url)
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://api.github.com', 403, '', {}, io.BytesIO())
        client = cohort.ArtifactAPI('owner/repo', '123', 'token', opener=opener, clock=lambda: 0)
        with self.assertRaisesRegex(cohort.CohortError, 'status 403'):
            client.list(600)
        opener.open.assert_called_once()

    def test_download_length_is_not_implicitly_trusted(self):
        for raw in (b'longer', b'x'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                opener = mock.Mock()
                opener.open.return_value = io.BytesIO(raw)
                client = cohort.ArtifactAPI('owner/repo', '123', 'token', opener=opener, clock=lambda: 0)
                with self.assertRaises(cohort.CohortError):
                    client.download(7, Path(folder) / 'artifact.zip', 3, 600)


if __name__ == '__main__':
    unittest.main()
