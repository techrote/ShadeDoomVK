"""CPU-only exact admission/capture-boundary controls; no renderer or GPU."""
import copy
import json
from pathlib import Path
import subprocess
import types
from unittest.mock import Mock, patch

from .common import Stop, exclusive, pin, read_json
from .conditional_grant import authority, initialize_ledger
from .prepare import frozen_oracle, registered_packet
from .registered import (after_capture, before_capture, definition, validate,
                         shadowoff_reference_stage, shadowoff_reference_receipt)
from . import test_registered as registered_fixtures
from . import test_supervisor as fixtures
from tools.renderer_oracle import sdvk009_shadowoff as scaling


class ShadowoffAdmissionTests(fixtures.TempCase):
    # Reuse only CPU seed/preflight and the actual run.capture boundary harness,
    # not its inherited test methods or any native-supervisor target.
    seed_and_registration = registered_fixtures.RegisteredWorkloadTests.seed_and_registration
    assert_real_capture_boundary = registered_fixtures.RegisteredWorkloadTests.assert_real_capture_boundary

    def prepared(self):
        seed, previous, grant = self.seed_and_registration(scaling.SCENES, purpose=scaling.PURPOSE)
        document = read_json(previous)
        hashes = {row["scene"]: row["recipe_sha256"] for row in document["captures"]}
        document["captures"] = scaling.capture_specs(hashes)
        registration = self.root / "shadowoff-registration.json"
        exclusive(registration, document)
        grant.update(registered_workload={"profile": "REGISTERED_WORKLOAD", "registration": pin(registration)},
                     tests=[row["name"] for row in document["captures"]], max_renderer_launches=20,
                     ledger_root=str(self.root / "shadowoff-ledger"))
        grant_pin = initialize_ledger(grant)
        seed["conditional_grant"] = grant_pin
        seed["files"].append(grant_pin)
        with patch("tools.physical_supervisor.common.verify_registry"), \
             patch("tools.physical_supervisor.common.verify_source"):
            packet = registered_packet(seed, registration)
        return packet, grant

    def test_actual_twenty_stage_preparer_and_state_timing_capture_boundaries(self):
        packet, grant = self.prepared()
        self.assertEqual(authority(packet), grant)
        stages = packet["stages"]
        self.assertEqual(len(stages), 20)
        self.assertEqual([s["capture"]["mode"] for s in stages], ["state"] * 8 + ["timing"] * 12)
        for scene in scaling.SCENES:
            self.assertEqual(sum(s["capture"]["mode"] == "timing" and s["capture"]["scene"] == scene for s in stages), 3)
        self.assert_real_capture_boundary(packet, stages[0])
        with patch("tools.physical_supervisor.registered.before_capture",
                   return_value={"status": "PASS", "CPU_CONTROL_ONLY": True}) as gate:
            self.assert_real_capture_boundary(packet, stages[8])
        gate.assert_called_once()
        for stage in (stages[0], stages[8]):
            script = Path(stage["capture"]["out"]) / "capture.cfg"
            expected = next(row for row in stage["generated_pins"] if row["path"] == str(script))
            self.assertEqual(pin(script), expected)
            self.assertIn(b"; vid_setsize 1904 1001; ", script.read_bytes())
        self.assertIn("-sdvkobservegpu", stages[8]["expected_argv"])
        self.assertNotIn("-sdvkobservegpu", stages[0]["expected_argv"])
        self.assertEqual(stages[8]["expected_argv"][stages[8]["expected_argv"].index("-sdvkobserveframes") + 1], "120")
        self.assertNotIn("native.png", stages[8]["required_outputs"])

    def test_schedule_mutation_and_existing_purposes_cannot_enable_timing(self):
        packet, _ = self.prepared()
        original = definition(packet)
        for defect in ("early-timing", "missing-process", "extent", "warmup", "frames", "deadline", "shadow-scene", "foreign-purpose"):
            changed, document = copy.deepcopy(packet), copy.deepcopy(original)
            rows = document["captures"]
            if defect == "early-timing": rows[0], rows[8] = rows[8], rows[0]
            elif defect == "missing-process": rows.pop()
            elif defect == "extent": rows[8]["extent"] = [640, 480]
            elif defect == "warmup": rows[8]["warmup"] = 119
            elif defect == "frames": rows[8]["frames"] = 119
            elif defect == "deadline": rows[8]["deadline_seconds"] = 181
            elif defect == "shadow-scene": rows[8]["scene"] = "shadow-boundary"
            else: document["purpose"] = "sdvk011-viewmodel"
            path = self.root / (defect + ".json")
            exclusive(path, document)
            changed["workload_registration"] = pin(path)
            changed["files"].append(pin(path))
            with self.subTest(defect=defect), self.assertRaises((Stop, ValueError)):
                definition(changed)
        changed = copy.deepcopy(packet)
        changed["stages"][8]["expected_argv"].remove("-sdvkobservegpu")
        with self.assertRaises(Stop): validate(changed, check_files=True)

    def test_shadow_on_rayquery_and_quality_changes_are_rejected_before_capture(self):
        packet, _ = self.prepared()
        run = frozen_oracle(packet["oracle_source_root"])
        real_scene = run.prepared_scene
        # Complete the read-only Git/source regeneration before prohibiting
        # Popen. The guard below then covers only pure admission, not Git.
        verified = {scene: real_scene(packet["prepared"], scene) for scene in scaling.SCENES}
        for key, value in (("gl_light_shadows", 2), ("vk_rayquery", True), ("gl_texture_filter", 4)):
            def altered(*args):
                root, manifest, recipe = verified[args[1]]
                recipe = copy.deepcopy(recipe)
                recipe["native"]["settings"][key] = value
                return root, manifest, recipe
            with self.subTest(key=key), patch.object(run, "prepared_scene", side_effect=altered), \
                 patch.object(subprocess, "Popen", side_effect=AssertionError("No renderer in admission")) as child:
                with self.assertRaises(ValueError): scaling.validate_recipes(packet, run)
                child.assert_not_called()


