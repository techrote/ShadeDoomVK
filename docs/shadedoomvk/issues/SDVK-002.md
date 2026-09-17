# SDVK-002 — Renderer observability, reference scenes and benchmark harness

## Objective
Expand the PF hardening oracle into the durable renderer reference/diagnostic/benchmark system used by all later SDVK feature work.

## Scope / required work
- Consume PF-001/PF-020 fixtures/diagnostics rather than replacing them.
- Build a compact deterministic corpus for sprite rotations/mirroring, semantic materials, lights/occlusion, probes/sun, portals/views, decals/canvas/translucency, shadows and resource stress.
- Standardize machine-readable renderer state: context, semantic layers/samplers, selected/rejected lights, probe mode/index, shadow mode/caster, generations/resource counters, pipeline identity and CPU/GPU timing where available.
- Add fixed-camera capture and documented exact/tolerant image comparison.
- Establish repeatable benchmark workloads/percentiles and evidence manifest format.
- Preserve minimized PF negative fixtures and extend them as SDVK defects appear.

## Non-goals
No material/lighting/shadow feature implementation; no replacement of PF safety checks; no benchmark claims from average FPS alone.

## Dependencies
SDVK-001.

## Concurrency guidance
May proceed in parallel with SDVK-003. Later SDVK-004/006/009/014 depend on this durable oracle.

## Required context
Read `AGENTS.md`, PF freeze manifest/evidence, `06-VALIDATION-PERFORMANCE-CONTRACT.md`, all relevant RAG, current diagnostics/tests and canonical body.

## Autonomous implementation prompt
Complete SDVK-002 autonomously. Extend the accepted PF oracle into a maintainable deterministic corpus/diagnostic/benchmark harness; preserve old evidence where still valid; branch→tests/docs→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Later issues can inspect material/light/probe/shadow/resource/view state without ad-hoc instrumentation; deterministic corpus covers declared classes; image comparison policy documented; tractable subset runs in CI; benchmark outputs include repeatable timings/counters; PR merged/verified.

## Verification
Run corpus twice from clean state; compare state/captures; exercise CI subset; collect CPU/GPU/counter baseline on documented workloads.

## Expected artifacts
Reference scenes/fixtures, diagnostics schema, capture/comparison tooling, benchmark definitions/results format, developer docs, RAG/ledger updates.

## Blocking / stopping conditions
Stop if a proposed golden method is inherently unstable across supported hardware/drivers without state-based fallback; do not make CI depend on fragile exact pixels when tolerance/state assertions are required.
