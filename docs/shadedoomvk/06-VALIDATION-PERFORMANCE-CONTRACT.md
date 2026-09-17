# Validation and performance contract

Status: canonical evidence contract for PF and SDVK work  
Date: 2026-09-17

## Purpose

ShadeDoomVK changes are unusually vulnerable to "looks good on my test map" validation. This contract defines minimum evidence so visual plausibility, refactor cleanliness or code-shape optimism cannot substitute for correctness.

PF-001 establishes the minimal hardening oracle used by the pre-foundation tranche. SDVK-002 later expands it into the durable full renderer reference/benchmark corpus.

## Reference-scene classes

### Sprite orientation

- front-facing normal map;
- mirrored rotation frame;
- multiple actor rotations;
- billboard/wall/flat sprite variants where supported;
- pitched/rolled actor cases where relevant;
- mirror/portal render contexts.

### Lighting

- zero, one and many dynamic lights;
- colored point/spot lights;
- occluded versus visible light;
- sunlight;
- sector/probe boundary;
- portal-group cases;
- moving occluder with stationary actor/light;
- emissive/brightmapped material;
- dense-light case exceeding or approaching shadow/light-list boundaries.

### Materials/textures

- albedo-only fallback;
- normal + specular legacy material;
- PBR metallic/roughness/AO;
- roughness-zero numerical edge fixture;
- indexed/palette/translation paths including RedIsAlpha behavior;
- nearest-filtered pixel albedo plus independently filtered material layers;
- missing/invalid layer fallback;
- sprite precache/upscale/expand variants;
- dynamic/canvas/translucent textures.

Height/POM fixtures are introduced under SDVK-005/008, not PF-008.

### Probes/lightmaps

- no-probe/fallback path;
- explicit probe actor;
- auto-probe with non-zero floor height;
- sector/side nearest-probe assignment;
- per-lightmap probe-map selection with at least two spatially distinct probes;
- probe reset/rebake;
- multiple lightmap atlas pages;
- dynamic lightmap/geometry update where supported.

### Shadows

- no shadows/fallback;
- dynamic shadow-map mode;
- ray-query optional modes where supported;
- floor/wall occlusion;
- moving occluder invalidating cached actor visibility;
- >1024 or boundary shadowmapped-light selection fixture where tractable;
- sprite-shadow fixtures added later by SDVK-012/013.

### Portals/views

- ordinary main view;
- linked portal group displacement;
- mirror/plane mirror;
- camera texture;
- light-probe cubemap render;
- nested/recursive context where practical.

### Resource stress

- many unique multi-layer materials;
- repeated level load/unload;
- texture precache/eviction paths;
- async texture completion racing logical cleanup in a controlled fixture;
- descriptor allocation/free/reuse;
- forced/near descriptor capacity boundary without unsafe global flush;
- multiple lightmap/probe atlases;
- LevelMesh allocate/free/reuse cycles;
- render-buffer/device reset path where safely testable.

## Machine-readable evidence

Diagnostics should make relevant state inspectable, including where applicable:

- active renderer/backend and feature tier;
- render-view/pass context type/identity;
- frame index/tic fraction/render delta;
- material ID and semantic layers present;
- sampler/mip policy per layer;
- bindless slot plus generation/epoch/lifetime diagnostics;
- LevelMesh generation/dirty domains;
- dynamic lights considered/selected/rejected and candidate source;
- visibility-cache hit/miss/invalidation reason;
- probe index/mode and sunlight state;
- shadow candidate/selected index/mode/LOD;
- lightmap/probe atlas page identifiers;
- pipeline/shader key identity where a refactor touches keying;
- CPU/GPU timing;
- draw/light/shadow counts;
- allocation/high-water/reuse counters.

Diagnostic IDs are renderer-local identities unless explicitly documented otherwise.

## Image evidence

Image/golden comparisons are useful but must be paired with state assertions. Prefer deterministic fixed camera, fixed seed/time and fixed content.

Exact pixel hashes are acceptable only when the path is expected to be bit-stable. Otherwise use a documented tolerance/metric and preserve expected image + machine-readable state.

## PF refactor equivalence contract

PF-002..PF-011 are primarily structural refactors. Unless an issue explicitly owns a bugfix, acceptance requires:

