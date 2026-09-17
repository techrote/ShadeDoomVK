# ShadeDoomVK planning reconciliation

Status: canonical planning classification and reconciliation  
Date: 2026-09-17

## Purpose

This document reconciles the founding ShadeDoomVK planning, the VKDoom fork/donor survey, and the deeper baseline source audit performed before implementation. It prevents research observations or old suggestions from silently becoming requirements and records corrections where later source evidence supersedes earlier assumptions.

## Requirements

These are project requirements rather than suggestions:

- Perform a long hard refactor/correctness/performance tranche before SDVK-001 begins.
- Preserve stable SDVK-001..017 programme IDs and historical issue links unless genuinely impossible.
- Include as many high-value renderer-internal refactors as are plausible before feature development, but do not use the tranche as an uncontrolled whole-engine rewrite.
- Resolve every confirmed source bug identified by the pre-foundation audit, or record evidence that a superseding refactor made the bug/path irrelevant.
- Pursue no-image-quality performance opportunities where there is a clear implementation path; prove state/output equivalence rather than assuming optimization from code shape.
- Create durable repository-native RAG/reference material for future autonomous agents.
- Every implementation/research issue must specify objective, scope, non-goals, dependencies, concurrency guidance, required canonical context, implementation prompt, acceptance criteria, verification, expected artifacts and blocking/stopping conditions.
- Every implementation issue uses branch → PR → required automated checks → merge → verify `master` → close-only-if-accepted discipline.
- Gameplay/tic determinism is not silently changed by renderer work.
- Renderer approximations must be named honestly.

## Preferences / product direction

These guide later design but are not automatically PF acceptance blockers:

- Preserve Doom's sprite/sector/pixel-art language while making sprites materially responsive and pseudo-volumetric.
- Prefer strong dynamic lighting, normal/specular/PBR response, subtle height relief, convincing contact/projected shadows and smooth high-FPS visual motion.
- Retain broadly compatible fallbacks while allowing a high-end Vulkan path.
- Future graphical ambitions include richer HDR/bloom, volumetrics, temporal effects, scalable many-light rendering and deeper probe/environment lighting.

## Research findings — source verified at baseline

Baseline: `nashmuhandes/VkDoom@09634479ab5bf9adf691074fffe85a006a398cd0`.

### Already present

- `MaterialLayerSampling` and per-custom-layer sampling overrides are already present in `src/common/textures/gametexture.h`, `hw_material.cpp`, `r_data/gldefs.cpp` and Vulkan sampler/material code.
- Bindless slot reuse already exists in `src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp` using size-bucket free lists.
- LevelMesh has persistent CPU-side arrays, free lists, dirty upload ranges, CPU collision, lightmap tiles and probe-tree members.
- Vulkan HDR scene/pipeline buffers, normal/depth/linear-depth textures, SSAO/tonemap/custom postprocessing exist.
- Ray-query and CPU collision fallbacks exist for world geometry.
- Z-min/max and light-tile resources/pipelines exist as scaffolding.

### Partial or dormant

- `wadsrc/static/shaders/lightmap/frag_copy.glsl` selects a `findClosestProbe()` stub that returns probe `0`; the disabled implementation beneath is unfinished.
- `LightProbeAABBTree::Update()`/`Upload()` are empty at this baseline; the CPU tree exists but its integration is incomplete.
- The LevelMesh light-tile scene path is dormant: fragment code disables `uLightIndex` for that path and the draw-info dispatch block is disabled/commented.
- Model translucency code explicitly notes missing proper depth sorting.

### Confirmed source defects / correctness defects assigned to PF

1. automatic probe placement computes `floor + ceiling/2` instead of `(floor + ceiling)/2`;
2. per-lightmap probe-map selection is stubbed to probe 0;
3. Vulkan indexed-material path explicitly lacks `CTF_IndexedRedIsAlpha` handling;
4. PBR GGX path needs safe roughness-zero numerical handling;
5. shadow-map slot selection becomes traversal-order dependent once the 1024-light cap is reached, with an explicit source TODO for nearer-light preference;
6. sprite ceiling clip sentinel initialization/check is inconsistent;
7. sprite precache computes scale flags and then calls `ValidateTexture` with a boolean literal instead of the computed flags in one material-marking path;
8. `HWSkyInfo` equality uses raw `memcmp` across an ordinary C++ struct where semantic field equality is safer;
9. actor/static-light visibility cache validity does not explicitly encode relevant world-occluder generation and requires a deterministic moving-occluder reproducer/fix;
10. bindless fixed/lightmap/probe reservation arithmetic requires explicit boundary validation before richer resource use.

