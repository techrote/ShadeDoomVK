# SDVK-008 — Height/POM sprite relief and advanced PBR response

## Objective
Add bounded view-coherent pseudo-depth to sprite materials using SDVK-005 height semantics and SDVK-007 tangent orientation while preserving Doom sprite silhouettes/gameplay geometry and providing explicit quality/fallback behavior.

## Scope / required work
- Implement shallow parallax/POM/relief after stating algorithm hypotheses, step strategy, mip/filter assumptions and failure cases.
- Use canonical height semantics and explicit sprite basis/mirror state.
- Provide material depth scale/quality controls and no-height fallback.
- Prevent UV runaway, NaNs and relief outside alpha silhouette; handle grazing angles/distance with stable bounded work.
- Evaluate optional bounded height-driven self-occlusion only if measured/stable; keep it separable from later world sprite-cast shadows.
- Measure GPU cost by quality/workload and expose active algorithm/steps diagnostically.

## Non-goals
No true displacement/collision/silhouette geometry; no final projected sprite shadow architecture; no material-semantic redesign; no claim of ray-traced sprite geometry.

## Dependencies
SDVK-007.

## Concurrency guidance
SDVK-012 depends on this for depth-card comparison. May overlap SDVK-009/010/011 where files/interfaces are stable.

## Required context
Read `AGENTS.md`, SDVK-005/007 evidence, material/portal RAG, validation contract, SDVK-002 oracle and canonical body.

## Autonomous implementation prompt
Complete SDVK-008 autonomously. Define bounded relief contract/quality modes first; implement with accepted height+basis; add extreme/grazing/mirror tests and performance evidence; branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Relief view/light coherent on fixtures; mirrored/rotated sprites correct; extreme settings fail boundedly without NaN/UV explosion; alpha silhouette/gameplay geometry unchanged; no-height fallback equivalent; quality cost measured; PR merged/verified.

## Verification
Front/mirrored/rotated sprites, shallow/extreme depth, grazing angles, distance, alpha edges, missing height, moving camera/light and GPU timing/counters.

## Expected artifacts
Relief shader/material controls, diagnostics/tests, performance evidence, material/sprite RAG/docs and ledger updates.

## Blocking / stopping conditions
If POM cannot remain stable for a declared sprite mode/angle, use documented fallback/disable for that case rather than falsifying geometry or allowing unbounded work.
