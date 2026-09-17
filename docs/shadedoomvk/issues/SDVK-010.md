# SDVK-010 — Probe/environment lighting qualification for actors

## Objective
Qualify actor/sprite environment lighting, sunlight and PBR IBL on top of PF-012's corrected/bounded probe plumbing and SDVK-007's accepted orientation basis.

## Scope / required work
- Consume PF-012 truth about sector/side probe targets, per-lightmap probe maps, probe-0 fallback and AABB integration; do not re-port ancestral probe features.
- Validate actor probe assignment/selection at sector/spatial/portal boundaries and during movement.
- Validate diffuse irradiance and prefiltered/specular response on semantic PBR sprite materials with orientation-correct normals.
- Validate sunlight diffuse/specular and world-occlusion interaction using accepted PF visibility semantics.
- Investigate/fix actor-specific abrupt transitions, light bleeding or stale probe identity exposed by deterministic scenes.
- Define explicit actor fallback when probes are absent, incomplete or disabled.
- Expose probe source/index/transition/fallback diagnostics.

## Non-goals
No foundational probe-map plumbing repair (PF-012), no complete lightmapper stress campaign (SDVK-014), no new GI claim, no viewmodel policy (SDVK-011).

## Dependencies
SDVK-002, SDVK-007. PF-012 is inherited via PF-020.

## Concurrency guidance
May overlap SDVK-008/009. SDVK-011 and SDVK-014 depend on its accepted actor/environment semantics.

## Required context
Read `AGENTS.md`, PF-012 evidence, probe/lightmap/portal/material RAG, SDVK-002/007 evidence and canonical body.

## Autonomous implementation prompt
Complete SDVK-010 autonomously. Start from corrected PF probe plumbing, qualify actor assignment/IBL/sun/occlusion/fallback on deterministic scenes, fix only demonstrated actor-environment defects, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Actor probe/environment response predictable/diagnosable and orientation-correct; boundary/portal fixtures have explicit expected assignment/transitions; sunlight/occlusion coherent; stale probe identity absent during rebuild/movement; fallback compatible; PR merged/verified.

## Verification
Move actors across sectors/probe boundaries/linked portals; metallic/rough/dielectric normal-mapped sprites; sunlight occlusion; probe absence/reset; compare diagnostics/images.

## Expected artifacts
Actor probe/environment qualification fixes/tests, transition/fallback contract, diagnostics, probe/material RAG and ledger updates.

## Blocking / stopping conditions
If PF-012 plumbing is found unsound, classify as foundational regression and block this issue rather than compensating in actor shading. Do not invent interpolation/blending aesthetics without a documented design decision.
