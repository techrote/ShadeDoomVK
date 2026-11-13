"""Private, owner-owned Doom II texture gallery inputs; never redistribute output.

Source albedos are decoded from the supplied IWAD, never downloaded. Material
interpretations are procedural demonstrations, not recovered id artist intent.
No source-game material is overridden: gallery aliases are distinct.
"""

from __future__ import annotations
import hashlib
import math
import pathlib
import re
import struct

import numpy as np
from PIL import Image, ImageFilter


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Wad:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = self.path.read_bytes()
        magic, count, directory = struct.unpack_from("<4sii", self.data)
        assert magic == b"IWAD" and 0 < count < 100000
        assert directory >= 12 and directory + count * 16 <= len(self.data)
        self.entries = []
        self.by_name = {}
        for i in range(count):
            offset, size, name = struct.unpack_from(
                "<ii8s", self.data, directory + i * 16
            )
            name = name.rstrip(b"\0").decode("ascii").upper()
            assert offset >= 0 and size >= 0 and offset + size <= len(self.data)
            entry = (name, offset, size, i)
            self.entries.append(entry)
            self.by_name[name] = entry
        self.palette = np.frombuffer(
            self.lump("PLAYPAL")[:768], dtype=np.uint8
        ).reshape(256, 3)
        pnames = self.lump("PNAMES")
        pcount = struct.unpack_from("<i", pnames)[0]
        assert len(pnames) >= 4 + 8 * pcount
        self.pnames = [
            pnames[4 + i * 8 : 12 + i * 8].rstrip(b"\0").decode("ascii").upper()
            for i in range(pcount)
        ]
        self.patch_cache = {}

    def lump(self, name):
        _, offset, size, _ = self.by_name[name]
        return self.data[offset : offset + size]

    def patch(self, name):
        if name in self.patch_cache:
            return self.patch_cache[name]
        data = self.lump(name)
        width, height, _, _ = struct.unpack_from("<hhhh", data)
        assert 0 < width <= 8192 and 0 < height <= 8192
        pixels = np.zeros((height, width, 4), dtype=np.uint8)
        for x in range(width):
            at = struct.unpack_from("<I", data, 8 + x * 4)[0]
            previous = -1
            while True:
                top = data[at]
                if top == 255:
                    break
                length = data[at + 1]
                if top <= previous:
                    top += previous
                previous = top
                assert at + 3 + length < len(data)
                indices = np.frombuffer(data[at + 3 : at + 3 + length], dtype=np.uint8)
                for y in range(length):
                    if 0 <= top + y < height:
                        pixels[top + y, x, :3] = self.palette[indices[y]]
                        pixels[top + y, x, 3] = 255
                at += length + 4
        self.patch_cache[name] = pixels
        return pixels

    def textures(self):
        unique = {}
        definitions = 0
        for lump_name in ("TEXTURE1", "TEXTURE2"):
            if lump_name not in self.by_name:
                continue
            data = self.lump(lump_name)
            count = struct.unpack_from("<i", data)[0]
            for i in range(count):
                at = struct.unpack_from("<i", data, 4 + i * 4)[0]
                raw_name, flags, width, height, _, patch_count = struct.unpack_from(
                    "<8sIhhIh", data, at
                )
                name = raw_name.rstrip(b"\0").decode("ascii").upper()
                assert 0 < width <= 4096 and 0 < height <= 4096 and patch_count >= 0
                pixels = np.zeros((height, width, 4), dtype=np.uint8)
                patch_names = []
                for j in range(patch_count):
                    origin_x, origin_y, pindex, _, _ = struct.unpack_from(
                        "<hhhhh", data, at + 22 + j * 10
                    )
                    pname = self.pnames[pindex]
                    patch_names.append(pname)
                    patch = self.patch(pname)
                    ph, pw = patch.shape[:2]
                    x0, y0 = max(0, origin_x), max(0, origin_y)
                    x1, y1 = min(width, origin_x + pw), min(height, origin_y + ph)
                    if x1 > x0 and y1 > y0:
                        source = patch[
                            y0 - origin_y : y1 - origin_y, x0 - origin_x : x1 - origin_x
                        ]
                        target = pixels[y0:y1, x0:x1]
                        visible = source[:, :, 3] != 0
                        target[visible] = source[visible]
                unique[name] = dict(
                    name=name,
                    kind="wall",
                    pixels=pixels,
                    source_lump=lump_name,
                    source_index=i,
                    patches=patch_names,
                    placeholder=(i == 0 and name == "AASHITTY"),
                )
                definitions += 1
        self.texture_definitions = definitions
        return list(unique.values())

    def flats(self):
        active = False
        result = {}
        for name, offset, size, index in self.entries:
            if re.fullmatch(r"F(?:F|\d+)?_START", name):
                active = True
                continue
            if re.fullmatch(r"F(?:F|\d+)?_END", name):
                # Inner F1_END/F2_END do not terminate the outer F_START range.
                if name in ("F_END", "FF_END"):
                    active = False
                continue
            if active and size:
                assert size == 4096, (name, size)
                indices = np.frombuffer(
                    self.data[offset : offset + size], dtype=np.uint8
                ).reshape(64, 64)
                pixels = np.zeros((64, 64, 4), dtype=np.uint8)
                pixels[:, :, :3] = self.palette[indices]
                pixels[:, :, 3] = 255
                result[name] = dict(
                    name=name,
                    kind="flat",
                    pixels=pixels,
                    source_lump=name,
                    source_index=index,
                    patches=[],
                    placeholder=False,
                )
        return list(result.values())


