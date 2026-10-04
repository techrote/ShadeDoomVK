"""Runner failure/identity tests with authored data and fake children; no launch."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

PATH = Path(__file__).resolve().parents[1]/"run_pbr_probe_runtime.py"
SPEC = importlib.util.spec_from_file_location("pf113_runner_tests", PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ProbeRunner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(runner.subprocess, "Popen", side_effect=AssertionError("CPU tests must never launch a child")).start()

    def manifest(self):
        inputs = runner.inputs
        mod = self.out/"fixture.pk3"
        files = inputs.members()
        mod.write_bytes(inputs.archive_bytes(files))
        cfg, script = self.out/"input.ini", self.out/"input.cfg"
        cfg.write_text(inputs.configuration())
        script.write_text(inputs.capture_script(self.out/"native", self.out/"presentation.png"))
        exe, iwad = self.out/"candidate.exe", self.out/"doom2.wad"
        case = {"id": "hardware-truecolour-nearest", **inputs.SETTINGS, "extent": [640, 480], "executed": False,
                "config": str(cfg), "captureScript": str(script), "earlyPrefix": str(self.out/"early"),
                "nativePrefix": str(self.out/"native"), "presentationCapture": str(self.out/"presentation.png")}
        case["command"] = inputs.command(exe, iwad, mod, cfg, script, self.out/"early")
        return {"schema": inputs.SCHEMA, "status": "prepared-unaccepted", "gpuExecuted": False,
                "iwad": {"path": str(iwad), "sha256": inputs.IWAD_SHA256, "copiedIntoMod": False},
                "mod": {"path": str(mod), "members": {name: {"sha256": inputs.sha(raw), "bytes": len(raw)} for name, raw in files.items()}},
                "scenarios": [case], "scene": {"map": "PF113", "probes": inputs.PROBES, "probeThingType": 9892,
                    "prebakedProbeOrLightmapLumps": False, "sectorTarget": {"sector": 0, "origin": [0, 0, 64], "expectedOrdinal": 1},
                    "sideTarget": {"side": 2, "origin": [128, 0, 64], "expectedOrdinal": 1}, "materialNames": ["PF113W", "PF113FL"]}}, exe

    def test_authored_case_positive_and_mutations(self):
        manifest, exe = self.manifest()
        self.assertEqual(runner.checked_case(manifest, "hardware-truecolour-nearest", exe), manifest["scenarios"][0])
        for key, value in (("rendererMode", 0), ("lightProbes", False), ("levelMesh", True), ("uberShaders", True), ("lightShadows", 2), ("executed", True)):
            bad = copy.deepcopy(manifest)
            bad["scenarios"][0][key] = value
            with self.assertRaises(ValueError, msg=key):
                runner.checked_case(bad, "hardware-truecolour-nearest", exe)

    def test_unknown_scene_or_changed_argv_rejected(self):
        manifest, exe = self.manifest()
        for mutation in (lambda m: m["scene"].update(probes=[[0, 0, 0]]),
                         lambda m: m["scene"].update(prebakedProbeOrLightmapLumps=True),
                         lambda m: m["scenarios"][0]["command"].extend(["+quit"]),
                         lambda m: m.update(gpuExecuted=True)):
            bad = copy.deepcopy(manifest)
            mutation(bad)
            with self.assertRaises(ValueError):
                runner.checked_case(bad, "hardware-truecolour-nearest", exe)

    def test_changed_mod_member_or_duplicate_rejected(self):
        manifest, exe = self.manifest()
        files = runner.inputs.members()
        files["GLDEFS"] = b"material texture PF113W {}\n"
        Path(manifest["mod"]["path"]).write_bytes(runner.inputs.archive_bytes(files))
        with self.assertRaisesRegex(ValueError, "member differs"):
            runner.checked_case(manifest, "hardware-truecolour-nearest", exe)

    def test_exact_rebound_prefixes_and_command_order(self):
        manifest, _ = self.manifest()
        case = manifest["scenarios"][0]
        actual = runner.execution_command(case, self.out/"fresh")
        self.assertEqual(len(actual), len(case["command"]))
        for option, name in (("-config", "fixture-live.ini"), ("-pf113observe", "early"), ("+exec", "execute.cfg")):
            self.assertEqual(actual[actual.index(option)+1], str(self.out/"fresh"/name))
        self.assertLess(actual.index("-pf113observe"), actual.index("+map"))
        self.assertIn("-noautoexec", actual)
        self.assertEqual(runner.execution_script(self.out), runner.inputs.capture_script(self.out/"native", self.out/"presentation.png"))

    def test_missing_or_other_candidate_cannot_prepare(self):
        with self.assertRaisesRegex(ValueError, "requires.*candidate"):
            runner.candidate_identity(None, self.out/"candidate.exe")
        path = self.out/"candidate.json"
        path.write_text(json.dumps({"schema": "pf110-native-candidate/v1", "native_build": {"exit": 0}}))
        with self.assertRaisesRegex(ValueError, "Candidate receipt"):
            runner.candidate_identity(path, self.out/"candidate.exe")

    def test_native_candidate_dirty_compile_or_preaccepted_rejected(self):
        good = {"schema": "pf113-native-candidate/v1", "native_build": {"exit": 0},
                "source_closure_unchanged_during_engine_compile": True, "accepted": False, "gpu_executed": False}
        path = self.out/"candidate.json"
        for key, value in (("source_closure_unchanged_during_engine_compile", False), ("accepted", True), ("gpu_executed", True)):
            bad = {**good, key: value}
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "Candidate receipt"):
                runner.candidate_identity(path, self.out/"candidate.exe")

    def test_staged_inventory_matches_attestation_and_extra_dll_fails(self):
        names = sorted(runner.PACKAGES) + ["candidate.exe", "candidate.pdb", "ZMusic.dll"]
        for name in names:
            (self.out/name).write_bytes(name.encode())
        exe = self.out/"candidate.exe"
        inventory = runner.base.build_inventory(exe)
        candidate = {"verifiedArtifacts": [{**row, "buildSource": {"path": "authored source counterpart"}} for row in inventory.values()]}
        runner.require_staged_inventory(inventory, candidate, exe)
        (self.out/"unlisted.dll").write_bytes(b"unattested runtime library")
        with self.assertRaisesRegex(ValueError, "complete eight-artifact"):
            runner.require_staged_inventory(runner.base.build_inventory(exe), candidate, exe)
        changed = copy.deepcopy(inventory)
        changed["ZMusic.dll"]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "complete eight-artifact"):
            runner.require_staged_inventory(changed, candidate, exe)

    def test_exact_seven_package_closure(self):
        build = {}
        for name in runner.PACKAGES:
            path = self.out/name
            path.write_bytes(name.encode())
            build[name] = runner.identity(path)
        inputs = {}
        for name, filename in (("iwad", "doom2.wad"), ("mod", "synthetic.pk3")):
            path = self.out/filename
            path.write_bytes(filename.encode())
            inputs[name] = runner.identity(path)
        before = {"build": build, "inputs": inputs}
        paths = [Path(row["path"]) for row in build.values()] + [Path(row["path"]) for row in inputs.values()]
        def lines(selected):
            (self.out/"stdout.log").write_text("".join(f"adding {path}, 1 lumps\n" for path in selected))
        lines(paths)
        self.assertTrue(runner.package_evidence(self.out, before)["verified"])
        lines(paths[:-1])
        self.assertFalse(runner.package_evidence(self.out, before)["verified"])
        extra = self.out/"extras.wad"
        extra.write_bytes(b"unaccepted")
        lines(paths+[extra])
        self.assertFalse(runner.package_evidence(self.out, before)["verified"])
        lines(paths+paths[:1])
        self.assertFalse(runner.package_evidence(self.out, before)["verified"])

    @staticmethod
    def spv(nonuniform=True):
        words = [0x07230203, 0x10000, 0, 64, 0, 2<<16 | 17, 1]
        if nonuniform:
            words += [2<<16 | 17, 5301, 2<<16 | 17, 5307, 3<<16 | 71, 8, 5300, 1<<16 | 88]
        return struct.pack("<"+"I"*len(words), *words)

    def test_structural_spirv_and_nonuniform_failure(self):
        observed = runner.spirv(self.spv(), nonuniform=True)
        self.assertEqual(observed["nonuniformDecoratedIds"], [8])
        with self.assertRaisesRegex(ValueError, "NonUniform"):
            runner.spirv(self.spv(False), nonuniform=True)
        for bad in (b"bad", self.spv()[:-1], self.spv()[:20]+struct.pack("<I", 0)):
            with self.assertRaises(ValueError):
                runner.spirv(bad)

    def test_captured_view_and_sampler_are_application_metadata(self):
        view = {"basis": "captured-successful-vkCreateImageView-arguments", "type": 3, "baseMip": 0,
                "mips": 1, "baseLayer": 0, "layers": 6, "aspect": 1, "handle": 5, "image": 6}
        runner.view_contract(view, 3, 1)
        for key, value in (("type", 1), ("mips", 2), ("baseMip", 1), ("basis", "guessed-driver-query")):
            with self.assertRaises(ValueError):
                runner.view_contract({**view, key: value}, 3, 1)
        sampler = {"basis": "captured-successful-vkCreateSampler-arguments", "handle": 8, "minFilter": 1,
                   "magFilter": 1, "bias": 0, "anisotropy": False, "minLod": 0, "maxLod": 100, "address": [2, 2, 2]}
        runner.sampler_contract(sampler)
        for key, value in (("minFilter", 0), ("bias", 1), ("anisotropy", True)):
            with self.assertRaises(ValueError):
                runner.sampler_contract({**sampler, key: value})

    def test_duplicate_json_and_native_artifact_escape_rejected(self):
        path = self.out/"duplicate.json"
        path.write_text('{"status":"PASS","status":"FAIL"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            runner.read_json(path)
        with self.assertRaises(ValueError):
            runner.artifact(self.out, "../native", ".bin")
        with self.assertRaises(ValueError):
            runner.named_artifact(self.out, str(self.out/"native-other.bin"), "native.bin")

    def test_validation_current_is_required_not_recipe_or_loader_only(self):
        (self.out/"stderr.log").write_text('Insert instance layer "VK_LAYER_KHRONOS_validation"\n')
        (self.out/"stdout.log").write_text("")
        (self.out/"validation.log").write_text("validate_core = true\n")
        self.assertFalse(runner.base.validation_evidence(self.out, "core")["requestedModeVerified"])
        (self.out/"validation.log").write_text("CURRENT-VALIDATION-ENABLED\n  - Core Checks\n")
        self.assertTrue(runner.base.validation_evidence(self.out, "core")["requestedModeVerified"])
        self.assertFalse(runner.base.validation_evidence(self.out, "sync")["requestedModeVerified"])
        (self.out/"validation.log").write_text("CURRENT-VALIDATION-ENABLED\n  - Core Checks\n  - GPU-AV\n")
        self.assertFalse(runner.base.validation_evidence(self.out, "core")["requestedModeVerified"])

    def test_exec_wait_and_normal_exit_guards_remain_production_linked(self):
        script = runner.execution_script(self.out)
        self.assertEqual(len(script.splitlines()), 1)
        self.assertIn('pf113_probe_diag "', script)
        self.assertTrue(script.endswith('; wait 5; quit\n'))
        self.assertLess(script.index("wait 105"), script.index("pf113_probe_diag"))
        self.assertLess(script.index("pf113_probe_diag"), script.index("screenshot"))
        source = PATH.read_text()
        self.assertIn('require(receipt.get("exitCode") == 0', source)
        self.assertIn('receipt["validation"]["errorCount"] == 0', source)
        self.assertIn('receipt["validation"]["warningCount"] == 0', source)
        self.assertIn("base.wait_child(process", source)
        self.assertIn("process.kill()", source)
        self.assertNotIn("taskkill", source)
        self.assertNotIn("debug_restart", source)

    @staticmethod
    def float_controls():
        # Authored numerical test services only, never described as GPU output.
        a, b = 19, 41
        values = {}
        def put(row, band, x, value):
            row[(band*32+x)*4:(band*32+x+1)*4] = value
        for name in runner.CONTROL_NAMES:
            row = [0.]*1280
            for x in range(32):
                token = b if name.endswith("-b") else a
                if name in ("uniform-zero", "gather-allzero") or name == "quad-zero-live" and x % 3 == 0:
                    token = 0
                if name == "quad-live-live" and x % 3 == 0:
                    token = b
                def sample(pair, band):
                    return [(0. if not pair else .2+x*.01+c*.03+(0.4 if pair == b else 0.)+(0.2 if band else 0.)) for c in range(3)]
                taps, weights = [token, 0, 0, 0], [1., 0., 0., 0.]
                if name.startswith("gather-"):
                    taps = {"gather-allzero": [0, 0, 0, 0], "gather-mixed": [b, 0, 0, a], "gather-live": [a, b, b, a]}[name]
                    weights = [.30, .10, .45, .15]
                irr = [sum(sample(tap, 0)[c]*weight for tap, weight in zip(taps, weights)) for c in range(3)]
                pref = [sum(sample(tap, 1)[c]*weight for tap, weight in zip(taps, weights)) for c in range(3)]
                roughness = 0. if name == "roughness-zero-live-a" else 1. if name == "roughness-one-live-a" else .375
                if name == "roughness-one-live-a":
                    pref = [v+.25 for v in pref]
                diffuse, specular, lo = [v*.35 for v in irr], [v*.2 for v in pref], [.1, .2, .3]
                final = [lo[c]+diffuse[c]+specular[c] for c in range(3)]
                for band, v in enumerate((irr, pref, diffuse, specular, lo, final)):
                    put(row, band, x, [*v, 1.])
                put(row, 6, x, [0., 0., 1., roughness])
                put(row, 7, x, [.1, .2, .3, float(0 if name.startswith("gather-") else token)])
                put(row, 8, x, [float(v) for v in taps])
                put(row, 9, x, weights)
            values[name] = row
        return values, a, b

    def test_independent_raw_relationship_positive_and_controls(self):
        values, a, b = self.float_controls()
        result = runner.raw_control_relationships(values, a, b)
        self.assertLess(result["maximumGatherError"], 1.e-6)
        self.assertEqual(result["controls"], 12)
        self.assertGreater(result["spatialDelta"], .01)
        self.assertGreater(result["pairDelta"], .1)

    def test_zero_read_renormalization_wrong_order_and_nonfinite_rejected(self):
        values, a, b = self.float_controls()
        def renormalize(v):
            for x in range(32):
                for c in range(3):
                    v["gather-mixed"][x*4+c] /= .45
        mutations = (lambda v: v["uniform-zero"].__setitem__(0, 1.e-9), renormalize,
                     lambda v: v["gather-mixed"].__setitem__(8*32*4, float(a)),
                     lambda v: v["gather-live"].__setitem__(9*32*4, .31),
                     lambda v: v["uniform-live-a"].__setitem__(0, float("nan")),
                     lambda v: v["quad-zero-live"].__setitem__(0, .2))
        for mutation in mutations:
            bad = copy.deepcopy(values)
            mutation(bad)
            with self.assertRaises(ValueError):
                runner.raw_control_relationships(bad, a, b)

    def test_raw_positive_witness_cannot_be_constant_or_roughness_changed(self):
        values, a, b = self.float_controls()
        bad = copy.deepcopy(values)
        for x in range(32):
            for c in range(3):
                bad["roughness-one-live-a"][(32+x)*4+c] = bad["roughness-zero-live-a"][(32+x)*4+c]
        with self.assertRaisesRegex(ValueError, "constant"):
            runner.raw_control_relationships(bad, a, b)
        bad = copy.deepcopy(values)
        bad["gather-mixed"][6*32*4+3] = .5
        with self.assertRaisesRegex(ValueError, "roughness"):
            runner.raw_control_relationships(bad, a, b)

    def test_initial_window_is_required_before_native_controls(self):
        (self.out/"early.json").write_text(json.dumps({"schema": "shadedoomvk-pf113-startup-observer/v1", "status": "FAIL"}))
        with self.assertRaisesRegex(ValueError, "startup"):
            runner.native_evidence(self.out, {"rendererMode": 4, "globalFilter": 0})

    def test_three_real_draw_packet_and_retained_uniform_bytes_required(self):
        def view(kind, levels, image):
            return {"basis": "captured-successful-vkCreateImageView-arguments", "type": kind, "baseMip": 0,
                    "mips": levels, "baseLayer": 0, "layers": 6 if kind == 3 else 1, "aspect": 1, "handle": image+100, "image": image}
        sampler = {"basis": "captured-successful-vkCreateSampler-arguments", "handle": 8, "minFilter": 1,
                   "magFilter": 1, "bias": 0, "anisotropy": False, "minLod": 0, "maxLod": 100, "address": [2, 2, 2]}
        draws = []
        for kind, authored, token, published in (("initial-missing-probe1", 1, 0, False),
                                                ("initial-live-authored0", 0, 19, False),
                                                ("published-live-probe1", 1, 37, True)):
            stem = self.out/("early-"+kind)
            vertex, fragment, uniform = Path(str(stem)+".vert.spv"), Path(str(stem)+".frag.spv"), Path(str(stem)+".uniforms.bin")
            vertex.write_bytes(self.spv(False))
            fragment.write_bytes(self.spv())
            raw = bytearray(400)
            struct.pack_into("<i", raw, 380, token)
            struct.pack_into("<i", raw, 372, 55)
            uniform.write_bytes(raw)
            state = {"authoredProbe": authored, "runtimeProbe": token, "uniformProbe": token,
                     "uniformTexture": 55, "publishedPairs": 2 if published else 1, "publicationCount": int(published),
                     "shaderIndex": 4, "effectState": 4, "commandBuffer": 1, "pipeline": 2, "drawCount": 6,
                     "targetWidth": 128, "targetHeight": 128, "viewOwnerOrdinal": int(published), "missingTokenSamplesNoCube": token == 0,
                     "irradianceView": view(3, 1, 13 if published else 11), "prefilterView": view(3, 5, 14 if published else 12),
                     "irradianceSampler": sampler, "prefilterSampler": sampler, "uniformSize": 400, "probeOffset": 380, "textureOffset": 372}
            draws.append({"kind": kind, "material": "PF113W", "state": state, "vertexSpirv": str(vertex),
                          "fragmentSpirv": str(fragment), "uniformBytes": str(uniform)})
        data = {"schema": "shadedoomvk-pf113-startup-observer/v1", "status": "PASS",
                "fixed": {"nullSlot": 0, "brdfSlot": 1, "null": view(1, 1, 1), "brdf": view(1, 1, 2)},
                "draws": draws, "completedPublicationsAtFinalCommand": 5,
                "events": [{"kind": kind, "sequence": i, "irradiancePairs": i+1, "prefilterPairs": i+1, "authoredCount": 2,
                            "authoredPositions": [{"ordinal": j, "position": p} for j, p in enumerate(runner.inputs.PROBES)]}
                           for i, kind in enumerate(("before-completed-publication", "completed-publication"))]}
        path = self.out/"early.json"
        path.write_text(json.dumps(data))
        (self.out/"early-packaged-pbr.glsl").write_bytes((runner.ROOT/"wadsrc/static/shaders/scene/lightmodel_pbr.glsl").read_bytes())
        self.assertEqual(len(runner.early_evidence(self.out)["draws"]), 3)
        bad = copy.deepcopy(data)
        bad["draws"].pop(1)
        path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, "authored0"):
            runner.early_evidence(self.out)
        path.write_text(json.dumps(data))
        raw = bytearray(400)
        struct.pack_into("<i", raw, 372, 55)
        struct.pack_into("<i", raw, 380, 99)
        Path(draws[0]["uniformBytes"]).write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "uniform bytes"):
            runner.early_evidence(self.out)

    def test_live_original_gpu_cases_are_uniform_only(self):
        source = (runner.ROOT/"src/common/rendering/vulkan/textures/vk_pbrprobediagnostics.cpp").read_text()
        self.assertIn('Check(!reference || (mode == 4 && roughness == .375f)', source)
        self.assertIn('Draw("original-uniform-a", 4, .375f, none, true)', source)
        self.assertIn('Draw("original-uniform-b", 4, .375f, none, true)', source)
        self.assertNotIn('Draw("original-zero', source)
        self.assertNotIn('Draw("original-quad', source)
        self.assertIn('if (authored == 0 && token != 0', source)
        self.assertNotIn('const int authoredZero = manager->GetLightProbeTextureIndex(0);', source)

    def test_fake_exited_child_hash_failure_saves_final_failure_receipt(self):
        class FakeExitedChild:
            pid = 41113
            def poll(self):
                return 0
            def wait(self, timeout):
                return 0
            def kill(self):
                raise AssertionError("Already-exited fake child must not be killed")
        for name in ("native.json", "native-good.bin", "validation.log", "fixture-live.ini"):
            (self.out/name).write_bytes(b"authored CPU fixture")
        before = {"test": "unchanged"}
        receipt = {"status": "PREPARED", "argv": ["fake-never-executed-child"], "before": before, "generated": {}}
        saved_identity = runner.identity
        def fail_two_identities(path):
            if path.name in ("native.json", "stdout.log"):
                raise OSError("authored hash/stat race")
            return saved_identity(path)
        def finish_child(process, out, row, mod):
            row["exitCode"] = 0
        with patch.object(runner, "snapshot", return_value=before), patch.object(runner, "identity", side_effect=fail_two_identities), \
             patch.object(runner.base, "environment", return_value=({}, {})), patch.object(runner.base, "wait_child", side_effect=finish_child), \
             patch.object(runner.subprocess, "Popen", return_value=FakeExitedChild()), \
             patch.object(runner, "package_evidence", return_value={"verified": True}), \
             patch.object(runner.base, "validation_evidence", return_value={"requestedModeVerified": True, "errorCount": 0, "warningCount": 0}), \
             patch.object(runner.base, "exit_settings_evidence", return_value={"verified": True}), \
             patch.object(runner, "native_evidence", return_value={"scope": "authored test service"}), \
             patch.object(runner, "screenshot_evidence", return_value={"status": "PASS"}):
            result = runner.launch(receipt, {"mod": {"path": "authored-test.pk3"}}, {}, self.out/"manifest.json",
                                   self.out/"fake.exe", self.out, "core", self.out/"layer", self.out/"candidate.json")
        self.assertEqual(result, 1)
        saved = json.loads((self.out/"receipt.json").read_text())
        self.assertEqual(saved["status"], "FAIL")
        self.assertEqual(saved["exitCode"], 0)
        self.assertIn("native.json: OSError: authored hash/stat race", saved["artifactIdentityErrors"])
        self.assertIn("stdout.log: OSError: authored hash/stat race", saved["outputIdentityErrors"])
        self.assertIn("native-good.bin", saved["nativeArtifacts"])
        self.assertIn("stderr.log", saved["outputs"])
        self.assertNotIn("RUNNING", saved["status"])

    def test_artifact_directory_inventory_error_still_keeps_outputs(self):
        (self.out/"stdout.log").write_bytes(b"authored log")
        receipt = {"status": "PASS"}
        original = Path.iterdir
        def failing_directory(path):
            if path == self.out:
                raise OSError("authored directory stat race")
            return original(path)
        with patch.object(Path, "iterdir", failing_directory):
            runner.retained_output_identities(self.out, receipt)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("authored directory stat race", receipt["artifactError"])
        self.assertIn("stdout.log", receipt["outputs"])


if __name__ == "__main__":
    unittest.main()
