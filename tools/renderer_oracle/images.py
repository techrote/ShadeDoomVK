"""PNG/RGB comparison with an explicit, predeclared metric and tolerance.

Uses the accepted PF RGB decoder; compressed PNG bytes are not pixel identity.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct

try:
    from .common import ROOT, EvidenceError, integer, number, require, sha256
except ImportError:
    from common import ROOT, EvidenceError, integer, number, require, sha256

MAX_PIXELS = 1920 * 1080


def _decoder():
    path = ROOT / "tools/pf_oracle/run_freeze_dense_runtime.py"
    spec = importlib.util.spec_from_file_location("sdvk_pf_dense_decoder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decode_png


def decode(path):
    path = Path(path)
    require(path.is_file() and 33 <= path.stat().st_size <= 16 * 1024 * 1024, "PNG file size out of bounds")
    with path.open("rb") as stream:
        header = stream.read(33)
    require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", "Invalid PNG header")
    width, height = struct.unpack_from(">II", header, 16)
    require(0 < width <= 1920 and 0 < height <= 1080, "PNG extent out of bounds")
    try:
        rgb, metadata = _decoder()(path, extent=(width, height))
    except (ValueError, AssertionError, OSError) as error:
        raise EvidenceError(f"Unsupported or invalid PNG: {error}") from error
    require(isinstance(rgb, bytes) and len(rgb) == width * height * 3, "PF PNG decoder returned invalid RGB8")
    return (width, height), rgb


def validate_policy(policy):
    require(isinstance(policy, dict) and policy.get("metric") in ("exact-rgb8", "rgb8-absolute"),
            "Unknown image metric; a predeclared RGB8 policy is required")
    if policy["metric"] == "exact-rgb8":
        require(set(policy) == {"metric"}, "Exact comparison has no tolerance")
    else:
        require(set(policy) == {"metric", "max_channel_error", "mean_channel_error", "changed_pixel_fraction"},
                "Tolerant comparison needs all three explicit limits")
        integer(policy["max_channel_error"], "maximum channel error", maximum=255)
        number(policy["mean_channel_error"], "mean channel error")
        require(policy["mean_channel_error"] <= 255, "Mean channel tolerance exceeds RGB8 range")
        number(policy["changed_pixel_fraction"], "changed pixel fraction")
        require(policy["changed_pixel_fraction"] <= 1, "Changed pixel fraction exceeds one")


def compare_rgb(left, right, extent, policy):
    validate_policy(policy)
    require(len(left) == len(right) == extent[0] * extent[1] * 3 and len(left) > 0, "RGB extents differ")
    maximum = total = changed = 0
    for at in range(0, len(left), 3):
        errors = [abs(left[at+i] - right[at+i]) for i in range(3)]
        maximum = max(maximum, *errors)
        total += sum(errors)
        changed += any(errors)
    mean = total / len(left)
    fraction = changed / (extent[0] * extent[1])
    passed = maximum == 0 if policy["metric"] == "exact-rgb8" else (
        maximum <= policy["max_channel_error"] and mean <= policy["mean_channel_error"]
        and fraction <= policy["changed_pixel_fraction"])
    return {"passed": passed, "extent": list(extent), "policy": policy,
            "max_channel_error": maximum, "mean_channel_error": mean,
            "changed_pixels": changed, "changed_pixel_fraction": fraction,
            "left_rgb_sha256": sha256(left), "right_rgb_sha256": sha256(right)}


def compare(left, right, policy):
    left_extent, left_rgb = decode(left)
    right_extent, right_rgb = decode(right)
    require(left_extent == right_extent, "Image dimensions differ")
    return compare_rgb(left_rgb, right_rgb, left_extent, policy)
