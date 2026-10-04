#!/usr/bin/env python3
"""Prepare bounded PF-006/009/010 authored inputs; never execute an engine.

Stock Doom2 assets are referenced, never copied. The package is a proposed
view fixture, not evidence that portals, camera updates, sprites or probes ran.
Native observation and matched baseline/candidate state remain mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "pf020-freeze-view-inputs/v1"
IWAD_SHA256 = "31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab"
MAP = "PFVTEST"
CAMERA = "PFVCAM"
USER_TEXTURE = "PFVUSR"
USER_STOCK = "STARTAN3"
USER_EXTENT = (128, 128)
USER_SHADER_MEMBER = "shaders/pf020_identity.glsl"
# This is the current built-in default SetupMaterial body. The fixture gives it
# a distinct public user-shader identity without changing material arithmetic.
IDENTITY_SHADER = "\nvoid SetupMaterial(inout Material material)\n{\n\tvec2 texCoord = GetTexCoord();\n\tSetMaterialProps(material, texCoord);\n}\n"
EXTENT = [640, 480]
WALLS = ("STARTAN3", "STONE2", "BRICK7", "METAL2", "WOOD1", "TEKWALL1")
FLATS = ("FLOOR0_1", "CEIL3_5", "FLOOR4_8", "CEIL5_2")
ROTATIONS = ("POSSA1", "POSSA2A8", "POSSA3A7", "POSSA4A6", "POSSA5",
             "POSSA4A6", "POSSA3A7", "POSSA2A8")
CLASSES = {32100: "PFViewCamera", 32101: "PFViewFace", 32102: "PFViewWall",
           32103: "PFViewFlat", 32104: "PFViewFlipX", 32105: "PFViewFlipY",
           32106: "PFViewInterpolated"}
SETTINGS = {"vid_rendermode": 4, "gl_texture_filter": 0, "gl_multisample": 0,
            "gl_portals": True, "gl_mirrors": True, "r_mirror_recursions": 4,
            "gl_lightprobe": True, "gl_light_shadows": 0, "gl_levelmesh": False,
            "gl_ubershaders": False, "gl_customshader": True, "cl_capfps": False}
SOURCE_FILES = (
    "AGENTS.md", "docs/shadedoomvk/PF-006-PIPELINE-KEY-CONTRACT.md",
    "docs/shadedoomvk/PF-009-SPRITE-SURFACE-CONTRACT.md",
    "docs/shadedoomvk/PF-010-RENDER-CONTEXT-CONTRACT.md",
    "docs/shadedoomvk/06-VALIDATION-PERFORMANCE-CONTRACT.md",
    "tools/pf_oracle/prepare_freeze_view_fixture.py",
    "tools/pf_oracle/tests/test_freeze_view_fixture.py",
    "wadsrc/static/zscript.txt", "wadsrc/static/zscript/actors/actor.zs",
    "wadsrc/static/zscript/actors/shared/camera.zs", "wadsrc/static/zscript/doombase.zs",
    "src/scripting/thingdef_data.cpp", "src/scripting/vmthunks.cpp",
    "src/scripting/vmthunks_actors.cpp", "src/playsim/actor.h",
    "src/playsim/actorinlines.h", "src/playsim/p_maputl.cpp", "src/playsim/portal.cpp",
    "src/maploader/udmf.cpp", "src/maploader/specials.cpp", "src/r_data/sprites.cpp",
    "src/r_data/r_canvastexture.cpp", "src/gamedata/textures/animations.cpp",
    "src/rendering/hwrenderer/hw_entrypoint.cpp",
    "src/rendering/r_utility.cpp", "src/rendering/r_utility.h",
    "src/d_main.cpp", "src/d_net.cpp", "src/g_game.cpp",
    "src/common/utility/zstring.h",
    "src/common/console/c_dispatch.cpp",
    "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp",
    "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.h",
    "src/rendering/hwrenderer/scene/hw_sprites.cpp",
    "src/rendering/hwrenderer/scene/hw_sprite_surface.h",
    "src/rendering/hwrenderer/scene/hw_portal.cpp",
    "src/rendering/hwrenderer/scene/hw_drawinfo.cpp",
    "src/rendering/hwrenderer/scene/hw_rendercontext.h",
    "src/common/rendering/hwrenderer/data/hw_cvars.cpp",
    "src/r_data/gldefs.cpp", "src/common/textures/texturemanager.cpp",
    "src/common/textures/texturemanager.h", "src/common/textures/multipatchtexturebuilder.cpp",
    "src/common/textures/hw_material.cpp", "src/common/textures/hw_material.h",
    "src/common/textures/textures.h",
    "src/common/rendering/vulkan/shaders/vk_shader.cpp",
    "src/common/rendering/vulkan/shaders/vk_shader.h",
    "src/common/rendering/vulkan/vk_renderstate.cpp",
    "wadsrc/static/shaders/scene/material_default.glsl",
    "wadsrc/static/shaders/scene/material.glsl",
    "wadsrc/static/shaders/scene/mateffect_default.glsl",
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Required regular file missing: {path}")
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def wad_directory(raw: bytes, *, magic: bytes = b"IWAD") -> dict[str, tuple[int, int]]:
    if len(raw) < 12 or raw[:4] != magic:
        raise ValueError("Invalid WAD header")
    count, offset = struct.unpack_from("<II", raw, 4)
    if not 1 <= count <= 10000 or offset < 12 or offset + count * 16 > len(raw):
        raise ValueError("Invalid bounded WAD directory")
    entries = {}
    for i in range(count):
        start, size, name = struct.unpack_from("<II8s", raw, offset + 16*i)
        try:
            name = name.rstrip(b"\0").decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("Non-ASCII WAD name") from error
        if start > len(raw) or size > len(raw) - start:
            raise ValueError("WAD lump extends beyond input")
        entries[name] = (start, size)
    return entries


def stock_assets(raw: bytes) -> dict:
    """Inspect stock directory/texture definitions, without packaging pixels."""
    entries = wad_directory(raw)
    textures, definitions = set(), {}
    for lump in ("TEXTURE1", "TEXTURE2"):
        if lump not in entries:
            continue
        start, size = entries[lump]
        block = raw[start:start+size]
        if len(block) < 4:
            raise ValueError("Truncated stock texture directory")
        count = struct.unpack_from("<I", block)[0]
        if count > 4096 or 4 + 4*count > len(block):
            raise ValueError("Invalid stock texture count")
        for i in range(count):
            at = struct.unpack_from("<I", block, 4 + 4*i)[0]
            if at + 22 > len(block):
                raise ValueError("Truncated stock texture definition")
            name = block[at:at+8].rstrip(b"\0").decode("ascii")
            width, height = struct.unpack_from("<HH", block, at+12)
            patches = struct.unpack_from("<H", block, at+20)[0]
            if not 1 <= width <= 4096 or not 1 <= height <= 4096 or at+22+10*patches > len(block):
                raise ValueError("Invalid stock texture definition extent")
            textures.add(name)
            if name in WALLS:
                definitions[name] = {"extent": [width, height], "patches": patches,
                                     "definitionSha256": sha(block[at:at+22+10*patches])}
    if set(WALLS) - textures:
        raise ValueError("Required stock wall texture missing")
    if definitions[USER_STOCK]["extent"] != list(USER_EXTENT):
        raise ValueError("Identity user alias must retain the stock texture extent")
    wanted = sorted(set(FLATS + ROTATIONS))
    if set(wanted) - entries.keys():
        raise ValueError("Required stock flat or POSS rotation missing")
    rows = {}
    for name in wanted:
        at, size = entries[name]
        if name in FLATS and size != 4096:
            raise ValueError("Required stock flat is not 64 by 64")
        if name.startswith("POSS"):
            if size < 8:
                raise ValueError("Required stock sprite has no patch header")
            w, h = struct.unpack_from("<HH", raw, at)
            if not 1 <= w <= 256 or not 1 <= h <= 256 or size < 8+4*w:
                raise ValueError("Required stock sprite extent is invalid")
        rows[name] = {"sha256": sha(raw[at:at+size]), "bytes": size}
    return {"wallTextures": list(WALLS), "wallDefinitions": definitions, "lumps": rows,
            "logicalRotationNames": list(ROTATIONS), "pairedFrameFlip": [False]*5+[True]*3,
            "copiedIntoPackage": False}


def fixture() -> dict:
    scene = {"vertices": [], "sectors": [], "sides": [], "lines": [], "things": []}
    polygons = [((-256, -128), (-256, 128), (0, 128), (128, 128), (192, 128), (192, -128)),
                ((192, -128), (192, 128), (224, 128), (224, -128)),
                ((1216, -128), (1216, 128), (1472, 128), (1472, -128)),
                ((1184, -128), (1184, 128), (1216, 128), (1216, -128))]
    edges = {}
    for sector, polygon in enumerate(polygons):
        scene["sectors"].append({"heightfloor": 0, "heightceiling": 128,
                                 "texturefloor": FLATS[(sector//2)*2],
                                 "textureceiling": FLATS[(sector//2)*2+1], "lightlevel": 160})
        for a, b in zip(polygon, polygon[1:]+polygon[:1]):
            for point in (a, b):
                if point not in scene["vertices"]:
                    scene["vertices"].append(point)
            v1, v2 = scene["vertices"].index(a), scene["vertices"].index(b)
            side = len(scene["sides"])
            scene["sides"].append({"sector": sector, "texturemiddle": WALLS[(sector+side) % len(WALLS)]})
            if (v2, v1) in edges:
                line = scene["lines"][edges[(v2, v1)]]
                line.update(sideback=side, twosided=True, blocking=False)
                scene["sides"][line["sidefront"]]["texturemiddle"] = "-"
                scene["sides"][side]["texturemiddle"] = "-"
            else:
                edges[v1, v2] = len(scene["lines"])
                scene["lines"].append({"v1": v1, "v2": v2, "sidefront": side, "blocking": True})
    for line in scene["lines"]:
        a, b = (scene["vertices"][line[key]] for key in ("v1", "v2"))
        if a == (192, 128) and b == (192, -128):
            line.update(id=101, special=156, arg0=102, arg1=0, arg2=3, arg3=0)
        elif a == (1216, -128) and b == (1216, 128):
            line.update(id=102, special=156, arg0=101, arg1=0, arg2=3, arg3=0)
        elif a == (1472, 128) and b == (1472, -128):
            line.update(id=103, special=182)
        elif a == (0, 128) and b == (128, 128):
            scene["sides"][line["sidefront"]]["texturemiddle"] = CAMERA
        elif a == (128, 128) and b == (192, 128):
            line.update(id=104)
            scene["sides"][line["sidefront"]]["texturemiddle"] = USER_TEXTURE

    def thing(role, kind, tid, x, y, z=0, angle=0):
        scene["things"].append({"role": role, "type": kind, "id": tid, "x": x, "y": y,
                                "height": z, "angle": angle, **{f"skill{i}": True for i in range(1, 6)},
                                "single": True, "coop": True})
    thing("player", 1, 4000, -128, 0)
    thing("camera", 32100, 4100, 1328, -48, 48, 90)
    for k, (x, y) in enumerate((x, y) for x in (0, 64) for y in (-72, -24, 24, 72)):
        # Center of each inherited stock8rot pair, away from quantization edges.
        yaw = (math.degrees(math.atan2(y, x+128)) - ((2*k+.5)*22.5-202.5)) % 360
        # UDMF thing.angle is CheckInt/short; nearest integer remains well
        # inside the selected22.5-degree bin rather than authoring a float.
        thing(f"rotation-{k+1}", 32101, 4201+k, x, y, angle=round(yaw) % 360)
    for role, kind, tid, pos in (("wall", 32102, 4301, (96, -88, 32)),
                                ("flat", 32103, 4302, (96, 88, 8)),
                                ("flip-x", 32104, 4303, (128, -48, 0)),
                                ("flip-y", 32105, 4304, (128, 48, 0)),
                                ("interpolated", 32106, 4400, (-32, -48, 8)),
                                ("portal-face", 32101, 4501, (1408, 0, 0)),
                                ("probe", 9892, 4600, (0, -64, 64))):
        thing(role, kind, tid, *pos, angle=180 if role == "portal-face" else 0)
    return scene


def validate_scene(scene: dict) -> None:
    """Reject authoring changes that erase a required route before native work."""
    vertices, sectors, sides, lines, things = (scene[k] for k in ("vertices", "sectors", "sides", "lines", "things"))
    if len(sectors) != 4 or not 8 <= len(vertices) <= 32 or not 12 <= len(lines) <= 40 or len(things) != 17:
        raise ValueError("Fixture bounded counts changed")
    if any(len(v) != 2 or any(not math.isfinite(c) or abs(c) > 2048 for c in v) for v in vertices):
        raise ValueError("Fixture vertex exceeds finite bounds")
    if len({tuple(v) for v in vertices}) != len(vertices):
        raise ValueError("Duplicate fixture vertex")
    if any(s != {"heightfloor": 0, "heightceiling": 128, "texturefloor": FLATS[(i//2)*2],
                 "textureceiling": FLATS[(i//2)*2+1], "lightlevel": 160} for i, s in enumerate(sectors)):
        raise ValueError("Ordinary room or stock material changed")
    boundaries = [[] for _ in sectors]
    for line in lines:
        if any(type(line.get(k)) is not int or not 0 <= line[k] < len(vertices) for k in ("v1", "v2")) or line["v1"] == line["v2"]:
            raise ValueError("Invalid linedef vertex")
        for key in ("sidefront", "sideback"):
            if key not in line and key == "sideback":
                continue
            if type(line.get(key)) is not int or not 0 <= line[key] < len(sides):
                raise ValueError("Invalid linedef sidedef")
            side = sides[line[key]]
            if type(side.get("sector")) is not int or not 0 <= side["sector"] < 4:
                raise ValueError("Invalid sidedef sector")
            if side["texturemiddle"] not in WALLS + (CAMERA, USER_TEXTURE, "-"):
                raise ValueError("Non-stock or undeclared wall material")
            edge = (line["v1"], line["v2"])
            boundaries[side["sector"]].append(edge if key == "sidefront" else edge[::-1])
        if ("sideback" in line) != bool(line.get("twosided")):
            raise ValueError("Two-sided linedef flag and sector disagree")
    for edges in boundaries:
        if len({a for a, _ in edges}) != len(edges) or {a for a, _ in edges} != {b for _, b in edges}:
            raise ValueError("Sector boundary is not a closed single polygon")
        walk = dict(edges)
        visited, at = set(), edges[0][0]
        while at not in visited:
            visited.add(at)
            at = walk[at]
        if len(visited) != len(edges) or at != edges[0][0]:
            raise ValueError("Sector boundary has disconnected loops")
        if sum(vertices[a][0]*vertices[b][1]-vertices[b][0]*vertices[a][1] for a, b in edges) >= 0:
            raise ValueError("Sector front/back winding is reversed")
    portals = [line for line in lines if line.get("special") == 156]
    if len(portals) != 2 or {line.get("id") for line in portals} != {101, 102}:
        raise ValueError("Missing uniquely identified linked pair")
    by_id = {line["id"]: line for line in portals}
    for identity, target, front, back, delta in ((101, 102, 0, 1, (1024, 0)), (102, 101, 2, 3, (-1024, 0))):
        line, dest = by_id[identity], by_id[target]
        if [line.get(f"arg{i}") for i in range(4)] != [target, 0, 3, 0] or line.get("blocking") or "sideback" not in line:
            raise ValueError("Linked portal loses type, backlink or back sector")
        if sides[line["sidefront"]]["sector"] != front or sides[line["sideback"]]["sector"] != back:
            raise ValueError("Linked portal is on the wrong sector side")
        displacement = tuple(b-a for a, b in zip(vertices[line["v1"]], vertices[dest["v2"]]))
        d1 = tuple(b-a for a, b in zip(vertices[line["v1"]], vertices[line["v2"]]))
        d2 = tuple(b-a for a, b in zip(vertices[dest["v1"]], vertices[dest["v2"]]))
        if displacement != delta or d1 != tuple(-d for d in d2):
            raise ValueError("Linked portal displacement or parallel orientation is wrong")
    mirrors = [line for line in lines if line.get("special") == 182]
    if len(mirrors) != 1 or "sideback" in mirrors[0] or sides[mirrors[0]["sidefront"]]["sector"] != 2 or tuple(tuple(vertices[mirrors[0][k]]) for k in ("v1", "v2")) != ((1472, 128), (1472, -128)):
        raise ValueError("Nested mirror must be a one-sided B room boundary")
    demand = [line for line in lines if sides[line["sidefront"]]["texturemiddle"] == CAMERA]
    if len(demand) != 1 or sides[demand[0]["sidefront"]]["sector"] != 0 or tuple(tuple(vertices[demand[0][k]]) for k in ("v1", "v2")) != ((0, 128), (128, 128)):
        raise ValueError("Camera texture lacks its visible main-room material demand")
    user_walls = [line for line in lines if sides[line["sidefront"]]["texturemiddle"] == USER_TEXTURE]
    if (len(user_walls) != 1 or user_walls[0].get("id") != 104 or "sideback" in user_walls[0]
            or sides[user_walls[0]["sidefront"]]["sector"] != 0
            or tuple(tuple(vertices[user_walls[0][k]]) for k in ("v1", "v2")) != ((128, 128), (192, 128))):
        raise ValueError("Identity user material lacks its declared main-room wall demand")
    if len({t["id"] for t in things}) != len(things):
        raise ValueError("Duplicate fixture TID")
    expected_roles = {"player", "camera", "probe", "wall", "flat", "flip-x", "flip-y", "interpolated", "portal-face"} | {f"rotation-{i}" for i in range(1, 9)}
    if {t["role"] for t in things} != expected_roles:
        raise ValueError("Missing required actor role")
    expected_tids = {"player": 4000, "camera": 4100, "wall": 4301, "flat": 4302,
                     "flip-x": 4303, "flip-y": 4304, "interpolated": 4400,
                     "portal-face": 4501, "probe": 4600, **{f"rotation-{i}": 4200+i for i in range(1, 9)}}
    if any(t["id"] != expected_tids[t["role"]] for t in things):
        raise ValueError("Stable observer TID changed")
    for thing in things:
        if any(not math.isfinite(thing[k]) for k in ("x", "y", "height", "angle")) or not 0 <= thing["height"] < 128:
            raise ValueError("Invalid bounded fixture thing")
        if thing["type"] not in (1, 9892, *CLASSES):
            raise ValueError("Unapproved fixture thing type")
        if type(thing["angle"]) is not int or not 0 <= thing["angle"] < 360:
            raise ValueError("UDMF thing angle must be an integer degree")
    by_role = {t["role"]: t for t in things}
    expected_actor_types = {"wall": 32102, "flat": 32103, "flip-x": 32104,
                            "flip-y": 32105, "interpolated": 32106, "portal-face": 32101}
    if any(by_role[role]["type"] != kind for role, kind in expected_actor_types.items()):
        raise ValueError("Representative actor presentation type changed")
    for thing in things:
        x, y = thing["x"], thing["y"]
        if not (-256 < x < 192 and -128 < y < 128 or 1216 < x < 1472 and -128 < y < 128):
            raise ValueError("Fixture thing is outside the two main rooms")
    for role, wanted in (("player", (1, -128, 0, 0, 0)), ("camera", (32100, 1328, -48, 48, 90)), ("probe", (9892, 0, -64, 64, 0))):
        if tuple(by_role[role][k] for k in ("type", "x", "y", "height", "angle")) != wanted:
            raise ValueError("Player, camera or sole safe probe producer changed")
    if sum(t["type"] == 9892 for t in things) != 1:
        raise ValueError("Fixture must contain exactly one authored non-baked probe")
    for k in range(8):
        t = by_role[f"rotation-{k+1}"]
        angle = math.degrees(math.atan2(t["y"], t["x"]+128)) - t["angle"]
        actual = int(((angle+202.5) % 360)/22.5)//2
        if t["type"] != 32101 or actual != k:
            raise ValueError("Authored main-view eight-rotation witness changed")


def zscript() -> str:
    return '''version "4.15.1"
class PFViewFace : Actor
{
    Default { Radius 8; Height 48; Scale 0.5; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: POSS A -1; Stop; }
}
class PFViewWall : PFViewFace { Default { +WALLSPRITE } }
class PFViewFlat : PFViewFace { Default { +FLATSPRITE } }
class PFViewFlipX : PFViewFace { Default { +XFLIP } }
class PFViewFlipY : PFViewFace { Default { +YFLIP } }
class PFViewCamera : Actor
{
    Default { Radius 4; Height 8; CameraHeight 0; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: TNT1 A -1; Stop; }
    override void PostBeginPlay()
    {
        Super.PostBeginPlay();
        TexMan.SetCameraToTexture(self, "PFVCAM", 90);
    }
}
class PFViewInterpolated : PFViewFace
{
    Default { +INTERPOLATEANGLES }
    void PinEndpoints()
    {
        angle = 0;
        SetOrigin((-32, -48, 8), false);
        SetOrigin((-24, -40, 8), true);
        angle = 22.5;
    }
    override void PostBeginPlay() { Super.PostBeginPlay(); PinEndpoints(); }
    override void Tick() { Super.Tick(); PinEndpoints(); }
}
'''


def value_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        if not re.fullmatch(r"[A-Z0-9_-]{1,8}", value):
            raise ValueError("Unsafe UDMF stock name")
        return f'"{value}"'
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Unsupported UDMF value")
    return str(value)


def textmap(scene: dict) -> str:
    validate_scene(scene)
    text = ['namespace = "ZDoom";']
    groups = [("vertex", [dict(zip(("x", "y"), v)) for v in scene["vertices"]]),
              ("sector", scene["sectors"]), ("sidedef", scene["sides"]),
              ("linedef", scene["lines"]), ("thing", scene["things"])]
    for kind, records in groups:
        for record in records:
            text.append(kind + " { " + " ".join(f"{k} = {value_text(v)};" for k, v in record.items() if k != "role") + " }")
    return "\n".join(text) + "\n"


def wad(lumps: list[tuple[str, bytes]]) -> bytes:
    raw, rows = bytearray(b"PWAD"+struct.pack("<II", len(lumps), 0)), []
    for name, payload in lumps:
        if not re.fullmatch(r"[A-Z0-9_]{1,8}", name):
            raise ValueError("Unsafe map lump name")
        rows.append((len(raw), len(payload), name.encode().ljust(8, b"\0")))
        raw.extend(payload)
    struct.pack_into("<I", raw, 8, len(raw))
    for row in rows:
        raw.extend(struct.pack("<II8s", *row))
    return bytes(raw)


def members(scene: dict | None = None) -> dict[str, bytes]:
    scene = scene if scene is not None else fixture()
    script = zscript()
    return {"ZSCRIPT": script.encode(),
            "MAPINFO": ('map PFVTEST "PF freeze view laboratory" { nointermission }\nDoomEdNums\n{\n'
                        + "".join(f"    {i} = {name}\n" for i, name in CLASSES.items()) + "}\n").encode(),
            "ANIMDEFS": b"cameratexture PFVCAM 128 128 fit 128 128\n",
            "TEXTURES": f"WallTexture {USER_TEXTURE}, {USER_EXTENT[0]}, {USER_EXTENT[1]} {{ Patch {USER_STOCK}, 0, 0 }}\n".encode(),
            "GLDEFS": f'material texture {USER_TEXTURE}\n{{\n    shader "{USER_SHADER_MEMBER}"\n}}\n'.encode(),
            USER_SHADER_MEMBER: IDENTITY_SHADER.encode(),
            "maps/PFVTEST.wad": wad([(MAP, b""), ("TEXTMAP", textmap(scene).encode()), ("ENDMAP", b"")])}


def archive_bytes(files: dict[str, bytes]) -> bytes:
    if set(files) != {"ZSCRIPT", "MAPINFO", "ANIMDEFS", "TEXTURES", "GLDEFS", USER_SHADER_MEMBER, "maps/PFVTEST.wad"}:
        raise ValueError("Package contains unapproved assets or prebaked data")
    expected = {"TEXTURES": f"WallTexture {USER_TEXTURE}, {USER_EXTENT[0]}, {USER_EXTENT[1]} {{ Patch {USER_STOCK}, 0, 0 }}\n".encode(),
                "GLDEFS": f'material texture {USER_TEXTURE}\n{{\n    shader "{USER_SHADER_MEMBER}"\n}}\n'.encode(),
                USER_SHADER_MEMBER: IDENTITY_SHADER.encode()}
    if any(files[name] != payload for name, payload in expected.items()):
        raise ValueError("Identity user material source, stock alias or shader binding changed")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = info.external_attr = 0
            archive.writestr(info, files[name])
    return output.getvalue()


def observation_contract(scene: dict) -> dict:
    return {"executed": False, "accepted": False, "requestedRenderFraction": 0.5,
            "fractionRequestIsEngineCVar": False,
            "actualStateRequiredForBothBaselineAndCandidate": True,
            "interpolation": {"tid": 4400, "previous": [-32, -48, 8], "current": [-24, -40, 8],
                              "previousYaw": 0, "currentYaw": 22.5,
                              "expectedAtRequestedFraction": [-28, -44, 8], "expectedYawAtRequestedFraction": 11.25,
                              "positiveActorDrawContext": "MainView",
                              "fractionContexts": ["MainView", "CameraTexture"], "probeFractionMustRemain": 1},
            "requiredRoutes": ["main", "linked-101-to-102", "linked-then-mirror-depth2",
                                "camera-material-demand", "camera-completed-update-and-sampling", "probe-faces-0-through-5",
                                "identity-user-material-PFVUSR"],
            "userShader": {"texture": USER_TEXTURE, "stockSource": USER_STOCK, "extent": list(USER_EXTENT),
                           "sourceMember": USER_SHADER_MEMBER, "sourceSha256": sha(IDENTITY_SHADER.encode()),
                           "identityBodyOf": "wadsrc/static/shaders/scene/material_default.glsl",
                           "entryPoint": "SetupMaterial", "materialType": "SHADER_Default",
                           "lineId": 104, "linedefArrayIndex": next(i for i, line in enumerate(scene["lines"]) if line.get("id") == 104),
                           "endpointsXY": [[128, 128], [192, 128]], "frontSector": 0,
                           "actualUserShaderDrawRequired": True, "executed": False,
                           "classification": "Use actual engine FIRST_USER_SHADER and observed EffectState; no guessed numeric cutoff."},
            "portalDisplacement": [1024, 0], "nestedMirrorMinimumDepth": 2,
            "spriteTids": {t["role"]: t["id"] for t in scene["things"] if t["type"] in CLASSES and t["type"] != 32100},
            "mainLogicalRotationsRequested": list(range(1, 9)),
            "stateRequirements": ["actual root/pass/parent/epoch identities and parent restoration",
                                  "actual viewport fraction and actor Prev/Pos/PrevAngles/Angles",
                                  "selected texture/frame, paired Flip, face/wall/flat type, UV and four emitted vertices",
                                  "actual pipeline/shader/render-pass keys and compilation/cache route",
                                   "actual PFVUSR user material shader lookup/pipeline and public source identity; authored presence is insufficient",
                                  "actual camera registration, later material demand, completed callback and sampled image",
                                  "six actual probe faces, completion barrier, unchanged probe interpolation",
                                  "owned legal sampled captures, normal fence, invalidation and retirement",
                                  "actual main PNG and postprocess path; no omitted/overflowed events"],
            "captureConstraint": "Sample completed camera/probe views into an owned transfer-capable target; do not transfer-read production images.",
            "imageEquivalenceTolerance": {"status": "unassigned-unaccepted", "requiresPreregistrationBeforeNativeComparison": True},
            "limitations": ["Preparation and source projections do not prove route reachability or ZScript compilation.",
                            "Requested .5 needs an explicitly scoped native observer hook; ordinary timer fraction is not controlled here.",
                            "Identity user material authoring does not prove a native draw, general user shader compatibility or generalized/library map reuse.",
                            "This immediate fixture does not qualify LevelMesh, plane mirrors, stereo, SavePicture, or full freeze coverage.",
                            "No authored PBR material, copied IWAD pixels, prebaked lighting, STOP campaign, performance or human visual claim."]}


def configuration() -> str:
    settings = "\n".join(f"{k}={str(v).lower()}" for k, v in SETTINGS.items())
    return ("[GlobalSettings]\nvid_preferbackend=1\nvid_fullscreen=false\nwin_w=640\nwin_h=480\n"
            "vid_vsync=false\nvid_maxfps=60\nvid_gamma=1\nvid_brightness=0\nvid_contrast=1\n"
            + settings + "\n\n[Doom.ConsoleVariables]\nscreenblocks=12\ncrosshair=0\n")


def source_identity(root: Path = ROOT) -> dict:
    rows = {}
    for name in SOURCE_FILES:
        raw = (root/name).read_bytes()
        rows[name] = {"rawSha256": sha(raw), "normalizedLfSha256": sha(raw.replace(b"\r\n", b"\n")), "bytes": len(raw)}
    return rows


def prepare(out: Path, iwad: Path, *, root: Path = ROOT) -> dict:
    root = root.resolve(strict=True)
    build = (root/"build").resolve()
    if not build.is_relative_to(root) or build == root:
        raise ValueError("Resolved build directory escapes this source repository")
    out = out.resolve()
    if not out.is_relative_to(build) or out == build or out.exists():
        raise ValueError("Output must be a fresh child of this repository's ignored build directory")
    if any(c in out.as_posix() for c in '\r\n"\0;'):
        raise ValueError("Unsafe output path")
    iwad = iwad.resolve(strict=True)
    pin = file_identity(iwad)
    if pin["sha256"] != IWAD_SHA256:
        raise ValueError("IWAD differs from the pinned isolated Doom2 input")
    if any(p != iwad for p in iwad.parent.iterdir() if p.suffix.lower() == ".wad"):
        raise ValueError("Adjacent WAD would make actual loaded content ambiguous")
    stock = stock_assets(iwad.read_bytes())
    before = source_identity(root)
    scene, files = fixture(), members()
    package, config = archive_bytes(files), configuration().encode()
    if before != source_identity(root) or file_identity(iwad) != pin:
        raise ValueError("Preparation source or IWAD changed")
    out.mkdir(parents=True)
    mod, cfg = out/"pf020-freeze-views.pk3", out/"fixture.ini"
    mod.write_bytes(package)
    cfg.write_bytes(config)
    manifest = {"schema": SCHEMA, "status": "prepared-unaccepted", "gpuExecuted": False,
                "iwad": {**pin, "copiedIntoPackage": False}, "stockAssets": stock,
                "mod": {**file_identity(mod), "members": {name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in files.items()}},
                "config": file_identity(cfg), "settings": SETTINGS, "requestedClientExtent": EXTENT,
                "preMapCommands": [f"{k} {str(v).lower()}" for k, v in SETTINGS.items()],
                "fixtureInterfaceSources": before, "scene": scene, "observationContract": observation_contract(scene),
                "preparationNotes": ["Ignored local manifest is disposable acceptance input, never programme authority.",
                                     "Root must pin actual native build/source, loaded packages, core/sync mode and device before any claim.",
                                     "No engine was launched; no map/sprite/shader route is marked executed."]}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--iwad", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.out, args.iwad)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"status": result["status"], "manifest": str(args.out.resolve()/"manifest.json"), "gpuExecuted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
