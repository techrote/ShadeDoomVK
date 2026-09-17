# Autonomous issue bodies

These files are the canonical recoverable issue bodies for ShadeDoomVK's autonomous development programme.

Current stable programme sets:

- `PF-001` through `PF-020` — mandatory pre-foundation hardening tranche;
- `SDVK-001` through `SDVK-017` — founding renderer feature tranche, blocked until PF-020 accepts.

GitHub issue metadata should remain synchronized with material corrections to these files. Stable IDs are semantically authoritative; GitHub numbers are convenience mappings recorded in `../07-ISSUE-EMISSION-STATUS.md`.

Every issue must satisfy `ISSUE-CONTRACT.md` and `AGENTS.md` and be executable without inaccessible chat context.

Creation order is not execution order. Dependency/concurrency readiness is defined in `../05-AUTONOMOUS-ISSUE-GRAPH.md`.

Large shared architecture belongs in `../` canonical documents and `../rag/`; issue bodies should link to it rather than duplicating it.