PF issues may discover that a refactor removes a defect before its repair issue runs. In that case the issue must preserve the original reproducer, prove the bad behavior is no longer possible, document the supersession, and close only on that evidence.

## Donor research findings

### Useful external/non-ancestral concepts

- `jalovisko/VkDoom@033a3c5cb35c82708e4eeb3619373c33ddc40b75`: device-aware/configurable bindless texture limit and better exhaustion reporting.
- `MrRaveYard/MAD-VKDoom@2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5`: section-local small-actor light gathering; portal handling in donor is not authoritative.
- `MrRaveYard/MAD-VKDoom@807043b995264f166e333bca54c4e0b281bd8669` and `773c53489663040697e744b50bf1b89e06525930`: dynamic-light data-layout experiments; use as hypotheses.
- MAD render-frame delta/interpolation and viewmodel-light work remain useful later SDVK concepts.
- MAD bindless flush mitigation remains negative evidence because it can leave stale LevelMesh texture indices.

### Corrected donor assumption

`Waffle-Iron-Studios/GriddleVK@97eaa46b69a19966e1a802b15081bcdf56eff718` is useful provenance for per-layer sampling history, but the current ShadeDoomVK baseline already contains a materially equivalent per-layer sampling mechanism. It is **not** a missing feature to port. SDVK-005 owns semantic generalization/height authoring after PF-008 preserves and exposes existing semantics.

## Design decisions made by this reconciliation

- Insert PF-001..PF-020 before SDVK-001; PF-020 is a hard dependency of SDVK-001.
- Preserve existing SDVK issue numbers #1..#17; new PF issues use stable `PF-*` IDs and later GitHub issue numbers.
- Use RAG as a compact architectural/invariant layer, not as a copied source-tree mirror.
- Keep LevelMesh as the central persistent renderer-side world representation; refactor ownership/invalidation around it rather than replacing it wholesale.
- Introduce generation/lifetime validation at recyclable renderer identities before richer materials increase pressure.
- Extract sprite render-surface/orientation metadata before explicit sprite TBN work.
- Extract render-view/pass identity before future temporal rendering work.
- Centralize existing lighting math/compatibility constants before changing lighting policy.
- Finish/repair probe plumbing before SDVK-010 qualifies actor/environment lighting.
- Treat dormant tiled-light infrastructure as a research asset, not an active feature.

## Assumptions that must be verified during PF

- Existing inherited CI/build commands are sufficient to execute PF issues before SDVK-001 formalizes project branding/build documentation.
- Generation-safe identities can be introduced incrementally without forcing every renderer index into a heavyweight object.
- Section-local actor light gathering can be made exactly equivalent for a clearly defined actor/portal predicate.
- Dynamic-light upload deduplication can preserve current ordering/range semantics.
- Dormant light-tile/Z-minmax resources can be conditionally skipped without side effects when the dormant path is disabled.
- Typed/hash pipeline keys can preserve the exact pipeline-state partitioning currently implied by packed structs.

These are not accepted facts. Their owning issues must test them.

## Speculation / future research, not PF requirements

- Full clustered/forward+ lighting may eventually replace some current CPU light-list work.
- Sprite alpha/depth cards may be preferable to ray-query sprite BLAS for actor shadows.
- TAA, temporal volumetrics, SSR or temporal shadow denoising will likely require per-view motion/history contracts.
- The PBR compatibility bridge may eventually be replaced with a more formally calibrated lighting/exposure system.

PF may prepare clean seams for these ideas but must not claim them as implemented.

## No unresolved product decision blocking planning

The source audit changes implementation order and scope but does not require an external product decision before PF-001. Research uncertainties are localized to their issues and must fail closed without blocking independent lanes.
