"""Synthetic losslessness, corruption, incompleteness and traversal controls."""
import json
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

import renderer_evidence as evidence


class EvidenceTest(unittest.TestCase):
    source = '1' * 40
    runtime = '2' * 64
    plan = '3' * 64

    def test_compressor_memory_and_cpu_budget_cannot_overcommit_small_hosts(self):
        for memory, cpu in ((7 * 1024**3, 4), (16 * 1024**3, 2), (None, 8)):
            command = evidence.compression_policy({'effective_memory_bytes': memory, 'effective_processors': cpu})
            self.assertIn('-T1', command)
            self.assertIn('--memlimit-compress=1GiB', command)
            self.assertIn('--no-adjust', command)
        command = evidence.compression_policy({'effective_memory_bytes': 16 * 1024**3, 'effective_processors': 4})
        self.assertIn('-T3', command)
        self.assertIn('--block-size=512MiB', command)
        self.assertIn('--memlimit-compress=7GiB', command)
        self.assertIn('--no-adjust', command)
        # Exercise xz's own option/memory admission without another benchmark.
        result = subprocess.run(command, input=b'bounded option check', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.parts = self.root / 'parts'
        self.parts.mkdir()
        self.build.mkdir()

    def populate(self, suite, complete=False, status='success'):
        roots = evidence.ROOTS[suite] if complete else evidence.ROOTS[suite][:1]
        for name in roots:
            root = self.build / name / 'deep'
            root.mkdir(parents=True)
            (root / 'capture.bin').write_bytes(b'hello' * 10000)
        if complete:
            for name, gate_status in evidence.GATES[suite].items():
                gate = self.build / name
                gate.parent.mkdir(parents=True, exist_ok=True)
                gate.write_text(json.dumps({'status': gate_status}))
        evidence.pack(self.build, suite, expected_commit=self.source,
                      runtime_sha256=self.runtime, plan_sha256=self.plan, job_status=status)
        for path in self.build.glob(f'renderer-{suite}.*'):
            shutil.copy2(path, self.parts / path.name)
        for name in roots:
            shutil.rmtree(self.build / name)

    def merge(self, output, *, complete=True, suites=None, **kwargs):
        return evidence.merge(self.parts, output, complete=complete, suites=suites,
                              expected_commit=kwargs.get('source', self.source),
                              runtime_sha256=kwargs.get('runtime', self.runtime),
                              plan_sha256=kwargs.get('plan', self.plan))

    def populate_all(self):
        for suite in evidence.ROOTS:
            self.populate(suite, complete=True)

    def test_roundtrip_five_suites_and_legacy_consumer(self):
        self.populate_all()
        merged = self.root / 'merged'
        self.merge(merged)
        archive = self.root / 'renderer-software-vulkan.tar.xz'
        report = evidence.finalize(merged, archive)
        self.assertGreater(report['files'], 0)
        self.assertTrue(archive.with_suffix('.xz.sha256').is_file())
        listing = subprocess.check_output(['tar', '-tJf', str(archive)], text=True)
        self.assertIn('renderer-native/deep/capture.bin', listing)
        self.assertIn('renderer-sdvk014-controlled/deep/capture.bin', listing)

    def test_authenticated_relocation_keeps_every_original_byte(self):
        self.populate_all()
        merged = self.root / 'merged'
        self.merge(merged)
        source = 'renderer-sdvk009-worker-witness-1/deep/capture.bin'
        destination = 'renderer-sdvk009-publication/captures/shadow-witness-1/capture.bin'
        target = merged / destination
        target.parent.mkdir(parents=True)
        original = merged / source
        record = {'destination': destination, 'sha256': evidence.sha256(original),
                  'bytes': original.stat().st_size}
        original.rename(target)
        relocation = merged / 'renderer-sdvk009-publication/relocation.json'
        evidence.atomic_json(relocation, {'schema': 'sdvk009-publication-relocation/v1',
                                         'files': {source: record}})
        evidence.finalize(merged, self.root / 'relocated.tar.xz')
        manifest = evidence.read_json(self.root / 'renderer-evidence-manifest.json')
        self.assertIn(destination, manifest['files'])
        self.assertNotIn(source, manifest['files'])

    def test_lost_or_modified_original_cannot_be_sealed(self):
        self.populate_all()
        merged = self.root / 'merged'
        self.merge(merged)
        (merged / 'renderer-native/deep/capture.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'lost or altered'):
            evidence.finalize(merged, self.root / 'bad.tar.xz')

    def test_strict_merge_rejects_mismatched_source_runtime_plan(self):
        self.populate_all()
        for key, value in (('source', '4' * 40), ('runtime', '5' * 64), ('plan', '6' * 64)):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Mismatched worker'):
                self.merge(self.root / key, **{key: value})

    def test_cancelled_worker_retains_partial_evidence_but_cannot_pass(self):
        self.populate('corpus', complete=True, status='cancelled')
        self.merge(self.root / 'partial', complete=False)
        with self.assertRaisesRegex(ValueError, 'Unsuccessful worker'):
            self.merge(self.root / 'strict')
        evidence.finalize(self.root / 'partial', self.root / 'failed.tar.xz')

    def test_missing_worker_or_reordered_set_is_rejected(self):
        self.populate('corpus', complete=True)
        with self.assertRaisesRegex(ValueError, 'missing suite evidence'):
            self.merge(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'Unknown or reordered'):
            self.merge(self.root / 'reordered', suites=tuple(reversed(evidence.ROOTS)))

    def test_probe_requires_exact_three_worker_set(self):
        for suite in evidence.PROBE_SUITES:
            self.populate(suite, complete=True)
        self.merge(self.root / 'probe', suites=evidence.PROBE_SUITES)
        self.populate('corpus', complete=True)
        with self.assertRaisesRegex(ValueError, 'Unexpected or duplicated'):
            self.merge(self.root / 'extra', suites=evidence.PROBE_SUITES)

    def test_successful_worker_without_artifact_manifest_rejected(self):
        self.populate_all()
        (self.parts / 'renderer-witness-2.manifest.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing suite artifact or manifest'):
            self.merge(self.root / 'missing')

    def test_success_metadata_cannot_replace_missing_native_qualification(self):
        self.populate('corpus', complete=True)
        manifest_path = self.parts / 'renderer-corpus.manifest.json'
        manifest = evidence.read_json(manifest_path)
        # Forge an internally hash-consistent export containing roots but no
        # native result. Gate validation must reject it despite success metadata.
        del manifest['files']['renderer-native/native-ci.json']
        evidence.atomic_json(manifest_path, manifest)
        archive = self.parts / 'renderer-corpus.tar'
        with tarfile.open(self.build / 'renderer-corpus.tar', 'r:') as src, tarfile.open(archive, 'w:') as dst:
            for member in src:
                if member.name != 'renderer-native/native-ci.json':
                    dst.addfile(member, src.extractfile(member) if member.isfile() else None)
        (self.parts / 'renderer-corpus.tar.sha256').write_text(evidence.sha256(archive) + '  ' + archive.name + '\n')
        with self.assertRaisesRegex(ValueError, 'missing qualification receipt'):
            self.merge(self.root / 'no-native-result')

    def test_artifact_namespaces_prevent_duplicate_leaf_overwrite(self):
        self.populate_all()
        for suite in evidence.ROOTS:
            folder = self.parts / ('renderer-software-vulkan-' + suite)
            folder.mkdir()
            for path in list(self.parts.glob('renderer-' + suite + '.*')):
                path.rename(folder / path.name)
        self.merge(self.root / 'nested')
        duplicate = self.parts / 'renderer-software-vulkan-witness-1-copy'
        duplicate.mkdir()
        shutil.copy2(self.parts / 'renderer-software-vulkan-witness-1/renderer-witness-1.tar', duplicate)
        with self.assertRaisesRegex(ValueError, 'Unexpected or duplicated'):
            self.merge(self.root / 'duplicate')

    def test_cross_wired_nested_artifact_rejected_before_extraction(self):
        self.populate('corpus', complete=True)
        folder = self.parts / 'renderer-software-vulkan-publication'
        folder.mkdir()
        for path in list(self.parts.glob('renderer-corpus.*')):
            path.rename(folder / path.name)
        with self.assertRaisesRegex(ValueError, 'Cross-wired artifact namespace'):
            self.merge(self.root / 'cross-wired', complete=False)

    def test_cross_wired_manifest_and_duplicate_json_rejected(self):
        self.populate('corpus')
        path = self.parts / 'renderer-corpus.manifest.json'
        data = evidence.read_json(path)
        data['identity']['worker'] = 'publication'
        evidence.atomic_json(path, data)
        with self.assertRaisesRegex(ValueError, 'Cross-wired'):
            evidence.verify_suite(self.parts, 'corpus')
        path.write_text('{"schema":"first","schema":"second"}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            evidence.verify_suite(self.parts, 'corpus')

    def test_rehashed_ambiguous_native_status_is_rejected(self):
        self.populate('corpus', complete=True)
        target = 'renderer-native/native-ci.json'
        raw = b'{"status":"FAIL","status":"PASS"}'
        archive = self.parts / 'renderer-corpus.tar'
        with tarfile.open(self.build / archive.name, 'r:') as src, tarfile.open(archive, 'w:') as dst:
            for member in src:
                if member.name == target:
                    member.size = len(raw)
                    dst.addfile(member, io.BytesIO(raw))
                else:
                    dst.addfile(member, src.extractfile(member) if member.isfile() else None)
        path = self.parts / 'renderer-corpus.manifest.json'
        data = evidence.read_json(path)
        data['files'][target] = {'size': len(raw), 'sha256': evidence.sha256(io.BytesIO(raw))}
        evidence.atomic_json(path, data)
        (self.parts / 'renderer-corpus.tar.sha256').write_text(evidence.sha256(archive) + '  ' + archive.name + '\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON member'):
            self.merge(self.root / 'ambiguous')

    def test_rehashed_trailing_tar_payload_is_rejected(self):
        self.populate('corpus')
        archive = self.parts / 'renderer-corpus.tar'
        with archive.open('ab') as stream:
            stream.write(b'undeclared trailing evidence')
        (self.parts / 'renderer-corpus.tar.sha256').write_text(evidence.sha256(archive) + '  ' + archive.name + '\n')
        with self.assertRaisesRegex(ValueError, 'Nonzero bytes after suite tar'):
            evidence.verify_suite(self.parts, 'corpus')

    def test_rejects_corrupt_transport_or_manifest(self):
        self.populate('corpus')
        archive = self.parts / 'renderer-corpus.tar'
        with archive.open('ab') as stream:
            stream.write(b'x')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            evidence.verify_suite(self.parts, 'corpus')
        shutil.copy2(self.build / 'renderer-corpus.tar', archive)
        manifest = self.parts / 'renderer-corpus.manifest.json'
        obj = json.loads(manifest.read_text())
        obj['files'].pop(next(iter(obj['files'])))
        manifest.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, 'tar member'):
            evidence.verify_suite(self.parts, 'corpus')

    def test_partial_retention_and_complete_fail_closed(self):
        self.populate('corpus')
        self.merge(self.root / 'partial', complete=False)
        with self.assertRaisesRegex(ValueError, 'missing qualification receipt|missing a required evidence root'):
            self.merge(self.root / 'strict', complete=True)

    def test_final_xz_corruption_is_rejected_with_all_hash_checks_intact(self):
        self.populate_all()
        merged = self.root / 'merged'
        self.merge(merged)
        archive = self.root / 'complete.tar.xz'
        evidence.finalize(merged, archive)
        raw = archive.read_bytes()
        archive.write_bytes(raw[:-8])
        with self.assertRaisesRegex(ValueError, 'XZ integrity'):
            evidence.verify_final(archive, self.root / 'renderer-evidence-manifest.json')

    def test_rejects_path_escape_or_symlink(self):
        self.populate('corpus')
        manifest = self.parts / 'renderer-corpus.manifest.json'
        obj = json.loads(manifest.read_text())
        obj['files']['renderer-native/../escape'] = {'sha256':'0'*64,'size':1}
        manifest.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            evidence.verify_suite(self.parts, 'corpus')
        (self.build / 'renderer-native').mkdir()
        (self.build / 'renderer-native' / 'link').symlink_to(self.parts / 'renderer-corpus.tar')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            evidence.pack(self.build, 'corpus')


if __name__ == '__main__':
    unittest.main()
