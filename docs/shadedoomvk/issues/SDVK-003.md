# SDVK-003 — VKDoom/UZDoom/GZDoom differential and upstream maintenance strategy

## Objective
Define a repeatable selective upstream-maintenance strategy from the now-hardened ShadeDoomVK renderer without losing VKDoom-specific capabilities or reintroducing PF-resolved defects.

## Scope / required work
- Pin current suitable VKDoom/UZDoom/GZDoom references at execution time.
- Diff engine compatibility, Vulkan/backend, scripting/resource, platform/build/security and relevant renderer changes against current ShadeDoomVK `master`.
- Use PF RAG/contracts to classify owned ShadeDoomVK surfaces versus safely syncable upstream surfaces.
- Identify upstream fixes that supersede or conflict with PF work; never silently overwrite accepted PF invariants.
- Exercise at least one representative selective import/dry-run to expose conflict topology and verification procedure.
- Define provenance, cadence, conflict-resolution and regression requirements.

## Non-goals
No assumed wholesale rebase; no feature import merely because upstream is newer; no reopening PF contracts without explicit evidence/issue.

## Dependencies
SDVK-001.

## Concurrency guidance
May run with SDVK-002. SDVK-004 and SDVK-009 wait for accepted upstream ownership/sync policy.

## Required context
Read `AGENTS.md`, PF freeze manifest/RAG, `04-DONOR-PROVENANCE.md`, current history and canonical body.

## Autonomous implementation prompt
Complete SDVK-003 autonomously. Pin current upstreams, produce source/evidence differential, exercise selective-sync mechanics, document ownership/conflict tests, branch→PR→checks→merge→verify `master`→provenance/RAG/ledger→close.

## Acceptance criteria
Exact upstream refs/deltas recorded; owned vs syncable surfaces explicit; representative import path exercised or precise blocker; sync procedure includes PF regression gates; no VKDoom/ ShadeDoomVK renderer capability lost accidentally; PR merged/verified.

## Verification
Compare commits/files; dry-run or small safe import with test evidence; rerun relevant PF/SDVK oracle; source/provenance audit.

## Expected artifacts
Pinned differential report, upstream ownership/sync policy, representative import evidence, donor/provenance updates, ledger entry.

## Blocking / stopping conditions
If upstream lineage or licensing/provenance is ambiguous, or a proposed import overwrites a hardened contract without equivalent evidence, stop that import and record a research/decision issue while continuing independent analysis.


## Acceptance record

Accepted, merged and verified. Exact final PR head `cbc8fa1601123e595483a2ab5d8f9997c36c0768` passed Continuous Integration run `37846204348` and Renderer source evidence run `37846204325`; PR #122 merged as `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`. The accepted upstream ownership/sync policy is present on verified current `master@a05743fb428c0d7c66defccfb577834d012b4e31`. Issue #3 is closed completed; SDVK-004 and SDVK-009 may consume the policy subject to their other dependencies.
