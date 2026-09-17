# SDVK-013 — Hybrid world + sprite shadows and contact grounding

## Purpose
Integrate the qualified sprite-caster path with VKDoom's LevelMesh world shadows/ray queries into one scalable lighting model.

## Autonomous execution prompt
Complete SDVK-013 after SDVK-012. Read all founding docs and the complete SDVK-012 evidence. Preserve non-ray-query fallback. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Implement the selected sprite shadow path and explicit quality/LOD modes.
- Combine it with world shadowmap/ray-query visibility without double-darkening or contradictory occlusion.
- Add robust contact bias/grounding and shadow-acne/light-leak controls.
- Support soft-shadow radius semantics where practical.
- Handle actor rotation/mirroring/height material consistently.
- Define distance/caster/light budgets and deterministic fallback when exceeded.
- Expose active shadow algorithms/LOD in diagnostics.

## Acceptance criteria
- World occluder → actor and actor → world cases both behave coherently.
- Shadow fallback works on hardware without optional ray-query features.
- Contact shadows ground actors without persistent acne/halo artifacts on reference fixtures.
- Dense-caster performance is measured and bounded by explicit budgets.
- PR merged and verified on `master`.

## Dependencies
SDVK-012.