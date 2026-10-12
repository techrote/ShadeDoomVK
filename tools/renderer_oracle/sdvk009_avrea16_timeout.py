#!/usr/bin/env python3
"""Avrea 16-vCPU wrapper for the SDVK-009 timeout discriminator.

This changes only the approved hosted execution surface. Renderer/content/workload
and the 600-second failure boundary remain those of the frozen PR #146 control.
It cannot grant PR #146 qualification acceptance.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

try:
    from . import sdvk009_publication as publication
    from . import sdvk009_timeout_discriminator as discriminator
    from .common import pin, read_json, require
except ImportError:
    import sdvk009_publication as publication
    import sdvk009_timeout_discriminator as discriminator
    from common import pin, read_json, require

RUNNER_LABEL = "avrea-ubuntu-24.04-16-vcpu"
EXPECTED_VCPUS = 16


def avrea16_software_guard():
    require(sys.platform == "linux" and os.environ.get("GITHUB_ACTIONS") == "true",
            "Avrea diagnostic requires a GitHub Actions Linux job")
    require(os.environ.get("SDVK_REQUESTED_RUNNER") == RUNNER_LABEL,
            "Avrea diagnostic runner label is not the preregistered 16-vCPU label")
    require(hasattr(os, "sched_getaffinity"), "CPU affinity evidence is unavailable")
    affinity = sorted(os.sched_getaffinity(0))
    require(len(affinity) == EXPECTED_VCPUS,
            "Avrea diagnostic did not receive exactly 16 allowed CPUs")
    require((os.cpu_count() or 0) >= EXPECTED_VCPUS,
            "Host reports fewer than 16 logical CPUs")

    names = ("VK_DRIVER_FILES", "VK_ICD_FILENAMES")
    selected = []
    for name in names:
        value = os.environ.get(name, "")
        require(value and len(value.split(os.pathsep)) == 1,
                "Select one lavapipe ICD explicitly with " + name)
        path = Path(value)
        require(path.is_absolute(), "Software ICD selection must use an absolute manifest path")
        selected.append(path.resolve(strict=True))
    require(selected[0] == selected[1], "Vulkan driver manifest selectors differ")
    path = selected[0]
    require(re.fullmatch(r"lvp_icd(?:\.[A-Za-z0-9_-]+)?\.json", path.name) is not None,
            "Selected manifest is not the lavapipe ICD")
    manifest = read_json(path, maximum=65536)
    require(isinstance(manifest, dict) and isinstance(manifest.get("ICD"), dict),
            "Malformed software ICD manifest")
    library = manifest["ICD"].get("library_path", "")
    require(isinstance(library, str)
            and re.fullmatch(r"libvulkan_lvp\.so(?:\.[0-9]+)*", Path(library).name),
            "Selected ICD does not name the lavapipe shared library")
    overrides = {key: value for key, value in os.environ.items() if value and
                 ((key.startswith("VK_") and key not in names) or key in
                  ("MESA_LOADER_DRIVER_OVERRIDE", "MESA_VK_DEVICE_SELECT",
                   "MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE", "DRI_PRIME"))}
    require(not overrides, "Additional Vulkan driver/layer/device overrides are not isolated")
    return {"platform": sys.platform, "provider": "avrea",
            "requested_runner": RUNNER_LABEL, "expected_vcpus": EXPECTED_VCPUS,
            "allowed_cpus": affinity, "logical_processors": os.cpu_count(),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
            "icd": pin(path), "library_path": library,
            "selectors": {key: os.environ[key] for key in names},
            "additional_overrides": {}}


def main(argv=None):
    publication.hosted_software_guard = avrea16_software_guard
    return discriminator.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
