#!/usr/bin/env python3
"""Check built executables' --version without an IWAD or display. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def validate_identity_output(stdout, *, commit, state, description, constants):
    """Require the six current GetBuildIdentity fields, in their emitted order."""
    expected_lines = [
        constants["SDVK_PROJECT_NAME"] + " " + constants["SDVK_VERSIONSTR"],
        "Commit: " + commit,
        "Working tree: " + state,
        "Git description: " + description,
        "VKDoom lineage: nashmuhandes/VkDoom@" + constants["SDVK_FOUNDING_COMMIT"],
        "PF-020 freeze: " + constants["SDVK_PF_FREEZE_COMMIT"],
    ]
    expected_output = "\n".join(expected_lines) + "\n"
    if stdout != expected_output:
        raise ValueError("six-field build identity is incomplete, changed or out of order")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--config", default="RelWithDebInfo")
    parser.add_argument("--expected-state", choices=("clean", "modified", "unknown"))
    args = parser.parse_args()
    build = args.build_dir.resolve()
    cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
    multi_config = any(line.startswith("CMAKE_CONFIGURATION_TYPES:STRING=") and
                       line.split("=", 1)[1] for line in cache.splitlines())
    runtime = build / args.config if multi_config else build
    system = platform.system()
    version_timeout = 60 if system == "Windows" else 20
    if system == "Windows":
        executables = [runtime / "vkdoom.exe", runtime / "vktool.exe"]
    elif system == "Darwin":
        executables = [runtime / "vkdoom.app/Contents/MacOS/vkdoom", runtime / "vktool"]
    else:
        executables = [runtime / "vkdoom", runtime / "vktool"]
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    description = subprocess.check_output(
        ["git", "describe", "--tags", "--always", "--dirty=-m"], cwd=ROOT, text=True).strip()
    observed_state = "modified" if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, text=True).strip() else "clean"
    if args.expected_state and args.expected_state != observed_state:
        raise SystemExit(f"Unexpected source working-tree state: {observed_state}")
    header = (ROOT / "src/version.h").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^#define (SDVK_\w+) "([^"]+)"', header, re.MULTILINE))
    environment = os.environ.copy()
    environment.pop("DISPLAY", None)
    environment.pop("WAYLAND_DISPLAY", None)
    # A fresh empty cwd supplies neither game resources nor configuration.
    with tempfile.TemporaryDirectory() as directory:
        for executable in executables:
            result = subprocess.run([str(executable), "--version"], cwd=directory,
                                    env=environment, capture_output=True, text=True, timeout=version_timeout)
            if result.returncode:
                raise SystemExit(f"{executable} failed ({result.returncode}): {result.stderr}")
            try:
                validate_identity_output(result.stdout, commit=expected, state=observed_state,
                                         description=description, constants=constants)
            except ValueError as error:
                raise SystemExit(f"Unexpected identity from {executable}: {error}; {result.stdout!r}") from error
            print(f"PASS {executable}\n{result.stdout}", end="")


if __name__ == "__main__":
    main()
