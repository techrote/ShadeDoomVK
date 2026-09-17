# SDVK-017 — Integrated renderer synthesis, defaults and first ShadeDoomVK freeze

## Objective
Consume the complete PF and SDVK founding programme and decide, fail-closed, whether the first ShadeDoomVK renderer tranche is ready to freeze with truthful defaults, fallbacks, documentation and evidence.

## Scope / required work
- Inspect current `master`, PF freeze manifest, every SDVK issue/PR/report/fixture and complete relevant open/closed issue set.
- Build an evidence matrix mapping founding invariants/features/fallbacks/performance claims to merged implementation/tests.
- Rerun decisive compatibility/performance/resource/material/light/probe/shadow/view fixtures when evidence is stale or contradictory.
- Freeze semantic material/height/tangent behavior and authoring contract.
- Freeze actor/probe/viewmodel lighting modes and many-light architecture.
- Freeze world+sprite shadow architecture, quality tiers/budgets/fallbacks and defaults.
- Re-audit descriptor/LevelMesh/atlas/probe/light/resource lifetime under final composition.
- Reconcile donor/upstream provenance and all RAG/canonical docs with final source.
- Set defaults conservatively from evidence; high-end optional features need not become default.
- Create versioned renderer freeze/release manifest naming exact commit, tests, tier defaults and known limitations.

## Non-goals
No new feature added solely to make the freeze impressive; no waiver of unresolved corruption/compatibility blockers; no claim approximate effects are true geometry/GI/RT when they are not.

## Dependencies
SDVK-001 through SDVK-016 all accepted, merged and verified. PF-020 freeze remains foundational provenance.

## Concurrency guidance
Serial final gate. No concurrent renderer implementation affecting freeze contracts.

## Required context
Read `AGENTS.md`, PF freeze, all canonical/RAG docs, all SDVK issue/PR/evidence, compatibility/performance reports and current source/history.

## Autonomous implementation prompt
Complete SDVK-017 autonomously only after all predecessors. Build evidence matrix first; rerun conflicts; reconcile docs/source; create freeze manifest/release documentation; open PR for final synthesis changes; repair required checks; merge only if freeze passes; verify `master`; close only on genuine success. Otherwise record named blockers and leave freeze unaccepted.

## Acceptance criteria
Every predecessor traceable; no contradiction left unexplained; resource/material/light/probe/shadow/view contracts compose safely; compatibility matrix and tier budgets satisfied; defaults/fallbacks explicit; full required CI/regression passes; docs/RAG/provenance complete; freeze manifest names exact commit/known limitations; PR merged/verified only if gate passes.

## Verification
Full regression/compatibility/performance suite as defined by accepted docs; resource stress; capability fallbacks; source↔RAG audit; issue/PR/merge evidence audit; exact final commands/results recorded.

## Expected artifacts
Final evidence matrix, versioned renderer freeze/release manifest, reconciled README/user/developer/material docs, defaults/config, final RAG/provenance/ledger updates.

## Blocking / stopping conditions
Freeze is blocked by stale/corrupt renderer identity, materially wrong light/probe/tangent/shadow state, silent supported-path compatibility regression, unsafe unsupported-hardware behavior, unbounded declared-tier performance or documentation that overstates approximations. Record blockers; do not weaken the gate.
