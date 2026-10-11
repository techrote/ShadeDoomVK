#!/usr/bin/env python3
"""Independent, finite SDVK-008 physical collection; never awards acceptance.

The default campaign refuses incomplete fixtures before launching a renderer.
--correctness-only explicitly collects the available bounded subset and cannot
proceed to timing. Failed attempts are retained, never automatically retried.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.renderer_oracle import benchmark, images, prepare, run
    from tools.renderer_oracle.common import EvidenceError, canonical, checked, number, pin, read_json, require
else:
    from . import benchmark, images, prepare, run
    from .common import EvidenceError, canonical, checked, number, pin, read_json, require

IMPLEMENTATION_COMMIT = "9536324ce33ea418af5a8efe733b4659f6b4ad9b"
IMPLEMENTATION_TREE = "3123bc7fd3dd9074487cbe3487f9336ef3589003"
IMAGE_ORACLE_REVISION = "sdvk008-image-oracle-v2-alpha-active"
REFERENCE_EXTENT = "640x480"
TIMING_EXTENT = "1904x1001"
TIMING_ORDER = (
    ("S0", "SL", "SM", "SH", "M0", "MM", "MH", "G0", "GH", "P0", "PM"),
    ("PM", "P0", "GH", "G0", "MH", "MM", "M0", "SH", "SM", "SL", "S0"),
    ("MM", "G0", "SL", "P0", "MH", "S0", "PM", "SM", "GH", "M0", "SH"),
)
MATCHED_OFF = {"SL": "S0", "SM": "S0", "SH": "S0", "MM": "M0", "MH": "M0", "GH": "G0", "PM": "P0"}
WORK_CEILINGS = {"S0": 0, "SL": 10, "SM": 15, "SH": 23, "M0": 0, "MM": 15,
                 "MH": 23, "G0": 0, "GH": 23, "P0": 0, "PM": 15}


def fixture_contract():
    # Lazy import allows host-only statistical tests independently of authored
    # fixture integration. Missing fixture tooling is itself a preflight failure.
    if __package__ in (None, ""):
        from tools.renderer_oracle import sdvk008_fixtures
    else:
        from . import sdvk008_fixtures
    return sdvk008_fixtures


def capture_args(args, prepared, out, scene, mode, extent):
    return argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared, out=out,
        scene=scene, mode=mode, frames=1 if mode == "state" else 120, warmup=120,
        timeout=args.timeout, gpu=mode == "timing", include_stress=True,
        image_policy="exact", extent=extent, expected_commit=getattr(args, "expected_commit", None) or IMPLEMENTATION_COMMIT,
        require_clean=True, runtime_pins=getattr(args, "runtime_pins", None))


def pin_runtime(args):
    exe, iwad = args.exe.resolve(strict=True), args.iwad.resolve(strict=True)
    packages = {name: pin(exe.parent / name) for name in run.PACKAGES if (exe.parent / name).is_file()}
    require("vkdoom.pk3" in packages, "Physical runtime is missing vkdoom.pk3")
    return {"executable": pin(exe), "iwad": pin(iwad), "engine_packages": packages}


def driver_version_raw(value, vendor_id, driver_id=None):
    """Decode vulkaninfo's known driverVersion formats to the runtime uint32."""
    require(isinstance(value, str), "Vulkan preflight driver version is missing")
    if re.fullmatch(r"(?:0x[0-9a-fA-F]+|[0-9]+)", value):
        raw = int(value, 16 if value.startswith("0x") else 10)
    else:
        require(re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", value),
                "Vulkan preflight driver version has an unsupported encoding")
        parts = [int(part) for part in value.split(".")]
        if driver_id == "DRIVER_ID_NVIDIA_PROPRIETARY" or (driver_id is None and vendor_id == 0x10de):
            require(len(parts) == 4 and all(part < limit for part, limit in zip(parts, (1024, 256, 256, 64))),
                    "Vulkan preflight NVIDIA driver version is invalid")
            raw = (parts[0] << 22) | (parts[1] << 14) | (parts[2] << 6) | parts[3]
        elif driver_id == "DRIVER_ID_INTEL_PROPRIETARY_WINDOWS":
            require(len(parts) == 2 and parts[0] < (1 << 18) and parts[1] < (1 << 14),
                    "Vulkan preflight Intel Windows driver version is invalid")
            raw = (parts[0] << 14) | parts[1]
        else:
            require(len(parts) == 3 and all(part < limit for part, limit in zip(parts, (1024, 1024, 4096))),
                    "Vulkan preflight driver version is invalid")
            raw = (parts[0] << 22) | (parts[1] << 12) | parts[2]
    require(0 <= raw <= 0xffffffff, "Vulkan preflight driver version exceeds uint32")
    return raw


