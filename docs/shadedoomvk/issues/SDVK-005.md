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
