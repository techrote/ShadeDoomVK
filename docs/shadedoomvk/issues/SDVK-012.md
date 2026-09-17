# SDVK-012 — Sprite shadow-caster comparative prototype

## Objective
Select the simplest sprite-shadow representation that meets ShadeDoomVK correctness/quality/scalability requirements on top of PF-015-correct world shadow/visibility semantics.

## Scope / required work
- Use one SDVK-002 oracle to compare inherited/simple contact/blob behavior, alpha projected card, height/depth-influenced card, coarse proxy and bounded acceleration-structure sprite participation where tractable.
- Consume SDVK-008 height/basis semantics for depth-card candidates and PF-015 deterministic world-shadow/caching behavior.
- Measure silhouette/mirror/rotation correctness, floor/wall receivers, world occluders, portals/3D floors, translucent/cutout behavior, softness, temporal stability, CPU/GPU/memory and dense actor/light scaling.
- Keep candidate implementations isolated enough to remove/reject without contaminating production paths.
- Select architecture/fallback/LOD from evidence, or commit a no-qualified-candidate decision with explicit blockers.

## Non-goals
No predetermined raster/RT winner; no claim projected cards are full ray-traced sprite geometry; no final production integration/defaults (SDVK-013); no unrelated world-shadow redesign.

## Dependencies
SDVK-008, SDVK-009. PF-015 inherited via PF-020.

## Concurrency guidance
Comparative prototypes may overlap SDVK-011/014 research on separate code. SDVK-013 waits for accepted result.

## Required context
Read `AGENTS.md`, PF-015 evidence, SDVK-002/008/009 evidence, lighting/portal/material RAG and canonical body.

## Autonomous implementation prompt
Complete SDVK-012 autonomously as comparative research. Implement at least alpha-card and depth-card prototypes plus cheap baseline; evaluate with same fixtures/metrics; include tractable proxy/AS candidate; commit evidence/decision; branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
At least alpha/depth cards measured consistently; limitations truthful; portal/mirror/receiver behavior explicit; performance/temporal data recorded; architecture + fallback/LOD selected from evidence or no-candidate blocker committed; PR merged/verified.

## Verification
Rotations/mirrors, alpha/cutout/translucency, moving actor/light/camera, floors/walls/world occluders, linked portals/3D floors, dense caster/light scenes and optional ray-query/no-ray hardware paths.

## Expected artifacts
Prototype implementations/branches or gated code, comparative report, captures/state/benchmarks, architecture decision, RAG/ledger updates.

## Blocking / stopping conditions
Do not choose a visually impressive candidate that fails portal/correctness/budget criteria. A well-evidenced no-candidate outcome is valid and must block/replan SDVK-013.
