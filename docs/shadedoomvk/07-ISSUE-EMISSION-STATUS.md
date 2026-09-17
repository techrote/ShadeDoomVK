# GitHub issue emission status

Date: 2026-09-17

The founding plan defines SDVK-001 through SDVK-017. Their exact autonomous GitHub issue bodies are stored under `docs/shadedoomvk/issues/`.

## Current blocker

At emission time GitHub returned HTTP 410 `Issues has been disabled in this repository` when creating SDVK-001. The connected GitHub tooling does not expose the repository setting required to enable Issues.

Therefore:

- no GitHub issue object was successfully created;
- no fake issue numbers or URLs are recorded;
- the complete issue bodies are committed so they can be emitted verbatim once Issues are enabled;
- the dependency graph remains authoritative via stable `SDVK-*` IDs.

Once repository Issues are enabled, create the 17 issues from `docs/shadedoomvk/issues/SDVK-001.md` through `SDVK-017.md`, preserving titles and bodies. After successful creation, update this file and `05-AUTONOMOUS-ISSUE-GRAPH.md` with GitHub issue-number mappings in a normal reviewed change.
