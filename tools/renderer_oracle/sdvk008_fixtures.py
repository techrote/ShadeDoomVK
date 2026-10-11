"""Finite authored SDVK-008 recipes; preparation is not native qualification.

The timing families share identical archive bytes between OFF and ON. Only
declared relief controls differ. Advanced visual gates stay explicitly missing
until they have directional oracles and independently reviewed native evidence.
"""
from __future__ import annotations

import copy
from .sdvk008_marker import REVISION as DIRECTION_WITNESS_REVISION, source_projected_marker_direction

FIXTURE_REVISION = "sdvk008-camera-bam-v2"
MATERIAL_ASSERTION_REVISION = "sdvk008-material-bindings-v3"
BOOTSTRAP_REVISION = "sdvk008-no-startup-v1"


def validate_bootstrap(native: dict) -> None:
    if native.get("bootstrap_revision") != BOOTSTRAP_REVISION:
        raise ValueError("SDVK-008 bootstrap revision differs")
    if native.get("argv", []).count("-nostartup") != 1:
        raise ValueError("SDVK-008 requires exactly one -nostartup before initialization")


def validate_direction_witness(native: dict) -> None:
    if native.get("relief_family") == "single" and native.get("direction_witness_revision") != DIRECTION_WITNESS_REVISION:
        raise ValueError("SDVK-008 source-projected direction witness revision differs")


def canonical_view_angle(degrees: int) -> float:
    """DAngle::Normalized180: nearest-even BAM, then signed BAM to degrees.

    See vectors.h BAMs/Normalized180 and xs_Float.h xs_CRoundToInt. This is
    deliberately not floor: authored 87 degrees rounds upward in BAM space.
    """
    if type(degrees) is not int or not -32768 <= degrees <= 32767:
        raise ValueError("SDVK-008 UDMF camera angles must be authored integers in short range")
    bam = round(degrees * (0x40000000 / 90.0)) & 0xffffffff
    signed_bam = bam if bam < 0x80000000 else bam - 0x100000000
    return signed_bam * (90.0 / 0x40000000)


def validate_camera(native: dict) -> dict:
    authored = native.get("authored_camera_angles", {})
    if set(authored) != {"yaw", "pitch", "roll"}:
        raise ValueError("SDVK-008 requires separate authored camera angles")
    if native.get("fixture_revision") != FIXTURE_REVISION:
        raise ValueError("SDVK-008 camera fixture revision differs")
    for key, value in authored.items():
        if native["camera"][key] != canonical_view_angle(value):
            raise ValueError("SDVK-008 expected camera differs from canonical BAM conversion")
    return authored

TIMING_VARIANTS = {name: "sdvk008-" + name.lower() for name in
                   ("S0", "SL", "SM", "SH", "M0", "MM", "MH", "G0", "GH", "P0", "PM")}
CORRECTNESS_PAIRS = [
    {"id": "default-off", "off": "sdvk008-default-off", "on": "sdvk008-s0", "oracle": "exact"},
    {"id": "heightless", "off": "sdvk008-heightless-off", "on": "sdvk008-heightless-on", "oracle": "exact"},
    *({"id": "single-" + q, "off": "sdvk008-s0", "on": "sdvk008-s" + q, "oracle": "effect"}
      for q in ("l", "m", "h")),
    {"id": "alpha", "off": "sdvk008-alpha-off", "on": "sdvk008-alpha-on", "oracle": "silhouette",
     "background": "sdvk008-alpha-background"},
    {"id": "mirror", "off": "sdvk008-mirror-off", "on": "sdvk008-mirror-on", "oracle": "mirror"},
    {"id": "pbr", "off": "sdvk008-p0", "on": "sdvk008-pm", "oracle": "effect"},
    {"id": "grazing", "off": "sdvk008-g0", "on": "sdvk008-gh", "oracle": "effect"},
    {"id": "grazing-fallback", "off": "sdvk008-grazing-fallback-off",
     "on": "sdvk008-grazing-fallback-on", "oracle": "exact"},
    *({"id":"single-" + flip, "off":"sdvk008-"+flip+"-off",
       "on":"sdvk008-"+flip+"-on", "oracle":"effect"} for flip in ("flipx","flipy")),
]
AVAILABLE_GATES = ("default-off-equivalence", "heightless-equivalence", "visible-effect",
                   "same-build-repeatability", "emitted-basis-and-material-state",
                   "directional-displacement", "alpha-silhouette-matte",
                   "grazing-hard-fallback-equivalence")
MISSING_GATES = ("mirror-direction", "actor-x-y-mirror-direction",
                 "portal-relief-parity", "invalid-height-native-fallback",
                 "invalid-view-native-fallback", "grazing-and-distance-bounds",
                 "atlas-and-filter-footprint", "semantic-pbr-uv-coherence")
