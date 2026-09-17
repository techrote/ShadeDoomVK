# SDVK-002 — Renderer observability, reference scenes and benchmark harness

## Purpose
Create the objective renderer oracle used by every later material/light/shadow/performance issue.

## Autonomous execution prompt
Complete SDVK-002 after SDVK-001. Read `AGENTS.md`, all founding docs under `docs/shadedoomvk/`, SDVK-001 evidence, and current `master`. Define diagnostic schema, deterministic fixture rules and falsification criteria before implementation. Work on a dedicated branch; PR; repair required CI; merge only after checks pass; verify `master`; close only when criteria hold.

## Required work
- Build a compact deterministic renderer reference corpus covering sprite rotations/mirroring, lights/occlusion, probes/sun, legacy and PBR materials, portals, decals/canvas/translucency and resource stress.
- Add machine-readable diagnostics for active renderer/features, material layers, selected/rejected lights, probe, shadow mode, descriptor usage and timings where available.
- Add fixed-camera capture support or an equivalent repeatable visual-evidence mechanism.
- Pair image evidence with state assertions; do not rely on subjective screenshots alone.
- Establish repeatable CPU frame measurement and GPU timing where backend support permits.
- Preserve minimized negative fixtures for wrong light selection, stale resources and tangent/mirror errors as they are discovered.

## Acceptance criteria
- Corpus and diagnostics run deterministically enough for CI/regression use.
- Later issues can measure selected lights/material semantics/resource counters without ad-hoc instrumentation.
- At least one positive and negative fixture exists for major scene categories in `06-VALIDATION-PERFORMANCE-CONTRACT.md`.
- CI exercises a tractable deterministic subset.
- PR merged and verified on `master`.

## Dependencies
SDVK-001.