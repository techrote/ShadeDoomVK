"""SDVK-010 matched PBR actor world-sun occlusion acceptance.

This checks emitted Vulkan draw data and separately samples two predeclared
symmetric actor image patches. Source/CPU geometry alone cannot award native
acceptance. The GPU fragment sun-ray result is not reported by a CPU proxy.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import math

try:
    from .common import integer, number, require
except ImportError:
    from common import integer, number, require


def check_contract(spec):
    require(isinstance(spec, dict) and set(spec) == {
        "sunlit_tid", "occluded_tid", "authored_probe_index", "material",
        "sunlit_xy", "occluded_xy", "expected_sun_direction", "image_rois",
    }, "SDVK-010 sun/world-occlusion contract fields differ")
    for key in ("sunlit_tid", "occluded_tid", "authored_probe_index"):
        integer(spec[key], key, minimum=0)
    require(spec["sunlit_tid"] != spec["occluded_tid"], "Sunlit/occluded actors must differ")
    require(spec["material"] == "SDVOA0", "Unrecognized matched PBR material")
    for key in ("sunlit_xy", "occluded_xy"):
        xy = spec[key]
        require(isinstance(xy, list) and len(xy) == 2 and all(
            type(n) in (int, float) and math.isfinite(n) for n in xy), "Actor XY is malformed")
    require(spec["sunlit_xy"] == [0, -88] and spec["occluded_xy"] == [0, 88],
            "Authored paired actor geometry changed")
    direction = spec["expected_sun_direction"]
    require(isinstance(direction, list) and len(direction) == 3 and all(
        type(x) in (int, float) and math.isfinite(x) for x in direction),
        "Missing finite native sunlight direction")
    require(all(abs(a - b) < 1e-8 for a, b in zip(direction,
        (-0.6123724357, 0.3535533906, 0.7071067812))),
        "Sun direction/occluder geometry no longer matches the frozen rays")
    require(set(spec["image_rois"]) == {"sunlit", "occluded"},
            "Both native actor image patches are required")
    for name, expected in (("sunlit", [467, 267, 8]), ("occluded", [173, 267, 8])):
        roi = spec["image_rois"][name]
        require(roi == expected, "Predeclared projected actor ROI changed: " + name)
    return True


def _finite_xyz(value):
    require(isinstance(value, list) and len(value) == 3 and all(
        type(x) in (int, float) and math.isfinite(x) for x in value),
        "Actual actor XYZ is incomplete or nonfinite")
    return value


def _probe_token(probe):
    resource = probe.get("resource", {})
    require(resource.get("available") is True and
            all(key in resource for key in ("index", "generation", "epoch", "span")),
            "Actor's actual irradiance/prefilter descriptor owner is absent")
    require(resource["span"] == 2,
            "Actor environment resource is not the PF-113 adjacent irradiance/prefilter pair")
    require(probe.get("runtime_irradiance_index") == resource["index"],
            "Actor runtime irradiance base does not match its published descriptor pair")
    return (resource["index"], resource["generation"], resource["epoch"], resource["span"])


def validate_emitted_frame(records, spec):
    """Fail closed on missing/altered emitted draw identity and direct sun route."""
    check_contract(spec)
    paired = {spec["sunlit_tid"]: [], spec["occluded_tid"]: []}
    material = spec["material"]
    owners = [r["data"] for r in records if r["kind"] == "resource"]
    require(owners, "No actual renderer owner/sun state")
    for owner in owners:
        sun = owner.get("sun", {})
        require(sun.get("intensity") == 1 and "direction" in sun,
                "Actual sun intensity/direction provenance absent")
        direction = _finite_xyz(sun["direction"])
        require(all(abs(a - b) < 0.001 for a, b in zip(
                direction, spec["expected_sun_direction"])),
                "Actual emitted sun direction differs from authored scene")
        require(owner.get("irradiance_maps", 0) >= 1 and owner.get("prefilter_maps", 0) >= 1,
                "No actual published irradiance/prefilter pair")
        require(owner.get("levelmesh", {}).get("available") is not False and
                owner.get("levelmesh", {}).get("epoch", 0) >= 1,
                "No actual world mesh to trace against")
    for record in records:
        if record["kind"] != "probe":
            continue
        row = record["data"]
        sun = row.get("actor_sunlight", {})
        tid = sun.get("actor_tid")
        if sun.get("available") is not True or tid not in paired:
            continue
        context = row.get("context", {})
        if context.get("root_type") != "main":
            continue
        require(sun.get("contract") == "sdvk-010-actor-sun-world-v1" and
                sun.get("scope") == "actual actor sprite packed sunlight proxy; fragment visibility is image evidence, not a CPU prediction",
                "Sunlight packed-draw provenance was invented or omitted")
        require(sun.get("packed_sun_count") == sun.get("traced_sun_count") == 1,
                "Actual actor draw did not upload one traced sun proxy")
        require(sun.get("light_range_uploaded") is True and
                type(sun.get("light_range_index")) is int and sun["light_range_index"] >= 0,
                "Traced sun proxy was not uploaded for the actual draw")
        selection = row.get("actor_selection", {})
        require(selection.get("available") is True and selection.get("selected") is True and
                selection.get("authored_index") == spec["authored_probe_index"] and
                selection.get("policy") == "spatial-nearest",
                "Actual actor draw selected wrong authored probe")
        require(selection.get("source_portal_group") == selection.get("render_portal_group") ==
                sun.get("source_portal_group") == sun.get("render_portal_group"),
                "Matched scene has ambiguous portal/group provenance")
        xyz = _finite_xyz(selection.get("actor_position"))
        expected_xy = spec["sunlit_xy"] if tid == spec["sunlit_tid"] else spec["occluded_xy"]
        require(all(abs(a - b) < 0.001 for a, b in zip(xyz[:2], expected_xy)),
                "Actual actor source pose differs from the authored sun-ray position")
        require(row.get("material") == material and row.get("authored_index") == spec["authored_probe_index"] and
                row.get("fallback") is False and row.get("runtime_irradiance_index", 0) > 0,
                "Matched actors do not share a live PBR probe/IBL material")
        require(type(row.get("probe_epoch")) is int and row["probe_epoch"] >= 1,
                "Stale or absent PBR probe epoch")
        _probe_token(row)
        paired[tid].append(row)
    require(all(paired.values()), "Both sunlit and world-occluded actual actor draws are required")
    require(set(r["data"].get("name") for r in records if r["kind"] == "material") >= {material},
            "Matched PBR material semantic draw was absent")
    shader_modes = {row["data"].get("mode") for row in records if row["kind"] == "shadow" and
                    row["data"].get("material") == material and
                    row["data"].get("context", {}).get("root_type") == "main"}
    require(shader_modes and shader_modes <= {"world-trace", "world-trace-precise"},
            "Actual PBR actor shader did not select the supported world-trace path")
    left, right = paired[spec["sunlit_tid"]][0], paired[spec["occluded_tid"]][0]
    require(_probe_token(left) == _probe_token(right) and
            left["probe_epoch"] == right["probe_epoch"] and
            left["runtime_irradiance_index"] == right["runtime_irradiance_index"] and
            left["published_irradiance"] == right["published_irradiance"] and
            left["published_prefilter"] == right["published_prefilter"],
            "Sunlit/occluded actors diverged in published probe resource identity/epoch")
    require(all(_probe_token(row) == _probe_token(left) and
                row["probe_epoch"] == left["probe_epoch"] and
                row["runtime_irradiance_index"] == left["runtime_irradiance_index"]
                for rows in paired.values() for row in rows),
            "Matched actor card draws used inconsistent environment resources")
    return {"status": "PASS", "actors": sorted(paired), "shader_modes": sorted(shader_modes),
            "shared_authored_ordinal": left["authored_index"],
            "shared_probe_epoch": left["probe_epoch"],
            "trace_scope": "submitted packed sun proxy and real shader world-trace policy; fragment visibility requires image"}


def validate_projected_image(extent, rgb, spec):
    """Native screen-space discriminant on predeclared symmetric actor centres.

    This is only a sign comparison, not an arbitrary absolute pixel threshold.
    The fixture's identical flat-albedo PBR cards and symmetric camera positions
    make the occluded half the required darker result of direct world sunlight.
    """
    check_contract(spec)
    require(tuple(extent) == (640, 480) and len(rgb) == 640 * 480 * 3,
            "Native sun-occlusion RGB extent/bytes differ")
    values = {}
    for label, (cx, cy, half) in spec["image_rois"].items():
        total = 0
        for y in range(cy - half, cy + half + 1):
            for x in range(cx - half, cx + half + 1):
                at = (y * extent[0] + x) * 3
                total += rgb[at] + rgb[at + 1] + rgb[at + 2]
        values[label] = total
    require(values["sunlit"] > values["occluded"],
            "Actual rendered PBR actor sunlit/occluded patch order is incorrect")
    return {"status": "PASS", "sunlit_rgb_sum": values["sunlit"],
            "occluded_rgb_sum": values["occluded"],
            "comparison": "strict relative RGB energy of equally-sized predeclared actor patches; no absolute brightness threshold"}
