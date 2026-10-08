"""Retain and index accepted PF formats without upgrading their evidence claims.

PF's own native validators remain authoritative. An import is not a re-run,
source-equivalence assertion, or validation of referenced private artifacts.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

try:
    from .common import pin, read_json, require
except ImportError:
    from common import pin, read_json, require

CHANNELS = ("context", "material", "lights", "probe", "shadow", "resources", "pipeline", "timing", "images")

# The selections are paths in the original JSON, not substitute values. Users
# inspect the complete source document, including each producer's limitations.
FORMATS = {
    "pf020-native-scene-observation/v1": {
        "states": ("COLLECTED_STATE_ONLY",), "scope": "Bounded PFVTEST scene/sprite observation",
        "channels": {"context": ["records"], "material": ["records"]},
        "validator": "tools/pf_oracle/run_freeze_view_acceptance.py:scene_evidence",
    },
    "shadedoomvk-pf020-vulkan-observation/v1": {
        "states": ("COLLECTED_PENDING_VALIDATION",), "scope": "Bounded PF020 producer and cache observations",
        "channels": {"pipeline": ["keyLookups", "workerState"], "images": ["images"]},
        "validator": "tools/pf_oracle/run_freeze_view_acceptance.py:validate_state",
    },
    "shadedoomvk-pf110-native-indexed/v1": {
        "states": ("PASS",), "scope": "Bounded indexed material private controls and real presentation",
        "channels": {"material": ["cases"]},
        "validator": "tools/pf_oracle/run_indexed_material_runtime.py",
    },
    "shadedoomvk-pf113-startup-observer/v1": {
        "states": ("PASS",), "scope": "Actual bounded PBR publication-window draw and uniform observations",
        "channels": {"probe": ["draws", "events"], "material": ["draws"]},
        "validator": "tools/pf_oracle/run_pbr_probe_runtime.py",
    },
    "shadedoomvk-pf113-native-probe-controls/v1": {
        "states": ("PASS",), "scope": "Bounded private probe fragment readbacks; separate from ordinary scene output",
        "channels": {"probe": ["cases"], "resources": ["resources"]},
        "validator": "tools/pf_oracle/run_pbr_probe_runtime.py",
    },
}


def adapt(path):
    source = read_json(path)
    require(isinstance(source, dict) and source.get("schema") in FORMATS, "Unknown PF producer schema")
    specification = FORMATS[source["schema"]]
    require(source.get("status") in specification["states"] and not source.get("error"),
            "Failed/incomplete PF producer cannot be imported as collected evidence")
    result = {"schema": "sdvk-pf-import/v1", "source": pin(path),
              "producer_schema": source["schema"], "producer_status": source["status"],
              "scope": specification["scope"], "producer_validator": specification["validator"],
              "validation": "indexed_only; run the original PF validator with its complete artifact packet",
              "fresh_execution": False, "current_build_equivalence_established": False,
              "channels": {}, "original": source}
    for channel in CHANNELS:
        requested = specification["channels"].get(channel, [])
        fields = [key for key in requested if key in source and source[key] not in ([], {}, None)]
        result["channels"][channel] = (
            {"status": "source_present", "json_pointers": ["/" + key for key in fields],
             "qualification": "Only the original producer's documented subset; not complete channel coverage"}
            if fields else {"status": "not_collected", "reason": "No value supplied by this PF producer"})
    if source["schema"] == "shadedoomvk-pf110-native-indexed/v1":
        pointers = [f"/cases/{index}/token" for index, case in enumerate(source.get("cases", []))
                    if isinstance(case, dict) and isinstance(case.get("token"), dict) and case["token"]]
        if pointers:
            result["channels"]["resources"] = {
                "status": "source_present", "json_pointers": pointers,
                "qualification": "Original per-case resource tokens only; run the original PF validator for liveness/readback proof"}
    require(any(row["status"] == "source_present" for row in result["channels"].values()),
            "PF document contains no observations for its declared producer schema")
    return result
