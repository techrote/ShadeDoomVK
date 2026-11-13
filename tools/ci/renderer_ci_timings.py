#!/usr/bin/env python3
"""Read-only CI timing evidence for hosted software-Vulkan publication captures.

Do not use these measurements to grant physical-GPU or performance acceptance.
The report reads original attempt receipts without altering them or their hashes.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import subprocess

SCHEMA = "sdvk-software-vulkan-ci-timing/v1"
CAPTURES = ("compositing-control", "shadow-control", "shadow-witness-1", "shadow-witness-2")
WORKERS = ("controls", "witness-1", "witness-2")
SUITES = ("corpus", "publication", *WORKERS)


def capture_interval(receipt: dict) -> tuple[datetime, datetime] | None:
    start, finish = receipt.get("started_utc"), receipt.get("finished_utc")
    if not isinstance(start, str) or not isinstance(finish, str):
        return None
    beginning, end = datetime.fromisoformat(start), datetime.fromisoformat(finish)
    if beginning.tzinfo is None or end.tzinfo is None:
        raise ValueError("Capture timestamps must have timezone offsets")
    seconds = (end - beginning).total_seconds()
    if seconds < 0:
        raise ValueError("Capture timestamps run backwards")
    return beginning, end


def duration_seconds(receipt: dict) -> float | None:
    interval = capture_interval(receipt)
    return None if interval is None else round((interval[1] - interval[0]).total_seconds(), 3)


def capture_overlap(records: list[dict]) -> dict:
    """Observe receipt intervals; never substitute a modeled schedule for them."""
    intervals = [interval for row in records if (interval := capture_interval(row)) is not None]
    span = None
    first = last = None
    active = peak = 0
    if intervals:
        first, last = min(start for start, _ in intervals), max(end for _, end in intervals)
        span = (last - first).total_seconds()
        # Finishes precede starts at a shared timestamp; zero-length intervals
        # occupy no wall time and cannot manufacture overlapping execution.
        events = [(instant, delta) for start, end in intervals if start < end
                  for instant, delta in ((start, 1), (end, -1))]
        for _, delta in sorted(events):
            active += delta
            peak = max(peak, active)
    total = sum((end - start).total_seconds() for start, end in intervals)
    return {
        "timed_captures": len(intervals),
        "all_expected_captures_timed": len(intervals) == len(CAPTURES),
        "all_expected_captures_passed": all(row["status"] == "PASS" for row in records),
        "first_started_utc": first.isoformat() if first else None,
        "last_finished_utc": last.isoformat() if last else None,
        "observed_span_seconds": round(span, 3) if span is not None else None,
        "summed_capture_seconds": round(total, 3),
        "sum_to_observed_span_ratio": round(total / span, 6) if span else None,
        "peak_overlapping_capture_steps": peak,
        "interval_basis": "Actual capture-attempt receipt wall-clock intervals, including capture validation; not OS process lifetimes",
        "limitations": "Cross-runner UTC clock alignment is assumed; this is one observed run, not repeatable speedup or workflow latency",
    }


def topology_model(records: list[dict]) -> dict:
    result = {
        "basis": "Scheduling estimates using the individual successful capture durations observed in this run",
        "measured_alternative_execution": False,
        "excludes": ["shared build", "runner queue/startup", "dependency preparation", "artifact transfer",
                     "evidence assembly", "compression", "runner-to-runner workload variability"],
    }
    if len(records) != len(CAPTURES) or any(row["status"] != "PASS" or row["duration_seconds"] is None
                                          for row in records):
        return {**result, "available": False, "reason": "All four successful capture durations are required"}
    durations = {row["name"]: row["duration_seconds"] for row in records}
    controls = durations["compositing-control"] + durations["shadow-control"]
    witnesses = max(durations["shadow-witness-1"], durations["shadow-witness-2"])
    return {**result, "available": True, "serial_capture_seconds": round(sum(durations.values()), 3),
            "ideal_parallel_capture_seconds": round(max(controls, witnesses), 3),
            "ideal_control_gated_capture_seconds": round(controls + witnesses, 3)}


def worker_evidence(root: Path, qualification: dict) -> tuple[list[dict], dict]:
    """Read retained worker metadata, not the aggregation runner's CPU as theirs."""
    workers = qualification.get("workers", [])
    if (not isinstance(workers, list) or
            any(not isinstance(row, dict) or row.get("worker") not in WORKERS for row in workers)):
        raise ValueError("Unknown capture worker timing identity")
    if len({row["worker"] for row in workers}) != len(workers):
        raise ValueError("Duplicate capture worker timing identity")
    profiles = {}
    for name in SUITES:
        profile_path = root.parent / ("renderer-ci-" + name) / "profile.json"
        if not profile_path.is_file():
            continue
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if not isinstance(profile, dict) or profile.get("worker") != name:
            raise ValueError("Cross-wired hosted worker profile: " + name)
        profiles[name] = {"source": str(profile_path), "profile": profile}
    return workers, profiles


