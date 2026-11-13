"""Synthetic losslessness, corruption, incompleteness and traversal controls."""
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

import renderer_evidence as evidence


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.parts = self.root / 'parts'
        self.parts.mkdir()
        self.build.mkdir()

    def populate(self, suite, complete=False):
        roots = evidence.ROOTS[suite] if complete else evidence.ROOTS[suite][:1]
        for name in roots:
            root = self.build / name / 'deep'
            root.mkdir(parents=True)
            (root / 'capture.bin').write_bytes(b'hello' * 10000)
        evidence.pack(self.build, suite)
        for path in self.build.glob(f'renderer-{suite}.*'):
            shutil.copy2(path, self.parts / path.name)
        for name in roots:
            shutil.rmtree(self.build / name)

    def test_roundtrip_both_suites_and_final(self):
        self.populate('corpus', complete=True)
        self.populate('publication', complete=True)
        merged = self.root / 'merged'
        evidence.merge(self.parts, merged, complete=True)
        names = (self.root / 'renderer-evidence-directories.txt').read_text().splitlines()
        archive = self.root / 'renderer-software-vulkan.tar.xz'
        with tarfile.open(archive, 'w:xz') as dst:
            for name in names:
                dst.add(merged / name, arcname=name)
        evidence.verify_final(archive, self.root / 'renderer-evidence-manifest.json')
        self.assertTrue(archive.with_suffix('.xz.sha256').is_file())

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
        evidence.merge(self.parts, self.root / 'partial', complete=False)
        with self.assertRaisesRegex(ValueError, 'missing a required evidence root'):
            evidence.merge(self.parts, self.root / 'strict', complete=True)

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
