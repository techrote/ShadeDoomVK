# GitHub issue emission and reconciliation status

Date: 2026-10-09

Status: complete for the current planning programme.

The repository now has two stable autonomous issue sets:

- PF-001 through PF-020 — mandatory pre-foundation hardening/refactor/correctness/performance tranche;
- SDVK-001 through SDVK-017 — founding renderer feature tranche, gated by PF-020.

Canonical issue bodies are stored under `docs/shadedoomvk/issues/`. Live GitHub issue bodies have been reconciled to the expanded autonomous issue contract.

## SDVK stable ID → GitHub issue

| Stable ID | Issue |
|---|---:|
| SDVK-001 | #1 |
| SDVK-002 | #2 |
| SDVK-003 | #3 |
| SDVK-004 | #4 |
| SDVK-005 | #5 |
| SDVK-006 | #6 |
| SDVK-007 | #7 |
| SDVK-008 | #8 |
| SDVK-009 | #9 |
| SDVK-010 | #10 |
| SDVK-011 | #11 |
| SDVK-012 | #12 |
| SDVK-013 | #13 |
| SDVK-014 | #14 |
| SDVK-015 | #15 |
| SDVK-016 | #16 |
| SDVK-017 | #17 |

## PF stable ID → GitHub issue

| Stable ID | Issue |
|---|---:|
| PF-001 | #18 |
| PF-002 | #19 |
| PF-003 | #20 |
| PF-004 | #21 |
| PF-005 | #22 |
| PF-006 | #23 |
| PF-007 | #24 |
| PF-008 | #25 |
| PF-009 | #26 |
| PF-010 | #27 |
| PF-011 | #28 |
| PF-012 | #29 |
| PF-013 | #30 |
| PF-014 | #31 |
| PF-015 | #32 |
| PF-016 | #33 |
| PF-017 | #34 |
| PF-018 | #35 |
| PF-019 | #36 |
| PF-020 | #37 |

## Gate state

- PF-001 through PF-020 are accepted; the [PF-020 release receipt](PF-020-RELEASE-ACCEPTANCE.json) records verified master integration.
- PF-020 is the pre-foundation synthesis/release gate.
- SDVK-001 is accepted, merged and verified on master at `7f34f15827f3cc98685d1af303d212ed5edc2b47`; its [foundation/build contract](SDVK-001-FOUNDATION.md) and [release receipt](SDVK-001-RELEASE-ACCEPTANCE.json) record the compatibility boundary and passing PR/master evidence.
- SDVK-002 / #2 is accepted, merged and verified on repaired `master@a05743fb428c0d7c66defccfb577834d012b4e31`; its [release receipt](SDVK-002-RELEASE-ACCEPTANCE.json) pins the original implementation, reproducibility repair, native corpus, timing evidence and retained failures.
- SDVK-003 / #3 is accepted, merged and verified through PR #122 / `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`, and its accepted policy is present on the same verified current master.
- SDVK-004 / #4 is accepted, merged and verified through PR #126 / `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b`; its [release receipt](SDVK-004-RELEASE-ACCEPTANCE.json) pins exact-head/post-merge 9/9 CI, software-Vulkan state/image evidence, deterministic pressure and retained failure evidence.
- SDVK-005 / #5, SDVK-006 / #6 and SDVK-009 / #9 are dependency-ready. Downstream issues retain the hard dependencies in `05-AUTONOMOUS-ISSUE-GRAPH.md`.

GitHub issue numbers are convenience mappings only. Stable `PF-*` / `SDVK-*` IDs remain authoritative for dependencies and documentation.
