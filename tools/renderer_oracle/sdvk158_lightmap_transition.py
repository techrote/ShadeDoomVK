#!/usr/bin/env python3
"""SDVK-158 retained multi-page lightmap transition qualification.

Hosted isolated software Vulkan only. A fixed outcome-blind input scheduler
invalidates, reloads the same retained-v5 map, and invalidates again. Passive
resource records prove current atlas/page ownership, accepted retained tiles,
real completed tile updates, dirty-state convergence, and level-reload epochs.
This is correctness evidence, not physical GPU performance qualification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from tools.renderer_oracle.common import pin, require, write_json

SCENE = "lightmap-retained-transition"
MAP = "SDV158"
WARMUP = 32
FRAMES = 120
DEADLINE = 600
SCHEDULE = [
    {"after_main_views": 56, "phase": "invalidate-1", "command": "invalidatelightmap"},
    {"after_main_views": 88, "phase": "reload", "command": "map SDV158"},
    {"after_main_views": 120, "phase": "invalidate-2", "command": "invalidatelightmap"},
]


def validate_recipe(scene: dict) -> None:
    native = scene["native"]
    require(scene["id"] == SCENE and native.get("generator") == "lightmap_transition"
            and native.get("map") == MAP, "Unknown SDVK-158 lightmap transition recipe")
    require(native.get("lightmap_transition_schedule") == SCHEDULE,
            "Lightmap transition schedule differs from preregistration")
    require(native.get("recommended_warmup_frames") == WARMUP,
            "Lightmap transition warmup differs")
    require(native["settings"].get("gl_levelmesh") is True,
            "Lightmap transition requires the LevelMesh path")
    require(native["settings"].get("lm_dynlights") is False,
            "Lightmap transition fixture must not substitute dynamic-lightmap mode")


def _resource_rows(raw: dict) -> dict[int, dict]:
    rows = {}
    for record in raw["records"]:
        if record.get("kind") != "resource":
            continue
        frame = record["frame"]
        require(frame not in rows, "Duplicate SDVK-158 resource record for one retained frame")
        rows[frame] = record["data"]
    require(set(rows) == set(range(1, FRAMES + 1)),
            "SDVK-158 requires one resource snapshot for every retained frame")
    return rows


def _phase(rows: dict[int, dict], first: int, last: int) -> list[dict]:
    return [rows[frame] for frame in range(first, last + 1)]


def _lightmap(row: dict) -> dict:
    state = row.get("lightmap_state", {})
    require(state.get("available") is True, "SDVK-158 lightmap lifecycle state unavailable")
    require(state.get("map") == MAP, "SDVK-158 observed an unexpected map owner")
    require(type(state.get("texture_count")) is int and state["texture_count"] >= 2,
            "SDVK-158 fixture did not reach a multi-page CPU atlas")
    require(state.get("vulkan_page_count") == state["texture_count"]
            and state.get("page_count_match") is True,
            "CPU and Vulkan lightmap page populations diverged")
    require(state.get("invalid_live_tiles") == 0
            and state.get("sampling_page_bounds_ok") is True
            and state.get("valid_live_tiles") == state.get("live_tiles"),
            "Current live lightmap tile/page identity is invalid")
    pages = state.get("page_live_tiles")
    require(isinstance(pages, list) and len(pages) == state["texture_count"]
            and sum(1 for count in pages if type(count) is int and count > 0) >= 2
            and sum(pages) == state["valid_live_tiles"],
            "Live lightmap tiles do not occupy at least two current atlas pages")
    require(state.get("retained_tiles_loaded") == 2,
            "Version-5 retained floor/ceiling provenance was not accepted")
    return state


def _require_completed_cycle(rows: list[dict], name: str, *, minimum_updates: int = 1) -> dict:
    states = [_lightmap(row) for row in rows]
    updates = sum(state.get("frame_tile_updates", 0) for state in states)
    require(updates >= minimum_updates, name + " did not complete real lightmap tile work")
    require(states[-1].get("all_clean") is True
            and states[-1].get("initial_dirty") == 0
            and states[-1].get("geometry_dirty") == 0
            and states[-1].get("light_dirty") == 0,
            name + " did not converge all dirty/completion state")
    return {"frames": len(states), "completed_tile_updates": updates,
            "final_pages": states[-1]["texture_count"],
            "final_page_live_tiles": states[-1]["page_live_tiles"]}


def validate_transition_records(raw: dict, stdout: str, native: dict) -> dict:
    require(raw.get("observed_frames") == FRAMES,
            "SDVK-158 retained frame budget differs")
    expected = [f"SDVK158_LIGHTMAP_INPUT phase={phase['phase']} after_main_views={phase['after_main_views']}"
                for phase in SCHEDULE]
    actual = [line for line in stdout.splitlines() if line.startswith("SDVK158_LIGHTMAP_INPUT")]
    require(actual == expected, "SDVK-158 input driver order/count differs from preregistration")

    rows = _resource_rows(raw)
    for row in rows.values():
        _lightmap(row)

    initial = _phase(rows, 1, 24)
    require(_lightmap(initial[-1]).get("all_clean") is True,
            "Initial retained load did not stabilize before the first invalidation")

    before_reload_epoch = rows[56].get("lightmap_epoch")
    invalidate1 = _require_completed_cycle(_phase(rows, 25, 56), "first invalidation")
    reload = _require_completed_cycle(_phase(rows, 57, 88), "same-map retained reload")
    reload_epochs = {row.get("lightmap_epoch") for row in _phase(rows, 57, 88)}
    require(type(before_reload_epoch) is int and all(type(value) is int for value in reload_epochs)
            and any(value != before_reload_epoch for value in reload_epochs),
            "Same-map reload did not replace the Vulkan lightmap resource epoch")
    invalidate2 = _require_completed_cycle(_phase(rows, 89, 120), "second invalidation")

    final = _lightmap(rows[FRAMES])
    return {
        "status": "PASS",
        "frames": FRAMES,
        "minimum_pages": min(_lightmap(row)["texture_count"] for row in rows.values()),
        "retained_tiles_loaded": final["retained_tiles_loaded"],
        "cycles": {"invalidate_1": invalidate1, "reload": reload, "invalidate_2": invalidate2},
        "final_all_clean": final["all_clean"],
        "scope": "hosted emitted resource/lifecycle state and final image; no per-texel GPU readback",
        "physical_gpu_qualified": False,
    }


def qualify(args) -> dict:
    from tools.renderer_oracle import native_ci, prepare, run, sdvk010_sun_native
    out = run.fresh_directory(args.out)
    result = {
        "schema": "sdvk158-lightmap-transition-qualification/v1", "status": "FAIL", "steps": [],
        "physical_stop_active": True, "physical_gpu_qualified": False, "performance_accepted": False,
        "historical_physical_root_cause": "UNDETERMINED", "automatic_retries": 0,
    }
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None,
                "Expected exact build commit required")
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()),
                "No CFX experiments in this gate")
        result["software_host"] = sdvk010_sun_native.software_host_guard()
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out / "prepared"
        manifest = prepare.prepare(prepared, [SCENE])
        captures = []
        for name in ("transition-1", "transition-2"):
            target = out / name
            options = argparse.Namespace(
                exe=args.exe, iwad=args.iwad, prepared=prepared, out=target, scene=SCENE,
                mode="state", frames=FRAMES, warmup=WARMUP, timeout=DEADLINE, gpu=False,
                include_stress=True, image_policy="exact", extent=None, collision_snapshot=False,
                publication_witness=False, expected_commit=args.expected_commit, require_clean=True)
            step = native_ci.attempt(out, name, lambda a=options: run.capture(a), ("COLLECTED",))
            result["steps"].append(step)
            require(step["status"] == "PASS",
                    "Native lightmap transition attempt failed; no retry/dependent run")
            captures.append(target)

        comparison = run.compare_runs(captures[0], captures[1])
        write_json(out / "repeatability.json", comparison)
        require(comparison["status"] == "PASS",
                "SDVK-158 repeated transition state/RGB is not exact-repeatable")
        result.update(
            status="PASS",
            captures=[pin(path / "run.json", relative_to=out) for path in captures],
            comparison=pin(out / "repeatability.json", relative_to=out),
            prepared_scene=manifest["scenes"][0]["id"],
        )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        write_json(out / "qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("exe", "iwad", "iwad-license", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    result = qualify(parser.parse_args(argv))
    print(json.dumps({key: result.get(key) for key in ("schema", "status", "error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
