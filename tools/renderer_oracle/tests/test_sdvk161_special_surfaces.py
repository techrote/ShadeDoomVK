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
            "map_sequence": ["SDV161A", "SDV161A", "SDV161B", "SDV161B"],
            "surface_witness_frames": list(range(8, 97, 8)),
            "console_commands": ["lm_max_updates 128", "lm_background_updates 32", "screenshot_quiet true"],
            "settings": {"gl_levelmesh": True, "lm_dynlights": False, "gl_lightprobe": True,
                         "gl_texture_filter": 0, "gl_texture_filter_anisotropic": 1}}


def stdout():
    # Independent literals preserve exact phase timing/order in the controls.
    return ("SDVK161_INPUT phase=invalidate-a-1 after_main_views=40\n"
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
            "map": "SDV161B" if second else "SDV161A", "settings": settings}})
        work = int(frame in (9, 25, 41, 57, 73, 89))
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
        self.assertEqual(set(result["cycles"]), {"invalidate_a_1", "reload_a", "invalidate_a_2", "invalidate_b_1", "reload_b", "invalidate_b_2"})
        self.assertFalse(result["physical_gpu_qualified"])

    def test_wrong_missing_duplicate_or_reordered_input_markers_fail(self):
        text = stdout()
        for bad in (text.replace("=56", "=57"), text + text.splitlines()[0] + "\n",
                    text.replace(text.splitlines()[0] + "\n", ""), "\n".join(reversed(text.splitlines()))):
            with self.subTest(text=bad), self.assertRaises(EvidenceError):
                self.validate(text=bad)

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

    def test_all_three_lifecycle_windows_require_actual_completion(self):
        for start, stop in ((9, 24), (25, 40), (41, 48), (57, 72), (73, 88), (89, 96)):
            raw = lifecycle_raw()
            for frame in range(start, stop + 1):
                resource(raw, frame)["lightmap_state"]["frame_tile_completions"] = 0
            with self.subTest(window=(start, stop)), self.assertRaisesRegex(EvidenceError, "complete real"):
                self.validate(raw)

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
            ("S161WP", 1, 4, 0, -1, 4, [1, 0, 0, 256], 1, "warped-wall"),
            ("S161PN", 1, 5, 0, -1, 5, [1, 0, 0, 256], 1, "wall"),
            ("S161HO", 1, 7, 0, -1, 7, [1, 0, 0, 256], 1, "wall"),
            ("S161NO", 1, 8, 0, -1, 8, [1, 0, 0, 256], 1, "wall"),
            ("S161GL", 1, 9, 0, -1, 9, [1, 0, 0, 32], 0.5, "translucent-wall"),
            ("S161RF", 5, -1, 0, -1, 17, [0, 0, 1, 0], 0.75, "reflective-floor"),
        ] if not second else [
            ("S161T4", 5, -1, 6, 4, 77, [0, 0, 1, 48], 1, "3d-floor"),
            ("S161B5", 4, -1, 6, 5, 78, [0, 0, -1, -96], 1, "3d-ceiling"),
            ("S161S4", 1, 34, 1, 4, 34, [1, 0, 0, 1100], 1, "3d-side"),
            ("S161S5", 1, 34, 1, 5, 34, [1, 0, 0, 1100], 1, "3d-side"),
            ("S161PN", 2, 34, 1, -1, 34, [1, 0, 0, 1100], 1, "wall"),
            ("S161HO", 3, 34, 1, -1, 34, [1, 0, 0, 1100], 1, "wall"),
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
                   "type": "portal" if second else "main", "depth": 1 if second else 0,
                   "epoch": 1 + incarnation, "identity": 2 if second else 1,
                   "parent_identity": 1 if second else 0, "producer": "LineToLine" if second else "root",
                   "portal_group": 2 if second else 0}
        raw["records"].append({"kind": "context", "frame": frame, "count": 1, "data": {"context": copy.deepcopy(context)}})
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
            stencil["owner"].update(type=0, type_index=3, side=3, sector=0, control_sector=-1, portal_group=1)
            stencil["key"]["shader"]["UseLevelMesh"] = 0
            stencil["geometry"]["current_uv_valid"] = False
            stencil["lightmap"].update(eligible=False, tile=-1, page=-1, valid=False,
                                       receipt={"owner": 0, "incarnation": 0, "slot": 0})
            raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": stencil})
    return raw


def surface(raw, name="S161PH", frame=8):
    return next(row["data"] for row in raw["records"] if row["kind"] == "surface" and row["frame"] == frame
                and row["data"].get("material", {}).get("name") == name)


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
            lambda value: value["context"].update(producer="root"),
            lambda value: value["context"].update(portal_group=1),
        )
        for mutation in mutations:
            raw = full_raw()
            mutation(surface(raw, "S161B5", 56))
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError): self.validate(raw)

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
                with self.subTest(name=name, mutation=mutation), self.assertRaisesRegex(EvidenceError, "ordinary upper/lower"):
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
    def test_real_control_code_rejects_sixteen_copies_without_mutating_admitted_source(self):
        raw = full_raw()
        original = copy.deepcopy(raw)
        result = gate.captured_negatives(raw, stdout(), native_recipe())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["controls"]), 16)
        self.assertTrue(all(control["status"] == "REJECTED" and control["reason"]
                            and len(control["mutant_sha256"]) == 64 for control in result["controls"]))
        self.assertEqual(raw, original)
        self.assertFalse(result["native_execution"])

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
