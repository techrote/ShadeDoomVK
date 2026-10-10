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

## SDVK-008 off-GPU implementation checkpoint — 10 October 2026

- Starting exact accepted SDVK-007 master `adead010aa40d0f4f8d9ffdb51573005b7f9a964`. The complete nine readable prepass documents/reference/scripts are preserved byte-for-byte on dedicated branch `sdvk-008-bounded-sprite-relief`, with prepass-original ZIP/checksum remaining on `prepass/sdvk-008-relief@34b7a126249aec98168fc188ab113c374a034f80`. The prepass is research, **not earlier production implementation**.
- [Substantive default-OFF implementation PR #138](https://github.com/techrote/ShadeDoomVK/pull/138) integrates two append-only sprite-only `SurfaceUniforms`, optional 0..0.0200 UV depth, low/medium/high fixed traversal, existing height/basis semantic, alpha and frame-rect safeguards. `SDVKResolveSpriteReliefUV` never changes geometry, clip depth, gameplay, actor/sprite UV identity or custom material bindings; unproven/degenerate/transformed/NPOT/paletted routes fall back.
- Provisional controls `gl_sprite_relief_depth=0` and `gl_sprite_relief_quality=2` are **globally disabled by default**, and only active for qualifying authored height-bearing sprites. No self-occlusion, real displacement, shadows or #16 tier promises. The complete [integration contract](../SDVK-008-PRODUCTION-CONTRACT.md) and [off-GPU qualification report](../SDVK-008-OFFGPU-QUALIFICATION.md) describe math, affected symbols, tests, immutable draw diagnostics and limitations.
- The inherited ten-scene `sprite-mirror` software-Vulkan corpus now asserts **real emitted** height+specular sprite eligibility, signed UV/line mirror parity, explicit 10/15/23 max sample ceilings, and no-height PBR/legacy controls. The prepass 11 CPU tests/1620-case reference grid, new production CPU/negative contracts and full CI/software Vulkan form the **off-GPU** gate.
- **Hard remaining acceptance** is exact-build physical-GPU scene/image and quality/cost matrix following [preregistered protocol](../prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md). Do not close #8 or unblock #12 on the strength of source/host evidence. PR #138 passed the full off-GPU software-Vulkan matrix and was merged; the hardware gate remains outstanding and issue #8 must remain open.

## Bounded off-GPU merge reconciliation (10 October 2026)

Substantive implementation PR #138 is **merged at `master@9536324ce33ea418af5a8efe733b4659f6b4ad9b`**. The final integration head `6c0d418e82f34de89084b4175d8aafe0bc024e71` passed Renderer source evidence 38068791101 and full CI **38068790984 (9/9)**. The complete software-Vulkan corpus passed with both SDVK-010 actor probe and SDVK-008 height/POM assertions preserved. Tested tree and merged tree are identical (`3123bc7fd3dd9074487cbe3487f9336ef3589003`). Merge-push source-evidence run 38074510322 passed; full merge-push CI **38074510339 passed 9/9**, including the full native software-Vulkan corpus, on exactly the same merged SHA.

The [off-GPU qualification report](../SDVK-008-OFFGPU-QUALIFICATION.md) and [receipt](../SDVK-008-OFFGPU-RELEASE-ACCEPTANCE.json) pin artifact IDs/digests and historical failures. The implementation is default OFF. **Status: merged, off-GPU qualified, physical correctness/cost/quality pending. Issue #8 stays OPEN and #12 stays BLOCKED**. GitHub's automatic issue closure from the PR merge was reversed explicitly, not accepted as final sign-off.
