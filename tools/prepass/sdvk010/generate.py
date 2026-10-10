#!/usr/bin/env python3
"""SDVK-010 synthetic OFFLINE reference environments and PF-012 oracle.

Produces authored reference PNGs and deterministic host-state goldens ONLY.
It does not install a cubemap, bake a probe, run Vulkan or assert actor policy.
Python >=3.9; standard library only; no IWAD/external asset content.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

FACE_RGB = {
    "+X": (255, 35, 26),
    "-X": (0, 235, 235),
    "+Y": (42, 255, 22),
    "-Y": (235, 30, 235),
    "+Z": (30, 50, 255),
    "-Z": (255, 235, 28),
}
SIZE = 16
MIPS = 5
RADIUS = 512.0
SCHEMA = "sdvk010-synthetic-cube-assets/v1"


def canonical(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    if not 1 <= width <= 256 or not 1 <= height <= 256 or len(rgba) != 4 * width * height:
        raise ValueError("Incorrect authored PNG dimensions")
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    payload = b"".join(b"\0" + rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(payload, 9)) + chunk(b"IEND", b""))


def image(width: int, rgb_func) -> bytes:
    return bytes(channel for y in range(width) for x in range(width)
                 for channel in (*rgb_func(x, y, width), 255))


def axes_color(face: str, x: int, y: int, size: int) -> tuple[int, int, int]:
    """Per-face base + asymmetric U/V markers. **Not** a GPU face-frame claim."""
    r, g, b = FACE_RGB[face]
    if x <= 1 and y >= 3:       # left vertical (dark) margin
        return r // 4, g // 4, b // 4
    if y <= 1 and x >= 3:       # top horizontal (light) margin
        return (r + 255) // 2, (g + 255) // 2, (b + 255) // 2
    if x >= size - 3 and y >= size - 3:  # bottom-right corner glyph
        return 10, 10, 10
    if x >= 2 and y in (size//2, size//2 + 1):
        return 255 - r, 255 - g, 255 - b
    return r, g, b


def specular_rgb(face: str, x: int, y: int, size: int) -> tuple[int, int, int]:
    """One very bright off-centre lobe; other faces dark but deliberately distinct."""
    base = 6 + list(FACE_RGB).index(face) * 2
    centre_x, centre_y = int(size * 0.63), int(size * 0.31)
    dist2 = (x - centre_x)**2 + (y - centre_y)**2
    intensity = 235 if face == "+Z" and dist2 <= 4 else (110 if face == "+Z" and dist2 <= 12 else 0)
    return min(255, base + intensity), min(255, base + intensity // 3), min(255, base + intensity // 8)


def downsample(src: bytes, old: int) -> bytes:
    if old <= 1 or len(src) != old * old * 4 or old % 2:
        raise ValueError("Invalid deterministic 2x2 downsample")
    size = old // 2
    out = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            for c in range(4):
                values = [src[((2*y+dy)*old + 2*x+dx)*4+c] for dy in range(2) for dx in range(2)]
                out[(y*size+x)*4+c] = sum(values) // 4
    return bytes(out)


def finite_unit(vec: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    if len(vec) != 3 or not all(isinstance(a, (int,float)) and math.isfinite(a) for a in vec):
        raise ValueError("Invalid nonfinite or non-3D vector")
    length = math.sqrt(sum(a*a for a in vec))
    if length <= 1e-12:
        raise ValueError("Unnormalizable vector")
    return tuple(float(a)/length for a in vec)


def reflect_view(view_to_camera: list[float] | tuple[float, ...], normal: list[float] | tuple[float, ...]) -> list[float]:
    """Matching shader expression R=reflect(-V,N), in one consistent space."""
    v, n = finite_unit(view_to_camera), finite_unit(normal)
    dot = sum(a*b for a,b in zip(v,n))
    return list(finite_unit(tuple(2*dot*n[i]-v[i] for i in range(3))))


def face_major_axis(direction: list[float] | tuple[float, ...]) -> str:
    """Reference major-axis class only. GPU cube face-local UV convention is pending."""
    d = finite_unit(direction)
    axis = max(range(3), key=lambda i: abs(d[i]))   # stable X->Y->Z ties
    return ("X","Y","Z")[axis].join(("+" if d[axis]>=0 else "-", ""))


def prefilter_lod(roughness: float) -> float:
    if not isinstance(roughness, (float,int)) or not math.isfinite(roughness) or not 0 <= roughness <= 1:
        raise ValueError("Material roughness outside accepted [0,1]")
    return 4.0 * roughness


def world_texel_nearest_live(candidates: list[dict], position: list[float], radius: float=RADIUS) -> int:
    """PF-012 reference selector ONLY; not a new actor/sector selection policy."""
    if not math.isfinite(radius) or radius < 0 or len(position) != 3 or not all(math.isfinite(v) for v in position):
        raise ValueError("Invalid PF-012 selector input")
    nearest = 0
    best = radius * radius
    found = False
    for c in candidates:
        idx = c["runtime_irradiance"]
        if not isinstance(idx, int) or not 1 <= idx <= 65535:
            continue
        dist = sum((float(a)-float(b))**2 for a,b in zip(position,c["world_position"]))
        if math.isfinite(dist) and dist <= radius*radius and (not found or dist < best):
            best, nearest, found = dist, idx, True
    return nearest


def expected_goldens() -> dict:
    candidates = [
        {"authored_index":0,"runtime_irradiance":713,"world_position":[-128,0,64]},
        {"authored_index":1,"runtime_irradiance":1201,"world_position":[128,0,64]},
    ]
    positions = [[-128,0,64],[-1,0,64],[0,0,64],[1,0,64],[128,0,64],[641,0,64]]
    return {
        "schema":"sdvk010-offline-world-selector-goldens/v1",
        "status":"OFFLINE_PF012_ONLY_NOT_ACTOR_POLICY",
        "radius_inclusive":RADIUS,
        "candidate_order_is_tie_break":True,
        "candidates":candidates,
        "world_texels":[{"position":p,"expected_runtime_irradiance":world_texel_nearest_live(candidates,p)} for p in positions],
        "unavailable":[{"authored_index":0,"runtime_irradiance":0,"world_position":[0,0,0]},
                       {"authored_index":1,"runtime_irradiance":70000,"world_position":[1,0,0]}],
        "unavailable_result":world_texel_nearest_live([
            {"runtime_irradiance":0,"world_position":[0,0,0]},
            {"runtime_irradiance":70000,"world_position":[1,0,0]}],[0,0,0]),
        "reflections":[
            {"N":[0,1,0],"V":[0,1,0],"R":reflect_view([0,1,0],[0,1,0])},
            {"N":[0,0,1],"V":[0,0.6,0.8],"R":reflect_view([0,0.6,0.8],[0,0,1])},
            {"N":[1,0,0],"V":[1,0,0],"R":reflect_view([1,0,0],[1,0,0])},
        ],
        "roughness_lod":[{"roughness":r,"lod":prefilter_lod(r)} for r in (0,0.125,0.25,0.5,0.75,1.0)],
        "face_classification":[{"direction":d,"face":face_major_axis(d)}
            for d in ([1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1],[0.2,0.1,0.9])],
        "warning":"Face local-UV and runtime cube orientation are NOT proven; do not infer actor selection from world-texel goldens."
    }


def generate(out: Path) -> dict:
    if out.exists() and not out.is_dir():
        raise ValueError("Output must be a directory")
    out.mkdir(parents=True, exist_ok=True)
    assets = {}
    def write(path: str, data: bytes, width: int, meaning: str) -> None:
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        assets[path] = {"width":width,"height":width,"sha256":hashlib.sha256(data).hexdigest(),
                        "bytes":len(data),"meaning":meaning}
    for face in FACE_RGB:
        write("orientation_axes/"+face+".png", png_rgba(SIZE,SIZE,image(SIZE,lambda x,y,n:axes_color(face,x,y,n))),SIZE,
              "RGB8 reference face with non-symmetric U/V glyph, not a Vulkan image")
        write("uniform_neutral/"+face+".png",png_rgba(SIZE,SIZE,bytes((128,128,128,255))*SIZE*SIZE),SIZE,
              "constant channel-value probe")
        for group, rgb in (("probe_warm",(225,55,30)),("probe_cool",(20,150,235))):
            write(group+"/"+face+".png",png_rgba(SIZE,SIZE,bytes((*rgb,255))*SIZE*SIZE),SIZE,
                  "constant distinct per-probe color, all cube faces equal")
        rgba = image(SIZE,lambda x,y,n:specular_rgb(face,x,y,n))
        dimension = SIZE
        for level in range(MIPS):
            write("specular_mips/mip"+str(level)+"/"+face+".png",png_rgba(dimension,dimension,rgba),dimension,
                  "CPU box-filtered off-centre highlight; authored reference mip "+str(level))
            if level + 1 < MIPS:
                rgba = downsample(rgba,dimension)
                dimension //= 2
    golden = canonical(expected_goldens())
    (out/"offline_goldens.json").write_bytes(golden)
    report = {
        "schema":SCHEMA, "status":"GENERATED_REFERENCE_ONLY_NOT_RENDERED",
        "pixel_format":"PNG 8-bit straight RGBA; no embedded ICC/gamma metadata",
        "cube_face_order":list(FACE_RGB),
        "face_colors_rgb8":{k:list(v) for k,v in FACE_RGB.items()},
        "axes_convention":"Synthetic labels only. Runtime VkLightprober face camera / cube sample orientation must be calibrated.",
        "specular_mips":"mip0 16x16 to mip4 1x1; box-filtered per-face; test LOD selection but does not implement production convolution",
        "assets":assets,
        "offline_goldens_sha256":hashlib.sha256(golden).hexdigest(),
    }
    (out/"manifest.json").write_bytes(canonical(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True,type=Path,help="Destination for generated reference PNGs + golden JSON")
    args = parser.parse_args()
    report = generate(args.out)
    print(json.dumps({"status":report["status"],"count":len(report["assets"]),
        "manifest":str(args.out/"manifest.json")},sort_keys=True))


if __name__ == "__main__":
    main()