def vulkan_preflight(path, device_name, *, software=False):
    """Authenticate an operator-retained vulkaninfo --summary before launch.

    Runtime diagnostics must subsequently agree; a summary alone is never
    physical renderer evidence. No OS/CUDA inventory substitutes for Vulkan.
    """
    text = Path(path).read_text(encoding="utf-8")
    devices = []
    for section in re.split(r"(?m)^GPU\d+:\s*$", text)[1:]:
        values = dict(re.findall(r"(?m)^\s*(deviceName|deviceType|vendorID|deviceID|driverVersion|driverName|driverID)\s*=\s*(.*?)\s*$", section))
        if values.get("deviceName") == device_name:
            devices.append(values)
    require(len(devices) == 1, "Vulkan preflight has no unique preregistered device")
    selected = devices[0]
    types = {"PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU": 1, "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU": 2}
    if software:
        types = {"PHYSICAL_DEVICE_TYPE_CPU": 4}
        require(device_name.startswith("llvmpipe ("), "Software fixture control requires llvmpipe")
        require(len(re.findall(r"(?m)^GPU\d+:\s*$", text)) == 1
                and selected.get("driverName") == "llvmpipe"
                and selected.get("driverID") == "DRIVER_ID_MESA_LLVMPIPE", "Software fixture control requires one exact llvmpipe ICD")
    require(selected.get("deviceType") in types, "Prelaunch Vulkan software/unidentified device is refused")
    require(all(key in selected for key in ("vendorID", "deviceID", "driverVersion")), "Vulkan preflight identity is incomplete")
    vendor_id = int(selected["vendorID"], 0)
    return {"summary": pin(path), "device_name": device_name, "device_type": types[selected["deviceType"]],
            "vendor_id": vendor_id, "device_id": int(selected["deviceID"], 0),
            "driver_version": selected["driverVersion"],
            "driver_id": selected.get("driverID"),
            "driver_version_raw": driver_version_raw(selected["driverVersion"], vendor_id, selected.get("driverID"))}


def runtime_vulkan_identity(build, preflight):
    device = build.get("vulkan", {})
    require(type(device.get("driver_version_raw")) is int and 0 <= device["driver_version_raw"] <= 0xffffffff,
            "Renderer Vulkan raw driver version is missing or invalid")
    require(all(device.get(key) == preflight[key]
                for key in ("device_type", "vendor_id", "device_id", "driver_version_raw")),
            "Renderer Vulkan device/driver identity differs from prelaunch Vulkan inventory")


def validate_fixtures(contract, catalog, *, correctness_only=False):
    variants = contract.TIMING_VARIANTS
    require(set(variants) == set(WORK_CEILINGS), "Incomplete eleven-variant fixture matrix")
    require(len(set(variants.values())) == 11, "Timing variants must have distinct pinned recipes")
    scenes = {row["id"]: row for row in catalog["scenes"]}
    pairs = contract.CORRECTNESS_PAIRS
    require(pairs and len({row["id"] for row in pairs}) == len(pairs), "Missing/duplicate correctness pairs")
    ids = set(variants.values()) | {row[key] for row in pairs for key in ("off", "on", "background") if key in row}
    require(ids <= scenes.keys(), "Required SDVK-008 fixtures are absent from the authenticated corpus")
    for variant, scene_id in variants.items():
        native = scenes[scene_id]["native"]
        settings = native["settings"]
        depth = settings.get("gl_sprite_relief_depth")
        quality = settings.get("gl_sprite_relief_quality")
        expected_quality = 1 if variant == "SL" else 3 if variant in ("SH", "MH", "GH") else 2
        require(depth == (0 if variant.endswith("0") else 0.012) and quality == expected_quality,
                "Timing relief controls differ from preregistration: " + variant)
        require({"gl_sprite_relief_depth", "gl_sprite_relief_quality"} <= set(native["console_queries"]),
                "Timing recipe does not read back both relief controls")
        require(native.get("generic_capture_supported", True), "Fixture requires an incompatible private PF driver")
        require(set(scenes[scene_id]["required_state_channels"]) >= {"sprite-basis", "sprite-relief", "material"},
                "Fixture does not require emitted material/basis/relief evidence")
    for pair in pairs:
        off, on = (scenes[pair[key]]["native"] for key in ("off", "on"))
        for key in ("map", "camera", "seed", "clock"):
            require(off[key] == on[key], "Authored OFF/ON fixture changed " + key)
        def unchanged_settings(native):
            return {key: value for key, value in native["settings"].items()
                    if key not in ("gl_sprite_relief_depth", "gl_sprite_relief_quality")}
        require(unchanged_settings(off) == unchanged_settings(on), "Authored OFF/ON non-relief settings differ")
    missing = list(contract.MISSING_GATES)
    require(set(contract.AVAILABLE_GATES).isdisjoint(missing), "Fixture gate claimed both present and missing")
    require(set(contract.REQUIRED_GATES) <= set(contract.AVAILABLE_GATES) | set(missing), "Unaccounted required fixture gate")
    if not correctness_only:
        require(not missing, "Incomplete physical correctness fixtures: " + ", ".join(missing))
    return sorted(ids)


