"""Original, bounded SDVK-161 special-surface authoring (no renderer launch).

The warped texture deliberately has shader speed zero: the actual Warp2 shader
still displaces UV spatially, while this lifecycle witness has no animated clock.
3D floors use only ordinary opaque solid controls, never BOTH/INVERTPLANES.
Generated members are inputs, not proof that any surface was submitted or baked.
"""
from __future__ import annotations

import copy

SCENE = "special-surface-lifecycle"
MAPS = ("SDV161A", "SDV161B")
GENERATOR = "special_surface_lifecycle"
CAMERA = {"position": [-192, 0, 64], "yaw": 0, "pitch": 0, "roll": 0, "camera_height": 0, "actor_tid": 2002}
MAP_CAMERAS = {MAPS[0]: CAMERA, MAPS[1]: {"position": [1060, -176, 64], "yaw": 90,
               "pitch": 0, "roll": 0, "camera_height": 0, "actor_tid": 2002}}
PLAYER_STARTS = {MAPS[0]: [-240, 0], MAPS[1]: [-240, 0]}

# Semantic identities, never renderer-local surface/tile/descriptor ordinals.
MATERIALS = {
    "S161PH": {"shader": "pbr", "height_binding": 8,
               "authored_semantics": ["albedo", "normal", "metallic", "roughness", "ambient-occlusion", "height"]},
    "S161PN": {"shader": "pbr", "height_binding": -1,
               "authored_semantics": ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"]},
    "S161WP": {"shader": "warp2", "height_binding": 4,
               "authored_semantics": ["albedo", "height"]},
    "S161HO": {"shader": "default", "height_binding": 4,
               "authored_semantics": ["albedo", "height"]},
    "S161NO": {"shader": "default", "height_binding": -1,
               "authored_semantics": ["albedo"]},
}


def validate_recipe(scene: dict) -> None:
    native = scene.get("native", {})
    if (scene.get("id") != SCENE or native.get("generator") != GENERATOR
            or native.get("map") != MAPS[0] or native.get("camera") != CAMERA
            or native.get("map_cameras") != MAP_CAMERAS):
        raise ValueError("SDVK-161 needs its exact authored scene/map/camera")
    if (native.get("settings", {}).get("gl_levelmesh") is not True
            or native.get("settings", {}).get("lm_dynlights") is not False):
        raise ValueError("SDVK-161 requires ordinary lightmapped LevelMesh rendering")


def _sector(author, *, floor=0, ceiling=160, floor_texture="SDVFL", ceiling_texture="SDVFL", **extra):
    return {"heightfloor": floor, "heightceiling": ceiling, "texturefloor": floor_texture,
            "textureceiling": ceiling_texture, "lightlevel": 160, **extra}


def _ring(model, points, front, texture, *, back=None):
    """Explicit sector-sided geometry; clockwise outside / CCW inset boundary."""
    start = len(model.records["vertex"])
    model.records["vertex"] += [{"x": x, "y": y} for x, y in points]
    lines, sides = [], []
    for i in range(len(points)):
        side = len(model.records["sidedef"])
        model.records["sidedef"].append({"sector": front, "texturemiddle": texture})
        line = {"v1": start + i, "v2": start + (i + 1) % len(points), "sidefront": side,
                "blocking": back is None}
        if back is not None:
            line.update(sideback=side + 1, twosided=True)
            model.records["sidedef"].append({"sector": back, "texturemiddle": "-"})
        lines.append(len(model.records["linedef"]))
        sides.append(side)
        model.records["linedef"].append(line)
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2
    model.polygon_areas.append(area)
    return lines, sides


def _common_things(model, map_name):
    camera = MAP_CAMERAS[map_name]
    model.thing(1, *PLAYER_STARTS[map_name], tid=2001)
    model.thing(32200, *camera["position"], camera["yaw"], tid=camera["actor_tid"])
    model.thing(9890, -96, 0, angle=0, pitch=0, lm_suncolor=16777215,
                lm_sunintensity=0, lm_sampledist=32)


def models(author):
    first = author._Map(floor=0, ceiling=160)
    first.records["sector"][0].update(texturefloor="S161RF", floor_reflect=0.25)
    first.boundary([(-256, -192), (-256, 192), (256, 192), (256, 128), (256, 64),
                    (256, 0), (256, -64), (256, -128), (256, -192)],
                   ["S161NO", "S161NO", "S161NO", "S161PH", "S161WP", "S161PN",
                    "S161NO", "S161HO", "S161NO"])
    first.records["linedef"][2].update(id=16109, special=9)
    first.records["linedef"][6].update(id=16182, special=182)
    first.records["vertex"] += [{"x": 32, "y": 48}, {"x": 32, "y": -48}]
    first.records["sidedef"] += [{"sector": 0, "texturemiddle": "S161GL"}] * 2
    first.records["linedef"].append({"v1": 9, "v2": 10, "sidefront": 9, "sideback": 10,
                                        "twosided": True, "blocking": False, "alpha": 0.5, "id": 16150})
    _common_things(first, MAPS[0])
    first.thing(9200, 240, 96, 80, 180, 2030, arg0=25061 & 255, arg1=25061 >> 8)
    first.thing(9200, 0, 96, 80, 180, 2031, arg0=25061 & 255, arg1=25061 >> 8)

    second = author._Map(floor=0, ceiling=160)
    portals = author._linked_portal_geometry(second)
    # The existing portal helper is retained exactly. Its two-sided lines need
    # no new geometry. Each ordinary floor control gets its own closed sector.
    for index, bottom, top in ((4, 32, 48), (5, 96, 112)):
        second.records["sector"].append(_sector(author, floor=bottom, ceiling=top,
            floor_texture=f"S161B{index}", ceiling_texture=f"S161T{index}"))
        x = 1600 + (index - 4) * 128
        lines, _ = _ring(second, [(x, -32), (x, 32), (x + 64, 32), (x + 64, -32)],
                         index, f"S161S{index}")
        second.records["linedef"][lines[0]].update(special=160, arg0=161, arg1=1, arg2=0, arg3=255)
    second.records["sector"].append(_sector(author, floor=16, ceiling=144, id=161))
    target_lines, target_sides = _ring(second,
        [(1100, -96), (1340, -96), (1340, 96), (1100, 96)], 1, "-", back=6)
    for side in target_sides:
        second.records["sidedef"][side].update(texturetop="S161PN", texturebottom="S161HO")
    _common_things(second, MAPS[1])
    metadata = {"linked_portal": portals, "target_sector": 6, "target_lines": target_lines,
                "outside_sides": target_sides, "controls": [4, 5],
                "ordinary_height_bands": [
                    {"owner_sector": 1, "control_sector": -1, "type": kind, "side_indices": target_sides,
                     "material": material, "z_min": lower, "z_max": upper}
                    for kind, material, lower, upper in ((2, "S161PN", 144, 160), (3, "S161HO", 0, 16))],
                "three_d_floor_planes": [
                    {"owner_sector": 6, "control_sector": control, "type": kind, "z": z,
                     "material": f"S161{plane}{control}"}
                    for control, lower, upper in ((4, 32, 48), (5, 96, 112))
                    for kind, z, plane in ((4, lower, "B"), (5, upper, "T"))],
                "three_d_floor_sides": [
                    {"owner_sector": 1, "control_sector": control, "type": 1,
                     "side_indices": target_sides, "material": f"S161S{control}"}
                    for control in (4, 5)]}
    return {MAPS[0]: first, MAPS[1]: second}, metadata


def validate_geometry(authored, ownership):
    """Reject authoring drift before producing a purported fixed witness."""
    if set(authored) != set(MAPS):
        raise ValueError("SDVK-161 map population differs")
    first, second = (authored[name].records for name in MAPS)
    for name in MAPS:
        rows = authored[name].records
        cameras = [thing for thing in rows["thing"] if thing["type"] == 32200]
        camera = MAP_CAMERAS[name]
        if (len(cameras) != 1 or [cameras[0][key] for key in ("x", "y", "height")] != camera["position"]
                or cameras[0]["angle"] != camera["yaw"] or cameras[0]["id"] != camera["actor_tid"]):
            raise ValueError("SDVK-161 per-map authored camera differs: " + name)
        players = [thing for thing in rows["thing"] if thing["type"] == 1]
        if len(players) != 1 or [players[0][key] for key in ("x", "y")] != PLAYER_STARTS[name]:
            raise ValueError("SDVK-161 per-map player start differs: " + name)
    if (first["linedef"][2].get("special") != 9 or first["linedef"][6].get("special") != 182
            or first["linedef"][9].get("alpha") != 0.5
            or first["sector"][0].get("floor_reflect") != 0.25):
        raise ValueError("SDVK-161 special-surface definitions differ")
    if len(second["sector"]) != 7 or second["sector"][6].get("id") != 161:
        raise ValueError("SDVK-161 target sector identity differs")
    if ((second["sector"][1]["heightfloor"], second["sector"][1]["heightceiling"]) != (0, 160)
            or (second["sector"][6]["heightfloor"], second["sector"][6]["heightceiling"]) != (16, 144)):
        raise ValueError("SDVK-161 ordinary upper/lower wall height bands differ")
    for control, bottom, top in ((4, 32, 48), (5, 96, 112)):
        sector = second["sector"][control]
        if (sector["heightfloor"], sector["heightceiling"]) != (bottom, top):
            raise ValueError("SDVK-161 distinct control planes differ")
        definitions = [line for line in second["linedef"] if line.get("special") == 160
                       and second["sidedef"][line["sidefront"]]["sector"] == control]
        if len(definitions) != 1 or any(definitions[0].get(f"arg{i}") != value
                                       for i, value in enumerate((161, 1, 0, 255))):
            raise ValueError("SDVK-161 requires ordinary opaque solid 3D-floor controls")
    if ownership["outside_sides"] != [28, 30, 32, 34]:
        raise ValueError("SDVK-161 authored semantic side ordinals differ")
    for side in ownership["outside_sides"]:
        if second["sidedef"][side]["sector"] != 1 or second["sidedef"][side + 1]["sector"] != 6:
            raise ValueError("SDVK-161 target side owner/control topology differs")
        front, back = second["sidedef"][side], second["sidedef"][side + 1]
        if (front.get("texturetop"), front.get("texturemiddle"), front.get("texturebottom")) != ("S161PN", "-", "S161HO"):
            raise ValueError("SDVK-161 upper/lower semantic material ownership differs")
        if any(back.get(key, "-") != "-" for key in ("texturetop", "texturemiddle", "texturebottom")):
            raise ValueError("SDVK-161 target back faces must not own the outside height-band materials")
    for model in authored.values():
        records = model.records
        if len(records["linedef"]) > 32 or len(records["thing"]) > 8:
            raise ValueError("SDVK-161 exceeds compact geometry/actor bound")
        model.text()  # Existing finite literal and hard authoring limits.


def authored_members(scene, author):
    validate_recipe(scene)
    members = author._base_members()
    author._material_layers(members)
    names = ["S161PH", "S161PN", "S161WP", "S161HO", "S161NO", "S161GL", "S161RF"]
    names += [f"S161{part}{control}" for control in (4, 5) for part in ("B", "T", "S")]
    for index, name in enumerate(names):
        members[f"textures/{name}.png"] = author._texture(64, 64,
            (40 + index * 13, 80 + index * 7, 190 - index * 9, 255),
            (220 - index * 9, 180 - index * 5, 48 + index * 11, 255))
    # The warp's PBR declarations deliberately cannot select the PBR model;
    # height is appended independently. Height alone also cannot select PBR.
    def pbr(name, *, with_height=False):
        text = author._pbr(name).replace(' normal "SDVN"', ' normal "SDVN" { filter linear }')
        return text[:-2] + (height if with_height else "") + "}\n"
    height = ' height "SDVH" { filter linear }\n'
    members["GLDEFS"] = (pbr("S161PH", with_height=True)
        + pbr("S161PN") + pbr("S161WP", with_height=True)
        + f'material texture S161HO\n{{\n{height}}}\n').encode()
    members["ANIMDEFS"] = b"warp2 texture S161WP 0\n"
    members["DECALDEF"] = b"decal SDVK161Mark 25061\n{\n pic S161DCL\n solid\n}\n"
    members["graphics/S161DCL.png"] = author._texture(32, 32,
        (250, 35, 90, 255), (250, 225, 35, 255), offset=(16, 16))
    authored, ownership = models(author)
    validate_geometry(authored, ownership)
    for name, model in authored.items():
        members[f"maps/{name}.wad"] = author.pf_indexed.wad([
            (name, b""), ("TEXTMAP", model.text().encode()), ("ENDMAP", b"")])
    members["MAPINFO"] = ("".join(f'map {name} "SDVK special surfaces {index}" {{ nointermission }}\n'
        for index, name in enumerate(MAPS)) + 'DoomEdNums { 32200 = SDVKFixedCamera\n }\n').encode()
    return members, {"geometry": "two compact original authored UDMF maps",
        "textures": "generated_rgba_only", "native_executed": False,
        "camera_actor_tid": 2002, "camera_position_world": copy.deepcopy(CAMERA["position"]),
        "player_start_world": [-240, 0], "monsters": 0, "animated_or_random_actors": 0,
        "baked_lightmap_members": 0, "materials": copy.deepcopy(MATERIALS),
        "initial_retained_work": {"after_main_views": 32, "phase": "invalidate-a-retained-start",
                                  "command": "invalidatelightmap", "retained_frames": [1, 8],
                                  "scope": "explicit forced update after warmup; not observed initial construction bake"},
        "warp": {"material": "S161WP", "style": 2, "shader_speed": 0,
                 "scope": "static spatial Warp2 UV displacement; animated clock unclaimed"},
        "horizon_observation": "first emitted nonindexed strip from every actual horizon contents producer on selected witness frames; all render commands execute",
        "decal": {"attached_tid": 2030, "negative_tid": 2031, "expected_side": 3,
                  "attached_distance": 16, "negative_distance": 256, "search_limit": 64,
                  "route": "decal overlay; never a standalone baked receiver"},
        "reverse_portal_receiver": {"side": 1, "owner_sector": 0, "control_sector": -1,
                                    "portal_group": 1, "material": "SDVW", "producer": "immediate-special-surface",
                                    "virtual_camera_world": [36, -176, 64], "yaw": 90,
                                    "legacy_context_portal_group": 2,
                                    "line_portal_selection": {"selected_span_index": 0, "origin_line": 10,
                                        "destination_line": 3, "source_sector": 1, "destination_sector": 0,
                                        "source_group": 2, "destination_group": 1}},
        "ownership": ownership,
        "maps": [{"map": name, "camera": copy.deepcopy(MAP_CAMERAS[name]),
                  "player_start_world": copy.deepcopy(PLAYER_STARTS[name]), "counts": {kind: len(rows) for kind, rows in model.records.items()},
                  "boundary_signed_areas": model.polygon_areas} for name, model in authored.items()],
        "excluded": ["inverted/both-plane 3D floors", "animated warp time", "physical GPU qualification",
                     "recursive 3D-flat native submission (source-only boundary)"]}
