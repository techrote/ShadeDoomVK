# Initial implementation plan

Status: **historical only; superseded** by `03-REVISED-ROADMAP.md`, `08-PREFOUNDATION-HARDENING-PROGRAMME.md` and `09-PLANNING-RECONCILIATION.md`  
Purpose: preserve the first coherent sequence before critique. **Do not execute this document as the current plan.**

The donor assumptions below intentionally preserve what was believed during the first pass. Later source audit established, among other corrections, that per-layer material sampling and bindless slot reuse already exist in the inherited VKDoom baseline. Use the canonical reconciliation/donor documents for current truth.

## First-pass sequence

The initial plan was:

1. Establish ShadeDoomVK identity, reproducible build and donor provenance.
2. Add deterministic renderer diagnostics/reference scenes.
3. Harden bindless descriptor capacity and lifetime handling.
4. Add semantic material layers and per-layer sampling, including height.
5. Add a renderer delta-time/interpolation substrate.
6. Add explicit sprite-space tangent handling and validate mirrored/rotated normal maps.
7. Add sprite PBR height/parallax and shallow self-occlusion.
8. Optimize dynamic-light gathering for sprite-heavy scenes.
9. Improve probe/environment lighting for sprites.
10. Bring first-person viewmodels into the same lighting/material model.
11. Prototype alpha/depth-card sprite shadow casters.
12. Integrate sprite shadows with LevelMesh ray-query world shadows and contact softening.
13. Harden lightmapper/dynamic-lightmap/probe behavior around the richer renderer.
14. Run compatibility/regression qualification.
15. Define performance/quality tiers and release gates.
16. Freeze the first ShadeDoomVK renderer tranche.

## Initial architecture hypothesis

The first-pass architecture assumed:

- current VKDoom remains the codebase;
- UZDoom/GZDoom are donor/upstream references rather than immediate rebase targets;
- world geometry stays in the inherited LevelMesh/ray-query path;
- sprites remain billboard/card-based for gameplay/render topology;
- normal/PBR maps provide directional material response;
- shallow height/parallax provides pseudo-depth;
- sprite-cast shadows use projected alpha/depth cards rather than full sprite geometry in the RT acceleration structure;
- high-FPS visual animation remains separate from 35 Hz gameplay semantics.

## Initial donor set

The first pass identified these non-ancestral concepts as worth evaluating:

- `jalovisko/VkDoom` commit `033a3c5cb35c82708e4eeb3619373c33ddc40b75`: GPU-limit-aware configurable bindless descriptor count;
- `Waffle-Iron-Studios/GriddleVK` commit `97eaa46b69a19966e1a802b15081bcdf56eff718`: per-custom-material-layer sampler selection;
- `MrRaveYard/MAD-VKDoom` commit `2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5`: small-actor dynamic-light collection fast path;
- MAD commits `807043b995264f166e333bca54c4e0b281bd8669` and `773c53489663040697e744b50bf1b89e06525930`: dynamic-light bookkeeping experiments;
- MAD commit `316b18a4d96b1a120c681d368ac670286234bcc8`: rendered-frame delta-time API;
- MAD commit `7d1f2df404711986a3cc742dad1f9e6e0ac69cde`: opt-in scale/alpha interpolation;
- MAD commit `346f4c0e87139ec8eb0d94d5792d8521b9d17a85`: first-person weapon light-level control;
- MAD commit `e2de04134c4654d38dd4b5452a0306036a5e0911`: descriptor exhaustion mitigation, useful mainly as negative design evidence because it can leave stale LevelMesh texture indices.

## Initial success test

The first pass considered the tranche complete when rich sprite materials, pseudo-depth, coherent actor/viewmodel lighting and scalable sprite shadows worked on a reference map without major compatibility/performance regressions.

The later review/source-audit documents explain why this was not sufficiently rigorous and why PF-001..PF-020 now precede SDVK-001.