def physical_build(build, *, commit, device_name):
    require(build.get("backend") == "vulkan" and build.get("working_tree") == "clean",
            "Physical campaign requires a clean identified Vulkan renderer")
    require(build.get("commit") == commit, "Renderer source commit differs from the frozen implementation")
    device = build.get("vulkan", {})
    require(device.get("available") is True and device.get("device_type") in (1, 2),
            "Physical campaign refuses software/unidentified Vulkan devices")
    require(build.get("device") == device_name, "Actual Vulkan GPU differs from the preregistered device name")


def software_build(build, *, commit, device_name):
    require(build.get("backend") == "vulkan" and build.get("working_tree") == "clean" and build.get("commit") == commit,
            "Software fixture control requires an exact clean identified Vulkan build")
    require(build.get("vulkan", {}).get("available") is True and build["vulkan"].get("device_type") == 4
            and build.get("device") == device_name and device_name.startswith("llvmpipe ("),
            "Software fixture control requires the preregistered CPU llvmpipe device")


def prepared_pair_continuity(prepared, pairs):
    scenes = {row["id"]: row for row in prepared["scenes"]}
    for pair in pairs:
        identities = [prepared["files"][scenes[pair[key]]["native"]["pk3"]] for key in ("off", "on")]
        require(identities[0] == identities[1], "Authored OFF/ON package bytes differ: " + pair["id"])


def relief_draw_witness(path):
    raw = read_json(Path(path) / "native.renderer.json")
    native = read_json(Path(path) / "recipe.json")["native"]
    family = native["relief_family"]
    material = "SDVRA1" if family == "mirror" else "SDVEA0"
    rows = [row["data"] for row in raw["records"] if row["kind"] == "sprite-relief"
            and row["data"].get("material") == material]
    if family == "alpha-background":
        require(not rows, "No-card matte background unexpectedly drew the test sprite")
        return {"emitted_test_draws": 0, "eligible_draws": 0}
    require(rows, "Authored sprite material has no emitted relief draw witness")
    settings = native["settings"]
    depth, quality = settings.get("gl_sprite_relief_depth", 0), settings.get("gl_sprite_relief_quality", 2)
    if "gl_sprite_relief_depth" not in settings:
        # The default-OFF recipe queries depth without assigning it. Authenticate
        # this extra readback although it is intentionally absent from settings.
        run.console_settings((Path(path) / "stdout.log").read_text(encoding="utf-8", errors="replace"),
                             {"gl_sprite_relief_depth": 0})
    enabled = depth > 0 and quality in (1, 2, 3) and family != "heightless"
    require(any(row["eligible_draw"] for row in rows) if enabled else not any(row["eligible_draw"] for row in rows),
            "Observed eligible relief draws disagree with the declared fixture work")
    if enabled:
        require(all(row["quality"] == quality and abs(row["depth"] - depth) <= 1e-6
                    and row["height_reads_max"] == {1: 10, 2: 15, 3: 23}[quality]
                    for row in rows if row["eligible_draw"]), "Emitted relief work ceiling/control mismatch")
    return {"material": material, "emitted_test_draws": len(rows),
            "eligible_draws": sum(row["eligible_draw"] for row in rows),
            "height_read_ceilings": sorted({row["height_reads_max"] for row in rows}),
            "actual_fragment_work_measured": False}


