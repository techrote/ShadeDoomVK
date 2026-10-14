#!/usr/bin/env python3
"""SDVK-010 sunlight actor fixture / emitted-state adversarial tests.

CPU only: generation, source-contract checks and synthetic negative proofs do
not replace the required two hosted native image/state captures.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.renderer_oracle import prepare, run, sdvk010_sun_occlusion as sun
from tools.renderer_oracle.common import EvidenceError

SPEC = {
    "sunlit_tid": 2020, "occluded_tid": 2021, "authored_probe_index": 0, "material": "SDVOA0",
    "sunlit_xy": [0, -88], "occluded_xy": [0, 88],
    "expected_sun_direction": [-0.6123724357, 0.3535533906, 0.7071067812],
    "image_rois": {"sunlit": [467, 267, 8], "occluded": [173, 267, 8]},
}


def emitted_rows():
    def actor(tid, xy):
        return {
            "kind": "probe", "data": {
                "context": {"root_type": "main"},
                "material": "SDVOA0", "authored_index": 0, "runtime_irradiance_index": 259,
                "fallback": False, "probe_epoch": 2,
                "published_irradiance": 1, "published_prefilter": 1,
                "resource": {"available": True, "index": 259, "generation": 1, "epoch": 3, "span": 2},
                "actor_selection": {"available": True, "selected": True, "policy": "spatial-nearest",
                    "authored_index": 0, "actor_position": [xy[0], xy[1], 32],
                    "source_portal_group": 0, "render_portal_group": 0},
                "actor_sunlight": {
                    "available": True, "contract": "sdvk-010-actor-sun-world-v1",
                    "actor_tid": tid, "packed_sun_count": 1, "traced_sun_count": 1,
                    "light_range_index": 0, "light_range_uploaded": True,
                    "source_portal_group": 0, "render_portal_group": 0,
                    "scope": "actual actor sprite packed sunlight proxy; fragment visibility is image evidence, not a CPU prediction"},
            }}
    return [
        {"kind": "resource", "data": {
            "sun": {"intensity": 1, "direction": SPEC["expected_sun_direction"][:]},
            "irradiance_maps": 1, "prefilter_maps": 1, "levelmesh": {"epoch": 4}}},
        {"kind": "material", "data": {"name": "SDVOA0"}},
        {"kind": "shadow", "data": {"context": {"root_type": "main"},
              "material": "SDVOA0", "mode": "world-trace"}},
        actor(2020, SPEC["sunlit_xy"]),
        actor(2021, SPEC["occluded_xy"])
    ]


def pbr_image(first=205, second=25):
    image = bytearray([70] * (640 * 480 * 3))
    for label, brightness in (("sunlit", first), ("occluded", second)):
        x, y, r = SPEC["image_rois"][label]
        for py in range(y-r, y+r+1):
            for px in range(x-r, x+r+1):
                idx = (py * 640 + px) * 3
                image[idx:idx+3] = bytes([brightness] * 3)
    return bytes(image)


class SDVK010SunOcclusionTests(unittest.TestCase):
    def test_authored_geometry_is_one_sided_and_sun_ray_not_camera_ray(self):
        scene = next(s for s in prepare.load_catalog()["scenes"] if s["id"] == "sun-actor-occlusion")
        sun.check_contract(scene["native"]["state_assertions"]["actor_sun_occlusion"])
        prepare.validate_catalog(prepare.load_catalog())
        members, info = prepare.authored_members(scene)
        self.assertEqual(info["boundary_signed_areas"][0] < 0, True)
        self.assertEqual(len(info["boundary_signed_areas"]), 2)
        self.assertGreater(info["boundary_signed_areas"][1], 0)
        self.assertEqual(info["counts"]["sector"], 1)
        self.assertEqual(info["actor_sun_occlusion"]["probe_ordinal"], 0)
        self.assertEqual(info["actor_sun_occlusion"]["camera_ray_blocked_by_column"], False)
        self.assertIn(b'class SDVKMarker : Actor', members["ZSCRIPT"])
        self.assertIn(b'material texture SDVOA0', members["GLDEFS"])
        self.assertIn("maps/SDVSOCC.wad", members)
        self.assertIn("sprites/SDVOA0.png", members)
        self.assertEqual(scene["native"]["settings"]["gl_light_shadows"], 2)
        self.assertEqual(scene["native"]["settings"]["gl_spritelight"], 2)
        self.assertTrue(scene["native"]["settings"]["gl_levelmesh"])
        self.assertFalse(scene["native"]["settings"]["vk_rayquery"])
        # Physically authored collision slab x[-96,-48], y[96,160].
        # Northern sun ray goes NW/up; southern sun ray misses entirely.
        dx, dy, dz = SPEC["expected_sun_direction"]
        for x in (-96, -48):
            time_to_slab = x / dx
            north_y, south_y = (88 + time_to_slab*dy, -88 + time_to_slab*dy)
            z = 64 + time_to_slab*dz
            self.assertTrue(96 < north_y < 160)
            self.assertFalse(96 < south_y < 160)
            self.assertTrue(32 < z < 256)
            # Camera (-192,0,80) -> both cards at (0,+/-88,64):
            # the y coordinate through the slab is below its northern edge.
            self.assertLess((x + 192)/192 * 88, 96)
        self.assertTrue(info["actor_sun_occlusion"]["image_and_fragment_visibility_not_proven_by_authoring"])

    def test_sun_shader_reuses_accepted_world_trace_before_local_shadow_rule(self):
        shader = (ROOT / "wadsrc/static/shaders/scene/lightmodel_pbr.glsl").read_text()
        normal = (ROOT / "wadsrc/static/shaders/scene/lightmodel_normal.glsl").read_text()
        self.assertIn("traceSun(L)", shader)
        self.assertIn("(LIGHTINFO_SUN | LIGHTINFO_TRACE)", shader)
        self.assertIn("attenuation *= traceSun(lightdir)", normal)
        self.assertLess(shader.index("attenuation *= traceSun(L)"),
                        shader.index("attenuation *= shadowAttenuation("))
        self.assertIn("LIGHT_COMPAT_SUN_ATTENUATION_RADIUS", shader)

    def test_native_draw_provenance_positive_and_adversarial_mutations(self):
        records=emitted_rows()
        proof=sun.validate_emitted_frame(records, SPEC)
        self.assertEqual(proof["status"], "PASS")
        changes = [
            (4, ["data", "actor_sunlight", "actor_tid"], 2020),
            (4, ["data", "actor_selection", "authored_index"], 1),
            (4, ["data", "actor_selection", "actor_position"], [0, -88, 32]),
            (4, ["data", "material"], "WRONG"),
            (4, ["data", "actor_sunlight", "traced_sun_count"], 0),
            (4, ["data", "actor_sunlight", "light_range_uploaded"], False),
            (4, ["data", "probe_epoch"], 999),
            (4, ["data", "resource", "generation"], 999),
            (4, ["data", "resource", "span"], 1),
            (4, ["data", "runtime_irradiance_index"], 260),
            (4, ["data", "actor_selection", "policy"], "sector-target"),
            (2, ["data", "mode"], "disabled"),
            (0, ["data", "sun", "intensity"], 0),
            (0, ["data", "sun", "direction"], [0, 0, 1]),
            (0, ["data", "irradiance_maps"], 0),
        ]
        for index, keys, value in changes:
            with self.subTest(keys=keys,value=value):
                bad=copy.deepcopy(records)
                cursor=bad[index]
                for key in keys[:-1]:
                    cursor=cursor[key]
                cursor[keys[-1]]=value
                with self.assertRaises(EvidenceError):
                    sun.validate_emitted_frame(bad, SPEC)
        for removed in (1, 3, 4):
            bad=copy.deepcopy(records)
            bad.pop(removed)
            with self.subTest(missing=removed), self.assertRaises(EvidenceError):
                sun.validate_emitted_frame(bad, SPEC)

    def test_projected_native_image_order_and_integrity_negative_controls(self):
        self.assertEqual(sun.validate_projected_image((640,480), pbr_image(),SPEC)["status"], "PASS")
        for first, second in ((50,220),(100,100)):
            with self.subTest(first=first,second=second), self.assertRaises(EvidenceError):
                sun.validate_projected_image((640,480), pbr_image(first,second),SPEC)
        with self.assertRaises(EvidenceError):
            sun.validate_projected_image((640,480), b"short",SPEC)
        wrong=copy.deepcopy(SPEC)
        wrong["image_rois"]["sunlit"]=[320,267,8]
        with self.assertRaises(EvidenceError):
            sun.check_contract(wrong)

    def test_process_local_resource_labels_normalize_bijectively_and_probe_state_stays_strict(self):
        left = [
            {"kind": "material", "data": {"name": "SDVSKY", "resource":
                {"available": True, "index": 259, "generation": 3, "epoch": 2, "span": 4}}},
            {"kind": "material", "data": {"name": "SDVSKY", "resource":
                {"available": True, "index": 259, "generation": 3, "epoch": 2, "span": 4}}},
            {"kind": "resource", "data": {"texture_epoch": 3, "probe_epoch": 2, "lightmap_epoch": 4, "async_upload_epoch": 1}},
            {"kind": "resource", "data": {"texture_epoch": 5, "probe_epoch": 2, "lightmap_epoch": 4, "async_upload_epoch": 1}},
            {"kind": "probe", "data": {"resource":
                {"available": True, "index": 283, "generation": 1, "epoch": 2, "span": 2}}},
        ]
        right = copy.deepcopy(left)
        right[0]["data"]["resource"]["generation"] = 4
        right[1]["data"]["resource"]["generation"] = 4
        right[2]["data"]["texture_epoch"] = 4
        right[3]["data"]["texture_epoch"] = 6
        self.assertEqual(run._sdvk010_repeatability_projection(left, "sun-actor-occlusion"),
                         run._sdvk010_repeatability_projection(right, "sun-actor-occlusion"))

        changed_material_lifecycle = copy.deepcopy(right)
        changed_material_lifecycle[1]["data"]["resource"]["generation"] = 5
        self.assertNotEqual(run._sdvk010_repeatability_projection(left, "sun-actor-occlusion"),
                            run._sdvk010_repeatability_projection(changed_material_lifecycle, "sun-actor-occlusion"))

        changed_texture_epoch_pattern = copy.deepcopy(right)
        changed_texture_epoch_pattern[3]["data"]["texture_epoch"] = 4
        self.assertNotEqual(run._sdvk010_repeatability_projection(left, "sun-actor-occlusion"),
                            run._sdvk010_repeatability_projection(changed_texture_epoch_pattern, "sun-actor-occlusion"))

        changed_probe = copy.deepcopy(right)
        changed_probe[4]["data"]["resource"]["generation"] = 2
        self.assertNotEqual(run._sdvk010_repeatability_projection(left, "sun-actor-occlusion"),
                            run._sdvk010_repeatability_projection(changed_probe, "sun-actor-occlusion"))

        changed_probe_epoch = copy.deepcopy(right)
        changed_probe_epoch[2]["data"]["probe_epoch"] = 3
        self.assertNotEqual(run._sdvk010_repeatability_projection(left, "sun-actor-occlusion"),
                            run._sdvk010_repeatability_projection(changed_probe_epoch, "sun-actor-occlusion"))

    def test_unsafe_catalog_fails_closed_before_native_capture(self):
        for change in ("sun_angle", "shadow_mode", "actor_pair", "probe_material", "map_guard"):
            catalog=prepare.load_catalog()
            scene=next(s for s in catalog["scenes"] if s["id"] == "sun-actor-occlusion")
            if change=="sun_angle":
                scene["native"]["state_assertions"]["actor_sun_occlusion"]["expected_sun_direction"]=[0,0,1]
            elif change=="shadow_mode":
                scene["native"]["settings"]["gl_light_shadows"]=0
            elif change=="actor_pair":
                scene["native"]["state_assertions"]["actor_sun_occlusion"]["occluded_tid"]=2020
            elif change=="probe_material":
                scene["native"]["state_assertions"]["actor_sun_occlusion"]["material"]="SDVOA0-OTHER"
            else:
                scene["native"]["map_guard"]["equals"]="SDVSUN"
            with self.subTest(change=change), self.assertRaises((ValueError, EvidenceError)):
                prepare.validate_catalog(catalog)


if __name__=="__main__":
    unittest.main()
