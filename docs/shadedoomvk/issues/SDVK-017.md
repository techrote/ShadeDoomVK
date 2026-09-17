# SDVK-017 — Integrated renderer synthesis, defaults and first ShadeDoomVK freeze

## Purpose
Consume the complete founding campaign and decide whether the first ShadeDoomVK renderer tranche is foundation-qualified.

## Autonomous execution prompt
Complete SDVK-017 only after SDVK-001 through SDVK-016 are accepted and merged. Read `AGENTS.md`, every founding document, every predecessor issue/PR/report/fixture and the complete relevant open/closed issue set. Do not assume the freeze passes. Build an evidence matrix first; rerun decisive fixtures where results conflict. Dedicated branch → PR → repair required CI → merge only if checks and freeze criteria pass → verify `master` → close only on genuine success. If blocked, record named blockers and leave the freeze unaccepted.

## Required synthesis
- Audit founding invariants against actual implementation.
- Reconcile donor/upstream provenance and update sync policy.
- Freeze semantic material/tangent/height behavior and documented fallbacks.
- Freeze actor/probe/viewmodel lighting modes.
- Freeze sprite/world shadow architecture and quality-tier behavior.
- Audit descriptor/atlas/probe/light/resource lifetime safety.
- Consume compatibility and performance matrices.
- Set defaults conservatively from evidence; optional High features need not become default.
- Update README/user/developer/build/material-authoring documentation.
- Create a versioned renderer contract/release-note/freeze manifest that names commit, tests and known limitations.

## Freeze blockers
The tranche cannot be declared foundation-qualified while any unresolved issue can cause:
- stale/corrupt renderer resource identity;
- materially wrong light selection or tangent-space response in a declared supported path;
- silent major compatibility regression;
- unsupported hardware crash rather than documented fallback;
- unbounded performance collapse in a declared quality tier;
- documentation that overstates approximation as physical geometry/RT capability.

## Acceptance criteria
- Every predecessor result is traceable in the synthesis evidence matrix.
- Contradictions are reconciled or named as freeze blockers.
- Defaults/fallbacks/tiers are explicit and tested.
- Full required CI/regression suite passes.
- Freeze manifest and current project documentation are complete.
- PR merged and verified on `master` only if the freeze passes.

## Dependencies
SDVK-001 through SDVK-016.