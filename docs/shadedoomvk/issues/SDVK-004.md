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

## Implementation candidate — 2026-10-09

Dedicated branch: `sdvk-004-rich-material-descriptor-stress`. PR: #126.
Starting authority: verified `master@c8b6db4dedae5da27249b6738f7628cf3a41b80a`.

The candidate repairs one reproduced bounded-failure defect in PF-003 allocation:
an impossible positive span could grow exact-size free-bucket storage before the
span was proved to fit the configured dynamic range. The pre-bucket whole-range
guard preserves normal exact-size reuse.

Qualification adds a 576-material deterministic pressure model plus 64 probe
pairs (3,072/4,096 dynamic descriptors, 75% high-water), repeated
rebuild/invalidation/stale-token controls, fixed-page lightmap pressure,
near-capacity/device-limit failures, and production-path assertions for material,
sampler, canvas, lightmap/probe and observer integration. The existing native
material-stress corpus is extended with eight real PBR custom-shader texture
bindings and state assertions for their `custom` semantic.

Detailed candidate record:
[SDVK-004-DESCRIPTOR-STRESS.md](../SDVK-004-DESCRIPTOR-STRESS.md).

**Not accepted yet.** #4 remains open until the final PR head passes all required
CPU/source/build/software-Vulkan gates, merges, the exact resulting master passes
post-merge verification, and the durable release/RAG/ledger acceptance record is
landed.
