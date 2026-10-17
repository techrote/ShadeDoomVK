"""Authoring-only positive/adversarial controls; never creates a device."""
from __future__ import annotations

import copy
import io
import struct
import unittest
import zipfile

from tools.renderer_oracle import prepare
from tools.renderer_oracle import sdvk161_fixtures as fixture


def recipe():
    return {"id": fixture.SCENE, "native": {
        "generator": fixture.GENERATOR, "map": fixture.MAPS[0],
        "camera": copy.deepcopy(fixture.CAMERA),
        "settings": {"gl_levelmesh": True, "lm_dynlights": False}}}


def wad_lumps(raw):
    magic, count, directory = struct.unpack_from("<4sII", raw)
    if magic != b"PWAD":
        raise AssertionError("fixture is not a PWAD")
    result = {}
    for index in range(count):
        start, length, name = struct.unpack_from("<II8s", raw, directory + 16 * index)
        result[name.rstrip(b"\0").decode()] = raw[start:start + length]
    return result


class SpecialSurfaceFixturesTests(unittest.TestCase):
    def test_original_members_are_deterministic_compact_and_do_not_claim_native(self):
        first, meta = fixture.authored_members(recipe(), prepare)
        second, again = fixture.authored_members(recipe(), prepare)
        self.assertEqual(first, second)
        self.assertEqual(meta, again)
        archive = prepare.archive_bytes(first)
        self.assertEqual(archive, prepare.archive_bytes(second))
        self.assertLess(len(archive), 350_000)
        with zipfile.ZipFile(io.BytesIO(archive)) as packed:
            self.assertEqual(packed.namelist(), sorted(first))
            self.assertTrue(all(row.date_time == (1980, 1, 1, 0, 0, 0) for row in packed.infolist()))
        self.assertIs(meta["native_executed"], False)
        self.assertEqual(meta["textures"], "generated_rgba_only")
        self.assertEqual(meta["baked_lightmap_members"], 0)
        self.assertEqual(meta["animated_or_random_actors"], 0)
        self.assertEqual([row["counts"]["linedef"] for row in meta["maps"]], [10, 30])
        for name in fixture.MAPS:
            lumps = wad_lumps(first[f"maps/{name}.wad"])
            self.assertEqual(list(lumps), [name, "TEXTMAP", "ENDMAP"])
            self.assertTrue(lumps["TEXTMAP"].startswith(b'namespace = "ZDoom";'))
            self.assertNotIn("LIGHTMAP", lumps)
        for name, payload in first.items():
            if name.endswith(".png"):
                self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_decal_overlay_has_attached_and_out_of_trace_distance_controls(self):
        members, _ = fixture.authored_members(recipe(), prepare)
        self.assertNotIn(b"fullbright", members["DECALDEF"])
        models, _ = fixture.models(prepare)
        rows = models[fixture.MAPS[0]].records
        decals = {row["id"]: row for row in rows["thing"] if row["type"] == 9200}
        for tid, distance in ((2030, 16), (2031, 256)):
            self.assertEqual(256 - decals[tid]["x"], distance)
            self.assertEqual(decals[tid]["y"], 96)
            self.assertEqual(decals[tid]["angle"], 180)
            self.assertEqual(decals[tid]["arg0"] + 256 * decals[tid]["arg1"], 25061)
        east = rows["linedef"][3]
        self.assertEqual(rows["sidedef"][east["sidefront"]]["texturemiddle"], "S161PH")
        vertices = [rows["vertex"][east[key]] for key in ("v1", "v2")]
        self.assertEqual(vertices, [{"x": 256, "y": 128}, {"x": 256, "y": 64}])
        # The interior transparent line ends at y48, so it cannot steal either
        # eastward decal trace at y96 from the intended wall.
        glass = rows["linedef"][9]
        self.assertTrue(all(rows["vertex"][glass[key]]["y"] <= 48 for key in ("v1", "v2")))

    def test_supported_portal_reflection_horizon_and_translucency_are_real_definitions(self):
        models, ownership = fixture.models(prepare)
        a = models[fixture.MAPS[0]].records
        b = models[fixture.MAPS[1]].records
        self.assertEqual(a["linedef"][2]["special"], 9)
        self.assertEqual(a["linedef"][6]["special"], 182)
        self.assertEqual(a["sector"][0]["floor_reflect"], 0.25)
        self.assertEqual(a["linedef"][9]["alpha"], 0.5)
        self.assertTrue(a["linedef"][9]["twosided"])
        self.assertEqual({a["sidedef"][a["linedef"][9][key]]["texturemiddle"]
                          for key in ("sidefront", "sideback")}, {"S161GL"})
        for index, destination, origin in ((3, 102, 101), (10, 101, 102)):
            self.assertEqual(b["linedef"][index]["special"], 156)
            self.assertEqual([b["linedef"][index][f"arg{i}"] for i in range(4)],
                             [destination, origin, 3, 0])
        self.assertEqual(ownership["linked_portal"]["portal_displacement"], [1024, 0])

    def test_distinct_slab_planes_and_shared_sides_have_separate_control_identity(self):
        models, ownership = fixture.models(prepare)
        fixture.validate_geometry(models, ownership)
        rows = models[fixture.MAPS[1]].records
        self.assertEqual([(row["heightfloor"], row["heightceiling"])
                          for row in rows["sector"][4:6]], [(32, 48), (96, 112)])
        self.assertEqual(rows["sector"][6]["id"], 161)
        self.assertEqual({(row["type"], row["control_sector"], row["z"])
                          for row in ownership["three_d_floor_planes"]},
                         {(4, 4, 32), (5, 4, 48), (4, 5, 96), (5, 5, 112)})
        for row in ownership["three_d_floor_sides"]:
            self.assertEqual(row["owner_sector"], 1)
            self.assertNotEqual(row["owner_sector"], row["control_sector"])
            self.assertEqual(row["side_indices"], [28, 30, 32, 34])
        for side in ownership["outside_sides"]:
            self.assertEqual((rows["sidedef"][side]["sector"], rows["sidedef"][side + 1]["sector"]), (1, 6))
        # Each intended model lies inside room B, wholly separate from control
        # rooms. The shared boundary makes a hole in B and therefore stresses
        # more than one subsector without a large or generated stress map.
        self.assertEqual(models[fixture.MAPS[1]].polygon_areas[-1], 46080)

    def test_warp_and_height_positive_negative_inputs_preserve_semantic_contract(self):
        members, meta = fixture.authored_members(recipe(), prepare)
        definitions = members["GLDEFS"].decode()
        self.assertEqual(members["ANIMDEFS"], b"warp2 texture S161WP 0\n")
        self.assertEqual(definitions.count('height "SDVH"'), 3)
        # Independently count braces: sampling blocks must not accidentally
        # swallow/duplicate height declarations when authoring the PBR map.
        depth = 0
        for line in definitions.splitlines():
            if line.startswith(' height '):
                self.assertEqual(depth, 1)
            depth += line.count("{") - line.count("}")
            self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)
        self.assertNotIn("material texture S161NO", definitions)
        self.assertEqual(meta["materials"]["S161PH"]["height_binding"], 8)
        self.assertEqual(meta["materials"]["S161WP"]["height_binding"], 4)
        self.assertEqual(meta["materials"]["S161WP"]["authored_semantics"], ["albedo", "height"])
        self.assertEqual(meta["materials"]["S161PN"]["height_binding"], -1)
        self.assertEqual(meta["materials"]["S161HO"]["shader"], "default")

    def test_serialized_upper_and_lower_bands_keep_front_material_and_back_sector_ownership(self):
        from tools.renderer_oracle.tests.test_corpus import parse_udmf
        members, meta = fixture.authored_members(recipe(), prepare)
        records = parse_udmf(wad_lumps(members["maps/SDV161B.wad"])["TEXTMAP"])
        self.assertEqual([(records["sector"][i]["heightfloor"], records["sector"][i]["heightceiling"])
                          for i in (1, 6)], [(0, 160), (16, 144)])
        for line_index, side_index in zip((26, 27, 28, 29), (28, 30, 32, 34)):
            line = records["linedef"][line_index]
            self.assertEqual((line["sidefront"], line["sideback"]), (side_index, side_index + 1))
            front, back = (records["sidedef"][line[key]] for key in ("sidefront", "sideback"))
            self.assertEqual((front["sector"], back["sector"]), (1, 6))
            self.assertEqual([front.get(key, "-") for key in ("texturetop", "texturemiddle", "texturebottom")],
                             ["S161PN", "-", "S161HO"])
            self.assertEqual([back.get(key, "-") for key in ("texturetop", "texturemiddle", "texturebottom")],
                             ["-", "-", "-"])
        self.assertEqual([(row["type"], row["material"], row["z_min"], row["z_max"])
                          for row in meta["ownership"]["ordinary_height_bands"]],
                         [(2, "S161PN", 144, 160), (3, "S161HO", 0, 16)])
        self.assertEqual({kind: len(rows) for kind, rows in records.items()},
                         {"vertex": 28, "sector": 7, "sidedef": 36, "linedef": 30, "thing": 3})

    def test_recipe_rejects_foreign_scene_camera_and_non_lightmapped_policy(self):
        for field, value in (("id", "other"), ("generator", "lighting"), ("map", "SDV161B"),
                             ("camera", {**fixture.CAMERA, "yaw": 90}),
                             ("settings", {"gl_levelmesh": False, "lm_dynlights": False}),
                             ("settings", {"gl_levelmesh": True, "lm_dynlights": True})):
            scene = recipe()
            (scene if field == "id" else scene["native"])[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                fixture.authored_members(scene, prepare)

    def test_geometry_rejects_owner_alias_and_unsupported_special_drift(self):
        for mutation in ("owner", "tag", "flat-plane", "translucent-control", "both-planes",
                         "horizon", "mirror", "glass-alpha", "reflect", "raised-floor", "lowered-ceiling",
                         "upper-material", "lower-material", "back-material"):
            models, ownership = fixture.models(prepare)
            a, b = (models[name].records for name in fixture.MAPS)
            if mutation == "owner":
                b["sidedef"][28]["sector"] = 4
            elif mutation == "tag":
                b["sector"][6]["id"] = 4
            elif mutation == "flat-plane":
                b["sector"][4]["heightfloor"] = 48
            elif mutation == "translucent-control":
                b["linedef"][18]["arg3"] = 128
            elif mutation == "both-planes":
                b["linedef"][18]["arg1"] = 5
            elif mutation == "horizon":
                a["linedef"][2]["special"] = 0
            elif mutation == "mirror":
                a["linedef"][6]["special"] = 0
            elif mutation == "glass-alpha":
                a["linedef"][9]["alpha"] = 1
            elif mutation == "reflect":
                a["sector"][0]["floor_reflect"] = 0
            elif mutation == "raised-floor":
                b["sector"][6]["heightfloor"] = 0
            elif mutation == "lowered-ceiling":
                b["sector"][6]["heightceiling"] = 160
            elif mutation == "upper-material":
                b["sidedef"][34]["texturetop"] = "S161HO"
            elif mutation == "lower-material":
                b["sidedef"][34]["texturebottom"] = "S161PN"
            elif mutation == "back-material":
                b["sidedef"][35]["texturetop"] = "S161PN"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                fixture.validate_geometry(models, ownership)


if __name__ == "__main__":
    unittest.main()
