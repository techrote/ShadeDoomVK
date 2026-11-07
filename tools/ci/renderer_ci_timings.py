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

SCHEMA = "sdvk-software-vulkan-ci-timing/v1"
CAPTURES = ("compositing-control", "shadow-control", "shadow-witness-1", "shadow-witness-2")


def duration_seconds(receipt: dict) -> float | None:
    start, finish = receipt.get("started_utc"), receipt.get("finished_utc")
    if not isinstance(start, str) or not isinstance(finish, str):
        return None
    beginning, end = datetime.fromisoformat(start), datetime.fromisoformat(finish)
    if beginning.tzinfo is None or end.tzinfo is None:
        raise ValueError("Capture timestamps must have timezone offsets")
    seconds = (end - beginning).total_seconds()
    if seconds < 0:
        raise ValueError("Capture timestamps run backwards")
    return round(seconds, 3)


def machine_profile() -> dict:
    cpu_model = platform.processor() or "unavailable"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name") and ":" in line:
                cpu_model = line.split(":", 1)[1].strip()
                break
    cgroup_quota = Path("/sys/fs/cgroup/cpu.max")
    return {
        "cpu_model": cpu_model,
        "logical_processors": os.cpu_count(),
        "affinity_processors": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cgroup_cpu_max": cgroup_quota.read_text().strip() if cgroup_quota.is_file() else None,
        "platform": platform.platform(),
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
    return {
        "schema": SCHEMA,
        "source": str(root),
        "qualification_status": qualification.get("status", "UNKNOWN"),
        "actual_processes": records,
        "capture_duration_seconds_sum": round(sum(row["duration_seconds"] or 0 for row in records), 3),
        "host": host if host is not None else machine_profile(),
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
        "Descriptive GitHub-hosted llvmpipe timings only; **not physical GPU performance acceptance**.",
        "",
    ]
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
