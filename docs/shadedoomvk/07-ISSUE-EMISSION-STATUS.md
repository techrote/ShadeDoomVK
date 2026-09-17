# GitHub issue emission and reconciliation status

Date: 2026-09-17

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

- PF-001 is the first implementation issue.
- PF-020 is the pre-foundation synthesis/release gate.
- SDVK-001 remains **blocked** until PF-020 is accepted, merged, verified on `master`, and explicitly records `SDVK-001: UNBLOCKED`.

GitHub issue numbers are convenience mappings only. Stable `PF-*` / `SDVK-*` IDs remain authoritative for dependencies and documentation.
