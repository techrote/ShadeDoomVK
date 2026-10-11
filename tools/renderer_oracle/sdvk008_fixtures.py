"""Finite authored SDVK-008 recipes; preparation is not native qualification.

The timing families share identical archive bytes between OFF and ON. Only
declared relief controls differ. Advanced visual gates stay explicitly missing
until they have directional oracles and independently reviewed native evidence.
"""
from __future__ import annotations

import copy

TIMING_VARIANTS = {name: "sdvk008-" + name.lower() for name in
                   ("S0", "SL", "SM", "SH", "M0", "MM", "MH", "G0", "GH", "P0", "PM")}
CORRECTNESS_PAIRS = [
    {"id": "default-off", "off": "sdvk008-default-off", "on": "sdvk008-s0", "oracle": "exact"},
    {"id": "heightless", "off": "sdvk008-heightless-off", "on": "sdvk008-heightless-on", "oracle": "exact"},
    *({"id": "single-" + q, "off": "sdvk008-s0", "on": "sdvk008-s" + q, "oracle": "effect"}
      for q in ("l", "m", "h")),
    {"id": "alpha", "off": "sdvk008-alpha-off", "on": "sdvk008-alpha-on", "oracle": "silhouette"},
    {"id": "mirror", "off": "sdvk008-mirror-off", "on": "sdvk008-mirror-on", "oracle": "mirror"},
    {"id": "pbr", "off": "sdvk008-p0", "on": "sdvk008-pm", "oracle": "effect"},
    {"id": "grazing", "off": "sdvk008-g0", "on": "sdvk008-gh", "oracle": "effect"},
]
AVAILABLE_GATES = ("default-off-equivalence", "heightless-equivalence", "visible-effect",
                   "same-build-repeatability", "emitted-basis-and-material-state")
MISSING_GATES = ("directional-displacement", "alpha-silhouette-matte", "mirror-direction",
                 "portal-relief-parity", "invalid-height-native-fallback",
                 "invalid-view-native-fallback", "grazing-and-distance-bounds",
                 "atlas-and-filter-footprint", "semantic-pbr-uv-coherence")
REQUIRED_GATES = AVAILABLE_GATES + MISSING_GATES
FAMILIES = {"single", "multiple", "grazing", "pbr", "heightless", "alpha", "mirror"}


