#!/usr/bin/env python3
"""Preregistered physical-GPU campaign driver for SDVK-009.

This tool is deliberately not used by hosted CI. It consumes the accepted
renderer-oracle preparation/capture/comparison machinery on a physical Vulkan
GPU and leaves every process packet in a deterministic directory layout. It
never retries a failed launch and stops before performance timing when a
correctness gate fails.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.renderer_oracle import prepare, run
    from tools.renderer_oracle.common import EvidenceError, canonical, require
else:
    from . import prepare, run
    from .common import EvidenceError, canonical, require

REFERENCE_SCENES = (
    "compositing", "lights-zero", "lights-one", "lights-many",
    "lights-dense-overlap", "lights-dense-dispersed", "shadow-boundary",
    "material-stress", "sun-probes", "sprite-mirror",
)
HIGHRES_STATE_SCENES = ("lights-many", "lights-dense-dispersed", "lights-dense-overlap")
TIMING_SCENES = ("lights-zero", "lights-one", "lights-many", "lights-dense-dispersed", "lights-dense-overlap")
TIMING_ORDER = (
    ("lights-zero", "lights-one", "lights-many", "lights-dense-dispersed", "lights-dense-overlap"),
    ("lights-dense-overlap", "lights-dense-dispersed", "lights-many", "lights-one", "lights-zero"),
    ("lights-many", "lights-zero", "lights-dense-overlap", "lights-one", "lights-dense-dispersed"),
)
REFERENCE_EXTENT = "640x480"
ARCHITECTURE_EXTENT = "1904x1001"
EXPECTED_RENDERER_COMMIT = "0a2fbad203549d18ac6e5a61bb4747709637bfde"


def _write(path: Path, value) -> None:
    path.write_bytes(canonical(value))


def _capture_args(args, prepared: Path, out: Path, scene: str, mode: str, *, extent=None):
    return argparse.Namespace(
        exe=args.exe, iwad=args.iwad, prepared=prepared, out=out, scene=scene, mode=mode,
        frames=1 if mode == "state" else 120, warmup=120, timeout=args.timeout,
        gpu=mode == "timing", include_stress=True, image_policy="exact", extent=extent,
        expected_commit=getattr(args, "expected_commit", EXPECTED_RENDERER_COMMIT), require_clean=True,
        runtime_pins=getattr(args, "runtime_pins", None),
    )


def _physical_build(build) -> None:
    vulkan = build.get("vulkan", {})
    require(vulkan.get("available") is True, "SDVK-009 physical campaign requires an identified Vulkan device")
    require(vulkan.get("device_type") in (1, 2),
            "SDVK-009 physical campaign requires an integrated or discrete physical Vulkan GPU")


def _same_build(reference, candidate) -> None:
    require(run.comparable_build(reference) == run.comparable_build(candidate),
            "SDVK-009 campaign build/device identity changed between processes")


def _runtime_identity(result):
    """Pin engine bytes across scenes; scene.pk3 deliberately varies by workload."""
    executable = result.get("executable", {})
    require(re.fullmatch(r"[0-9a-f]{64}", executable.get("sha256", "")), "Missing executable checksum")
    packages = result.get("loaded_packages", [])
    engine = sorted((Path(row["path"]).name, row["sha256"], row["bytes"], row["lumps"])
                    for row in packages if Path(row["path"]).name in run.PACKAGES)
    require(any(row[0] == "vkdoom.pk3" for row in engine), "Missing loaded engine package identity")
    iwad = result.get("reproduction", {}).get("iwad_sha256", "")
    require(re.fullmatch(r"[0-9a-f]{64}", iwad), "Missing IWAD checksum")
    return {"executable_sha256": executable["sha256"], "engine_packages": engine, "iwad_sha256": iwad}


def _pin_runtime(args):
    exe, iwad = args.exe.resolve(strict=True), args.iwad.resolve(strict=True)
    packages = {name: run.pin(exe.parent / name) for name in run.PACKAGES if (exe.parent / name).is_file()}
    require("vkdoom.pk3" in packages, "Runtime has no vkdoom.pk3")
    return {"executable": run.pin(exe), "iwad": run.pin(iwad), "engine_packages": packages}


def _timing_integrity(path):
    raw = run.read_json(path / "native.renderer.json")
    require(raw.get("mode") == "timing" and raw.get("observed_frames") == 120,
            "Physical timing interval must retain 120 frames")
    groups = {}
    failures = []
    for record in raw["records"]:
        if record["kind"] != "timing":
            continue
        value = record["data"]
        if value.get("available") is False:
            failures.append("Unresolved GPU batch in retained physical timing interval")
        if value.get("clock") == "gpu":
            frames = groups.setdefault(value["name"], {})
            frames[record["frame"]] = frames.get(record["frame"], 0) + 1
    if not groups:
        failures.append("No resolved GPU timestamp groups in physical timing interval")
    for name, frames in groups.items():
        if set(frames) != set(range(1, 121)) or len(set(frames.values())) != 1:
            failures.append("Incomplete or inconsistent retained GPU group: " + name)
    return {"status": "INCONCLUSIVE" if failures else "COMPLETE_GROUPS_SCOPE_UNQUALIFIED",
            "failures": sorted(set(failures)),
            "groups": {name: {"frames": len(frames), "samples_per_frame": sorted(set(frames.values()))}
                       for name, frames in sorted(groups.items())}}


def campaign(args):
    require(args.execute, "Physical GPU launches require explicit --execute")
    root = run.fresh_directory(args.out)
    prepared = root / "prepared"
    receipt = {
        "schema": "sdvk009-physical-campaign/v1", "status": "FAIL",
        "physical_gpu_evidence_collected": False, "physical_gpu_qualified": False, "performance_accepted": False,
        "reference_extent": REFERENCE_EXTENT, "architecture_extent": ARCHITECTURE_EXTENT,
        "reference_scenes": list(REFERENCE_SCENES), "highres_state_scenes": list(HIGHRES_STATE_SCENES),
        "timing_scenes": list(TIMING_SCENES), "timing_order": [list(row) for row in TIMING_ORDER],
        "automatic_retries": 0, "steps": [],
        "expected_renderer_commit": getattr(args, "expected_commit", EXPECTED_RENDERER_COMMIT),
    }
    reference_build = None
    reference_runtime = None

    def check_capture(result):
        nonlocal reference_build, reference_runtime
        _physical_build(result["build"])
        require(result["build"].get("working_tree") == "clean", "Physical campaign requires a clean renderer build")
        require(result["build"].get("commit") == receipt["expected_renderer_commit"],
                "Renderer commit differs from the preregistered physical baseline")
        identity = _runtime_identity(result)
        if reference_build is None:
            reference_build, reference_runtime = result["build"], identity
            receipt["build"] = run.comparable_build(reference_build)
            receipt["runtime_identity"] = identity
        else:
            _same_build(reference_build, result["build"])
            require(identity == reference_runtime, "Campaign executable/engine package/IWAD bytes changed between processes")

    try:
        args.runtime_pins = _pin_runtime(args)
        receipt["preregistered_runtime"] = args.runtime_pins
        prepared_result = prepare.prepare(prepared, list(REFERENCE_SCENES))
        receipt["prepared"] = prepared_result
        receipt["steps"].append({"name": "prepare", "status": "PASS"})

        for scene in REFERENCE_SCENES:
            paths = []
            for attempt in (1, 2):
                path = root / "reference-state" / scene / str(attempt)
                result = run.capture(_capture_args(args, prepared, path, scene, "state"))
                check_capture(result)
                paths.append(path)
                receipt["steps"].append({"name": f"reference-{scene}-state-{attempt}", "status": "PASS"})
            comparison = run.compare_runs(paths[0], paths[1])
            _write(root / f"reference-{scene}-comparison.json", comparison)
            require(comparison["status"] == "PASS", f"Reference state/image comparison failed: {scene}")
            receipt["steps"].append({"name": f"reference-{scene}-compare", "status": "PASS"})

        for scene in HIGHRES_STATE_SCENES:
            paths = []
            for attempt in (1, 2):
                path = root / "highres-state" / scene / str(attempt)
                result = run.capture(_capture_args(args, prepared, path, scene, "state", extent=ARCHITECTURE_EXTENT))
                check_capture(result)
                paths.append(path)
                receipt["steps"].append({"name": f"highres-{scene}-state-{attempt}", "status": "PASS"})
            comparison = run.compare_runs(paths[0], paths[1])
            _write(root / f"highres-{scene}-comparison.json", comparison)
            require(comparison["status"] == "PASS", f"High-resolution state/image comparison failed: {scene}")
            receipt["steps"].append({"name": f"highres-{scene}-compare", "status": "PASS"})

        timing_paths = {scene: [] for scene in TIMING_SCENES}
        for repetition, order in enumerate(TIMING_ORDER, 1):
            for ordinal, scene in enumerate(order, 1):
                path = root / "timing" / f"rep-{repetition}" / f"{ordinal:02d}-{scene}"
                result = run.capture(_capture_args(args, prepared, path, scene, "timing", extent=ARCHITECTURE_EXTENT))
                check_capture(result)
                coverage = _timing_integrity(path)
                timing_paths[scene].append(path)
                receipt["steps"].append({"name": f"timing-r{repetition}-{scene}", "status": "PASS", "gpu_coverage": coverage})

        receipt["timing_summaries"] = {}
        for scene in TIMING_SCENES:
            summary = run.summarize_runs(timing_paths[scene], minimum_samples=120)
            target = root / f"timing-{scene}-summary.json"
            _write(target, summary)
            receipt["timing_summaries"][scene] = target.relative_to(root).as_posix()

        receipt["status"] = "COLLECTED_PENDING_SDVK009_DECISION"
        receipt["physical_gpu_evidence_collected"] = True
        receipt["physical_gpu_qualified"] = False
        receipt["performance_accepted"] = False
        timing_steps = [step for step in receipt["steps"] if step["name"].startswith("timing-r")]
        receipt["gpu_scene_timing_complete"] = len(timing_steps) == 15 and all(
            step["gpu_coverage"].get("status") == "COMPLETE_GROUPS_SCOPE_UNQUALIFIED" and
            step["gpu_coverage"].get("groups", {}).get("scene.immediate") ==
            {"frames": 120, "samples_per_frame": [1]} for step in timing_steps)
        if receipt["gpu_scene_timing_complete"]:
            receipt["gpu_architecture_decision"] = "PENDING_THRESHOLD_ANALYSIS"
        else:
            receipt["gpu_architecture_decision"] = "INCONCLUSIVE_NO_LIGHT_SENSITIVE_SCENE_TIMESTAMP_GROUP"
            receipt["gpu_scope_limitation"] = (
                "Complete scene.immediate intervals were not established. The original frozen source "
                "timestamps postprocess/lightmapping and dormant tile work only; "
                "resolved postprocess groups do not measure immediate world/sprite light shading. "
                "A separately preregistered instrumentation revision or external GPU profiler is required.")
    except (OSError, ValueError, EvidenceError) as error:
        receipt["error"] = str(error)
    finally:
        _write(root / "sdvk009-physical-campaign.json", receipt)
    require(receipt["status"] == "COLLECTED_PENDING_SDVK009_DECISION",
            "SDVK-009 physical campaign failed; retain the packet and do not continue timing/acceptance")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--expected-commit", default=EXPECTED_RENDERER_COMMIT,
                        help="preregistered renderer commit; default is the accepted SDVK-009 baseline")
    parser.add_argument("--execute", action="store_true", help="explicitly authorize the preregistered physical launches")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_commit):
        parser.error("--expected-commit must be a complete lowercase Git SHA")
    try:
        result = campaign(args)
    except (OSError, ValueError, EvidenceError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "physical_gpu_evidence_collected": result["physical_gpu_evidence_collected"],
                      "physical_gpu_qualified": result["physical_gpu_qualified"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
