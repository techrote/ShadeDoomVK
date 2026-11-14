#!/usr/bin/env python3
"""NONQUALIFYING passive wall-origin diagnosis of unmodified SDVK-161 lifecycle recipe.

The eight original 32+96 native processes are planned before execution. A
separate sidecar records primitive queued/drawn wall IDs and upload call indices.
The original native run validator, structural/semantic/negative controls and
strict state/RGB comparator remain unchanged. No retries; never acceptance.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import traceback

from tools.renderer_oracle import native_ci, prepare, run, sdvk161_special_surfaces as ss
from tools.renderer_oracle.common import canonical, pin, read_json, require, sha256, write_json

COUNT = 8
ROOT = Path("build/sdvk161-passive-wall")
TRACE_NAME = "native.walltrace.json"
STAGES = {1: "queued", 2: "draw-entry", 3: "after-setup", 4: "actually-drawn",
          5: "draw-exit", 6: "successful-light-upload"}


def stage_key(row):
    # Exclude only non-semantic recording order and mutable upload slot ordinal.
    # The complete native and sidecar records are retained without normalization.
    return json.dumps({k: v for k, v in row.items() if k not in ("seq", "light_index")},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def summaries(raw, trace):
    require(trace.get("schema") == "sdvk161-passive-wall-trace/v1"
            and trace.get("qualification") == "NONQUALIFYING"
            and trace.get("overflow") is False
            and type(trace.get("capacity")) is int
            and type(trace.get("retained")) is int
            and trace["retained"] <= trace["capacity"]
            and trace["total"] == trace["retained"] == len(trace.get("rows", [])),
            "Passive sidecar invalid, truncated or overflowed")
    by_frame = defaultdict(list)
    for row in trace["rows"]:
        require(type(row.get("frame")) is int and 1 <= row["frame"] <= ss.FRAMES
                and type(row.get("stage")) is int and row["stage"] in STAGES,
                "Passive trace contains an invalid frame/stage")
        by_frame[row["frame"]].append(row)
    original_frames = {r["frame"]: r["data"] for r in raw["records"] if r.get("kind") == "frame"}
    resources = {r["frame"]: r["data"] for r in raw["records"] if r.get("kind") == "resource"}
    require(set(by_frame) == set(original_frames) == set(resources) == set(range(1, ss.FRAMES + 1)),
            "Passive trace and original complete native frame census disagree")
    output = {}
    for frame in range(1, ss.FRAMES + 1):
        stage = Counter(row["stage"] for row in by_frame[frame])
        emitted = [r for r in by_frame[frame] if r["stage"] == 4]
        uploaded = [r for r in by_frame[frame] if r["stage"] == 6]
        accounted = sum(r["vertices"] for r in emitted)
        original = original_frames[frame]["vertices"]
        light = resources[frame]["light_uploads"]
        require(type(original) is int and original == accounted,
                f"Frame {frame}: summed real wall draw vertices disagree with protected native counter")
        require(light["attempts"] == light["successful"] == len(uploaded)
                and light["failed"] == 0
                and light["records_used"] == sum(r["normal"] + r["subtractive"] + r["additive"]
                                                   for r in uploaded),
                f"Frame {frame}: indexed actual upload calls disagree with native light ledger")
        require(stage[2] == stage[3] == stage[5],
                f"Frame {frame}: draw-entry/setup/exit stage calls disagree")
        output[str(frame)] = {
            "native_walls": original_frames[frame]["walls"],
            "native_vertices": original, "native_light_attempts": light["attempts"],
            "native_light_bytes": light["uploaded_bytes"],
            "stages": {STAGES[k]: stage[k] for k in STAGES},
            "emitted": len(emitted), "sum_emitted_vertices": accounted,
            "actual_empty_uploads": sum(r["normal"] + r["subtractive"] + r["additive"] == 0 for r in uploaded),
            "portal_queue_rows": sum(r["portal"] == 1 for r in by_frame[frame] if r["stage"] == 1),
        }
    return output


def compare_traces(left, right, frame):
    la = [r for r in left["rows"] if r["frame"] == frame]
    ra = [r for r in right["rows"] if r["frame"] == frame]
    differences = {}
    for stage in STAGES:
        x = Counter(stage_key(r) for r in la if r["stage"] == stage)
        y = Counter(stage_key(r) for r in ra if r["stage"] == stage)
        extra_l, extra_r = list((x - y).elements()), list((y - x).elements())
        if extra_l or extra_r:
            differences[STAGES[stage]] = {
                "left_only_count": len(extra_l), "right_only_count": len(extra_r),
                "left_only": [json.loads(v) for v in extra_l[:12]],
                "right_only": [json.loads(v) for v in extra_r[:12]],
            }
    return differences


def attempt(index, prepared, manifest, source, root):
    out = root / f"attempt-{index:02d}"
    args = argparse.Namespace(
        exe=Path("build/vkdoom"), iwad=Path("/usr/share/games/doom/freedoom2.wad"),
        prepared=prepared, out=out, scene=ss.SCENE, mode="state",
        frames=ss.FRAMES, warmup=ss.WARMUP, timeout=ss.DEADLINE,
        gpu=False, include_stress=True, image_policy="exact", extent=None,
        collision_snapshot=False, publication_witness=False,
        expected_commit=source, require_clean=True)
    entry = {"ordinal": index, "folder": str(out), "status": "FAIL",
             "started_utc": datetime.now(timezone.utc).isoformat()}
    trace = None
    try:
        run.capture(args)
        # Independent original gates, not a parallel proxy:
        native_root, _, raw, _ = run.validate_run(out)
        qualified = ss.validate_transition_records(
            raw, (native_root / "stdout.log").read_text(), manifest["scenes"][0]["native"])
        checkpoints = ss.validate_checkpoint_images(native_root, raw)
        negatives = ss.captured_negatives(
            raw, (native_root / "stdout.log").read_text(), manifest["scenes"][0]["native"])
        require(negatives["status"] == "PASS", "Original SDVK-161 negative controls failed")
        write_json(out / "original-negative-controls.json", negatives)
        write_json(out / "original-transition.json", qualified)
        write_json(out / "original-checkpoints.json", checkpoints)
        trace = read_json(out / TRACE_NAME)
        verified = summaries(raw, trace)
        write_json(out / "passive-frame-summary.json", verified)
        entry.update(status="ADMITTED_ORIGINAL_NATIVE_WITH_NONQUALIFYING_TRACE",
                     original_gate_pass=True,
                     raw=pin(out / "native.renderer.json", relative_to=out),
                     trace=pin(out / TRACE_NAME, relative_to=out),
                     frames=pin(out / "passive-frame-summary.json", relative_to=out),
                     originals={"negative_controls": pin(out / "original-negative-controls.json", relative_to=out),
                                "transition": pin(out / "original-transition.json", relative_to=out),
                                "checkpoints": pin(out / "original-checkpoints.json", relative_to=out)})
        print(f"ATTEMPT {index} ORIGINAL_GATE_PASS, trace_events={trace['retained']}", flush=True)
    except Exception as error:
        entry["error"] = repr(error)
        entry["traceback"] = traceback.format_exc(limit=8)
        print(f"ATTEMPT {index} REJECTED: {error!r}", flush=True)
        # A raw incomplete or rejected packet is useful only diagnostically.
        if (out / TRACE_NAME).is_file():
            trace = read_json(out / TRACE_NAME)
            entry["trace"] = pin(out / TRACE_NAME, relative_to=out)
        if (out / "native.renderer.json").is_file():
            entry["unadmitted_raw"] = pin(out / "native.renderer.json", relative_to=out)
    entry["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(root / f"attempt-{index:02d}-receipt.json", entry)
    return entry, trace


def main():
    root = run.fresh_directory(ROOT)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(len(source) == 40, "Full source commit required")
    prepared = root / "prepared"
    manifest = prepare.prepare(prepared, [ss.SCENE])
    report = {
        "schema": "sdvk161-passive-wall-forensics/v1", "status": "NONQUALIFYING",
        "source": source, "fixture": ss.SCENE,
        "planned_attempts": COUNT, "automatic_retries": 0,
        "original_frames": ss.FRAMES, "original_warmup": ss.WARMUP,
        "original_detailed_witness_frames": list(range(8, ss.FRAMES + 1, 8)),
        "policy": "Diagnostic env only; original native input and all native acceptance predicates unchanged",
        "attempts": [], "pair_comparisons": [],
    }
    traces = {}
    for i in range(1, COUNT + 1):
        receipt, trace = attempt(i, prepared, manifest, source, root)
        report["attempts"].append(receipt)
        if receipt["status"].startswith("ADMITTED_") and trace is not None:
            traces[i] = trace
    for i in range(1, COUNT, 2):
        row = {"pair": [i, i + 1], "status": "NOT_COMPARABLE"}
        if i in traces and i + 1 in traces:
            a = root / f"attempt-{i:02d}"
            b = root / f"attempt-{i+1:02d}"
            try:
                # This IS the unaltered original exact semantic/RGB comparator.
                cmp = run.compare_runs(a, b)
                row.update(status=cmp["status"], state_equal=cmp["state_equal"],
                           image=cmp["image"],
                           first_state_differences=cmp["first_state_differences"])
                write_json(root / f"pair-{i:02d}-{i+1:02d}-original-comparison.json", cmp)
                divergence = {}
                for f in range(1, ss.FRAMES + 1):
                    differences = compare_traces(traces[i], traces[i + 1], f)
                    if differences:
                        divergence[str(f)] = differences
                row["trace_differences"] = divergence
                print("PAIR", i, i + 1, cmp["status"], "state_equal", cmp["state_equal"],
                      "different_wall_trace_frames", sorted(divergence, key=int), flush=True)
                if not cmp["state_equal"]:
                    print("ORIGINAL_MISMATCH", json.dumps(cmp["first_state_differences"][:12]), flush=True)
            except Exception as error:
                row.update(status="REJECTED", error=repr(error))
        report["pair_comparisons"].append(row)
    write_json(root / "forensics.json", report)
    print("PASSIVE_NONQUALIFYING_FINISHED", "attempts", len(report["attempts"]),
          "admitted_original_native", len(traces), "pairs", len(report["pair_comparisons"]),
          "original_repeatability_failures",
          sum(p["status"] == "FAIL" for p in report["pair_comparisons"]), flush=True)


if __name__ == "__main__":
    main()
