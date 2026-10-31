#!/usr/bin/env python3
"""Report original SDVK-009 publication step timings without modifying receipts.

Descriptive CI diagnostics only; no approval, result, or evidence contract changes.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import sys

STAGES = ("compositing-control", "shadow-control", "shadow-witness-1", "shadow-witness-2")


def seconds_between(start: str, finish: str) -> float:
    left, right = datetime.fromisoformat(start), datetime.fromisoformat(finish)
    if left.tzinfo is None or right.tzinfo is None:
        raise ValueError("Publication timestamps must carry a timezone")
    elapsed = (right - left).total_seconds()
    if elapsed < 0:
        raise ValueError("Publication step finished before it started")
    return elapsed


def report(root: Path) -> str:
    rows = ["| Original publication process | Status | Wall time |", "| --- | --- | ---: |"]
    total = 0.0
    seen = 0
    for name in STAGES:
        receipt = root / "steps" / (name + ".json")
        if not receipt.is_file():
            rows.append(f"| \x60{name}\x60 | Not reached | — |")
            continue
        if receipt.stat().st_size > 1024 * 1024:
            raise ValueError(f"Oversized publication step receipt: {receipt}")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if data.get("name") != name or data.get("status") not in ("PASS", "FAIL"):
            raise ValueError(f"Invalid publication step receipt identity/status: {receipt}")
        elapsed = seconds_between(data["started_utc"], data["finished_utc"])
        total += elapsed
        seen += 1
        rows.append(f"| \x60{name}\x60 | {data['status']} | {elapsed / 60:.1f} min |")
    rows.append(f"\nObserved processes: {seen}/{len(STAGES)}; sum of observed process-step wall times: {total / 60:.1f} min.")
    rows.append("These are descriptive hosted software-Vulkan times, not physical-GPU performance acceptance.")
    return "\n".join(rows) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: renderer_publication_timings.py <publication-root>", file=sys.stderr)
        return 2
    output = report(Path(argv[1]))
    print(output, end="")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("### SDVK-009 original publication processes (sharding profile)\n\n" + output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