def family_of(name, kind):
    # Reviewed against a contact sheet of all 150 source flats. Numeric Doom
    # names do not encode semantics: SLIME13..16 are metal floor panels, for
    # example, and must not receive a wet-liquid material by prefix alone.
    if kind == "flat":
        explicit_groups = {
            "metal": "FLOOR0_1 FLOOR0_3 FLOOR0_6 FLOOR4_1 FLOOR4_5 FLOOR4_8 FLOOR5_1 STEP1 STEP2 MFLR8_1 FLAT23 CEIL3_5 CEIL3_6 FLAT4 SLIME13 SLIME14 SLIME15 SLIME16 CRATOP1",
            "painted panels": "FLOOR0_5 FLOOR0_7 FLAT1 FLAT18 FLAT20 CEIL3_1 CEIL3_2 CEIL3_3 CEIL3_4 FLAT3 FLAT9 COMP01",
            "painted technology": "FLOOR1_1 FLOOR1_7 TLITE6_1 TLITE6_4 TLITE6_5 TLITE6_6 CEIL4_2 CEIL4_3 FLAT2 FLAT14 FLAT22 CONS1_1 CONS1_5 CONS1_7 CEIL1_2 CEIL1_3 CEIL4_1 FLAT17 GRNLITE1",
            "wood": "FLOOR0_2 FLOOR3_3 FLOOR7_1 FLAT5_4 FLAT5_5 CEIL1_1 FLAT5_1 FLAT5_2 CRATOP2",
            "brick / mortar": "FLOOR4_6 FLOOR5_4 FLAT1_1 FLAT1_2 FLAT8 RROCK12 RROCK14 RROCK15",
            "stone / concrete": "FLOOR5_2 FLOOR5_3 FLOOR6_2 FLOOR7_2 FLAT5 FLAT10 MFLR8_2 MFLR8_3 MFLR8_4 DEM1_5 DEM1_6 FLAT5_7 FLAT5_8 FLAT19 GRNROCK RROCK03 RROCK04 RROCK10 RROCK11 RROCK13 RROCK16 RROCK17 RROCK18 RROCK19 RROCK20",
            "lava crust": "FLOOR6_1 RROCK01 RROCK02 RROCK05 RROCK06 RROCK07 RROCK08 RROCK09 SLIME09 SLIME10 SLIME11 SLIME12",
            "carved stone": "DEM1_1 DEM1_2 DEM1_3 DEM1_4 GATE1 GATE2 GATE3 GATE4",
            "organic": "SFLR6_1 SFLR6_4 SFLR7_1 SFLR7_4 FLAT5_6",
            "fabric": "FLOOR1_6 FLAT5_3",
            "vegetation": "GRASS1 GRASS2",
        }
        for family, names in explicit_groups.items():
            if name in names.split():
                return family
        if re.fullmatch(r"SLIME0[1-8]", name):
            return "liquid / static sample"
    if name.startswith(("SKY", "F_RSKY")) or name == "F_SKY1":
        return "sky / static artwork"
    if name.startswith(
        (
            "BFALL",
            "SFALL",
            "BLODRIP",
            "NUKAGE",
            "SLIME",
            "LAVA",
            "FWATER",
            "BLOOD",
            "FIRE",
        )
    ):
        return "liquid / static sample"
    if (
        name.startswith(("SKIN", "SP_", "SKSNAKE", "SKSPINE", "DBRAIN", "SLOPPY"))
        or "FLESH" in name
    ):
        return "organic"
    if name.startswith(("WOOD", "CRAT", "PAN")) or "WOOD" in name:
        return "wood"
    if name.startswith(("BRICK", "BIGBRIK")) or "BRIK" in name:
        return "brick / mortar"
    if name.startswith(("MARB", "GST", "BSTONE")) or "MARB" in name:
        return "carved stone"
    if name.startswith(("COMP", "TEK", "SPACE", "MODWALL", "LITE", "EXIT")):
        return "painted technology"
    if name.startswith(
        (
            "METAL",
            "SILVER",
            "SHAWN",
            "BRONZE",
            "MIDBAR",
            "MIDGRATE",
            "MIDSPACE",
            "PIPE",
            "SUPPORT",
            "DOOR",
            "BIGDOOR",
            "SPCDOOR",
            "ZDOOR",
            "BRWINDOW",
            "BLAKWAL",
        )
    ):
        return "metal"
    if name.startswith(
        ("STAR", "SLAD", "BRN", "ICK", "GRAY", "NUKE", "STEP", "REDWALL")
    ):
        return "painted panels"
    if name.startswith(
        ("ROCK", "TANROCK", "STONE", "STUCCO", "CEMENT", "ASH", "CRACK", "ZIM", "BROWN")
    ):
        return "stone / concrete"
    if name.startswith(("CEIL5", "CEIL3", "FLAT14", "FLAT23", "FLOOR4_", "FLOOR5_")):
        return "painted panels"
    if name.startswith(
        ("FLOOR6_", "FLOOR7_", "RROCK", "MFLR", "DEM1", "SFLR", "FLAT5_")
    ):
        return "stone / concrete"
    if name.startswith("SW"):
        return "mixed switch panel"
    return "neutral dielectric"


