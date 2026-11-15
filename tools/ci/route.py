#!/usr/bin/env python3
"""R-001 risk routing. Unknown or missing change information never means docs-only.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

GROUPS = ("actors", "materials", "resources", "lightmaps", "portals", "lighting")
NATIVE_SUITES = ("routine", "actors", "resources", "lightmaps", "surfaces")
ROOT = Path(__file__).resolve().parents[2]


def classify(paths):
    paths = sorted(set(paths))
    groups = set()
    reasons = []
    native = False
    for path in paths:
        if not path or path.startswith("/") or ".." in path.split("/") or "\\" in path:
            raise ValueError("Invalid changed repository path: " + repr(path))
        p = path.lower()
        selected = set()
        if p.startswith("docs/") or p in {"readme.md", "agents.md", "license", "license.txt", ".gitignore"}:
            reasons.append({"path": path, "scope": "documentation; CPU and compilation still required"})
            continue
        native = True
        actor_path = p.startswith("tools/shadow001/") or any(x in p for x in
            ("hw_sprites.", "hw_sprite_", "hw_projectedshadow", "hw_projected_shadow"))
        if p.startswith((".github/", "tools/ci/")) or p in {
                "tools/check.py", "tools/renderer_oracle/tests/test_ci_runner_policy.py"}:
            # Qualify the changed executor with routine and resource/actor lanes.
            # Selector fixtures separately prove every special-path mapping.
            selected.update(("actors", "resources"))
        if actor_path:
            selected.add("actors")
        if "portal" in p or "mirror" in p or "rendercontext" in p:
            selected.update(("portals", "actors"))
        if any(x in p for x in ("levelmesh", "lightmap", "lightmapper", "atlas")):
            selected.update(("lightmaps", "resources"))
        if any(x in p for x in ("probe", "descriptor", "bindless", "generation", "resource")):
            selected.add("resources")
        if any(x in p for x in ("material", "texture", "sampler", "shader", "image")):
            selected.update(("materials", "resources"))
        if any(x in p for x in ("spritelight", "dynlight", "lightquery", "lighting")) or (
                "shadow" in p and not actor_path):
            selected.update(("lighting", "actors"))
        if any(x in p for x in ("actor", "weapon", "sprite", "playsim/", "gameplay")):
            selected.add("actors")
        if "sdvk010" in p or "sdvk011" in p:
            selected.add("actors")
        if "sdvk150" in p or "sdvk153" in p:
            selected.add("resources")
        if any(x in p for x in ("sdvk158", "sdvk161", "sdvk014")):
            selected.update(("lightmaps", "resources"))
        if "sdvk008" in p:
            selected.update(("materials", "actors"))
        if not selected:
            # New source directories, shared headers, build configuration and
            # unclassified harness changes must not accidentally lose coverage.
            selected.update(GROUPS)
        groups.update(selected)
        reasons.append({"path": path, "scope": "native", "targeted": sorted(selected)})
    if not paths:
        native = True
        groups.update(GROUPS)
        reasons.append({"scope": "empty change set; conservative full targeted coverage"})
    return {"schema": "sdvk-ci-routing/v1", "native": native,
            "targeted": sorted(groups), "deep": False, "paths": paths,
            "reasons": reasons, "physical_stop_active": True}


def select_native_suites(result):
    """Select each native risk group once; do not mistake a skipped suite for a PASS."""
    if not result["native"]:
        return []
    groups = set(result["targeted"])
    selected = ["routine"]
    if "actors" in groups:
        selected.append("actors")
    if "resources" in groups or "materials" in groups:
        selected.append("resources")
    if "lightmaps" in groups:
        selected.append("lightmaps")
    if "lightmaps" in groups or "portals" in groups:
        selected.append("surfaces")
    return selected


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def changed_paths(event, event_name):
    head = git("rev-parse", "HEAD").decode().strip()
    if event_name == "pull_request":
        expected = event["pull_request"]["head"]["sha"]
        base = event["pull_request"]["base"]["sha"]
    elif event_name == "push":
        expected, base = event["after"], event["before"]
    else:
        raise ValueError("Unsupported routine event: " + event_name)
    if not re.fullmatch(r"[a-f0-9]{40}", expected) or head != expected:
        raise ValueError("Checkout does not match the exact event source head")
    if not re.fullmatch(r"[a-f0-9]{40}", base):
        raise ValueError("Malformed comparison base")
    if base == "0" * 40:
        return [], head, base
    git("cat-file", "-e", base + "^{commit}")
    if event_name == "pull_request":
        base = git("merge-base", base, head).decode().strip()
    raw = git("diff", "--name-only", "--no-renames", "-z", base, head)
    return [p.decode("utf-8", "strict") for p in raw.split(b"\0") if p], head, base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    paths, head, base = changed_paths(json.loads(args.event_path.read_text()), args.event_name)
    result = classify(paths)
    result.update(head=head, base=base)
    result["native_suites"] = select_native_suites(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    with args.github_output.open("a") as stream:
        stream.write("native=" + str(result["native"]).lower() + "\n")
        stream.write("suites=" + json.dumps(result["native_suites"] or ["not-applicable"], separators=(",", ":")) + "\n")
        for group in GROUPS:
            stream.write(group + "=" + str(group in result["targeted"]).lower() + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
