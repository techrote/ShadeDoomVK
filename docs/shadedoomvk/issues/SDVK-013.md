# SDVK-013 — Hybrid world + sprite shadows and contact grounding

## Objective
Integrate the evidence-selected SDVK-012 sprite-caster representation with the PF-correct world shadowmap/ray-query system into one scalable, diagnosable model with robust contact grounding and explicit fallbacks.

## Scope / required work
- Implement the selected SDVK-012 architecture and its fallback/LOD policy; do not silently substitute a rejected candidate.
- Combine actor→world casting with world→actor visibility without double-darkening or contradictory occlusion.
- Consume PF-015 deterministic shadow-slot/caching semantics and SDVK-008 height/orientation where applicable.
- Add contact bias/grounding, softness/penumbra controls and acne/light-leak prevention.
- Handle sprite mirror/rotation, portal groups, receivers, 3D-floor limitations and translucent/cutout policy as declared by SDVK-012.
- Define distance/caster/light budgets and deterministic overflow/fallback; expose active caster/shadow algorithm and LOD diagnostics.
- Preserve hardware path without optional ray query.

## Non-goals
No re-selection of SDVK-012 architecture without new evidence; no world lighting recalibration; no claim raster cards are RT geometry; no general model shadow rewrite unless explicitly selected.

## Dependencies
SDVK-012.

## Concurrency guidance
This consumes SDVK-012 serially. SDVK-015 waits for integrated shadow behavior. May overlap SDVK-014 on stable separate paths with coordination.

## Required context
Read `AGENTS.md`, PF-015 evidence, SDVK-008/012 decision/evidence, lighting/portal/material RAG, SDVK-002 oracle and canonical body.

## Autonomous implementation prompt
Complete SDVK-013 autonomously. Implement the selected actor-caster path with world occlusion, contact/softness and explicit budgets/fallback; validate portal/mirror/dense scenes and no-ray hardware; branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
World→actor and actor→world shadows compose coherently; no double-darkening contradiction; contact grounding stable; mirror/rotation/height semantics correct for declared path; dense caster work bounded; ray-query absence has explicit fallback; diagnostics identify path/LOD; PR merged/verified.

## Verification
World occluders, actor casts on floors/walls, motion, contacts, soft radius, mirrors/portals/3D floors, alpha/cutout, dense lights/casters, ray/no-ray configurations and image/state/performance evidence.

## Expected artifacts
Integrated shadow implementation, fallback/LOD/budget policy, diagnostics/tests/benchmarks, lighting/portal RAG/docs and ledger updates.

## Blocking / stopping conditions
If SDVK-012 has no accepted candidate or integration exposes a fundamental receiver/portal correctness failure, stop and reopen/replan the architecture rather than merging a degraded approximation as default.
