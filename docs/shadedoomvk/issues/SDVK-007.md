# SDVK-007 — Explicit sprite-space tangent basis and normal-map conformance

## Objective
Use PF-009's canonical sprite orientation state to make normal/specular/PBR tangent-space response correct across Doom rotations, mirrored frames, billboard modes and portal mirrors before height relief is enabled.

## Scope / required work
- Define explicit sprite-local right/up/forward and handedness from PF-009 state.
- Feed/derive a stable tangent basis for sprite materials instead of relying solely on derivative reconstruction where that is insufficient.
- Correct mirrored-frame and portal-mirror handedness; cover actor rotations, 8/16-direction frames where applicable, face/wall/flat sprites and roll/pitch paths.
- Keep geometry surfaces/models on their appropriate existing tangent paths.
- Add tangent/normal debug visualization/state and positive/negative fixtures.
- Preserve un-normal-mapped legacy sprite output.

## Non-goals
No height/POM; no material-authoring redesign; no shadow-caster implementation; no global world-surface tangent rewrite unless a reproduced shared defect requires a separate issue.

## Dependencies
SDVK-005. PF-009/PF-014 are inherited prerequisites via PF-020.

## Concurrency guidance
SDVK-008 waits for merge. SDVK-010 also waits because actor IBL/specular orientation must use the accepted basis.

## Required context
Read `AGENTS.md`, PF-009/PF-014 evidence, material/portal RAG, SDVK-005 semantics, SDVK-002 fixtures and canonical body.

## Autonomous implementation prompt
Complete SDVK-007 autonomously. State tangent/handedness contract first, implement sprite-only explicit basis with compatibility fallback, validate rotations/mirrors/portal contexts and specular/normal response, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Reference normal lobes and specular highlights rotate/mirror correctly across declared sprite cases; portal mirror handedness correct; legacy un-normal-mapped sprites unchanged within tolerance; geometry/model tangent paths unaffected; automated positive/mirrored-negative fixtures pass; PR merged/verified.

## Verification
Fixed directional normal-map test, mirrored frames, multiple rotations, face/wall/flat modes, roll/pitch where supported, mirror/linked portal, specular motion and legacy comparisons.

## Expected artifacts
Sprite tangent-basis implementation, diagnostics/fixtures, authoring/orientation docs, material/portal RAG and ledger updates.

## Blocking / stopping conditions
If a sprite mode lacks enough stable orientation information, preserve derivative/legacy fallback for that mode and document the limitation rather than inventing arbitrary tangent orientation.

## Implementation reconciliation (10 October 2026)

Dedicated branch `sdvk-007-explicit-sprite-tangent-basis` and substantive [PR #135](https://github.com/techrote/ShadeDoomVK/pull/135) consume accepted SDVK-005 and PF-009/014 on starting master `cbff1d10b802e60a56d239338f810f7e1e52920d`. The pre-implementation trace, negative baseline, axes, signed-UV/mirror parity, and explicit fallback are documented in [SDVK-007-BASIS-ARCHITECTURE.md](../SDVK-007-BASIS-ARCHITECTURE.md).

Implementation derives the single sprite TBN from `HWSprite::CalculateVertices`' **final quad**, not duplicated actor/view angles. It appends two per-surface vectors without disturbing height, GLDEFS, or material binding ownership. Actor/particle/mirrored sprite orientation uses final signed UVs; portal parity remains an independent PF-010 context property. Only sprite normal-map shading selects the new TBN. Degenerate cards fall back; world/model/LevelMesh paths retain inherited derivative logic. A read-only `sprite-basis` record couples PF-009 selection to the uniform of a **submitted Vulkan draw**, with strict finite/orthogonal/parity validation.

The deterministic fixture uses unequal directional normal components, rotation/mirror/flip combinations and 3D camera transformations. The pre-existing sprite-mirror scene now includes directional normal, legacy normal/specular, PBR, height-without-relief and un-normal-mapped controls. This description is implementation progress, **not** acceptance: exact-head CI, complete native software Vulkan, final merge verification and the release receipt must all pass before the issue is closed.
