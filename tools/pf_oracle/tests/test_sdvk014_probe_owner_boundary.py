"""Preserve an upstream probe-owner blocker, not a probe robustness acceptance.

The retained-source negatives must fail. Current Step's covered positive cases
must pass. Run the current same-count modes separately to diagnose the unresolved
production gap; no test labels their failure as software campaign acceptance.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import current
HERE=Path(__file__).resolve().parent
DATA=ROOT/'src/common/rendering/hwrenderer/data'
GUARD='if (gl_lightprobe && level.lightProbes.size() > 0)'
POSITIVE=('same-owner-terminal','count-change','direct-empty-step','fresh-owner-control')


def build(directory: Path,original: bool=False) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    old=json.loads((HERE/'fixtures/sdvk014_lightmap_pre_fix.json').read_text())['functions']
    methods='\n'.join(old[k]['content'] if original else current(k) for k in ('probe_step','probe_full'))
    entry=(ROOT/'src/rendering/hwrenderer/hw_entrypoint.cpp').read_text()
    if entry.count(GUARD)!=1:
        raise AssertionError('Probe entry guard changed: reconcile the retained/current owner fixture')
    source=(HERE/'sdvk014_probe_owner_fixture.cpp').read_text().replace('@ENTRY_GUARD@',GUARD)
    (directory/'sdvk014_probe_methods.cpp').write_text(methods)
    fixture=directory/'probe_owner.cpp';fixture.write_text(source)
    return compile_fixture(fixture,output_dir=directory,
        includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


class ProbeOwnerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk014-probe-owner-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_existing_positive_boundaries(self):
        for case in POSITIVE:
            with self.subTest(case=case):
                p=subprocess.run([str(self.current),case],text=True,capture_output=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_retained_same_count_owner_failure(self):
        for case in ('same-count','same-count-via-empty'):
            with self.subTest(case=case):
                p=subprocess.run([str(self.original),case],text=True,capture_output=True,timeout=10)
                self.assertEqual(p.returncode,11,p.stdout+p.stderr)
                self.assertIn('BLOCKED new-owner-not-rebuilt',p.stderr)
                self.assertIn('new_owner_captures=0 reset_delta=0 pass_delta=0',p.stdout)


if __name__=='__main__':
    unittest.main()
