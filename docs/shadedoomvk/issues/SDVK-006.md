# SDVK-006 — Render-frame time and opt-in visual interpolation substrate

## Purpose
Provide a high-frame-rate visual clock without changing Doom gameplay simulation.

## Autonomous execution prompt
Complete SDVK-006 after SDVK-001 and SDVK-002. Read all founding docs, especially simulation/rendering rules, and inspect MAD-VKDoom commits `316b18a4d96b1a120c681d368ac670286234bcc8` and `7d1f2df404711986a3cc742dad1f9e6e0ac69cde`. Adapt concepts with explicit renderer semantics. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Add reliable rendered-frame delta/time access for renderer/shader/script visual use.
- Reset/clamp appropriately across loads, wipes, pauses and discontinuities.
- Add opt-in high-FPS interpolation for visually useful alpha/scale state where compatibility-safe.
- Keep authoritative game state/tics deterministic and unchanged.
- Add deterministic tests for discontinuity handling and interpolation endpoints.

## Acceptance criteria
- Visual delta time is well-defined and diagnosable.
- Load/wipe/pause barriers cannot produce uncontrolled temporal jumps.
- Opt-in alpha/scale interpolation is smooth and backward compatible.
- Gameplay/demos are not made frame-rate dependent by the feature.
- PR merged and verified on `master`.

## Dependencies
SDVK-001, SDVK-002.