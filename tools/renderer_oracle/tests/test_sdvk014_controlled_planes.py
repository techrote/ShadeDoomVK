"""CPU-only authored-map and native-admission controls; never native proof."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.renderer_oracle import prepare, run, sdvk014_controlled_planes as gate
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests import test_sdvk161_special_surfaces as old
from tools.renderer_oracle.tests.test_corpus import unpack_wad, parse_udmf


def scene():
    return copy.deepcopy(next(s for s in prepare.load_catalog()["scenes"] if s["id"] == gate.SCENE))


def witness():
    """Independent four-face synthetic observations, not fake renderer outputs."""
    raw = old.lifecycle_raw()
    resources = {r["frame"]: r["data"] for r in raw["records"] if r["kind"] == "resource"}
    for frame, resource in resources.items():
        incarnation = (frame-1)//24
        tiles = [{"tile": axis*2+facing, "page": 0, "valid": True,
                  "receipt": {"owner": 100+incarnation, "incarnation": 10+axis*2+facing, "slot": axis*2+facing},
                  "binding": {"type": 4+facing, "type_index": 0, "control_sector": 1, "control_plane": axis},
                  "dirty": {"initial": False, "geometry": False, "light": False}}
                 for axis in (0, 1) for facing in (0, 1)]
        # TileCensus emits the ordinary surface sentinel as a signed JSON integer.
        ordinary = json.loads('{"type": 4, "type_index": 1, "control_sector": -1, "control_plane": -1}')
        tiles.append({"tile": 4, "page": 0, "valid": True,
                      "receipt": {"owner": 100+incarnation, "incarnation": 14, "slot": 4},
                      "binding": ordinary, "dirty": {"initial": False, "geometry": False, "light": False}})
        resource["lightmap_state"].update(live_tiles=5, valid_live_tiles=5, page_live_tiles=[5], tile_receipts=tiles)
        if frame % 8: continue
        map_name = "SDV161A" if frame <= 48 else "SDV161B"
        context = {"available": True, "map": map_name, "type": "main", "producer": "root", "depth": 0,
                   "portal_group": 0, "epoch": incarnation+1, "identity": 1, "parent_identity": 0}
        for tile in tiles[:4]:
            axis, kind = tile["binding"]["control_plane"], tile["binding"]["type"]
            name = "S161PN" if axis == 0 else "S161PH"
            material, shader = old.material(name, int(17 <= frame <= 32 or 65 <= frame <= 80))
            material["resource"]["index"] = 300+axis*16
            shader["UseLevelMesh"] = 1
            key = {"shader": shader}; first = tile["tile"]*6
            height = ((32, 48) if frame <= 48 else (96, 112))[axis]
            normal = -1 if kind == 4 else 1
            value = {"producer": "levelmesh-surface-range", "class": "three-d-floor-ceiling" if kind == 4 else "three-d-floor-floor",
                     "mesh_owner": 70+incarnation, "mesh_epoch": 3, "context": copy.deepcopy(context),
                     "key": key, "indexed": True, "first_index": first, "index_count": 6, "draw_count": 6,
                     "batch_first_index": first, "batch_index_count": 6, "texture_index": material["resource"]["index"],
                     "material": material, "owner": {"type": kind, "type_index": 0, "side": -1, "sector": 0, "control_sector": 1, "portal_group": 0},
                     "geometry": {"triangle_mapping_valid": True, "current_uv_valid": True,
                                  "current_uv_tolerance": 2**-21, "uv_scope": "synthetic CPU control", "plane": [0, 0, normal, normal*height],
                                  "vertex_z_min": height, "vertex_z_max": height, "vertex_first": first, "vertex_count": 6},
                     "lightmap": {"eligible": True, "valid": True, "epoch": resource["lightmap_epoch"], "tile": tile["tile"], "page": 0,
                                  "receipt": copy.deepcopy(tile["receipt"])},
                     "probe": {"authored_index": -1, "runtime_irradiance_index": 0, "fallback": True,
                               "probe_epoch": resource["probe_epoch"], "authored_scope": "not stored in mesh; no authored target claim"}}
            raw["records"] += [{"kind": "pipeline", "frame": frame, "count": 1,
                                "data": {"producer": "levelmesh-indexed-range", "first_index": first, "draw_count": 6,
                                         "key": copy.deepcopy(key), "context": copy.deepcopy(context)}},
                               {"kind": "surface", "frame": frame, "count": 1, "data": value}]
            if kind == (5 if frame <= 48 else 4):
                immediate = copy.deepcopy(value)
                immediate.update(producer="immediate-special-surface", indexed=False, draw_count=4, index_count=4)
                immediate["key"]["shader"]["UseLevelMesh"] = 0
                immediate["context"].update(type="portal", producer="Mirror", depth=1, identity=2, parent_identity=1, line_mirror=True)
                immediate["probe"]["authored_scope"] = "current immediate authored uniform selector"
                raw["records"].append({"kind": "surface", "frame": frame, "count": 1, "data": immediate})
    return raw


def controlled(raw, *, frame=8, axis=0, kind=5, producer="levelmesh-surface-range"):
    return next(r["data"] for r in raw["records"] if r["kind"] == "surface" and r["frame"] == frame
                and r["data"]["producer"] == producer and r["data"]["owner"]["type"] == kind
                and r["data"]["material"]["name"] == ("S161PN" if axis == 0 else "S161PH"))


class ControlledPlaneNativeTests(unittest.TestCase):
    def validate(self, raw):
        return gate.validate_transition_records(raw, old.stdout(), scene()["native"])

    def test_actual_generated_maps_define_unequal_both_planes_and_real_mirrors(self):
        specification = scene(); members, metadata = gate.authored_members(specification, prepare)
        for index, map_name in enumerate(("SDV161A", "SDV161B")):
            records = parse_udmf(unpack_wad(members[f"maps/{map_name}.wad"])["TEXTMAP"])
            self.assertEqual((len(records["vertex"]), len(records["linedef"]), len(records["sector"])), (8, 8, 2))
            self.assertEqual(records["sector"][0]["id"], 161)
            self.assertEqual([records["sector"][1][key] for key in ("heightfloor", "heightceiling")], [[32, 48], [96, 112]][index])
            definition = records["linedef"][4]
            self.assertEqual([definition[f"arg{i}"] for i in range(4)], [161, 5, 0, 255])
            self.assertEqual(definition["special"], 160)
            self.assertEqual(records["sidedef"][definition["sidefront"]]["sector"], 1)
            mirrors = [line for line in records["linedef"] if line.get("special") == 182]
            self.assertEqual(len(mirrors), 1)
            self.assertTrue(mirrors[0]["blocking"])
        self.assertEqual(metadata["baked_lightmap_members"], 0)
        self.assertIn("FF_FIX/Vavoom", metadata["excluded"])
        self.assertIs(prepare.special_surface_module(specification), gate)

    def test_preparation_is_source_authenticated_and_never_native_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"prepared"
            prepared = prepare.prepare(path, [gate.SCENE])
            self.assertFalse(prepared["native_executed"])
            self.assertFalse(prepared["native_qualified"])
            self.assertEqual(prepare.verify_prepared(path), prepared)
            (path/prepared["scenes"][0]["native"]["pk3"]).write_bytes(b"corrupt")
            with self.assertRaises(ValueError): prepare.verify_prepared(path)

    def test_all_four_main_and_both_immediate_facing_pairs_with_real_admission(self):
        admitted = self.validate(witness())
        self.assertEqual(admitted["status"], "PASS")
        self.assertFalse(admitted["physical_gpu_qualified"])
        self.assertEqual(admitted["source_facing_submissions"]["8"]["immediate_faces"], [(0, 5), (1, 5)])
        self.assertEqual(admitted["source_facing_submissions"]["56"]["immediate_faces"], [(0, 4), (1, 4)])

    def test_ordinary_tile_rejects_internal_unsigned_sentinel(self):
        raw = witness()
        ordinary = old.resource(raw, 8)["lightmap_state"]["tile_receipts"][4]
        ordinary["binding"]["control_plane"] = 0xFFFFFFFF
        with self.assertRaisesRegex(EvidenceError, "Ordinary tile invented"):
            self.validate(raw)

    def test_old_source_alias_and_opposite_facing_uv_are_rejected(self):
        for mutation, message in (
            (lambda raw: controlled(raw)["lightmap"].update(tile=3, receipt=copy.deepcopy(old.resource(raw, 8)["lightmap_state"]["tile_receipts"][3]["receipt"])), "model-source/facing"),
            (lambda raw: controlled(raw, producer="immediate-special-surface")["geometry"].update(current_uv_valid=False), "UV"),
            (lambda raw: controlled(raw)["geometry"].update(plane=[0, 0, 1, 48]), "selected/flipped"),
            (lambda raw: controlled(raw)["lightmap"]["receipt"].update(incarnation=999), "retired allocation"),
            (lambda raw: controlled(raw)["owner"].update(control_sector=0), "owner/facing"),
            (lambda raw: controlled(raw)["material"]["resource"].update(generation=0), "material generation"),
            (lambda raw: controlled(raw)["probe"].update(probe_epoch=999), "probe owner")):
            with self.subTest(message=message):
                raw = witness(); mutation(raw)
                with self.assertRaisesRegex(EvidenceError, message): self.validate(raw)

    def test_missing_actual_immediate_face_and_census_plane_are_rejected(self):
        raw = witness(); missing = controlled(raw, producer="immediate-special-surface")
        raw["records"] = [r for r in raw["records"] if r.get("data") is not missing]
        with self.assertRaisesRegex(EvidenceError, "mirrored source/facing"): self.validate(raw)
        raw = witness(); old.resource(raw, 8)["lightmap_state"]["tile_receipts"][0]["binding"].pop("control_plane")
        with self.assertRaisesRegex(EvidenceError, "model-source axis"): self.validate(raw)

    def test_normal_legacy_receipts_keep_strict_optional_new_source_identity(self):
        raw = old.full_raw(); value = old.surface(raw, "S161T4", frame=56); resource = old.resource(raw, 56)
        tile = next(t for t in resource["lightmap_state"]["tile_receipts"] if t["tile"] == value["lightmap"]["tile"])
        tile["binding"]["control_plane"] = 1
        gate.legacy._surface_lightmap(value, resource, gate.legacy._tile_census(resource))
        tile["binding"]["control_plane"] = 0
        with self.assertRaisesRegex(EvidenceError, "control namespace"):
            gate.legacy._surface_lightmap(value, resource, gate.legacy._tile_census(resource))

    def test_native_copy_controls_preserve_original_and_reject_intended_faults(self):
        raw = witness(); before = copy.deepcopy(raw)
        controls = gate.captured_negatives(raw, old.stdout(), scene()["native"])
        self.assertEqual(controls["status"], "PASS")
        self.assertEqual(len(controls["controls"]), 4)
        self.assertEqual(raw, before)


if __name__ == "__main__": unittest.main()
