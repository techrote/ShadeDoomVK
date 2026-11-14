#!/usr/bin/env python3
"""TEMPORARY NONQUALIFYING SDVK-161 draw-identity investigation.

Eight preregistered, independent complete 32+96 native captures. No retries,
no correctness acceptance, no adjustment to original fixture or comparison.
The alternate frame-4/37 detail selection exists ONLY on this diagnostic branch.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import traceback

from tools.renderer_oracle import prepare, run, sdvk161_special_surfaces as ss
from tools.renderer_oracle.common import write_json


ROOT = Path("build/sdvk161-frame37-diagnostic")
FRAMES = (4, 37)
COUNT = 8  # Fixed upfront: four pairs, never retry a failed attempt.


def frame_records(raw, frame):
    return [r for r in raw.get("records", []) if r.get("frame") == frame]


def draw_key(record):
    data = record.get("data", {})
    # Native emitted record bytes. Keep exact values, including diagnostics,
    # instead of inventing a new semantic normalization.
    return json.dumps({"kind": record.get("kind"), "data": data},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def reduce_record(record):
    data = record.get("data", {})
    return {"kind": record.get("kind"),
            "class": data.get("class"),
            "count": data.get("count"),
            "vertex_count": data.get("vertex_count"),
            "index_count": data.get("index_count"),
            "draw": data.get("draw"),
            "key": data.get("key"),
            "context": data.get("context"),
            "surface": data.get("surface"),
            "material": data.get("material"),
            "light": data.get("light"),
            "source": data.get("source"),
            "side": data.get("side"),
            "sector": data.get("sector")}


def inspect(path):
    raw = json.loads((path / "native.renderer.json").read_text())
    result = {"path": str(path), "observed_frames": raw.get("observed_frames"),
              "record_count": len(raw.get("records", [])),
              "frames": {}}
    for f in FRAMES:
        records = frame_records(raw, f)
        kinds = Counter(r.get("kind") for r in records)
        counter = next((r.get("data", {}) for r in records if r.get("kind") == "frame"), {})
        result["frames"][str(f)] = {
            "kinds": dict(sorted(kinds.items())),
            "frame_counters": {k: counter.get(k) for k in (
                "walls", "flats", "sprites", "decals", "portals", "vertices",
                "light_wall_considered", "light_wall_rendered")},
            "records": records,
        }
    return result


def compare(a, b, frame):
    aa = a["frames"][str(frame)]
    bb = b["frames"][str(frame)]
    left = aa["records"]
    right = bb["records"]
    diff = {}
    for kind in sorted(set(x.get("kind") for x in left + right)):
        la = Counter(draw_key(x) for x in left if x.get("kind") == kind)
        rb = Counter(draw_key(x) for x in right if x.get("kind") == kind)
        missing = list((la - rb).elements())
        added = list((rb - la).elements())
        if missing or added:
            diff[kind] = {
                "left_only_count": len(missing), "right_only_count": len(added),
                "left_only": [reduce_record(json.loads(v)) for v in missing[:30]],
                "right_only": [reduce_record(json.loads(v)) for v in added[:30]],
                "samples_sha": [str(len(v)) for v in (missing, added)],
            }
    return {"frame": frame,
            "counters_left": aa["frame_counters"], "counters_right": bb["frame_counters"],
            "kinds_left": aa["kinds"], "kinds_right": bb["kinds"],
            "differing_kinds": diff}


def main():
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert len(expected) == 40
    ROOT.mkdir(parents=True, exist_ok=False)
    prepared = ROOT / "prepared"
    manifest = prepare.prepare(prepared, [ss.SCENE])
    report = {"schema": "sdvk161-frame37-diagnostic/v1",
              "qualification_awarded": False,
              "source": expected,
              "planned_independent_native_processes": COUNT,
              "automatic_retries": 0,
              "frames_extra_observed": list(FRAMES),
              "original_warmup": ss.WARMUP, "original_frames": ss.FRAMES,
              "source_scene": manifest["scenes"][0]["id"],
              "attempts": [], "pair_comparisons": []}
    seen = []
    for i in range(1, COUNT + 1):
        path = ROOT / ("attempt-%02d" % i)
        opts = argparse.Namespace(exe=Path("build/vkdoom"), iwad=Path("/usr/share/games/doom/freedoom2.wad"),
            prepared=prepared, out=path, scene=ss.SCENE, mode="state",
            frames=ss.FRAMES, warmup=ss.WARMUP, timeout=ss.DEADLINE, gpu=False,
            include_stress=True, image_policy="exact", extent=None,
            collision_snapshot=False, publication_witness=False,
            expected_commit=expected, require_clean=True)
        entry = {"ordinal": i, "path": str(path), "started": datetime.now(timezone.utc).isoformat()}
        try:
            receipt = run.capture(opts)
            entry["capture_status"] = receipt.get("status")
            if (path / "native.renderer.json").exists():
                summary = inspect(path)
                seen.append(summary)
                entry["observation"] = summary
                # Do not dump full raw records into the job log.
                for f in FRAMES:
                    x = summary["frames"][str(f)]
                    print("FRAME", i, f, "COUNTERS", json.dumps(x["frame_counters"], sort_keys=True),
                          "KINDS", json.dumps(x["kinds"], sort_keys=True), flush=True)
        except Exception as exc:
            entry["error"] = repr(exc)
            entry["traceback"] = traceback.format_exc()
            print("CAPTURE_EXCEPTION", i, entry["error"], flush=True)
        entry["finished"] = datetime.now(timezone.utc).isoformat()
        # Each independently authorised attempt is recorded once, even on failure.
        report["attempts"].append({k: v for k, v in entry.items() if k != "observation"})
        write_json(ROOT / "report.json", report)
    for i in range(0, len(seen) - 1, 2):
        pair = {"pair": [seen[i]["path"], seen[i + 1]["path"]],
                "frames": [compare(seen[i], seen[i + 1], frame) for frame in FRAMES]}
        report["pair_comparisons"].append(pair)
        for comparison in pair["frames"]:
            print("PAIR", pair["pair"], "FRAME", comparison["frame"],
                  "DIFFERING_KINDS",
                  json.dumps({k: [v["left_only_count"], v["right_only_count"]]
                              for k, v in comparison["differing_kinds"].items()},
                             sort_keys=True), flush=True)
            if comparison["counters_left"] != comparison["counters_right"]:
                print("COUNTER_MISMATCH",
                      json.dumps({"pair": pair["pair"], "frame": comparison["frame"],
                                  "a": comparison["counters_left"],
                                  "b": comparison["counters_right"],
                                  "differing": comparison["differing_kinds"]}, sort_keys=True)[:14000], flush=True)
    write_json(ROOT / "report.json", report)
    print("NONQUALIFYING_DIAGNOSTIC_COMPLETE", expected,
          "planned", COUNT, "captured", len(seen),
          "pairs", len(report["pair_comparisons"]), flush=True)


if __name__ == "__main__":
    main()
