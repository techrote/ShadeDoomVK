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
    if system == "Windows":
        executables = [runtime / "vkdoom.exe", runtime / "vktool.exe"]
    elif system == "Darwin":
        executables = [runtime / "vkdoom.app/Contents/MacOS/vkdoom", runtime / "vktool"]
    else:
        executables = [runtime / "vkdoom", runtime / "vktool"]
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    header = (ROOT / "src/version.h").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^#define (SDVK_\w+) "([^"]+)"', header, re.MULTILINE))
    environment = os.environ.copy()
    environment.pop("DISPLAY", None)
    environment.pop("WAYLAND_DISPLAY", None)
    # A fresh empty cwd supplies neither game resources nor configuration.
    with tempfile.TemporaryDirectory() as directory:
        for executable in executables:
            result = subprocess.run([str(executable), "--version"], cwd=directory,
                                    env=environment, capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise SystemExit(f"{executable} failed ({result.returncode}): {result.stderr}")
            lines = result.stdout.splitlines()
            expected_lines = [constants["SDVK_PROJECT_NAME"] + " " + constants["SDVK_VERSIONSTR"],
                              "Commit: " + expected,
                              "VKDoom lineage: nashmuhandes/VkDoom@" + constants["SDVK_FOUNDING_COMMIT"],
                              "PF-020 freeze: " + constants["SDVK_PF_FREEZE_COMMIT"]]
            if not all(line in lines for line in expected_lines) or len(lines) != 6:
                raise SystemExit(f"Unexpected identity from {executable}: {result.stdout!r}")
            if args.expected_state and "Working tree: " + args.expected_state not in lines:
                raise SystemExit(f"Unexpected working-tree state: {result.stdout!r}")
            print(f"PASS {executable}\n{result.stdout}", end="")


if __name__ == "__main__":
    main()
