"""CPU-hostable SDVK-008 controls: no renderer or Vulkan process is launched."""
from argparse import Namespace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import sdvk008_physical as physical
from tools.renderer_oracle.common import EvidenceError, canonical, read_json


def fixture_contract(*, complete=True):
    return SimpleNamespace(TIMING_VARIANTS={key: "sdvk008-" + key.lower() for key in physical.WORK_CEILINGS},
        CORRECTNESS_PAIRS=[{"id": "single", "off": "sdvk008-s0", "on": "sdvk008-sm", "oracle": "effect"}],
        REQUIRED_GATES=["direction"], AVAILABLE_GATES=["direction"] if complete else [],
        MISSING_GATES=[] if complete else ["direction"])


def fixture_catalog(contract):
    rows = []
    for variant, scene_id in contract.TIMING_VARIANTS.items():
        rows.append({"id": scene_id, "required_state_channels": ["sprite-basis", "sprite-relief", "material"],
            "native": {"settings": {"gl_sprite_relief_depth": 0 if variant.endswith("0") else 0.012,
                "gl_sprite_relief_quality": 1 if variant == "SL" else 3 if variant in ("SH", "MH", "GH") else 2},
                "map": "SDVTEST", "camera": {}, "seed": 1, "clock": {},
                "console_queries": ["gl_sprite_relief_depth", "gl_sprite_relief_quality"]}})
    return {"scenes": rows}


def summary(value=1.0, *, cpu_count=120, gpu_count=120):
    cpu = physical.benchmark.distribution([value] * cpu_count, minimum_samples=1)
    gpu = physical.benchmark.distribution([value] * gpu_count, minimum_samples=1)
    data = {"raw_cpu_render_view_ms": [value] * cpu_count, "cpu_render_view": cpu,
            "gpu_groups": {"opaque": {"samples_ms": [value] * gpu_count, "distribution": gpu}}}
    return {"independent_processes": 3, "runs": [{"summary": data} for _ in range(3)]}


