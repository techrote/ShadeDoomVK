# Implementation plan review

Status: founding critique plus deep-source-audit amendment  
Date: 2026-09-17

## Founding review

The first-pass plan had the right feature direction but still treated visual milestones as the main dependency structure. That is risky for a renderer fork: the highest-cost failures are likely to come from resource lifetime, unclear upstream ownership, non-reproducible visual tests, compatibility regressions and hidden CPU light-selection costs.

The founding revised roadmap therefore moved **observability, upstream strategy, descriptor lifetime and material semantics ahead of the headline sprite effects** and separated research/prototype gates from production-default changes.

### Finding 1 — upstream strategy was implicit

VKDoom is a strong renderer baseline but UZDoom/GZDoom continue to change engine compatibility, platform/build code and Vulkan internals. SDVK-003 therefore owns a pinned differential/selective-sync strategy instead of assuming a wholesale rebase.

### Finding 2 — descriptor work must include lifetime, not just capacity

A larger bindless pool postpones exhaustion but does not solve stale descriptor indices. MAD-VKDoom's emergency texture-flush experiment is explicit negative evidence because LevelMesh can retain old indices.

### Finding 3 — visual testing needs a machine-readable oracle

Screenshots can look plausible while using the wrong light, probe, tangent handedness or resource. SDVK-002 therefore owns deterministic fixtures plus inspectable state.

### Finding 4 — material semantics must precede height effects

Height/POM should consume a semantic material contract rather than become another ad-hoc generic custom texture.

### Finding 5 — sprite TBN correctness is a separate gate

Mirrors/rotation/billboard modes can invalidate a normal-map result that appears correct front-facing. SDVK-007 therefore gates POM.

### Finding 6 — dynamic-light optimization needs baseline evidence

MAD small-actor/section-list work is a hypothesis. Exact selected-light behavior, including portals, is the correctness gate.

### Finding 7 — probes and viewmodels should be validated before final shadow composition

Correct environment/local lighting remains foundational even when projected shadows look visually impressive.

### Finding 8 — sprite shadow architecture should remain comparative

Alpha/depth card, blob/proxy and tractable AS participation must be compared rather than preselecting a winner.

### Finding 9 — lightmapper/probe robustness is not late polish

Atlas lifetime, dynamic updates and probe transitions need a dedicated campaign before compatibility freeze.

### Finding 10 — performance needs explicit tiers

Quality tiers must correspond to measured algorithm/resource changes rather than labels.

### Finding 11 — final tranche needs a synthesis gate

A pile of merged renderer features does not prove composition. SDVK-017 is therefore fail-closed.

---

# Second review — deep VKDoom baseline source audit

The later audit inspected the actual VKDoom source at founding baseline `09634479ab5bf9adf691074fffe85a006a398cd0`. It materially changes execution order and corrects several assumptions from the founding plan.

## Finding 12 — per-layer sampling was already inherited

The baseline already contains `MaterialLayerSampling`, per-custom-layer sampling state, parsing and Vulkan override samplers. The old roadmap's phrasing that SDVK-005 should generalize the GriddleVK concept was too donor-centric and could cause an agent to reimplement an inherited feature.

**Correction:** PF-008 first exposes/tags the semantics of the existing layer model without output change; SDVK-005 later adds height authoring/semantic policy. Griddle remains provenance/history, not missing functionality.

## Finding 13 — bindless reuse also already exists

`VkDescriptorSetManager` already allocates contiguous bindless blocks and recycles them through allocation-size free buckets.

**Correction:** the hard problem is raw index lifetime, reserved-range arithmetic, runtime capacity and stale consumers. PF-002/PF-003 own this before SDVK-004 becomes rich-material qualification/stress.

## Finding 14 — probe architecture was over-described

The engine can render environment cubemaps and assign nearest probes to sectors/sides, but the per-lightmap probe-map shader currently compiles a stub returning probe `0`; the disabled tree traversal is unfinished. `LightProbeAABBTree::Update`/`Upload` are also empty at this baseline.

