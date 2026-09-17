# SDVK-008 — Height/POM sprite relief and advanced PBR response

## Purpose
Add bounded pseudo-depth to sprites while preserving their 2D identity and correct PBR response.

## Autonomous execution prompt
Complete SDVK-008 after SDVK-007. Read all founding docs/material/TBN evidence. State POM/relief hypotheses, quality levels, mip strategy and falsification cases before coding. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Implement shallow parallax/parallax-occlusion relief using the SDVK-005 height semantic.
- Provide explicit depth scale/step controls and non-height fallback.
- Handle sprite mirroring/rotation through the SDVK-007 basis.
- Investigate bounded self-occlusion/self-shadow approximation only if it materially improves relief without excessive instability.
- Prevent edge/silhouette artifacts from pretending the sprite has geometry outside its alpha silhouette.
- Add distance/angle quality reduction and stable filtered/mipped height sampling.

## Acceptance criteria
- Relief is demonstrably view/light coherent on deterministic fixtures.
- Extreme settings expose controlled failure rather than NaNs/UV explosions.
- Default/recommended settings preserve sprite character.
- No gameplay collision/silhouette semantics are falsely changed.
- Performance cost is measured by quality level.
- PR merged and verified on `master`.

## Dependencies
SDVK-007.