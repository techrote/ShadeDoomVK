"""SDVK-150 probe-owner repair contract using exact production Step/Full source.

The retained pre-fix builder/header must still reproduce the owner failures.
Current source must rebuild on semantic owner revision changes, including empty
and partial-pass transitions. No renderer or Vulkan device is created.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.pf_oracle.tests.legacy_msvc_fixture import (
    compile_legacy_fixture as compile_fixture, extracted_legacy_scope)
from tools.pf_oracle.tests.sdvk014_source import current

HERE=Path(__file__).resolve().parent
DATA=ROOT/'src/common/rendering/hwrenderer/data'
OLD=HERE/'fixtures/sdvk014_lightmap_pre_fix.json'

POSITIVE=(
    'same-owner-terminal',
    'count-change',
    'direct-empty-step',
    'fresh-owner-control',
    'same-count',
    'same-count-via-empty',
    'partial-owner',
    'full-same-count',
)
RETAINED_NEGATIVES={
    'same-count':'new-owner-not-rebuilt',
    'same-count-via-empty':'new-owner-not-rebuilt',
    'partial-owner':'partial-owner-mixed-pass',
    'full-same-count':'full-new-owner-not-rebuilt',
}


def build(directory: Path, original: bool=False) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    retained=json.loads(OLD.read_text())['functions']
    methods='\n'.join(retained[k]['content'] if original else current(k)
                      for k in ('probe_step','probe_full'))
    # Exact production int progress consumes bounded TArray fixture populations.
    (directory/'sdvk014_probe_methods.cpp').write_text(extracted_legacy_scope(methods, (4267,)))

    source=(HERE/'sdvk014_probe_owner_fixture.cpp').read_text()
    if original:
        (directory/'hw_lightprobe.h').write_text(retained['probe_header']['content'])
        source='#define SDVK150_RETAINED 1\n'+source
    fixture=directory/'probe_owner.cpp'
    fixture.write_text(source)
    return compile_fixture(
        fixture,output_dir=directory,
        includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


class ProbeOwnerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk150-probe-owner-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_current_entry_observes_empty_owner_and_semantic_revision(self):
        entry=(ROOT/'src/rendering/hwrenderer/hw_entrypoint.cpp').read_text()
        self.assertNotIn('if (gl_lightprobe && level.lightProbes.size() > 0)',entry)
        self.assertIn('if (gl_lightprobe)',entry)
        self.assertEqual(entry.count('ObserveLightProbeBuilder(lightProbeBuilder.Step('), 2)
        self.assertIn(
            'level.lightProbes, level.GetLightProbeSetRevision(), {}));',
            entry,
        )
        self.assertIn(
            'level.lightProbes, level.GetLightProbeSetRevision(), renderEnvMap));',
            entry,
        )

    def test_revision_producers_cover_teardown_and_runtime_add(self):
        setup=(ROOT/'src/p_setup.cpp').read_text()
        clear_marker='\tMarkLightProbeSetChanged();\n\tlightProbes.Clear();'
        self.assertEqual(setup.count(clear_marker),1)

        runtime=(ROOT/'src/rendering/hwrenderer/doom_lightprobes.cpp').read_text()
        push='\tlevel.lightProbes.Push(probe);'
        advance='\tlevel.MarkLightProbeSetChanged();'
        self.assertEqual(runtime.count(push),1)
        self.assertEqual(runtime.count(advance),1)
        self.assertLess(runtime.index(push),runtime.index(advance))

        level_header=(ROOT/'src/g_levellocals.h').read_text()
        self.assertIn('uint64_t LightProbeSetRevision = AllocateLightProbeSetRevision();',level_header)
        self.assertIn('uint64_t GetLightProbeSetRevision() const',level_header)
        self.assertIn('LightProbeSetRevision = AllocateLightProbeSetRevision();',level_header)

        owner_source=(ROOT/'src/g_level.cpp').read_text()
        self.assertIn('uint64_t AllocateLightProbeSetRevision()',owner_source)
        self.assertIn('static std::atomic<uint64_t> next{ 1 };',owner_source)
        self.assertIn('I_FatalError("Light probe set revision exhausted")',owner_source)

    def test_retained_header_is_exactly_pinned(self):
        retained=json.loads(OLD.read_text())['functions']['probe_header']
        raw=retained['content'].encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),retained['sha256'])
        git_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(git_blob,retained['git_blob'])

    def test_current_owner_boundaries(self):
        for case in POSITIVE:
            with self.subTest(case=case):
                p=subprocess.run([str(self.current),case],text=True,capture_output=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertIn('PASS '+case,p.stdout)

    def test_retained_same_count_and_partial_owner_failures(self):
        for case,reason in RETAINED_NEGATIVES.items():
            with self.subTest(case=case):
                p=subprocess.run([str(self.original),case],text=True,capture_output=True,timeout=10)
                self.assertEqual(p.returncode,11,p.stdout+p.stderr)
                self.assertIn('BLOCKED '+reason,p.stderr)

    def test_retained_independent_controls_still_pass(self):
        for case in ('same-owner-terminal','count-change','direct-empty-step','fresh-owner-control'):
            with self.subTest(case=case):
                p=subprocess.run([str(self.original),case],text=True,capture_output=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertIn('PASS '+case,p.stdout)


if __name__=='__main__':
    unittest.main()
