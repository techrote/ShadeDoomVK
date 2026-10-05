"""CPU-only fabricated-interface controls; no native/GPU/library evidence."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
RUNNER = HERE.with_name("run_freeze_view_acceptance.py")
if not RUNNER.is_file(): RUNNER = HERE.parents[1] / "run_freeze_view_acceptance.py"
spec = importlib.util.spec_from_file_location("pf020_view_uber_controls", RUNNER)
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
spec = importlib.util.spec_from_file_location("pf020_uber_inherited_controls", runner.ROOT / "tools/pf_oracle/tests/test_freeze_view_acceptance.py")
controls = importlib.util.module_from_spec(spec); spec.loader.exec_module(controls)


def uber_packet(variant="current"):
    data = controls.key_packet(variant)
    user, specialized = data["keyLookups"][0]["observation"], data["keyLookups"][1]["observation"]
    user["route"] = "specialized-worker-lookup"
    specialized["scene"] = None  # Matching real program may come from startup/worker creation.
    p = copy.deepcopy(user)
    p["route"] = "generalized-lookup"
    p["scene"].update(phase="startup", rootType="light-probe", face=0)
    program = {"kind": "shader", "route": "generic-find", "hit": True, "generalized": True,
               "actualGeneralizedKey": runner.generalized_identity(p["pipeline"]["shader"]),
               "shader": copy.deepcopy(p["pipeline"]["shader"]), "workerThread": False, "scene": None}
    data["keyLookups"] += [{"count": 1, "observation": p}, {"count": 1, "observation": program}]
    for route in ("vertex-library-lookup", "fragment-library-lookup", "specialized-worker-published", "fragment-library-worker-published"):
        o = copy.deepcopy(user); o.update(route=route, scene=None)
        data["keyLookups"].append({"count": 1, "observation": o})
    data["workerState"].update(scheduledPriority=1, completedWorkers=2, completedMainPublications=2)
    return data


class UberPolicyControls(unittest.TestCase):
    def test_default_configuration_is_byte_identical_and_uber_changes_exactly_one_startup_line(self):
        plain = runner.fixture.configuration().encode()
        self.assertEqual(runner.runtime_configuration(), plain)
        uber = runner.runtime_configuration("uber-library")
        self.assertEqual(uber.replace(b"\ngl_ubershaders=true\n", b"\ngl_ubershaders=false\n"), plain)
        self.assertTrue(runner.runtime_settings("uber-library")["gl_ubershaders"])
        self.assertIn("gl_ubershaders true;", runner.script(Path("C:/views"), "uber-library"))
        for policy in (None, "", "uber", "waived"):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "policy"):
                runner.runtime_settings(policy)

    def test_actual_capability_line_must_be_once_and_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); log = out / "startup.log"
            yes = "Vulkan capabilities: bindless=yes pipeline-library=yes shader-clip-distance=yes; ray-query-enabled=no\n"
            log.write_text(yes); self.assertIn("pipeline-library=yes", runner.pipeline_library_evidence(out))
            for text in ("", yes.replace("pipeline-library=yes", "pipeline-library=no"), yes + yes,
                         "echo pipeline-library=yes\n", yes.replace("pipeline-library=yes", "pipeline-library=yes-but-fake")):
                log.write_text(text)
                with self.subTest(text=text), self.assertRaisesRegex(ValueError, "capability"):
                    runner.pipeline_library_evidence(out)

    def prepare_service(self, root):
        (root / "build").mkdir()
        cfg = root / "build/config.ini"; cfg.write_text(runner.fixture.configuration())
        snapshot = {"inputs": {"config": runner.identity(cfg), "iwad": {"path": str(root / "Doom2.wad")}, "mod": {"path": str(root / "fixture.pk3")}},
                    "variants": {v: {"build": {"vkdoom.exe": {"path": str(root / v / "vkdoom.exe")}}} for v in ("current", "original-seams")}}
        with patch.object(runner, "snapshot", return_value=snapshot):
            receipt = runner.prepare(root / "fixture.json", root / "derivation.json", {v: root / v / "candidate.json" for v in snapshot["variants"]},
                                     root / "layers", root / "build/packet", "core", pipeline_policy="uber-library")
        return receipt, snapshot

    def test_preregistration_changes_startup_config_and_rejects_policy_or_config_tampering_before_popen(self):
        for mutation in ("policy", "child-policy", "settings", "config", "script"):
            with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
                receipt, snapshot = self.prepare_service(Path(temporary))
                self.assertEqual(receipt["pipelinePolicy"], "uber-library")
                first = receipt["children"][0]; out = Path(first["directory"])
                self.assertEqual((out / "fixture-live.ini").read_bytes(), runner.runtime_configuration("uber-library"))
                if mutation == "policy": receipt["pipelinePolicy"] = "specialized"
                elif mutation == "child-policy": first["pipelinePolicy"] = "specialized"
                elif mutation == "settings": receipt["requestedSettings"]["gl_ubershaders"] = False
                elif mutation == "config": (out / "fixture-live.ini").write_bytes(runner.runtime_configuration())
                else: (out / "execute.cfg").write_text(runner.script(out))
                with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner.subprocess, "Popen") as native:
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError): runner.launch(receipt)
                    native.assert_not_called()

    def test_full_uber_packet_includes_startup_program_and_probe_generic_witnesses(self):
        for variant in ("current", "original-seams"):
            result = runner.key_evidence(uber_packet(variant), variant, "uber-library")
            self.assertTrue(result["generalizedExecuted"])
            self.assertGreater(result["uberLibraryWitnesses"]["cacheFamilies"], 0)
            self.assertFalse(result["generalizedAccepted"])

    def test_specialized_only_and_missing_each_library_or_publication_witness_fail(self):
        with self.assertRaisesRegex(ValueError, "ready main user"):
            runner.key_evidence(controls.key_packet(), "current", "uber-library")
        for route in ("generalized-lookup", "vertex-library-lookup", "fragment-library-lookup",
                      "specialized-worker-published", "fragment-library-worker-published"):
            data = uber_packet()
            data["keyLookups"] = [r for r in data["keyLookups"] if r["observation"].get("route") != route]
            with self.subTest(route=route), self.assertRaises(ValueError): runner.key_evidence(data, "current", "uber-library")

    def test_pending_failed_incomplete_or_zero_worker_accounting_fails(self):
        for fields in ({"queued": 1}, {"active": 1}, {"pendingMainPublications": 1}, {"failed": 1},
                       {"completedWorkers": 1}, {"completedMainPublications": 0}, {"completedMainPublications": 1},
                       {"scheduledPrecache": 0, "completedWorkers": 1}, {"scheduledPriority": 0, "completedWorkers": 1},
                       {"scheduledPrecache": 0, "scheduledPriority": 0, "completedWorkers": 0}):
            data = uber_packet(); data["workerState"].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError): runner.key_evidence(data, "current", "uber-library")

    def test_source_generalized_integer_is_exact_bounded_and_excludes_texture_fog_flags(self):
        data = uber_packet(); shader = data["keyLookups"][4]["observation"]
        expected = shader["actualGeneralizedKey"]
        shader["shader"].update(TextureMode=7, FogAfterLights=1, LightMode=3)
        self.assertEqual(runner.generalized_identity(shader["shader"]), expected)
        runner.key_evidence(data, "current", "uber-library")
        for value in (expected + 1, -1, 1 << 64, True):
            broken = copy.deepcopy(data); broken["keyLookups"][4]["observation"]["actualGeneralizedKey"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): runner.key_evidence(broken, "current", "uber-library")
        source = copy.deepcopy(shader["shader"]); source.update(SpecialEffect=-1, VertexFormat=257)
        self.assertEqual(runner.generalized_identity(source), (12 << 32) | (255 << 48) | (1 << 56))

    def test_unrelated_specialized_or_generic_program_cannot_satisfy_ready_pipeline(self):
        for index in (1, 4):
            data = uber_packet(); o = data["keyLookups"][index]["observation"]
            o["shader"]["EffectState"] += 1
            if o["generalized"]: o["actualGeneralizedKey"] = runner.generalized_identity(o["shader"])
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "matching|Matching"):
                runner.key_evidence(data, "current", "uber-library")

    def test_whole_process_identity_ignores_schedule_but_preserves_family_key_and_pass(self):
        rows = uber_packet()["keyLookups"]; wanted = runner.cache_family_identity(rows)
        altered = copy.deepcopy(rows)
        for row in altered:
            row["count"] = 100; o = row["observation"]
            o.update(hit=False, ready=False, workerThread=True, scene=None)
            if o.get("route") == "specialized-worker-published": o["route"] = "specialized-worker-lookup"
            if o.get("route") == "fragment-library-worker-published": o["route"] = "fragment-library-precompile-lookup"
        self.assertEqual(runner.cache_family_identity(altered), wanted)
        # Readiness is a separate required gate: these identities alone cannot pass it.
        invalid = uber_packet(); invalid["keyLookups"] = altered
        with self.assertRaises(ValueError): runner.key_evidence(invalid, "current", "uber-library")
        for mutation in ("family", "key", "pass", "unknown-route"):
            changed = copy.deepcopy(rows); o = changed[5]["observation"]
            if mutation == "family": o["route"] = "generalized-lookup"
            elif mutation == "key": o["pipeline"]["CullMode"] += 1
            elif mutation == "pass": o["pass"]["Samples"] += 1
            else: o["route"] = "invented-ready"
            if mutation == "unknown-route":
                with self.assertRaises(ValueError): runner.cache_family_identity(changed)
            else: self.assertNotEqual(runner.cache_family_identity(changed), wanted)

    def test_uber_pair_keeps_exact_tics_producer_state_images_main_and_binary_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            service = controls.ViewAcceptanceControls()
            def packet(variant):
                raw = service.image_service(out, variant)
                main = runner.main_presentation_evidence(raw, out, variant)
                return {"pipelinePolicy": "uber-library", "state": {"scene": runner.scene_evidence(controls.scene_packet(variant), variant),
                        "keys": runner.key_evidence(uber_packet(variant), variant, "uber-library"), "rawImages": runner.image_evidence(raw, out, variant),
                        "mainPresentation": main}, "presentation": main, "nativeDevice": "same", "settings": "same"}
            a, b = packet("current"), packet("original-seams")
            self.assertEqual(runner.paired_compare(a, b)["status"], "PAIRED_EXACT_MATCH")
            for mutation in ("tic", "camera", "main", "binary", "worker-null-key", "policy"):
                changed = copy.deepcopy(b)
                if mutation == "tic": changed["state"]["scene"]["records"][0]["tic"] += 1
                elif mutation == "camera": changed["state"]["rawImages"]["camera-PFVCAM-demanded"]["metadata"]["scene"]["completedView"]["position"][0] += 1
                elif mutation == "main": changed["presentation"]["decodedRgbSha256"] = "changed"
                elif mutation == "binary": changed["state"]["keys"]["keys"][2]["observation"]["actualSourceChecksum"] = "5-" + "f" * 40 + "-2222"
                elif mutation == "worker-null-key": changed["state"]["keys"]["keys"][-1]["observation"]["pipeline"]["CullMode"] += 1
                else: changed["pipelinePolicy"] = "specialized"
                with self.subTest(mutation=mutation), self.assertRaises(ValueError): runner.paired_compare(a, changed)


if __name__ == "__main__": unittest.main()