class StatisticalRules(unittest.TestCase):
    def test_type_seven_percentiles(self):
        values = [float(i) for i in range(120)]
        self.assertAlmostEqual(physical.benchmark.percentile(values, 95), 113.05)
        self.assertAlmostEqual(physical.benchmark.percentile(values, 99), 117.81)

    def test_detection_limit_is_strict_and_is_not_zero_cost(self):
        below = physical.matched_effect([1, 1, 1], [1.01, 1.01, 1.01])
        self.assertEqual(below["status"], "BELOW_DETECTION_LIMIT")
        self.assertFalse(below["zero_cost_claim"])
        at_threshold = physical.matched_effect([0, 0, 0], [0.05, 0.05, 0.05])
        self.assertEqual(at_threshold["status"], "BELOW_DETECTION_LIMIT")
        above = physical.matched_effect([1, 1, 1], [1.1, 1.2, 1.1])
        self.assertEqual(above["status"], "DETECTABLE_DIRECTIONAL_EFFECT")
        self.assertEqual(above["same_sign_repetitions"], 3)

    def test_off_variability_gate_retains_all_repetitions(self):
        value = physical.matched_effect([1, 1, 1.06], [1.2, 1.2, 1.26])
        self.assertEqual(value["status"], "INCONCLUSIVE")
        self.assertEqual(value["off_process_medians_ms"], [1, 1, 1.06])
        self.assertEqual(physical.matched_effect([1, 1, 1], [1.2] * 3, anomaly=True)["status"], "INCONCLUSIVE")

    def test_mad_increases_detection_threshold(self):
        value = physical.matched_effect([10, 10.04, 9.96], [10.06, 10.10, 10.02])
        self.assertAlmostEqual(value["detection_threshold_ms"], 0.08)
        self.assertEqual(value["status"], "BELOW_DETECTION_LIMIT")

    def test_nonfinite_negative_and_missing_processes_rejected(self):
        for off, on in (([1, 1], [1, 1]), ([1, 1, float("nan")], [1] * 3), ([-1] * 3, [1] * 3)):
            with self.assertRaises(EvidenceError):
                physical.matched_effect(off, on)

    def test_exact_cpu_gpu_sample_limits(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        result = physical.timing_analysis(data)
        self.assertFalse(result["nested_gpu_groups_summed"])
        self.assertEqual(result["comparisons"]["SM"]["off"], "S0")
        for count in (119, 121):
            bad = dict(data, SM=summary(cpu_count=count))
            with self.assertRaisesRegex(EvidenceError, "120"):
                physical.timing_analysis(bad)
            bad = dict(data, SM=summary(gpu_count=count))
            incomplete = physical.timing_analysis(bad)
            self.assertEqual(incomplete["status"], "INCONCLUSIVE_GPU_SCENE_SCOPE")
            self.assertFalse(incomplete["gpu_scene_scope_complete"])
            self.assertEqual(incomplete["gpu_group_integrity"]["SM"][0]["incomplete_retained_groups"], ["opaque"])
            self.assertEqual(incomplete["comparisons"]["SM"]["groups"]["gpu:opaque"]["status"], "INCONCLUSIVE")

    def test_gpu_postprocess_or_other_spans_cannot_replace_scene_immediate(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        result = physical.timing_analysis(data)
        self.assertEqual(result["status"], "INCONCLUSIVE_GPU_SCENE_SCOPE")
        self.assertFalse(result["gpu_scene_scope_complete"])
        self.assertIn("gpu:opaque", result["comparisons"]["SM"]["groups"])
        self.assertIn("cpu_render_view_ms", result["comparisons"]["SM"]["groups"])
        self.assertFalse(result["performance_accepted"])

    def test_scene_scope_requires_complete_span_in_all_thirty_three_processes(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        for item in data.values():
            for process in item["runs"]:
                groups = process["summary"]["gpu_groups"]
                groups["scene.immediate"] = groups["opaque"]
                process["gpu_timing_integrity"] = {"status": "COMPLETE_GPU_SCENE_SCOPE",
                    "scene_immediate_complete": True, "all_retained_groups_complete": True}
        result = physical.timing_analysis(data)
        self.assertTrue(result["gpu_scene_scope_complete"])
        self.assertEqual(result["status"], "DESCRIPTIVE_GPU_SCENE_SCOPE_AVAILABLE")
        self.assertFalse(result["physical_gpu_qualified"])
        # Replace one independent process instead of mutating the shared
        # synthetic summary dictionary used by the other repetitions.
        data["PM"]["runs"][2] = summary()["runs"][0]
        result = physical.timing_analysis(data)
        self.assertFalse(result["gpu_scene_scope_complete"])
        self.assertEqual(result["status"], "INCONCLUSIVE_GPU_SCENE_SCOPE")

    def test_complete_scene_span_cannot_hide_incomplete_other_group(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        for item in data.values():
            for process in item["runs"]:
                process["summary"]["gpu_groups"]["scene.immediate"] = {
                    "samples_ms": [1] * 120, "distribution": physical.benchmark.distribution([1] * 120)}
        data["PM"]["runs"][2] = summary(gpu_count=119)["runs"][0]
        data["PM"]["runs"][2]["summary"]["gpu_groups"]["scene.immediate"] = {
            "samples_ms": [1] * 120, "distribution": physical.benchmark.distribution([1] * 120)}
        result = physical.timing_analysis(data)
        self.assertFalse(result["gpu_scene_scope_complete"])
        self.assertEqual(result["gpu_group_integrity"]["PM"][2]["incomplete_retained_groups"], ["opaque"])

    def test_one_hundred_twenty_values_without_raw_frame_attestation_are_inconclusive(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        for item in data.values():
            for process in item["runs"]:
                process["summary"]["gpu_groups"]["scene.immediate"] = {
                    "samples_ms": [1] * 120, "distribution": physical.benchmark.distribution([1] * 120)}
        self.assertEqual(physical.timing_analysis(data)["status"], "INCONCLUSIVE_GPU_SCENE_SCOPE")

    def test_raw_gpu_duplicate_and_missing_frame_do_not_cancel(self):
        raw = {"mode": "timing", "observed_frames": 120, "records": [
            {"kind": "timing", "frame": frame, "count": 1,
             "data": {"clock": "gpu", "name": "scene.immediate", "milliseconds": 1}}
            for frame in range(1, 121)]}
        with patch.object(physical, "read_json", return_value=raw), patch.object(physical, "pin", return_value={}):
            self.assertTrue(physical.timing_integrity("packet")["scene_immediate_complete"])
            raw["records"][60]["frame"] = 60  # 120 values: frame 60 twice, frame 61 absent.
            with self.assertRaisesRegex(EvidenceError, "duplicate raw per-frame"):
                physical.timing_integrity("packet")

    def test_raw_gpu_unresolved_batch_and_incomplete_other_group_fail(self):
        raw = {"mode": "timing", "observed_frames": 120, "records": [
            {"kind": "timing", "frame": frame, "count": 1,
             "data": {"clock": "gpu", "name": "scene.immediate", "milliseconds": 1}}
            for frame in range(1, 121)]}
        with patch.object(physical, "read_json", return_value=raw), patch.object(physical, "pin", return_value={}):
            raw["records"].append({"kind": "timing", "frame": 1, "count": 1, "data": {"available": False}})
            with self.assertRaisesRegex(EvidenceError, "Unresolved GPU"):
                physical.timing_integrity("packet")
            raw["records"][-1]["data"] = {"clock": "gpu", "name": "postprocess", "milliseconds": 1}
            with self.assertRaisesRegex(EvidenceError, "Incomplete or duplicate"):
                physical.timing_integrity("packet")
            raw["records"] = []
            self.assertEqual(physical.timing_integrity("packet")["status"], "INCONCLUSIVE_GPU_SCENE_SCOPE")

    def test_inconsistent_gpu_groups_not_fabricated(self):
        data = {key: summary() for key in physical.WORK_CEILINGS}
        data["SM"]["runs"][1] = {"summary": {"raw_cpu_render_view_ms": [1] * 120,
            "cpu_render_view": physical.benchmark.distribution([1] * 120), "gpu_groups": {}}}
        result = physical.timing_analysis(data)["comparisons"]["SM"]
        self.assertEqual(result["unavailable_or_inconsistent_groups"], ["gpu:opaque"])
        self.assertNotIn("gpu:opaque", result["groups"])


class FixtureAndIdentityRules(unittest.TestCase):
    def test_draw_witness_rejects_disabled_positive_fixture(self):
        raw = {"records": [{"kind": "sprite-relief", "data": {"material": "SDVEA0", "eligible_draw": True,
               "quality": 2, "depth": 0.012, "height_reads_max": 15}}]}
        recipe = {"native": {"relief_family": "single", "settings": {"gl_sprite_relief_depth": 0.012,
                                                                    "gl_sprite_relief_quality": 2}}}
        with patch.object(physical, "read_json", side_effect=[raw, recipe]):
            self.assertEqual(physical.relief_draw_witness("packet")["eligible_draws"], 1)
        raw["records"][0]["data"]["eligible_draw"] = False
        with patch.object(physical, "read_json", side_effect=[raw, recipe]):
            with self.assertRaisesRegex(EvidenceError, "eligible"):
                physical.relief_draw_witness("packet")

    def test_prelaunch_off_on_package_identity_required(self):
        data = {"scenes": [{"id": name, "native": {"pk3": name + ".pk3"}} for name in ("off", "on")],
                "files": {name + ".pk3": {"sha256": "a" * 64, "bytes": 3} for name in ("off", "on")}}
        pairs = [{"id": "single", "off": "off", "on": "on"}]
        physical.prepared_pair_continuity(data, pairs)
        data["files"]["on.pk3"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(EvidenceError, "package bytes differ"):
            physical.prepared_pair_continuity(data, pairs)

    def test_missing_gates_block_full_but_allow_explicit_partial(self):
        contract = fixture_contract(complete=False)
        catalog = fixture_catalog(contract)
        with self.assertRaisesRegex(EvidenceError, "Incomplete physical correctness"):
            physical.validate_fixtures(contract, catalog)
        self.assertEqual(len(physical.validate_fixtures(contract, catalog, correctness_only=True)), 11)

    def test_wrong_settings_and_missing_readbacks_rejected(self):
        contract = fixture_contract()
        catalog = fixture_catalog(contract)
        catalog["scenes"][0]["native"]["settings"]["gl_sprite_relief_depth"] = 0.012
        with self.assertRaisesRegex(EvidenceError, "controls"):
            physical.validate_fixtures(contract, catalog)
        catalog = fixture_catalog(contract)
        catalog["scenes"][0]["native"]["console_queries"] = []
        with self.assertRaisesRegex(EvidenceError, "read back"):
            physical.validate_fixtures(contract, catalog)

    def test_software_dirty_wrong_commit_and_wrong_device_rejected(self):
        build = {"backend": "vulkan", "working_tree": "clean", "commit": physical.IMPLEMENTATION_COMMIT,
                 "device": "test GPU", "vulkan": {"available": True, "device_type": 2}}
        physical.physical_build(build, commit=physical.IMPLEMENTATION_COMMIT, device_name="test GPU")
        for changed in (dict(build, vulkan={"available": True, "device_type": 4}),
                        dict(build, working_tree="modified"), dict(build, commit="a" * 40),
                        dict(build, device="wrong GPU")):
            with self.assertRaises(EvidenceError):
                physical.physical_build(changed, commit=physical.IMPLEMENTATION_COMMIT, device_name="test GPU")

    def test_prelaunch_vulkan_summary_refuses_software_device(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vulkan-summary.txt"
            text = "GPU0:\n deviceName = test GPU\n deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU\n vendorID = 0x10de\n deviceID = 0x2187\n driverVersion = 1.2.3\n"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(physical.vulkan_preflight(path, "test GPU")["device_id"], 0x2187)
            path.write_text(text.replace("DISCRETE_GPU", "CPU"), encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "software"):
                physical.vulkan_preflight(path, "test GPU")

    def test_rgb_difference_does_not_claim_direction_or_silhouette(self):
        with patch.object(physical.images, "decode", side_effect=[((1, 1), b"\x00\x00\x00"), ((1, 1), b"\x01\x00\x00")]):
            result = physical.image_pair("off", "on", "effect")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["changed_pixels"], 1)
        self.assertFalse(result["direction_qualified"])
        self.assertFalse(result["alpha_silhouette_qualified"])
        with patch.object(physical.images, "decode", return_value=((1, 1), b"\x00\x00\x00")):
            self.assertEqual(physical.image_pair("off", "on", "effect")["status"], "FAIL")
            self.assertEqual(physical.image_pair("off", "on", "silhouette")["status"], "DESCRIPTIVE")

    def test_alpha_background_mask_rejects_escape_and_missing_sprite(self):
        off = ((2, 1), b"\x01\x00\x00\x00\x00\x00")
        on = ((2, 1), b"\x02\x00\x00\x00\x00\x00")
        escaped = ((2, 1), b"\x02\x00\x00\x01\x00\x00")
        background = ((2, 1), bytes(6))
        with patch.object(physical.images, "decode", side_effect=[off, on, background]):
            result = physical.image_pair("off", "on", "silhouette", background="bg")
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["alpha_silhouette_qualified"])
        with patch.object(physical.images, "decode", side_effect=[off, escaped, background]):
            result = physical.image_pair("off", "on", "silhouette", background="bg")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["silhouette_mask_mismatch_pixels"], 1)
        with patch.object(physical.images, "decode", side_effect=[background] * 3):
            self.assertEqual(physical.image_pair("off", "on", "silhouette", background="bg")["status"], "FAIL")

    def test_flip_witness_requires_actual_material_signed_uv_state(self):
        raw = {"records": [{"kind": "sprite-basis", "data": {"material": "SDVEA0", "surface": {"uv_mirror_x": True}}}]}
        self.assertEqual(physical.flip_witness(raw, raw, "x")["on_emitted_draws"], 1)
        with self.assertRaisesRegex(EvidenceError, "signed-UV"):
            physical.flip_witness(raw, raw, "y")


class CampaignControls(unittest.TestCase):
    def execute(self, root, *, partial=False, incomplete=False, compare_status="PASS", crash=False, software=False,
                image_status="PASS"):
        exe, iwad = root / "engine.exe", root / "iwad.wad"
        exe.write_bytes(b"not executed")
        iwad.write_bytes(b"private fixture")
        (root / "vkdoom.pk3").write_bytes(b"runtime fixture")
        vulkan_summary = root / "vulkan-summary.txt"
        vulkan_summary.write_text("GPU0:\n deviceName = test GPU\n deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU\n vendorID = 0x10de\n deviceID = 0x2187\n driverVersion = 1.2.3\n", encoding="utf-8")
        args = Namespace(exe=exe, iwad=iwad, out=root / "campaign", timeout=600,
                         execute=True, correctness_only=partial, device_name="test GPU", vulkan_summary=vulkan_summary)
        contract = fixture_contract(complete=not incomplete)
        if software:
            args.software_fixture_control = True
            args.expected_commit = "b" * 40
            args.device_name = "llvmpipe (host-only-test)"
            args.iwad_license = root / "license.txt"
            args.iwad_license.write_text("test notice", encoding="utf-8")
            vulkan_summary.write_text("GPU0:\n deviceName = llvmpipe (host-only-test)\n deviceType = PHYSICAL_DEVICE_TYPE_CPU\n driverName = llvmpipe\n driverID = DRIVER_ID_MESA_LLVMPIPE\n vendorID = 0x10de\n deviceID = 0x2187\n driverVersion = 1.2.3\n", encoding="utf-8")
            contract.CORRECTNESS_PAIRS[0]["id"] = "single-m"
        captures = []

        def capture(ns):
            ns.out.mkdir(parents=True)
            (ns.out / "retained.log").write_text("attempt retained", encoding="utf-8")
            (ns.out / "request.json").write_bytes(canonical({"host": {"test": True}, "environment": {}}))
            captures.append(ns)
            if crash:
                raise EvidenceError("simulated crash")
            return {"build": {"backend": "vulkan", "working_tree": "clean", "commit": args.expected_commit if software else physical.IMPLEMENTATION_COMMIT,
                    "device": args.device_name, "vulkan": {"available": True, "device_type": 4 if software else 2,
                    "vendor_id": 0x10de, "device_id": 0x2187}},
                    "executable": {"sha256": "a" * 64}, "loaded_packages": []}

        with patch.object(physical, "fixture_contract", return_value=contract), \
             patch.object(physical.prepare, "load_catalog", return_value=fixture_catalog(contract)), \
             patch.object(physical.prepare, "prepare", return_value={"status": "PREPARED"}), \
             patch.object(physical, "prepared_pair_continuity"), \
             patch.object(physical.run, "capture", side_effect=capture), \
             patch.object(physical.run, "compare_runs", return_value={"status": compare_status}), \
             patch.object(physical, "controlled_pair"), \
             patch.object(physical, "relief_draw_witness", return_value={}), \
             patch.object(physical, "timing_integrity", return_value={"status": "INCONCLUSIVE_GPU_SCENE_SCOPE"}), \
             patch.object(physical, "image_pair", return_value={"status": image_status}), \
             patch.object(physical.run, "summarize_runs", return_value=summary()):
            try:
                result = physical.campaign(args)
            except EvidenceError:
                result = read_json(args.out / ("sdvk008-software-fixture-control.json" if software else "sdvk008-physical-campaign.json"))
        return args, captures, result

    def test_preregistered_serial_order_and_exact_command_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            args, captures, result = self.execute(Path(directory))
            physical.verify_checksums(args.out)
        timings = [ns for ns in captures if ns.mode == "timing"]
        self.assertEqual(len(timings), 33)
        self.assertEqual([ns.scene for ns in timings], ["sdvk008-" + variant.lower()
                         for order in physical.TIMING_ORDER for variant in order])
        self.assertTrue(all(ns.frames == ns.warmup == 120 and ns.gpu and ns.extent == "1904x1001" for ns in timings))
        self.assertTrue(all(ns.frames == 1 and not ns.gpu for ns in captures if ns.mode == "state"))
        self.assertEqual(result["status"], "COLLECTED_PENDING_REVIEW")
        self.assertFalse(result["physical_gpu_qualified"])

    def test_partial_never_launches_timing_and_records_missing_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            _, captures, result = self.execute(Path(directory), partial=True, incomplete=True)
        self.assertTrue(captures)
        self.assertTrue(all(ns.mode == "state" for ns in captures))
        self.assertEqual(result["status"], "PARTIAL_CORRECTNESS_COLLECTED")
        self.assertEqual(result["missing_gates"], ["direction"])

    def test_full_incomplete_fixture_stops_before_any_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            _, captures, result = self.execute(Path(directory), incomplete=True)
        self.assertEqual(captures, [])
        self.assertEqual(result["status"], "FAIL")

    def test_software_smoke_is_distinct_and_cannot_claim_physical_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            args, captures, result = self.execute(Path(directory), partial=True, incomplete=True, software=True)
            self.assertTrue((args.out / "sdvk008-software-fixture-control.json").is_file())
            self.assertFalse((args.out / "sdvk008-physical-campaign.json").exists())
        self.assertEqual(result["status"], "SOFTWARE_FIXTURE_CONTROL_COLLECTED")
        self.assertTrue(result["software_vulkan_evidence_collected"])
        self.assertFalse(result["physical_gpu_evidence_collected"])
        self.assertFalse(result["physical_gpu_qualified"])
        self.assertTrue(all(ns.mode == "state" and ns.extent == "640x480" and not ns.gpu for ns in captures))
        self.assertEqual(len(captures), 4)
        self.assertTrue(all(ns.expected_commit == "b" * 40 and ns.require_clean for ns in captures))

    def test_inconclusive_software_witness_fails_and_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            args, captures, result = self.execute(Path(directory), partial=True, incomplete=True, software=True,
                                                   image_status="INCONCLUSIVE")
            physical.verify_checksums(args.out)
            self.assertTrue(list(args.out.rglob("retained.log")))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["incomplete_image_pairs"], ["single-m"])
        self.assertEqual([row["status"] for row in result["image_pairs"]["single-m"]], ["INCONCLUSIVE"] * 2)
        self.assertFalse(result["software_vulkan_evidence_collected"])
        self.assertFalse(result["physical_gpu_evidence_collected"])
        self.assertTrue(all(ns.mode == "state" for ns in captures))

    def test_physical_partial_inconclusive_witness_remains_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            _, captures, result = self.execute(Path(directory), partial=True, incomplete=True,
                                               image_status="INCONCLUSIVE")
        self.assertEqual(result["status"], "PARTIAL_CORRECTNESS_COLLECTED")
        self.assertEqual(result["incomplete_image_pairs"], ["single"])
        self.assertFalse(result["physical_gpu_qualified"])
        self.assertTrue(all(ns.mode == "state" for ns in captures))

    def test_failure_is_retained_without_retry_or_timing(self):
        for crash in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                args, captures, result = self.execute(Path(directory), compare_status="FAIL", crash=crash)
                self.assertEqual(len(captures), 1 if crash else 2)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["automatic_retries"], 0)
                self.assertTrue(list(args.out.rglob("retained.log")))
                physical.verify_checksums(args.out)

    def test_checksums_detect_tampering_and_added_files(self):
        with tempfile.TemporaryDirectory() as directory:
            args, _, _ = self.execute(Path(directory), partial=True)
            log = next(args.out.rglob("retained.log"))
            original = log.read_bytes()
            log.write_bytes(b"tampered")
            with self.assertRaisesRegex(EvidenceError, "identity changed"):
                physical.verify_checksums(args.out)
            log.write_bytes(original)
            (args.out / "unregistered.bin").write_bytes(b"added")
            with self.assertRaisesRegex(EvidenceError, "inventory changed"):
                physical.verify_checksums(args.out)

    def test_explicit_authorization_required_and_fresh_output_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = Namespace(execute=False, out=root / "output")
            with self.assertRaisesRegex(EvidenceError, "explicit --execute"):
                physical.campaign(args)
            self.assertFalse(args.out.exists())
            args.execute = True
            args.out.mkdir()
            with self.assertRaises(FileExistsError):
                physical.campaign(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)

