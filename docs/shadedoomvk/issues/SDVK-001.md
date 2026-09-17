# SDVK-001 — Foundation, identity, reproducible build and provenance

## Purpose
Establish the trustworthy project baseline before renderer behavior diverges materially from VKDoom.

## Autonomous execution prompt
Complete SDVK-001 autonomously in `techrote/ShadeDoomVK`. Treat current `master`, this issue, `AGENTS.md`, `README.md`, and every document in `docs/shadedoomvk/00-` through `06-` as authoritative. Inspect current source, CI and relevant history first. Work on a dedicated branch; open a PR; repair all required automated checks; merge only after they pass; verify the merge on `master`; close only when the criteria below genuinely hold. Record blockers precisely rather than weakening criteria.

## Required work
- Establish ShadeDoomVK project/version identity without blindly renaming compatibility-sensitive VKDoom identifiers.
- Pin and document founding baseline `09634479ab5bf9adf691074fffe85a006a398cd0` and current project lineage.
- Reconcile Windows/Linux build instructions with actual source and CI.
- Audit `.github/workflows/continuous_integration.yml`, including intentionally disabled packaging/upload behavior.
- Add minimal reproducible developer build/run instructions/scripts where useful without renderer semantic changes.
- Ensure diagnostic/version output can identify ShadeDoomVK build SHA and lineage.
- Preserve GPL and third-party provenance; validate donor update procedure.

## Acceptance criteria
- Accurate project identity and baseline provenance are visible in-repo and at runtime/build diagnostics.
- Documented Windows and Linux build paths match reality.
- Required CI is green, or a previously broken baseline is repaired with evidence.
- Compatibility-sensitive names are not mass-renamed without proof.
- PR merged after checks and verified on `master`.

## Dependencies
None.