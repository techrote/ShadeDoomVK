#!/usr/bin/env python3
"""NONQUALIFYING SDVK-161 startup texture-epoch lifecycle diagnosis.

Run exactly eight independent original 32+96 SDVK-161 captures, never retry.
Each process separately retains the production observation and an opt-in sidecar
which freezes at retained frame one. Preserve original lifecycle/negative/RGB
acceptance intact. This is diagnostics, NOT a publication acceptance workflow.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
import subprocess
import traceback

from tools.renderer_oracle import prepare, run, sdvk161_special_surfaces as ss
from tools.renderer_oracle.common import canonical, pin, read_json, require, sha256, write_json

COUNT = 8
ROOT = Path("build/sdvk161-texture-epoch-investigation")
TRACE_FILE = "native.texture-epoch.json"
ACTIONS = {"manager-create", "manager-deinit", "manager-destroy",
           "hw-add", "hw-remove", "pp-add", "pp-remove"}
INCREMENTS = {"hw-remove", "pp-remove", "manager-deinit"}
ELF_OFFSET = re.compile(r"\(\+0x([0-9a-fA-F]+)\)")


def utc():
    return datetime.now(timezone.utc).isoformat()


def symbolize(events, binary):
    """Decode image-relative PCs from GNU backtrace_symbols after native exit."""
    all_pc = set()
    for e in events:
        for pc in e.get("pc_offsets", []):
            if pc.get("module", "").startswith("vkdoom"):
                require(type(pc.get("offset")) is int and pc["offset"] >= 0,
                        "Invalid native module-relative call-site offset")
                all_pc.add("0x" + format(pc["offset"], "x"))
    if not all_pc:
        return {}
    pcs = sorted(all_pc, key=lambda x: int(x, 16))
    command = ["addr2line", "-C", "-f", "-p", "-e", str(binary.resolve()), *pcs]
    output = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    require(output.returncode == 0 and len(output.stdout.splitlines()) == len(pcs),
            "Cannot symbolize authored executable PCs for source-root attribution")
    return dict(zip(pcs, output.stdout.splitlines()))


def call_chain(row, resolved):
    mapped = []
    for pc in row.get("pc_offsets", []):
        if pc.get("module", "").startswith("vkdoom"):
            key = "0x" + format(pc["offset"], "x")
            mapped.append(resolved.get(key, key))
    return mapped or list(row.get("stack", []))


def validate_trace(trace, raw):
    """Fail closed on ungrounded epoch state, missing event, stale owner or truncation."""
    require(trace.get("schema") == "sdvk161-texture-epoch-startup/v1"
            and trace.get("status") == "NONQUALIFYING_DIAGNOSTIC"
            and trace.get("snapshot_frozen") is True
            and trace.get("overflow") is False
            and trace.get("default_off") is True,
            "Unknown, incomplete or overflowed startup lifetime trace")
    events = trace.get("events")
    require(isinstance(events, list) and 0 < len(events) <= 256
            and trace.get("recorded") == len(events)
            and trace.get("capacity") == 256,
            "Startup epoch trace has missing or unbounded events")
    managers = {}
    live = {}
    owners_ever_seen = set()
    for i, event in enumerate(events):
        require(event.get("ordinal") == i
                and event.get("event") in ACTIONS
                and type(event.get("manager_id")) is int
                and event["manager_id"] >= 1
                and type(event.get("before")) is int
                and type(event.get("after")) is int
                and type(event.get("presented_view_ordinal")) is int
                and 0 <= event["presented_view_ordinal"] <= 33
                and isinstance(event.get("stack"), list)
                and len(event["stack"]) >= 2
                and isinstance(event.get("pc_offsets"), list)
                and len(event["pc_offsets"]) >= 2,
                "Startup epoch trace has invalid event ownership/phase/callstack")
        kind = event["event"]
        manager = event["manager_id"]
        owner = event.get("owner_id")
        require(event["owner_kind"] ==
                ("hardware" if kind.startswith("hw-") else
                 "postprocess" if kind.startswith("pp-") else "manager"),
                "Owner class differs from original call kind")
        require(type(event.get("hardware_count")) is int
                and type(event.get("pp_count")) is int
                and event["hardware_count"] >= 0 and event["pp_count"] >= 0,
                "Invalid actual texture manager registration counts")
        if kind == "manager-create":
            require(manager not in managers and owner == -1
                    and event["before"] == event["after"] == 1,
                    "Texture manager was not created with epoch one")
            managers[manager] = 1
            live[manager] = {}
        else:
            require(manager in managers and managers[manager] == event["before"],
                    "Epoch chain is broken or a manager birth is missing")
            expect_after = (1 if event["before"] == 0xFFFFFFFF else event["before"] + 1) \
                if kind in INCREMENTS else event["before"]
            require(event["after"] == expect_after,
                    "Texture epoch changed without an authenticated invalidation or failed to advance")
            managers[manager] = event["after"]
        if kind in ("hw-add", "pp-add"):
            require(type(owner) is int and owner >= 1 and owner not in owners_ever_seen,
                    "Registration has reused or unidentified owner")
            owners_ever_seen.add(owner)
            live[manager][owner] = "hardware" if kind == "hw-add" else "postprocess"
        elif kind in ("hw-remove", "pp-remove"):
            require(type(owner) is int and owner in live[manager]
                    and live[manager][owner] == ("hardware" if kind == "hw-remove" else "postprocess"),
                    "Texture retirement is detached from its registered live owner")
        else:
            require(owner == -1, "Manager-level event unexpectedly claims a texture owner")
        # Registration counts are sampled just after Add, just after an
        # invalidating Remove but BEFORE unlink, and on Deinit entry.
        counts = Counter(live[manager].values())
        require(event["hardware_count"] == counts["hardware"]
                and event["pp_count"] == counts["postprocess"],
                "Actual manager counts disagree with the traced lifetime births/retirements")
        if kind in ("hw-remove", "pp-remove"):
            del live[manager][owner]
    first_id = trace.get("first_retained_manager_id")
    first_epoch = trace.get("first_retained_texture_epoch")
    require(type(first_id) is int and first_id in managers
            and type(first_epoch) is int and first_epoch == managers[first_id],
            "Actual first-retained texture epoch differs from recorded event chain")
    resource = [r for r in raw.get("records", [])
                if r.get("kind") == "resource" and r.get("frame") == 1]
    require(len(resource) == 1 and resource[0]["data"]["texture_epoch"] == first_epoch,
            "Original retained native texture epoch differs from sidecar snapshot")
    return {"events": len(events), "first_retained_texture_epoch": first_epoch,
            "active_manager": first_id,
            "increments": sum(e["event"] in INCREMENTS for e in events),
            "events_by_type": dict(sorted(Counter(e["event"] for e in events).items()))}


def event_signature(trace):
    return [{"event": e["event"], "before": e["before"], "after": e["after"],
             "manager": e["manager_id"], "owner": e["owner_id"],
             "hardware_count": e["hardware_count"], "pp_count": e["pp_count"],
             "observer_view": e["presented_view_ordinal"]}
            for e in trace["events"]]


def delta(left, right):
    l, r = event_signature(left), event_signature(right)
    # This is a source-event discriminator, NOT a repeatability normalization.
    a = [json.dumps({k:v for k,v in e.items() if k not in ("before","after","owner")},
                    sort_keys=True) for e in l]
    b = [json.dumps({k:v for k,v in e.items() if k not in ("before","after","owner")},
                    sort_keys=True) for e in r]
    diff = []
    for op, x1, x2, y1, y2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            diff.append({"change": op, "left": l[x1:x2], "right": r[y1:y2]})
    return diff


def attempt(i, prepared, manifest, source, root):
    out = root / ("attempt-%02d" % i)
    argv = argparse.Namespace(
        exe=Path("build/vkdoom"), iwad=Path("/usr/share/games/doom/freedoom2.wad"),
        prepared=prepared, out=out, scene=ss.SCENE, mode="state",
        frames=ss.FRAMES, warmup=ss.WARMUP, timeout=ss.DEADLINE,
        gpu=False, include_stress=True, image_policy="exact", extent=None,
        collision_snapshot=False, publication_witness=False,
        expected_commit=source, require_clean=True)
    entry = {"attempt": i, "status": "FAIL", "started": utc()}
    try:
        run.capture(argv)
        native_root, _, raw, _ = run.validate_run(out)
        stdout = (native_root / "stdout.log").read_text()
        # Existing independently admitted validation remains authoritative.
        transition = ss.validate_transition_records(raw, stdout, manifest["scenes"][0]["native"])
        checkpoints = ss.validate_checkpoint_images(native_root, raw)
        negatives = ss.captured_negatives(raw, stdout, manifest["scenes"][0]["native"])
        require(negatives["status"] == "PASS" and len(negatives["controls"]) == 35,
                "Original named SDVK-161 negative controls incomplete")
        trace = read_json(out / TRACE_FILE)
        census = validate_trace(trace, raw)
        paths = {
            "native": pin(out / "native.renderer.json", relative_to=out),
            "trace": pin(out / TRACE_FILE, relative_to=out),
            "stdout": pin(out / "stdout.log", relative_to=out)}
        write_json(out / "original-negative-controls.json", negatives)
        write_json(out / "original-transition.json", transition)
        write_json(out / "original-checkpoints.json", checkpoints)
        # Symbolization occurs strictly after source capture, never in renderer
        # or during live gameplay/image observation.
        pcs = symbolize(trace["events"], Path("build/vkdoom"))
        events = [{"event": event, "call_chain": call_chain(event, pcs)}
                  for event in trace["events"]]
        write_json(out / "source-callers.json",
                   {"schema": "sdvk161-startup-caller-symbolization/v1",
                    "binary": source, "address_count": len(pcs),
                    "decoded": pcs, "events": events})
        entry.update(status="PASS_ORIGINAL_NATIVE_WITH_DIAGNOSTIC",
                     trace=census, paths=paths,
                     negative_controls=len(negatives["controls"]),
                     source_callers=pin(out / "source-callers.json", relative_to=out))
        print("ATTEMPT", i, "PASS first_epoch", census["first_retained_texture_epoch"],
              "events", census["events"], "increment_types", census["events_by_type"],
              "resolved_source_pcs", len(pcs), flush=True)
    except Exception as error:
        entry.update(status="FAIL", error=repr(error),
                     traceback=traceback.format_exc(limit=8))
        print("ATTEMPT", i, "FAIL", repr(error), flush=True)
        if (out / "native.renderer.json").exists():
            entry["unadmitted_native"] = pin(out / "native.renderer.json", relative_to=out)
        if (out / TRACE_FILE).exists():
            entry["unadmitted_trace"] = pin(out / TRACE_FILE, relative_to=out)
    entry["finished"] = utc()
    write_json(root / ("attempt-%02d-receipt.json" % i), entry)
    return entry


def main():
    root = run.fresh_directory(ROOT)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(len(source) == 40, "Full exact diagnostic source commit required")
    prepared = root / "prepared"
    manifest = prepare.prepare(prepared, [ss.SCENE])
    report = {"schema": "sdvk161-epoch-forensics/v1",
              "disposition": "NONQUALIFYING_DIAGNOSTIC_ONLY",
              "source": source, "planned_independent_attempts": COUNT,
              "original_frames": ss.FRAMES, "original_warmup": ss.WARMUP,
              "automatic_retries": 0,
              "original_detailed_witness_frames": list(range(8, 97, 8)),
              "pixel_policy": "unchanged exact RGB8",
              "attempts": [], "pair_comparisons": []}
    for index in range(1, COUNT + 1):
        report["attempts"].append(attempt(index, prepared, manifest, source, root))
    for index in range(1, COUNT, 2):
        pair = {"left": index, "right": index + 1, "status": "NOT_COMPARABLE"}
        left = root / ("attempt-%02d" % index)
        right = root / ("attempt-%02d" % (index+1))
        if report["attempts"][index-1]["status"].startswith("PASS_") and \
           report["attempts"][index]["status"].startswith("PASS_"):
            try:
                comparison = run.compare_runs(left, right)
                write_json(root / ("pair-%02d-%02d-original.json" % (index,index+1)), comparison)
                lt = read_json(left / TRACE_FILE)
                rt = read_json(right / TRACE_FILE)
                pair.update(status=comparison["status"], state_equal=comparison["state_equal"],
                            first_state_differences=comparison["first_state_differences"][:40],
                            image=comparison["image"], source_event_differences=delta(lt, rt),
                            first_retained_epoch=[lt["first_retained_texture_epoch"],
                                                  rt["first_retained_texture_epoch"]])
                print("PAIR", index, index+1, "ORIGINAL", pair["status"],
                      "state_equal", pair["state_equal"],
                      "epochs", pair["first_retained_epoch"],
                      "event_delta", len(pair["source_event_differences"]), flush=True)
            except Exception as error:
                pair.update(status="ERROR", error=repr(error))
        report["pair_comparisons"].append(pair)
    write_json(root / "epoch-forensics.json", report)
    print("TEXTURE_EPOCH_NONQUALIFYING_COMPLETE", "attempts",
          len(report["attempts"]), "original_comparison_failures",
          sum(p["status"] == "FAIL" for p in report["pair_comparisons"]),
          "output", root / "epoch-forensics.json", flush=True)


if __name__ == "__main__":
    main()
