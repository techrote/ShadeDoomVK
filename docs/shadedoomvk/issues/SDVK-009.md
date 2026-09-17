# SDVK-009 — Dynamic-light gathering and data-layout qualification

## Purpose
Reduce CPU/light-selection overhead for sprite-heavy scenes without changing which lights are physically eligible.

## Autonomous execution prompt
Complete SDVK-009 after SDVK-002 and SDVK-003. Read all founding docs and inspect MAD-VKDoom commits `2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5`, `807043b995264f166e333bca54c4e0b281bd8669`, and `773c53489663040697e744b50bf1b89e06525930`. Treat them as competing hypotheses. Preserve portal/group correctness. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Profile stock actor/sprite dynamic-light gathering across sparse/dense scenes.
- Compare BSP walking with section-local/indexed light gathering for small actors.
- Investigate pointer-heavy linked structures versus compact indexed containers where profiling supports it.
- Require selected-light equivalence on reference scenes including portals/occlusion.
- Keep a compatibility/debug switch capable of comparing old/new selection during qualification.
- Record whether GPU clustered/tiled culling is warranted as a later architecture step; do not add it merely for fashion.

## Acceptance criteria
- Before/after CPU cost and selected-light sets are captured.
- Any adopted fast path preserves required portal/group/actor filtering semantics.
- Dense-light stress has bounded behavior and no stale-light lifetime bugs.
- Negative donor assumptions are documented rather than copied.
- PR merged and verified on `master`.

## Dependencies
SDVK-002, SDVK-003.