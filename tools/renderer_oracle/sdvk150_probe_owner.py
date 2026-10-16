#!/usr/bin/env python3
"""SDVK-150 same-process probe-owner qualification.

CPU helpers validate retained lifecycle records. The CLI runs two independent
same-process A->B captures only on the approved Avrea 16-vCPU llvmpipe lane.
Hosted timing/performance is not accepted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

try:
    from . import native_ci, prepare, run, sdvk010_sun_native
    from .common import pin, require, write_json
except ImportError:
    from tools.renderer_oracle import native_ci, prepare, run, sdvk010_sun_native
    from tools.renderer_oracle.common import pin, require, write_json

SCENE = "probe-owner-transition"
WARMUP_FRAMES = 100
RETAINED_FRAMES = 1
DEADLINE_SECONDS = 300


def validate_lifecycle_records(records: list[dict], spec: dict) -> dict:
    rows = [record for record in records if record.get("kind") == "probe-builder"]
    require(len(rows) == 1 and rows[0].get("count") == 1,
            "Probe-owner transition requires exactly one retained lifecycle record")
    data = rows[0].get("data", {})
    require(data.get("scope") == "actual incremental builder reset/publication callbacks across observer warmup",
            "Unknown probe-owner lifecycle scope")
    events = data.get("events")
    require(isinstance(events, list) and events,
            "Probe-owner transition has no actual builder lifecycle events")

    owners = spec.get("owners")
    passes_required = spec.get("passes_per_owner")
    require(isinstance(owners, list) and len(owners) == 2 and passes_required == 5,
            "Probe-owner transition assertion recipe is malformed")

    # Inspect every event before selecting per-owner rows. Filtering by both
    # map and count first would hide a wrong-count reset from this same-count
    # fixture. A plausible publication must also be a completed producer state,
    # not merely an event name with a matching epoch.
    require(len(events) <= 64, "Probe-owner lifecycle event bound exceeded")
    require(all(isinstance(owner, dict) for owner in owners),
            "Probe-owner assertion owner is malformed")
    owner_names = [owner.get("map") for owner in owners]
    require(all(isinstance(name, str) and name for name in owner_names)
            and len(set(owner_names)) == 2,
            "Probe-owner assertion maps must be distinct")
    for event in events:
        require(isinstance(event, dict), "Malformed probe-owner lifecycle event")
        require(event.get("map") in owner_names,
                "Probe-owner lifecycle event belongs to an undeclared map")
        require(type(event.get("authored_count")) is int and event["authored_count"] == 2,
                "Probe-owner lifecycle event has wrong authored count")
        kind = event.get("event")
        require(kind in ("owner-reset", "pass-published"),
                "Probe-owner lifecycle event is not a declared reset/publication")
        for field in ("iteration", "next_index", "collected"):
            require(type(event.get(field)) is int and event[field] >= 0,
                    "Probe-owner lifecycle progress is not a nonnegative integer")
        if kind == "owner-reset":
            require(event["iteration"] == event["next_index"] == event["collected"] == 0,
                    "Probe-owner reset retained old progress")
        else:
            require(1 <= event["iteration"] <= passes_required
                    and event["next_index"] == event["authored_count"]
                    and event["collected"] == 0,
                    "Probe-owner publication is not completed producer state")

    summaries = []
    cursor = -1
    for owner in owners:
        map_name = owner.get("map")
        authored = owner.get("authored_count")
        require(isinstance(map_name, str) and map_name and authored == 2,
                "Probe-owner assertion owner/count is malformed")

        relevant = [(index, event) for index, event in enumerate(events)
                    if event.get("map") == map_name and event.get("authored_count") == authored]
        resets = [(index, event) for index, event in relevant if event.get("event") == "owner-reset"]
        count_resets = [(index, event) for index, event in relevant if event.get("event") == "count-reset"]
        publications = [(index, event) for index, event in relevant if event.get("event") == "pass-published"]

        require(len(resets) == 1, "Each same-count map owner must cause exactly one semantic owner reset")
        require(not count_resets, "Equal-count owner transition incorrectly relied on count-reset fallback")
        require(len(publications) == passes_required,
                "Each probe owner must publish exactly five completed passes")

        reset_index, reset = resets[0]
        require(reset_index > cursor, "Probe owner resets are not ordered A then B")
        require([event.get("iteration") for _, event in publications] == list(range(1, passes_required + 1)),
                "Probe owner publication iterations are incomplete or reordered")
        require(all(index > reset_index for index, _ in publications),
                "Probe pass publication occurred before semantic owner reset")
        require(all(index > cursor for index, _ in publications),
                "Probe publication crossed an earlier owner boundary")

        revision = reset.get("owner_revision")
        epoch = reset.get("light_probe_epoch")
        require(type(revision) is int and revision > 0 and type(epoch) is int and epoch > 0,
                "Probe owner reset lacks semantic revision/resource epoch")
        require(all(event.get("owner_revision") == revision for _, event in publications),
                "Probe pass publication mixed semantic owner revisions")
        require(all(event.get("light_probe_epoch") == epoch for _, event in publications),
                "Probe pair publication changed epoch within one owner")
        require(all(event.get("irradiance_count", 0) >= authored
                    and event.get("irradiance_count") == event.get("prefilter_count")
                    for _, event in publications),
                "Probe owner pass lacks a complete irradiance/prefilter family")

        cursor = publications[-1][0]
        summaries.append({
            "map": map_name,
            "owner_revision": revision,
            "light_probe_epoch": epoch,
            "passes": passes_required,
            "authored_count": authored,
        })

    require(summaries[0]["owner_revision"] != summaries[1]["owner_revision"],
            "Same-count maps reused the same semantic probe owner revision")
    require(summaries[1]["light_probe_epoch"] > summaries[0]["light_probe_epoch"],
            "New map probe resources were not reset to a later epoch")
    return {
        "status": "PASS",
        "owners": summaries,
        "same_count": True,
        "count_fallback_used": False,
        "actual_publication_callbacks": passes_required * len(summaries),
    }


def qualify(args) -> dict:
    out = run.fresh_directory(args.out)
    steps = []
    result = {
        "schema": "sdvk150-probe-owner-qualification/v1",
        "status": "FAIL",
        "started_utc": run.utc(),
        "expected_commit": args.expected_commit,
        "scene": SCENE,
        "warmup_frames": WARMUP_FRAMES,
        "retained_frames": RETAINED_FRAMES,
        "timeout_seconds": DEADLINE_SECONDS,
        "automatic_retries": 0,
        "physical_stop_active": True,
        "physical_gpu_qualified": False,
        "performance_accepted": False,
        "historical_physical_root_cause": "UNDETERMINED",
        "steps": steps,
    }
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None,
                "An exact expected build commit is required")
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()),
                "Probe-owner qualification must not inherit CFX experiment controls")
        result["software_host"] = sdvk010_sun_native.software_host_guard()
        result["preflight"] = native_ci.preflight(args, out)

        prepared = out / "prepared"
        manifest = prepare.prepare(prepared, [SCENE])
        scene = manifest["scenes"][0]
        spec = scene["native"]["state_assertions"]["probe_owner_transition"]

        captures = []
        for index in (1, 2):
            target = out / "state" / str(index)
            capture_args = argparse.Namespace(
                exe=args.exe, iwad=args.iwad, prepared=prepared, out=target, scene=SCENE,
                mode="state", frames=RETAINED_FRAMES, warmup=WARMUP_FRAMES,
                timeout=DEADLINE_SECONDS, gpu=False, include_stress=True,
                image_policy="exact", extent=None, collision_snapshot=False,
                publication_witness=False, expected_commit=args.expected_commit,
                require_clean=True)
            steps.append(native_ci.attempt(
                out, f"{SCENE}-state-{index}",
                lambda a=capture_args: run.capture(a), ("COLLECTED",)))
            require(steps[-1]["status"] == "PASS",
                    "Probe-owner native capture failed; dependent comparison stopped")
            raw = run.validate_run(target)[2]
            lifecycle = validate_lifecycle_records(raw["records"], spec)
            write_json(target / "probe-owner-lifecycle.json", lifecycle)
            captures.append(target)

        comparison = run.compare_runs(*captures)
        write_json(out / "comparison.json", comparison)
        require(comparison["status"] == "PASS" and comparison["state_equal"] is True
                and comparison["image"]["changed_pixels"] == 0,
                "Independent same-process A->B state/RGB captures were not exactly repeatable")

        result.update(
            status="PASS",
            native_captures=[pin(path / "run.json", relative_to=out) for path in captures],
            lifecycle=[pin(path / "probe-owner-lifecycle.json", relative_to=out) for path in captures],
            comparison=pin(out / "comparison.json", relative_to=out),
            qualification_scope=(
                "same-process same-count A->B semantic owner reset and five-pass "
                "irradiance/prefilter republication on software llvmpipe only"
            ),
        )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "qualification.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "iwad-license", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    result = qualify(args)
    print(json.dumps({key: result.get(key) for key in ("schema", "status", "error")}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
