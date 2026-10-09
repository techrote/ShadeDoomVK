"""Synthetic negative controls for native envelope and controlled comparisons.

These constructed records test validation rules; they are never native evidence.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import run
import validate
from test_evidence import png


def context(identity=1, *, parent=0, depth=0, semantic="main"):
    return {"available": True, "semantic_key": semantic, "producer": "root", "map": "SDV001", "type": "main",
            "root_type": "main", "epoch": 1, "identity": identity, "parent_identity": parent,
            "depth": depth, "face": -1, "eye": 0, "portal_group": 0, "line_mirror": False,
            "plane_mirror": False, "mirrored": False, "history_eligible": True,
            "postprocess_eligible": True, "position": [0, 0, 64], "angles": [0, 0, 0],
            "fraction": .5, "gametic": 100, "angle_space": "hardware-view"}


def row(kind, data, *, frame=1, count=1):
    return {"kind": kind, "frame": frame, "count": count, "data": data}


def observation():
    unavailable = {"available": False, "reason": "synthetic absent channel"}
    sampler = {"available": True, "min_filter": 1, "mag_filter": 1, "mipmap_mode": 1,
               "address_u": 0, "address_v": 0, "address_w": 0, "lod_bias": 0, "min_lod": 0,
               "max_lod": 16, "anisotropy": False, "max_anisotropy": 1}
    records = [row("context", {"context": context(), "drawmode": 0}),
               row("material", {"context": context(), "semantic_key": "SYNTHETIC", "name": "SYNTHETIC",
                                "layers": [{"binding": 0, "semantic": "albedo", "role": "authored-layer", "sampler": sampler}],
                                "resource": {"available": True, "index": 16, "generation": 1, "epoch": 1, "span": 1}}),
               row("frame", {"gametic": 100, "map": "SDV001", "cpu_render_view_ms": 2,
                             "camera": {"position": [0, 0, 64], "angles": [0, 0, 0], "hardware_angles": [270, 0, 0], "fraction": .5, "fov": 90},
                             "settings": {"vid_rendermode": 4}, "hardware_renderer": True,
                             "state_instrumentation": True, "width": 2, "height": 1,
                             "walls": 4, "flats": 2, "sprites": 2, "decals": 0, "portals": 0, "vertices": 100})]
    return {"schema": "sdvk-renderer-observation/v1", "status": "COLLECTED_PENDING_VALIDATION", "error": "",
            "mode": "state", "gpu_timing_requested": False, "performance_accepted": False,
            "requested_frames": 1, "observed_frames": 1, "warmup_frames": 120, "dropped_records": 0,
            "build": {"commit": "a" * 40, "working_tree": "clean", "backend": "vulkan", "renderer": "hardware",
                      "device": "SYNTHETIC", "vulkan": {"available": True}, "identity": "synthetic unit test"},
            "limits": {"max_frames": 4096, "max_records": 65536, "max_record_bytes": 16384,
                       "max_retained_bytes": 16777216, "retained_records": 3, "retained_bytes": 1024},
            "availability": {"cpu_timing": {"available": True}, "state": {"available": True},
                             "gpu_timing": {**unavailable, "groups": 0}, "gpu_total_frame": unavailable},
            "screenshot": {"available": True, "path": "synthetic.png"}, "records": records}


def recount(data):
    data["limits"]["retained_records"] = len(data["records"])
    return data


class NativeEnvelopeTests(unittest.TestCase):
    def test_complete_state_collection_has_no_acceptance_claim(self):
        result = validate.observation(observation(), required_kinds=["material", "context"], expected_map="SDV001",
                                      expected_frames=1, expected_extent=[2, 1])
        self.assertEqual(result["status"], "PASS")
        self.assertIs(result["native_acceptance_awarded"], False)

    def test_failed_truncated_or_misidentified_collection_rejected(self):
        for key, value in (("status", "FAIL"), ("error", "overflow"), ("dropped_records", 1),
                           ("requested_frames", 2), ("requested_frames", True), ("performance_accepted", True)):
            data = observation()
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(common.EvidenceError):
                validate.observation(data)
        with self.assertRaises(common.EvidenceError):
            validate.observation(observation(), expected_map="OTHER")
        with self.assertRaises(common.EvidenceError):
            validate.observation(observation(), expected_extent=[640, 480])

    def test_one_complete_frame_does_not_hide_a_later_missing_channel(self):
        data = observation()
        later = copy.deepcopy(data["records"][-1])
        later["frame"] = 2
        data["records"].append(later)
        data["requested_frames"] = data["observed_frames"] = 2
        with self.assertRaisesRegex(common.EvidenceError, "Frame 2"):
            validate.observation(recount(data), required_kinds=["context", "material"])

    def test_referenced_context_payload_must_match_its_real_record(self):
        data = observation()
        data["records"][1]["data"]["context"]["position"][0] = 100
        with self.assertRaisesRegex(common.EvidenceError, "inconsistent context"):
            validate.observation(data)

    def test_orphan_or_wrong_depth_context_rejected(self):
        for parent, depth in ((9, 1), (1, 2)):
            data = observation()
            data["records"].append(row("context", {"context": context(2, parent=parent, depth=depth)}))
            with self.assertRaises(common.EvidenceError):
                validate.observation(recount(data))

    def test_mirror_parity_and_material_identity_fail_closed(self):
        data = observation()
        data["records"][0]["data"]["context"]["mirrored"] = True
        with self.assertRaises(common.EvidenceError):
            validate.observation(data)
        for material in ({"material": {"available": True}}, {"material": {"available": False, "reason": "absent"}}):
            data = observation()
            data["records"][1]["data"] = material
            with self.assertRaises(common.EvidenceError):
                validate.observation(data, required_kinds=["material"])
        data = observation()
        data["records"][1]["data"]["resource"]["generation"] = 0
        with self.assertRaises(common.EvidenceError):
            validate.observation(data)

    def test_sampler_range_and_duplicate_layer_binding_rejected(self):
        data = observation()
        layer = data["records"][1]["data"]["layers"][0]
        layer["sampler"]["min_lod"] = 17
        with self.assertRaises(common.EvidenceError):
            validate.observation(data)
        layer["sampler"]["min_lod"] = 0
        data["records"][1]["data"]["layers"].append(copy.deepcopy(layer))
        with self.assertRaises(common.EvidenceError):
            validate.observation(data)

    def test_gpu_groups_are_individual_requested_samples(self):
        data = observation()
        data["gpu_timing_requested"] = True
        data["records"].append(row("timing", {"clock": "gpu", "name": "Scene", "milliseconds": 1}))
        data["availability"]["gpu_timing"].update(available=True, groups=1)
        validate.observation(recount(data))
        data["records"][-1]["count"] = 2
        data["availability"]["gpu_timing"]["groups"] = 2
        with self.assertRaises(common.EvidenceError):
            validate.observation(data)
        data["records"][-1] = row("timing", {"available": False, "reason": "query unavailable"}, count=2)
        data["availability"]["gpu_timing"].update(available=False, groups=0)
        validate.observation(data)  # Unavailable batches may be deduplicated.

    def test_timing_mode_cannot_include_per_draw_state(self):
        data = observation()
        data["mode"] = "timing"
        data["records"][-1]["data"]["state_instrumentation"] = False
        data["availability"]["state"] = {"available": False, "reason": "timing mode"}
        with self.assertRaisesRegex(common.EvidenceError, "per-draw"):
            validate.observation(data)


class SemanticProjectionTests(unittest.TestCase):
    def test_only_declared_static_clock_and_context_tokens_are_normalized(self):
        left, right = observation(), observation()
        for record in right["records"]:
            value = record["data"]
            if "context" in value:
                value["context"].update(epoch=2, identity=8, gametic=200, fraction=.7)
            if record["kind"] == "frame":
                value.update(gametic=200, cpu_render_view_ms=99)
                value["camera"]["fraction"] = .7
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))
        self.assertEqual(validate.state_projection(left, static_scene=True), validate.state_projection(right, static_scene=True))
        right["records"][1]["data"]["resource"]["generation"] += 1
        self.assertNotEqual(validate.state_projection(left, static_scene=True), validate.state_projection(right, static_scene=True))

    def test_renderer_local_resource_slots_normalize_but_aliasing_and_generation_remain(self):
        left = observation()
        left["records"].insert(2, copy.deepcopy(left["records"][1]))
        recount(left)
        right = copy.deepcopy(left)
        for record in right["records"]:
            resource = record["data"].get("resource")
            if isinstance(resource, dict) and resource.get("available"):
                resource["index"] = 22
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))
        right["records"][2]["data"]["resource"]["index"] = 23
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))
        right = copy.deepcopy(left)
        right["records"][1]["data"]["resource"]["generation"] += 1
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))

    def test_shadow_rows_normalize_but_aliasing_and_rejection_remain(self):
        def shadow(light, decision, row_number):
            return row("shadow", {"caster": "world-geometry", "mode": "dynamic-1d-shadow-map",
                                  "decision": decision, "row": row_number,
                                  "light": {"semantic_key": light}})

        left = observation()
        left["records"][1:1] = [shadow("L0", "selected", 573), shadow("L1", "selected", 404),
                                 shadow("L2", "capacity-rejected", -1)]
        recount(left)
        right = copy.deepcopy(left)
        right["records"][1]["data"]["row"] = 571
        right["records"][2]["data"]["row"] = 403
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))

        aliased = copy.deepcopy(right)
        aliased["records"][2]["data"]["row"] = 571
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(aliased))

        rejected = copy.deepcopy(right)
        rejected["records"][3]["data"].update(decision="selected", row=12)
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(rejected))

    def test_context_float_noise_and_derived_label_normalize_but_real_motion_remains(self):
        left, right = observation(), observation()
        for record in left["records"]:
            value = record["data"]
            if "context" in value:
                value["context"]["semantic_key"] = "SDV001:MainView:-1:0:0:root:0:[0,0,64]:[0,0,0]"
        for record in right["records"]:
            value = record["data"]
            if "context" in value:
                value["context"]["position"][1] = -1e-14
                value["context"]["semantic_key"] = "SDV001:MainView:-1:0:0:root:0:[0,-0.00000000000001,64]:[0,0,0]"
            if record["kind"] == "frame":
                value["camera"]["position"][1] = -1e-14
                value["camera"]["fov"] = 89.99999999999999
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))
        right["records"][0]["data"]["context"]["position"][1] = 1e-6
        right["records"][1]["data"]["context"]["position"][1] = 1e-6
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))

        different_kind = copy.deepcopy(left)
        for record in different_kind["records"]:
            if "context" in record["data"]:
                record["data"]["context"]["producer"] = "portal-kind"
                record["data"]["context"]["semantic_key"] = "arbitrary derived label ignored by projection"
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(different_kind))


    def test_visual_time_validates_context_ownership_but_wall_values_do_not_pollute_scene_equality(self):
        left, right = observation(), observation()
        context_visual = {"scope": "main-owner", "advances_main_clock": True, "delta_seconds": 0.01,
                          "accumulated_seconds": 1.5, "generation": 3, "main_frame": 121,
                          "delta_valid": True, "interpolation_valid": True, "clamped": False,
                          "discontinuity": "none"}
        frame_visual = {"scope": "main-view-owner", "delta_seconds": 0.01,
                        "accumulated_seconds": 1.5, "generation": 3, "main_frame": 121,
                        "delta_valid": True, "interpolation_valid": True, "clamped": False,
                        "discontinuity": "none"}
        for data in (left, right):
            for record in data["records"]:
                if "context" in record["data"]:
                    record["data"]["context"]["visual_time"] = copy.deepcopy(context_visual)
                if record["kind"] == "frame":
                    record["data"]["visual_time"] = copy.deepcopy(frame_visual)
        right["records"][0]["data"]["context"]["visual_time"].update(
            delta_seconds=0.017, accumulated_seconds=7.0, generation=9, main_frame=444,
            delta_valid=True, interpolation_valid=False, discontinuity="interpolation-disabled")
        right["records"][1]["data"]["context"]["visual_time"].update(
            delta_seconds=0.017, accumulated_seconds=7.0, generation=9, main_frame=444,
            delta_valid=True, interpolation_valid=False, discontinuity="interpolation-disabled")
        right["records"][-1]["data"]["visual_time"].update(
            delta_seconds=0.017, accumulated_seconds=7.0, generation=9, main_frame=444,
            delta_valid=True, interpolation_valid=False, discontinuity="interpolation-disabled")
        validate.observation(left)
        validate.observation(right)
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))

        wrong_scope = copy.deepcopy(left)
        wrong_scope["records"][0]["data"]["context"]["visual_time"].update(
            scope="non-main-fallback", advances_main_clock=False)
        with self.assertRaisesRegex(common.EvidenceError, "visual-time scope"):
            validate.observation(wrong_scope)

        leaking_non_main = copy.deepcopy(left)
        non_main = leaking_non_main["records"][0]["data"]["context"]
        non_main.update(type="camera-texture", root_type="camera-texture", history_eligible=False,
                        postprocess_eligible=False)
        non_main["visual_time"].update(scope="non-main-fallback", advances_main_clock=False,
                                       delta_seconds=0.01, accumulated_seconds=1.0, delta_valid=True)
        with self.assertRaisesRegex(common.EvidenceError, "Non-main render context"):
            validate.observation(leaking_non_main)

    def test_resource_workload_telemetry_normalizes_but_health_and_epoch_state_remain(self):
        resource = {"scope": "synthetic cumulative owner snapshot",
                    "descriptor_requested": 64, "descriptor_device_limit": 64, "descriptor_capacity": 64,
                    "descriptor_dynamic_start": 8, "descriptor_current": 10, "descriptor_high_water": 12,
                    "descriptor_allocations": 4, "descriptor_reuses": 2, "descriptor_frees": 1,
                    "descriptor_failures": 0, "descriptor_invalid_frees": 0, "descriptor_limit_source": "device",
                    "lifetime": {"activations": 4, "retirements": 1, "resets": 0, "stale_rejects": 0,
                                 "invalid_retires": 0, "duplicate_activations": 0},
                    "texture_epoch": 1, "lightmap_epoch": 1, "probe_epoch": 1, "async_upload_epoch": 1,
                    "hardware_textures": 30, "lightmap_pages": 0, "irradiance_maps": 0, "prefilter_maps": 0,
                    "async_uploads": {"queued": 5, "completed": 5, "cancelled": 0,
                                      "missing_ticket_rejects": 0, "manager_epoch_rejects": 0, "target_epoch_rejects": 0},
                    "staging": {"requests": 5, "bytes": 1000, "high_water": 1000, "reuses": 4,
                                "wrap_waits": 0, "dedicated": 0}}
        left = observation()
        left["records"].append(row("resource", resource))
        recount(left)
        right = copy.deepcopy(left)
        changed = right["records"][-1]["data"]
        changed.update(descriptor_current=11, descriptor_high_water=13, descriptor_allocations=5,
                       descriptor_reuses=3, descriptor_frees=2, hardware_textures=31)
        changed["lifetime"].update(activations=5, retirements=2)
        changed["async_uploads"].update(queued=6, completed=6)
        changed["staging"].update(requests=6, bytes=1200, high_water=1200, reuses=5)
        self.assertEqual(validate.state_projection(left), validate.state_projection(right))
        for mutate in (
            lambda d: d["records"][-1]["data"].update(descriptor_failures=1),
            lambda d: d["records"][-1]["data"]["lifetime"].update(stale_rejects=1),
            lambda d: d["records"][-1]["data"]["lifetime"].update(resets=1),
            lambda d: d["records"][-1]["data"]["async_uploads"].update(cancelled=1),
            lambda d: d["records"][-1]["data"]["async_uploads"].update(manager_epoch_rejects=1),
            lambda d: d["records"][-1]["data"]["staging"].update(wrap_waits=1),
            lambda d: d["records"][-1]["data"]["staging"].update(dedicated=1),
            lambda d: d["records"][-1]["data"].update(texture_epoch=2),
            lambda d: d["records"][-1]["data"].update(descriptor_capacity=63),
        ):
            candidate = copy.deepcopy(left)
            mutate(candidate)
            self.assertNotEqual(validate.state_projection(left), validate.state_projection(candidate))

    def test_parent_semantic_lineage_survives_token_normalization(self):
        left = observation()
        parent = context(2, semantic="other-root")
        parent["history_eligible"] = False
        left["records"] += [row("context", {"context": parent}),
                            row("context", {"context": context(3, parent=1, depth=1, semantic="child")})]
        recount(left)
        right = copy.deepcopy(left)
        right["records"][-1]["data"]["context"]["parent_identity"] = 2
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))

    def test_duplicate_parent_labels_do_not_hide_different_parent_state(self):
        left = observation()
        parent = context(2)
        parent["history_eligible"] = False
        left["records"] += [row("context", {"context": parent}),
                            row("context", {"context": context(3, parent=1, depth=1, semantic="child")})]
        recount(left)
        right = copy.deepcopy(left)
        right["records"][-1]["data"]["context"]["parent_identity"] = 2
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))

    def test_cross_channel_order_is_preserved(self):
        left, right = observation(), observation()
        right["records"][0], right["records"][1] = right["records"][1], right["records"][0]
        self.assertNotEqual(validate.state_projection(left), validate.state_projection(right))


class CaptureReceiptTests(unittest.TestCase):
    def test_every_console_setting_needs_one_matching_real_readback(self):
        expected = {"flag": True, "quality": 4, "bias": .25, "screenshot_type": "png"}
        text = '\n'.join(f'"{key}" is "{str(value).lower()}" (default: "unused")' for key, value in expected.items()) + '\n'
        self.assertEqual(run.console_settings(text, expected), expected)
        for invalid in (text + text, text.replace('"quality" is "4"', '"quality" is "3"'),
                        text.replace('"bias" is "0.25"', '"bias" is "nan"'), text.splitlines()[0]):
            with self.assertRaises(common.EvidenceError):
                run.console_settings(invalid, expected)

    def test_loaded_inventory_rejects_injected_missing_or_changed_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "known.pk3"
            path.write_bytes(b"synthetic package bytes")
            expected = {str(path): common.pin(path)}
            text = f'W_Init: Init WADfiles.\nadding {path}, 2 lumps\n'
            self.assertEqual(len(run.loaded_packages(text, expected)), 1)
            for invalid in (text + f'adding {path}, 2 lumps\n', text.replace("known.pk3", "unknown.pk3"),
                            text.replace("W_Init: Init WADfiles.", "")):
                with self.assertRaises(common.EvidenceError):
                    run.loaded_packages(invalid, expected)
            path.write_bytes(b"changed package bytes")
            with self.assertRaises(common.EvidenceError):
                run.loaded_packages(text, expected)
            self.assertEqual(len(run.loaded_packages(text, expected, verify_files=False)), 1)

    def test_failed_capture_markers_cannot_hide_behind_success(self):
        run.completion_log("SDVK_OBSERVATION_COLLECTED: native.renderer.json\n")
        for text in ("", "SDVK_OBSERVATION_COLLECTED: x\nScript error: x", "SDVK_OBSERVATION_COLLECTED: x\nUnknown command x"):
            with self.assertRaises(common.EvidenceError):
                run.completion_log(text)

    def test_fixed_camera_settings_and_workload_counters_are_asserted(self):
        data = observation()
        scene = {"id": "synthetic", "native": {"camera": {"position": [0, 0, 64], "yaw": 0, "pitch": 0, "roll": 0},
                 "settings": {"vid_rendermode": 4}, "frame_assertions": {"sprites": {"minimum": 2}}}}
        run._scene_assertions(data, scene)
        rounded = copy.deepcopy(data)
        rounded["records"][-1]["data"]["camera"].update(position=[-2.8e-14, 0, 64], fov=89.99999999999999)
        run._scene_assertions(rounded, scene)
        rounded["records"][-1]["data"]["camera"]["position"][0] = 1e-6
        with self.assertRaises(common.EvidenceError):
            run._scene_assertions(rounded, scene)
        for key, value in (("sprites", 0), ("camera", {"position": [10, 0, 64]}), ("settings", {"vid_rendermode": 1})):
            changed = copy.deepcopy(data)
            changed["records"][-1]["data"][key] = value
            with self.assertRaises(common.EvidenceError):
                run._scene_assertions(changed, scene)

    def test_scene_assertions_reject_unexercised_mirror_material_and_probe_routes(self):
        data = observation()
        scene = {"id": "synthetic", "native": {"camera": {"position": [0, 0, 64], "yaw": 0, "pitch": 0, "roll": 0},
                 "settings": {}, "state_assertions": {"line_mirror": True, "materials": ["SYNTHETIC"],
                 "material_semantics": {"SYNTHETIC": ["albedo"]}, "published_probes_minimum": 2, "sun_intensity": 1}}}
        data["records"][0]["data"]["context"]["line_mirror"] = True
        data["records"] += [row("resource", {"irradiance_maps": 2, "prefilter_maps": 2, "sun": {"intensity": 1}}),
                            row("probe", {"fallback": False, "resource": {"available": True}})]
        run._scene_assertions(data, scene)
        mutations = [lambda d: d["records"][0]["data"]["context"].update(line_mirror=False),
                     lambda d: d["records"][1]["data"].update(name="WRONG"),
                     lambda d: d["records"][1]["data"]["layers"][0].update(semantic="normal"),
                     lambda d: d["records"][-2]["data"].update(irradiance_maps=1),
                     lambda d: d["records"][-2]["data"]["sun"].update(intensity=0),
                     lambda d: d["records"][-1]["data"].update(fallback=True)]
        for mutation in mutations:
            changed = copy.deepcopy(data)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(common.EvidenceError):
                run._scene_assertions(changed, scene)

    def test_material_semantics_allow_only_ordered_one_pixel_engine_placeholders(self):
        data = observation()
        scene = {"id": "synthetic", "native": {"camera": {"position": [0, 0, 64], "yaw": 0, "pitch": 0, "roll": 0},
                 "settings": {}, "state_assertions": {"materials": ["SYNTHETIC"],
                 "material_semantics": {"SYNTHETIC": ["albedo"]}}}}
        base = copy.deepcopy(data["records"][1]["data"]["layers"][0])
        for semantic in ("brightmap-emissive", "detail", "glow"):
            layer = copy.deepcopy(base)
            layer["binding"] = len(data["records"][1]["data"]["layers"])
            layer["semantic"] = semantic
            layer["role"] = "fallback-placeholder"
            layer["source"] = {"lump": 0, "width": 1, "height": 1}
            data["records"][1]["data"]["layers"].append(layer)
        run._scene_assertions(data, scene)

        changed = copy.deepcopy(data)
        changed["records"][1]["data"]["layers"][-1]["source"]["lump"] = 9
        with self.assertRaises(common.EvidenceError):
            run._scene_assertions(changed, scene)

        changed = copy.deepcopy(data)
        changed["records"][1]["data"]["layers"][-1]["semantic"] = "metallic"
        with self.assertRaises(common.EvidenceError):
            run._scene_assertions(changed, scene)

        changed = copy.deepcopy(data)
        changed["records"][1]["data"]["layers"][-1]["role"] = "authored-layer"
        with self.assertRaises(common.EvidenceError):
            run._scene_assertions(changed, scene)

        changed = copy.deepcopy(data)
        changed["records"][1]["data"]["layers"][0]["semantic"] = "normal"
        with self.assertRaises(common.EvidenceError):
            run._scene_assertions(changed, scene)

    def test_equal_images_do_not_hide_a_state_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            roots = [Path(temporary) / name for name in ("left", "right")]
            for root in roots:
                root.mkdir()
                (root / "native.png").write_bytes(png(bytes(6)))
                common.write_json(root / "run.json", {"synthetic": True})
                common.write_json(root / "request.json", {"cwd": str(root)})
            a, b = observation(), observation()
            b["records"][1]["data"]["resource"]["generation"] = 2
            receipt = {"mode": "state", "reproduction": {"clock": "static_after_initialization", "image_policy": {"metric": "exact-rgb8"}},
                       "build": a["build"], "executable": {"sha256": "a" * 64}, "loaded_packages": []}
            with mock.patch.object(run, "validate_run", side_effect=[(roots[0], receipt, a, {}), (roots[1], receipt, b, {})]):
                result = run.compare_runs(*roots)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["image"]["passed"])
            self.assertFalse(result["state_equal"])


if __name__ == "__main__":
    unittest.main()
