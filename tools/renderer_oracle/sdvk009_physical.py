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


def _write(path: Path, value) -> None:
    path.write_bytes(canonical(value))


def _capture_args(args, prepared: Path, out: Path, scene: str, mode: str, *, extent=None):
    return argparse.Namespace(
        exe=args.exe, iwad=args.iwad, prepared=prepared, out=out, scene=scene, mode=mode,
        frames=1 if mode == "state" else 120, warmup=120, timeout=args.timeout,
        gpu=mode == "timing", include_stress=True, image_policy="exact", extent=extent,
    )


def _physical_build(build) -> None:
    vulkan = build.get("vulkan", {})
    require(vulkan.get("available") is True, "SDVK-009 physical campaign requires an identified Vulkan device")
    require(vulkan.get("device_type") in (1, 2),
            "SDVK-009 physical campaign requires an integrated or discrete physical Vulkan GPU")


def _same_build(reference, candidate) -> None:
    require(run.comparable_build(reference) == run.comparable_build(candidate),
            "SDVK-009 campaign build/device identity changed between processes")


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
    }
    reference_build = None
    try:
        prepared_result = prepare.prepare(prepared, list(REFERENCE_SCENES))
        receipt["prepared"] = prepared_result
        receipt["steps"].append({"name": "prepare", "status": "PASS"})

        for scene in REFERENCE_SCENES:
            paths = []
            for attempt in (1, 2):
                path = root / "reference-state" / scene / str(attempt)
                result = run.capture(_capture_args(args, prepared, path, scene, "state"))
                _physical_build(result["build"])
                if reference_build is None:
                    reference_build = result["build"]
                else:
                    _same_build(reference_build, result["build"])
                paths.append(path)
                receipt["steps"].append({"name": f"reference-{scene}-state-{attempt}", "status": "PASS"})
            comparison = run.compare_runs(paths[0], paths[1])
            require(comparison["status"] == "PASS", f"Reference state/image comparison failed: {scene}")
            _write(root / f"reference-{scene}-comparison.json", comparison)
            receipt["steps"].append({"name": f"reference-{scene}-compare", "status": "PASS"})

        for scene in HIGHRES_STATE_SCENES:
            paths = []
            for attempt in (1, 2):
                path = root / "highres-state" / scene / str(attempt)
                result = run.capture(_capture_args(args, prepared, path, scene, "state", extent=ARCHITECTURE_EXTENT))
                _physical_build(result["build"])
                _same_build(reference_build, result["build"])
                paths.append(path)
                receipt["steps"].append({"name": f"highres-{scene}-state-{attempt}", "status": "PASS"})
            comparison = run.compare_runs(paths[0], paths[1])
            require(comparison["status"] == "PASS", f"High-resolution state/image comparison failed: {scene}")
            _write(root / f"highres-{scene}-comparison.json", comparison)
            receipt["steps"].append({"name": f"highres-{scene}-compare", "status": "PASS"})

        timing_paths = {scene: [] for scene in TIMING_SCENES}
        for repetition, order in enumerate(TIMING_ORDER, 1):
            for ordinal, scene in enumerate(order, 1):
                path = root / "timing" / f"rep-{repetition}" / f"{ordinal:02d}-{scene}"
                result = run.capture(_capture_args(args, prepared, path, scene, "timing", extent=ARCHITECTURE_EXTENT))
                _physical_build(result["build"])
                _same_build(reference_build, result["build"])
                timing_paths[scene].append(path)
                receipt["steps"].append({"name": f"timing-r{repetition}-{scene}", "status": "PASS"})

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
    parser.add_argument("--execute", action="store_true", help="explicitly authorize the preregistered physical launches")
    args = parser.parse_args(argv)
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
