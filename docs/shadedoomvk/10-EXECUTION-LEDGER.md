# ShadeDoomVK execution ledger

Status: active canonical planning/execution ledger  
Started: 2026-09-17

This ledger records significant programme-level planning changes and later gate transitions. Individual issue/PR evidence remains authoritative for implementation details.

## Ledger entries

### 2026-09-17 — founding programme created

- Established baseline `VKDoom@09634479ab5bf9adf691074fffe85a006a398cd0`.
- Created founding documents `00` through `07` and autonomous issues SDVK-001..017 (#1..#17).
- Initial plan placed observability, upstream policy, descriptors and material semantics before headline sprite effects.

### 2026-09-17 — fork/donor audit reconciled

- Confirmed several apparent VKDoom donor forks are ancestral to the ShadeDoomVK baseline.
- Retained non-ancestral donor concepts from jalovisko and MAD-VKDoom as explicit provenance/hypotheses.
- Recorded GriddleVK per-layer sampling as an initially attractive donor concept.

### 2026-09-17 — deep baseline source audit

Key corrections:

- per-layer material sampling is already present in the inherited baseline;
- bindless descriptor reuse already exists but lacks the desired capacity/lifetime diagnostics and hardening;
- per-lightmap probe selection is stubbed to probe 0 and its dormant implementation is unfinished;
- light-tile/cluster scaffolding exists but is dormant;
- HDR/postprocess groundwork is stronger than the founding plan assumed;
- multiple concrete renderer correctness defects and no-quality-change optimization opportunities were identified.

Decision: do not begin SDVK-001 yet.

### 2026-09-17 — pre-foundation hardening programme inserted

- Added `08-PREFOUNDATION-HARDENING-PROGRAMME.md`.
- Added `09-PLANNING-RECONCILIATION.md`.
- Defined PF-001..PF-020 as a hard pre-SDVK tranche.
- PF-020 becomes the hard release gate for SDVK-001.
- Stable SDVK-001..017 IDs and issue numbers remain preserved.
- New PF issue set is required to use the expanded autonomous issue contract: objective; scope; non-goals; dependencies; concurrency; canonical context; implementation prompt; acceptance criteria; verification; expected artifacts; blockers/stopping conditions.

## Planning-pass stage checklist

- [x] Reconcile relevant planning conversation history available to this run.
- [x] Inspect current repository and GitHub issue/PR state before broad mutation.
- [x] Determine implementation decomposition is warranted but old graph is insufficient without PF tranche.
- [x] Identify major omissions/incorrect assumptions from deep source audit.
- [ ] Commit complete RAG/reference corpus.
- [ ] Reconcile founding docs/AGENTS/README with PF tranche.
- [ ] Emit complete PF issue set with canonical issue-body files.
- [ ] Reconcile SDVK-001..017 issue bodies and canonical files.
- [ ] Review dependencies/concurrency/issue sizing independently.
- [ ] Correct findings from independent review.
- [ ] Perform final repository-wide consistency pass.
- [ ] Record final GitHub issue mapping and master commit state.

## Future implementation ledger rule

When a PF or SDVK gate issue merges, append a concise entry naming:

- issue/PR;
- merge commit;
- contract changed/frozen;
- verification artifact(s);
- dependencies newly unblocked;
- material residual blocker(s).

Do not record an issue as complete merely because a PR exists or CI ran; acceptance criteria and merge-to-master verification remain mandatory.
