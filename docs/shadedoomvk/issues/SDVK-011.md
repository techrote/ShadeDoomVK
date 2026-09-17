# SDVK-011 — First-person viewmodel lighting and material parity

## Objective
Make first-person weapon sprites/models participate coherently in the accepted world lighting/material language while preserving explicit legacy compatibility modes and respecting viewmodel projection differences.

## Scope / required work
- Consume SDVK-009 many-light architecture and SDVK-010 environment semantics.
- Define explicit viewmodel lighting modes such as legacy, sector-faithful and world/probe/PBR, with diagnostics.
- Apply local lights/probes/sun/sector state coherently where meaningful for weapon sprites/models.
- Support semantic normal/PBR weapon materials using accepted material/TBN behavior where technically valid.
- Ensure muzzle/local-light response is stable and does not alter gameplay.
- Account for HUD/viewmodel projection: do not apply impossible world-space POM/shadow assumptions blindly.
- Use MAD viewmodel-light work as problem evidence/provenance, not mandated UI design.

## Non-goals
No gameplay recoil/timing changes; no world actor shadow architecture; no requirement that legacy weapons use PBR; no fake geometric claims for HUD projection.

## Dependencies
SDVK-009, SDVK-010.

## Concurrency guidance
May overlap SDVK-008/012 prototyping on separate code, but SDVK-015 waits for accepted viewmodel behavior.

## Required context
Read `AGENTS.md`, SDVK-009/010 evidence, PF/SDVK material/lighting/view RAG, donor provenance, SDVK-002 oracle and canonical body.

## Autonomous implementation prompt
Complete SDVK-011 autonomously. Define compatibility modes, implement enhanced viewmodel lighting/material parity with projection-aware limitations, preserve legacy mode, add fixtures/diagnostics, branch→PR→checks→merge→verify `master`→RAG/provenance/ledger→close.

## Acceptance criteria
Legacy mode preserves inherited behavior; enhanced modes are explicit/diagnosable; dynamic lights/probes/sun/material response coherent with world semantics where applicable; muzzle lights stable/render-only; unsupported projection effects fall back explicitly; PR merged/verified.

## Verification
Dark/bright rooms, colored/moving lights, probe boundaries, sunlight, muzzle flash, translated/normal/PBR weapon sprites/models, legacy comparison and varying FOV/viewmodel offsets.

## Expected artifacts
Viewmodel lighting modes/implementation, fixtures/diagnostics/docs, donor/RAG/ledger updates.

## Blocking / stopping conditions
If a world-space effect has no defensible viewmodel-space interpretation, keep it disabled/fallback in that mode rather than forcing visual parity by incorrect math.
