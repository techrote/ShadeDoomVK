# ShadeDoomVK autonomous issue contract

Every PF/SDVK implementation or research issue must contain these sections or clearly link to an issue-specific canonical artifact that supplies them.

## Required sections

1. **Objective** — one clear outcome, not a task list masquerading as a goal.
2. **Scope / required work** — concrete implementation/research boundaries.
3. **Non-goals** — important adjacent work intentionally excluded.
4. **Dependencies** — hard stable-ID prerequisites and what evidence must exist before starting.
5. **Concurrency guidance** — safe/unsafe overlap with neighboring issues and likely shared-file conflicts.
6. **Required context** — `AGENTS.md`, canonical planning docs and relevant `rag/` references.
7. **Autonomous implementation prompt** — explicit instruction to inspect current `master`/history, implement, test, document, open PR, repair CI, merge only after required checks, verify `master`, close only on acceptance.
8. **Acceptance criteria** — falsifiable conditions, including compatibility/output equivalence or deliberate bugfix delta.
9. **Verification** — tests, fixtures, diagnostics, benchmark/equivalence evidence required.
10. **Expected artifacts** — code/tests/docs/RAG updates/benchmark or decision records that should exist after completion.
11. **Blocking/stopping conditions** — conditions requiring the issue to stop/fail closed rather than weaken criteria.

## PF-specific rule

PF refactor/performance issues are output/state-equivalent by default. A PF issue may change accepted output only when its body explicitly owns a documented correctness defect and preserves a failing reproducer.

## Research issue rule

A comparative/research issue may conclude that no candidate qualifies. That is an acceptable result if the evidence is committed and dependents are correctly blocked/replanned. Do not force a positive implementation decision to close a research issue.

## Source/provenance rule

Do not cite chat as implementation authority. Convert durable findings into repository documents with exact source repository/commit/path where applicable. Distinguish source-verified finding, project requirement, design decision, assumption and speculation.

## Completion rule

No issue is complete until:

- acceptance evidence exists;
- required automated checks pass;
- PR is merged;
- merge is verified on `master`;
- affected canonical/RAG documents are updated;
- blockers/residual limitations are recorded;
- the issue is closed only after those conditions genuinely hold.
