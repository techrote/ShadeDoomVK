#!/usr/bin/env python3
"""Targeted exact-source SDVK-161 fixture-isolation qualification; not publication.

Execute the UNMODIFIED existing SDVK-161 qualifier four times, with eight
independent original 32+96-frame captures and eight sets of 35 original
negative controls. Then compare all 28 distinct native pairs with the
UNMODIFIED exact-state and exact-RGB comparer. No retries or comparator edits.
"""
from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import re
import subprocess
import sys

from tools.renderer_oracle import run, sdvk161_special_surfaces as ss
from tools.renderer_oracle.common import pin, read_json, require, write_json

PAIR_COHORTS = 4
EXPECTED_ATTEMPTS = PAIR_COHORTS * 2
EXPECTED_ALL_PAIRS = EXPECTED_ATTEMPTS * (EXPECTED_ATTEMPTS - 1) // 2


def retained_native(path):
    root, receipt, raw, scene = run.validate_run(path)
    argv = read_json(root / "request.json")["argv"]
    require(argv.count("-nostartup") == 1
            and argv.index("-nostartup") == argv.index("-stdout") + 1,
            "Original executed native argv lacks the single, pinned startup-isolation switch")
    negative = read_json(root / "negative-controls.json")
    require(negative["status"] == "PASS" and len(negative["controls"]) == 35
            and all(row["status"] == "REJECTED" for row in negative["controls"]),
            "Original SDVK-161 copied-state falsifiers were not retained and rejected")
    lifecycle = read_json(root / "special-surface-lifecycle.json")
    require(lifecycle["status"] == "PASS",
            "Original SDVK-161 lifecycle/material/owner gate did not pass")
    native_resource = [row["data"] for row in raw["records"]
                       if row["kind"] == "resource" and row["frame"] == 1]
    require(len(native_resource) == 1 and type(native_resource[0].get("texture_epoch")) is int,
            "Original first-retained texture epoch missing")
    return {
        "run": pin(root / "run.json", relative_to=root),
        "native_state": pin(root / "native.renderer.json", relative_to=root),
        "original_negatives": pin(root / "negative-controls.json", relative_to=root),
        "original_lifecycle": pin(root / "special-surface-lifecycle.json", relative_to=root),
        "first_retained_texture_epoch": native_resource[0]["texture_epoch"],
        "first_retained_map": next(row["data"]["map"] for row in raw["records"]
                                  if row["kind"] == "frame" and row["frame"] == 1),
        "original_35_negative_controls": len(negative["controls"]),
        "argv": argv,
    }


def run_all(args):
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None,
            "Exact source identity required")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(actual == args.expected_commit, "Runner source differs from exact qualification source")
    root = run.fresh_directory(args.out)
    report = {
        "schema": "sdvk161-nostartup-fixture-qualification/v1",
        "status": "FAIL",
        "qualified_scope": "Original SDVK-161 lifecycle with explicitly isolated startup screen; NOT full SDVK-009 publication",
        "source": actual,
        "campaign_type": "targeted",
        "planned_original_qualifier_cohorts": PAIR_COHORTS,
        "planned_independent_native_attempts": EXPECTED_ATTEMPTS,
        "planned_exact_pairwise_comparisons": EXPECTED_ALL_PAIRS,
        "original_35_negatives_per_admitted_attempt": True,
        "warmup_frames": 32, "retained_frames": 96,
        "detailed_witness_frames": list(range(8, 97, 8)),
        "image_policy": "original-exact-rgb8",
        "state_policy": "unchanged-semantic-state-projection",
        "automatic_retries": 0,
        "full_publication_qualified": False,
        "physical_gpu_qualified": False,
        "cohorts": [], "native_attempts": [], "cross_comparisons": [],
    }
    valid = []
    try:
        for i in range(1, PAIR_COHORTS + 1):
            subdir = root / f"cohort-{i}"
            options = argparse.Namespace(exe=args.exe, iwad=args.iwad,
                iwad_license=args.iwad_license, out=subdir,
                expected_commit=args.expected_commit)
            result = ss.qualify(options)   # Unmodified original qualifier
            outcome = {"ordinal": i, "status": result.get("status"),
                       "original_qualification": pin(subdir / "qualification.json", relative_to=root)}
            if result.get("status") != "PASS":
                outcome["error"] = result.get("error")
                report["cohorts"].append(outcome)
                print("ORIGINAL_COHORT", i, "FAIL", result.get("error"), flush=True)
                continue
            for attempt_no in (1, 2):
                original = subdir / f"lifecycle-{attempt_no}"
                try:
                    receipt = retained_native(original)
                    receipt.update(ordinal=len(report["native_attempts"]) + 1,
                                   cohort=i, attempt=attempt_no,
                                   location=str(original.relative_to(root)))
                    valid.append(original)
                    report["native_attempts"].append(receipt)
                except Exception as error:
                    outcome["status"] = "FAIL"
                    outcome["error"] = str(error)
                    break
            report["cohorts"].append(outcome)
            print("ORIGINAL_COHORT", i, outcome["status"],
                  "native_attempts", len(report["native_attempts"]), flush=True)
        # When a cohort fails, retain all independent results without treating
        # missing processes as comparable or silently rerunning any attempt.
        if len(valid) == EXPECTED_ATTEMPTS and all(x["status"] == "PASS" for x in report["cohorts"]):
            for index,(left,right) in enumerate(combinations(valid,2), 1):
                comparison = run.compare_runs(left, right)
                out_path = root / f"cross-{index:02d}.json"
                write_json(out_path, comparison)
                record = {
                    "left": str(left.relative_to(root)),
                    "right": str(right.relative_to(root)),
                    "status": comparison["status"],
                    "state_equal": comparison["state_equal"],
                    "image_passed": comparison["image"]["passed"],
                    "changed_pixels": comparison["image"].get("changed_pixels"),
                    "first_state_differences": comparison["first_state_differences"][:12],
                    "receipt": pin(out_path, relative_to=root),
                }
                report["cross_comparisons"].append(record)
                if comparison["status"] != "PASS":
                    print("CROSS_EXACT_FAIL", index, record["left"], record["right"],
                          json.dumps(record["first_state_differences"]), flush=True)
        epoch_values = [r["first_retained_texture_epoch"] for r in report["native_attempts"]]
        report["first_retained_texture_epochs"] = epoch_values
        report["status"] = "PASS" if (
            len(report["cohorts"]) == PAIR_COHORTS
            and all(r["status"] == "PASS" for r in report["cohorts"])
            and len(report["native_attempts"]) == EXPECTED_ATTEMPTS
            and len(report["cross_comparisons"]) == EXPECTED_ALL_PAIRS
            and all(r["status"] == "PASS" and r["state_equal"]
                    and r["image_passed"] and r["changed_pixels"] == 0
                    for r in report["cross_comparisons"])
            and len(set(epoch_values)) == 1
        ) else "FAIL"
    except Exception as error:
        report["error"] = repr(error)
    finally:
        write_json(root / "fixture-qualification.json", report)
    print("NOSTARTUP_TARGETED_QUALIFICATION", report["status"],
          "cohorts", len(report["cohorts"]),
          "admitted", len(report["native_attempts"]),
          "exact_pairs", len(report["cross_comparisons"]),
          "epochs", report.get("first_retained_texture_epochs", []),
          flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--iwad", type=Path, required=True)
    parser.add_argument("--iwad-license", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    result = run_all(parser.parse_args())
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
