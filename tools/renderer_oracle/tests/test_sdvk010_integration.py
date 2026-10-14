"""CPU-only integration contracts; no renderer, device, or external service."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.renderer_oracle import prepare, run, sdvk010_acceptance as combined
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests import test_actor_probe_portal_transition as portal_fixture
from tools.renderer_oracle.tests import test_sdvk010_sun_occlusion as sun_fixture


class CombinedDriverTests(unittest.TestCase):
    def exercise(self, directory, fail_at=None, guard_ok=True):
        args = argparse.Namespace(
            exe=Path('vkdoom'), iwad=Path('freedoom2.wad'), iwad_license=Path('COPYING'),
            out=Path(directory)/'qualification', expected_commit='a'*40)
        scenes = [{'id':name} for name in combined.SCENES]
        calls = []
        def capture(arg):
            calls.append(arg)
            if len(calls) == fail_at:
                raise EvidenceError('injected capture failure')
            return {'status':'COLLECTED'}
        with patch.object(combined.sdvk010_sun_native, 'software_host_guard',
                          return_value={'status':'PASS'}, side_effect=None if guard_ok else EvidenceError('physical surface rejected')) as guard, \
             patch.object(combined.native_ci, 'preflight', return_value={'status':'PASS'}), \
             patch.object(combined.prepare, 'prepare', return_value={'scenes':scenes}), \
             patch.object(combined, 'pin', return_value={'sha256':combined.sdvk009_publication.IWAD_SHA256}), \
             patch.object(combined.run, 'capture', side_effect=capture), \
             patch.object(combined, 'captured_negatives', return_value={'status':'PASS'}) as negatives, \
             patch.object(combined.run, 'compare_runs', return_value={'status':'PASS'}) as comparison:
            result = combined.qualify(args)
            with self.assertRaises(FileExistsError):
                combined.qualify(args)
            return result, calls, negatives.call_count, comparison.call_count

    def test_complete_four_process_plan_with_exact_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            result, calls, negatives, comparisons = self.exercise(directory)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([a.scene for a in calls], ['sun-actor-occlusion']*2+['portal-probes']*2)
        self.assertEqual((negatives, comparisons), (4, 2))
        self.assertEqual(result['automatic_retries'], 0)
        for args in calls:
            self.assertEqual((args.warmup, args.frames, args.timeout), (240, 1, 600))
            self.assertEqual(args.image_policy, 'exact')
            self.assertTrue(args.require_clean)
            self.assertEqual(args.expected_commit, 'a'*40)
            self.assertFalse(args.gpu or args.collision_snapshot or args.publication_witness)
        self.assertFalse(result['physical_gpu_qualified'] or result['performance_accepted'])

    def test_failure_suppresses_dependent_processes_and_comparison(self):
        for fail_at in (1, 2, 3, 4):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                result, calls, negatives, comparisons = self.exercise(directory, fail_at)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(len(calls), fail_at)
            self.assertEqual(negatives, fail_at-1)
            self.assertEqual(comparisons, 1 if fail_at > 2 else 0)

    def test_guard_failure_launches_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            result, calls, negatives, comparisons = self.exercise(directory, guard_ok=False)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual((calls, negatives, comparisons), ([], 0, 0))

    def test_captured_negatives_use_both_real_record_shapes(self):
        catalog = prepare.load_catalog()
        for name, rows in ((combined.SCENES[0], sun_fixture.emitted_rows()),
                           (combined.SCENES[1], portal_fixture.good_rows())):
            for record in rows:
                record['frame'] = 1
            with self.subTest(scene=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'native.renderer.json').write_text(json.dumps({
                    'mode':'state','requested_frames':1,'records':rows}))
                scene = next(s for s in catalog['scenes'] if s['id'] == name)
                result = combined.captured_negatives(root, scene)
                self.assertEqual(len(result['controls']), 4)
                self.assertTrue(all(c['status'] == 'REJECTED' for c in result['controls']))
                self.assertFalse(result['native_execution'])


class SharedIntegrationTests(unittest.TestCase):
    def test_both_generators_and_assertions_exist_and_maps_are_bound(self):
        catalog = prepare.load_catalog()
        prepare.validate_catalog(catalog)
        scenes = {s['id']:s for s in catalog['scenes']}
        for name, generator, assertion in (
            ('sun-actor-occlusion','sun_actor_occlusion','actor_sun_occlusion'),
            ('portal-probes','portal_probes','actor_probe_portal')):
            native = scenes[name]['native']
            self.assertEqual(native['generator'], generator)
            self.assertIn(assertion, native['state_assertions'])
            self.assertEqual(native['map_guard']['equals'], native['map'])
            bad = copy.deepcopy(catalog)
            next(s for s in bad['scenes'] if s['id'] == name)['native']['map_guard']['equals'] = 'SDVSUN'
            with self.assertRaisesRegex(ValueError, 'map guard'):
                prepare.validate_catalog(bad)

    def test_normalization_never_changes_other_scenes_or_actor_resources(self):
        base = [
            {'kind':'material','data':{'name':name,'resource':{
                'available':True,'index':idx,'generation':3,'epoch':2,'span':4}}}
            for idx, name in enumerate(('SDVSKY','SDVFL','SDVOA0','SDVTA0'))]
        base += [{'kind':'resource','data':{'texture_epoch':3,'probe_epoch':2}},
                 {'kind':'probe','data':{'resource':{
                     'available':True,'index':40,'generation':1,'epoch':2,'span':2}}}]
        for scene, idx in (('sun-actor-occlusion',0),('portal-probes',1)):
            for changed_index in (0,1,2,3,5):
                other=copy.deepcopy(base)
                other[changed_index]['data']['resource']['generation'] += 1
                equal = run._sdvk010_repeatability_projection(base,scene) == run._sdvk010_repeatability_projection(other,scene)
                self.assertEqual(equal, changed_index == idx)
        self.assertEqual(run._sdvk010_repeatability_projection(base,'sun-probes'),base)
        self.assertEqual(run._sdvk010_repeatability_projection(base,'shadow-boundary'),base)
        self.assertEqual(base[0]['data']['resource']['generation'],3)

    def test_background_transition_pattern_survives_both_policies(self):
        for scene, material in (('sun-actor-occlusion','SDVSKY'),('portal-probes','SDVFL')):
            row = {'kind':'material','data':{'name':material,'resource':{
                'available':True,'index':1,'generation':3,'epoch':2,'span':4}}}
            rows = [copy.deepcopy(row),copy.deepcopy(row)]
            changed = copy.deepcopy(rows)
            changed[1]['data']['resource']['generation']=4
            self.assertNotEqual(run._sdvk010_repeatability_projection(rows,scene),
                                run._sdvk010_repeatability_projection(changed,scene))


if __name__ == '__main__':
    unittest.main()
