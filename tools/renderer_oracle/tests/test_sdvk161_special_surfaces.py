"""Independent synthetic SDVK-161 semantic and lifecycle negative controls.

CPU only. No screenshot can substitute for an absent or wrong submitted path.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools.renderer_oracle import sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError


def native_recipe():
    return {"generator": "special_surface_lifecycle", "map": "SDV161A",
            "special_surface_schedule": copy.deepcopy(gate.SCHEDULE),
            "recommended_warmup_frames": 32,
            "camera": {"position": [-192, 0, 64], "yaw": 0, "pitch": 0, "roll": 0, "camera_height": 0, "actor_tid": 2002},
            "map_cameras": {
                "SDV161A": {"position": [-192, 0, 64], "yaw": 0, "pitch": 0, "roll": 0, "camera_height": 0, "actor_tid": 2002},
                "SDV161B": {"position": [1060, -176, 64], "yaw": 90, "pitch": 0, "roll": 0, "camera_height": 0, "actor_tid": 2002}},
            "map_sequence": ["SDV161A", "SDV161A", "SDV161B", "SDV161B"],
            "surface_witness_frames": list(range(8, 97, 8)),
            "console_commands": ["lm_max_updates 128", "lm_background_updates 32", "screenshot_quiet true"],
            "settings": {"gl_levelmesh": True, "lm_dynlights": False, "gl_lightprobe": True, "con_notifylines": 0,
                         "gl_texture_filter": 0, "gl_texture_filter_anisotropic": 1}}


def stdout():
    # Independent literals preserve exact phase timing/order in the controls.
    return ("SDVK161_INPUT phase=invalidate-a-retained-start after_main_views=32\n"
            "SDVK161_INPUT phase=invalidate-a-1 after_main_views=40\n"
            "SDVK161_INPUT phase=filter-linear-a after_main_views=48\n"
            "SDVK161_INPUT phase=reload-a after_main_views=56\n"
            "SDVK161_INPUT phase=filter-nearest-a after_main_views=64\n"
            "SDVK161_INPUT phase=invalidate-a-2 after_main_views=72\n"
            "SDVK161_INPUT phase=map-b after_main_views=80\n"
            "SDVK161_INPUT phase=invalidate-b-1 after_main_views=88\n"
            "SDVK161_INPUT phase=filter-linear-b after_main_views=96\n"
            "SDVK161_INPUT phase=reload-b after_main_views=104\n"
            "SDVK161_INPUT phase=filter-nearest-b after_main_views=112\n"
            "SDVK161_INPUT phase=invalidate-b-2 after_main_views=120\n")


def lifecycle_raw():
    records = []
    for frame in range(1, 97):
        second = frame > 48
        incarnation = (frame - 1) // 24
        settings = {"gl_levelmesh": True, "lm_dynlights": False, "gl_lightprobe": True,
                    "gl_texture_filter": 4 if 17 <= frame <= 32 or 65 <= frame <= 80 else 0,
                    "gl_texture_filter_anisotropic": 1}
        records.append({"kind": "frame", "frame": frame, "count": 1, "data": {
            "map": "SDV161B" if second else "SDV161A", "settings": settings,
            "camera": {"position": [1060, -176, 64] if second else [-192, 0, 64],
                       "angles": [90, 0, 0] if second else [0, 0, 0],
                       "hardware_angles": [180, 0, 0] if second else [270, 0, 0], "fov": 90}}})
        work = int(frame in (1, 9, 25, 41, 57, 73, 89))
        records.append({"kind": "resource", "frame": frame, "count": 1, "data": {
            "lightmap_epoch": 3 + incarnation, "probe_epoch": 5 + incarnation,
            "levelmesh": {"epoch": 7 + incarnation},
            "lightmap_state": {
                "available": True, "map": "SDV161B" if second else "SDV161A",
                "texture_count": 1, "vulkan_page_count": 1, "page_count_match": True, "authored_probe_count": 0,
                "live_tiles": 6, "valid_live_tiles": 6, "invalid_live_tiles": 0,
                "sampling_page_bounds_ok": True, "page_live_tiles": [6],
                "initial_dirty": 0, "geometry_dirty": 0, "light_dirty": 0, "all_clean": True,
                "frame_tile_updates": work, "frame_tile_completions": work}}})
    return {"observed_frames": 96, "records": records}


def resource(raw, frame):
    return next(row["data"] for row in raw["records"] if row["kind"] == "resource" and row["frame"] == frame)


class SpecialSurfaceLifecycleTests(unittest.TestCase):
    # These tests isolate lifecycle admission. Submitted-surface tests below run
    # the complete semantic gate and never use this service double.
    def validate(self, raw=None, text=None, native=None):
        with patch.object(gate, "_validate_submitted_surfaces", return_value={"synthetic": True}):
            return gate.validate_transition_records(lifecycle_raw() if raw is None else raw,
                                                    stdout() if text is None else text,
                                                    native_recipe() if native is None else native)

    def test_two_map_actual_completed_cycles_and_material_reset_phases(self):
        result = self.validate()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(set(result["cycles"]), {"initial_retained_invalidation", "invalidate_a_1", "reload_a", "invalidate_a_2", "invalidate_b_1", "reload_b", "invalidate_b_2"})
        self.assertFalse(result["physical_gpu_qualified"])

    def test_wrong_missing_duplicate_or_reordered_input_markers_fail(self):
        text = stdout()
        for bad in (text.replace("=56", "=57"), text + text.splitlines()[0] + "\n",
                    text.replace(text.splitlines()[0] + "\n", ""), "\n".join(reversed(text.splitlines()))):
            with self.subTest(text=bad), self.assertRaises(EvidenceError):
                self.validate(text=bad)

    def test_each_map_camera_is_pinned_through_both_same_map_reloads(self):
        for frame in (1, 25, 49, 73, 96):
            for key in ("position", "angles", "hardware_angles", "fov"):
                raw = lifecycle_raw()
                camera = next(row["data"]["camera"] for row in raw["records"] if row["kind"] == "frame" and row["frame"] == frame)
                if key == "fov": camera[key] = 80
                else: camera[key][0] += 1
                with self.subTest(frame=frame, key=key), self.assertRaisesRegex(EvidenceError, "camera"):
                    self.validate(raw)
        native = native_recipe()
        native["map_cameras"]["SDV161B"]["position"] = [-192, 0, 64]
        with self.assertRaisesRegex(EvidenceError, "per-map camera recipe"):
            self.validate(native=native)

    def test_missing_duplicate_cross_frame_resource_rejects(self):
        for edit in ("missing", "duplicate", "foreign-frame"):
            raw = lifecycle_raw()
            row = next(row for row in raw["records"] if row["kind"] == "resource" and row["frame"] == 9)
            if edit == "missing":
                raw["records"].remove(row)
            elif edit == "duplicate":
                raw["records"].append(copy.deepcopy(row))
            else:
                row["frame"] = 97
            with self.subTest(edit=edit), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_forged_map_census_page_or_completion_flags_reject(self):
        mutations = (
            lambda row: row.update(map="SDV161A"),
            lambda row: row.update(available=False),
            lambda row: row.update(vulkan_page_count=2),
            lambda row: row.update(valid_live_tiles=5, invalid_live_tiles=1),
            lambda row: row.update(sampling_page_bounds_ok=False),
            lambda row: row.update(page_live_tiles=[5]),
            lambda row: row.update(light_dirty=1),
            lambda row: row.update(frame_tile_completions=-1),
            lambda row: row.update(frame_tile_updates=True),
        )
        for mutation in mutations:
            raw = lifecycle_raw()
            mutation(resource(raw, 89)["lightmap_state"])
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_every_fixed_work_window_requires_actual_completion(self):
        for start, stop in ((1, 8), (9, 24), (25, 40), (41, 48), (57, 72), (73, 88), (89, 96)):
            raw = lifecycle_raw()
            for frame in range(start, stop + 1):
                resource(raw, frame)["lightmap_state"]["frame_tile_completions"] = 0
            with self.subTest(window=(start, stop)), self.assertRaisesRegex(EvidenceError, "complete real"):
                self.validate(raw)

    def test_warmup_completed_bake_cannot_replace_explicit_retained_invalidation_work(self):
        raw = lifecycle_raw()
        for frame in range(1, 9):
            resource(raw, frame)["lightmap_state"].update(frame_tile_updates=0, frame_tile_completions=0)
        with self.assertRaisesRegex(EvidenceError, "initial retained A invalidation did not complete real admitted"):
            self.validate(raw)
        missing = copy.deepcopy(native_recipe())
        missing["special_surface_schedule"].pop(0)
        with self.assertRaisesRegex(EvidenceError, "schedule differs"):
            self.validate(native=missing)

    def test_each_owner_advances_at_map_boundary_and_survives_sampler_resets(self):
        for key in ("lightmap_epoch", "probe_epoch", "levelmesh"):
            for mode in ("stale-reload", "reset-churn"):
                raw = lifecycle_raw()
                if mode == "stale-reload":
                    for frame in range(25, 49):
                        resource(raw, frame)[key] = copy.deepcopy(resource(raw, 24)[key])
                elif key == "levelmesh":
                    resource(raw, 17)[key]["epoch"] += 1
                else:
                    resource(raw, 17)[key] += 1
                with self.subTest(key=key, mode=mode), self.assertRaises(EvidenceError):
                    self.validate(raw)

    def test_actual_filter_state_cannot_be_substituted_by_input_markers(self):
        for frame in (17, 25, 33):
            raw = lifecycle_raw()
            value = next(row["data"] for row in raw["records"] if row["kind"] == "frame" and row["frame"] == frame)
            value["settings"]["gl_texture_filter"] = 0 if frame <= 32 else 4
            with self.subTest(frame=frame), self.assertRaisesRegex(EvidenceError, "actual frame setting"):
                self.validate(raw)


def material(name="S161PH", filtering=0):
    # These explicit binding layouts do not call the asset author or oracle.
    pbr = name in ("S161PH", "S161PN")
    height = name in ("S161PH", "S161HO", "S161WP")
    shader = 4 if pbr else 2 if name == "S161WP" else 0
    semantics = ["albedo"] + (["normal", "metallic", "roughness", "ambient-occlusion"] if pbr else [])
    layers = []
    for semantic in semantics + ["brightmap-emissive", "detail", "glow"] + (["height"] if height else []):
        placeholder = semantic in ("brightmap-emissive", "detail", "glow")
        explicit = semantic in ("height", "normal")
        selected = 1 if explicit else filtering
        layers.append({"binding": len(layers), "semantic": semantic,
                       "role": "fallback-placeholder" if placeholder else "authored-layer",
                       "requested_sampling": 1 if explicit else -1,
                       "source": {"lump": 0 if placeholder else 123,
                                  "width": 1 if placeholder else 64,
                                  "height": 1 if placeholder else 64},
                       "sampler": {"available": True, "min_filter": selected, "mag_filter": selected,
                                   "mipmap_mode": selected, "anisotropy": False}})
    return {"name": name, "shader": shader, "height_texture_index": len(layers) - 1 if height else -1,
            "resource": {"available": True, "index": 300, "generation": 4, "epoch": 2, "span": len(layers)},
            "layers": layers}, {"EffectState": shader, "NoFragmentShader": 0, "AlphaTestOnly": 0}


class SpecialSurfaceMaterialTests(unittest.TestCase):
    def test_authored_pbr_height_warp_and_heightless_controls_at_all_filter_phases(self):
        for name in ("S161PH", "S161PN", "S161WP", "S161HO", "S161NO", "S161GL", "S161T4"):
            for filtering in (0, 1):
                value, shader = material(name, filtering)
                with self.subTest(name=name, filtering=filtering):
                    self.assertEqual(gate._material(value, shader, 300, filtering),
                                     (300, 4, 2, len(value["layers"])))

    def test_wrong_shader_pipeline_never_passes_from_unchanged_rgb(self):
        for name in ("S161PH", "S161WP", "S161HO"):
            value, shader = material(name)
            shader["EffectState"] = 2 if name == "S161HO" else 0
            with self.subTest(name=name), self.assertRaisesRegex(EvidenceError, "pipeline shader"):
                gate._material(value, shader, 300, 0)

    def test_depth_only_or_alpha_only_submission_cannot_cover_shaded_material(self):
        for key in ("NoFragmentShader", "AlphaTestOnly"):
            value, shader = material()
            shader[key] = 1
            with self.subTest(key=key), self.assertRaises(EvidenceError):
                gate._material(value, shader, 300, 0)

    def test_material_inventory_cannot_replace_bound_descriptor(self):
        value, shader = material()
        with self.assertRaisesRegex(EvidenceError, "bound texture index"):
            gate._material(value, shader, 302, 0)
        for field in ("available", "index", "generation", "epoch", "span"):
            value, shader = material()
            value["resource"][field] = False if field == "available" else 0
            with self.subTest(field=field), self.assertRaises(EvidenceError):
                gate._material(value, shader, 300, 0)

    def test_semantics_binding_placeholder_and_per_layer_sampler_corruptions_fail(self):
        mutations = (
            lambda value: value.update(height_texture_index=-1),
            lambda value: value["layers"].pop(),
            lambda value: value["layers"][1].update(semantic="albedo"),
            lambda value: value["layers"][5]["source"].update(lump=99),
            lambda value: value["layers"][0].update(binding=1),
            lambda value: value["layers"][1]["sampler"].update(min_filter=0),
            lambda value: value["layers"][-1]["sampler"].update(mag_filter=0),
            lambda value: value["layers"][-1].update(requested_sampling=0),
            lambda value: value["resource"].update(span=1),
        )
        for mutation in mutations:
            value, shader = material()
            mutation(value)
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                gate._material(value, shader, 300, 0)

    def test_live_material_filter_change_must_be_observed_in_selected_sampler(self):
        value, shader = material(filtering=0)
        with self.assertRaisesRegex(EvidenceError, "actual per-layer sampler"):
            gate._material(value, shader, 300, 1)
        value, shader = material(filtering=1)
        with self.assertRaisesRegex(EvidenceError, "actual per-layer sampler"):
            gate._material(value, shader, 300, 0)


def full_raw():
    raw = lifecycle_raw()
    resources = {row["frame"]: row["data"] for row in raw["records"] if row["kind"] == "resource"}
    for frame in range(1, 97):
        second = frame > 48
        incarnation = (frame - 1) // 24
        resource_row = resources[frame]
        state = resource_row["lightmap_state"]
        # name,type,side,sector,control,actual binding type_index,plane,alpha,class
        specs = ([
            ("S161PH", 1, 3, 0, -1, 3, [1, 0, 0, 256], 1, "wall"),
            ("S161WP", 1, 4, 0, -1, 4, [1, 0, 0, 256], 1, "wall"),
            ("S161PN", 1, 5, 0, -1, 5, [1, 0, 0, 256], 1, "wall"),
            ("S161HO", 1, 7, 0, -1, 7, [1, 0, 0, 256], 1, "wall"),
            ("S161NO", 1, 8, 0, -1, 8, [1, 0, 0, 256], 1, "wall"),
            ("S161GL", 1, 9, 0, -1, 9, [1, 0, 0, 32], 0.5, "translucent-wall"),
            ("S161RF", 5, -1, 0, -1, 17, [0, 0, 1, 0], 0.75, "reflective-floor"),
        ] if not second else [
            ("S161T4", 5, -1, 6, 4, 77, [0, 0, 1, 48], 1, "three-d-floor-floor"),
            ("S161B5", 4, -1, 6, 5, 78, [0, 0, -1, -96], 1, "three-d-floor-ceiling"),
            ("S161S4", 1, 34, 1, 4, 34, [1, 0, 0, 1100], 1, "three-d-floor-side"),
            ("S161S5", 1, 34, 1, 5, 34, [1, 0, 0, 1100], 1, "three-d-floor-side"),
            ("S161PN", 2, 34, 1, -1, 34, [1, 0, 0, 1100], 1, "wall"),
            ("S161HO", 3, 34, 1, -1, 34, [1, 0, 0, 1100], 1, "wall"),
            ("SDVW", 1, 1, 0, -1, 1, [0, -1, 0, -192], 1, "wall"),
        ])
        tiles = []
        for ordinal, (tile_name, kind, _, _, control, type_index, _, _, _) in enumerate(specs):
            if tile_name == "S161GL":
                continue
            tiles.append({"tile": ordinal, "page": 0, "valid": True,
                          "receipt": {"owner": 100 + incarnation, "incarnation": ordinal + 10, "slot": ordinal},
                          "binding": {"type": kind, "type_index": type_index, "control_sector": control},
                          "dirty": {"initial": False, "geometry": False, "light": False}})
        state.update(live_tiles=len(tiles), valid_live_tiles=len(tiles), page_live_tiles=[len(tiles)], tile_receipts=tiles)
        census_by_ordinal = {tile["tile"]: tile for tile in tiles}
        if frame % 8:
            continue
        context = {"available": True, "map": "SDV161B" if second else "SDV161A", "root_type": "main",
                   "type": "main", "depth": 0, "epoch": 1 + incarnation, "identity": 1,
                   "parent_identity": 0, "producer": "root", "portal_group": 2 if second else 0,
                   "position": [1060, -176, 64] if second else [-192, 0, 64],
                   "angles": [180, 0, 0] if second else [270, 0, 0]}
        raw["records"].append({"kind": "context", "frame": frame, "count": 1, "data": {"context": copy.deepcopy(context)}})
        if second:
            reverse = dict(context, type="portal", depth=1, identity=2, parent_identity=1,
                           producer="LineToLine", portal_group=2, position=[36, -176, 64],
                           line_portal_selection={"available": True, "selected_span_index": 0,
                                                  "source_sector": 1, "destination_sector": 0,
                                                  "source_group": 2, "destination_group": 1,
                                                  "origin_line": 10, "destination_line": 3})
            raw["records"].append({"kind": "context", "frame": frame, "count": 1, "data": {"context": reverse}})
        if not second:
            mirror = dict(context, type="portal", depth=1, identity=2, parent_identity=1, producer="Mirror", line_mirror=True)
            raw["records"].append({"kind": "context", "frame": frame, "count": 1, "data": {"context": mirror}})
            plane_mirror = dict(context, type="portal", depth=1, identity=3, parent_identity=1, producer="PlaneMirror", plane_mirror=True)
            raw["records"].append({"kind": "context", "frame": frame, "count": 1, "data": {"context": plane_mirror}})
        filtering = int(17 <= frame <= 32 or 65 <= frame <= 80)
        for ordinal, (name, kind, side, sector, control, type_index, plane, alpha, cls) in enumerate(specs):
            bound, shader = material(name, filtering)
            bound["resource"]["index"] = 300 + ordinal * 16
            shader["UseLevelMesh"] = 1
            key = {"shader": shader}
            first = ordinal * 6
            if name != "SDVW":
                raw["records"].append({"kind": "pipeline", "frame": frame, "count": 1, "data": {
                    "producer": "levelmesh-indexed-range", "surface": "side" if kind < 4 else "flat",
                    "indexed": True, "first_index": first, "draw_count": 6, "key": copy.deepcopy(key),
                    "context": copy.deepcopy(context)}})
            value = {"producer": "levelmesh-surface-range", "class": cls,
                     "mesh_epoch": resource_row["levelmesh"]["epoch"], "surface_index": ordinal,
                     "context": copy.deepcopy(context), "key": key, "indexed": True, "draw_count": 6,
                     "first_index": first, "index_count": 6, "batch_first_index": first, "batch_index_count": 6,
                     "texture_index": bound["resource"]["index"], "material": bound, "alpha": alpha,
                     "owner": {"type": kind, "side": side, "sector": sector, "control_sector": control,
                               "type_index": type_index, "portal_group": 2 if second else 0},
                     "geometry": {"triangle_mapping_valid": True, "current_uv_valid": True, "current_uv_tolerance": 4.76837158203125e-7,
                                  "uv_scope": "synthetic current CPU UV witness", "plane": plane,
                                  "vertex_z_min": 144 if second and kind == 2 else 0,
                                  "vertex_z_max": 16 if second and kind == 3 else 160, "portal_index": 0, "is_sky": False, "vertex_first": first, "vertex_count": 6},
                     "lightmap": {"eligible": True, "tile": ordinal, "page": 0,
                                  "epoch": resource_row["lightmap_epoch"], "valid": True,
                                  "receipt": copy.deepcopy(census_by_ordinal.get(ordinal, {"receipt": {"owner": 0, "incarnation": 0, "slot": 0}})["receipt"])},
                     "probe": {"authored_index": -1, "runtime_irradiance_index": 0,
                               "fallback": True, "probe_epoch": resource_row["probe_epoch"],
                               "authored_scope": "not stored in mesh; no authored target claim"}}
            if name == "SDVW":
                value.update(producer="immediate-special-surface", context=copy.deepcopy(reverse),
                             indexed=False, draw_count=4, index_count=4)
                value["owner"]["portal_group"] = 1
                value["key"]["shader"]["UseLevelMesh"] = 0
                value["probe"]["authored_scope"] = "current immediate authored uniform selector"
            if name == "S161GL":
                value.update(producer="immediate-special-surface", indexed=False, draw_count=4, index_count=4)
                value["key"]["shader"]["UseLevelMesh"] = 0
                value["probe"]["authored_scope"] = "current immediate authored uniform selector"
                value["geometry"]["current_uv_valid"] = False
                value["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False)
            raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": value})
        if not second:
            receiver = next(row["data"] for row in raw["records"] if row["kind"] == "surface"
                            and row["frame"] == frame and row["data"]["material"]["name"] == "S161PH")
            decal = copy.deepcopy(receiver)
            bound, shader = material("S161DCL", filtering)
            bound["resource"]["index"] = 500
            shader["UseLevelMesh"] = 0
            decal.update(producer="immediate-special-surface", **{"class": "decal"},
                         material=bound, texture_index=500, key={"shader": shader}, indexed=False, draw_count=4, index_count=4)
            decal["probe"]["authored_scope"] = "current immediate authored uniform selector"
            raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": decal})
            for cls, side in (("horizon", 2), ("mirror", 6)):
                stencil = copy.deepcopy(decal)
                stencil.update(**{"class": cls}, texture_index=-1,
                               material={"material": {"available": False, "reason": "portal stencil does not shade a material"}},
                               probe={"available": False, "reason": "portal stencil does not shade a material"})
                stencil["owner"].update(type=0, side=side, type_index=side)
                stencil["geometry"]["current_uv_valid"] = False
                stencil["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                           receipt={"owner": 0, "incarnation": 0, "slot": 0})
                raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": stencil})
            for name, kind, plane in (("S161RF", 5, [0, 0, 1, 0]), ("SDVFL", 4, [0, 0, -1, -160])):
                contents = copy.deepcopy(decal)
                bound, shader = material(name, filtering)
                bound["resource"]["index"] = 520 if kind == 5 else 540
                shader["UseLevelMesh"] = 0
                contents.update(**{"class": "horizon-contents"}, material=bound,
                                texture_index=bound["resource"]["index"], key={"shader": shader}, alpha=1)
                contents["owner"].update(type=kind, type_index=2, side=2)
                contents["geometry"]["current_uv_valid"] = False
                contents["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                            receipt={"owner": 0, "incarnation": 0, "slot": 0})
                contents["geometry"].update(plane=plane)
                contents["probe"]["authored_index"] = 0  # Legal raw reset selector; actual runtime fallback remains zero.
                raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": contents})
        if second:
            stencil = copy.deepcopy(value)
            stencil.update(producer="immediate-special-surface", **{"class": "line-to-line-portal"},
                           texture_index=-1, material={"material": {"available": False, "reason": "portal stencil"}},
                           probe={"available": False, "reason": "portal stencil"}, indexed=False, draw_count=4, index_count=4)
            stencil["owner"].update(type=0, type_index=11, side=11, sector=1, control_sector=-1, portal_group=2)
            stencil["context"] = copy.deepcopy(context)
            stencil["key"]["shader"]["UseLevelMesh"] = 0
            stencil["geometry"]["current_uv_valid"] = False
            stencil["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                       receipt={"owner": 0, "incarnation": 0, "slot": 0})
            raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": stencil})
    return raw


def surface(raw, name="S161PH", frame=8):
    return next(row["data"] for row in raw["records"] if row["kind"] == "surface" and row["frame"] == frame
                and row["data"].get("material", {}).get("name") == name)


def portal_receiver_and_decal(raw, frame=8):
    context = next(row["data"]["context"] for row in raw["records"]
                   if row["kind"] == "context" and row["frame"] == frame
                   and row["data"]["context"].get("plane_mirror") is True)
    receiver = copy.deepcopy(surface(raw, "S161PH", frame))
    receiver.update(producer="immediate-special-surface", context=copy.deepcopy(context),
                    indexed=False, draw_count=4, index_count=4)
    receiver["key"]["shader"]["UseLevelMesh"] = 0
    receiver["probe"]["authored_scope"] = "current immediate authored uniform selector"
    decal = copy.deepcopy(surface(raw, "S161DCL", frame))
    decal["context"] = copy.deepcopy(context)
    for value in (receiver, decal):
        if "context" in value["material"]:
            value["material"]["context"] = copy.deepcopy(context)
        raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": value})
    return receiver, decal


def independent_receiver_tile(raw, value, frame):
    state = resource(raw, frame)["lightmap_state"]
    index = max(tile["tile"] for tile in state["tile_receipts"]) + 1
    receipt = {"owner": state["tile_receipts"][0]["receipt"]["owner"], "incarnation": 100 + index, "slot": 100 + index}
    state["tile_receipts"].append({"tile": index, "page": 0, "receipt": copy.deepcopy(receipt),
        "binding": {"type": value["owner"]["type"], "type_index": value["owner"]["type_index"],
                    "control_sector": value["owner"]["control_sector"]},
        "valid": True, "dirty": {"initial": False, "geometry": False, "light": False}})
    state["live_tiles"] += 1
    state["valid_live_tiles"] += 1
    state["page_live_tiles"][0] += 1
    value["lightmap"].update(eligible=True, tile=index, page=0, valid=True, receipt=copy.deepcopy(receipt))
    value["geometry"]["current_uv_valid"] = True


def ordinary_a_ceiling(raw):
    value = copy.deepcopy(surface(raw, "S161NO", 8))
    descriptor = surface(raw, "SDVFL", 8)
    value.update(**{"class": "flat"}, material=copy.deepcopy(descriptor["material"]), texture_index=descriptor["texture_index"])
    value["owner"].update(type=4, type_index=41, side=-1)
    value["geometry"]["plane"] = [0, 0, -1, -160]
    independent_receiver_tile(raw, value, 8)
    row = {"kind": "surface", "frame": 8, "count": 1, "data": value}
    raw["records"].append(row)
    return row


def additional_b_portal_wall(raw, name):
    source = next(row["data"] for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 56
                  and row["data"].get("material", {}).get("name") == name
                  and row["data"]["producer"] == "levelmesh-surface-range"
                  and row["data"]["context"]["type"] == "main" and row["data"]["owner"]["side"] == 34)
    value = copy.deepcopy(source)
    context = dict(source["context"], type="portal", producer="LineToLine", depth=2, identity=17, parent_identity=2,
        line_portal_selection={"available": True, "selected_span_index": 0, "origin_line": 3, "destination_line": 10,
                               "source_sector": 0, "destination_sector": 1, "source_group": 1, "destination_group": 2})
    value.update(producer="immediate-special-surface", **{"class": "wall"}, indexed=False,
                 draw_count=4, index_count=4, context=context)
    value["key"]["shader"]["UseLevelMesh"] = 0
    value["probe"]["authored_scope"] = "current immediate authored uniform selector"
    if "context" in value["material"]: value["material"]["context"] = copy.deepcopy(context)
    index = next(index for index, row in enumerate(raw["records"]) if row.get("data") is source)
    row = {"kind": "surface", "frame": 56, "count": 1, "data": value}
    raw["records"].insert(index, row)
    return row


class SubmittedSpecialSurfaceTests(unittest.TestCase):
    def validate(self, raw):
        return gate.validate_transition_records(raw, stdout(), native_recipe())

    def test_complete_same_attempt_submissions_across_both_reloads_pass(self):
        raw = full_raw()
        result = self.validate(raw)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["submitted_surfaces"]["witness_frames"], list(range(8, 97, 8)))
        self.assertEqual(len(result["resource_owners"]), 4)
        for row in raw["records"]:
            if row["kind"] == "surface":
                gate.validate_surface_record(row["data"])

    def test_each_witness_requires_every_authored_material_and_special_class(self):
        for name, frame in (("S161PH", 8), ("S161WP", 24), ("S161PN", 32), ("S161HO", 40),
                            ("S161NO", 48), ("S161DCL", 16), ("S161GL", 8), ("S161RF", 8),
                            ("S161T4", 56), ("S161B5", 80), ("S161S4", 88), ("S161S5", 96)):
            raw = full_raw()
            raw["records"] = [row for row in raw["records"] if not (row["kind"] == "surface" and row["frame"] == frame
                              and row["data"].get("material", {}).get("name") == name)]
            with self.subTest(name=name, frame=frame), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_wrong_pipeline_path_range_or_mesh_owner_fails_with_unchanged_rgb(self):
        mutations = (
            lambda value: value.update(producer="cpu-map-inventory"),
            lambda value: value.update(producer="immediate-special-surface"),
            lambda value: value.update(indexed=False),
            lambda value: value.update(first_index=999),
            lambda value: value.update(batch_first_index=999),
            lambda value: value.update(draw_count=0),
            lambda value: value.update(mesh_epoch=6),
            lambda value: value["key"]["shader"].update(EffectState=0),
            lambda value: value["key"]["shader"].update(UseLevelMesh=0),
            lambda value: value["key"]["shader"].update(NoFragmentShader=1),
            lambda value: value["geometry"].update(triangle_mapping_valid=False),
            lambda value: value["geometry"].update(current_uv_valid=False),
            lambda value: value["geometry"].update(current_uv_tolerance=1 / 1024),
        )
        for mutation in mutations:
            raw = full_raw()
            mutation(surface(raw))
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_same_frame_parent_batch_context_and_pipeline_are_required(self):
        for edit in ("missing", "frame", "context", "pipeline"):
            raw = full_raw()
            row = next(row for row in raw["records"] if row["kind"] == "pipeline" and row["frame"] == 8)
            if edit == "missing": raw["records"].remove(row)
            elif edit == "frame": row["frame"] = 16
            elif edit == "context": row["data"]["context"]["identity"] = 50
            else: row["data"]["key"]["shader"]["EffectState"] = 0
            with self.subTest(edit=edit), self.assertRaisesRegex(EvidenceError, "same-frame actual parent"):
                self.validate(raw)

    def test_current_receipt_incarnation_page_and_binding_are_independent_of_rgb(self):
        mutations = (
            lambda value: value["lightmap"].update(valid=False),
            lambda value: value["lightmap"].update(epoch=2),
            lambda value: value["lightmap"].update(page=1),
            lambda value: value["lightmap"].update(tile=1),
            lambda value: value["lightmap"]["receipt"].update(owner=99),
            lambda value: value["lightmap"]["receipt"].update(incarnation=9),
            lambda value: value["lightmap"]["receipt"].update(slot=1),
            lambda value: value["owner"].update(type_index=4),
            lambda value: value["owner"].update(control_sector=4),
        )
        for mutation in mutations:
            raw = full_raw()
            mutation(surface(raw))
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError): self.validate(raw)

    def test_3d_floor_controls_planes_subsectors_and_portal_ownership_are_exact(self):
        mutations = (
            lambda value: value["owner"].update(control_sector=4),
            lambda value: value["owner"].update(sector=4),
            lambda value: value["owner"].update(portal_group=1),
            lambda value: value["owner"].update(type=5),
            lambda value: value["geometry"].update(plane=[0, 0, -1, -112]),
            lambda value: value["geometry"].update(plane=[0, 0, 1, 96]),
            lambda value: value["geometry"].update(portal_index=3),
            lambda value: value["geometry"].update(is_sky=True),
            lambda value: value["context"].update(producer="LineToLine"),
            lambda value: value["context"].update(portal_group=1),
        )
        for mutation in mutations:
            raw = full_raw()
            mutation(surface(raw, "S161B5", 56))
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError): self.validate(raw)

    def test_ordinary_a_ceiling_has_its_own_current_tile_and_cannot_hide_bad_neighbor(self):
        raw = full_raw()
        ceiling = ordinary_a_ceiling(raw)
        self.validate(raw)
        self.assertNotEqual(ceiling["data"]["lightmap"]["tile"], surface(raw, "S161NO")["lightmap"]["tile"])
        for edit in ("coherent-material", "unsupported-class"):
            for position in ("before", "after"):
                changed = copy.deepcopy(raw)
                wrong = copy.deepcopy(ceiling)
                if edit == "coherent-material":
                    donor = surface(raw, "S161NO")
                    wrong["data"]["material"] = copy.deepcopy(donor["material"])
                    wrong["data"]["texture_index"] = donor["texture_index"]
                    reason = "A ordinary ceiling owner/material"
                else:
                    wrong["data"]["class"] = "unsupported-flat-path"
                    reason = "A ordinary wall owner/material"
                index = changed["records"].index(ceiling)
                changed["records"].insert(index + (position == "after"), wrong)
                with self.subTest(edit=edit, position=position), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(changed)

    def test_b_main_mesh_presence_accepts_valid_additional_immediate_walls_but_validates_each_owner(self):
        for name in ("S161S4", "S161S5", "S161PN", "S161HO"):
            raw = full_raw()
            portal = additional_b_portal_wall(raw, name)
            self.validate(raw)
            portal["data"]["owner"]["sector"] = 0
            with self.subTest(name=name), self.assertRaisesRegex(EvidenceError, "B target side owner"):
                self.validate(raw)

    def test_b_main_mesh_receivers_and_reverse_immediate_portal_are_distinct_real_paths(self):
        raw = full_raw()
        self.validate(raw)
        for name in ("S161T4", "S161B5", "S161S4", "S161S5", "S161PN", "S161HO"):
            value = surface(raw, name, 56)
            self.assertEqual((value["producer"], value["context"]["type"], value["context"]["depth"],
                              value["context"]["portal_group"]), ("levelmesh-surface-range", "main", 0, 2))
        receiver = surface(raw, "SDVW", 56)
        self.assertEqual((receiver["producer"], receiver["context"]["producer"], receiver["owner"]["portal_group"]),
                         ("immediate-special-surface", "LineToLine", 1))
        self.assertEqual(receiver["context"]["position"], [36, -176, 64])
        self.assertEqual(receiver["context"]["angles"], [180, 0, 0])
        self.assertTrue(receiver["geometry"]["current_uv_valid"])

    def test_a_portal_context_cannot_satisfy_required_b_main_mesh_even_with_matching_parent(self):
        raw = full_raw()
        value = surface(raw, "S161T4", 56)
        context = dict(value["context"], type="portal", producer="LineToLine", depth=1,
                       identity=17, parent_identity=1)
        value["context"] = copy.deepcopy(context)
        parent = next(row["data"] for row in raw["records"] if row["kind"] == "pipeline" and row["frame"] == 56
                      and row["data"]["first_index"] == value["batch_first_index"])
        parent["context"] = copy.deepcopy(context)
        with self.assertRaisesRegex(EvidenceError, "main LevelMesh S161T4 3D-floor plane"):
            self.validate(raw)

    def test_reverse_portal_needs_actual_current_receiver_even_with_valid_context_and_stencil(self):
        edits = ("missing", "wrong-material", "wrong-owner", "wrong-group", "wrong-path",
                 "wrong-position", "wrong-hardware-angle", "wrong-destination-group", "wrong-origin-line",
                 "unlightmapped", "stale-uv", "stale-receipt")
        for edit in edits:
            raw = full_raw()
            receiver = surface(raw, "SDVW", 56)
            wrong = copy.deepcopy(receiver)
            reason = "reverse portal receiver"
            if edit == "missing":
                raw["records"] = [row for row in raw["records"] if row.get("data") is not receiver]
                reason = "reverse linked-portal receiving wall"
            else:
                if edit == "wrong-material":
                    donor = surface(raw, "S161S4", 56)
                    wrong["material"] = copy.deepcopy(donor["material"])
                    wrong["texture_index"] = donor["texture_index"]
                    reason = "B receiver owner/material"
                elif edit == "wrong-owner":
                    wrong["owner"]["sector"] = 1
                    reason = "B target side owner"
                elif edit == "wrong-group":
                    wrong["owner"]["portal_group"] = 2
                    reason = "B target side owner"
                elif edit == "wrong-path": wrong["context"]["producer"] = "Mirror"
                elif edit == "wrong-position":
                    wrong["context"]["position"] = [36, 0, 64]
                    reason = "reverse portal context position"
                elif edit == "wrong-hardware-angle":
                    wrong["context"]["angles"] = [90, 0, 0]
                    reason = "reverse portal context angles"
                elif edit == "wrong-destination-group":
                    wrong["context"]["line_portal_selection"]["destination_group"] = 2
                elif edit == "wrong-origin-line":
                    wrong["context"]["line_portal_selection"]["origin_line"] = 3
                elif edit == "unlightmapped":
                    wrong["geometry"]["current_uv_valid"] = False
                    wrong["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                             receipt={"owner": 0, "incarnation": 0, "slot": 0})
                elif edit == "stale-uv":
                    wrong["geometry"]["current_uv_valid"] = False
                    reason = "receiver UVs do not match"
                else:
                    wrong["lightmap"]["receipt"]["incarnation"] += 1
                    reason = "stale page/allocation incarnation"
                raw["records"].append({"kind": "surface", "frame": 56, "count": 1, "data": wrong})
            with self.subTest(edit=edit), self.assertRaisesRegex(EvidenceError, reason):
                self.validate(raw)

    def test_b_ordinary_upper_lower_require_actual_current_slots_and_height_bands(self):
        result = self.validate(full_raw())
        for frame in (56, 64, 72, 80, 88, 96):
            bands = result["submitted_surfaces"]["frames"][frame]["ordinary_wall_bands"]
            self.assertEqual((bands["S161PN"]["type"], bands["S161PN"]["vertex_z_min"], bands["S161PN"]["vertex_z_max"]),
                             (2, 144, 160))
            self.assertEqual((bands["S161HO"]["type"], bands["S161HO"]["vertex_z_min"], bands["S161HO"]["vertex_z_max"]),
                             (3, 0, 16))
        for name, frame in (("S161PN", 56), ("S161HO", 96)):
            raw = full_raw()
            raw["records"] = [row for row in raw["records"] if not (row["kind"] == "surface" and row["frame"] == frame
                              and row["data"].get("material", {}).get("name") == name)]
            with self.subTest(missing=name), self.assertRaisesRegex(EvidenceError, "ordinary upper/lower"):
                self.validate(raw)

    def test_b_ordinary_band_cannot_be_a_midwall_3d_control_or_unlightmapped_fallback(self):
        for name in ("S161PN", "S161HO"):
            for mutation in ("mid-slot", "controlled", "class", "unlightmapped", "height"):
                raw = full_raw()
                value = surface(raw, name, 56)
                tile = next(tile for tile in resource(raw, 56)["lightmap_state"]["tile_receipts"]
                            if tile["tile"] == value["lightmap"]["tile"])
                if mutation == "mid-slot":
                    value["owner"]["type"] = tile["binding"]["type"] = 1
                elif mutation == "controlled":
                    value["owner"]["control_sector"] = tile["binding"]["control_sector"] = 4
                elif mutation == "class": value["class"] = "three-d-floor-side"
                elif mutation == "unlightmapped":
                    value["geometry"]["current_uv_valid"] = False
                    value["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                             receipt={"owner": 0, "incarnation": 0, "slot": 0})
                else: value["geometry"].update(vertex_z_min=32, vertex_z_max=48)
                reason = ("B receiver owner/material" if mutation in ("mid-slot", "controlled", "class")
                          else "ordinary upper/lower")
                with self.subTest(name=name, mutation=mutation), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(raw)

    def test_no_missing_or_cross_attempt_tile_census_can_back_a_draw(self):
        for edit in ("missing", "truncated", "duplicate", "stale-owner", "dirty"):
            raw = full_raw()
            state = resource(raw, 8)["lightmap_state"]
            if edit == "missing": state.pop("tile_receipts")
            elif edit == "truncated": state["tile_receipts"].pop()
            elif edit == "duplicate": state["tile_receipts"][1] = copy.deepcopy(state["tile_receipts"][0])
            elif edit == "stale-owner": state["tile_receipts"][0]["receipt"]["owner"] = 99
            else: state["tile_receipts"][0]["dirty"]["initial"] = True
            with self.subTest(edit=edit), self.assertRaises(EvidenceError): self.validate(raw)

    def test_explicit_fallback_and_special_material_alpha_are_not_inferred_from_image(self):
        for name, edit in (("S161PH", "probe"), ("S161GL", "alpha"), ("S161RF", "alpha"), ("S161DCL", "receiver")):
            raw = full_raw()
            value = surface(raw, name)
            if edit == "probe": value["probe"].update(authored_index=0, runtime_irradiance_index=300, fallback=False)
            elif edit == "alpha": value["alpha"] = 1
            else: value["owner"]["side"] = 4
            with self.subTest(name=name, edit=edit), self.assertRaises(EvidenceError): self.validate(raw)


    def test_horizon_contents_reflection_and_stencils_require_their_actual_producers(self):
        for missing in ("horizon", "mirror", "horizon-floor-contents", "horizon-ceiling-contents", "plane-mirror", "line-to-line-portal"):
            raw = full_raw()
            frame = 56 if missing == "line-to-line-portal" else 8
            def remove(row):
                if row["frame"] != frame:
                    return False
                if missing == "plane-mirror":
                    return row["kind"] == "context" and row["data"]["context"].get("plane_mirror") is True
                if row["kind"] != "surface":
                    return False
                value = row["data"]
                if missing.startswith("horizon-"):
                    kind = 5 if missing == "horizon-floor-contents" else 4
                    return value.get("class") == "horizon-contents" and value["owner"]["type"] == kind
                return value.get("class") == missing
            raw["records"] = [row for row in raw["records"] if not remove(row)]
            with self.subTest(missing=missing), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_horizon_real_material_plane_and_no_tile_policy_are_exact(self):
        for edit in ("plane", "alpha", "source-side", "range", "sampler"):
            raw = full_raw()
            value = next(row["data"] for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 8
                         and row["data"].get("class") == "horizon-contents" and row["data"]["owner"]["type"] == 4)
            if edit == "plane": value["geometry"]["plane"] = [0, 0, -1, -112]
            elif edit == "alpha": value["alpha"] = 0.75
            elif edit == "source-side": value["owner"]["side"] = 6
            elif edit == "range": value["geometry"]["vertex_count"] = 3
            else: value["material"]["layers"][0]["sampler"]["min_filter"] = 1
            with self.subTest(edit=edit), self.assertRaises(EvidenceError):
                self.validate(raw)

    def test_portal_decal_joins_actual_immediate_receiver_in_its_own_context(self):
        raw = full_raw()
        receiver, decal = portal_receiver_and_decal(raw)
        self.assertEqual(receiver["lightmap"], decal["lightmap"])
        self.assertEqual(receiver["context"], decal["context"])
        self.assertEqual(receiver["producer"], "immediate-special-surface")
        self.validate(raw)

    def test_portal_decal_cannot_use_another_context_material_or_receiving_owner(self):
        for edit in ("wrong-context", "wrong-material", "wrong-receiver", "missing-receiver", "bad-neighbor"):
            raw = full_raw()
            receiver, decal = portal_receiver_and_decal(raw)
            reason = "decal row has wrong material/owner/current receiver context"
            if edit == "wrong-context":
                decal["context"] = copy.deepcopy(next(row["data"]["context"] for row in raw["records"]
                    if row["kind"] == "context" and row["frame"] == 8
                    and row["data"]["context"].get("line_mirror") is True))
            elif edit == "wrong-material":
                donor = surface(raw, "S161PN")
                receiver["material"] = copy.deepcopy(donor["material"])
                receiver["texture_index"] = donor["texture_index"]
                reason = "A ordinary wall owner/material"
            elif edit == "wrong-receiver":
                receiver["owner"]["sector"] = 1
                reason = "A submitted owner differs"
            elif edit == "missing-receiver":
                raw["records"] = [row for row in raw["records"] if row.get("data") is not receiver]
            else:
                wrong = copy.deepcopy(decal)
                wrong["context"] = copy.deepcopy(surface(raw, "S161PH")["context"])
                wrong["context"]["identity"] = 99
                raw["records"].append({"kind": "surface", "frame": 8, "count": 1, "data": wrong})
            with self.subTest(edit=edit), self.assertRaisesRegex(EvidenceError, reason):
                self.validate(raw)

    def test_portal_decal_does_not_replace_main_decal_or_main_mesh_receiver(self):
        for missing in ("decal", "mesh-receiver"):
            raw = full_raw()
            portal_receiver_and_decal(raw)
            name = "S161DCL" if missing == "decal" else "S161PH"
            raw["records"] = [row for row in raw["records"] if not (row["kind"] == "surface" and row["frame"] == 8
                and row["data"].get("material", {}).get("name") == name
                and row["data"]["context"]["type"] == "main")]
            with self.subTest(missing=missing), self.assertRaisesRegex(EvidenceError, "main-view"):
                self.validate(raw)

    def test_repeated_correct_special_rows_are_admitted(self):
        raw = full_raw()
        repeated = [copy.deepcopy(row) for row in raw["records"]
                    if row["kind"] == "surface" and row["frame"] == 8
                    and row["data"].get("class") in ("decal", "reflective-floor", "horizon-contents")]
        self.assertEqual(len(repeated), 4)
        for row in repeated:
            index = raw["records"].index(row)
            raw["records"][index:index + 1] = [copy.deepcopy(row), row, copy.deepcopy(row)]
        self.validate(raw)

    def test_coherent_wrong_special_material_cannot_hide_beside_correct_neighbor(self):
        cases = (("decal", 1, "decal row has wrong material"),
                 ("reflective-floor", 5, "reflective-floor row has wrong material"),
                 ("horizon-contents", 4, "horizon-contents row has wrong material"),
                 ("horizon-contents", 5, "horizon-contents row has wrong material"))
        for cls, kind, reason in cases:
            for position in ("before", "after"):
                raw = full_raw()
                records = raw["records"]
                index = next(index for index, row in enumerate(records)
                             if row["kind"] == "surface" and row["frame"] == 8
                             and row["data"].get("class") == cls and row["data"]["owner"]["type"] == kind)
                original = copy.deepcopy(records[index])
                wrong = copy.deepcopy(original)
                coherent = surface(raw, "S161NO")
                wrong["data"]["material"] = copy.deepcopy(coherent["material"])
                wrong["data"]["texture_index"] = coherent["texture_index"]
                records.insert(index + (position == "after"), wrong)
                self.assertIn(original, records)
                self.assertEqual(wrong["data"]["material"], coherent["material"])
                with self.subTest(cls=cls, kind=kind, position=position), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(raw)

    def test_repeated_correct_ordinary_and_controlled_receivers_are_admitted(self):
        raw = full_raw()
        repeated = [copy.deepcopy(row) for row in raw["records"]
                    if row["kind"] == "surface" and row["frame"] in (8, 56)
                    and row["data"]["producer"] == "levelmesh-surface-range"]
        for row in repeated:
            index = raw["records"].index(row)
            raw["records"][index:index + 1] = [copy.deepcopy(row), row, copy.deepcopy(row)]
        self.validate(raw)

    def test_coherent_owner_material_substitution_cannot_hide_beside_good_wall_or_control(self):
        cases = ((8, "S161PH", "S161PN", "A ordinary wall owner/material"),
                 (56, "S161T4", "S161B5", "B receiver owner/material"),
                 (56, "S161B5", "S161T4", "B receiver owner/material"),
                 (56, "S161S4", "S161S5", "B receiver owner/material"),
                 (56, "S161S5", "S161S4", "B receiver owner/material"),
                 (56, "S161HO", "S161B5", "B receiver owner/material"))
        for frame, name, donor_name, reason in cases:
            for position in ("before", "after"):
                raw = full_raw()
                records = raw["records"]
                index = next(index for index, row in enumerate(records)
                             if row["kind"] == "surface" and row["frame"] == frame
                             and row["data"].get("material", {}).get("name") == name)
                original = copy.deepcopy(records[index])
                wrong = copy.deepcopy(original)
                donor = surface(raw, donor_name, frame)
                self.assertEqual(wrong["data"]["material"]["shader"], donor["material"]["shader"])
                wrong["data"]["material"] = copy.deepcopy(donor["material"])
                wrong["data"]["texture_index"] = donor["texture_index"]
                records.insert(index + (position == "after"), wrong)
                self.assertIn(original, records)
                with self.subTest(name=name, donor=donor_name, position=position), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(raw)

    def test_owner_fields_cannot_skip_known_wall_side_or_controlled_class_dispatch(self):
        namespace = "another side/sector/control namespace"
        cases = ((8, "S161PH", "S161PN", "sector", 1, "A submitted owner differs"),
                 (8, "S161PH", "S161PN", "portal_group", 2, "A submitted owner differs"),
                 (8, "S161PH", "S161PN", "control_sector", 4, namespace),
                 (8, "S161PH", "S161PN", "type", 2, namespace),
                 (8, "S161PH", "S161PN", "side", 99, "A ordinary wall owner/material"),
                 (56, "S161T4", "S161B5", "sector", 0, "B controlled flat owner/type"),
                 (56, "S161T4", "S161B5", "portal_group", 0, "B controlled flat owner/type"),
                 (56, "S161T4", "S161B5", "control_sector", -1, namespace),
                 (56, "S161T4", "S161B5", "type", 4, namespace),
                 (56, "S161T4", "S161B5", "side", 34, "B controlled flat owner/type"),
                 (56, "S161S4", "S161S5", "sector", 6, "B target side owner"),
                 (56, "S161S4", "S161S5", "portal_group", 0, "B target side owner"),
                 (56, "S161S4", "S161S5", "control_sector", -1, namespace),
                 (56, "S161S4", "S161S5", "type", 2, namespace),
                 (56, "S161S4", "S161S5", "side", 99, "B target side owner"))
        for frame, name, donor_name, field, replacement, reason in cases:
            for position in ("before", "after"):
                raw = full_raw()
                records = raw["records"]
                index = next(index for index, row in enumerate(records)
                             if row["kind"] == "surface" and row["frame"] == frame
                             and row["data"].get("material", {}).get("name") == name)
                original = copy.deepcopy(records[index])
                wrong = copy.deepcopy(original)
                donor = surface(raw, donor_name, frame)
                wrong["data"]["material"] = copy.deepcopy(donor["material"])
                wrong["data"]["texture_index"] = donor["texture_index"]
                wrong["data"]["owner"][field] = replacement
                records.insert(index + (position == "after"), wrong)
                self.assertIn(original, records)
                with self.subTest(name=name, field=field, position=position), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(raw)

    def test_complete_b_ordinary_owner_cells_reject_coherent_bad_neighbors_outside_target_anchors(self):
        for cell in ("ordinary-control-wall", "ordinary-control-flat"):
            for position in ("before", "after"):
                raw = full_raw()
                source = surface(raw, "S161S4" if cell.endswith("wall") else "S161T4", 56)
                ordinary = copy.deepcopy(source)
                ordinary["class"] = "wall" if cell.endswith("wall") else "flat"
                if cell.endswith("wall"):
                    ordinary["owner"].update(type=1, type_index=20, side=20, sector=4, control_sector=-1, portal_group=0)
                    ordinary["geometry"]["plane"] = [1, 0, 0, 1600]
                else:
                    ordinary["owner"].update(type=4, type_index=99, side=-1, sector=4, control_sector=-1, portal_group=0)
                    ordinary["geometry"]["plane"] = [0, 0, -1, -48]
                state = resource(raw, 56)["lightmap_state"]
                index = max(tile["tile"] for tile in state["tile_receipts"]) + 1
                receipt = {"owner": state["tile_receipts"][0]["receipt"]["owner"], "incarnation": 90, "slot": 90}
                state["tile_receipts"].append({"tile": index, "page": 0, "receipt": receipt,
                    "binding": {"type": ordinary["owner"]["type"], "type_index": ordinary["owner"]["type_index"], "control_sector": -1},
                    "valid": True, "dirty": {"initial": False, "geometry": False, "light": False}})
                state["live_tiles"] += 1
                state["valid_live_tiles"] += 1
                state["page_live_tiles"][0] += 1
                ordinary["lightmap"].update(tile=index, receipt=copy.deepcopy(receipt))
                row = {"kind": "surface", "frame": 56, "count": 1, "data": ordinary}
                raw["records"].append(row)
                self.validate(raw)
                for edit in ("material", "sector", "portal_group"):
                    changed = copy.deepcopy(raw)
                    wrong = copy.deepcopy(row)
                    donor = surface(raw, "S161S5", 56)
                    wrong["data"]["material"] = copy.deepcopy(donor["material"])
                    wrong["data"]["texture_index"] = donor["texture_index"]
                    if edit == "sector":
                        wrong["data"]["owner"].update(sector=6, portal_group=2)
                    elif edit == "portal_group":
                        wrong["data"]["owner"]["portal_group"] = 2
                    index = changed["records"].index(row)
                    changed["records"].insert(index + (position == "after"), wrong)
                    if cell.endswith("wall"):
                        reason = "B receiver owner/material" if edit == "material" else "B target side owner"
                    else:
                        reason = "B ordinary flat owner/type" if edit == "portal_group" else "B ordinary flat material"
                    with self.subTest(cell=cell, position=position, edit=edit), self.assertRaisesRegex(EvidenceError, reason):
                        self.validate(changed)

    def test_ordinary_control_sector_geometry_is_not_misclassified_as_a_controlled_receiver(self):
        raw = full_raw()
        draws = [(row["data"], (row["data"]["lightmap"]["tile"],) if row["data"]["lightmap"]["eligible"] else None)
                 for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 56]
        ordinary = copy.deepcopy(surface(raw, "S161T4", 56))
        ordinary["class"] = "flat"
        ordinary["owner"].update(type=4, sector=4, control_sector=-1, portal_group=0)
        ordinary["geometry"]["plane"] = [0, 0, -1, -48]
        gate._require_b_surfaces(56, draws + [(ordinary, (99,))], raw)

    def test_semantic_dispatch_asserts_type_control_and_side_index_before_material_lookup(self):
        raw = full_raw()
        draws = [(row["data"], (row["data"]["lightmap"]["tile"],) if row["data"]["lightmap"]["eligible"] else None)
                 for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 56]
        for name, field, value, reason in (("S161T4", "control_sector", -1, "controlled flat owner/type"),
                                           ("S161T4", "type", 1, "controlled flat owner/type"),
                                           ("S161S4", "control_sector", -1, "receiver owner/material"),
                                           ("S161S4", "type", 2, "receiver owner/material"),
                                           ("S161S4", "type_index", 28, "target side owner")):
            wrong = copy.deepcopy(surface(raw, name, 56))
            wrong["owner"][field] = value
            with self.subTest(name=name, field=field), self.assertRaisesRegex(EvidenceError, reason):
                gate._require_b_surfaces(56, draws + [(wrong, (99,))], raw)

    def test_b_authored_owner_guard_covers_all_target_front_sides_and_slab_planes(self):
        raw = full_raw()
        draws = [(row["data"], (row["data"]["lightmap"]["tile"],) if row["data"]["lightmap"]["eligible"] else None)
                 for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 56]
        cells = []
        for side in (28, 30, 32, 34):
            for name, kind, control in (("S161S4", 1, 4), ("S161S5", 1, 5),
                                        ("S161PN", 2, -1), ("S161HO", 3, -1)):
                value = copy.deepcopy(surface(raw, name, 56))
                value["owner"].update(side=side, type_index=side, type=kind, control_sector=control)
                cells.append(value)
        for control, bottom, top in ((4, 32, 48), (5, 96, 112)):
            for kind, name, z, normal in ((4, f"S161B{control}", bottom, -1),
                                           (5, f"S161T{control}", top, 1)):
                value = copy.deepcopy(surface(raw, "S161T4", 56))
                value["owner"].update(type=kind, control_sector=control)
                value["class"] = "three-d-floor-ceiling" if kind == 4 else "three-d-floor-floor"
                value["material"]["name"] = name
                value["geometry"]["plane"] = [0, 0, normal, normal * z]
                cells.append(value)
        # Exercise admission for observed cells; this does not require their visibility.
        for value in cells:
            gate._require_b_surfaces(56, draws + [(value, (99,))], raw)
            wrong = copy.deepcopy(value)
            wrong["material"]["name"] = "S161NO"
            with self.subTest(owner=value["owner"]), self.assertRaisesRegex(EvidenceError, "B receiver owner/material"):
                gate._require_b_surfaces(56, draws + [(wrong, (99,))], raw)

    def test_each_horizon_row_has_exact_owner_type_and_plane_with_correct_neighbor(self):
        edits = (("side", 6), ("type_index", 6), ("sector", 1),
                 ("control_sector", 4), ("portal_group", 2), ("type", 1))
        for field, replacement in edits:
            for position in ("before", "after"):
                raw = full_raw()
                records = raw["records"]
                index = next(index for index, row in enumerate(records)
                             if row["kind"] == "surface" and row["frame"] == 8
                             and row["data"].get("class") == "horizon-contents"
                             and row["data"]["owner"]["type"] == 4)
                wrong = copy.deepcopy(records[index])
                wrong["data"]["owner"][field] = replacement
                records.insert(index + (position == "after"), wrong)
                reason = ("A submitted owner differs" if field in ("sector", "control_sector", "portal_group")
                          else "horizon-contents row has wrong material/type/owner")
                with self.subTest(field=field, position=position), self.assertRaisesRegex(EvidenceError, reason):
                    self.validate(raw)
        raw = full_raw()
        correct = next(row for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 8
                       and row["data"].get("class") == "horizon-contents" and row["data"]["owner"]["type"] == 4)
        wrong = copy.deepcopy(correct)
        wrong["data"]["geometry"]["plane"] = [0, 0, -1, -112]
        raw["records"].append(wrong)
        with self.assertRaisesRegex(EvidenceError, "selected/flipped control plane"):
            self.validate(raw)

    def test_rgb_equality_cannot_rescue_a_wrong_submitted_shader(self):
        from pathlib import Path
        import tempfile
        from tools.renderer_oracle.tests.test_sdvk161_checkpoints import write_images
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / "left", Path(directory) / "right"
            left.mkdir(); right.mkdir()
            write_images(left, width=2, height=1)
            write_images(right, width=2, height=1)
            self.assertEqual(gate.compare_checkpoint_images(left, right)["status"], "PASS")
            raw = full_raw()
            surface(raw)["key"]["shader"]["EffectState"] = 0
            with self.assertRaisesRegex(EvidenceError, "shader disagrees"):
                self.validate(raw)


class CapturedSpecialSurfaceNegativeTests(unittest.TestCase):
    def test_real_control_code_rejects_twenty_one_copies_without_mutating_admitted_source(self):
        raw = full_raw()
        original = copy.deepcopy(raw)
        result = gate.captured_negatives(raw, stdout(), native_recipe())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["controls"]), 21)
        self.assertTrue(all(control["status"] == "REJECTED" and control["reason"]
                            and len(control["mutant_sha256"]) == 64 for control in result["controls"]))
        self.assertEqual(raw, original)
        self.assertFalse(result["native_execution"])

    def test_captured_special_material_controls_select_the_actual_class_and_owner(self):
        raw = full_raw()
        ceiling = next(row for row in raw["records"] if row["kind"] == "surface" and row["frame"] == 8
                       and row["data"].get("class") == "horizon-contents" and row["data"]["owner"]["type"] == 4)
        unrelated = copy.deepcopy(ceiling)
        unrelated["data"]["class"] = "flat"
        unrelated["data"]["owner"]["side"] = -1
        unrelated["data"]["material"]["resource"]["index"] = 560
        unrelated["data"]["texture_index"] = 560
        raw["records"].insert(0, unrelated)
        result = gate.captured_negatives(raw, stdout(), native_recipe())
        controls = {item["name"]: item for item in result["controls"]}
        for name, cls, kind, side in (("wrong-actual-horizon-material", "horizon-contents", 4, 2),
                                      ("wrong-actual-decal-material", "decal", 1, 3),
                                      ("wrong-actual-reflective-floor-material", "reflective-floor", 5, -1),
                                      ("wrong-actual-ordinary-wall-material", "wall", 1, 3)):
            control = controls[name]
            target = raw["records"][control["record_index"]]["data"]
            self.assertEqual((target["class"], target["owner"]["type"], target["owner"]["side"]),
                             (cls, kind, side))
            donor = raw["records"][control["source_record_index"]]
            self.assertEqual((donor["frame"], control["source_frame"], control["source_material"]),
                             (8, 8, "S161PN" if cls == "wall" else "S161NO"))
            self.assertEqual(control["after"], {"material": donor["data"]["material"],
                                               "texture_index": donor["data"]["texture_index"]})
            self.assertEqual(control["before"], {"material": target["material"],
                                                "texture_index": target["texture_index"]})
            self.assertIn("A ordinary wall owner/material" if cls == "wall" else cls + " row has wrong material",
                          control["reason"])

    def test_all_captured_controls_reject_intended_invariants_with_repeated_correct_special_rows(self):
        raw = full_raw()
        repeated = [copy.deepcopy(row) for row in raw["records"]
                    if row["kind"] == "surface" and row["frame"] == 8
                    and row["data"].get("class") in ("wall", "decal", "reflective-floor", "horizon-contents")]
        for row in repeated:
            index = raw["records"].index(row)
            raw["records"][index:index + 1] = [copy.deepcopy(row), row, copy.deepcopy(row)]
        original = copy.deepcopy(raw)
        baseline = gate.captured_negatives(full_raw(), stdout(), native_recipe())
        result = gate.captured_negatives(raw, stdout(), native_recipe())
        self.assertEqual(len(result["controls"]), 21)
        self.assertEqual({item["name"] for item in result["controls"]},
                         {item["name"] for item in baseline["controls"]})
        self.assertTrue(all(item["status"] == "REJECTED" for item in result["controls"]))
        self.assertEqual(raw, original)

    def test_captured_b_targets_are_required_main_receivers_despite_earlier_ordinary_or_portal_rows(self):
        raw = full_raw()
        for name, sector, side, kind, plane in (("S161B5", 5, -1, 5, [0, 0, 1, 96]),
                                                ("S161S5", 5, 24, 1, [1, 0, 0, 1728])):
            source = surface(raw, name, 56)
            ordinary = copy.deepcopy(source)
            ordinary["class"] = "flat" if side == -1 else "wall"
            ordinary["owner"].update(type=kind, type_index=100 if side == -1 else side,
                                     side=side, sector=sector, control_sector=-1, portal_group=0)
            ordinary["geometry"]["plane"] = plane
            independent_receiver_tile(raw, ordinary, 56)
            index = next(index for index, row in enumerate(raw["records"]) if row.get("data") is source)
            raw["records"].insert(index, {"kind": "surface", "frame": 56, "count": 1, "data": ordinary})
        for name in ("S161S4", "S161S5", "S161PN", "S161HO"):
            additional_b_portal_wall(raw, name)
        result = gate.captured_negatives(raw, stdout(), native_recipe())
        controls = {item["name"]: item for item in result["controls"]}
        expected = (("wrong-selected-3d-floor-plane", "three-d-floor-ceiling", 6, 5, 4),
                    ("cross-control-same-side-substitution", "three-d-floor-side", 1, 5, 1),
                    ("wrong-ordinary-upper-wall-height-band", "wall", 1, -1, 2),
                    ("wrong-ordinary-lower-wall-control-owner", "wall", 1, -1, 3))
        for name, cls, sector, control, kind in expected:
            target = raw["records"][controls[name]["record_index"]]["data"]
            self.assertEqual((target["class"], target["owner"]["sector"], target["owner"]["control_sector"],
                              target["owner"]["type"]), (cls, sector, control, kind))
            self.assertEqual((target["producer"], target["context"]["type"], target["context"]["depth"]),
                             ("levelmesh-surface-range", "main", 0))
            self.assertEqual(target["owner"]["side"], -1 if cls == "three-d-floor-ceiling" else 34)
        self.assertEqual(len(result["controls"]), 21)

    def test_captured_controls_cannot_promote_an_invalid_source(self):
        raw = full_raw()
        surface(raw)["geometry"]["triangle_mapping_valid"] = False
        with self.assertRaises(EvidenceError):
            gate.captured_negatives(raw, stdout(), native_recipe())

    def test_one_valid_current_packet_cannot_hide_another_attempts_missing_witness(self):
        left, right = full_raw(), full_raw()
        left["records"] = [row for row in left["records"] if not (row["kind"] == "surface"
                           and row["frame"] == 8 and row["data"].get("material", {}).get("name") == "S161PH")]
        right["records"] = [row for row in right["records"] if not (row["kind"] == "surface"
                            and row["frame"] == 8 and row["data"].get("material", {}).get("name") == "S161WP")]
        for raw in (left, right, {"observed_frames": 96, "records": left["records"] + right["records"]}):
            with self.assertRaises(EvidenceError):
                gate.validate_transition_records(raw, stdout(), native_recipe())


if __name__ == "__main__":
    unittest.main()