REQUIRED_GATES = AVAILABLE_GATES + MISSING_GATES
FAMILIES = {"single", "multiple", "grazing", "grazing-fallback", "pbr", "heightless", "alpha", "alpha-background", "mirror", "flipx", "flipy"}


def material_assertions(family: str) -> dict:
    """Exact authored prefixes and appended height from FMaterial's layout.

    The three intervening engine placeholders are checked by run.py semantics
    and the exact total count. They are not authored bright/detail/glow layers.
    Source lump ordinals vary with loaded packages; only positive authored lump
    identity and the generated channel dimensions are part of this contract.
    """
    if family not in FAMILIES:
        raise ValueError("Unknown SDVK-008 fixture family")
    pbr = ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"]
    spec = ["albedo", "normal", "legacy-specular"]
    prefixes = {"SDVEA0": pbr if family == "pbr" else ["albedo"]}
    if family == "alpha-background":
        prefixes = {"SDVW": ["albedo"], "SDVFL": ["albedo"]}
    elif family == "mirror":
        prefixes = {name: spec for name in ("SDVRA1", "SDVRA2A8", "SDVRA3A7", "SDVRA4A6", "SDVRA5")}
        prefixes.update(SDVPA0=pbr, SDVLA0=["albedo"])
    heights = {} if family in ("heightless", "alpha-background") else {
        "SDVRA1" if family == "mirror" else "SDVEA0": {"binding": 6 if family == "mirror" else 8 if family == "pbr" else 4,
                                                       "requested_sampling": 1}}
    sampling, counts = {}, {}
    for name, prefix in prefixes.items():
        requirements = []
        for binding, semantic in enumerate(prefix):
            extent = 16 if family == "alpha-background" else 128 if family != "mirror" else 64 if binding == 0 else 16
            linear = (family == "pbr" and binding > 0) or (family == "mirror" and name == "SDVRA1" and semantic == "normal")
            requirements.append({"semantic": semantic, "binding": binding,
                "requested_sampling": 1 if linear else -1,
                "min_filter": int(linear), "mag_filter": int(linear), "mipmap_mode": int(linear),
                "source_extent": [extent, extent]})
        if name in heights:
            requirements.append({"semantic": "height", **heights[name],
                "min_filter": 1, "mag_filter": 1, "mipmap_mode": 1, "source_extent": [128, 128]})
        sampling[name] = requirements
        counts[name] = len(prefix) + 3 + int(name in heights)
    return {"material_semantics": prefixes, "material_height_layers": heights,
            "material_layer_sampling": sampling, "material_layer_count": counts}


def validate_material_assertions(native: dict) -> None:
    if native.get("material_assertion_revision") != MATERIAL_ASSERTION_REVISION:
        raise ValueError("SDVK-008 material assertion revision differs")
    expected = material_assertions(native["relief_family"])
    actual = native.get("state_assertions", {})
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError("SDVK-008 material assertions differ from authored binding contract")
    if set(actual.get("materials", [])) != set(expected["material_semantics"]):
        raise ValueError("SDVK-008 material assertions require every authored material")