def continuity(reference, candidate):
    require(run.comparable_build(reference["build"]) == run.comparable_build(candidate["build"]),
            "Source/build/device changed during SDVK-008 collection")
    require(reference["executable"]["sha256"] == candidate["executable"]["sha256"], "Executable bytes changed")
    # Scene packages intentionally vary between fixtures. Engine/IWAD packages
    # must remain identical across the entire campaign.
    def common_packages(value):
        return [row for row in run.package_identity(value) if row[0] != "scene.pk3"]
    require(common_packages(reference) == common_packages(candidate), "Engine/IWAD package continuity failed")


def image_pair(left, right, oracle, *, background=None):
    """A bounded RGB witness; never invents alpha or directional evidence."""
    extent, a = images.decode(Path(left) / "native.png")
    other_extent, b = images.decode(Path(right) / "native.png")
    require(extent == other_extent, "OFF/ON image extents differ")
    require(oracle in ("exact", "effect", "silhouette", "mirror"), "Unknown image oracle")
    changed = sum(a[i:i+3] != b[i:i+3] for i in range(0, len(a), 3))
    passed = changed == 0 if oracle == "exact" else changed > 0
    result = {"status": ("PASS" if passed else "FAIL") if oracle in ("exact", "effect") else "DESCRIPTIVE",
            "oracle": oracle, "oracle_revision": IMAGE_ORACLE_REVISION,
            "extent": list(extent), "changed_pixels": changed,
            "changed_pixel_fraction": changed / (extent[0] * extent[1]),
            "direction_qualified": False, "alpha_silhouette_qualified": False,
            "useful_relief_qualified": False,
            "scope": "RGB equality/difference only; no fragment execution, alpha-mask, direction or quality inference"}
    if oracle == "silhouette" and background is not None:
        bg_extent, bg = images.decode(Path(background) / "native.png")
        require(extent == bg_extent, "Silhouette background extent differs")
        off_mask = [a[i:i+3] != bg[i:i+3] for i in range(0, len(a), 3)]
        on_mask = [b[i:i+3] != bg[i:i+3] for i in range(0, len(a), 3)]
        mismatch = sum(x != y for x, y in zip(off_mask, on_mask))
        # material.glsl retains baseTexel.a while changing relieved RGB. Demand
        # positive color work in this same fixture so an all-fallback ON image
        # cannot vacuously establish silhouette preservation under relief.
        qualified = mismatch == 0 and any(off_mask) and changed > 0
        result.update(status="PASS" if qualified else "FAIL",
                      silhouette_mask_mismatch_pixels=mismatch, affected_pixels=sum(off_mask),
                      alpha_silhouette_qualified=qualified, alpha_relief_effect_detected=changed > 0,
                      scope="Exact binary RGB-versus-no-card-background mask plus nonzero OFF/ON RGB effect; this authored fixture only")
    return result


def controlled_pair(left, right):
    """Validate the actual packets before attributing pixels to relief controls."""
    _, a, raw_a, _ = run.validate_run(left)
    _, b, raw_b, _ = run.validate_run(right)
    continuity(a, b)
    require(a["mode"] == b["mode"] == "state", "OFF/ON needs independently collected state images")
    x, y = a["reproduction"], b["reproduction"]
    for key in ("scene_sha256", "iwad_sha256", "camera", "seed", "extent", "clock", "warmup_frames",
                "frames", "application_cache", "driver_cache", "image_policy"):
        require(x[key] == y[key], "OFF/ON changed a non-relief input: " + key)
    def legacy_settings(value):
        return {key: item for key, item in value.items() if key not in
                ("gl_sprite_relief_depth", "gl_sprite_relief_quality")}
    require(legacy_settings(x["settings"]) == legacy_settings(y["settings"]),
            "OFF/ON changed non-relief settings")
    return raw_a, raw_b


def flip_witness(raw_a, raw_b, axis):
    require(axis in ("x", "y"), "Unknown actor flip axis")
    counts = [sum(row["kind"] == "sprite-basis" and row["data"].get("material") == "SDVEA0"
                  and row["data"].get("surface", {}).get("uv_mirror_" + axis) is True
                  for row in raw["records"]) for raw in (raw_a, raw_b)]
    require(all(count > 0 for count in counts), "Actor flip lacks emitted signed-UV witness: " + axis)
    return {"axis": axis, "off_emitted_draws": counts[0], "on_emitted_draws": counts[1]}


