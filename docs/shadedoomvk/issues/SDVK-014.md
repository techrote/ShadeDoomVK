# SDVK-014 — Lightmapper, dynamic-lightmap and probe robustness campaign

## Objective
Stress and harden the integrated lightmapper/dynamic-lightmap/probe system after PF-012 establishes correct/basic probe plumbing and SDVK material/many-light/actor-environment semantics are in place.

## Scope / required work
- Stress static bake/load/delete round trips, AO/bounce/sun combinations and dynamic-lightmap updates.
- Cover moving/changing sectors/lights/polyobjects where supported, atlas create/repack/rebuild across multiple pages and repeated level/resource transitions.
- Stress probe-map/index lifetime, environment cubemap reset/rebake and transitions using PF-012/SDVK-010 semantics.
- Cover decals, warped/reflective/translucent surfaces, portals/Line_Horizon/3D-floor interactions where supported.
- Verify semantic material/height additions do not corrupt baked/dynamic lightmap state.
- Measure heavy bake/update CPU/GPU/memory/upload behavior and preserve tractable CI smoke subset.
- Classify all discovered failures as fix, explicit fallback/limitation, baseline incompatibility or blocker.

## Non-goals
No reinvention of PF probe-map selection; no actor IBL policy redesign; no speculative global illumination claim; no hidden quality reduction to make dynamic updates cheap.

## Dependencies
SDVK-002, SDVK-005, SDVK-009, SDVK-010.

## Concurrency guidance
May overlap late SDVK-012/013 work on separate paths with coordination. SDVK-015 waits for acceptance.

## Required context
Read `AGENTS.md`, PF-004/PF-012 evidence, SDVK dependency evidence, LevelMesh/probe/material/lighting RAG, validation contract and canonical body.

## Autonomous implementation prompt
Complete SDVK-014 autonomously. Build an integrated stress matrix, reproduce/fix lifetime/update/light-leak failures or establish explicit fallback, measure bake/update costs, keep CI smoke coverage, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
No stale atlas/probe/descriptor identity in stress; dynamic geometry/light updates produce current state; known light bleeding/update issues fixed or bounded/fallbacked; semantic material/height paths compatible; bake/update diagnostics and CI smoke exist; PR merged/verified.

## Verification
Bake/load/delete; AO/bounce/sun matrix; dynamic sector/light/polyobject changes; multi-page atlases; probe reset/rebake; decals/warps/translucency/portals/3D floors; repeated level transitions; timing/memory/upload counters.

## Expected artifacts
Stress corpus/results, fixes/fallbacks, bake/update diagnostics/benchmarks, lightmap/probe/LevelMesh RAG/docs and ledger updates.

## Blocking / stopping conditions
If a PF foundational lifetime/selection invariant regresses, classify/block upstream rather than adding local compensating hacks. Do not close with an unexplained visually plausible stale result.