def red_marker_direction(off_rgb: bytes, on_rgb: bytes, width: int, height: int) -> dict:
    """Retained legacy aggregate diagnostic, never a hard direction gate.

    Area/Jacobian changes can reverse a centroid despite uniformly rightward
    material-point motion. Deletion can also give a false positive. Keep this
    historical algorithm callable to reproduce the preserved negative receipt.
    """
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("Invalid marker extent")
    if len(off_rgb) != width*height*3 or len(on_rgb) != width*height*3:
        raise ValueError("Marker witness needs matched RGB8 images")
    def centroid(raw):
        count = sx = sy = 0
        for i in range(width*height):
            r,g,b = raw[3*i:3*i+3]
            # The stripe is red; generated room/blue/yellow sprite areas fail
            # this dominance predicate even under the fixed warm direct light.
            if r >= 80 and r >= 1.8*g and r >= 1.35*b:
                count += 1
                sx += i % width
                sy += i // width
        return (count, sx/count if count else None, sy/count if count else None)
    off,on = centroid(off_rgb),centroid(on_rgb)
    result = {"status":"UNAVAILABLE", "off_pixels":off[0], "on_pixels":on[0],
              "delta_x_px":None, "delta_y_px":None, "expected_sign":[1,-1],
              "minimum_centroid_shift_px":0.05,
              "scope":"single-fixed-wall-card-red-stripe-centroid"}
    if min(off[0],on[0]) < 8:
        result["reason"] = "Authored marker has fewer than eight visible pixels"
        return result
    dx,dy = on[1]-off[1],on[2]-off[2]
    result.update(delta_x_px=dx,delta_y_px=dy,
                  status="PASS" if dx >= .05 and dy <= -.05 else "FAIL")
    return result


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
    authored_angles = validate_camera(native)
    family = native["relief_family"]
    if family not in FAMILIES:
        raise ValueError("Unknown SDVK-008 fixture family")
    validate_direction_witness(native)
    validate_material_assertions(native)
    if family == "mirror":
        inherited = copy.deepcopy(scene)
        inherited["native"]["generator"] = "sprite_mirror"
        # The inherited generator uses scene id in MAPINFO, so pin family id.
        inherited["id"] = "sdvk008-mirror"
        members, metadata = prep.authored_members(inherited)
        members["textures/SDVH.png"] = prep.png_rgba(128, 128, pixels("height"))
        metadata.update(relief_family=family, height_surface="asymmetric-nonflat",
                        fixture_revision=FIXTURE_REVISION, authored_camera_angles=authored_angles,
                        material_assertion_revision=MATERIAL_ASSERTION_REVISION,
                        directional_native_qualified=False)
        return members, metadata
    model = prep._Map(ceiling=256)
    model.boundary([(-384, -256), (-384, 256), (384, 256), (384, -256)], ["SDVW"]*4)
    camera = native["camera"]
    cx, cy, cz = camera["position"]
    model.thing(1, cx-48, cy, tid=2001)
    model.thing(32200, cx, cy, cz, angle=authored_angles["yaw"], pitch=authored_angles["pitch"], tid=2002)
    members = prep._base_members()
    members["textures/SDVW.png"] = prep.png_rgba(16, 16, bytes((42, 47, 53, 255))*256)
    members["flats/SDVFL.png"] = prep.png_rgba(16, 16, bytes((26, 31, 37, 255))*256)
    members["sprites/SDVEA0.png"] = prep.png_rgba(128, 128,
        pixels("alpha" if family in ("alpha", "alpha-background") else "albedo"), offset=(64, 128))
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
    if family in ("flipx", "flipy"):
        flag = "+XFLIP" if family == "flipx" else "+YFLIP"
        members["ZSCRIPT"] = members["ZSCRIPT"].replace(
            b"+WALLSPRITE }\n    States { Spawn: SDVE", ("+WALLSPRITE " + flag + " }\n    States { Spawn: SDVE").encode())
    layers = '' if family == "heightless" else ' height "SDVEH" { filter linear }\n'
    if family == "pbr":
        layers = (' normal "SDVEN" { filter linear }\n metallic "SDVEM" { filter linear }\n'
                  ' roughness "SDVER" { filter linear }\n ao "SDVEAO" { filter linear }\n') + layers
    members["GLDEFS"] = ("material sprite SDVEA0\n{\n" + layers + "}\n").encode() if layers else b""
    cards = [(0, 0, 180)]
    if family == "alpha-background":
        cards = []
    if family == "multiple":
        cards = [(i*10, (i%3-1)*20, 180) for i in range(8)]
    if family == "grazing":
        cards = [(0, (i-2)*64, angle) for i, angle in enumerate((180, 140, 110, 100, 90))]
    for i, (x,y,angle) in enumerate(cards):
        model.thing(32218, x, y, angle=angle, tid=4600+i)
    # Same constant direct light within every matched family; enables PBR path.
    model.thing(9800, -96, -96, 128, tid=4500, arg0=255, arg1=208, arg2=156, arg3=256)
    map_name = native["map"]
    title_family = "alpha" if family == "alpha-background" else family
    members["MAPINFO"] = (f'map {map_name} "SDVK008 {title_family}" {{ nointermission }}\n'
        'DoomEdNums\n{\n 32200 = SDVKFixedCamera\n 32218 = SDVKReliefCard\n}\n').encode()
    members[f"maps/{map_name}.wad"] = prep.pf_indexed.wad(
        [(map_name,b""),("TEXTMAP",model.text().encode()),("ENDMAP",b"")])
    return members, {"geometry": "authored_udmf", "textures": "generated_rgba_only",
        "native_executed": False, "relief_family": family, "camera_actor_tid": 2002,
        "fixture_revision": FIXTURE_REVISION, "authored_camera_angles": authored_angles,
        "material_assertion_revision": MATERIAL_ASSERTION_REVISION,
        "camera_position_world": camera["position"], "player_start_world": [cx-48,cy],
        "authored_relief_card_count": len(cards), "relief_card_tids": list(range(4600,4600+len(cards))),
        "height_surface": "asymmetric-nonflat", "card_angles": [c[2] for c in cards],
        "height_semantics": "red-linear", "albedo_sampling": "nearest", "height_sampling": "linear-mipmap",
        "directional_native_qualified": False, "alpha_matte_native_qualified": False,
        "counts": {kind:len(rows) for kind,rows in model.records.items()},
        "boundary_signed_areas": model.polygon_areas}