def blur(values, radius):
    image = Image.fromarray(np.uint8(np.clip(values, 0, 1) * 255), "L")
    return (
        np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        / 255
    )


def maps_for(pixels, family):
    """Family-guided image interpretation; no physical displacement is generated."""
    h, w = pixels.shape[:2]
    scale = min(4, 512 / max(h, w))
    tw, th = max(16, round(w * scale)), max(16, round(h * scale))
    rgba = (
        np.asarray(
            Image.fromarray(pixels).resize((tw, th), Image.Resampling.BICUBIC),
            dtype=np.float32,
        )
        / 255
    )
    rgb = rgba[:, :, :3]
    lum = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    saturation = rgb.max(2) - rgb.min(2)
    smooth = blur(lum, max(0.7, scale * 0.45))
    broad = blur(lum, max(1.2, scale * 1.2))
    lower, upper = (
        np.percentile(smooth[rgba[:, :, 3] > 0.5], [15, 85])
        if np.any(rgba[:, :, 3] > 0.5)
        else (0, 1)
    )
    structure = np.clip((smooth - lower) / max(0.16, upper - lower), 0, 1)
    # Broad material structure controls relief; fine albedo pixels have only a
    # restrained contribution. Thus checker color and baked highlight intensity
    # are not blindly interpreted as deep geometry.
    fine = smooth - broad
    height = 0.55 * structure + 0.10 * fine
    rough = np.full((th, tw), 0.78, dtype=np.float32)
    metal = np.zeros((th, tw), dtype=np.float32)
    relief_pixels = 1.0
    interpretation = "Conservative image-guided microrelief; matte dielectric"
    if family == "brick / mortar":
        # Only dark features coherent at the source-pixel scale get recessed
        # joints; shallow bevels are obtained from the smoothed transition.
        height = blur(
            np.clip((smooth - lower) / max(0.12, upper - lower), 0, 1),
            max(0.65, scale * 0.28),
        )
        rough = 0.80 + 0.12 * (1 - structure)
        relief_pixels = 2.0
        interpretation = (
            "Dark coherent mortar/joints recessed; shallow softened brick relief"
        )
    elif family in ("carved stone", "stone / concrete", "lava crust"):
        height = 0.6 * structure + 0.2 * fine
        rough = 0.68 + 0.23 * (1 - smooth)
        relief_pixels = 1.6 if family == "carved stone" else 1.2
        interpretation = "Shallow mineral relief and dark recesses; rough nonmetal"
    elif family == "wood":
        height = 0.45 * structure + 0.12 * fine
        rough = 0.58 + 0.24 * (1 - smooth)
        relief_pixels = 1.2
        interpretation = (
            "Existing grain/plank contrast interpreted as shallow wood relief; nonmetal"
        )
    elif family == "metal":
        height = 0.45 * structure + 0.05 * fine
        metal = np.clip(0.65 + 0.3 * (1 - saturation), 0, 0.95)
        rough = 0.24 + 0.29 * (1 - smooth) + 0.12 * saturation
        relief_pixels = 1.3
        interpretation = "Metal body with shallow existing seams/fasteners; brightness-varying polish"
    elif family in ("painted technology", "painted panels", "mixed switch panel"):
        height = 0.4 * structure + 0.06 * fine
        # Saturated paint and screens are dielectric; neutral brighter edges
        # can read as exposed metal. This is an interpretation, not segmentation
        # of the original artist's intended substrate.
        metal = np.clip((0.25 - saturation) * 4, 0, 1) * np.clip(
            (smooth - 0.38) * 1.5, 0, 0.55
        )
        rough = 0.42 + 0.32 * (1 - smooth) + 0.12 * saturation
        relief_pixels = 1.15
        interpretation = "Paint/screen dielectric with conservative exposed-metal mask; existing panel relief"
    elif family == "organic":
        height = 0.55 * structure + 0.05 * fine
        rough = 0.40 + 0.25 * (1 - smooth)
        relief_pixels = 1.5
        interpretation = "Soft organic relief; moderately wet nonmetal"
    elif family in ("fabric", "vegetation"):
        height = 0.25 * structure + 0.12 * fine
        rough = np.full((th, tw), 0.92, dtype=np.float32)
        relief_pixels = 0.65
        interpretation = "Shallow soft fibre/turf relief; very rough nonmetal"
    elif family == "liquid / static sample":
        height = blur(lum, max(2, scale * 2)) * 0.18
        rough = np.full((th, tw), 0.20, dtype=np.float32)
        relief_pixels = 0.55
        interpretation = "Static wet dielectric sample; no animation, transparency or fluid simulation claim"
    elif family == "sky / static artwork":
        height = np.zeros((th, tw), dtype=np.float32)
        rough = np.ones((th, tw), dtype=np.float32)
        relief_pixels = 0
        interpretation = "Flat-normal nonmetal fallback; displayed as static artwork, not a physical sky"
    dx = (
        (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1))
        * 0.5
        * relief_pixels
        * scale
    )
    dy = (
        (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0))
        * 0.5
        * relief_pixels
        * scale
    )
    normal = np.stack((-dx, dy, np.ones_like(dx)), axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    normal = np.uint8(np.clip(normal * 127 + 128, 0, 255))
    visible = rgba[:, :, 3] > 0.5
    normal[~visible] = (128, 128, 255)
    ao = np.clip(0.84 + 0.16 * structure, 0.84, 1)
    if family in ("sky / static artwork", "liquid / static sample"):
        ao = np.ones((th, tw))
    spec = np.clip(0.12 + 0.5 * metal + 0.12 * (1 - rough), 0.08, 0.8)
    result = {"normal": Image.fromarray(normal, "RGB")}
    for key, array in (
        ("metallic", metal),
        ("roughness", rough),
        ("ao", ao),
        ("specular", spec),
    ):
        result[key] = Image.fromarray(np.uint8(np.clip(array, 0, 1) * 255), "L")
    return (
        result,
        interpretation,
        {
            "normal_extent": [tw, th],
            "relief_source_pixels": relief_pixels,
            "mean_metallic": round(float(metal.mean()), 3),
            "mean_roughness": round(float(rough.mean()), 3),
        },
    )
