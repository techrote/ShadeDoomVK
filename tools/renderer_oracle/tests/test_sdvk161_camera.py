"""The generic native receipt gate must enforce each authored map camera."""
import copy
import unittest

from tools.renderer_oracle import prepare, run
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.sdvk161_special_surfaces import settings_for_frame


class SpecialSurfaceCameraReceiptTests(unittest.TestCase):
    def packet(self):
        scene = copy.deepcopy(next(scene for scene in prepare.load_catalog()["scenes"]
                                   if scene["id"] == "special-surface-lifecycle"))
        records = []
        for number, name in ((1, "SDV161A"), (49, "SDV161B")):
            camera = scene["native"]["map_cameras"][name]
            records.append({"kind": "frame", "frame": number, "data": {
                "map": name, "settings": settings_for_frame(scene["native"], number),
                "camera": {"position": list(camera["position"]),
                           "angles": [camera[key] for key in ("yaw", "pitch", "roll")], "fov": 90}}})
        # This isolates the actual generic frame admission function. Complete
        # state/lifecycle/attempt admission has its separate full-packet tests.
        return {"mode": "timing", "records": records}, scene

    def test_actual_generic_gate_admits_both_authored_cameras(self):
        raw, scene = self.packet()
        run._scene_assertions(raw, scene)

    def test_prior_map_camera_cannot_be_borrowed_by_b(self):
        raw, scene = self.packet()
        raw["records"][1]["data"]["camera"] = copy.deepcopy(raw["records"][0]["data"]["camera"])
        with self.assertRaisesRegex(EvidenceError, "camera position"):
            run._scene_assertions(raw, scene)

    def test_unknown_map_has_no_camera_fallback(self):
        raw, scene = self.packet()
        raw["records"][1]["data"]["map"] = "SDV161C"
        with self.assertRaisesRegex(EvidenceError, "no authored map camera"):
            run._scene_assertions(raw, scene)

    def test_changed_camera_recipe_is_not_an_admission_override(self):
        raw, scene = self.packet()
        scene["native"]["map_cameras"]["SDV161B"]["position"][0] += 1
        raw["records"][1]["data"]["camera"]["position"][0] += 1
        with self.assertRaises((ValueError, EvidenceError)):
            run._scene_assertions(raw, scene)

    def test_ordinary_scene_cannot_select_an_injected_map_camera(self):
        scene = copy.deepcopy(next(scene for scene in prepare.load_catalog()["scenes"]
                                   if scene["id"] == "lights-zero"))
        native = scene["native"]
        wrong = dict(native["camera"], position=[1060, -176, 64], yaw=90)
        native["map_cameras"] = {native["map"]: wrong}
        raw = {"mode": "timing", "records": [{"kind": "frame", "frame": 1, "data": {
            "map": native["map"], "settings": native["settings"], "camera": {
                "position": wrong["position"], "angles": [90, 0, 0], "fov": 90}}}]}
        with self.assertRaisesRegex(EvidenceError, "camera position"):
            run._scene_assertions(raw, scene)


if __name__ == "__main__":
    unittest.main()
