"""SDVK-014 actual CPU atlas boundary/rebuild tests; never creates Vulkan."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.tests.legacy_msvc_fixture import compile_legacy_fixture as compile_fixture
from tools.pf_oracle.tests.sdvk156_source import RETAINED, retain_atlas_headers

HERE = Path(__file__).resolve().parent
DATA = ROOT / 'src/common/rendering/hwrenderer/data'
OLD = HERE / 'fixtures/sdvk014_rectpacker_pre_fix.cpp'
CASES = ('full-height', 'padded-full-page', 'clear-rebuild', 'invalid-atomic',
         'invalid-boundaries', 'oracle-negatives', 'bounded-stress')


def build(directory: Path, original: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    text = (OLD if original else DATA/'hw_rectpacker.cpp').read_text()
    (directory/'sdvk014_rectpacker_under_test.cpp').write_text(text)
    if original:
        retain_atlas_headers(directory)
    fixture = (RETAINED if original else HERE) / 'sdvk014_atlas_fixture.cpp'
    if original:
        local_fixture = directory / fixture.name
        # Keep the authenticated historical fixture unchanged in Git. Its one
        # unsigned high-water assignment measures only this bounded fixture
        # (96 allocations per cycle). Suppress that exact line only.
        text = fixture.read_text()
        line = '            if(cycle==0) { warmItems=p.Items.size(); warmPages=p.GetNumPages(); }'
        if text.count(line) != 1:
            raise AssertionError('Historical high-water assignment changed')
        text = text.replace(line, '#ifdef _MSC_VER\n#pragma warning(push)\n'
                            '#pragma warning(disable: 4267)\n#endif\n' + line +
                            '\n#ifdef _MSC_VER\n#pragma warning(pop)\n#endif')
        local_fixture.write_text(text, encoding='utf-8', newline='\n')
        fixture = local_fixture
    return compile_fixture(fixture, output_dir=directory,
        includes=[directory, DATA, ROOT/'src/common/utility'])


class AtlasLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sdvk014-atlas-')
        cls.directory = Path(cls.temp.name)
        cls.current = build(cls.directory/'current')
        cls.original = build(cls.directory/'original', True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_current_boundaries_stress_and_independent_negatives(self):
        for case in CASES:
            with self.subTest(case=case):
                p = subprocess.run([str(self.current), case], text=True,
                                   capture_output=True, timeout=20)
                self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                self.assertIn('PASS '+case, p.stdout)

    def test_exact_retained_defects_fail_for_the_intended_reason(self):
        pins = json.loads(OLD.with_suffix('.json').read_text())
        self.assertEqual(hashlib.sha256(OLD.read_bytes()).hexdigest(), pins['sha256'])
        raw = OLD.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), pins['git_blob'])
        cases = {
            'full-height': (10, 'Tile too large'),
            'padded-full-page': (10, 'Tile too large'),
            'clear-rebuild': (10, 'RectPacker items are corrupted'),
            'invalid-atomic': (11, 'invalid-allocation-mutated-owner'),
        }
        for case, (code, reason) in cases.items():
            with self.subTest(case=case):
                p = subprocess.run([str(self.original), case], text=True,
                                   capture_output=True, timeout=10)
                self.assertEqual(p.returncode, code, p.stdout+p.stderr)
                self.assertIn(reason, p.stderr)


if __name__ == '__main__':
    unittest.main()
