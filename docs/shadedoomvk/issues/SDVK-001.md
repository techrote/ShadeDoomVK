# SDVK-001 — Foundation, identity, reproducible build and provenance

## Objective
Establish ShadeDoomVK project/build/runtime identity and reproducible developer/CI baseline **after** PF-020 has frozen trustworthy renderer ground.

## Scope / required work
- Consume `PF-FREEZE-MANIFEST.md` and verify PF-020 gate is genuinely passed on `master`.
- Establish ShadeDoomVK project/version identity without breaking compatibility-sensitive inherited identifiers.
- Pin/document founding VKDoom lineage plus PF freeze commit/provenance.
- Reconcile actual Windows/Linux build/run instructions, dependencies and CI with current source.
- Audit existing workflow behavior and add minimal reproducible build/run helpers where useful.
- Expose ShadeDoomVK version/build SHA/lineage in runtime/build diagnostics.
- Preserve GPL/third-party notices and donor provenance.

## Non-goals
No PF renderer refactor/correctness/performance reopening without a new defect issue; no mass rename; no new visual feature; no upstream mega-merge (SDVK-003).

## Dependencies
PF-020 accepted, merged, verified and explicitly records `SDVK-001: UNBLOCKED`.

## Concurrency guidance
This is the serial entry gate to the SDVK programme. SDVK-002/003 begin only after merge.

## Required context
Read `AGENTS.md`, all canonical planning docs/RAG, `PF-FREEZE-MANIFEST.md`, PF-020 evidence, current `master`, and this canonical body.

## Autonomous implementation prompt
Complete SDVK-001 autonomously only after PF-020 unblocks it. Reconcile identity/build/CI/provenance against the actual frozen source; branch→implementation/tests/docs→PR→repair required checks→merge only after checks→verify `master`→ledger/RAG updates→close only on acceptance.

## Acceptance criteria
Runtime/build diagnostics identify ShadeDoomVK commit/lineage; documented Windows/Linux build paths match reality; applicable required CI is green/repaired; compatibility-sensitive names are preserved unless individually justified; PF freeze provenance is retained; PR merged/verified.

## Verification
Clean documented build/configure paths where CI/runtime permits; version/provenance output checks; CI workflow run/status review; compatibility-name diff audit.

## Expected artifacts
Updated project/build/run/provenance docs, minimal helpers as justified, runtime/build identity diagnostics/tests, ledger entry.

## Blocking / stopping conditions
Do not start if PF-020 gate is not passed. Stop if a rename/build-policy change threatens content/config compatibility without evidence; record a separate decision rather than forcing it.