def pixels(kind: str) -> bytes:
    """128-square asymmetric authored channels, no external image dependencies."""
    result = bytearray()
    for y in range(128):
        for x in range(128):
            if kind == "height":
                # Tilted, stepped surface; neither a flat height nor symmetric.
                h = 24 + (3*x + y)//4
                if 25 <= x < 57 and 30 <= y < 94:
                    h = 208
                if 74 <= x < 91 and 16 <= y < 67:
                    h = 48
                rgba = (h, h, h, 255)
            elif kind == "normal":
                rgba = (202, 93, 226, 255) if x < 49 else (92, 177, 237, 255)
            elif kind == "roughness":
                rgba = (48, 48, 48, 255) if y < 79 else (210, 210, 210, 255)
            elif kind == "metallic":
                rgba = (230, 230, 230, 255) if x > 76 else (12, 12, 12, 255)
            elif kind in ("albedo", "alpha"):
                # Sharp direction witnesses plus nonperiodic bands, at nearest
                # albedo sampling. Measured effect must be observed, not assumed.
                rgba = (230, 196, 51, 255) if (x//7 + y//13) % 2 else (38, 103, 205, 255)
                if 26 <= x < 33 or 83 <= y < 88:
                    rgba = (241, 55, 89, 255)
                if kind == "alpha" and (x < 5 or y < 5 or x >= 123 or y >= 123 or
                                         (47 <= x < 67 and 39 <= y < 92)):
                    rgba = (0, 0, 0, 0)
            else:
                raise ValueError("Unknown SDVK-008 channel")
            result.extend(rgba)
    return bytes(result)


def authored_members(scene: dict, prep) -> tuple[dict[str, bytes], dict]:
    native = scene["native"]
    family = native["relief_family"]
    if family not in FAMILIES:
        raise ValueError("Unknown SDVK-008 fixture family")
    if family == "mirror":
        inherited = copy.deepcopy(scene)
        inherited["native"]["generator"] = "sprite_mirror"
        # The inherited generator uses scene id in MAPINFO, so pin family id.
        inherited["id"] = "sdvk008-mirror"
        members, metadata = prep.authored_members(inherited)
        members["textures/SDVH.png"] = prep.png_rgba(128, 128, pixels("height"))
        metadata.update(relief_family=family, height_surface="asymmetric-nonflat",
                        directional_native_qualified=False)
        return members, metadata
    model = prep._Map(ceiling=256)
    model.boundary([(-384, -256), (-384, 256), (384, 256), (384, -256)], ["SDVW"]*4)
    camera = native["camera"]
    cx, cy, cz = camera["position"]
    model.thing(1, cx-48, cy, tid=2001)
    model.thing(32200, cx, cy, cz, angle=camera["yaw"], pitch=camera["pitch"], tid=2002)
    members = prep._base_members()
    members["textures/SDVW.png"] = prep.png_rgba(16, 16, bytes((42, 47, 53, 255))*256)
    members["flats/SDVFL.png"] = prep.png_rgba(16, 16, bytes((26, 31, 37, 255))*256)
    members["sprites/SDVEA0.png"] = prep.png_rgba(128, 128,
        pixels("alpha" if family == "alpha" else "albedo"), offset=(64, 128))
    members["textures/SDVEH.png"] = prep.png_rgba(128, 128, pixels("height"))
    members["textures/SDVEN.png"] = prep.png_rgba(128, 128, pixels("normal"))
    members["textures/SDVER.png"] = prep.png_rgba(128, 128, pixels("roughness"))
    members["textures/SDVEM.png"] = prep.png_rgba(128, 128, pixels("metallic"))
    members["textures/SDVEAO.png"] = prep.png_rgba(128, 128, bytes((255,255,255,255))*16384)
    members["ZSCRIPT"] += b'''
class SDVKReliefCard : Actor
{
    Default { Radius 1; Height 128; +NOGRAVITY +NOBLOCKMAP +WALLSPRITE }
    States { Spawn: SDVE A -1; Stop; }
}
'''
    layers = '' if family == "heightless" else ' height "SDVEH" { filter linear }\n'
    if family == "pbr":
        layers = (' normal "SDVEN" { filter linear }\n metallic "SDVEM" { filter linear }\n'
                  ' roughness "SDVER" { filter linear }\n ao "SDVEAO" { filter linear }\n') + layers
    members["GLDEFS"] = ("material sprite SDVEA0\n{\n" + layers + "}\n").encode() if layers else b""
    cards = [(0, 0, 180)]
    if family == "multiple":
        cards = [(i*10, (i%3-1)*20, 180) for i in range(8)]
    if family == "grazing":
        cards = [(0, (i-2)*64, angle) for i, angle in enumerate((180, 140, 110, 100, 90))]
    for i, (x,y,angle) in enumerate(cards):
        model.thing(32218, x, y, angle=angle, tid=4600+i)
    # Same constant direct light within every matched family; enables PBR path.
    model.thing(9800, -96, -96, 128, tid=4500, arg0=255, arg1=208, arg2=156, arg3=256)
    map_name = native["map"]
    members["MAPINFO"] = (f'map {map_name} "SDVK008 {family}" {{ nointermission }}\n'
        'DoomEdNums\n{\n 32200 = SDVKFixedCamera\n 32218 = SDVKReliefCard\n}\n').encode()
    members[f"maps/{map_name}.wad"] = prep.pf_indexed.wad(
        [(map_name,b""),("TEXTMAP",model.text().encode()),("ENDMAP",b"")])
    return members, {"geometry": "authored_udmf", "textures": "generated_rgba_only",
        "native_executed": False, "relief_family": family, "camera_actor_tid": 2002,
        "camera_position_world": camera["position"], "player_start_world": [cx-48,cy],
        "authored_relief_card_count": len(cards), "relief_card_tids": list(range(4600,4600+len(cards))),
        "height_surface": "asymmetric-nonflat", "card_angles": [c[2] for c in cards],
        "height_semantics": "red-linear", "albedo_sampling": "nearest", "height_sampling": "linear-mipmap",
        "directional_native_qualified": False, "alpha_matte_native_qualified": False,
        "counts": {kind:len(rows) for kind,rows in model.records.items()},
        "boundary_signed_areas": model.polygon_areas}
