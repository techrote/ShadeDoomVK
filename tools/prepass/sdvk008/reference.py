#!/usr/bin/env python3
"""Standalone, CPU-only SDVK-008 shallow POM oracle (prepass, NOT renderer code).

UVs are in the input sprite/height texture coordinate domain; +U is the
accepted basis T direction and +V is B. View points from fragment TO camera.
Height=1 intersects the top of the relief slab; height=0 its bottom.
No production sprite orientation, Vulkan or material descriptor APIs are used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Optional

POLICIES = {"off": (0, 0), "low": (8, 1), "medium": (12, 2), "high": (20, 2)}
MAX_HEIGHT_SCALE = 0.02             # UV units, not Doom world units
MAX_UV_EXCURSION = 0.05            # Euclidean distance in UV space
MIN_VIEW_Z = 0.20                  # backfaces and <= this are disabled
FULL_VIEW_Z = 0.32                 # smooth fade between min and full
MIN_PROJECTED_PIXELS = 16.0       # optional projected-size fade
FULL_PROJECTED_PIXELS = 32.0
MAX_HEIGHT_LOD = 4.0
MAX_HEIGHT_SAMPLES = 23             # 1 initial + 20 march + 2 bisections


@dataclass(frozen=True)
class Result:
    uv: tuple[float, float]
    height_samples: int = 0
    alpha_samples: int = 0
    actual_steps: int = 0
    requested_steps: int = 0
    fallback_reason: str = "NONE"
    refined: bool = False
    max_excursion: float = 0.0
    effective_scale: float = 0.0
    scale_capped: bool = False
    derived_lod: float = 0.0
    intersection_depth: float = 0.0
    numerical_anomaly: bool = False
    relief_applied: bool = False

    def as_dict(self):
        data = asdict(self)
        data["uv"] = list(self.uv)
        return data


def _finite(*numbers):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers)


def _smooth(a, b, value):
    t = max(0.0, min(1.0, (value - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _valid_grid(grid):
    if not isinstance(grid, (list, tuple)) or not grid:
        return False
    width = len(grid[0]) if isinstance(grid[0], (list, tuple)) else 0
    return bool(width and all(isinstance(row, (list, tuple)) and len(row) == width and
                              all(_finite(value) and 0 <= value <= 1 for value in row)
                              for row in grid))


def _mips(grid):
    levels = [grid]
    while len(levels[-1]) > 1 or len(levels[-1][0]) > 1:
        previous = levels[-1]
        height, width = len(previous), len(previous[0])
        next_level = []
        for y in range((height + 1) // 2):
            row = []
            for x in range((width + 1) // 2):
                # Edge replication is explicit for odd sizes.
                row.append(sum(previous[min(height - 1, 2*y+dy)][min(width - 1, 2*x+dx)]
                               for dy in (0, 1) for dx in (0, 1)) / 4.0)
            next_level.append(row)
        levels.append(next_level)
    return levels


def _bilinear_repeat(grid, u, v):
    height, width = len(grid), len(grid[0])
    x, y = u * width - 0.5, v * height - 0.5
    ix, iy = math.floor(x), math.floor(y)
    tx, ty = x - ix, y - iy
    p00 = grid[iy % height][ix % width]
    p10 = grid[iy % height][(ix + 1) % width]
    p01 = grid[(iy + 1) % height][ix % width]
    p11 = grid[(iy + 1) % height][(ix + 1) % width]
    return (p00 * (1-tx) + p10 * tx) * (1-ty) + (p01 * (1-tx) + p11 * tx) * ty


def _height(levels, u, v, lod):
    lo = min(int(math.floor(lod)), len(levels)-1)
    hi = min(lo+1, len(levels)-1)
    blend = lod - math.floor(lod) if lo != hi else 0.0
    return _bilinear_repeat(levels[lo], u, v) * (1-blend) + _bilinear_repeat(levels[hi], u, v)*blend


def _alpha_nearest(grid, u, v):
    # Pinned nearest-mask oracle, not a replacement for renderer getTexel alpha.
    height, width = len(grid), len(grid[0])
    return grid[min(height-1, max(0, int(v*height)))][min(width-1, max(0, int(u*width)))]


def resolve(height: Optional[list], uv: tuple[float, float], view: tuple[float, float, float],
            scale: float, policy: str = "medium", *, rect=(0., 0., 1., 1.),
            alpha=None, alpha_threshold=0.5, lod=0., basis_supported=True,
            projected_pixels=None) -> Result:
    """Return bounded ray/UV result and explicit diagnostics. No geometry change.

    `view` is normalized internally, but is supplied in *semantic* tangent
    coordinates by the caller. The API deliberately knows no #7 struct layout.
    `lod` stands for caller-computed derivative LOD and is clamped to [0,4].
    `projected_pixels=None` bypasses optional distance/size fade for the oracle.
    """
    if not isinstance(uv, (tuple, list)) or len(uv) != 2 or not _finite(*uv):
        return Result((0.5, 0.5), fallback_reason="INVALID_UV", numerical_anomaly=True)
    original = (float(uv[0]), float(uv[1]))
    def stop(reason, *, anomaly=False, **kwargs):
        return Result(original, fallback_reason=reason, numerical_anomaly=anomaly, **kwargs)

    if policy not in POLICIES:
        return stop("INVALID_POLICY", anomaly=True)
    layers, refinements = POLICIES[policy]
    if policy == "off":
        return stop("DISABLED")
    if height is None:
        return stop("NO_HEIGHT")
    if not _valid_grid(height):
        return stop("INVALID_HEIGHT", anomaly=True)
    if not basis_supported:
        return stop("UNSUPPORTED_BASIS")
    if not _finite(scale):
        return stop("INVALID_SCALE", anomaly=True)
    if scale < 0:
        return stop("NEGATIVE_SCALE")
    if scale == 0:
        return stop("ZERO_SCALE")
    if scale > MAX_HEIGHT_SCALE:
        return stop("SCALE_LIMIT")
    if not isinstance(rect, (tuple, list)) or len(rect) != 4 or not _finite(*rect):
        return stop("INVALID_RECT", anomaly=True)
    u0, v0, u1, v1 = rect
    if not (0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1):
        return stop("INVALID_RECT", anomaly=True)
    def in_rect(point):
        return u0 <= point[0] <= u1 and v0 <= point[1] <= v1
    if not in_rect(original):
        return stop("UV_OUTSIDE_RECT")
    if not isinstance(view, (tuple, list)) or len(view) != 3 or not _finite(*view):
        return stop("INVALID_VIEW", anomaly=True)
    vx, vy, vz = (float(v) for v in view)
    length = math.hypot(vx, vy, vz)
    if length < 1e-8:
        return stop("ZERO_VIEW")
    vx, vy, vz = vx/length, vy/length, vz/length
    if vz <= MIN_VIEW_Z:
        return stop("GRAZING_OR_BACKFACE")
    if math.hypot(vx, vy) < 1e-8:
        return stop("FRONT_ON")
    if not _finite(lod) or lod < 0:
        return stop("INVALID_LOD", anomaly=True)
    derived_lod = min(float(lod), MAX_HEIGHT_LOD)
    if not _finite(alpha_threshold) or not 0 <= alpha_threshold <= 1:
        return stop("INVALID_ALPHA_THRESHOLD", anomaly=True)
    if alpha is not None and not _valid_grid(alpha):
        return stop("INVALID_ALPHA_MASK", anomaly=True)
    alpha_reads = 0
    if alpha is not None:
        alpha_reads = 1
        if _alpha_nearest(alpha, *original) <= alpha_threshold:
            return stop("BASE_TRANSPARENT", alpha_samples=alpha_reads)
    fade = _smooth(MIN_VIEW_Z, FULL_VIEW_Z, vz)
    if projected_pixels is not None:
        if not _finite(projected_pixels) or projected_pixels < 0:
            return stop("INVALID_PROJECTED_SIZE", anomaly=True, alpha_samples=alpha_reads)
        if projected_pixels <= MIN_PROJECTED_PIXELS:
            return stop("TOO_SMALL", alpha_samples=alpha_reads)
        fade *= _smooth(MIN_PROJECTED_PIXELS, FULL_PROJECTED_PIXELS, projected_pixels)
    effective_scale = scale * fade
    ray_u, ray_v = effective_scale * vx / vz, effective_scale * vy / vz
    ray_len = math.hypot(ray_u, ray_v)
    cap = ray_len > MAX_UV_EXCURSION
    if cap:
        ratio = MAX_UV_EXCURSION / ray_len
        ray_u *= ratio
        ray_v *= ratio
        effective_scale *= ratio
        ray_len = MAX_UV_EXCURSION
    if ray_len < 1e-12:
        return stop("ZERO_EXCURSION", alpha_samples=alpha_reads)

    levels = _mips(height)
    sample_count = 0
    steps_taken = 0
    max_excursion = 0.0

    def inspect(depth):
        nonlocal sample_count, max_excursion
        point = (original[0]-ray_u*depth, original[1]-ray_v*depth)
        max_excursion = max(max_excursion, math.hypot(point[0]-original[0], point[1]-original[1]))
        if not in_rect(point):
            return None
        sample_count += 1
        h = _height(levels, *point, derived_lod)
        if not _finite(h) or h < 0 or h > 1:
            return None
        return depth + h - 1.0  # crossing at 0, with h=1 top, h=0 bottom

    f0 = inspect(0.0)
    if f0 is None:
        return stop("INVALID_SAMPLED_HEIGHT", anomaly=True, height_samples=sample_count,
                    alpha_samples=alpha_reads, max_excursion=max_excursion)
    if f0 >= 0:
        return stop("TOP_PLANE", height_samples=sample_count, alpha_samples=alpha_reads,
                    requested_steps=layers, derived_lod=derived_lod,
                    effective_scale=effective_scale, scale_capped=cap)

    low_d, low_f = 0.0, f0
    found = False
    high_d, high_f = 1.0, 0.0
    for i in range(1, layers+1):
        d = i / layers
        f = inspect(d)
        steps_taken += 1
        if f is None:
            return stop("FRAME_ESCAPE", height_samples=sample_count, alpha_samples=alpha_reads,
                        actual_steps=steps_taken, requested_steps=layers,
                        max_excursion=max_excursion, effective_scale=effective_scale,
                        derived_lod=derived_lod, scale_capped=cap)
        if f >= 0:
            high_d, high_f = d, f
            found = True
            break
        low_d, low_f = d, f
    if not found:
        return stop("NO_INTERSECTION", anomaly=True, height_samples=sample_count,
                    alpha_samples=alpha_reads, actual_steps=steps_taken,
                    requested_steps=layers, max_excursion=max_excursion)
    for _ in range(refinements):
        mid_d = 0.5*(low_d + high_d)
        f = inspect(mid_d)
        if f is None:
            return stop("REFINEMENT_INVALID", anomaly=True, height_samples=sample_count,
                        alpha_samples=alpha_reads, actual_steps=steps_taken,
                        requested_steps=layers, max_excursion=max_excursion)
        if f >= 0:
            high_d, high_f = mid_d, f
        else:
            low_d, low_f = mid_d, f
    delta = high_f - low_f
    t = -low_f/delta if delta > 1e-12 else 0.5
    t = max(0.0, min(1.0, t))
    intersection = low_d + (high_d-low_d)*t
    resolved = (original[0]-ray_u*intersection, original[1]-ray_v*intersection)
    if not _finite(*resolved) or not in_rect(resolved):
        return stop("INVALID_INTERSECTION", anomaly=True, height_samples=sample_count,
                    alpha_samples=alpha_reads, actual_steps=steps_taken,
                    requested_steps=layers, max_excursion=max_excursion)
    if alpha is not None:
        alpha_reads += 1
        if _alpha_nearest(alpha, *resolved) <= alpha_threshold:
            return stop("ALPHA_ESCAPE", height_samples=sample_count, alpha_samples=alpha_reads,
                        actual_steps=steps_taken, requested_steps=layers,
                        max_excursion=max_excursion, derived_lod=derived_lod,
                        effective_scale=effective_scale, scale_capped=cap)
    return Result(resolved, sample_count, alpha_reads, steps_taken, layers, "NONE",
                  refinements > 0, max_excursion, effective_scale, cap, derived_lod,
                  intersection, False, resolved != original)
