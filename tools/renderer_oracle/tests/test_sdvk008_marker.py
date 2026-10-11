"""Independent CPU projection/sampling controls; no native renderer launch."""
import copy
import math
import unittest

from tools.renderer_oracle import prepare, sdvk008_marker as marker, sdvk008_fixtures as fixtures


def state(enabled):
    context = dict(type="main", mirrored=False, position=[-160, -80, 96], angles=[243, 0, 0])
    surface = dict(presentation=3, uv=[1, 0, 0, 1], render_angles=[180, 0, 0],
        basis_valid=True, frame_mirrored=False, uv_mirror_x=False, uv_mirror_y=False,
        portal_mirrored=False, expected_tangent=[0, 0, -1], expected_normal=[-1, 0, 0],
        expected_handedness=1)
    common = dict(material="SDVEA0", shader=0, height_texture_index=4, context=context, surface=surface)
    return {"records": [dict(kind="frame", data=dict(width=640, height=480,
        camera=dict(position=[-160, -80, 96], fov=90))),
        dict(kind="sprite-basis", data=dict(**common, tangent=[0, 0, -1], normal=[-1, 0, 0],
            handedness=1, explicit=True)),
        dict(kind="sprite-relief", data=dict(**common, eligible_draw=enabled,
            depth=.012 if enabled else 0, quality=2, uv_bounds=[1, 0, 0, 1] if enabled else [0, 0, 0, 0]))]}


def sampled_plane(depth, *, x_sign=1, y_sign=1):
    """Invert perspective per pixel, then sample via the shader's ray equation.

    This avoids both the forward homography and interval/raster helpers under
    test. The source-flat plateau is extended only for this CPU analytic model.
    """
    raw = bytearray(640*480*3)
    cosine, sine = math.cos(math.radians(27)), math.sin(math.radians(27))
    for x in range(640):
        right = (x+.5-320)/320
        y = 160*(sine-right*cosine)/(cosine+right*sine)-80
        distance = 160*cosine+(y+80)*sine
        u = 64-y
        for row in range(480):
            z = 96+(240-row-.5)*distance/384
            v = 128-z
            sampled_u = u-x_sign*depth*.012*128*(80+y)/160
            sampled_v = v-y_sign*depth*.012*128*(z-96)/160
            if 0 <= u < 128 and 0 <= v < 128 and (
                26 <= sampled_u < 33 or 83 <= sampled_v < 88):
                offset = 3*(row*640+x)
                raw[offset:offset+3] = bytes((241, 55, 89))
    return bytes(raw)


class SourceProjectedMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.natives = {s['id']: s['native'] for s in prepare.load_catalog()['scenes']}
        cls.off = sampled_plane(0)
        cls.on = sampled_plane(47/255)

    def check(self, off=None, on=None, **overrides):
        args = dict(off_state=state(False), on_state=state(True),
            off_native=self.natives['sdvk008-s0'], on_native=self.natives['sdvk008-sm'])
        args.update(overrides)
        return marker.source_projected_marker_direction(self.off if off is None else off,
            self.on if on is None else on, 640, 480, **args)

    def test_analytic_source_ray_sampling_matches_forward_edge_predictions(self):
        witness = self.check()
        self.assertEqual(witness['status'], 'PASS', witness)
        self.assertGreaterEqual(witness['delta_x_px'], .05)
        self.assertLessEqual(witness['delta_y_px'], -.05)
        self.assertEqual(len(witness['sections']), 22)
        self.assertFalse(witness['pixel_correspondence_proven'])
        self.assertFalse(witness['general_uv_correctness_qualified'])

    def test_source_plateau_contains_both_marker_supports_and_fixed_domains(self):
        height = fixtures.pixels('height')
        for x0, x1, y0, y1 in ((25, 35, 38, 63), (38, 53, 81, 90)):
            for y in range(y0, y1):
                for x in range(x0, x1):
                    self.assertEqual(height[4*(y*128+x)], 208)
        x, y = marker.project(26, 50)
        self.assertAlmostEqual(x, 266.9739927, places=6)
        self.assertAlmostEqual(y, 275.2415859, places=6)
        shifted = marker.project(26, 50, relieved=True)
        self.assertGreater(shifted[0]-x, .05)
        self.assertLess(shifted[1]-y, 0)

    def test_wrong_and_stationary_axes_reject_without_threshold_adaptation(self):
        self.assertEqual(self.check(on=self.off)['status'], 'FAIL')
        for signs in ((-1, 1), (1, -1), (-1, -1)):
            bad = sampled_plane(47/255, x_sign=signs[0], y_sign=signs[1])
            self.assertEqual(self.check(on=bad)['status'], 'FAIL')

    def test_missing_deletion_and_ambiguous_intervals_cannot_pass(self):
        self.assertEqual(self.check(on=bytes(len(self.on)))['status'], 'UNAVAILABLE')
        section = marker.sections()[0]
        x = marker._raster_interval(section['on'])[0]
        y = section['line']
        for removed_x in (x, x+2):
            bad = bytearray(self.on)
            at = 3*(y*640+removed_x)
            bad[at:at+3] = bytes(3)
            self.assertNotEqual(self.check(on=bytes(bad))['status'], 'PASS')
        bad = bytearray(self.on)
        at = 3*(y*640+x-3)
        bad[at:at+3] = bytes((241, 55, 89))
        self.assertEqual(self.check(on=bytes(bad))['status'], 'UNAVAILABLE')

    def test_required_actual_pose_basis_uv_parity_and_active_bounds_fail_closed(self):
        mutations = (
            lambda r: r['records'][0]['data']['camera'].update(fov=89),
            lambda r: r['records'][0]['data'].update(width=641),
            lambda r: r['records'][1]['data'].update(normal=[1, 0, 0]),
            lambda r: r['records'][1]['data'].update(handedness=-1),
            lambda r: r['records'][1]['data']['surface'].update(uv=[0, 0, 1, 1]),
            lambda r: r['records'][1]['data']['surface'].update(uv_mirror_x=True),
            lambda r: r['records'][1]['data']['context'].update(mirrored=True),
            lambda r: r['records'][1]['data']['context'].update(position=[-161, -80, 96]),
            lambda r: r['records'][2]['data'].update(uv_bounds=[0, 0, 0, 0]),
            lambda r: r['records'][2]['data'].update(depth=float('nan')),
            lambda r: r['records'][2]['data'].update(quality=1),
        )
        for mutate in mutations:
            raw = state(True)
            mutate(raw)
            self.assertEqual(self.check(on_state=raw)['status'], 'UNAVAILABLE')
        self.assertEqual(self.check(on_state=None)['status'], 'UNAVAILABLE')
        native = copy.deepcopy(self.natives['sdvk008-sm'])
        native['direction_witness_revision'] = 'old'
        self.assertEqual(self.check(on_native=native)['status'], 'UNAVAILABLE')
        self.assertEqual(self.check(on_native=self.natives['sdvk008-flipx-on'])['status'], 'UNAVAILABLE')

    def test_existing_numeric_pose_contract_accepts_roundoff_without_new_tolerance(self):
        raw = state(False)
        raw['records'][0]['data']['camera']['fov'] = 90.00000000000001
        for row in raw['records'][1:]:
            row['data']['context']['position'] = [-160.00000000000003, -80.00000000000001, 96]
        self.assertEqual(self.check(off_state=raw)['status'], 'PASS')

    def test_area_jacobian_counterexample_invalidates_global_centroid(self):
        def image(on):
            raw = bytearray(100*20*3)
            for lo, hi in (((11, 16), (81, 85)) if on else ((10, 14), (80, 84))):
                for y in range(5 if on else 6, 11 if on else 12):
                    for x in range(lo, hi):
                        at = 3*(y*100+x)
                        raw[at:at+3] = bytes((241, 55, 89))
            return bytes(raw)
        # Left T(x)=x+1+(x-10)/4, right T(x)=x+1, both T(y)=y-1.
        # Every point goes right/up, but the expanding left component gains
        # area weight. No clipping, deletion, or source point moves left.
        legacy = fixtures.red_marker_direction(image(False), image(True), 100, 20)
        self.assertEqual(legacy['status'], 'FAIL')
        self.assertAlmostEqual(legacy['delta_x_px'], -2.6111111111111143)

    def test_local_edges_survive_unrelated_area_jacobian_centroid_reversal(self):
        off, on = bytearray(self.off), bytearray(self.on)
        # Extra material patches stay outside the preregistered stripe supports.
        # The left patch expands under T(x)=x+1+(x-10)/4; the right translates.
        # All these patch points also move right/up, yet aggregate X reverses.
        for raw, moved in ((off, False), (on, True)):
            for lo, hi in (((11, 111), (501, 581)) if moved else ((10, 90), (500, 580))):
                for y in range(19 if moved else 20, 99 if moved else 100):
                    for x in range(lo, hi):
                        at = 3*(y*640+x)
                        raw[at:at+3] = bytes((241, 55, 89))
        self.assertEqual(fixtures.red_marker_direction(bytes(off), bytes(on), 640, 480)['status'], 'FAIL')
        self.assertEqual(self.check(bytes(off), bytes(on))['status'], 'PASS')

    def test_source_projection_extent_is_fixed(self):
        result = marker.source_projected_marker_direction(bytes(1200), bytes(1200), 20, 20)
        self.assertEqual(result['status'], 'UNAVAILABLE')
        with self.assertRaises(ValueError):
            marker.source_projected_marker_direction(b'bad', b'bad', 640, 480)

    def test_prepare_requires_new_separately_identified_oracle_recipe(self):
        catalog = prepare.load_catalog()
        scene = next(s for s in catalog['scenes'] if s['id'] == 'sdvk008-sm')
        scene['native'].pop('direction_witness_revision')
        with self.assertRaisesRegex(ValueError, 'source-projected direction witness revision'):
            prepare.validate_catalog(catalog)


if __name__ == '__main__':
    unittest.main()
