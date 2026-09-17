# SDVK-016 — Performance tiers, budgets and adaptive quality policy

## Objective
Convert the qualified renderer into measured, understandable compatibility/enhanced/high-end quality tiers and hardware fallbacks, using SDVK-015 compatibility evidence without disguising correctness/performance problems as quality settings.

## Scope / required work
- Measure representative CPU/GPU frame-time distributions, memory/descriptor pressure and effect work counts at fixed resolutions/scenes/hardware capability states.
- Define evidence-backed user-facing tiers with concrete algorithm/resource switches for POM, shadow caster/LOD/resolution, ray-query use/fallback, many-light architecture/overflow and probe/lightmap quality.
- Keep PF output-equivalent optimizations always-on where safe rather than presenting them as quality reductions.
- Detect unsupported optional Vulkan capabilities through PF-007 registry and choose explicit fallbacks.
- Define budgets/adaptive downgrade rules only where changes are transparent/diagnosable and compatibility matrix permits them.
- Expose active tier, algorithm, budget pressure and downgrade/fallback reasons.
- Record exact test hardware/driver/build; avoid vendor-specific default conclusions from one machine.

## Non-goals
No new headline rendering feature; no silent quality downgrade; no using average FPS alone; no hiding unresolved compatibility defects behind a lower tier.

## Dependencies
SDVK-015.

## Concurrency guidance
Serial after compatibility campaign. SDVK-017 waits for accepted tier/default evidence.

## Required context
Read `AGENTS.md`, validation contract, PF-007/PF performance evidence, SDVK-009/013/015 results, Vulkan/HDR/lighting RAG and canonical body.

## Autonomous implementation prompt
Complete SDVK-016 autonomously. Define workloads/capability predicates first, measure algorithm costs, formulate concrete tiers/budgets/fallbacks, verify unsupported hardware behavior and compatibility, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Every tier maps to concrete algorithm/resource changes; representative workloads have measured budgets/percentiles; unsupported hardware uses explicit fallback; adaptive downgrades are diagnosable/deterministic enough for their purpose; no correctness defect is relabeled a tier; PR merged/verified.

## Verification
Documented hardware/capability matrix; fixed-resolution reference scenes; percentile CPU/GPU/memory/resource counts; force capability absence/overflow; transition/downgrade diagnostics; compatibility/image checks.

## Expected artifacts
Tier/budget policy, hardware/capability evidence, diagnostics/UI/config integration as appropriate, performance report, user/developer docs/RAG/ledger.

## Blocking / stopping conditions
If a tier cannot meet its declared budget without silent semantic corruption or an unsupported hardware state has no safe fallback, leave the tier/default unresolved and block SDVK-017 rather than lowering truthfulness.
