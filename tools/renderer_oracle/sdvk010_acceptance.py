#!/usr/bin/env python3
"""Combined SDVK-010 correctness gate within the normal software-Vulkan CI job.

Four fresh native processes (two per scene), exact RGB/state comparisons,
fail-stop dependencies, 240 warmup + 1 retained frame and 600 seconds/process.
Never retries. No physical GPU or performance acceptance is implied.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess

try:
    from . import native_ci, prepare, run, sdvk009_publication, sdvk010_sun_native
    from . import sdvk010_sun_occlusion as sun
    from .common import EvidenceError, pin, read_json, require, write_json
except ImportError:
    import native_ci, prepare, run, sdvk009_publication, sdvk010_sun_native
    import sdvk010_sun_occlusion as sun
    from common import EvidenceError, pin, read_json, require, write_json

SCENES = ("sun-actor-occlusion", "portal-probes")
WARMUP_FRAMES = 240
RETAINED_FRAMES = 1
DEADLINE_SECONDS = 600


def captured_negatives(capture_root, scene):
    """Falsify the real retained emitted-draw evidence, not just a toy fixture."""
    root = Path(capture_root)
    raw = read_json(root / "native.renderer.json")
    require(raw.get("mode") == "state" and raw.get("requested_frames") == RETAINED_FRAMES,
            "Negative controls require the complete state capture")
    spec = scene["native"]["state_assertions"]
    records = [r for r in raw["records"] if r["frame"] == 1]
    if scene["id"] == "sun-actor-occlusion":
        contract = spec["actor_sun_occlusion"]
        check = lambda rows: sun.validate_emitted_frame(rows, contract)
        targets = [i for i, r in enumerate(records) if r["kind"] == "probe"
                   and r["data"].get("actor_sunlight", {}).get("actor_tid") == contract["occluded_tid"]]
        edits = (
            ("missing-sun-world-trace", ("actor_sunlight", "traced_sun_count"), 0),
            ("wrong-authored-probe", ("actor_selection", "authored_index"), -1),
            ("missing-prefilter-pair", ("resource", "span"), 1),
        )
    else:
        contract = spec["actor_probe_portal"]
        check = lambda rows: run._portal_actor_probe_assertions(rows, contract)
        on = next(s for s in contract["samples"] if s["role"] == "on")
        targets = [i for i, r in enumerate(records) if r["kind"] == "probe"
                   and r["data"].get("actor_selection", {}).get("actor_tid") == on["actor_tid"]]
        edits = (
            ("cross-group-nearest-substitution", ("actor_selection", "policy"), "spatial-nearest"),
            ("double-portal-context-displacement", ("context", "position"),
             [on["context_position"][0] + 1024, *on["context_position"][1:]]),
            ("missing-required-runtime-pair", ("runtime_irradiance_index",), 0),
        )
    check(records)
    require(targets, "No actual emitted actor for captured negative controls")
    controls = []
    for name, path, value in edits:
        changed = copy.deepcopy(records)
        for i in targets:
            data = changed[i]["data"]
            for key in path[:-1]:
                data = data[key]
            data[path[-1]] = value
        try:
            check(changed)
        except EvidenceError as error:
            controls.append({"name": name, "status": "REJECTED", "reason": str(error)})
        else:
            raise EvidenceError("Captured negative was incorrectly accepted: " + name)
    changed = [row for i, row in enumerate(records) if i not in targets]
    try:
        check(changed)
    except EvidenceError as error:
        controls.append({"name": "missing-required-actor", "status": "REJECTED", "reason": str(error)})
    else:
        raise EvidenceError("Captured negative accepted the missing required actor")
    return {"schema": "sdvk010-captured-negatives/v1", "status": "PASS", "scene": scene["id"],
            "source": pin(root / "native.renderer.json"), "native_execution": False, "controls": controls}


def qualify(args):
    out = run.fresh_directory(args.out)
    steps = []
    result = {"schema": "sdvk010-combined-acceptance/v1", "status": "FAIL", "started_utc": run.utc(),
              "expected_commit": args.expected_commit, "scenes": list(SCENES),
              "warmup_frames": WARMUP_FRAMES, "retained_frames": RETAINED_FRAMES,
              "timeout_seconds": DEADLINE_SECONDS, "automatic_retries": 0,
              "physical_stop_active": True, "physical_gpu_qualified": False,
              "performance_accepted": False, "steps": steps}
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None,
                "An exact expected build commit is required")
        require(not any(k.startswith("CFX_") and v for k, v in os.environ.items()),
                "Combined actor correctness must not inherit CFX experiment controls")
        result["software_host"] = sdvk010_sun_native.software_host_guard()
        require(pin(args.iwad)["sha256"] == sdvk009_publication.IWAD_SHA256,
                "Combined actor acceptance requires the historical authenticated Freedoom IWAD")
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out / "prepared"
        manifest = prepare.prepare(prepared, list(SCENES))
        scenes = {scene["id"]: scene for scene in manifest["scenes"]}
        for name in SCENES:
            paths = [out / "state" / name / str(i) for i in (1, 2)]
            for i, path in enumerate(paths, 1):
                capture_args = argparse.Namespace(
                    exe=args.exe, iwad=args.iwad, prepared=prepared, out=path, scene=name,
                    mode="state", frames=RETAINED_FRAMES, warmup=WARMUP_FRAMES,
                    timeout=DEADLINE_SECONDS, gpu=False, include_stress=True,
                    image_policy="exact", extent=None, collision_snapshot=False,
                    publication_witness=False, expected_commit=args.expected_commit, require_clean=True)
                steps.append(native_ci.attempt(out, name + "-state-" + str(i),
                    lambda a=capture_args: run.capture(a), ("COLLECTED",)))
                require(steps[-1]["status"] == "PASS", "Combined actor capture failed; dependent work stopped")
                steps.append(native_ci.attempt(out, name + "-negatives-" + str(i),
                    lambda p=path, s=scenes[name]: captured_negatives(p, s)))
                require(steps[-1]["status"] == "PASS", "Captured actor negative controls failed")
            steps.append(native_ci.attempt(out, name + "-compare", lambda p=paths: run.compare_runs(*p)))
            require(steps[-1]["status"] == "PASS", "Combined actor state/RGB repeatability failed")
        result["status"] = "PASS"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "iwad-license", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    result = qualify(args)
    print(json.dumps({k: result.get(k) for k in ("schema", "status", "error")}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