def state_raw(scene):
    census = ("spot_lights", "subtractive_lights", "additive_lights", "actor_light_queries", "actor_light_candidates",
              "actor_light_selected", "actor_light_filtered", "actor_light_duplicates", "actor_light_traces",
              "light_wall_considered", "light_wall_rendered", "light_flat_considered", "light_flat_rendered",
              "walls", "flats", "sprites", "decals", "portals", "vertices")
    frame = dict.fromkeys(census, 1)
    frame.update(authored_lights=scaling.COUNTS[scene], active_lights=scaling.COUNTS[scene],
        settings={"gl_light_shadows": 0, "vk_rayquery": False, "gl_levelmesh": False},
        shadow_candidates=0, shadow_selected=0, shadow_dropped=0)
    resource = dict(light_uploads=dict(available=True, records_used=16, failed=0,
        index_capacity_failures=0, data_capacity_failures=0),
        descriptor_capacity=1024, descriptor_current=32, descriptor_high_water=32, descriptor_failures=0)
    return dict(mode="state", records=[dict(kind="frame", data=frame), dict(kind="resource", data=resource)])


class ShadowoffEvidenceTests(fixtures.TempCase):
    def inputs(self):
        specs = scaling.capture_specs({scene: "a" * 64 for scene in scaling.SCENES})
        stages = [dict(name=s["name"], capture={**s, "out": str(self.root / s["name"])}) for s in specs]
        source = {"commit": "b" * 40}
        build = dict(commit=source["commit"], working_tree="clean", device="CPU_CONSTRUCTED_PHYSICAL_ID_NOT_EXECUTED",
                     vulkan=dict(available=True, device_type=2, vendor_id=4318, device_id=8583))
        result = dict(build=build, executable={"sha256": "c" * 64}, reproduction={"iwad_sha256": "d" * 64},
                      loaded_packages=[dict(path="vkdoom.pk3", sha256="e" * 64, bytes=1, lumps=1)])
        packet = dict(kind="registered-workload", source=source, packet_sha256="f" * 64,
                      native_device={"device_type": 2, "vendor_id": 4318, "device_id": 8583}, stages=stages)
        registration = self.root / "CPU-evidence-registration.json"
        exclusive(registration, {"purpose": scaling.PURPOSE, "captures": specs})
        packet["workload_registration"] = pin(registration)
        raws = {}
        for stage in stages:
            path = Path(stage["capture"]["out"])
            path.mkdir()
            current = copy.deepcopy(result)
            capture = stage["capture"]
            current.update(scene=capture["scene"], mode=capture["mode"])
            current["reproduction"].update(scene=capture["scene"], recipe_sha256=capture["recipe_sha256"],
                extent=list(scaling.EXTENT), warmup_frames=120, frames=capture["frames"],
                gpu_timestamps_requested=capture["mode"] == "timing",
                clock="ordinary_engine_clock" if capture["mode"] == "timing" else "static_after_initialization",
                settings={"gl_light_shadows": 0, "vk_rayquery": False, "gl_levelmesh": False})
            exclusive(path / "run.json", current)
            exclusive(path / "request.json", dict(host={"CPU_ONLY": True}, environment={"CPU_ONLY": True}))
            raws[str(path)] = state_raw(stage["capture"]["scene"])
        run = types.SimpleNamespace(read_json=read_json,
            validate_run=lambda path: (path, read_json(path / "run.json"), raws[str(path)], {}),
            compare_runs=Mock(return_value={"status": "PASS"}), summarize_runs=Mock(return_value={"status": "DESCRIPTIVE"}))
        return packet, run, raws

    def fenced_states(self, packet, raws):
        states = []
        for index, stage in enumerate(packet["stages"][:8]):
            path = Path(stage["capture"]["out"])
            native = path / "native.renderer.json"
            image = path / "native.png"
            exclusive(native, raws[str(path)])
            # No image decoding occurs at this boundary. The independent parent
            # comparison already checked decoded RGB before the stage fence.
            exclusive(image, b"CPU-only artifact", raw=True)
            run_path = path / "run.json"
            manifest = read_json(run_path)
            manifest["artifacts"] = {
                item.name: {"path": item.name, "bytes": item.stat().st_size, "sha256": pin(item)["sha256"]}
                for item in (native, image)
            }
            run_path.write_text(json.dumps(manifest), encoding="utf-8")
            collected = {"run": pin(run_path), "native": pin(native)}
            comparison = None
            if index % 2:
                comparison = {"status": "PASS", "state_equal": True, "explicit_build_change": False,
                    "image": {"passed": True, "policy": {"metric": "exact-rgb8"},
                              "extent": scaling.EXTENT, "changed_pixels": 0}}
                for key, row in (("left", states[-1]["files"][0]), ("right", collected["run"])):
                    comparison[key] = {"path": row["path"], "bytes": row["size"], "sha256": row["sha256"]}
            reference = shadowoff_reference_stage(stage, collected)
            reference.update(comparison=comparison,
                             workload=scaling.state_workload(raws[str(path)], stage["capture"]["scene"]))
            states.append(reference)
        return states

    def test_before_timing_reuses_all_eight_exact_paired_state_gates(self):
        packet, run, raws = self.inputs()
        states = self.fenced_states(packet, raws)
        timing = packet["stages"][8]
        path = self.root / "shadowoff-fenced-references.json"
        receipt = shadowoff_reference_receipt(packet, timing, states)
        exclusive(path, receipt)
        with (
            patch("tools.physical_supervisor.registered.definition", return_value={"purpose": scaling.PURPOSE}),
            patch.object(subprocess, "Popen", side_effect=AssertionError("No renderer in state gate")) as child,
        ):
            result = before_capture(packet, timing, run, control=self.root, reference_pin=pin(path))
            self.assertEqual(result, receipt)
            self.assertEqual(set(result["state_workloads"]), set(scaling.SCENES))
            self.assertFalse(result["physical_gpu_qualified"])
            run.compare_runs.assert_not_called()
            child.assert_not_called()

    def test_first_timing_rejects_missing_or_changed_state_custody(self):
        packet, run, raws = self.inputs()
        states = self.fenced_states(packet, raws)
        timing = packet["stages"][8]
        for defect in ("missing", "misordered", "state-failed", "image-policy", "workload", "foreign-run"):
            changed = copy.deepcopy(states)
            if defect == "missing": changed.pop()
            elif defect == "misordered": changed.reverse()
            elif defect == "state-failed": changed[1]["comparison"]["state_equal"] = False
            elif defect == "image-policy": changed[1]["comparison"]["image"]["policy"]["metric"] = "rgb8-absolute"
            elif defect == "workload": changed[1]["workload"]["light_uploads"]["records_used"] += 1
            else: changed[1]["comparison"]["right"]["sha256"] = "1" * 64
            with self.subTest(defect=defect), self.assertRaises(Stop):
                shadowoff_reference_receipt(packet, timing, changed)
        path = self.root / "shadowoff-fenced-references.json"
        receipt = shadowoff_reference_receipt(packet, timing, states)
        exclusive(path, receipt)
        bound = pin(path)
        with patch("tools.physical_supervisor.registered.definition", return_value={"purpose": scaling.PURPOSE}):
            with self.assertRaisesRegex(Stop, "Missing parent-fenced"):
                before_capture(packet, timing, run, control=self.root)
            changed = dict(receipt, packet_sha256="0" * 64)
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(Stop, "Pinned file changed"):
                before_capture(packet, timing, run, control=self.root, reference_pin=bound)
            with self.assertRaisesRegex(Stop, "binding differs"):
                before_capture(packet, timing, run, control=self.root, reference_pin=pin(path))
            path.write_text(json.dumps(receipt), encoding="utf-8")
            for row in states[-1]["files"]:
                asset = Path(row["path"])
                original = asset.read_bytes()
                asset.write_bytes(original + b"changed")
                with self.subTest(asset=asset.name), self.assertRaisesRegex(Stop, "Pinned file changed"):
                    before_capture(packet, timing, run, control=self.root, reference_pin=pin(path))
                asset.write_bytes(original)

    def test_state_failure_counts_and_physical_identity_cannot_pass(self):
        packet, run, raws = self.inputs()
        stage = packet["stages"][0]
        self.assertFalse(after_capture(packet, stage, run)["performance_accepted"])
        original = copy.deepcopy(raws[stage["capture"]["out"]])
        for defect in ("shadow", "rayquery", "count", "upload-failure"):
            raw = copy.deepcopy(original)
            if defect == "shadow": raw["records"][0]["data"]["settings"]["gl_light_shadows"] = 2
            elif defect == "rayquery": raw["records"][0]["data"]["settings"]["vk_rayquery"] = True
            elif defect == "count": raw["records"][0]["data"]["active_lights"] = 0
            else: raw["records"][1]["data"]["light_uploads"]["failed"] = 1
            raws[stage["capture"]["out"]] = raw
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                scaling.validate_capture(packet, stage, run)
        raws[stage["capture"]["out"]] = original
        path = Path(packet["stages"][1]["capture"]["out"])
        wrong = read_json(path / "run.json"); wrong["build"]["vulkan"]["device_id"] += 1
        (path / "run.json").write_text(json.dumps(wrong))
        with self.assertRaisesRegex(ValueError, "physical device changed"):
            scaling.validate_capture(packet, packet["stages"][1], run)

    def test_actual_gpu_group_integrity_rejects_missing_multiplied_or_unresolved_samples(self):
        packet, run, raws = self.inputs()
        stage = packet["stages"][8]
        raw = dict(schema="sdvk-renderer-observation/v1", mode="timing", status="COLLECTED_PENDING_VALIDATION",
            error="", performance_accepted=False, requested_frames=120, observed_frames=120, dropped_records=0,
            records=[dict(kind="frame", frame=f, count=1, data={"cpu_render_view_ms": 0.5}) for f in range(1, 121)] +
                    [dict(kind="timing", frame=f, count=1, data=dict(clock="gpu", name="scene.immediate", milliseconds=0.25))
                     for f in range(1, 121)])
        def collect(value, target=stage):
            output = Path(target["capture"]["out"])
            (output / "native.renderer.json").write_text(json.dumps(value))
            raws[str(output)] = value
            return scaling.validate_capture(packet, target, run)
        self.assertEqual(collect(raw)["gpu_coverage"]["groups"]["scene.immediate"]["frames"], 120)
        for defect in ("missing", "multiplied", "unresolved", "cpu-frame"):
            changed = copy.deepcopy(raw)
            if defect == "missing": changed["records"].pop()
            elif defect == "multiplied": changed["records"].append(copy.deepcopy(changed["records"][-1]))
            elif defect == "unresolved": changed["records"].append(dict(kind="timing", frame=120, data={"available": False}))
            else: changed["records"].pop(0)
            with self.subTest(defect=defect), self.assertRaises(ValueError): collect(changed)
        receipt = collect(raw, packet["stages"][-1])
        self.assertFalse(receipt["performance_accepted"])
        self.assertEqual(set(receipt["summaries"]), set(scaling.SCENES))
        for call in run.summarize_runs.call_args_list:
            self.assertEqual(len(set(call.args[0])), 3)
