"""Original SHADOW-002 native fixture assets and geometric image witnesses.

The source art is a deliberately asymmetric alpha card, with two large holes,
transparent outer margins and a side notch. No game/IWAD pixels are copied.
These helpers describe expected geometry; only native_capture awards a rendered
result. SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import math

from tools.renderer_oracle import prepare

MAP = "SDVSHD"
EXTENT = (640, 480)
RED_LIGHT = (-144.0, -96.0, 96.0)
BLUE_LIGHT = (256.0, 96.0, 128.0)
CAMERA = (0.0, -256.0, 96.0)
ORBIT_CAMERA = (64.0, -256.0, 96.0)
WALL_Y = 160.0
ACTOR_TID = 21502
SOURCE_SIZE = (64, 96)
# Preserve a measurable ambient channel in every material model. At lightlevel
# 80 the inherited PBR ambient response quantizes to RGB green=3, below the
# fixed image control minimum of 4; 128 gives that control useful headroom.
AMBIENT_LIGHTLEVEL = 128


def opaque(x, y, *, solid=False):
    if not (4 <= x < 60 and 4 <= y < 92):
        return False
    if solid:
        return True
    return not ((24 <= x < 40 and (18 <= y < 36 or 58 <= y < 76))
                or (44 <= x < 60 and 38 <= y < 52))


def camera(variant):
    return (ORBIT_CAMERA, 100.0) if variant == "orbit" else (CAMERA, 90.0)


def source_to_world(x, y, *, receiver, flip=False):
    """Project an interior source texel from the emitter onto a real receiver.

    HWSprite's signed horizontal texture convention is source U decreasing
    along the (-normal.y, normal.x) tangent. This is independent of the camera.
    """
    nx, ny = -RED_LIGHT[0], -RED_LIGHT[1]
    length = math.hypot(nx, ny)
    nx, ny = nx / length, ny / length
    horizontal = 32.0 - (x + 0.5)
    if flip:
        horizontal = -horizontal
    hit = (-ny * horizontal, nx * horizontal, 96.0 - (y + 0.5))
    direction = tuple(hit[i] - RED_LIGHT[i] for i in range(3))
    if receiver == "floor":
        t = -RED_LIGHT[2] / direction[2]
    elif receiver == "wall":
        t = (WALL_Y - RED_LIGHT[1]) / direction[1]
    else:
        raise ValueError("Unknown receiver")
    if t <= 1.0:
        raise ValueError("Witness is not beyond the actor")
    point = tuple(RED_LIGHT[i] + t * direction[i] for i in range(3))
    if not (-384 < point[0] < 384 and -320 < point[1] <= WALL_Y and 0 <= point[2] < 224):
        raise ValueError("Witness misses its actual receiver")
    return point


def project(point, *, variant="base", extent=EXTENT):
    origin, yaw = camera(variant)
    angle = math.radians(yaw)
    dx, dy, dz = (point[i] - origin[i] for i in range(3))
    depth = dx * math.cos(angle) + dy * math.sin(angle)
    right = dx * math.sin(angle) - dy * math.cos(angle)
    if depth <= 0:
        raise ValueError("Witness is behind camera")
    focal = extent[0] * 0.5  # 90 degree horizontal FOV, ordinary 4:3 viewport.
    return (extent[0] * 0.5 + right * focal / depth,
            extent[1] * 0.5 - dz * focal / depth)


def receiver_patch_is_clear(sample, origin, yaw, *, extent=EXTENT):
    """Conservatively exclude the foreground sprite from every sampled pixel.

    With gl_billboard_faces_camera=false the actual visible card is parallel to
    the view plane. Intersect the outer edges of the full 3x3 pixel patch with
    that plane, then exclude its entire expanded source rectangle, including
    transparent margins. No alpha hole is used to claim an unobstructed view.
    """
    angle = math.radians(yaw)
    forward, right = (math.cos(angle), math.sin(angle)), (math.sin(angle), -math.cos(angle))
    card_depth = -sum(origin[i] * forward[i] for i in range(2))
    if card_depth <= 0:
        return True
    cx, cy = (round(value) for value in sample["pixel"])
    half, focal = sample["half_extent"], extent[0] * 0.5
    floor = abs(sample["world"][2]) < 0.000001
    if not floor and abs(sample["world"][1] - WALL_Y) >= 0.000001:
        raise ValueError("Receiver witness does not lie on the authored floor or wall")
    sides, heights, receiver_depths = [], [], []
    for x in (cx - half, cx + half + 1):
        for y in (cy - half, cy + half + 1):
            u, v = (x - extent[0] * 0.5) / focal, (extent[1] * 0.5 - y) / focal
            ray = (forward[0] + right[0] * u, forward[1] + right[1] * u, v)
            depth = -origin[2] / ray[2] if floor else (WALL_Y - origin[1]) / ray[1]
            if depth <= 0:
                raise ValueError("Receiver patch is behind the camera")
            receiver_depths.append(depth)
            hit = tuple(origin[i] + card_depth * ray[i] for i in range(3))
            sides.append(sum(hit[i] * right[i] for i in range(2)))
            heights.append(hit[2])
    if max(receiver_depths) <= card_depth:
        return True
    # Original 64x96 pixels, offset (32,96), plus the rendering expansion.
    return (max(sides) < -33 or min(sides) > 33
            or max(heights) < -1 or min(heights) > 97)


def witnesses(variant="base"):
    samples = {}
    for receiver, label, xy in (
        ("floor", "opaque", (10, 66)), ("floor", "hole", (31, 66)),
        ("wall", "opaque", (10, 26)), ("wall", "hole", (31, 26)),
        ("floor", "notch", (50, 45)),
    ):
        world = source_to_world(*xy, receiver=receiver)
        samples[f"{receiver}_{label}"] = {"source_xy": list(xy), "world": list(world),
            "pixel": list(project(world, variant=variant)), "half_extent": 1}
    origin, yaw = camera(variant)
    for label, sample in samples.items():
        if not receiver_patch_is_clear(sample, origin, yaw):
            raise ValueError("Foreground sprite occludes receiver witness: " + label)
    # Visible source sprite control: this mid-height opaque strip is clear of
    # both holes and must not darken itself when its own caster is enabled.
    facing = math.radians(yaw)
    right = (math.sin(facing), -math.cos(facing))
    for label, horizontal in (("left", -20.0), ("middle", 0.0), ("right", 20.0)):
        world = (horizontal * right[0], horizontal * right[1], 42.0)
        samples["sprite_" + label] = {"world": list(world),
            "pixel": list(project(world, variant=variant)), "half_extent": 1}
    return samples


def settings(enabled):
    return {
        "vid_rendermode": 4, "vid_fullscreen": False, "vid_vsync": False,
        "vid_maxfps": 0, "cl_capfps": False, "vid_gamma": 1,
        "vid_brightness": 0, "vid_contrast": 1, "gl_ubershaders": False,
        "gl_levelmesh": False, "lm_dynlights": False, "vk_rayquery": False,
        "gl_lightprobe": False, "gl_lights": True, "gl_light_sprites": True,
        "gl_spritelight": 2, "gl_light_shadows": 0,
        "gl_billboard_mode": 0, "gl_billboard_faces_camera": False,
        "gl_actor_light_shadows": bool(enabled), "gl_customshader": True,
        "gl_bloom": False, "gl_ssao": 0, "gl_tonemap": 0, "gl_fxaa": 0,
        "gl_lens": False, "gl_multisample": 0, "gl_texture_filter": 0,
        "gl_texture_filter_anisotropic": 1, "r_drawplayersprites": False,
        "screenblocks": 12, "crosshair": 0, "use_mouse": False,
        "use_joystick": False, "screenshot_type": "png", "screenshot_quiet": True,
        "con_notifylines": 0,
    }


def members(*, material="normal", variant="base"):
    if material not in ("normal", "specular", "pbr"):
        raise ValueError("Unknown material shader")
    if variant not in ("base", "solid", "flip", "orbit", "invisible", "animated"):
        raise ValueError("Unknown controlled fixture change")
    model = prepare._Map(floor=0, ceiling=224)
    model.records["sector"][0].update(lightlevel=AMBIENT_LIGHTLEVEL)
    model.boundary([(-384, -320), (-384, 160), (384, 160), (384, -320)], ["SDVW"] * 4)
    model.thing(1, -352, -288, tid=21500)
    origin, yaw = camera(variant)
    model.thing(32200, *origin, angle=int(yaw), tid=21501)
    model.thing(32201, 0, 0, tid=ACTOR_TID)
    for tid, position, colour in ((21510, RED_LIGHT, (255, 0, 0)),
                                  (21511, BLUE_LIGHT, (0, 0, 255))):
        model.thing(9800, *position, tid=tid, arg0=colour[0], arg1=colour[1],
                    arg2=colour[2], arg3=256, light_noshadowmap=True)
    extra_flag = "+XFLIP" if variant == "flip" else "+INVISIBLE" if variant == "invisible" else ""
    zscript = '''version "4.15.1"
class SH002Camera : Actor
{
    Default { Radius 1; Height 1; CameraHeight 0; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: TNT1 A -1; Stop; }
    override void Tick()
    {
        Super.Tick();
        if (playeringame[0] && players[0].mo != null)
        {
            players[0].camera = self;
            players[0].mo.bInvisible = true;
            players[0].mo.bShootable = false;
        }
    }
}
class SH002Caster : Actor
{
    Default { Radius 24; Height 96; Health 100; +NOGRAVITY +NOBLOCKMAP +SHOOTABLE %s }
    States { Spawn: SH02 A -1; Stop; }
}
''' % extra_flag
    if variant == "animated":
        zscript = zscript.replace("Spawn: SH02 A -1; Stop;", "Spawn: SH02 A 10; SH02 B -1; Stop;")
    pixels = bytes(channel for y in range(96) for x in range(64)
        for channel in (192, 192, 192, 255 if opaque(x, y, solid=variant == "solid") else 0))
    texture = prepare.png_rgba(64, 64, bytes((160, 160, 160, 255)) * 4096)
    result = {
        "ZSCRIPT": zscript.encode(),
        "MAPINFO": (f'map {MAP} "SHADOW-002 alpha and coloured-light controls" {{ nointermission pixelratio = 1.0 }}\n'
            'DoomEdNums { 32200 = SH002Camera\n 32201 = SH002Caster\n }\n').encode(),
        "textures/SDVW.png": texture, "flats/SDVFL.png": texture,
        "sprites/SH02A0.png": prepare.png_rgba(64, 96, pixels, offset=(32, 96)),
        f"maps/{MAP}.wad": prepare.pf_indexed.wad([
            (MAP, b""), ("TEXTMAP", model.text().encode()), ("ENDMAP", b"")]),
    }
    if variant == "animated":
        # Frame B deliberately fills only the asymmetric side notch. The two
        # holes stay clear. A stale frame-A mask therefore fails a fixed native
        # floor witness after the visible actor has actually selected B.
        phase_b = bytes(channel for y in range(96) for x in range(64)
            for channel in (192, 192, 192, 255 if (opaque(x, y)
                or (44 <= x < 60 and 38 <= y < 52)) else 0))
        result["sprites/SH02B0.png"] = prepare.png_rgba(64, 96, phase_b, offset=(32, 96))
    if material != "normal":
        prepare._material_layers(result)
        # A high-roughness dielectric keeps independent light channels easy to
        # discriminate while entering the real PBR fragment-light path.
        result["textures/SDVM.png"] = prepare.png_rgba(16, 16, bytes((0, 0, 0, 255)) * 256)
        result["textures/SDVR.png"] = prepare.png_rgba(16, 16, bytes((220, 220, 220, 255)) * 256)
        if material == "pbr":
            definitions = prepare._pbr("SDVW") + prepare._pbr("SDVFL", "flat") + prepare._pbr("SH02A0", "sprite")
        else:
            definitions = "".join(f'material {kind} {name}\n{{\n normal "SDVN"\n specular "SDVSP"\n}}\n'
                for kind, name in (("texture", "SDVW"), ("flat", "SDVFL"), ("sprite", "SH02A0")))
        result["GLDEFS"] = definitions.encode()
    return result


def archive(**kwargs):
    return prepare.archive_bytes(members(**kwargs))


def recipe(material="normal", variant="base", enabled=False):
    result = {"schema": "shadow002-native-scene/v1", "map": MAP,
        "material": material, "variant": variant, "enabled": enabled,
        "ambient_lightlevel": AMBIENT_LIGHTLEVEL,
        "extent": list(EXTENT), "pixel_ratio": 1.0, "camera_position": list(camera(variant)[0]),
        "camera_yaw": camera(variant)[1], "red_light": list(RED_LIGHT),
        "blue_light": list(BLUE_LIGHT), "source_extent": list(SOURCE_SIZE),
        "source_offset": [32, 96], "settings": settings(enabled),
        "witnesses": witnesses(variant), "warmup_frames": 40, "frames": 1,
        "scope": "real fragment alpha-card visibility; no physical GPU performance claim"}
    if variant == "animated":
        result["settings"]["cl_capfps"] = True
        result["animation"] = {"initial_frame": "SH02A0", "initial_tics": 10,
            "retained_frame": "SH02B0", "policy": "ordinary 35 Hz tic pacing; retained actual material must be B"}
    return result
