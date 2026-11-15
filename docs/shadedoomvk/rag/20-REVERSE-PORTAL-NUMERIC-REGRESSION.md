# Reverse linked-portal plane: float-precision diagnostic boundary

**Authority:** [PR #199](https://github.com/techrote/ShadeDoomVK/pull/199), merged 14 November 2026 as `0ecba708e283e33c381fae329ace7a2cedc6a3f3`; original head `5fbdb58597b3448f7ac07a1339aa452cec5bc246`.

**Retrieval queries:** SDVK-161 reverse portal, camera owner plane, negative Y normal, float rounding, false oracle failure, math.isclose, linked portal receiving wall, source-qualified tolerance.

## Correctly scoped change

The first master-hosted SDVK-161 lifecycle capture reported the submitted reverse portal wall's oriented plane as:

`[0, -0.9999999403953552, 0, -191.99998474121094]`

The exact expected plane `[0, -1, 0, -192]` is equivalent within normal **single-precision** geometry coefficient rounding. Its actual material, receiver, owner, view, tile and context/camera were already correct. Rejecting the frame on exact integer coefficients was an **overstrict diagnostic**, not a renderer defect.

The repaired production oracle `tools/renderer_oracle/sdvk161_special_surfaces.py` specifically checks this known authored plane with `math.isclose` (`rel_tol=2e-7`, `abs_tol=1e-7`), finite numeric values, correct vector length and the same orientation/distance target. It does not relax camera assertions, source owner identity, drawn surface checks or exact state/RGB paired comparisons. `test_sdvk161_special_surfaces.py` adds the observed regression and negative altered orientation/axis/offset controls.

Original failed [master job](https://github.com/techrote/ShadeDoomVK/actions/runs/43483342120/job/132088679762) and corrected replay are retained in the PR description. It records 66 focused tests and an exact-head native repeatability requirement.

## What this is NOT

- No renderer pipeline, actual portal geometry, shader or lightmap implementation was changed.
- No global visual tolerance or acceptance-policy relaxation was established.
- No automatic dismissal of other #161 special-surface lifecycle failures, driver faults, coordinate-space regressions or invalid receiving planes is justified.

If a future receiver mismatch exceeds this *specific* tolerance or uses the wrong space, investigate the actual source/plane/portal context; do not widen thresholds to force green CI.

Cross-references: [portal coordinate spaces](07-PORTAL-COORDINATE-SPACES.md), [observability](11-RENDERER-OBSERVABILITY.md), [special-surface lifecycle](../SDVK-161-SPECIAL-SURFACE-LIFECYCLE.md).
