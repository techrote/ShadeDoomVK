"""Source-projected, bounded stripe-edge witness; no renderer is launched.

This is deliberately restricted to the unchanged single-card fixture. It is
not pixel correspondence, general UV correctness, or measured fragment work.
"""
from __future__ import annotations

import math

REVISION = "sdvk008-source-projected-stripe-v1"
EXTENT = (640, 480)
MINIMUM_SHIFT = .05


def project(u, v, *, relieved=False):
    """Texel boundaries -> screen boundaries for the source-authored card.

    U=(64-Y)/128, V=(128-Z)/128; arguments use texels, not normalized UV.
    For height208, the GLSL secant interpolation gives depth=47/255 exactly
    in real arithmetic, independently of the fixed low/medium/high bracket.
    Solving resolved=original-depth*ray gives the forward affine UV map below.
    """
    if relieved:
        k = (47 / 255) * .012 / 160
        u, v = (u + 128*144*k)/(1+128*k), (v + 128*32*k)/(1+128*k)
    y, z = 64-u, 128-v
    c, s = math.cos(math.radians(27)), math.sin(math.radians(27))
    d = 160*c + (y+80)*s
    return (320 + 320*(160*s-(y+80)*c)/d, 240 - 384*(z-96)/d)


def _horizontal(v, column, relieved=False):
    # Intersect the projected constant-V boundary with this pixel-center X.
    x0, y0 = project(0, v, relieved=relieved)
    x1, y1 = project(128, v, relieved=relieved)
    return y0 + (column+.5-x0)*(y1-y0)/(x1-x0)


def sections():
    """Fixed UV domains selected from authored channel geometry, never images."""
    result = []
    for v in range(40, 61, 2):
        row = math.floor(project(29.5, v)[1])
        result.append(dict(axis="x", line=row,
            search=(project(18, v)[0], project(41, v)[0]),
            off=(project(26, v)[0], project(33, v)[0]),
            on=(project(26, v, relieved=True)[0], project(33, v, relieved=True)[0])))
    for u in range(40, 51):
        column = math.floor(project(u, 85.5)[0])
        result.append(dict(axis="y", line=column,
            search=(_horizontal(76, column), _horizontal(93, column)),
            off=(_horizontal(83, column), _horizontal(88, column)),
            on=(_horizontal(83, column, True), _horizontal(88, column, True))))
    return result


def _raster_interval(bounds):
    # A texel interval [a,b) contains pixel centers i+.5 in this integer range.
    return math.ceil(bounds[0]-.5), math.ceil(bounds[1]-.5)-1


def _red(raw, x, y, width):
    r, g, b = raw[3*(y*width+x):3*(y*width+x)+3]
    return r >= 80 and r >= 1.8*g and r >= 1.35*b


def _interval(raw, section, width, height):
    lo, hi = _raster_interval(section["search"])
    axis, line = section["axis"], section["line"]
    size, fixed_size = (width, height) if axis == "x" else (height, width)
    if not 0 <= lo <= hi < size or not 0 <= line < fixed_size:
        return None
    selected = [i for i in range(lo, hi+1)
                if _red(raw, i if axis == "x" else line, line if axis == "x" else i, width)]
    if not selected or selected != list(range(selected[0], selected[-1]+1)):
        return None
    # Touching the search boundary is not a proven complete stripe.
    if selected[0] == lo or selected[-1] == hi:
        return None
    return selected[0], selected[-1]


