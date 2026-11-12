"""Build local auxiliary maps from the owner's installed Doom II and DBP50 art."""

from collections import Counter
from io import BytesIO
import hashlib
import json
import re
import struct
from zipfile import ZIP_DEFLATED, ZipFile

from dbp50_effective import IWAD_SHA256, PWAD_SHA256
from material_generator import Image, ImageFilter, Wad, np

FAMILIES = {
    "human": "POSS SPOS CPOS SSWV PLAY KEEN",
    "flesh": "TROO SARG HEAD BOS2 BOSS PAIN VILE SKEL FATT",
    "cyborg": "CYBR SPID BSPI",
    "bone": "SKUL",
    "weapon": "PUNG PISG SHTG SHT2 CHGG MISG PLSG BFGG SAWG SHOT SGN2 MGUN LAUN PLAS BFUG CSAW",
    "armor": "ARM1 ARM2 BON2",
    "medical": "MEDI STIM PSTR SUIT",
    "ammo": "CLIP AMMO SHEL SBOX ROCK BROK CELL CELP BPAK",
    "key": "BKEY RKEY YKEY BSKU RSKU YSKU",
    "powerup": "BON1 SOUL MEGA PINS PINV PVIS PMAP",
}
PROFILES = {
    prefix: family
    for family, prefixes in FAMILIES.items()
    for prefix in prefixes.split()
}
CHANNELS = ("normal", "metallic", "roughness", "ao")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_wad(path, identity, expected_kind):
    data = path.read_bytes()
    if sha(data) != identity:
        raise ValueError(f"Unexpected WAD identity: {path}")
    magic, count, directory = struct.unpack_from("<4sII", data)
    if magic != expected_kind or directory + 16 * count > len(data):
        raise ValueError(f"Invalid WAD directory: {path}")
    sprites = {}
    palette = None
    active = False
    for index in range(count):
        offset, size, raw_name = struct.unpack_from(
            "<II8s", data, directory + 16 * index
        )
        name = raw_name.rstrip(b"\0").decode("ascii")
        if offset + size > len(data):
            raise ValueError(f"Invalid lump extent: {name}")
        if re.fullmatch(r"S(?:S|\d+)?_(START|END)", name):
            active = name.endswith("START")
        elif name == "PLAYPAL":
            palette = data[offset : offset + 768]
        elif active and size:
            sprites[name] = data[offset : offset + size]
    return sprites, palette


class SpriteDecoder(Wad):
    def __init__(self, sprites, palette):
        self.sprites = sprites
        self.palette = np.frombuffer(palette, dtype=np.uint8).reshape(256, 3)
        self.patch_cache = {}

    def lump(self, name):
        return self.sprites[name]


