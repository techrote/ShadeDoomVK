# SDVK-004 — Rich-material descriptor integration and lifetime stress qualification

## Objective
Qualify the PF-hardened descriptor/lifetime system under the larger, more varied material/lightmap/probe workloads that the SDVK feature programme is about to introduce, and reconcile any current-upstream integration changes found by SDVK-003.

## Scope / required work
- Consume PF-002/PF-003 lifetime/capacity/reservation contracts and SDVK-002 diagnostics; do not reinvent slot reuse.
- Stress many unique semantic material variants, translations/palette modes, custom shaders, canvases, lightmap/probe pages and repeated level/resource rebuilds.
- Exercise descriptor generation/reset behavior across sampler/material invalidation and current upstream changes accepted by SDVK-003.
- Verify effective device-limit behavior across capability fixtures/hardware where available.
- Repair integration/lifetime defects exposed by the richer workload and add minimized regressions.
- Establish descriptor-pressure budget/counters consumed by SDVK-005/016.

## Non-goals
No new height/POM authoring; no global unsafe flush; no arbitrary limit inflation; no repeat of PF allocator architecture absent a newly reproduced defect.

## Dependencies
SDVK-002, SDVK-003. PF-002/PF-003 are inherited prerequisites via PF-020.

## Concurrency guidance
May overlap SDVK-006/009 after SDVK-002/003, but SDVK-005 waits for it. Coordinate any upstream descriptor changes with SDVK-003 evidence.

## Required context
Read `AGENTS.md`, PF freeze, PF-002/PF-003 evidence, identity/material/Vulkan RAG, SDVK-002/003 evidence and canonical body.

## Autonomous implementation prompt
Complete SDVK-004 autonomously. Stress the accepted PF descriptor contracts with the forthcoming rich-material workload, repair only demonstrated integration defects, record pressure/budgets, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
No stale/mismatched descriptor resolution under stress; reservations/capacity remain safe with rich material/probe/lightmap usage; reset/rebuild generations behave correctly; pressure diagnostics/budget documented; upstream-integrated behavior covered; PR merged/verified.

## Verification
High unique-material counts; translations/palette/custom shader variants; canvas resize/recreate; multi-page lightmap/probe; repeated level transitions; near-capacity devices/mocks; PF/SDVK image/state equivalence.

## Expected artifacts
Stress fixtures/results, integration fixes if needed, descriptor-pressure baseline/budget, RAG/ledger updates.

## Blocking / stopping conditions
If PF lifetime invariants fail, open/reclassify a foundational regression and block SDVK-005 rather than patching around it with a flush or silent resource reduction.
