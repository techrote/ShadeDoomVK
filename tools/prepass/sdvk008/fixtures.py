#!/usr/bin/env python3
"""Deterministic SDVK-008 candidate scalar/alpha/normal/PBR test textures.

All authored bytes are stdlib-generated. P2/P3 ASCII PNM is lossless and
trivially inspectable; later corpus integration may package these into a PK3.
This generator never modifies production corpus or renderer files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

NAMES = ("ramp", "mound", "asymmetric_wedge", "stepped", "checker",
         "thin_feature", "constant_0", "constant_05", "constant_1")


def _quant(v):
    return max(0, min(255, int(v*255+0.5))) / 255.0


def height_grid(name, size=32):
    if name not in NAMES or size < 2 or size > 512:
        raise ValueError("unsupported fixture or dimension")
    rows = []
    for j in range(size):
        row = []
        for i in range(size):
            x, y = (i+0.5)/size, (j+0.5)/size
            if name == "ramp": value = .10 + .80*x
            elif name == "mound": value = .05 + .93*math.exp(-(((x-.48)**2+(y-.52)**2)/.035))
            elif name == "asymmetric_wedge": value = max(.04, min(.98, .13 + .85*x - .36*y))
            elif name == "stepped": value = .10 + .20*min(4, int(x*5))
            elif name == "checker": value = 1.0 if (int(x*8)+int(y*8))%2 else 0.0
            elif name == "thin_feature": value = 1.0 if i == size//2 and size//4 <= j < 3*size//4 else .03
            elif name == "constant_0": value = 0.0
            elif name == "constant_05": value = 0.5
            else: value = 1.0
            row.append(_quant(value))
        rows.append(row)
    return rows


def alpha_grid(size=32):
    # Opaque outer shape, a punched 4x4 hole, a thin 2-pixel arm and empty corners.
    rows = []
    for j in range(size):
        row = []
        for i in range(size):
            inside = 2 <= i < size-2 and 2 <= j < size-2
            hole = size//2-2 <= i < size//2+2 and size//2-2 <= j < size//2+2
            arm = size//4 <= i < 3*size//4 and j in (size//4, size//4+1)
            row.append(1.0 if (inside and not hole) or arm else 0.0)
        rows.append(row)
    return rows


def _pnm(grid, channels):
    height, width = len(grid), len(grid[0])
    header = f"P{3 if channels == 3 else 2}\n{width} {height}\n255\n"
    body = []
    for row in grid:
        body.append(" ".join(" ".join(str(int(255*v+0.5)) for v in pixel)
                             if channels == 3 else str(int(255*pixel+0.5))
                             for pixel in row))
    return (header + "\n".join(body) + "\n").encode("ascii")


def _color_asset(size=32):
    albedo, normals = [], []
    nx, ny = .33, -.42
    nz = math.sqrt(1 - nx*nx - ny*ny)
    for j in range(size):
        aa, nn = [], []
        for i in range(size):
            x, y = i/(size-1), j/(size-1)
            aa.append((_quant(.15+.8*x), _quant(.1+.7*y), _quant(.65-.4*x*y)))
            nn.append((_quant(.5+.5*nx), _quant(.5+.5*ny), _quant(.5+.5*nz)))
        albedo.append(aa)
        normals.append(nn)
    return albedo, normals


def generate(out: Path, size=32):
    if size < 4 or size > 512:
        raise ValueError("invalid fixture size")
    out.mkdir(parents=True, exist_ok=False)  # fail closed; no stale overwrites
    asset_hashes = {}
    def write(filename, data):
        (out/filename).write_bytes(data)
        asset_hashes[filename] = hashlib.sha256(data).hexdigest()
    for name in NAMES:
        write(f"height_{name}.pgm", _pnm(height_grid(name, size), 1))
    a, n = _color_asset(size)
    write("albedo_directional.ppm", _pnm(a, 3))
    write("normal_directional.ppm", _pnm(n, 3))
    write("alpha_holes.pgm", _pnm(alpha_grid(size), 1))
    for key, scalar in (("metallic",.15),("roughness",.42),("ao",.87)):
        write(f"pbr_{key}.pgm", _pnm([[_quant(scalar)]*size for _ in range(size)],1))
    manifest = {"schema":"sdvk008-pnm-fixtures/v1", "size":size,
                "interpretation":"height red/gray linear UNORM; normal directional; albedo nearest; independent height linear+mipmap",
                "assets":dict(sorted(asset_hashes.items())),
                "non_image_negative_cases":["height missing", "malformed dimensions", "nonfinite scalar", "invalid scale"]}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--size",type=int,default=32)
    args=parser.parse_args()
    print(json.dumps(generate(args.out,args.size),sort_keys=True,indent=2))

if __name__ == "__main__": main()
