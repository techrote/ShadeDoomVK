"""CPU binding contracts: retained native negative evidence plus authored PK3s.

Constructed records below derive channels/dimensions/filter authoring from the
archive, not from expected recipe assertions. They are source-model tests and
do not substitute for fresh emitted native observations.
"""
import copy
import json
from pathlib import Path
import re
import unittest

from tools.renderer_oracle import prepare, run, sdvk008_fixtures as fixtures
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests.test_corpus import unpack_png


ROOT = Path(__file__).resolve().parents[3]
RETAINED = Path(__file__).parent / 'fixtures/sdvk008_alpha_off_material_38102402396.json'


def authored_records(scene):
    """Independent minimal FMaterial source layout model from authored GLDEFS."""
    _, members, _ = prepare.scene_assets(scene)
    definitions = {}
    text = members['GLDEFS'].decode()
    for match in re.finditer(r'material\s+(?:sprite|texture)\s+(\w+)\s*\{', text):
        start = match.end()
        depth, end = 1, start
        while depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        definitions[match[1]] = {m[1]: (m[2], m[3]) for m in re.finditer(
            r'(normal|specular|metallic|roughness|ao|height)\s+"([^"]+)"(?:\s*\{\s*filter\s+(linear|nearest|default)\s*\})?',
            text[start:end-1])}
    records = {}
    for name in scene['native']['state_assertions']['materials']:
        channels = definitions.get(name, {})
        prefix = ['albedo']
        if {'normal', 'specular'} <= channels.keys():
            prefix += ['normal', 'specular']
        elif {'normal', 'metallic', 'roughness', 'ao'} <= channels.keys():
            prefix += ['normal', 'metallic', 'roughness', 'ao']
        layers = []
        def append(channel):
            if channel == 'albedo':
                path = next(p for p in (f'sprites/{name}.png', f'textures/{name}.png', f'flats/{name}.png') if p in members)
                requested = -1
            else:
                texture, filtering = channels[channel]
                path = f'textures/{texture}.png'
                requested = 1 if filtering == 'linear' or (channel == 'height' and filtering in (None, 'default')) else 0 if filtering == 'nearest' else -1
            header, _ = unpack_png(members[path])
            layers.append({'binding': len(layers), 'semantic': {'specular':'legacy-specular', 'ao':'ambient-occlusion'}.get(channel, channel),
                'role':'authored-layer', 'requested_sampling': requested,
                'source': {'lump':100+len(layers), 'width':header['width'], 'height':header['height']},
                'sampler': {'min_filter':int(requested == 1), 'mag_filter':int(requested == 1), 'mipmap_mode':int(requested != -1)}})
        for channel in prefix:
            append(channel)
        for semantic in ('brightmap-emissive', 'detail', 'glow'):
            layers.append({'binding': len(layers), 'semantic':semantic, 'role':'fallback-placeholder',
                'source':{'lump':0, 'width':1, 'height':1}, 'requested_sampling':-1})
        if 'height' in channels:
            append('height')
        records[name] = {'name':name, 'layers':layers,
            'height_texture_index':len(layers)-1 if 'height' in channels else -1}
    return records


def assertions_pass(value, assertions):
    name = value['name']
    heights = assertions['material_height_layers']
    return (run._material_semantics_match(value, assertions['material_semantics'][name], allow_height=name in heights)
        and run._material_layer_sampling_match(value, assertions['material_layer_sampling'][name])
        and len(value['layers']) == assertions['material_layer_count'][name]
        and (run._material_height_layer_match(value, heights[name]) if name in heights else value['height_texture_index'] == -1))


