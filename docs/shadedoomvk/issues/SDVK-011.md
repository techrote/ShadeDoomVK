# SDVK-011 — First-person viewmodel lighting and material parity

## Purpose
Make weapon sprites/models participate coherently in the same lighting language as world actors.

## Autonomous execution prompt
Complete SDVK-011 after SDVK-009 and SDVK-010. Read all founding docs and inspect MAD-VKDoom `346f4c0e87139ec8eb0d94d5792d8521b9d17a85` as evidence of the problem, not a mandatory binary-toggle design. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Define compatibility-selectable viewmodel modes such as legacy, sector-faithful and world/probe/PBR.
- Apply local dynamic lights/probes/sun/sector state coherently where meaningful for first-person sprites/models.
- Support normal/PBR weapon materials through the same semantic material system where technically valid.
- Avoid impossible world-space parallax/shadow assumptions caused by HUD/viewmodel projection.
- Add dark-room, colored-light, probe-boundary and muzzle-flash fixtures.

## Acceptance criteria
- Viewmodel lighting no longer requires an unrelated ad-hoc material model for the enhanced path.
- Legacy mode preserves inherited behavior.
- World/PBR mode is diagnostically explicit and tested.
- Muzzle/local light response is stable and does not feed back into gameplay.
- PR merged and verified on `master`.

## Dependencies
SDVK-009, SDVK-010.