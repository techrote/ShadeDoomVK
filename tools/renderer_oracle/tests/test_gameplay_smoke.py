"""CPU-only preparation/admission controls; constructed rows are not play evidence."""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.renderer_oracle import gameplay_smoke as smoke, prepare
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block
from test_sdvk011_viewmodel import draw
from test_evidence import png

ROOT = Path(__file__).resolve().parents[3]


def recipe():
    return next(scene for scene in prepare.load_catalog()["scenes"] if scene["id"] == smoke.SCENE)


def constructed_records():
    records = []
    for frame in range(1, smoke.FRAMES+1):
        map_name = smoke.MAP_A if frame <= 56 or frame > 96 else smoke.MAP_B
        x = 0 if frame <= 8 or frame > 56 else 16
        yaw = -8 if 24 < frame <= 56 else 0
        ammo = 90 - int(40 < frame <= 56 or 80 < frame <= 96)
        camera = dict(position=[x, 0, 41], angles=[yaw, 0, 0])
        game = dict(contract="ordinary-gameplay/v1", producer="actual-player-inventory-after-main-view",
            map=map_name, position=[x, 0, 0], yaw=yaw, gametic=100+frame, ammo=ammo,
            weapon="SDVKVMWeapon", cheats=0, extra_light=1 if 44 <= frame <= 48 or 84 <= frame <= 88 else 0,
            forward=False, right=False, attack=False, pending_input=False,
            detail_selected=frame in (*smoke.CHECKPOINTS, 44, 84))
        weapon = draw()
        weapon.update(shader=4, material="SDVUB0" if game["extra_light"] else "SDVUA0",
            sample=[x + 8*math.cos(math.radians(yaw)), 41, 8*math.sin(math.radians(yaw))])
        for kind, value in (("frame", dict(map=map_name, camera=camera)), ("gameplay", game),
                ("resource", {"levelmesh": {"owner": 100 if frame <= 56 else 101 if frame <= 96 else 102}}),
                ("viewmodel", weapon)):
            records.append(dict(kind=kind, frame=frame, count=1, data=value))
        if game["detail_selected"]:
            for kind in smoke.DETAIL_KINDS:
                value = ({"name": weapon["material"], "layers": [dict(semantic=name, role="authored-layer") for name in smoke.PBR_SEMANTICS]}
                         if kind == "material" else {"constructed_budget_policy_control": True})
                records.append(dict(kind=kind, frame=frame, count=1, data=value))
    return dict(warmup_frames=smoke.WARMUP, observed_frames=smoke.FRAMES,
                gpu_timing_requested=False, records=records)