**Correction:** PF-012 repairs or explicitly bounds this plumbing before SDVK-010/014 depend on it.

## Finding 15 — dormant tiled-light infrastructure must not be mistaken for an active feature

Z-min/max textures, light-tile buffers, descriptor/pipeline code and compute shader scaffolding exist, but the active LevelMesh fragment path disables tiled-light indexing and the scene dispatch is disabled/commented.

**Correction:** PF-019 may remove unnecessary dormant work when provably unused; SDVK-009 may later research whether the scaffold is worth reviving for scalable many-light rendering.

## Finding 16 — HDR/postprocess groundwork is stronger than expected

The renderer already has HDR scene/pipeline images, depth, linear depth, normal/fog buffers, SSAO, tonemapping and custom postprocess abstraction.

**Implication:** bloom, richer volumetrics and screen-space work are plausible later. The missing architectural seam is coherent **per-render-view temporal history**, especially across portals, camera textures and probe captures. PF-010 extracts render-context identity without implementing temporal effects.

## Finding 17 — shared refactors should precede subsystem bugfixes

The audit identified dangerous cross-layer identities and large monolithic scene paths. Fixing individual symptoms before ownership/identity contracts stabilize would likely create churn or hide stale-state defects.

**Correction:** insert PF resource/LevelMesh/pipeline/material/sprite/view/lighting-contract refactors first, then repair bugs against those contracts.

## Finding 18 — confirmed source defects justify a dedicated correctness milestone

The audit found concrete defects or incomplete paths including:

- per-lightmap probe selection stubbed to probe 0;
- automatic probe midpoint arithmetic;
- incomplete Vulkan indexed RedIsAlpha handling;
- PBR roughness-zero numerical edge;
- traversal-order shadow selection at the 1024-light cap;
- sprite ceiling clip sentinel inconsistency;
- sprite precache computed scale flags not passed to one material validation path;
- padding-sensitive `HWSkyInfo` memory comparison;
- visibility-cache invalidation requiring moving-occluder coverage;
- fixed descriptor/lightmap/probe reservation boundaries requiring validation.

**Correction:** PF-012..PF-015 own these defects after shared contracts settle.

## Finding 19 — many high-value performance changes can be quality-neutral

Potential output/state-equivalent wins include:

- O(1) dynamic-light duplicate marking;
- exact-equivalence section-local light gathering for qualified actors;
- deduplicated physical light-data upload with preserved ranges;
- hashed material descriptor-variant lookup;
- typed/hash pipeline lookup;
- improved LevelMesh free bins/growth;
- cached moving-AABB parent paths;
- persistent staging upload arena;
- reduced repeated descriptor/default-layer pressure where semantically identical;
- compiler/SPIR-V-qualified shader micro-optimizations;
- avoiding allocations/work belonging solely to disabled dormant paths.

**Correction:** PF-005 and PF-016..PF-019 own these with a strict no-image-quality/state-equivalence rule.

## Finding 20 — a pre-foundation synthesis gate is required

Because PF touches many shared renderer contracts, SDVK-001 should not start merely when individual PF issues happen to be closed.

**Correction:** PF-020 consumes all PF evidence, reconciles RAG against source, reruns the complete hardening corpus and explicitly unlocks SDVK-001 only if the ground is trustworthy.

## Second-review result

The executable programme is now:

1. PF-001 establishes the hardening oracle;
2. PF-002..PF-011 refactor identity/ownership/render contracts while preserving output;
3. PF-012..PF-015 repair confirmed correctness defects against those contracts;
4. PF-016..PF-019 take output-equivalent performance opportunities;
5. PF-020 performs synthesis/qualification;
6. only then does SDVK-001 begin the original founding feature programme.

`08-PREFOUNDATION-HARDENING-PROGRAMME.md`, `05-AUTONOMOUS-ISSUE-GRAPH.md` and the issue bodies are authoritative for exact dependencies.