def machine_profile() -> dict:
    cpu_model = platform.processor() or "unavailable"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name") and ":" in line:
                cpu_model = line.split(":", 1)[1].strip()
                break
    mesa = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "mesa-vulkan-drivers"],
                          capture_output=True, text=True, timeout=5, check=False)
    cgroup_quota = Path("/sys/fs/cgroup/cpu.max")
    return {
        "cpu_model": cpu_model,
        "logical_processors": os.cpu_count(),
        "affinity_processors": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cgroup_cpu_max": cgroup_quota.read_text().strip() if cgroup_quota.is_file() else None,
        "platform": platform.platform(),
        "mesa_vulkan_drivers_version": mesa.stdout.strip() if mesa.returncode == 0 else None,
        "vulkan_icd": os.environ.get("VK_DRIVER_FILES"),
        "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "evidence_scope": "Descriptive software-Vulkan runner profile, not a physical GPU",
    }


def summarize(root: Path, host: dict | None = None) -> dict:
    qualification_path = root / "qualification.json"
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    records = []
    for name in CAPTURES:
        receipt_path = root / "steps" / (name + ".json")
        if not receipt_path.is_file():
            records.append({"name": name, "status": "NOT_RUN", "duration_seconds": None})
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("name") != name:
            raise ValueError(f"Attempt receipt name mismatch: {name}")
        records.append({
            "name": name,
            "status": receipt.get("status", "UNKNOWN"),
            "started_utc": receipt.get("started_utc"),
            "finished_utc": receipt.get("finished_utc"),
            "duration_seconds": duration_seconds(receipt),
        })
    workers, profiles = worker_evidence(root, qualification)
    return {
        "schema": SCHEMA,
        "source": str(root),
        "qualification_status": qualification.get("status", "UNKNOWN"),
        "actual_processes": records,
        "capture_duration_seconds_sum": round(sum(row["duration_seconds"] or 0 for row in records), 3),
        "capture_observation": capture_overlap(records),
        "topology_model": topology_model(records),
        "workers": workers,
        "worker_profiles": profiles,
        "missing_capture_worker_profiles": [row["worker"] for row in workers if row["worker"] not in profiles],
        "host": host if host is not None else machine_profile(),
        "host_role": "Report generator; capture-worker CPU and identity evidence is retained separately",
        "physical_gpu_qualified": False,
        "performance_accepted": False,
        "timing_interpretation": "Elapsed CI process-step wall time, not frame GPU time or physical acceptance",
    }


def markdown(result: dict) -> str:
    lines = [
        "### Hosted software-Vulkan publication timings",
        "",
        "| Capture | Result | Wall time |",
        "| --- | --- | ---: |",
    ]
    for row in result["actual_processes"]:
        duration = row["duration_seconds"]
        minutes = "not run" if duration is None else f"{duration / 60:.2f} min"
        lines.append(f"| `{row['name']}` | {row['status']} | {minutes} |")
    lines += [
        "",
        f"Qualification: **{result['qualification_status']}**. Total capture-step time: "
        f"**{result['capture_duration_seconds_sum'] / 60:.2f} min**.",
    ]
    observed = result.get("capture_observation", {})
    span = observed.get("observed_span_seconds")
    if span is not None:
        label = "all four captures" if observed["all_expected_captures_timed"] else "partial capture evidence"
        ratio = observed["sum_to_observed_span_ratio"]
        lines += [
            f"Observed first-start to last-finish span ({label}): **{span / 60:.2f} min**. "
            f"Peak overlapping capture steps: **{observed['peak_overlapping_capture_steps']}**.",
            (f"Sum of measured capture durations / observed span: **{ratio:.2f}×**. "
             "This excludes build, setup, transfer and final assembly; it is not end-to-end workflow speedup.")
            if ratio is not None else "No positive-duration interval is available for a span ratio.",
        ]
    model = result.get("topology_model", {})
    if model.get("available"):
        lines += [
            "",
            "**Modeled scheduling only**, using this run's capture durations and excluding startup/queue/transfer overhead:",
            f"three-way parallel **{model['ideal_parallel_capture_seconds'] / 60:.2f} min**; "
            f"control-gated **{model['ideal_control_gated_capture_seconds'] / 60:.2f} min**.",
            "These estimates are separate from the actual observed intervals and any separately retained native compatibility probe.",
        ]
    profiles = result.get("worker_profiles", {})
    if profiles:
        lines += ["", "| Worker | CPU | Logical / affinity CPUs | CPU quota | Mesa package |",
                  "| --- | --- | ---: | --- | --- |"]
        def cell(value):
            return str(value if value is not None else "unavailable").replace("|", "\\|").replace("\n", " ")
        for worker, record in profiles.items():
            profile = record["profile"]
            lines.append(f"| `{worker}` | {cell(profile.get('cpu_model'))} | "
                         f"{cell(profile.get('logical_processors'))} / {cell(profile.get('affinity_processors'))} | "
                         f"{cell(profile.get('cgroup_cpu_max'))} | {cell(profile.get('mesa_vulkan_drivers_version'))} |")
    lines += ["", "Descriptive GitHub-hosted llvmpipe timings only; **not physical GPU performance acceptance**.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="renderer-sdvk009-publication evidence directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = markdown(result)
    print(summary, flush=True)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("a", encoding="utf-8") as file:
            file.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