def matched_effect(off, on, *, anomaly=False):
    """Three paired process medians; strict preregistered detection limits."""
    require(len(off) == len(on) == 3, "Effect analysis requires three matched independent processes")
    off = [number(value, "OFF median") for value in off]
    on = [number(value, "ON median") for value in on]
    baseline = statistics.median(off)
    on_median = statistics.median(on)
    mad = statistics.median(abs(value - baseline) for value in off)
    deviation = max(abs(value - baseline) for value in off)
    differences = [b - a for a, b in zip(off, on)]
    median = statistics.median(differences)
    threshold = max(0.05, 2 * mad)
    direction_count = max(sum(value > 0 for value in differences), sum(value < 0 for value in differences))
    variable = deviation > 0.05 * baseline
    status = "INCONCLUSIVE" if variable or anomaly else (
        "DETECTABLE_DIRECTIONAL_EFFECT" if direction_count >= 2 and abs(median) > threshold
        else "BELOW_DETECTION_LIMIT")
    return {"status": status, "off_process_medians_ms": off, "on_process_medians_ms": on,
            "off_median_ms": baseline, "off_process_median_mad_ms": mad,
            "on_median_ms": on_median,
            "on_process_median_mad_ms": statistics.median(abs(value - on_median) for value in on),
            "off_max_deviation_ms": deviation, "off_variability_exceeds_five_percent": variable,
            "differences_ms": differences, "median_difference_ms": median,
            "ratios": [b / a if a else None for a, b in zip(off, on)],
            "median_ratio": statistics.median([b / a for a, b in zip(off, on)]) if all(off) else None,
            "detection_threshold_ms": threshold, "same_sign_repetitions": direction_count,
            "anomaly": anomaly, "zero_cost_claim": False}


def timing_integrity(path):
    """Authenticate raw per-frame GPU coverage, never infer it from length."""
    native_path = Path(path) / "native.renderer.json"
    raw = read_json(native_path)
    require(raw.get("mode") == "timing" and raw.get("observed_frames") == 120,
            "Timing integrity requires exactly 120 retained timing frames")
    groups = {}
    for row in raw["records"]:
        if row["kind"] != "timing":
            continue
        data = row["data"]
        require(data.get("available") is not False, "Unresolved GPU batch in retained timing frames")
        if data.get("clock") != "gpu":
            continue
        name = data.get("name")
        require(isinstance(name, str) and name, "Raw GPU timing group is unnamed")
        require(row.get("count") == 1, "Raw GPU timestamp records must retain individual samples")
        frame = row.get("frame")
        require(type(frame) is int and 1 <= frame <= 120, "GPU timestamp frame lies outside the retained interval")
        counts = groups.setdefault(name, {})
        counts[frame] = counts.get(frame, 0) + 1
    for name, counts in groups.items():
        require(set(counts) == set(range(1, 121)) and all(value == 1 for value in counts.values()),
                "Incomplete or duplicate raw per-frame GPU group: " + name)
    scene_complete = "scene.immediate" in groups
    return {"schema": "sdvk008-raw-gpu-timing-integrity/v1",
            "status": "COMPLETE_GPU_SCENE_SCOPE" if scene_complete else "INCONCLUSIVE_GPU_SCENE_SCOPE",
            "scene_immediate_complete": scene_complete, "all_retained_groups_complete": True,
            "native_observation": pin(native_path),
            "groups": {name: {"frame_ordinals": sorted(counts), "samples_per_frame": 1}
                       for name, counts in sorted(groups.items())},
            "physical_gpu_qualified": False}


