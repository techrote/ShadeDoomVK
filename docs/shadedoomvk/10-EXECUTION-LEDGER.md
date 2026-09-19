# ShadeDoomVK execution ledger

Status: planning workflow complete; implementation begins at PF-001  
Started: 2026-09-17  
Planning closure: 2026-09-17

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
- Added renderer RAG/reference corpus under `docs/shadedoomvk/rag/`.
- Defined PF-001..PF-020 as a hard pre-SDVK tranche.
- PF-020 becomes the hard release gate for SDVK-001.
- Stable SDVK-001..017 IDs and issue numbers remain preserved.
- New PF issue set uses the expanded autonomous issue contract: objective; scope; non-goals; dependencies; concurrency; canonical context; implementation prompt; acceptance criteria; verification; expected artifacts; blockers/stopping conditions.

### 2026-09-17 — PF/SDVK tracker reconciliation completed

- Created PF-001..PF-020 as GitHub issues #18..#37 and canonical issue-body files.
- Reconciled every SDVK-001..017 live/canonical issue to the same autonomous contract.
- Reframed duplicated founding scope:
  - SDVK-004 is rich-workload descriptor integration/stress after PF hardening;
  - SDVK-005 adds height semantics rather than re-porting inherited per-layer sampling;
  - SDVK-009 evaluates higher-order many-light architecture after PF exact-equivalence CPU optimization.
- Updated README, AGENTS, revised roadmap, issue graph, validation contract and donor provenance.

### 2026-09-17 — independent second review completed

- Added `11-INDEPENDENT-PLAN-REVIEW.md`.
- Verified requested refactor/bug/performance coverage.
- Reviewed issue sizing, duplicate scope, hidden assumptions, unsafe concurrency, tests and stopping conditions.
- Found and repaired two hidden prerequisites:
  - PF-012 now depends on PF-003 so probe/page descriptor correctness cannot run before descriptor reservation/lifetime hardening;
  - PF-017 now depends on PF-013 so material-cache optimization consumes corrected material behavior.
- Rechecked the corrected graph as acyclic.

### 2026-09-17 — final repository consistency pass completed

Verification snapshot before the final consistency-report/ledger commits: `master@9e3d016fff290dfbe3b78490cbc5a1d7f60af2e6`.

- Added `12-FINAL-CONSISTENCY-CHECK.md`.
- Inspected live issue tracker and confirmed the programme mapping remains SDVK #1..#17 and PF #18..#37.
- Inspected canonical issue-body and RAG directories.
- Exact planning-placeholder search returned no result.
- `TEMP` issue search returned no result.
- Open pull-request list was empty.
- Marked `01-INITIAL-IMPLEMENTATION-PLAN.md` historical/non-executable.
- Amended founding brief with PF gate and deep-audit qualifications.
- Recorded that `master` is not currently branch-protected; `AGENTS.md` therefore mandates PR/check/merge discipline independently of repository enforcement. This is not a renderer planning blocker.

## Planning-pass stage checklist

- [x] Reconcile relevant planning conversation history available to this run.
- [x] Inspect current repository and GitHub issue/PR state before broad mutation.
- [x] Determine implementation decomposition is warranted and insert PF tranche before the old graph.
- [x] Identify and repair major omissions/incorrect assumptions from deep source audit.
- [x] Commit complete RAG/reference corpus.
- [x] Reconcile founding docs/AGENTS/README with PF tranche.
- [x] Emit complete PF issue set with canonical issue-body files.
- [x] Reconcile SDVK-001..017 issue bodies and canonical files.
- [x] Review dependencies/concurrency/issue sizing independently.
- [x] Correct findings from independent review.
- [x] Perform final repository-wide consistency pass.
- [x] Record final GitHub issue mapping and implementation gate state.

### 2026-09-17 — PF-001 accepted and merged

- PF-001 / #18 completed through PR #38.
- Required CI passed: deterministic PF renderer oracle plus the inherited Windows, macOS and Linux build matrix.
- Repaired the inherited Linux Clang 11 CI dependency gap by adding `libvpx-dev`.
- Merge commit: `069d25a156c6341de448abf98a99b7ebf059f948`.
- PF-002, PF-006, PF-007, PF-009 and PF-011 became dependency-ready.

### 2026-09-18 — PF-002 accepted and merged

- PF-002 / #19 completed through PR #39.
- Required current-head CI passed: deterministic PF oracle, compiled stale-resource identity fixture, Windows/macOS/Linux build matrix.
- Introduced the renderer generation/epoch substrate and wired bindless, LevelMesh, texture, lightmap, probe and async reset hooks without replacing hot-path integer identities.
- Merge commit: `77d143ae888cbd8fbdd5f86b0fc3207025cdc2a4`.
- The post-merge `master` run also passed the full matrix.
- PF-003 and PF-004 became dependency-ready.

## Current implementation gate

- **COMPLETED:** PF-001 / #18, PF-002 / #19.
- **READY:** PF-003 / #20, PF-004 / #21, PF-006 / #23, PF-007 / #24, PF-009 / #26, PF-011 / #28.
- **BLOCKED:** SDVK-001 / #1 until PF-020 / #37 is accepted, merged, verified on `master` and explicitly records `SDVK-001: UNBLOCKED`.
- No planning-level blocker remains.

## Future implementation ledger rule

When a PF or SDVK gate issue merges, append a concise entry naming:

- issue/PR;
- merge commit;
- contract changed/frozen;
- verification artifact(s);
- dependencies newly unblocked;
- material residual blocker(s).

Do not record an issue as complete merely because a PR exists or CI ran; acceptance criteria and merge-to-master verification remain mandatory.
