# ShadeDoomVK pre-foundation hardening programme

Status: canonical pre-SDVK implementation programme  
Date: 2026-09-17  
Baseline under audit: `nashmuhandes/VkDoom@09634479ab5bf9adf691074fffe85a006a398cd0`

## Why this tranche exists

The founding SDVK-001..017 roadmap was directionally sound, but a deeper source audit showed that the inherited renderer is simultaneously more capable and more uneven than the first plan assumed. Several planned donor features are already present in the baseline, several important subsystems are only partially wired, and the most dangerous future failure mode is not lack of graphical capability but corruption or semantic drift across renderer-owned indices, cached state, portals, materials, LevelMesh, probes, descriptors and asynchronous resource work.

The project therefore inserts a long hardening/refactor tranche **before SDVK-001**. SDVK-001 does not begin until PF-020 accepts the tranche.

This tranche is intentionally allowed to make substantial renderer-internal changes, but it is not a licence for uncontrolled engine modernization. Every refactor must preserve observable rendering unless its issue explicitly owns a confirmed bugfix. Every performance change must prove output/state equivalence for the covered path.

## Source-audit corrections to the old plan

1. Per-layer material sampling is already inherited. `MaterialLayerSampling`, custom-layer sampling overrides and Vulkan override samplers exist. SDVK-005 must extend/generalize this mechanism rather than port it as a missing GriddleVK feature.
2. Bindless slots are already reusable by allocation-size bucket. The missing work is capacity/device limits, reserved-range safety, stale-reference detection and stronger lifetime identity.
3. The per-lightmap probe-map path is not production-complete. `wadsrc/static/shaders/lightmap/frag_copy.glsl` currently selects a stub `findClosestProbe()` that returns probe 0; the disabled implementation beneath is unfinished.
4. Tiled/clustered-light scaffolding exists but is dormant: Z-min/max/light-tile resources are present while the fragment path sets `uLightIndex = -1` and the dispatch is disabled/commented.
5. HDR/postprocess infrastructure is strong: 16F scene/pipeline buffers, normal/depth/linear-depth, SSAO, tonemapping and custom postprocess stages already exist.
6. The current renderer uses several raw integer resource identities and fixed/reserved ranges that become more dangerous as ShadeDoomVK adds richer materials, probes and shadow paths.

## Programme invariants

- No SDVK headline effect is permitted to hide a pre-existing correctness defect.
- Refactors must default to render/state equivalence unless their issue explicitly names a bugfix.
- Compatibility-sensitive Doom/GZDoom semantics are not casually redesigned.
- No performance issue may gain speed by selecting fewer eligible lights, lowering precision, filtering differently, reducing resolution, changing LOD, or silently disabling work unless that behavior is already part of the accepted baseline contract.
- Main-view, portal, mirror, camera-texture and light-probe render contexts must remain distinguishable.
- New renderer identities must be diagnosable and lifetime-safe.
- RAG/reference documents describe source truth and invariants; they are not copies of source code and must name baseline/source locations.

## Logical milestones

### PF-M0 — Truth, fixtures and hardening oracle

**PF-001 — Pre-foundation renderer safety harness and invariant fixtures**

Establish targeted regression fixtures and diagnostics needed to prove the refactors below. This is not SDVK-001 rebranding/build work; inherited build/CI remains the execution substrate.

### PF-M1 — Renderer identity and lifetime safety

**PF-002 — Renderer resource generations, stale-reference detection and lifetime contract**  
Introduce a small generation/lifetime model for renderer-owned recyclable identities and diagnostics capable of detecting stale references.

**PF-003 — Bindless descriptor capacity, reservation and reuse hardening**  
Adapt device-aware limits, validate existing bucket reuse, harden fixed/lightmap/probe reservations and exhaustion behavior, and integrate PF-002 lifetime checks.

**PF-004 — LevelMesh ownership, mutation and allocator hardening**  
Encapsulate mutation/dirty-range/invalidation contracts without replacing the performant persistent LevelMesh representation.

**PF-005 — Asynchronous texture jobs and persistent staging-upload arena**  
Generalize upload-ID cancellation/lifetime safety and reduce per-texture staging allocation churn while preserving texture results.

### PF-M2 — Canonical renderer contracts

**PF-006 — Typed shader/pipeline keys and cache contract**  
Remove dependence on raw C++ object-representation `memcmp` keys and make pipeline/shader identity explicit and hashable.

**PF-007 — Central Vulkan capability and driver-quirk registry**  
Move scattered capability/vendor/driver decisions behind a documented query surface without changing established fallbacks.

**PF-008 — Existing material-layer semantic refactor**  
Tag and expose existing albedo/normal/specular/PBR/bright/detail/glow/custom layers semantically while retaining current authoring and rendering behavior. Height authoring remains SDVK-005 scope.

**PF-009 — Sprite render-surface and orientation-state extraction**  
Extract canonical sprite geometry/orientation/mirror/billboard metadata from the large sprite path without yet changing the normal-map tangent algorithm. SDVK-007 later consumes this contract.

**PF-010 — Render-view/pass context extraction**  
Represent main view, recursive portal/mirror, camera texture and probe cubemap render contexts explicitly, establishing safe future seams for temporal effects without implementing TAA/history yet.

**PF-011 — Lighting math, units and compatibility-bridge contract**  
Centralize/document existing dynamic/PBR/sun/classic-light constants and conversions without changing accepted output; isolate later physically richer policy changes from compatibility behavior.

### PF-M3 — Correctness repair after shared contracts stabilize

**PF-012 — Probe/lightmap correctness and spatial-selection repair**  
Repair/qualify the probe-map stub, automatic probe placement, LightProbe AABB lifecycle and incremental/full probe-building edge cases. Preserve explicit fallback where a subpath cannot yet be made trustworthy.

