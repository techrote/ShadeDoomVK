# SDVK-012 — Sprite shadow-caster comparative prototype

## Purpose
Select the simplest sprite-shadow representation that meets ShadeDoomVK quality/correctness requirements.

## Autonomous execution prompt
Complete SDVK-012 after SDVK-008 and SDVK-009. Read all founding docs and use SDVK-002 diagnostics/reference scenes. This is a comparative research/implementation issue: do not predeclare alpha-card or ray-traced sprite geometry the winner. Dedicated branch → PR → required checks → merge → verify `master`.

## Required candidates
Evaluate at least:
- existing/blob/contact approximation;
- alpha-shaped projected sprite card;
- height/depth-influenced projected card;
- coarse proxy approach where useful;
- acceleration-structure sprite participation only if technically tractable enough for a fair bounded test.

## Measurements
- silhouette/mirror/rotation correctness;
- projection to floors/walls and interaction with world occluders;
- translucent/cutout behavior;
- portal/3D-floor limitations;
- softness/penumbra behavior;
- CPU/GPU/memory cost with many actors/lights;
- temporal stability while actors/camera move.

## Acceptance criteria
- At least alpha-card and depth-card prototypes are measured against the same fixtures.
- Candidate limitations are explicit; no raster method is mislabeled full RT sprite geometry.
- A preferred architecture plus fallback/LOD policy is selected from evidence, or the issue records why no candidate qualifies.
- Reproducible fixtures/results are committed.
- PR merged and verified on `master`.

## Dependencies
SDVK-008, SDVK-009.