"""CPU controls for live-player viewmodel recipes and emitted uniform policy."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import prepare
import sdvk011_viewmodel as target
import validate
from test_validation import context, observation, recount, row


def draw():
    return {"contract": target.CONTRACT, "material": "SDVUA0", "context": context(),
            "requested_mode": 2, "effective_mode": 2, "fallback_reason": 0,
            "world_sample_enabled": True, "sample": [8, 41, 0], "tangent": [0, 0, 1],
            "normal": [-1, 0, 0], "handedness": -1, "explicit_basis": True,
            "relief_enabled": False, "authored_probe": 0, "runtime_irradiance_index": 22,
            "probe_epoch": 1, "probe_resource": {"available": True, "index": 22, "generation": 1,
                                                       "epoch": 1, "span": 2},
            "shader": 3, "light_index": 0, "indexed": False, "draw_count": 4,
            "pipeline": {"fixture": True},
            "uniform_scope": "emitted-vulkan-draw-after-apply-surface-uniforms"}


def model_draw():
    value = draw()
    value.update(material="SDVW", shader=4, model_geometry=True, explicit_basis=False,
                 tangent=[0, 0, 0], normal=[0, 0, 0], handedness=0, draw_count=36,
                 normal_model_matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                 basis_source="model-world-normal-matrix-and-derivative-tbn",
                 pipeline={"shader": {"VertexFormat": 2, "ShadeVertex": 0, "LightNoNormals": 0,
                                      "UseSpriteCenter": 1, "UseLevelMesh": 0}})
    return value


class ViewmodelTests(unittest.TestCase):
    def test_model_world_normal_matrix_and_derivative_policy(self):
        target.validate_draw(model_draw())
        for key, bad in (("explicit_basis", True), ("normal_model_matrix", [0]*16),
                         ("normal_model_matrix", [float("nan")]*16),
                         ("normal_model_matrix", ["1"]*16), ("basis_source", "camera-space-guess")):
            value = model_draw(); value[key] = bad
            with self.subTest(key=key), self.assertRaises(common.EvidenceError): target.validate_draw(value)

    def test_model_frame_requires_the_actual_loader_draw_and_anchor_pipeline(self):
        scene = next(s for s in prepare.load_catalog()["scenes"] if s["id"] == "viewmodel-model-pbr")
        spec, camera = scene["native"]["state_assertions"]["viewmodel"], scene["native"]["camera"]
        target.validate_frame([row("viewmodel", model_draw())], spec, camera)
        for mutation in ("quad", "vertices", "vertex-shading", "sample-origin"):
            value = model_draw()
            if mutation == "quad": value = draw(); value.update(material="SDVW", shader=4)
            elif mutation == "vertices": value["draw_count"] = 4
            elif mutation == "vertex-shading": value["pipeline"]["shader"]["ShadeVertex"] = 1
            else: value["pipeline"]["shader"]["UseSpriteCenter"] = 0
            with self.subTest(mutation=mutation), self.assertRaises(common.EvidenceError):
                target.validate_frame([row("viewmodel", value)], spec, camera)

    def test_original_model_assets_use_existing_loader_and_normal_weapon_states(self):
        catalog = prepare.load_catalog()
        for scene in (s for s in catalog["scenes"] if s["id"].startswith("viewmodel-model-")):
            _, members, metadata = prepare.scene_assets(scene)
            self.assertEqual(members["models/sdvkvm.obj"].count(b"\nf "), 6)
            self.assertIn(b'Model 0 "sdvkvm.obj"', members["MODELDEF"])
            self.assertIn(b'Skin 0 "SDVW"', members["MODELDEF"])
            self.assertIn(b'FrameIndex SDVU A 0 0', members["MODELDEF"])
            self.assertEqual(metadata["weapon_material"], "SDVW")

    def test_modes_fallbacks_and_projection_uniform_reset(self):
        target.validate_draw(draw())
        for requested, mode, fallback in ((0, 0, 0), (1, 1, 0), (2, 0, 2),
                                           (2, 0, 3), (2, 1, 4), (2, 0, 5), (2, 1, 6), (99, 0, 1)):
            value = draw()
            value.update(requested_mode=requested, effective_mode=mode, fallback_reason=fallback,
                         world_sample_enabled=False, explicit_basis=False,
                         sample=[0, 0, 0], tangent=[0, 0, 0], normal=[0, 0, 0], handedness=0)
            with self.subTest(requested=requested, mode=mode, fallback=fallback):
                target.validate_draw(value)
                invalid = copy.deepcopy(value); invalid["sample"][0] = 8
                with self.assertRaises(common.EvidenceError): target.validate_draw(invalid)

    def test_wrong_basis_projection_modes_and_relief_fail(self):
        for key, bad in (("tangent", [1, 0, 0]), ("normal", [0, 0, 0]),
                         ("sample", [float("nan"), 0, 0]), ("handedness", 0),
                         ("requested_mode", True), ("world_sample_enabled", False),
                         ("effective_mode", 1), ("fallback_reason", 2),
                         ("relief_enabled", True), ("uniform_scope", "cpu-prediction")):
            value = draw(); value[key] = bad
            with self.subTest(key=key), self.assertRaises(common.EvidenceError): target.validate_draw(value)

    def test_envelope_checks_actual_probe_identity_and_normalizes_only_slot_label(self):
        left = observation(); left["records"].insert(1, row("viewmodel", draw())); recount(left)
        validate.observation(left, required_kinds=["viewmodel"])
        right = copy.deepcopy(left)
        right["records"][1]["data"]["runtime_irradiance_index"] = 80
        right["records"][1]["data"]["probe_resource"]["index"] = 80
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))
        right["records"][1]["data"]["probe_resource"]["generation"] = 2
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))
        right["records"][1]["data"]["probe_resource"]["index"] = 81
        with self.assertRaises(common.EvidenceError): validate.observation(right)

    def test_frame_requires_real_weapon_current_probe_local_lights_and_world_sample(self):
        scene = next(s for s in prepare.load_catalog()["scenes"] if s["id"] == "viewmodel-enhanced")
        spec, camera = scene["native"]["state_assertions"]["viewmodel"], scene["native"]["camera"]
        target.validate_frame([row("viewmodel", draw())], spec, camera)
        for mutation in ("missing", "sample", "probe", "light", "shader"):
            value = draw()
            if mutation == "sample": value["sample"] = [8, 0, 41]
            if mutation == "probe": value["runtime_irradiance_index"] = 0
            if mutation == "light": value["light_index"] = -1
            if mutation == "shader": value["shader"] = 4
            records = [] if mutation == "missing" else [row("viewmodel", value)]
            with self.subTest(mutation=mutation), self.assertRaises(common.EvidenceError):
                target.validate_frame(records, spec, camera)

    def test_live_player_assets_and_all_mode_recipes_are_deterministic(self):
        catalog = prepare.load_catalog(); prepare.validate_catalog(catalog)
        scenes = [s for s in catalog["scenes"] if s["native"]["generator"] == "viewmodel"]
        self.assertEqual(len(scenes), 10)
        for scene in scenes:
            first = prepare.scene_assets(scene); second = prepare.scene_assets(scene)
            self.assertEqual(first, second)
            _, members, metadata = first
            self.assertTrue(metadata["live_player_camera"])
            self.assertIsNone(metadata["camera_actor_tid"])
            self.assertIn(b'PlayerClasses = "SDVKVMPlayer"', members["MAPINFO"])
            self.assertIn(b"A_WeaponReady", members["ZSCRIPT"])
            self.assertIn(b"A_FireBullets", members["ZSCRIPT"])
            self.assertIn("sprites/SDVUA0.png", members)
            self.assertTrue(scene["native"]["settings"]["r_drawplayersprites"])
            self.assertIn("viewmodel", scene["required_state_channels"])
            self.assertNotIn(b"r_drawplayersprites false", prepare.capture_script(scene))
        self.assertEqual(next(s for s in scenes if s["id"] == "viewmodel-wide")["native"]["camera"]["fov"], 110)

    def test_hidden_weapon_and_unknown_mode_recipes_are_rejected(self):
        for mutation in ("hidden", "bad-mode"):
            catalog = prepare.load_catalog()
            scene = next(s for s in catalog["scenes"] if s["id"] == "viewmodel-enhanced")
            if mutation == "hidden": scene["native"]["settings"]["r_drawplayersprites"] = False
            else: scene["native"]["state_assertions"]["viewmodel"]["effective_mode"] = 9
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): prepare.validate_catalog(catalog)


if __name__ == "__main__": unittest.main()