**PF-013 — Texture/material correctness repair pack**  
Address indexed RedIsAlpha handling, numerical PBR roughness edge behavior, sprite precache material-variant flags and related minimized fixtures.

**PF-014 — Sprite/portal state correctness repair pack**  
Fix the sprite ceiling sentinel defect, replace padding-sensitive sky-info equality and cover mirror/portal state invariants touched by PF-009/PF-010.

**PF-015 — Shadow/visibility cache correctness repair pack**  
Make capped shadow-light selection deterministic/spatially meaningful, validate the 1024-slot boundary, and invalidate actor/static-light visibility caches when relevant world occluders change.

### PF-M4 — Output-equivalent performance work

**PF-016 — Unified dynamic-light query service and exact-equivalence actor fast path**  
Centralize candidate collection/filtering/portal-relative positions/visibility and implement O(1) duplicate marking plus qualified section-local gathering where selected-light equivalence is proven.

**PF-017 — Light/material data deduplication and cache lookup performance**  
Deduplicate physical dynamic-light uploads where safe, retain per-surface index ranges, and replace linear material-descriptor-variant scans with canonical lookup without changing bindings/results.

**PF-018 — LevelMesh/AABB allocator and update-path performance**  
Improve free-list/bin behavior, growth policy and moving-AABB parent update paths while preserving geometry, trace and upload results.

**PF-019 — Pipeline/resource micro-performance and dormant-path cleanup**  
Use PF-006 keys for efficient cache lookup, conditionally avoid provably unused dormant allocations, inspect generated SPIR-V before hand micro-optimizing repeated light-vector math, and accept only measured/equivalent wins.

### PF-M5 — Synthesis gate

**PF-020 — Pre-foundation hardening synthesis and SDVK-001 release gate**

Consume PF-001..019 evidence; run the complete pre-foundation corpus; reconcile RAG/reference truth with current source; record before/after performance and compatibility evidence; classify unresolved findings. SDVK-001 is unblocked only if no remaining PF blocker can corrupt renderer identity, mis-select lighting/probes/shadows, break declared compatibility, or invalidate the new architecture contracts.

## Dependency hierarchy

```text
PF-001
 ├─ PF-002 ─ PF-003 ─┬─ PF-005
 │                   └─ PF-008 ─ PF-013
 ├─ PF-004 ────────────────┬─ PF-012
 │                         ├─ PF-015
 │                         └─ PF-018
 ├─ PF-006 ───────────────────────────────┐
 ├─ PF-007 ─┬─ PF-010 ──────┬─ PF-012    │
 │          │                ├─ PF-014    │
 │          │                └─ PF-015    │
 ├─ PF-009 ─┬─ PF-014                    │
 │          └─ PF-016                    │
 └─ PF-011 ─┬─ PF-012                    │
            ├─ PF-015                    │
            └─ PF-016 ─ PF-017           │

PF-003 + PF-008 + PF-016 ── PF-017       │
PF-004 + PF-015 ─────────── PF-018       │
PF-005 + PF-006 + PF-007 + PF-017 + PF-018 ─ PF-019
PF-002..PF-019 ─────────────────────────────── PF-020
PF-020 ────────────────────────────────────── SDVK-001
```

Exact hard dependencies live in issue bodies and `05-AUTONOMOUS-ISSUE-GRAPH.md`.

## Safe concurrency

After PF-001, the following lanes are intentionally parallel:

- resource lifetime: PF-002 → PF-003;
- LevelMesh ownership: PF-004;
- pipeline identity: PF-006;
- Vulkan capability policy: PF-007;
- sprite-state extraction: PF-009;
- lighting-math contract: PF-011.

Do not run two implementation issues concurrently when both restructure the same owned files unless one explicitly rebases on the other and the issue graph is updated. In particular:

- PF-003 precedes material-descriptor performance work;
- PF-009 precedes sprite/portal correctness and the actor-light fast path;
- PF-010 precedes probe rendering and portal-sensitive cache work;
- PF-015 precedes optimization of visibility/light-query caches;
- PF-004 precedes LevelMesh allocator/update optimization.

## How this changes SDVK-001..017

The stable SDVK IDs and issue numbers remain intact.

- SDVK-001 gains hard dependency PF-020.
- SDVK-004 becomes qualification/stress and rich-material descriptor integration on top of PF-002/PF-003 rather than inventing descriptor reuse from scratch.
- SDVK-005 extends PF-008 with first-class height semantics, authoring/default sampling/color-space policy and compatibility behavior; per-layer sampling is acknowledged as inherited.
- SDVK-007 consumes PF-009's sprite orientation contract to implement explicit sprite tangent-space lighting.
- SDVK-009 moves beyond the PF-016 exact-equivalence CPU fast path to qualify higher-order scalable-light architecture, including the inherited dormant tiled-light scaffold.
- SDVK-010 starts from PF-012's corrected probe plumbing and focuses on actor/environment response and transitions.
- SDVK-014 treats probe-map/lightmap correctness as established preconditions and performs integrated robustness/stress qualification.

Other SDVK issues retain their feature goals but use the hardened contracts and structured issue format established here.

## Completion rule

PF work is not complete because code was reorganized or benchmarks improved. PF-020 must demonstrate that:

- all confirmed source defects assigned to PF are fixed or explicitly proven no longer relevant after a superseding refactor;
- no new stale renderer identity is observed under resource stress;
- output-equivalent optimizations preserve machine-readable selected-light/material/probe/shadow state and image evidence within the declared baseline tolerance;
- portal/mirror/camera/probe render contexts remain correct;
- all canonical RAG/reference documents match the resulting implementation;
- every PF issue was merged only after required automated checks and its own verification passed.
