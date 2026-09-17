#!/usr/bin/env python3
"""Deterministic pre-foundation source/contract oracle for ShadeDoomVK.

PF-001 deliberately avoids pretending that GitHub CI can render Vulkan reference
images without a runnable game/IWAD/GPU environment.  Instead this oracle pins
small, high-value architectural invariants and known-defect reproducers in the
source tree.  Later PF issues can add runtime evidence using the companion JSON
schema without replacing this cheap CI guard.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any


class OracleError(RuntimeError):
    """Manifest or source-contract configuration is invalid."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise OracleError(f"cannot read JSON {path}: {exc}") from exc


def _read_source(repo_root: Path, relpath: str) -> str:
    path = repo_root / relpath
    try:
        # Normalize line endings so the oracle is identical on all CI hosts.
        return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except OSError as exc:
        raise OracleError(f"cannot read source path {relpath}: {exc}") from exc


def _matches(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text, flags=re.MULTILINE | re.DOTALL) is not None
    except re.error as exc:
        raise OracleError(f"invalid regex {pattern!r}: {exc}") from exc


def evaluate_manifest(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise OracleError("manifest schema_version must be 1")
    probes = manifest.get("probes")
    if not isinstance(probes, list) or not probes:
        raise OracleError("manifest probes must be a non-empty list")

    seen_ids: set[str] = set()
    results: list[dict[str, str]] = []
    unexpected = 0

    for probe in probes:
        if not isinstance(probe, dict):
            raise OracleError("each probe must be an object")
        probe_id = probe.get("id")
        kind = probe.get("kind")
        category = probe.get("category")
        owner = probe.get("owner")
        paths = probe.get("paths")
        required = probe.get("required", [])
        forbidden = probe.get("forbidden", [])

        if not isinstance(probe_id, str) or not probe_id:
            raise OracleError("probe id must be a non-empty string")
        if probe_id in seen_ids:
            raise OracleError(f"duplicate probe id: {probe_id}")
        seen_ids.add(probe_id)
        if kind not in {"invariant", "known_defect"}:
            raise OracleError(f"probe {probe_id}: unsupported kind {kind!r}")
        if not isinstance(category, str) or not category:
            raise OracleError(f"probe {probe_id}: category must be a non-empty string")
        if not isinstance(owner, str) or not owner:
            raise OracleError(f"probe {probe_id}: owner must be a non-empty string")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
            raise OracleError(f"probe {probe_id}: paths must be a non-empty string list")
        if not isinstance(required, list) or not all(isinstance(p, str) for p in required):
            raise OracleError(f"probe {probe_id}: required must be a string list")
        if not isinstance(forbidden, list) or not all(isinstance(p, str) for p in forbidden):
            raise OracleError(f"probe {probe_id}: forbidden must be a string list")
        if not required and not forbidden:
            raise OracleError(f"probe {probe_id}: at least one required/forbidden pattern is required")

        combined = "\n\n/* PF_ORACLE_FILE_BOUNDARY */\n\n".join(
            _read_source(repo_root, relpath) for relpath in paths
        )
        present = all(_matches(pattern, combined) for pattern in required)
        absent = all(not _matches(pattern, combined) for pattern in forbidden)
        reproduced = present and absent

        if kind == "invariant":
            classification = "invariant_passed" if reproduced else "invariant_broken"
        else:
            classification = "known_defect_reproduced" if reproduced else "known_defect_changed"

        if classification in {"invariant_broken", "known_defect_changed"}:
            unexpected += 1

        results.append(
            {
                "id": probe_id,
                "category": category,
                "kind": kind,
                "owner": owner,
                "classification": classification,
            }
        )

    results.sort(key=lambda item: item["id"])
    summary = {
        "probe_count": len(results),
        "invariant_passed": sum(r["classification"] == "invariant_passed" for r in results),
        "known_defect_reproduced": sum(
            r["classification"] == "known_defect_reproduced" for r in results
        ),
        "unexpected": unexpected,
    }

    return {
        "schema_version": 1,
        "programme": manifest.get("programme", "PF-001"),
        "baseline_lineage": manifest.get("baseline_lineage", "unknown"),
        "summary": summary,
        "probes": results,
    }


def _compare_baseline(actual: dict[str, Any], baseline: dict[str, Any]) -> str | None:
    actual_text = _canonical_json(actual)
    baseline_text = _canonical_json(baseline)
    if actual_text == baseline_text:
        return None
    return "".join(
        difflib.unified_diff(
            baseline_text.splitlines(keepends=True),
            actual_text.splitlines(keepends=True),
            fromfile="checked-in baseline",
            tofile="current oracle",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_root / "tools" / "pf_oracle" / "probes.json",
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        manifest = _load_json(args.manifest)
        result = evaluate_manifest(args.repo_root.resolve(), manifest)
        rendered = _canonical_json(result)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)

        if result["summary"]["unexpected"]:
            print(
                f"PF oracle: {result['summary']['unexpected']} unexpected source-contract change(s)",
                file=sys.stderr,
            )
            return 2

        if args.baseline:
            baseline = _load_json(args.baseline)
            diff = _compare_baseline(result, baseline)
            if diff is not None:
                print("PF oracle baseline mismatch:\n" + diff, file=sys.stderr)
                return 3

        return 0
    except OracleError as exc:
        print(f"PF oracle configuration error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
