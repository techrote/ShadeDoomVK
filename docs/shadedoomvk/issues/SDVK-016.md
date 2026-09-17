# SDVK-016 — Performance tiers, budgets and adaptive quality policy

## Purpose
Turn ShadeDoomVK's renderer from a collection of expensive toggles into measured, understandable quality tiers.

## Autonomous execution prompt
Complete SDVK-016 after SDVK-015. Read `06-VALIDATION-PERFORMANCE-CONTRACT.md`, all predecessor evidence and current renderer diagnostics. Define workloads/hardware-capability predicates before choosing defaults. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Measure representative CPU/GPU/frame-time percentiles, memory/descriptor pressure and effect work counts at fixed resolutions/scenes.
- Define Compatibility, Enhanced and High (or evidence-backed equivalent) tiers with concrete algorithm switches.
- Include POM step/depth policy, shadow caster/LOD/resolution budgets, ray-query fallback, dynamic-light limits/culling behavior and probe/lightmap quality.
- Detect unsupported optional Vulkan features and select safe fallback without unexplained crash.
- Expose active tier and downgraded features in diagnostics.
- Avoid hard-coding one vendor/device as the only performance truth; record exact test hardware/driver when measuring.

## Acceptance criteria
- Every tier corresponds to documented algorithm/resource changes.
- Representative scenes have measured budgets and no unexplained catastrophic frame spikes in declared operating range.
- Unsupported hardware receives explicit fallback.
- Diagnostics identify active/downgraded features.
- PR merged and verified on `master`.

## Dependencies
SDVK-015.