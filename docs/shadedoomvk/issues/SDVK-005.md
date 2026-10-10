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


## Verified acceptance — 2026-10-10

**SDVK-005 substantive implementation is accepted, merged and verified.**

- Final implementation PR: #132.
- Final head: `9a87734357d15145ed791d89c4b98db94fb60cb6`.
- Tested PR merge ref: `116a45bf47dc4595ead106ce99588723750d4d5d`.
- Tested tree: `28f2ef41a99ea6979145030e807c7798c6e01735`.
- Merge/resulting master: `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`.
- Merged tree: `28f2ef41a99ea6979145030e807c7798c6e01735`; exact tree equality: PASS.
- PR-head source evidence run `38030309310`: PASS.
- PR-head CI run `38030309307`: 9/9 PASS including software Vulkan.
- Exact merged-master source evidence run `38032400496`: PASS.
- Exact merged-master CI run `38032400505`: 9/9 PASS including software Vulkan.
- Height remains optional and output-neutral for stock shading; historical fixed/custom bindings remain unchanged; indexed/palette routes omit height; mixed nearest albedo + filtered normal/PBR/height sampling is natively asserted.
- No physical-GPU gate was required or claimed.

Retained failures/anomalies are preserved in [SDVK-005 final acceptance](../SDVK-005-FINAL-ACCEPTANCE.md) and [release receipt](../SDVK-005-RELEASE-ACCEPTANCE.json). Acceptance reconciliation PR #134 is documentation-only. After that reconciliation itself merges and its resulting master is verified, close #5 and treat SDVK-007 / #7 as dependency-ready.
