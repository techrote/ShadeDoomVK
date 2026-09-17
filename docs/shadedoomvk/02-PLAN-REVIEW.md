# Implementation plan review

Status: completed critique of `01-INITIAL-IMPLEMENTATION-PLAN.md`  
Date: 2026-09-17

## Executive finding

The first-pass plan had the right feature direction but still treated visual milestones as the main dependency structure. That is risky for a renderer fork: the highest-cost failures are likely to come from resource lifetime, unclear upstream ownership, non-reproducible visual tests, compatibility regressions and hidden CPU light-selection costs.

The revised roadmap therefore moves **observability, upstream strategy, descriptor lifetime and material semantics ahead of the headline sprite effects** and separates research/prototype gates from production-default changes.

## Review finding 1 — upstream strategy was implicit

### Problem

VKDoom is a strong renderer baseline but its repository is no longer the only active branch of the family. UZDoom/GZDoom continue to change engine compatibility, platform/build code and Vulkan internals. Deep ShadeDoomVK changes made before defining an upstream policy could turn every later sync into archaeology.

### Improvement

Add an early differential/upstream issue. Pin exact candidate versions/commits, classify renderer-specific ShadeDoomVK ownership versus periodically imported engine maintenance, and test representative merges before the fork diverges further.

Do not require a wholesale rebase as the answer.

## Review finding 2 — descriptor work must include lifetime, not just capacity

### Problem

A configurable larger bindless pool postpones exhaustion but does not solve stale descriptor indices. MAD-VKDoom's emergency texture-flush experiment explicitly demonstrates the danger: LevelMesh can retain old indices after the texture slots change.

### Improvement

Treat jalovisko's device-aware budget as the minimum. Add diagnostics, slot reuse/freeing policy and generation/lifetime safety before rich multi-map sprite materials multiply descriptor demand.

## Review finding 3 — visual testing needs a machine-readable oracle

### Problem

Screenshots alone are weak regression tests. Lighting changes may look plausible while using the wrong lights, wrong mirrored normal orientation, wrong probe or stale descriptor.

### Improvement

Create deterministic reference scenes with inspectable renderer state: selected lights, material channels, descriptor usage, probe index, shadow mode, frame/GPU timing and stable image captures/hashes with tolerant comparison only where necessary.

## Review finding 4 — material semantics must precede height effects

### Problem

Bolting height onto the existing generic texture-layer path can lock in incorrect color space/filter/mip assumptions.

### Improvement

Define semantic channels and per-layer sampling first. Height/parallax becomes a consumer of that material contract rather than another ad-hoc custom texture.

## Review finding 5 — sprite TBN correctness is a separate gate

### Problem

Normal mapping can appear correct on a front-facing unmirrored sprite while being wrong on rotation/mirror frames. POM and specular only amplify that error.

### Improvement

Create an explicit sprite-local tangent basis/mirroring contract and validate it across billboard modes, rotations and flipped frames before height/PBR enhancement.

## Review finding 6 — dynamic-light optimization needs baseline evidence

### Problem

MAD's small-actor/section-list idea is promising, but its implementation includes unresolved portal-group assumptions and later data-structure rewrites. Copying it blindly could exchange CPU time for incorrect light selection.

### Improvement

Use it as a hypothesis. Benchmark stock BSP/light gathering versus section-indexed/compact approaches on deterministic scenes, including portals. Preserve exact light-selection equivalence as a correctness gate.

## Review finding 7 — probes and viewmodels should be validated before shadow complexity

### Problem

Projected shadows are visually dramatic, but a character with incorrect ambient/specular environment or a weapon lit under a different model will still look incoherent.

### Improvement

Qualify probe/environment lighting and viewmodel parity before declaring the material stack visually coherent. Shadow work may prototype in parallel after the material/TBN foundation, but final integration depends on the lighting model.

## Review finding 8 — sprite shadow architecture should remain comparative

### Problem

The first plan prematurely preferred rasterized shadow cards.

### Improvement

Prototype at least alpha-card and depth-card projection and compare against cheap proxy/blob and, where tractable, acceleration-structure sprite approaches. Judge correctness, softness, portal behavior, alpha/mirror handling and cost. Adopt the simplest architecture that meets the quality target.

## Review finding 9 — lightmapper/probe robustness is not a late polish task

### Problem

Richer materials can expose light leaks, atlas lifetime problems, dynamic-lightmap update behavior and probe transitions that classic diffuse surfaces hide.

### Improvement

Run a dedicated qualification/hardening issue before compatibility freeze, with moving geometry, dynamic sectors, decals, sunlight, multiple atlas textures and probe boundaries.

## Review finding 10 — performance needs explicit tiers

### Problem

"Runs fast" is not a release criterion. Ray queries, POM, rich materials and sprite shadows have very different hardware requirements.

### Improvement

Define feature tiers/fallbacks and budgets. Preserve a broadly compatible Vulkan path while allowing a high-end path. Quality settings must correspond to real algorithm changes and report their active state in diagnostics.

## Review finding 11 — the final tranche needs a synthesis gate

### Problem

A pile of merged features does not guarantee they compose.

### Improvement

Add a final synthesis/qualification issue that consumes all evidence, resolves defaults/fallbacks and freezes the first renderer contract only when compatibility/performance/resource-lifetime criteria pass.

## Resulting plan changes

The revised roadmap:

- adds a formal upstream/donor differential early;
- makes renderer diagnostics and descriptor lifetime foundational;
- separates material semantics from POM implementation;
- gates advanced shading on sprite-space TBN correctness;
- treats dynamic-light donor code as a benchmarked hypothesis;
- qualifies probes/viewmodels before final shadow integration;
- keeps sprite-shadow architecture comparative until evidence selects it;
- adds dedicated lightmapper/probe hardening;
- defines measured quality tiers and a final synthesis gate.