- same selected lights/probes/shadow mode for reference cases;
- same material/sampler meaning;
- same portal/view outcome;
- image equivalence within the declared baseline tolerance;
- no gameplay/demo-state change;
- no new resource-lifetime error under stress.

If bitwise/image identity cannot be maintained because instrumentation changes timing/order without visual semantic change, document the exact reason and rely on stronger state assertions plus justified tolerant image comparison.

## PF bugfix contract

PF-012..PF-015 must preserve a minimized pre-fix reproducer demonstrating the bad state, then demonstrate the corrected expected state.

If a preceding refactor removes the failing code/path, the assigned bug issue remains responsible for proving the reproducer can no longer enter the bad state and documenting the supersession.

## Correctness invariants

A change fails even if visually attractive when it:

- selects an ineligible or wrong portal-relative light;
- incorrectly reuses a cached visibility result after relevant geometry changes;
- mirrors tangent/orientation state incorrectly;
- silently changes existing material layer filtering/translation semantics;
- reuses a renderer slot/index while a live old reference can resolve to unrelated data;
- produces an out-of-range descriptor/lightmap/probe index;
- confuses main/portal/camera/probe render contexts;
- loses/falsifies fallback state;
- changes gameplay simulation from render-only work;
- silently disables inherited map/mod behavior.

## PF no-image-quality performance contract

PF-005 and PF-016..PF-019 may optimize internal work, allocation or lookup. They may **not** claim an equivalent optimization by:

- dropping otherwise eligible lights;
- changing light/shadow/probe priority semantics except where an explicit correctness issue already changed the accepted baseline;
- reducing render/shadow/texture resolution;
- changing filter/mip/anisotropy policy;
- reducing numeric precision where output can materially differ;
- shortening PBR/lighting work through a quality approximation;
- changing active feature settings;
- changing visible LOD policy.

Required acceptance evidence:

1. before/after same scene/build type/settings;
2. machine-readable state equivalence for the affected subsystem;
3. image equivalence within declared tolerance;
4. performance/memory numbers showing the proposed change actually helps its target workload;
5. stress/correctness tests remain passing.

## Performance measurement

Record as applicable:

- CPU frame-time distribution/percentiles;
- GPU frame time;
- subsystem CPU timer;
- dynamic-light candidates/selected count;
- visibility trace/cache counts;
- shadow candidates/selected count;
- descriptor/material allocation and lookup counters;
- LevelMesh allocation/free/dirty/upload byte counts;
- staging/upload bytes and wait/stall counts;
- pipeline/shader lookup/compile/cache counts;
- relevant memory/VRAM proxy counters;
- draw/geometry counts.

Do not use average FPS alone.

## Quality tiers

SDVK-016 owns final names/defaults. The architecture should continue to support conceptual:

- **Compatibility** — inherited/cheap behavior, no required ray query, minimal extras;
- **Enhanced** — rich semantic materials/probes/efficient dynamic lights with broad Vulkan support;
- **High** — optional ray-query and expensive sprite-shadow/POM/soft/contact work.

PF performance work is not a quality-tier exercise and should not silently change these conceptual outputs.

## Hardware fallback

Missing optional Vulkan ray-query/acceleration-structure features must not cause unexplained failure. PF-007 centralizes capability/quirk reporting while preserving established fallbacks; SDVK-016 later chooses user-facing tier policy.

## Compatibility campaign

SDVK-015 combines targeted synthetic fixtures with representative Doom-family content patterns: classic maps/sprites, portals, 3D floors, decals, translations, canvases, translucency, models, voxels, particles, warped textures and high material/light counts.

## PF-020 gate

PF-020 must rerun the complete applicable PF corpus and fail closed when:

- a confirmed PF defect remains reproducible in a declared supported path;
- renderer identity/resource stress exposes stale or mismatched data;
- refactor output/state equivalence is unproven;
- an optimization changed visible/semantic quality instead of internal cost;
- RAG/reference documents no longer match implementation;
- a dependency issue was closed without merge/check/acceptance evidence.

## Acceptance philosophy

The programme optimizes for **correct, inspectable, scalable approximations and trustworthy internal state**. A faster or more spectacular effect is not progress when the renderer cannot demonstrate what data/path produced it.
