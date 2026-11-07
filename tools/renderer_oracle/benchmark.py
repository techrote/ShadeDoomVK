"""Distributions for raw renderer samples; no inference from average FPS.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import math
import statistics

try:
    from .common import integer, number, require
except ImportError:
    from common import integer, number, require


def percentile(values, percent):
    """Hyndman/Fan type 7: linear interpolation at (n - 1) * p / 100."""
    require(values, "Cannot compute a percentile of no observations")
    number(percent, "percentile")
    require(percent <= 100, "Percentile exceeds 100")
    ordered = sorted(number(v, "timing sample") for v in values)
    index = (len(ordered) - 1) * percent / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def distribution(samples, *, minimum_samples=30):
    integer(minimum_samples, "minimum samples", minimum=1)
    require(len(samples) >= minimum_samples, f"Insufficient timing samples: {len(samples)} < {minimum_samples}")
    values = [number(value, "timing sample") for value in samples]
    return {"count": len(values), "min": min(values), "max": max(values),
            "mean": statistics.fmean(values), "p50": percentile(values, 50),
            "p90": percentile(values, 90), "p95": percentile(values, 95),
            "p99": percentile(values, 99),
            "method": "Hyndman-Fan type 7; linear interpolation at (n-1)*p/100"}


def summarize(observation, *, minimum_samples=30):
    # This is a supplementary admission check, not a replacement for the full
    # native envelope and artifact verification performed by run.validate_run.
    require(isinstance(observation, dict) and observation.get("schema") == "sdvk-renderer-observation/v1",
            "Unknown native timing observation schema")
    require(observation.get("mode") == "timing", "State/capture observations are not ordinary timing evidence")
    require(observation.get("status") == "COLLECTED_PENDING_VALIDATION" and observation.get("error") == "",
            "Failed or incomplete native timing collection")
    require(observation.get("performance_accepted") is False,
            "Native collector cannot award performance acceptance")
    count = integer(observation.get("requested_frames"), "requested timing frames", minimum=1, maximum=4096)
    require(integer(observation.get("observed_frames"), "observed timing frames", minimum=1, maximum=4096) == count,
            "Native timing interval is incomplete")
    require(type(observation.get("dropped_records")) is int and observation["dropped_records"] == 0,
            "Truncated native timing collection cannot be summarized")
    records = observation.get("records")
    require(isinstance(records, list) and all(isinstance(r, dict) and isinstance(r.get("kind"), str)
                                               for r in records), "Malformed native timing records")
    frames = [r for r in records if r["kind"] == "frame"]
    require(len(frames) == count and all(r.get("count") == 1 for r in frames) and
            {integer(r.get("frame"), "timing frame index", minimum=1, maximum=count) for r in frames}
            == set(range(1, count + 1)), "Missing, duplicated or multiplied native timing frame")
    values = [r["data"]["cpu_render_view_ms"] for r in frames]
    result = {"schema": "sdvk-renderer-benchmark/v1", "source": "actual native observer frames",
              "scope": "CPU RenderView; excludes simulation and presentation outside this call",
              "units": "milliseconds", "observer_mode": "timing",
              "cpu_render_view": distribution(values, minimum_samples=minimum_samples),
              "raw_cpu_render_view_ms": values, "gpu_groups": {}, "counters": {},
              "interpretation": "Descriptive samples; no significance, speedup or universal hardware claim."}
    for key in ("walls", "flats", "sprites", "decals", "portals", "vertices"):
        counts = [integer(r["data"][key], key) for r in frames if key in r["data"]]
        if counts:
            require(len(counts) == len(frames), f"Counter {key} is missing on some frames")
            result["counters"][key] = {"min": min(counts), "max": max(counts), "samples": counts}
    groups = {}
    for record in observation["records"]:
        if record["kind"] != "timing" or record["data"].get("clock") != "gpu":
            continue
        data = record["data"]
        require(isinstance(data.get("name"), str) and data["name"], "GPU group has no name")
        groups.setdefault(data["name"], []).append(number(data.get("milliseconds"), "GPU timestamp duration"))
    for name, samples in groups.items():
        result["gpu_groups"][name] = {"distribution": distribution(samples, minimum_samples=1),
                                      "samples_ms": samples,
                                      "scope": "Named timestamp group; groups may nest and MUST NOT be summed"}
    if not groups:
        result["gpu_unavailable_reason"] = "No resolved GPU timestamp groups in this collection"
    return result