class MaterialBindingContracts(unittest.TestCase):
    def setUp(self):
        self.catalog = prepare.load_catalog()
        self.scenes = {s['id']:s for s in self.catalog['scenes'] if s['native']['generator']=='sprite_relief'}
        self.retained = json.loads(RETAINED.read_text())

    def test_retained_failed_material_reproduces_old_error_and_matches_new_contract(self):
        value = self.retained['record']['data']
        self.assertEqual(self.retained['source']['native_observation_sha256'], '4457fef11ee2633424d98294ded1c78f46841202e65cb16216b640244132d6a2')
        self.assertEqual(self.retained['source']['renderer_commit'], '44f7b52280315889321788ab74f48c9f02bcfeab')
        self.assertFalse(run._material_semantics_match(value, ['albedo']))
        assertions = self.scenes['sdvk008-alpha-off']['native']['state_assertions']
        self.assertTrue(assertions_pass(value, assertions))
        # Exercise the real per-scene assertion path on this retained record.
        raw = {'mode':'state','observed_frames':1,'records':[self.retained['record'],
            {'kind':'context','frame':1,'data':{'context':value['context']}}]}
        old = copy.deepcopy(self.scenes['sdvk008-alpha-off'])
        old['native']['state_assertions'].pop('material_height_layers')
        with self.assertRaisesRegex(EvidenceError,'Required material semantic bindings differ: SDVEA0'):
            run._scene_assertions(raw, old)
        run._scene_assertions(raw, self.scenes['sdvk008-alpha-off'])

    def test_all_twenty_five_recipes_match_authored_archive_channels(self):
        self.assertEqual(len(self.scenes),25)
        for scene in self.scenes.values():
            for value in authored_records(scene).values():
                self.assertTrue(assertions_pass(value,scene['native']['state_assertions']), (scene['id'],value['name']))

    def test_retained_height_binding_extent_role_and_actual_sampler_negatives(self):
        original = self.retained['record']['data']
        assertions = self.scenes['sdvk008-alpha-off']['native']['state_assertions']
        for label, mutate in (
            ('missing', lambda v:v['layers'].pop()),
            ('wrong-index', lambda v:v.update(height_texture_index=3)),
            ('wrong-binding', lambda v:v['layers'][-1].update(binding=3)),
            ('wrong-request', lambda v:v['layers'][-1].update(requested_sampling=-1)),
            ('nearest-height', lambda v:v['layers'][-1]['sampler'].update(min_filter=0)),
            ('nearest-mip', lambda v:v['layers'][-1]['sampler'].update(mipmap_mode=0)),
            ('linear-albedo', lambda v:v['layers'][0]['sampler'].update(mag_filter=1)),
            ('wrong-extent', lambda v:v['layers'][-1]['source'].update(width=64)),
            ('noninteger-extent', lambda v:v['layers'][-1]['source'].update(width=128.0)),
            ('invalid-source', lambda v:v['layers'][-1].update(source=None)),
            ('placeholder-source', lambda v:v['layers'][-1]['source'].update(lump=0)),
            ('placeholder-role', lambda v:v['layers'][-1].update(role='fallback-placeholder')),
            ('oversized-fallback', lambda v:v['layers'][1]['source'].update(width=2)),
            ('missing-fallback', lambda v:v['layers'].pop(2)),
        ):
            bad = copy.deepcopy(original)
            mutate(bad)
            with self.subTest(label=label):
                self.assertFalse(assertions_pass(bad,assertions))

    def test_pbr_channels_are_required_and_each_sampler_is_checked(self):
        scene = self.scenes['sdvk008-pm']
        value = authored_records(scene)['SDVEA0']
        for binding in (1,2,3,4,8):
            for label in ('missing','wrong-semantic','nearest'):
                bad = copy.deepcopy(value)
                if label == 'missing': bad['layers'].pop(binding)
                elif label == 'wrong-semantic': bad['layers'][binding]['semantic']='custom'
                else: bad['layers'][binding]['sampler']['mag_filter']=0
                with self.subTest(binding=binding,label=label):
                    self.assertFalse(assertions_pass(bad,scene['native']['state_assertions']))

    def test_heightless_and_mirror_unmapped_controls_reject_height(self):
        for scene_id,name in (('sdvk008-heightless-on','SDVEA0'),('sdvk008-mirror-on','SDVPA0'),('sdvk008-mirror-on','SDVLA0')):
            scene = self.scenes[scene_id]
            value = authored_records(scene)[name]
            value['layers'].append(copy.deepcopy(self.retained['record']['data']['layers'][-1]))
            value['height_texture_index']=len(value['layers'])-1
            self.assertFalse(assertions_pass(value,scene['native']['state_assertions']))

    def test_recipe_cannot_drop_or_weaken_declared_material_checks(self):
        for key in ('material_semantics','material_height_layers','material_layer_sampling','material_layer_count'):
            altered = copy.deepcopy(self.catalog)
            scene = next(s for s in altered['scenes'] if s['id']=='sdvk008-alpha-off')
            scene['native']['state_assertions'].pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'authored binding contract'):
                prepare.validate_catalog(altered)

    def test_generic_new_assertions_reject_invalid_counts_and_extents(self):
        # Use an inherited scene so the generic schema is exercised separately
        # from the stricter SDVK-008 authored-contract check.
        for count in (0,257,True):
            altered=copy.deepcopy(self.catalog)
            scene=next(s for s in altered['scenes'] if s['id']=='sprite-mirror')
            scene['native']['state_assertions']['material_layer_count']={'SDVRA1':count}
            with self.assertRaisesRegex(ValueError,'positive layer counts'):
                prepare.validate_catalog(altered)
        for extent in ([0,128],[128],[-1,128],[True,128]):
            altered=copy.deepcopy(self.catalog)
            scene=next(s for s in altered['scenes'] if s['id']=='sprite-mirror')
            scene['native']['state_assertions']['material_layer_sampling']['SDVRA1'][0]['source_extent']=extent
            with self.assertRaisesRegex(ValueError,'source extent'):
                prepare.validate_catalog(altered)


if __name__ == '__main__':
    unittest.main()