def timing_analysis(summaries, *, anomaly=False):
    require(set(summaries) == set(WORK_CEILINGS), "Incomplete timing matrix")
    per_variant = {}
    gpu_integrity = {}
    for variant, summary in summaries.items():
        require(summary["independent_processes"] == len(summary["runs"]) == 3,
                "Timing matrix requires three independent processes per variant")
        per_variant[variant] = []
        gpu_integrity[variant] = []
        for process in summary["runs"]:
            data = process["summary"]
            require(len(data["raw_cpu_render_view_ms"]) == data["cpu_render_view"]["count"] == 120,
                    "Timing process must retain exactly 120 CPU frames")
            groups = {"cpu_render_view_ms": data["cpu_render_view"]}
            incomplete = []
            for name, group in data["gpu_groups"].items():
                if not len(group["samples_ms"]) == group["distribution"]["count"] == 120:
                    incomplete.append(name)
                groups["gpu:" + name] = group["distribution"]
            scene = data["gpu_groups"].get("scene.immediate")
            raw_integrity = process.get("gpu_timing_integrity", {})
            attested = (raw_integrity.get("status") == "COMPLETE_GPU_SCENE_SCOPE"
                        and raw_integrity.get("scene_immediate_complete") is True
                        and raw_integrity.get("all_retained_groups_complete") is True)
            gpu_integrity[variant].append({
                "scene_immediate_complete": attested and scene is not None and
                    len(scene["samples_ms"]) == scene["distribution"]["count"] == 120,
                "scene_immediate_raw_samples": len(scene["samples_ms"]) if scene else 0,
                "raw_frame_integrity": raw_integrity,
                "raw_frame_coverage_attested": attested,
                "incomplete_retained_groups": sorted(incomplete)})
            per_variant[variant].append(groups)
    comparisons = {}
    for on, off in MATCHED_OFF.items():
        group_sets = [set(row) for variant in (off, on) for row in per_variant[variant]]
        groups = set.intersection(*group_sets)
        missing = set.union(*group_sets) - groups
        comparisons[on] = {"off": off, "groups": {
            group: matched_effect([row[group]["p50"] for row in per_variant[off]],
                                  [row[group]["p50"] for row in per_variant[on]],
                                  anomaly=anomaly or (group.startswith("gpu:") and any(
                                      group.removeprefix("gpu:") in row["incomplete_retained_groups"]
                                      for variant in (off, on) for row in gpu_integrity[variant])))
            for group in sorted(groups)}, "unavailable_or_inconsistent_groups": sorted(missing)}
    gpu_complete = all(row["scene_immediate_complete"] and not row["incomplete_retained_groups"]
                       for rows in gpu_integrity.values() for row in rows)
    return {"schema": "sdvk008-physical-analysis/v1",
            "status": "DESCRIPTIVE_GPU_SCENE_SCOPE_AVAILABLE" if gpu_complete else "INCONCLUSIVE_GPU_SCENE_SCOPE",
            "gpu_scene_scope_complete": gpu_complete, "gpu_group_integrity": gpu_integrity,
            "gpu_scope_limitation": "Requires scene.immediate exactly once in each raw retained frame 1..120 in every one of 33 processes and complete retained groups; lengths or postprocess groups cannot substitute for the sprite scene span",
            "comparisons": comparisons,
            "per_process_distributions": per_variant, "nested_gpu_groups_summed": False,
            "work_ceilings": WORK_CEILINGS, "work_ceiling_is_measured_work": False,
            "physical_gpu_qualified": False, "performance_accepted": False, "quality_modes_accepted": []}


def verify_checksums(root):
    manifest = read_json(Path(root) / "checksums.json")
    require(manifest.get("schema") == "sdvk008-packet-checksums/v1", "Unknown packet checksum schema")
    names = {row["path"] for row in manifest["files"]}
    require(len(names) == len(manifest["files"]), "Duplicate packet checksum entries")
    actual = {path.relative_to(root).as_posix() for path in Path(root).rglob("*")
              if path.is_file() and path.name != "checksums.json"}
    require(names == actual, "Packet file inventory changed")
    for row in manifest["files"]:
        checked(root, row)
    return manifest