class GameplaySmokeTests(unittest.TestCase):
    def test_real_captured_payload_exhausts_old_budget_but_actual_selected_emit_fits_unchanged_store(self):
        source = (ROOT/"src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        extracted = '\n'.join(block(source, signature) for signature in (
            "bool GameplayCheckpoint(", "void SelectGameplayDetail(", "bool GameplayRecordSelected(", "void Emit("))
        payload = gzip.decompress(Path(__file__).with_name("fixtures").joinpath("viewmodel-legacy-record-payload.tsv.gz").read_bytes())
        self.assertEqual(hashlib.sha256(payload).hexdigest(), "5a7d8825e1d997e16353c9651e07ba18d2e9796c5a8a628ff4d06e7f9c4f2695")
        self.assertEqual(len(payload.splitlines()), 223)
        with tempfile.TemporaryDirectory(prefix="sdvk-gameplay-budget-") as directory:
            directory = Path(directory)
            (directory/"gameplay_budget.inc").write_text(extracted)
            captured = directory/"actual-payload.tsv"; captured.write_bytes(payload)
            executable = compile_fixture(Path(__file__).with_name("gameplay_budget_fixture.cpp"),
                output_dir=directory, includes=[directory, ROOT/"src/rendering/hwrenderer/diagnostics"])
            retained = directory/"actual-retained.json"
            result = subprocess.run([str(executable), str(captured), str(retained)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            report = json.loads(result.stdout)
            self.assertLess(report["old_rejected_frame"], 40)
            self.assertEqual(report["limit_bytes"], 16*1024*1024)
            self.assertEqual(report["detail_frames"], 9)
            self.assertLess(report["selected_bytes"], report["limit_bytes"])
            actual_rows = json.loads(retained.read_text())
            for kind in ("frame", "resource", "viewmodel", "gameplay"):
                self.assertEqual({row["frame"] for row in actual_rows if row["kind"] == kind}, set(range(1, smoke.FRAMES+1)))
            for kind in (*smoke.DETAIL_KINDS, "gameplay-checkpoint"):
                self.assertEqual({row["frame"] for row in actual_rows if row["kind"] == kind}, set((*smoke.CHECKPOINTS, 44, 84)))
            print("REAL_GAMEPLAY_BUDGET " + json.dumps(report,sort_keys=True))

    def test_exact_nine_detail_frames_retain_materials_and_reject_missing_or_extra_sampling(self):
        expected = sorted((*smoke.CHECKPOINTS, 44, 84))
        self.assertEqual(smoke.validate_records(constructed_records(), recipe()["native"])["detailed_frames"], expected)
        for defect in ("missing-flag", "extra-flag", "missing-material", "missing-probe", "outside-detail"):
            raw = constructed_records()
            if defect in ("missing-flag", "extra-flag"):
                for row in raw["records"]:
                    if row["kind"] == "gameplay" and row["frame"] == (44 if defect == "missing-flag" else 45):
                        row["data"]["detail_selected"] = defect == "extra-flag"
            elif defect.startswith("missing-"):
                raw["records"] = [r for r in raw["records"] if not (r["frame"] == 44 and r["kind"] == defect[8:])]
            else:
                extra = copy.deepcopy(next(r for r in raw["records"] if r["kind"] == "material"))
                extra["frame"] = 45; raw["records"].append(extra)
            with self.subTest(defect=defect), self.assertRaises(ValueError): smoke.validate_records(raw, recipe()["native"])

    def test_real_scene_assertion_gate_requires_world_materials_on_every_selected_detail_frame(self):
        from tools.renderer_oracle.run import _scene_assertions
        scene = recipe(); raw = constructed_records(); raw["mode"] = "state"
        for row in raw["records"]:
            if row["kind"] == "frame":
                row["data"]["settings"] = copy.deepcopy(scene["native"]["settings"])
                row["data"]["camera"]["fov"] = 90
                row["data"].update({key: bounds["minimum"] for key, bounds in scene["native"]["frame_assertions"].items()})
        for frame in smoke.detail_frames(raw):
            for name in scene["native"]["state_assertions"]["materials"]:
                raw["records"].append(dict(kind="material", frame=frame, count=1, data=dict(name=name)))
        _scene_assertions(raw, scene)
        raw["records"] = [row for row in raw["records"] if not (row["frame"] == 44 and row["kind"] == "material"
                          and row["data"].get("name") == "SDVLA0")]
        with self.assertRaisesRegex(ValueError, "Required material was not drawn"):
            _scene_assertions(raw, scene)

    def test_actual_resource_producer_emits_lifecycle_owner_for_gameplay_and_preserves_static_shape(self):
        diagnostics = (ROOT/"src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        resources = block((ROOT/"src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp").read_text(),
                          "void VulkanResources(")
        with tempfile.TemporaryDirectory(prefix="sdvk-gameplay-resources-") as directory:
            directory = Path(directory)
            (directory/"gameplay_resource_flags.inc").write_text('\n'.join(
                block(diagnostics, signature) for signature in ("bool SpecialSurfaceEnabled()", "bool GameplaySmokeEnabled()")))
            (directory/"gameplay_resource_mesh.inc").write_text(block(resources, "if (level.levelMesh)"))
            executable = compile_fixture(Path(__file__).with_name("gameplay_resource_fixture.cpp"),
                output_dir=directory, includes=[directory, ROOT/"src/rendering/hwrenderer/diagnostics"])
            def emitted(mode, owner):
                result = subprocess.run([str(executable), mode, str(owner)], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                return json.loads(result.stdout)
            actual = {owner: emitted("gameplay", owner) for owner in (100, 101, 102)}
            self.assertEqual(actual[100], emitted("special", 100))
            for mode in ("ordinary", "disabled"):
                static = emitted(mode, 100)
                self.assertNotIn("owner", static["levelmesh"])
                self.assertEqual(static, {**actual[100], "levelmesh": {
                    key: value for key, value in actual[100]["levelmesh"].items() if key != "owner"}})
            raw = constructed_records()
            for row in raw["records"]:
                if row["kind"] == "resource":
                    row["data"] = actual[100 if row["frame"] <= 56 else 101 if row["frame"] <= 96 else 102]
            self.assertEqual(smoke.validate_records(raw, recipe()["native"])["fresh_levelmesh_owners"], [100, 101, 102])
            for row in raw["records"]:
                if row["kind"] == "resource" and row["frame"] == 80: row["data"] = emitted("ordinary", 100)
            with self.assertRaisesRegex(ValueError, "producer lacks actual LevelMesh ownership"):
                smoke.validate_records(raw, recipe()["native"])

    def test_authored_room_fire_materials_maps_and_ordinary_commands_are_deterministic(self):
        catalog = prepare.load_catalog(); prepare.validate_catalog(catalog)
        scene = recipe()
        first = prepare.scene_assets(scene); self.assertEqual(first, prepare.scene_assets(scene))
        _, members, metadata = first
        self.assertTrue(metadata["live_player_camera"])
        self.assertEqual(metadata["maps"], [smoke.MAP_A, smoke.MAP_B])
        for map_name in (smoke.MAP_A, smoke.MAP_B): self.assertIn(f"maps/{map_name}.wad", members)
        self.assertIn(b'Weapon.AmmoType "Clip"', members["ZSCRIPT"])
        for action in (b"A_FireBullets", b"A_Light1", b"A_Light0", b"A_WeaponReady"):
            self.assertIn(action, members["ZSCRIPT"])
        self.assertIn(b"material sprite SDVUB0", members["GLDEFS"])
        self.assertIn("sprites/SDVLA0.png", members)
        self.assertNotIn(b"SDVKFixedCamera", members["MAPINFO"])

    def test_actual_deltas_pass_but_missing_motion_fire_resource_or_muzzle_evidence_fails(self):
        native = recipe()["native"]
        self.assertEqual(smoke.validate_records(constructed_records(), native)["status"], "PASS")
        for defect in ("motion", "fixed-camera", "turn", "fire", "owner", "map", "pending", "muzzle", "muzzle-b", "fire-material", "sample"):
            raw = constructed_records()
            for row in raw["records"]:
                value = row["data"]
                if row["kind"] == "gameplay":
                    if defect == "motion": value["position"][0] = 0
                    if defect == "turn": value["yaw"] = 0
                    if defect == "fire": value["ammo"] = 90
                    if defect == "map": value["map"] = smoke.MAP_A
                    if defect == "pending" and row["frame"] == 56: value["pending_input"] = True
                    if defect == "muzzle": value["extra_light"] = 0
                    if defect == "muzzle-b" and value["map"] == smoke.MAP_B: value["extra_light"] = 0
                if defect == "owner" and row["kind"] == "resource": value["levelmesh"]["owner"] = 100
                if defect == "fixed-camera":
                    if row["kind"] == "frame": value["camera"] = dict(position=[0, 0, 41], angles=[0, 0, 0])
                    if row["kind"] == "viewmodel": value["sample"] = [8, 41, 0]
                if defect == "sample" and row["kind"] == "viewmodel": value["sample"] = [0, 0, 0]
                if defect == "fire-material" and row["kind"] == "material" and value["name"] == "SDVUB0": value["layers"] = []
            with self.subTest(defect=defect), self.assertRaises(ValueError): smoke.validate_records(raw, native)

    def test_motion_exception_is_bound_to_one_exact_opt_in_recipe(self):
        for defect in ("id", "generator", "camera", "budget", "clock"):
            scene = copy.deepcopy(recipe())
            if defect == "id": scene["id"] = "viewmodel-pbr"
            if defect == "generator": scene["native"]["generator"] = "viewmodel"
            if defect == "camera": scene["native"]["camera"]["policy"] = "fixed"
            if defect == "budget": scene["native"]["gameplay_smoke"]["frames"] = 1
            if defect == "clock": scene["native"]["settings"]["cl_capfps"] = False
            with self.subTest(defect=defect), self.assertRaises(ValueError): smoke.validate_recipe(scene)

    def test_retained_command_log_requires_each_real_ordered_input_once(self):
        lines = [f"SDVK_GAMEPLAY_INPUT frame={frame} map={map_name} command={command}\n"
                 for frame, map_name, command in smoke.SCHEDULE]
        smoke.validate_input_log(''.join(lines))
        for invalid in (lines[:-1], lines+lines[:1], list(reversed(lines))):
            with self.assertRaises(ValueError): smoke.validate_input_log(''.join(invalid))

    def test_completed_view_images_require_real_pngs_motion_difference_and_original_manifest_pins(self):
        raw = constructed_records()
        maps = {row["frame"]: row["data"]["map"] for row in raw["records"] if row["kind"] == "frame"}
        for frame in smoke.CHECKPOINTS:
            raw["records"].append(dict(kind="gameplay-checkpoint", frame=frame, count=1, data={
                "producer": "completed-main-view-screenshot", "map": maps[frame],
                "phase": "fixed", "image": f"native.gameplay-{frame}.png", "main_views": smoke.WARMUP+frame}))
        for frame, suffix in ((44, "a"), (84, "b")):
            raw["records"].append(dict(kind="gameplay-checkpoint", frame=frame, count=1, data={
                "producer": "completed-main-view-screenshot", "map": maps[frame], "phase": "muzzle",
                "image": f"native.gameplay-fire-{suffix}.png", "main_views": smoke.WARMUP+frame}))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = png(bytes(640*480*3), width=640, height=480)
            moved = png(bytes([1])+bytes(640*480*3-1), width=640, height=480)
            for frame in smoke.CHECKPOINTS:
                (root/f"native.gameplay-{frame}.png").write_bytes(moved if frame == 24 else original)
            for suffix in ("a", "b"): (root/f"native.gameplay-fire-{suffix}.png").write_bytes(moved)
            result = smoke.validate_checkpoints(root, raw)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["dynamic_exact_rgb_repeatability"])
            late = copy.deepcopy(raw)
            for row in late["records"]:
                if row["kind"] == "gameplay-checkpoint" and row["data"].get("image") == "native.gameplay-fire-a.png":
                    row["frame"] = 45; row["data"]["main_views"] = smoke.WARMUP+45
            with self.assertRaisesRegex(ValueError, "first actual detailed firing frame"):
                smoke.validate_checkpoints(root, late)
            pins = {row["image"]["path"]: row["image"] for row in result["checkpoints"]}
            smoke.validate_checkpoint_artifacts(pins)
            del pins["native.gameplay-24.png"]
            with self.assertRaises(ValueError): smoke.validate_checkpoint_artifacts(pins)
            (root/"native.gameplay-24.png").write_bytes(original)
            with self.assertRaises(ValueError): smoke.validate_checkpoints(root, raw)

    def test_actual_driver_refuses_pending_wait_buttons_map_or_clock_and_is_inert_by_default(self):
        source = (ROOT/"src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        extracted = '\n'.join(block(source, signature) + (';' if signature.startswith(('struct ', 'constexpr ')) else '')
            for signature in ('struct GameplayPhase', 'constexpr GameplayPhase GameplayPhases[] =',
                              'bool GameplayButtonsIdle()', 'void DriveGameplayInput('))
        with tempfile.TemporaryDirectory(prefix="sdvk-gameplay-input-") as directory:
            directory = Path(directory)
            (directory/"gameplay_input.inc").write_text(extracted)
            executable = compile_fixture(Path(__file__).with_name("gameplay_input_fixture.cpp"),
                output_dir=directory, includes=[directory])
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == "__main__": unittest.main()
