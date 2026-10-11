#!/usr/bin/env python3
"""CPU authoring/provenance controls; these tests do not render the corpus."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.renderer_oracle import prepare
from tools.pf_oracle import prepare_freeze_view_fixture as pf_view
from tools.pf_oracle import prepare_indexed_material_runtime as pf_indexed
from tools.pf_oracle import prepare_pbr_probe_runtime as pf_pbr


def scene_named(name: str) -> dict:
    return next(scene for scene in prepare.load_catalog()["scenes"] if scene["id"] == name)


def unpack_wad(raw: bytes) -> dict[str, bytes]:
    """Independent bounded reader for the bytes that a map loader will receive."""
    magic, count, directory = struct.unpack_from("<4sII", raw)
    if magic != b"PWAD" or directory + 16 * count != len(raw):
        raise AssertionError("Invalid authored WAD directory")
    result = {}
    for i in range(count):
        at, size, encoded = struct.unpack_from("<II8s", raw, directory + 16 * i)
        name = encoded.rstrip(b"\0").decode("ascii")
        if name in result or at < 12 or at + size > directory:
            raise AssertionError("Duplicate or out-of-range authored WAD lump")
        result[name] = raw[at:at + size]
    return result


def parse_udmf(raw: bytes) -> dict[str, list[dict]]:
    text = raw.decode("ascii")
    result = {}
    for kind, body in re.findall(r"(vertex|sector|sidedef|linedef|thing)\s*\{([^}]*)\}", text):
        row = {}
        for key, literal in re.findall(r"([a-z0-9_]+)\s*=\s*([^;]+);", body):
            value = literal.strip()
            if value.startswith('"'):
                parsed = value[1:-1]
            elif value in ("true", "false"):
                parsed = value == "true"
            else:
                parsed = float(value) if "." in value else int(value)
            row[key] = parsed
        result.setdefault(kind, []).append(row)
    return result


def unpack_png(raw: bytes) -> tuple[dict, bytes]:
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Bad authored PNG signature")
    chunks, cursor = {}, 8
    while cursor < len(raw):
        size = struct.unpack_from(">I", raw, cursor)[0]
        kind = raw[cursor + 4:cursor + 8]
        data = raw[cursor + 8:cursor + 8 + size]
        crc = struct.unpack_from(">I", raw, cursor + 8 + size)[0]
        if crc != zlib.crc32(kind + data) & 0xffffffff:
            raise AssertionError("PNG CRC mismatch")
        chunks[kind] = chunks.get(kind, b"") + data
        cursor += size + 12
    if cursor != len(raw) or b"IEND" not in chunks:
        raise AssertionError("PNG does not terminate at the expected boundary")
    width, height, bits, kind, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunks[b"IHDR"])
    if (bits, kind, compression, filtering, interlace) != (8, 6, 0, 0, 0):
        raise AssertionError("Expected ordinary 8-bit RGBA PNG")
    scan = zlib.decompress(chunks[b"IDAT"])
    if len(scan) != height * (1 + width * 4):
        raise AssertionError("Unexpected PNG scan length")
    rows = []
    for y in range(height):
        start = y * (1 + width * 4)
        if scan[start] != 0:
            raise AssertionError("Authored fixture must use unfiltered scanlines")
        rows.append(scan[start + 1:start + 1 + width * 4])
    return {"width": width, "height": height, "offset": struct.unpack(">ii", chunks[b"grAb"]) if b"grAb" in chunks else None}, b"".join(rows)


class CatalogTests(unittest.TestCase):
    def test_catalog_resolves_every_class_to_actual_retained_contracts(self):
        catalog = prepare.load_catalog()
        prepare.validate_catalog(catalog)
        self.assertEqual(set().union(*(set(s["classes"]) for s in catalog["scenes"])), prepare.CLASSES)
        self.assertTrue(all(c["native_rendering_proof"] is False for c in catalog["cpu_contracts"].values()))
        self.assertTrue(all(s["native"]["status"] == "native_qualification_pending" for s in catalog["scenes"]))

    def test_false_native_acceptance_missing_contract_and_unsafe_source_fail(self):
        original = prepare.load_catalog()
        for mutate in (
            lambda c: c["scenes"][0]["native"].update(executed=True),
            lambda c: c["scenes"][0]["native"].update(status="accepted"),
            lambda c: c["scenes"][0].update(cpu_contracts=["invented-contract"]),
            lambda c: c["scenes"][0].update(source_refs=["../outside.txt"]),
            lambda c: c["scenes"][0]["native"].update(generator="arbitrary_module"),
            lambda c: c["scenes"][0]["comparison"].update(state_required=False),
            lambda c: c["scenes"][0]["native"]["clock"].update(timing="single-tic"),
            lambda c: c["scenes"][0]["native"].update(generic_capture_supported=True),
            lambda c: c["scenes"][0]["native"].update(pk3="../scene.pk3"),
            lambda c: c["scenes"][0]["native"]["camera"].update(position=[float("nan"), 0, 0]),
        ):
            changed = copy.deepcopy(original)
            mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises((ValueError, OSError)):
                prepare.validate_catalog(changed)

    def test_duplicate_scene_and_stale_cpu_command_fail(self):
        changed = prepare.load_catalog()
        changed["scenes"].append(copy.deepcopy(changed["scenes"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            prepare.validate_catalog(changed)
        changed = prepare.load_catalog()
        changed["cpu_contracts"]["sprite-surface"]["command"][-2] = "test_missing.py"
        with self.assertRaisesRegex(ValueError, "named existing test"):
            prepare.validate_catalog(changed)

    def test_unknown_cvar_and_missing_readback_fail(self):
        changed = prepare.load_catalog()
        changed["scenes"][0]["native"]["settings"]["invented_renderer_setting"] = 1
        with self.assertRaisesRegex(ValueError, "unverified setting"):
            prepare.validate_catalog(changed)
        changed = prepare.load_catalog()
        changed["scenes"][0]["native"]["console_queries"] = []
        with self.assertRaisesRegex(ValueError, "query every declared setting"):
            prepare.validate_catalog(changed)
        changed = prepare.load_catalog()
        changed["cvar_sources"]["gl_shadowmap_quality"] = ["src/d_main.cpp"]
        with self.assertRaisesRegex(ValueError, "no CVar definition"):
            prepare.validate_catalog(changed)

    def test_new_authored_scenes_accept_a_pinned_external_compatible_iwad(self):
        for scene in prepare.load_catalog()["scenes"]:
            iwad = scene["native"]["iwad"]
            if scene["native"]["generator"].startswith("pf_"):
                self.assertEqual(iwad["sha256"], pf_view.IWAD_SHA256)
            else:
                self.assertIsNone(iwad["sha256"])
                self.assertTrue(iwad["pin_actual_sha256_before_run"])
            self.assertFalse(iwad["copied_into_pk3"])

    def test_settings_reject_nonfinite_or_executable_console_values(self):
        for value in (float("nan"), float("inf"), "png; quit", "png\nquit", '"png"', "", [], None):
            changed = prepare.load_catalog()
            changed["scenes"][0]["native"]["settings"]["screenshot_type"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite or a safe literal"):
                prepare.validate_catalog(changed)

    def test_invalid_native_workload_assertions_fail_preparation(self):
        for assertions in ({"decals": {"minimum": 2, "maximum": 1}}, {"decals": {"minimum": True}},
                           {"imaginary_counter": {"minimum": 1}}):
            changed = prepare.load_catalog()
            changed["scenes"][3]["native"]["frame_assertions"] = assertions
            with self.subTest(assertions=assertions), self.assertRaisesRegex(ValueError, "frame assertion"):
                prepare.validate_catalog(changed)
        changed = prepare.load_catalog()
        changed["scenes"][3]["native"]["state_assertions"] = {"root_types": ["invented-view"]}
        with self.assertRaisesRegex(ValueError, "unsupported root context"):
            prepare.validate_catalog(changed)

    def test_new_native_assertions_are_typed_and_bound_to_observed_materials(self):
        variants = ({"line_mirror": False}, {"published_probes_minimum": True}, {"published_probes_minimum": 0},
                    {"sun_intensity": float("nan")}, {"sun_intensity": -1},
                    {"material_semantics": {"NOT_REQUIRED": ["albedo"]}},
                    {"materials": ["SM0000"], "material_semantics": {"SM0000": ["albedo", "albedo"]}})
        for assertions in variants:
            changed = prepare.load_catalog()
            changed["scenes"][3]["native"]["state_assertions"] = assertions
            with self.subTest(assertions=assertions), self.assertRaises(ValueError):
                prepare.validate_catalog(changed)


class AuthoredSceneTests(unittest.TestCase):
    def test_retained_pf_archives_remain_byte_identical(self):
        for name, module in (("pf-sprite-views", pf_view), ("pf-indexed-material", pf_indexed), ("pf-pbr-probes", pf_pbr)):
            with self.subTest(scene=name):
                archive, members, metadata = prepare.scene_assets(scene_named(name))
                self.assertEqual(members, module.members())
                self.assertEqual(archive, module.archive_bytes(module.members()))
                self.assertTrue(metadata["member_bytes_unchanged"])
                self.assertFalse(metadata["native_executed"])

    def test_authored_camera_maps_and_texture_pixels_are_bounded_and_self_contained(self):
        for scene in prepare.load_catalog()["scenes"]:
            if scene["native"]["generator"].startswith("pf_"):
                continue
            with self.subTest(scene=scene["id"]):
                archive, members, metadata = prepare.scene_assets(scene)
                with zipfile.ZipFile(io.BytesIO(archive)) as zip_file:
                    self.assertIsNone(zip_file.testzip())
                    self.assertEqual(zip_file.namelist(), sorted(members))
                    self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in zip_file.infolist()))
                map_name = scene["native"]["map"]
                lumps = unpack_wad(members[f"maps/{map_name}.wad"])
                self.assertEqual(set(lumps), {map_name, "TEXTMAP", "ENDMAP"})
                records = parse_udmf(lumps["TEXTMAP"])
                for line in records["linedef"]:
                    self.assertLess(line["v1"], len(records["vertex"]))
                    self.assertLess(line["v2"], len(records["vertex"]))
                    self.assertLess(line["sidefront"], len(records["sidedef"]))
                cameras = [t for t in records["thing"] if t["type"] == 32200]
                self.assertEqual(len(cameras), 1)
                camera = cameras[0]
                expected = scene["native"]["camera"]
                self.assertEqual([camera["x"], camera["y"], camera["height"] + records["sector"][0]["heightfloor"]], expected["position"])
                self.assertEqual(camera["id"], expected["actor_tid"])
                authored = scene["native"].get("authored_camera_angles", expected)
                self.assertEqual(camera["angle"], authored["yaw"])
                players = [t for t in records["thing"] if t["type"] == 1]
                self.assertEqual(len(players), 1)
                player = players[0]
                self.assertNotEqual([player["x"], player["y"]], [camera["x"], camera["y"]])
                view = math.radians(expected["yaw"])
                behind = ((player["x"] - camera["x"]) * math.cos(view)
                          + (player["y"] - camera["y"]) * math.sin(view))
                self.assertLess(behind, 0)
                self.assertEqual(metadata["player_start_world"], [player["x"], player["y"]])
                self.assertLess(metadata["boundary_signed_areas"][0], 0)
                self.assertTrue(all(area > 0 for area in metadata["boundary_signed_areas"][1:]))
                for path, raw in members.items():
                    if path.endswith(".png"):
                        image, pixels = unpack_png(raw)
                        self.assertLessEqual(image["width"], 256)
                        self.assertLessEqual(image["height"], 256)
                        self.assertEqual(len(pixels), image["width"] * image["height"] * 4)
                        self.assertRegex(Path(path).stem, r"^(SDV|SM)")

    def test_compositing_has_actual_decal_authoring_and_translucent_camera_routes(self):
        scene = scene_named("compositing")
        members, meta = prepare.authored_members(scene)
        records = parse_udmf(unpack_wad(members["maps/SDVCMP.wad"])["TEXTMAP"])
        decals = {row["id"]: row for row in records["thing"] if row["type"] == 9200}
        self.assertEqual(set(decals), {2030, 2031})
        self.assertEqual(decals[2030]["arg0"] + 256 * decals[2030]["arg1"], 25001)
        self.assertEqual((decals[2030]["x"], decals[2030]["angle"]), (240, 180))
        self.assertLess(256 - decals[2030]["x"], 64)
        self.assertGreater(decals[2031]["x"] - (-256), 64)
        self.assertIn(b"decal SDVKMark 25001", members["DECALDEF"])
        self.assertIn(b"cameratexture SDVCAM 128 128", members["ANIMDEFS"])
        self.assertIn("SDVCAM", [row["texturemiddle"] for row in records["sidedef"]])
        self.assertEqual(sum(t["type"] == 32202 for t in records["thing"]), 2)
        self.assertIn(b'Alpha 0.5; RenderStyle "Translucent"', members["ZSCRIPT"])
        self.assertTrue(meta["decal_controls"]["actual_attach_count_required"])
        self.assertEqual(scene["native"]["frame_assertions"]["decals"], {"minimum": 1})
        self.assertEqual(scene["native"]["state_assertions"], {
            "root_types": ["main", "camera-texture"], "materials": ["SDVCAM"]})

    def test_light_workloads_preserve_zero_one_many_and_true_capacity_boundary(self):
        for name, count in (("lights-zero", 0), ("lights-one", 1), ("lights-many", 64), ("shadow-boundary", 1025)):
            scene = scene_named(name)
            members, _ = prepare.authored_members(scene)
            records = parse_udmf(unpack_wad(members[f'maps/{scene["native"]["map"]}.wad'])["TEXTMAP"])
            lights = [thing for thing in records["thing"] if thing["type"] == 9800]
            self.assertEqual(len(lights), count)
            self.assertEqual(len({thing["id"] for thing in lights}), count)
            self.assertEqual(len({(thing["x"], thing["y"]) for thing in lights}), count)
            self.assertTrue(all(not (0 <= t["x"] <= 128 and -64 <= t["y"] <= 64) for t in lights))
            self.assertTrue(all(t["light_noshadowmap"] is False for t in lights))
            expected_counts = {"shadow_candidates": count, "shadow_selected": min(count, 1024),
                               "shadow_dropped": max(count - 1024, 0)}
            for counter, expected in expected_counts.items():
                self.assertEqual(scene["native"]["frame_assertions"][counter],
                                 {"minimum": expected, "maximum": expected})
            self.assertIs(scene["native"]["settings"]["gl_lights"], True)
            self.assertIs(scene["native"]["settings"]["gl_light_sprites"], True)
            self.assertEqual(scene["native"]["settings"]["gl_spritelight"], 2)
            if not count:
                self.assertNotIn("light-query", scene["required_state_channels"])
                self.assertNotIn("shadow", scene["required_state_channels"])
        shadow = scene_named("shadow-boundary")
        self.assertEqual(shadow["native"]["shadow_capacity_control"]["expected_authored_overflow"], 1)
        # The capacity witness is correctness-only: one light beyond the fixed
        # 1,024-row boundary is sufficient. Use the lowest valid shadow-map
        # resolution and one warmup frame so llvmpipe can execute the witness.
        self.assertEqual(shadow["native"]["recommended_warmup_frames"], 1)
        self.assertEqual(shadow["native"]["settings"]["gl_shadowmap_quality"], 128)
        self.assertEqual(scene_named("lights-many")["native"]["recommended_warmup_frames"], 120)

    def test_sdvk009_dense_light_workloads_are_matched_mixed_static_controls(self):
        expected_types = {9800, 9810, 9820, 9840, 9850, 9860}
        positions = {}
        for name, layout in (("lights-dense-overlap", "overlap"), ("lights-dense-dispersed", "dispersed")):
            scene = scene_named(name)
            members, meta = prepare.authored_members(scene)
            records = parse_udmf(unpack_wad(members[f'maps/{scene["native"]["map"]}.wad'])["TEXTMAP"])
            lights = [thing for thing in records["thing"] if thing["type"] in expected_types]
            self.assertEqual(len(lights), 256)
            self.assertEqual(len({thing["id"] for thing in lights}), 256)
            self.assertEqual(len({(thing["x"], thing["y"]) for thing in lights}), 256)
            self.assertEqual({thing["type"] for thing in lights}, expected_types)
            self.assertEqual(scene["native"]["light_layout"], layout)
            self.assertEqual(scene["native"]["light_profile"], "mixed-static")
            self.assertEqual(scene["native"]["settings"]["gl_light_shadows"], 0)
            self.assertNotIn("shadow", scene["required_state_channels"])
            self.assertEqual(meta["authored_light_count"], 256)
            self.assertEqual(set(meta["light_types"]), expected_types)
            positions[name] = {(thing["x"], thing["y"]) for thing in lights}
        self.assertNotEqual(positions["lights-dense-overlap"], positions["lights-dense-dispersed"])
        # Mode 1 can reject authored lights unless their influence hits a
        # one-sided back wall. The boundary recipe must request mode 2 so its
        # >1024 claim is testable, then still demand actual native counts.
        actual_light_source = (ROOT / "src/playsim/a_dynlight.cpp").read_text()
        self.assertIn("hitonesidedback || gl_light_shadows > 1", actual_light_source)
        for name in ("lights-one", "lights-many", "shadow-boundary"):
            self.assertEqual(scene_named(name)["native"]["settings"]["gl_light_shadows"], 2)

    def test_eight_rotations_and_mirror_require_actual_native_witnesses(self):
        import math
        scene = scene_named("sprite-mirror")
        members, metadata = prepare.authored_members(scene)
        records = parse_udmf(unpack_wad(members["maps/SDVROT.wad"])["TEXTMAP"])
        mirrors = [line for line in records["linedef"] if line.get("special") == 182]
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0]["id"], 2040)
        camera = scene["native"]["camera"]["position"]
        rotations = sorted((thing for thing in records["thing"] if thing["type"] == 32210), key=lambda thing: thing["id"])
        self.assertEqual(len(rotations), 8)
        for k, thing in enumerate(rotations):
            angle = math.degrees(math.atan2(thing["y"]-camera[1], thing["x"]-camera[0]))-thing["angle"]
            self.assertEqual(int(((angle+202.5) % 360)/22.5)//2, k)
        for name in metadata["rotation_material_names"]:
            header, pixels = unpack_png(members[f"sprites/{name}.png"])
            self.assertEqual(header["offset"], (32, 64))
            self.assertNotEqual(pixels[:4], pixels[60*4:61*4])
            self.assertIn(f"material sprite {name}".encode(), members["GLDEFS"])
        self.assertIs(scene["native"]["state_assertions"]["line_mirror"], True)
        self.assertEqual(scene["native"]["state_assertions"]["materials"],
                         metadata["rotation_material_names"] + ["SDVPA0", "SDVLA0"])
        self.assertEqual(metadata["pbr_sprite_material"], "SDVPA0")
        self.assertEqual(metadata["direction_light_tid"], 4500)
        self.assertEqual(metadata["per_pixel_sprite_light_mode"], 2)
        self.assertEqual(scene["native"]["settings"]["gl_spritelight"], 2)
        self.assertIs(scene["native"]["settings"]["gl_light_sprites"], True)
        self.assertEqual(len([thing for thing in records["thing"] if thing["type"] == 9800 and thing["id"] == 4500]), 1)
        self.assertEqual(metadata["legacy_unmapped_sprite"], "SDVLA0")
        for name in ("SDVPA0", "SDVLA0"):
            self.assertIn(f"sprites/{name}.png", members)
        self.assertIn(b"material sprite SDVPA0", members["GLDEFS"])
        self.assertNotIn(b"material sprite SDVLA0", members["GLDEFS"])
        self.assertEqual(sorted(thing["type"] for thing in records["thing"] if thing["type"] in (32215, 32216)), [32215, 32216])
        normal, pixels = unpack_png(members["textures/SDVN.png"])
        self.assertEqual((normal["width"], normal["height"]), (16, 16))
        self.assertNotEqual(pixels[:4], pixels[9*4:10*4])
        self.assertNotEqual(pixels[0], 128)
        self.assertNotEqual(pixels[1], 128)
        self.assertIn("sprite-basis", scene["required_state_channels"])
        self.assertIn(b'height "SDVH" { filter linear }', members["GLDEFS"])
        self.assertEqual(scene["native"]["state_assertions"]["material_height_layers"]["SDVRA1"],
                         {"binding": 6, "requested_sampling": 1})
        self.assertEqual(scene["native"]["frame_assertions"]["portals"]["minimum"], 1)
        for flag in (b"+WALLSPRITE", b"+FLATSPRITE", b"+XFLIP", b"+YFLIP"):
            self.assertIn(flag, members["ZSCRIPT"])

    def test_material_panels_reference_64_distinct_authored_inputs(self):
        members, metadata = prepare.authored_members(scene_named("material-stress"))
        records = parse_udmf(unpack_wad(members["maps/SDVMAT.wad"])["TEXTMAP"])
        textures = [side["texturemiddle"] for side in records["sidedef"] if side["texturemiddle"].startswith("SM")]
        self.assertEqual(len(textures), 64)
        self.assertEqual(len(set(textures)), 64)
        self.assertEqual(sorted(textures), metadata["material_names"])
        assertions = scene_named("material-stress")["native"]["state_assertions"]
        self.assertEqual(assertions["materials"], metadata["material_names"])
        self.assertEqual(set(assertions["material_semantics"]), set(textures))
        for name in textures:
            self.assertIn(f"textures/{name}.png", members)
        self.assertIn(b'specular "SDVSP"', members["GLDEFS"])
        self.assertIn(b'roughness "SDVZERO"', members["GLDEFS"])
        self.assertIn(b'ao "SDVAO"', members["GLDEFS"])
        self.assertEqual(metadata["custom_shader_material_names"],
                         ["SM0002", "SM0010", "SM0018", "SM0026",
                          "SM0034", "SM0042", "SM0050", "SM0058"])
        self.assertEqual(set(metadata["custom_shader_filters"].values()), {"nearest", "linear"})
        self.assertEqual(metadata["custom_shader_binding"], "SDVKExtra")
        self.assertEqual(metadata["custom_shader_texture"], "SDVCU")
        self.assertIn("textures/SDVCU.png", members)
        self.assertIn("shaders/sdvk004.fp", members)
        self.assertIn(b"texture(SDVKExtra, vTexCoord.st)", members["shaders/sdvk004.fp"])
        self.assertIn(b"SampleMaterialHeight(vTexCoord.st)", members["shaders/sdvk004.fp"])
        self.assertIn("textures/SDVH.png", members)
        self.assertEqual(metadata["height_texture"], "SDVH")
        for name in metadata["custom_shader_material_names"]:
            self.assertIn(f'material texture {name}'.encode(), members["GLDEFS"])
            self.assertNotIn("custom", assertions["material_semantics"][name])
            expected_sampling = 0 if metadata["custom_shader_filters"][name] == "nearest" else 1
            self.assertEqual(assertions["material_custom_layers"][name],
                             [{"binding": 8, "custom_index": 0,
                               "requested_sampling": expected_sampling}])
            self.assertEqual(assertions["material_height_layers"][name],
                             {"binding": 9, "requested_sampling": 1})
        self.assertEqual(set(metadata["height_material_names"]), set(assertions["material_height_layers"]))
        self.assertEqual(assertions["material_height_layers"]["SM0001"], {"binding": 6, "requested_sampling": 1})
        self.assertEqual(assertions["material_height_layers"]["SM0004"], {"binding": 4, "requested_sampling": 1})
        self.assertEqual(assertions["material_height_layers"]["SM0006"], {"binding": 8, "requested_sampling": 1})
        self.assertEqual(assertions["material_layer_sampling"]["SM0001"][0]["min_filter"], 0)
        self.assertEqual(assertions["material_layer_sampling"]["SM0001"][1]["min_filter"], 1)
        self.assertIn(b'shader "shaders/sdvk004.fp"', members["GLDEFS"])
        self.assertIn(b'texture SDVKExtra "SDVCU" { filter nearest }', members["GLDEFS"])
        self.assertIn(b'texture SDVKExtra "SDVCU" { filter linear }', members["GLDEFS"])

    def test_sun_scene_records_raised_floor_inputs_and_remains_unqualified(self):
        scene = scene_named("sun-probes")
        members, meta = prepare.authored_members(scene)
        records = parse_udmf(unpack_wad(members["maps/SDVSUN.wad"])["TEXTMAP"])
        self.assertEqual(records["sector"][0]["heightfloor"], 32)
        info = [t for t in records["thing"] if t["type"] == 9890]
        probes = [t for t in records["thing"] if t["type"] == 9892]
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["lm_sunintensity"], 1)
        self.assertEqual(len(probes), 2)
        self.assertEqual([[t["x"], t["y"], t["height"]] for t in probes], meta["authored_probe_positions"])
        lights = [t for t in records["thing"] if t["type"] == 9800]
        markers = [t for t in records["thing"] if t["type"] == 32203]
        self.assertEqual([t["id"] for t in lights], [3000])
        self.assertEqual([t["id"] for t in markers], [2020])
        self.assertEqual([t["id"] for t in records["thing"] if t["type"] == 32217], [2021])
        self.assertEqual(meta["actor_probe_tids"], [2020, 2021])
        self.assertIn(b"32217 = SDVKProbeMetal", members["MAPINFO"])
        self.assertIn(b"material texture SDVQA0", members["GLDEFS"])
        self.assertIn(b"material texture SDVOA0", members["GLDEFS"])
        self.assertIn(b'metallic "SDVZERO"', members["GLDEFS"])
        self.assertIn(b'roughness "SDVROUG"', members["GLDEFS"])
        self.assertIn(b'metallic "SDVMET"', members["GLDEFS"])
        self.assertIn(b'roughness "SDVROUGH"', members["GLDEFS"])
        self.assertIn("textures/SDVN.png", members)
        self.assertIn("textures/SDVROUG.png", members)
        self.assertEqual(scene["native"]["frame_assertions"]["sprites"], {"minimum": 2})
        self.assertEqual(scene["native"]["settings"]["gl_spritelight"], 2)
        self.assertIs(scene["native"]["settings"]["gl_light_sprites"], True)
        self.assertIs(scene["native"]["settings"]["gl_lights"], True)
        self.assertEqual(scene["native"]["state_assertions"]["published_probes_minimum"], 2)
        self.assertEqual(scene["native"]["state_assertions"]["sun_intensity"], 1)
        self.assertEqual(scene["native"]["state_assertions"]["actor_probe"]["required_indices"], [0, 1])
        self.assertTrue(scene["native"]["state_assertions"]["actor_probe"]["require_live"])
        self.assertEqual(set(scene["native"]["state_assertions"]["materials"]), {"SDVOA0", "SDVQA0"})
        self.assertFalse(meta["full_bake_qualified"])
        self.assertEqual(meta["baked_lightmap_members"], 0)

    def test_capture_scripts_have_no_time_based_quit_or_screenshot(self):
        for scene in prepare.load_catalog()["scenes"]:
            raw = prepare.capture_script(scene)
            self.assertEqual(raw.count(b"\n"), 1)
            self.assertLess(len(raw) + 1, 4094)
            commands = raw.decode().strip().split("; ")
            self.assertIn("unbindall", commands)
            self.assertIn("vid_setsize 640 480", commands)
            self.assertIn("fov 90", commands)
            self.assertIn("screenshot_type png", commands)
            self.assertIn(b"screenshot_type=png\n", prepare.configuration(scene))
            self.assertEqual(scene["native"]["settings"]["screenshot_type"], "png")
            self.assertEqual(scene["native"]["settings"]["r_drawplayersprites"], False)
            self.assertEqual(scene["native"]["settings"]["screenblocks"], 12)
            self.assertEqual(scene["native"]["settings"]["crosshair"], 0)
            self.assertFalse(any(c.split()[0] in ("quit", "screenshot", "wait", "freeze") for c in commands))
            self.assertNotIn("-pf020viewclock", raw.decode())
            for key, value in scene["native"]["settings"].items():
                self.assertGreater(commands.index(key), commands.index(f"{key} {str(value).lower()}"))
            self.assertNotIn("vid_preferbackend", scene["native"]["settings"])
            self.assertFalse(any(key.startswith("win_") for key in scene["native"]["settings"]))


class PreparationTests(unittest.TestCase):
    def test_two_fresh_preparations_have_identical_bytes_and_independent_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "different-output-name"
            first = prepare.prepare(a)
            second = prepare.prepare(b)
            self.assertEqual(first, second)
            self.assertEqual((a / "prepared.json").read_bytes(), (b / "prepared.json").read_bytes())
            self.assertFalse(first["native_executed"])
            self.assertFalse(first["native_qualified"])
            self.assertEqual(first["status"], "prepared_only")
            self.assertEqual(len(first["scenes"]), len(prepare.load_catalog()["scenes"]))
            self.assertEqual(len(first["files"]), 3 * len(first["scenes"]))
            for path, expected in first["files"].items():
                raw = (a / path).read_bytes()
                self.assertEqual(raw, (b / path).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
                self.assertEqual(len(raw), expected["bytes"])
            self.assertNotIn(str(a), (a / "prepared.json").read_text())
            self.assertNotIn(str(b), (b / "prepared.json").read_text())
            self.assertTrue(all(s["native"]["executed"] is False for s in first["scenes"]))
            self.assertEqual(prepare.verify_prepared(a), first)

    def test_subset_selection_is_explicit_and_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "subset"
            result = prepare.prepare(out, ["lights-zero"])
            self.assertEqual([s["id"] for s in result["scenes"]], ["lights-zero"])
            before = (out / "prepared.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "fresh directory"):
                prepare.prepare(out, ["lights-one"])
            self.assertEqual((out / "prepared.json").read_bytes(), before)
            for ids in ([], ["missing-scene"], ["lights-zero", "lights-zero"]):
                with self.assertRaises(ValueError):
                    prepare.prepare(Path(temp) / "not-created", ids)
            self.assertFalse((Path(temp) / "not-created").exists())

    def test_source_identity_pins_actual_retained_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            result = prepare.prepare(Path(temp) / "prepared", ["pf-pbr-probes"])
            sources = result["source_identity"]["files"]
            for name in ("tools/pf_oracle/fixtures/pf113-original/lightmodel_pbr.glsl",
                         "tools/pf_oracle/fixtures/pf113-original/original_probe_fixture.cpp",
                         "tools/pf_oracle/tests/shadow_visibility_correctness_fixture.cpp",
                         "tools/pf_oracle/prepare_freeze_view_fixture.py"):
                raw = (ROOT / name).read_bytes()
                self.assertEqual(sources[name], {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            self.assertEqual(result["source_identity"]["tree_cleanliness"], "not_asserted")

    def test_rehashed_forged_asset_or_recipe_cannot_pass_pure_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "forged"
            manifest = prepare.prepare(out, ["lights-zero"])
            path = "scenes/lights-zero/capture.cfg"
            raw = (out / path).read_bytes() + b"gl_light_shadows 4\n"
            (out / path).write_bytes(raw)
            manifest["files"][path] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            (out / "prepared.json").write_bytes(prepare.canonical_json(manifest))
            with self.assertRaisesRegex(ValueError, "regenerated fixture inputs"):
                prepare.verify_prepared(out)
            out = Path(temp) / "changed-camera"
            manifest = prepare.prepare(out, ["lights-zero"])
            manifest["scenes"][0]["native"]["camera"]["position"][0] += 1
            (out / "prepared.json").write_bytes(prepare.canonical_json(manifest))
            with self.assertRaisesRegex(ValueError, "authored source recipe"):
                prepare.verify_prepared(out)

    def test_verification_rejects_missing_or_changed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "changed"
            prepare.prepare(out, ["compositing"])
            (out / "scenes/compositing/scene.pk3").write_bytes(b"not the generated archive")
            with self.assertRaisesRegex(ValueError, "Prepared asset changed"):
                prepare.verify_prepared(out)


if __name__ == "__main__":
    unittest.main()