def _state_reason(off_state, on_state, off_native, on_native):
    from . import sdvk008_fixtures as fixtures
    from .run import _numeric_vector_matches
    for native in (off_native, on_native):
        if not isinstance(native, dict):
            return "Authenticated recipe is required"
        try:
            fixtures.validate_camera(native)
        except (ValueError, KeyError):
            return "Canonical authored camera contract differs"
        if (native.get("direction_witness_revision") != REVISION or native.get("relief_family") != "single"
            or native["camera"]["position"] != [-160, -80, 96]
            or native["authored_camera_angles"] != dict(yaw=27, pitch=0, roll=0)):
            return "Source-projected witness recipe/pose/family differs"
    for enabled, raw, native in ((False, off_state, off_native), (True, on_state, on_native)):
        if (native.get("extent") != [640, 480]
            or native.get("settings", {}).get("gl_sprite_relief_depth") != (.012 if enabled else 0)
            or native.get("settings", {}).get("gl_sprite_relief_quality") not in (1, 2, 3)):
            return "Authored extent/relief settings differ from source projection"
        if not isinstance(raw, dict):
            return "Authenticated emitted state is required"
        frames = [r["data"] for r in raw.get("records", []) if r["kind"] == "frame"]
        if not frames or any(not _numeric_vector_matches([f.get("camera", {}).get("fov")], [90])
            or (f.get("width"), f.get("height")) != EXTENT
            or not _numeric_vector_matches(f.get("camera", {}).get("position"), [-160, -80, 96])
            for f in frames):
            return "Actual FOV/extent/camera differs from source projection"
        for kind in ("sprite-basis", "sprite-relief"):
            rows = [r["data"] for r in raw.get("records", [])
                    if r["kind"] == kind and r["data"].get("material") == "SDVEA0"]
            if len(rows) != 1:
                return "Witness requires exactly one emitted test card per state"
            row = rows[0]
            context, surface = row.get("context", {}), row.get("surface", {})
            expected_surface = dict(presentation=3, uv=[1, 0, 0, 1], render_angles=[180, 0, 0],
                basis_valid=True, frame_mirrored=False, uv_mirror_x=False, uv_mirror_y=False,
                portal_mirrored=False, expected_tangent=[0, 0, -1], expected_normal=[-1, 0, 0],
                expected_handedness=1)
            if (context.get("type") != "main" or context.get("mirrored") is not False
                or not _numeric_vector_matches(context.get("position"), [-160, -80, 96])
                or not _numeric_vector_matches(context.get("angles"), [243, 0, 0])
                or any(surface.get(key) != value for key, value in expected_surface.items())
                or row.get("shader") != 0 or row.get("height_texture_index") != 4):
                return "Actual camera/final-quad/material state differs from source projection"
            if kind == "sprite-basis" and (row.get("tangent") != [0, 0, -1]
                or row.get("normal") != [-1, 0, 0] or row.get("handedness") != 1 or row.get("explicit") is not True):
                return "Actual basis differs from source projection"
            if kind == "sprite-relief" and (row.get("eligible_draw") is not enabled
                or row.get("uv_bounds") != ([1, 0, 0, 1] if enabled else [0, 0, 0, 0])
                or row.get("quality") != native.get("settings", {}).get("gl_sprite_relief_quality")
                or not isinstance(row.get("depth"), (int, float)) or not math.isfinite(row["depth"])
                or abs(row.get("depth", -1) - (.012 if enabled else 0)) > 1e-8):
                return "Actual relief controls differ from source projection"
    return None


def source_projected_marker_direction(off_rgb, on_rgb, width, height, *,
                                      off_state=None, on_state=None, off_native=None, on_native=None):
    """Qualify only the fixed interior stripe edges and their source-known signs.

    Exact predicted endpoint locations also constrain width, absence, deletion,
    and ambiguity. No observed image selects a region or a threshold. Source
    real-arithmetic predictions can fail to match a device's rasterization; an
    endpoint mismatch is retained as FAIL, never repaired by fitting the image.
    """
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("Invalid marker extent")
    if len(off_rgb) != width*height*3 or len(on_rgb) != width*height*3:
        raise ValueError("Marker witness needs matched RGB8 images")
    result = dict(status="UNAVAILABLE", oracle_revision=REVISION, expected_sign=[1, -1],
        minimum_edge_shift_px=MINIMUM_SHIFT, scope="source-projected-single-card-interior-stripe-edges",
        general_uv_correctness_qualified=False, pixel_correspondence_proven=False, sections=[])
    reason = "Source projection requires 640x480" if (width, height) != EXTENT else _state_reason(
        off_state, on_state, off_native, on_native)
    if reason:
        result["reason"] = reason
        return result
    shifts = {"x": [], "y": []}
    for section in sections():
        off, on = (_interval(raw, section, width, height) for raw in (off_rgb, on_rgb))
        expected_off, expected_on = (_raster_interval(section[key]) for key in ("off", "on"))
        row = {**section, "observed_off": off, "observed_on": on,
               "expected_off": expected_off, "expected_on": expected_on}
        result["sections"].append(row)
        if off is None or on is None:
            result["reason"] = "Missing, clipped, or ambiguous stripe interval"
            return result
        if off != expected_off or on != expected_on:
            result["status"] = "FAIL"
            result["reason"] = "Stripe endpoints/width differ from independently projected source boundaries"
            return result
        shifts[section["axis"]].extend(b-a for a, b in zip(off, on))
    if any(len({s["line"] for s in sections() if s["axis"] == axis}) < 8 for axis in shifts):
        result["reason"] = "Fewer than eight independent source-projected cross sections"
        return result
    dx, dy = (sum(shifts[axis])/len(shifts[axis]) for axis in ("x", "y"))
    result.update(delta_x_px=dx, delta_y_px=dy)
    if any(d < 0 for d in shifts["x"]) or any(d > 0 for d in shifts["y"]):
        result.update(status="FAIL", reason="Stripe edge moved against source-known direction")
    elif dx >= MINIMUM_SHIFT and dy <= -MINIMUM_SHIFT:
        result["status"] = "PASS"
    else:
        result["reason"] = "Source motion is below the unchanged raster witness threshold"
    return result
