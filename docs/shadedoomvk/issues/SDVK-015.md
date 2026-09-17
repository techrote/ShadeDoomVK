# SDVK-015 — Doom-family compatibility and renderer regression campaign

## Objective
Demonstrate that the integrated enhanced renderer preserves the Doom-family content language it claims to support, with every discovered regression classified and minimized before performance tiers/defaults are frozen.

## Scope / required work
- Build on SDVK-002/PF fixtures rather than a new framework.
- Exercise classic IWAD-style maps/sprites/lighting, rotations/translations/mirroring, portals/groups, 3D floors/render hacks, decals, canvases/dynamic/translucent textures, warped materials, models/voxels/particles, bright/emissive materials, semantic PBR/height, probes/lightmaps, many lights, hybrid shadows and repeated save/load/level/resource rebuilds.
- Test Compatibility/enhanced feature fallbacks even before SDVK-016 names final tiers.
- Classify every regression as fixed, explicit enhanced-mode limitation/fallback, proven pre-existing baseline behavior, or unresolved blocker.
- Preserve minimized reproducers and machine-readable state/image evidence.
- Audit gameplay/demo determinism for render-only features.

## Non-goals
No performance-tier tuning (SDVK-016); no silent compatibility exception; no requirement to support impossible combinations without explicit fallback.

## Dependencies
SDVK-008, SDVK-011, SDVK-013, SDVK-014.

## Concurrency guidance
Late integration gate. Do not accept while dependencies are still changing relevant behavior. SDVK-016 waits for merge.

## Required context
Read `AGENTS.md`, PF freeze, all accepted SDVK feature evidence, validation contract/RAG and canonical body.

## Autonomous implementation prompt
Complete SDVK-015 autonomously. Run systematic compatibility matrix, minimize/classify failures, implement fixes or explicit fallbacks with tests, verify render-only determinism, branch→PR→checks→merge→verify `master`→RAG/ledger→close only when no unsupported silent regression remains.

## Acceptance criteria
Evidence-backed compatibility matrix; no known crash/corruption/resource-identity or silent major visual-semantic regression in declared supported defaults; unsupported enhanced combinations fall back explicitly; minimized reproducers retained; automated regression subset in CI; gameplay/demo semantics unchanged by render-only features; PR merged/verified.

## Verification
Synthetic + legally usable representative content patterns across the listed categories, repeated transitions/save-load, fallback hardware/capability states, demos/game-state checks and image/state diagnostics.

## Expected artifacts
Compatibility matrix, minimized regressions/fixes/fallbacks, CI suite updates, user/developer compatibility docs, RAG/ledger updates.

## Blocking / stopping conditions
Any unresolved silent corruption/crash, stale identity, materially wrong supported rendering semantics or gameplay determinism change blocks acceptance. Do not relabel it as a later performance/default issue.