def blur(field, radius):
    pixels = Image.fromarray(np.uint8(np.rint(np.clip(field, 0, 1) * 255)))
    return (
        np.asarray(pixels.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        / 255
    )


def byte(field):
    return np.uint8(np.rint(np.clip(field, 0, 1) * 255))


def maps_for(pixels, family, name):
    # Fill the relief gradients across the silhouette using coverage-normalized
    # filtering. The original sprite supplies transparency, dimensions and offsets.
    rgb = pixels[:, :, :3].astype(np.float32) / 255
    coverage = pixels[:, :, 3].astype(np.float32) / 255
    r, g, b = rgb.transpose(2, 0, 1)
    luma = rgb @ np.array([0.30, 0.59, 0.11], dtype=np.float32)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    gray = (saturation < 0.14) & (luma > 0.18)
    warm = (r - b > 0.14) & (r - g > 0.045)
    red = (r - g > 0.25) & (r - b > 0.20) & (g < 0.31)
    gold = (r > 0.43) & (g > 0.28) & (g - b > 0.19)
    steel = gray & ~red
    dark = luma < 0.13

    m = np.full_like(luma, 0.035)
    rough = np.full_like(luma, 0.72)
    if family == "weapon":
        rough[:] = 0.62
        if name.startswith("PUNG"):
            rough[:] = 0.72
        else:
            m[steel] = 0.68
            rough[steel] = 0.44
            m[gold & ~warm] = 0.55
            rough[gold & ~warm] = 0.45
            rough[warm | dark] = 0.76
    elif family in ("human", "cyborg"):
        m[steel] = 0.47 if family == "human" else 0.79
        rough[steel] = 0.43 if family == "human" else 0.33
        rough[warm] = 0.65
    elif family == "flesh":
        rough[warm] = 0.56
        rough[red] = 0.43
        if name.startswith(("FATT", "SKEL")):
            m[steel & ~warm] = 0.52 if name.startswith("FATT") else 0.30
            rough[steel & ~warm] = 0.43
    elif family == "bone":
        rough[:] = 0.57
        rough[red | gold] = 0.86
    elif family == "armor":
        rough[:] = 0.42
        m[steel] = 0.75
        rough[steel] = 0.31
        rough[dark] = 0.74
    elif family == "ammo":
        m[steel | gold] = 0.69
        rough[steel | gold] = 0.36
        rough[dark] = 0.7
    elif family == "key":
        m[steel] = 0.65
        rough[:] = 0.43
        if "SKU" in name:
            m[:] = 0.04
            rough[:] = 0.59
    elif family == "powerup":
        rough[:] = 0.48
        m[steel] = 0.30
    else:
        m[steel] = 0.18
        rough[steel] = 0.55

    smooth_coverage = blur(coverage, 1.12)
    shape = blur(coverage, 2.65)
    diffuse = blur(luma * coverage, 1.12) / np.maximum(smooth_coverage, 0.08)
    fine = blur(luma * coverage, 0.70) / np.maximum(blur(coverage, 0.70), 0.08)
    # Smooth volume with restrained pixel-level detail. Keep dark seams,
    # painted trim and highlights from all becoming equally deep grooves.
    detail = np.clip(fine - diffuse, -0.18, 0.18)
    relief = 2.1 * diffuse + 1.1 * detail + 1.5 * shape
    padded = np.pad(relief, 1, mode="edge")
    gy, gx = np.gradient(padded)
    nx, ny = -gx[1:-1, 1:-1], -gy[1:-1, 1:-1]
    normal = np.stack((nx, ny, np.ones_like(nx)), axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    normal = byte(normal * 0.5 + 0.5)
    ao = 1 - np.clip(diffuse - fine, 0, 0.22) * 0.85
    return {
        "normal": normal,
        "metallic": byte(m),
        "roughness": byte(rough),
        "ao": byte(ao),
    }


def png(array):
    out = BytesIO()
    Image.fromarray(array).save(out, format="PNG", compress_level=6)
    return out.getvalue()


def build(out, label, sprites, palette, overridden):
    selected = sorted(name for name in sprites if name[:4] in PROFILES)
    decoder = SpriteDecoder(sprites, palette)
    counts = Counter()
    definitions = []
    records = []
    package = out / f"{label}-SpritePBR.pk3"
    pending = package.with_suffix(".tmp")
    with ZipFile(pending, "w", ZIP_DEFLATED) as archive:
        for index, name in enumerate(selected):
            if not re.fullmatch(
                r"[A-Z0-9]{4}[A-Z\[\]\\][0-9](?:[A-Z\[\]\\][0-9])?", name
            ):
                raise ValueError(f"Unexpected sprite lump name: {name}")
            family = PROFILES[name[:4]]
            pixels = decoder.patch(name)
            if not pixels[:, :, 3].any():
                raise ValueError(f"Empty sprite: {name}")
            paths = {
                channel: f"sdvksprpbr/{index:04}/{channel}.png" for channel in CHANNELS
            }
            for channel, array in maps_for(pixels, family, name).items():
                archive.writestr(paths[channel], png(array))
            layers = " ".join(f'{c} "{paths[c]}" {{ filter linear }}' for c in CHANNELS)
            definitions.append(f'material sprite "{name}" {{ {layers} }}')
            records.append(
                {
                    "name": name,
                    "family": family,
                    "size": list(pixels.shape[1::-1]),
                    "source": "DBP50" if name in overridden else "DoomII",
                    "sprite_sha256": sha(sprites[name]),
                }
            )
            counts[family] += 1
        archive.writestr("GLDEFS", "\n".join(definitions) + "\n")
    pending.replace(package)
    manifest = {
        "package_sha256": sha(package.read_bytes()),
        "palette_sha256": sha(palette),
        "iwad_sha256": IWAD_SHA256,
        "pwad_sha256": PWAD_SHA256 if label == "DBP50" else None,
        "counts": dict(counts),
        "bindings": records,
    }
    (out / f"{label}-sprite-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        label, len(selected), "frames", dict(counts), package.stat().st_size, flush=True
    )
    return manifest
