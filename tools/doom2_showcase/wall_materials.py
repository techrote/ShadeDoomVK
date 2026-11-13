"""Derive switch/door material context from original composite patches."""

import struct

import numpy as np
from PIL import Image


def definitions(lookup):
    names = lookup["PNAMES"]
    count = struct.unpack_from("<i", names)[0]
    pnames = [
        names[4 + i * 8 : 12 + i * 8].rstrip(b"\0").decode().upper()
        for i in range(count)
    ]
    out = {}
    for key in ("TEXTURE1", "TEXTURE2"):
        if key not in lookup:
            continue
        data = lookup[key]
        count = struct.unpack_from("<i", data)[0]
        for i in range(count):
            at = struct.unpack_from("<i", data, 4 + i * 4)[0]
            name, flags, w, h, unused, n = struct.unpack_from("<8sIhhIh", data, at)
            parts = []
            for j in range(n):
                x, y, pidx, _, _ = struct.unpack_from("<hhhhh", data, at + 22 + j * 10)
                parts.append((x, y, pnames[pidx]))
            out[name.rstrip(b"\0").decode().upper()] = (w, h, parts)
    return out


def switch_mask(row, defs, decoder):
    if row["kind"] != "wall" or not row["name"].startswith(("SW1", "SW2")):
        return None
    w, h, parts = defs[row["name"]]
    mask = np.zeros((h, w), dtype=np.float32)
    seen = False
    for x, y, pname in parts:
        patch = decoder.patch(pname)
        ph, pw = patch.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + pw), min(h, y + ph)
        if x1 <= x0 or y1 <= y0:
            continue
        visible = patch[y0 - y : y1 - y, x0 - x : x1 - x, 3] > 0
        is_device = pname.startswith("SW") or pname in (
            "WALL42_1",
            "WALL42_5",
            "WALL42_6",
        )
        mask[y0:y1, x0:x1][visible] = float(is_device)
        seen |= is_device
    return mask if seen else None


def context(row, rows, defs, decoder):
    ctx = {}
    mask = switch_mask(row, defs, decoder)
    if mask is not None:
        ctx["switch_mask"] = mask
    name = row["name"]
    if row["kind"] == "wall" and name.startswith(("SW1", "SW2")):
        if any(
            pname in ("SW2_7", "SW2_8", "WALL42_1", "WALL42_5", "WALL42_6")
            for x, y, pname in defs[name][2]
        ):
            ctx["switch_alloy"] = "bronze"
    if name.startswith(("SW1", "SW2")):
        other = "SW" + ("2" if name[2] == "1" else "1") + name[3:]
        pair = rows.get(("wall", other))
        if pair is not None and pair["pixels"].shape == row["pixels"].shape:
            ctx["paired_pixels"] = pair["pixels"]
    return ctx


def validate_maps(maps, pixels):
    size = maps["normal"].size
    assert all(im.size == size for im in maps.values())
    n = np.asarray(maps["normal"].convert("RGB"), dtype=np.float32) / 127.5 - 1
    assert (
        np.isfinite(n).all() and np.max(np.abs(np.linalg.norm(n, axis=2) - 1)) < 0.025
    )
    assert np.asarray(maps["roughness"]).min() > 0
    alpha = np.asarray(Image.fromarray(pixels).resize(size, Image.Resampling.NEAREST))[
        :, :, 3
    ]
    # Production alpha stays in original artwork; auxiliary maps must stay sane.
    assert np.asarray(maps["metallic"]).shape == alpha.shape
