# SDVK-014 — Lightmapper, dynamic-lightmap and probe robustness campaign

## Purpose
Stress and harden inherited VKDoom baked/dynamic lighting infrastructure under ShadeDoomVK's richer material stack.

## Autonomous execution prompt
Complete SDVK-014 after SDVK-002, SDVK-005, SDVK-009 and SDVK-010. Read all founding docs and identify which lightmapper/probe fixes are already ancestral before coding. State corruption/leak/update hypotheses first. Dedicated branch → PR → required checks → merge → verify `master`.

## Required coverage
- static lightmap bake/load/delete round trip;
- AO/bounce/sunlight combinations;
- dynamic-lightmap updates and moving/changing sectors/lights where supported;
- atlas creation/rebuild/multiple atlas textures;
- probe map/index lifetime and transition behavior;
- decals with lightmaps;
- warped/reflective/translucent surfaces where supported;
- portal and Line_Horizon cases;
- level reload and resource cleanup.

## Acceptance criteria
- No stale atlas/probe/descriptor references in stress fixtures.
- Known light bleeding/update artifacts are either fixed or explicitly bounded/fallbacked.
- Lightmap/probe results remain compatible with semantic material changes.
- Heavy bake/update work has reproducible diagnostics and tractable CI smoke coverage.
- PR merged and verified on `master`.

## Dependencies
SDVK-002, SDVK-005, SDVK-009, SDVK-010.