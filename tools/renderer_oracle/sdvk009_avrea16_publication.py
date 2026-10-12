#!/usr/bin/env python3
"""Run the frozen PR #146 publication qualification on Avrea 16-vCPU llvmpipe.

Only the hosted execution-surface guard is substituted. The publication
qualification plan, content pins, process ordering, 600-second per-process
deadline, fail-stop behavior and acceptance semantics are the frozen #146 code.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

try:
    from . import sdvk009_publication as publication
    from .sdvk009_avrea16_timeout import avrea16_software_guard
except ImportError:
    import sdvk009_publication as publication
    from sdvk009_avrea16_timeout import avrea16_software_guard


def main(argv=None):
    publication.hosted_software_guard = avrea16_software_guard
    return publication.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
