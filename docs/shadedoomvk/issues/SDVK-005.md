# SDVK-005 — Semantic material authoring, height channel and per-layer policy

## Objective
Extend PF-008's explicit existing material semantics with a first-class **height** channel and stable authoring/color-space/sampling/mip/fallback policy suitable for later sprite relief.

## Scope / required work
- Consume PF-008 semantic material model and inherited `MaterialLayerSampling`; do not re-port per-layer sampling.
- Add height as a named optional semantic through parser/authoring/material/descriptor/shader interfaces, with graceful absence/default.
- Define color-space/data interpretation for all semantic channels and evidence-backed default sampling/mip/wrap behavior, retaining compatibility overrides.
- Ensure precache, descriptor generation/invalidation and custom/global shader interactions include height safely.
- Add material-authoring docs and fixtures where crisp pixel albedo coexists with filtered normal/height/PBR data.
- Preserve legacy/specular/PBR materials and custom shader compatibility.

## Non-goals
No final POM/relief algorithm (SDVK-008); no explicit sprite TBN (SDVK-007); no lighting recalibration; no requirement that existing mods add height maps.

## Dependencies
SDVK-004.

## Concurrency guidance
SDVK-007 waits for accepted semantics. May overlap SDVK-006/009 when files do not conflict.

## Required context
Read `AGENTS.md`, PF-008/PF-013/PF-003 evidence, material/identity RAG, SDVK-004 results and canonical body.

## Autonomous implementation prompt
Complete SDVK-005 autonomously. Extend the accepted semantic material system with optional height authoring/data policy, preserving inherited sampling and legacy behavior; add docs/tests; branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Height is a first-class optional semantic from authoring to shader binding; channel color-space/sampler/mip policies documented; albedo can remain pixel-crisp while normal/height use their policy; legacy/custom materials remain compatible; no stale descriptor regression; PR merged/verified.

## Verification
Albedo-only, legacy normal+specular, PBR, height-present/absent/invalid, pixel-albedo+filtered-data, translated/custom/global shader and descriptor rebuild fixtures.

## Expected artifacts
Height semantic/authoring support, semantic defaults/docs, fixtures/tests, material RAG/ledger updates.

## Blocking / stopping conditions
If height cannot be added without breaking existing layer bindings/custom shaders, introduce an explicit compatibility adapter/versioned authoring extension rather than changing old semantics silently.


## Implementation candidate — 2026-10-10

Dedicated branch `sdvk-005-height-semantic` starts from `master@0a2fbad203549d18ac6e5a61bb4747709637bfde`. The design is recorded in [SDVK-005-MATERIAL-HEIGHT.md](../SDVK-005-MATERIAL-HEIGHT.md). Height is appended after all historical fixed/material/global custom bindings and exposed through a dynamic semantic index; existing 5/7/9 custom bindings do not move. The stock material path does not sample height. Existing semantic channels retain their defaults while the author may opt into per-layer nearest/linear sampling. Indexed/palette routes omit height to preserve palette semantics.

Acceptance remains pending exact-head CPU/software-Vulkan/hosted CI, merge and exact resulting-master verification. No physical-GPU gate is implied absent a reproduced hardware-specific defect.


## Final acceptance — 2026-10-10

**ACCEPTED, MERGED AND VERIFIED.** Substantive PR #132 final head `9a87734357d15145ed791d89c4b98db94fb60cb6` qualified on tested merge ref `116a45bf47dc4595ead106ce99588723750d4d5d`; source evidence and Continuous Integration passed, including the complete software-Vulkan state/image corpus. It squash-merged as `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`. The merged tree `28f2ef41a99ea6979145030e807c7798c6e01735` exactly equals the qualified PR tree, and exact merged-master source evidence run `38032400496` plus CI run `38032400505` passed **9/9**.

Height is a compatibility-preserving optional semantic: existing fixed/custom bindings do not move, height appends last, indexed/palette routes omit it, the stock material path remains height-neutral, and custom/later shaders may explicitly consume it. Native material-stress and sprite-mirror state evidence verifies actual height descriptor bindings and independent sampler policy on drawn materials. PF-002/PF-003/SDVK-004 descriptor identity/lifetime ownership remains unchanged.

Final human-readable and machine-readable evidence is in [SDVK-005-FINAL-ACCEPTANCE.md](../SDVK-005-FINAL-ACCEPTANCE.md) and [SDVK-005-RELEASE-ACCEPTANCE.json](../SDVK-005-RELEASE-ACCEPTANCE.json). No physical-GPU gate remains for SDVK-005. Once this acceptance reconciliation itself is merged and verified, #5 closes and **SDVK-007 is dependency-ready**.
