#!/usr/bin/env python3
"""Small, source-matched Lane A capture set; never awards legacy campaign acceptance.

Keeps the existing native validator and authored recipes. Only orchestration is
new: one capture per scene, no timing campaign or cross-process counter equality.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.renderer_oracle import images, native_ci, prepare, run
from tools.renderer_oracle.common import pin, require, write_json
from tools.renderer_oracle.gameplay_smoke import FRAMES, WARMUP
from tools.renderer_oracle.sdvk010_sun_native import software_host_guard

SCENES = ("compositing", "lights-zero", "lights-one", "gameplay-smoke")
EXTRA_SCENES = ("sprite-mirror", "material-stress", "sun-probes", "shadow-boundary")


def light_response(off, on):
    """A coarse missing-effect detector, deliberately not a beauty score."""
    require(len(off) == len(on) and len(off) >= 64 * 3 and len(off) % 3 == 0,
            "Lighting control RGB extent mismatch")
    changed = sum(max(abs(off[p+i] - on[p+i]) for i in range(3)) >= 4
                  for p in range(0, len(off), 3))
    require(changed >= 64, "One-light fixture has no substantive OFF/ON image effect")
    return {"status": "PASS", "pixels_with_channel_delta_at_least_4": changed,
            "minimum_pixels": 64,
            "scope": "missing-effect detector; not perceptual/beauty or exact-RGB acceptance"}


def qualify(args):
    require(re.fullmatch(r"[a-f0-9]{40}", args.expected_commit) is not None,
            "An exact source commit is required")
    out = run.fresh_directory(args.out)
    scenes = list(dict.fromkeys(SCENES + tuple(args.extra_scene)))
    result = {"schema": "sdvk-r001-routine-native/v1", "status": "FAIL",
              "started_utc": run.utc(), "expected_commit": args.expected_commit,
              "scenes": scenes, "automatic_retries": 0, "captures": [],
              "physical_stop_active": True, "legacy_campaign_accepted": False,
              "scope": "hosted software correctness/images and ordinary gameplay only"}
    try:
        result["host"] = software_host_guard()
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out / "prepared"
        prepare.prepare(prepared, scenes)
        for scene in scenes:
            destination = out / scene
            captured = run.capture(argparse.Namespace(
                exe=args.exe, iwad=args.iwad, prepared=prepared, out=destination,
                scene=scene, mode="state", frames=FRAMES if scene == "gameplay-smoke" else 1,
                warmup=WARMUP if scene == "gameplay-smoke" else None,
                timeout=600, gpu=False, include_stress=True, image_policy="exact",
                expected_commit=args.expected_commit, require_clean=True,
                extent=None, collision_snapshot=scene == "shadow-boundary"))
            require(captured["status"] == "COLLECTED", "Native capture failed: " + scene)
            # capture's normal admission validates native source/backend,
            # resource invariants, expected materials/camera/draws and gameplay.
            # Retained files remain available for review, without retroactively
            # claiming the original two-process legacy scene contract passed.
            result["captures"].append(pin(destination / "run.json", relative_to=out))
        off_extent, off = images.decode(out / "lights-zero" / "native.png")
        on_extent, on = images.decode(out / "lights-one" / "native.png")
        require(off_extent == on_extent == (640, 480), "Lighting fixture extent differs")
        result["off_on"] = light_response(off, on)
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "routine-native.json", result)
    print(json.dumps({key: result.get(key) for key in ("status", "scenes", "error")}))
    return 0 if result["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--iwad-license", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--extra-scene", action="append", choices=EXTRA_SCENES, default=[])
    return qualify(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