def campaign(args):
    require(args.execute, "Physical GPU launches require explicit --execute")
    software = getattr(args, "software_fixture_control", False)
    expected_commit = getattr(args, "expected_commit", None) or IMPLEMENTATION_COMMIT
    require(not software or args.correctness_only, "Software fixture control requires --correctness-only; no timing")
    require(not software or getattr(args, "expected_commit", None), "Software fixture control requires an explicit --expected-commit")
    require(re.fullmatch(r"[0-9a-f]{40}", expected_commit), "Expected renderer commit must be exact")
    require(software or expected_commit == IMPLEMENTATION_COMMIT, "Physical renderer source cannot override the frozen implementation")
    root = run.fresh_directory(args.out)
    receipt = {"schema": "sdvk008-software-fixture-control/v1" if software else "sdvk008-physical-campaign/v1", "status": "FAIL", "steps": [],
        "implementation_commit": expected_commit, "implementation_tree": None if software else IMPLEMENTATION_TREE,
        "image_oracle_revision": IMAGE_ORACLE_REVISION,
        "physical_gpu_evidence_collected": False, "physical_gpu_qualified": False,
        "performance_accepted": False, "automatic_retries": 0,
        "software_fixture_control": software, "software_vulkan_evidence_collected": False,
        "correctness_only": args.correctness_only, "timing_order": TIMING_ORDER,
        "reference_extent": REFERENCE_EXTENT, "timing_extent": TIMING_EXTENT,
        "default_policy": "OFF; SDVK-016 owns final tiers/defaults"}
    try:
        contract = fixture_contract()
        receipt["missing_gates"] = list(contract.MISSING_GATES)
        receipt["tooling_files"] = [pin(path) for path in
            (Path(__file__), Path(contract.__file__) if hasattr(contract, "__file__") else Path(__file__),
             Path(run.__file__), Path(prepare.__file__), prepare.CATALOG)]
        ids = validate_fixtures(contract, prepare.load_catalog(), correctness_only=args.correctness_only)
        pairs = contract.CORRECTNESS_PAIRS
        if software:
            pairs = [row for row in pairs if row["id"] in ("default-off", "heightless", "single-m", "alpha")]
            require(pairs, "Software smoke has no supported fixture pairs")
            ids = sorted({row[key] for row in pairs for key in ("off", "on", "background") if key in row})
            receipt["software_smoke_pairs"] = [row["id"] for row in pairs]
            license_path = getattr(args, "iwad_license", None)
            require(license_path is not None, "Software fixture control requires --iwad-license for retained artifact copies")
            (root / "iwad-copyright.txt").write_bytes(Path(license_path).read_bytes())
        receipt["vulkan_preflight"] = vulkan_preflight(args.vulkan_summary, args.device_name, software=software)
        (root / "vulkan-summary.txt").write_bytes(Path(args.vulkan_summary).read_bytes())
        require(pin(root / "vulkan-summary.txt")["sha256"] == receipt["vulkan_preflight"]["summary"]["sha256"],
                "Vulkan preflight inventory changed while being retained")
        args.runtime_pins = pin_runtime(args)
        receipt["input_identity"] = args.runtime_pins
        prepared = root / "prepared"
        receipt["prepared"] = prepare.prepare(prepared, ids)
        prepared_pair_continuity(receipt["prepared"], pairs)
        reference = None
        reference_environment = None
        state_paths = {}
        raw_timing_integrities = {}

        def capture(scene, extent, path, mode):
            nonlocal reference, reference_environment
            step = {"scene": scene, "extent": extent, "mode": mode,
                    "path": path.relative_to(root).as_posix(), "status": "STARTED"}
            receipt["steps"].append(step)
            result = run.capture(capture_args(args, prepared, path, scene, mode, extent))
            (software_build if software else physical_build)(result["build"], commit=expected_commit, device_name=args.device_name)
            runtime_vulkan_identity(result["build"], receipt["vulkan_preflight"])
            request = read_json(path / "request.json")
            environment = {key: request[key] for key in ("host", "environment")}
            if reference_environment is None:
                reference_environment = environment
                receipt["host_and_environment"] = environment
            else:
                require(reference_environment == environment, "Host/loader/layer environment changed during campaign")
            if reference is None:
                reference = result
                receipt["build"] = result["build"]
            else:
                continuity(reference, result)
            require(pin(args.exe)["sha256"] == receipt["input_identity"]["executable"]["sha256"]
                    and pin(args.iwad)["sha256"] == receipt["input_identity"]["iwad"]["sha256"],
                    "Campaign input bytes changed")
            if mode == "state":
                step["relief_draw_witness"] = relief_draw_witness(path)
            else:
                step["gpu_timing_integrity"] = timing_integrity(path)
                raw_timing_integrities[path] = step["gpu_timing_integrity"]
            step["status"] = "PASS"
            return result

        # Every correctness recipe twice, then every timing variant twice at
        # timing extent. These are state processes, never timing samples.
        stages = [(REFERENCE_EXTENT, ids)]
        if not software:
            stages.append((TIMING_EXTENT, list(contract.TIMING_VARIANTS.values())))
        for extent, selected in stages:
            for scene in selected:
                paths = [root / "state" / extent / scene / str(attempt) for attempt in (1, 2)]
                for path in paths:
                    capture(scene, extent, path, "state")
                comparison = run.compare_runs(*paths)
                (paths[0].parent / "repeat-comparison.json").write_bytes(canonical(comparison))
                require(comparison["status"] == "PASS", "Independent state/image repeat failed: " + scene)
                state_paths[extent, scene] = paths
        receipt["image_pairs"] = {}
        for pair in pairs:
            witnesses = []
            for attempt in (0, 1):
                off = state_paths[REFERENCE_EXTENT, pair["off"]][attempt]
                on = state_paths[REFERENCE_EXTENT, pair["on"]][attempt]
                raw_pair = controlled_pair(off, on)
                background = (state_paths[REFERENCE_EXTENT, pair["background"]][attempt]
                              if "background" in pair else None)
                witness = image_pair(off, on, pair["oracle"], background=background)
                if pair["id"] in ("single-flipx", "single-flipy"):
                    witness["emitted_flip"] = flip_witness(*raw_pair, pair["id"][-1])
                if pair["id"].startswith("single-") and hasattr(contract, "red_marker_direction"):
                    extent, off_rgb = images.decode(off / "native.png")
                    _, on_rgb = images.decode(on / "native.png")
                    direction = contract.red_marker_direction(off_rgb, on_rgb, *extent)
                    witness["directional_marker"] = direction
                    witness["direction_qualified"] = direction["status"] == "PASS"
                    if direction["status"] == "FAIL":
                        witness["status"] = "FAIL"
                    elif direction["status"] != "PASS":
                        witness["status"] = "INCONCLUSIVE"
                witnesses.append(witness)
            receipt["image_pairs"][pair["id"]] = witnesses
            require(all(row["status"] != "FAIL" for row in witnesses), "OFF/ON image witness failed: " + pair["id"])
        receipt["incomplete_image_pairs"] = [name for name, rows in receipt["image_pairs"].items()
                                             if any(row["status"] != "PASS" for row in rows)]
        if software:
            require(not receipt["incomplete_image_pairs"],
                    "Software fixture control has incomplete image/direction/alpha witnesses: "
                    + ", ".join(receipt["incomplete_image_pairs"]))
        receipt["physical_gpu_evidence_collected"] = not software
        receipt["software_vulkan_evidence_collected"] = software
        if args.correctness_only:
            receipt["status"] = "SOFTWARE_FIXTURE_CONTROL_COLLECTED" if software else "PARTIAL_CORRECTNESS_COLLECTED"
        else:
            require(all(row["status"] == "PASS" for rows in receipt["image_pairs"].values() for row in rows),
                    "Descriptive image witnesses cannot qualify correctness before timing")
            timing_paths = {variant: [] for variant in WORK_CEILINGS}
            for repetition, order in enumerate(TIMING_ORDER, 1):
                for ordinal, variant in enumerate(order, 1):
                    path = root / "timing" / f"rep-{repetition}" / f"{ordinal:02d}-{variant}"
                    capture(contract.TIMING_VARIANTS[variant], TIMING_EXTENT, path, "timing")
                    timing_paths[variant].append(path)
            summaries = {variant: run.summarize_runs(paths, minimum_samples=120) for variant, paths in timing_paths.items()}
            for variant, paths in timing_paths.items():
                for process, path in zip(summaries[variant]["runs"], paths):
                    process["gpu_timing_integrity"] = raw_timing_integrities[path]
            receipt["analysis"] = timing_analysis(summaries)
            for variant, summary in summaries.items():
                (root / f"timing-{variant}-summary.json").write_bytes(canonical(summary))
            receipt["status"] = "COLLECTED_PENDING_REVIEW"
    except (OSError, ValueError, ImportError, KeyError, TypeError) as error:
        receipt["error"] = str(error)
    finally:
        receipt_name = "sdvk008-software-fixture-control.json" if software else "sdvk008-physical-campaign.json"
        (root / receipt_name).write_bytes(canonical(receipt))
        inventory = {"schema": "sdvk008-packet-checksums/v1", "files": [pin(path, relative_to=root)
            for path in sorted(root.rglob("*")) if path.is_file()]}
        (root / "checksums.json").write_bytes(canonical(inventory))
    verify_checksums(root)
    require(receipt["status"] != "FAIL", "SDVK-008 campaign failed; retain packet: " + receipt.get("error", "unknown"))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--device-name", required=True, help="exact preregistered Vulkan device name")
    parser.add_argument("--vulkan-summary", type=Path, required=True, help="retained vulkaninfo --summary from this host")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--correctness-only", action="store_true", help="bounded partial evidence; never runs timings")
    parser.add_argument("--software-fixture-control", action="store_true", help="separate CPU llvmpipe smoke; never physical evidence")
    parser.add_argument("--expected-commit", help="exact hosted software-control build; physical source is immutable")
    parser.add_argument("--iwad-license", type=Path, help="license retained for the software-control artifact")
    args = parser.parse_args(argv)
    try:
        result = campaign(args)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ("status", "physical_gpu_evidence_collected", "physical_gpu_qualified")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
