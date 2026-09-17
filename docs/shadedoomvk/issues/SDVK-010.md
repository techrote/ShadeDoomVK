# SDVK-010 — Probe/environment lighting qualification for actors

## Purpose
Qualify and harden the inherited probe/environment/sunlight path under ShadeDoomVK's explicit sprite materials.

## Autonomous execution prompt
Complete SDVK-010 after SDVK-002 and SDVK-007. Read all founding docs and first determine which probe-map/AABB-tree/sunlight-specular features are already ancestral to current `master`; do not re-port them. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Test probe assignment/selection/weighting across sector and spatial boundaries.
- Validate diffuse ambient and prefiltered/specular environment response on sprite PBR materials.
- Validate sunlight diffuse/specular and world occlusion interaction.
- Reproduce/fix light bleeding or abrupt probe transitions exposed by deterministic scenes.
- Ensure probe indices/lifetimes remain safe across level/lightmap rebuilds.
- Document behavior when probe data is absent or disabled.

## Acceptance criteria
- Actor probe/environment response is predictable, diagnosable and orientation-correct.
- Boundary/light-leak fixtures have explicit expected results.
- No ancestral feature is redundantly reimplemented.
- Fallback without probes remains compatible.
- PR merged and verified on `master`.

## Dependencies
SDVK-002, SDVK-007.