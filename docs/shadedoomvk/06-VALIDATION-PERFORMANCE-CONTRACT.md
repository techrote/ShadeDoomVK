# Validation and performance contract

## Scoped dependency qualification — 14 October 2026

[SDVK-009-GATE-SPLIT-20261014](SDVK-009-SOFTWARE-DEPENDENCY-AUTHORITY.md) separates
**software-qualified dependency use** from **physical-performance acceptance** for
#11/#14 only. It does not lower the correctness or performance requirements below.
Source/CPU/explicitly hosted software-Vulkan evidence can qualify the software scope;
physical-GPU cost/scaling/stability needs its own authorized evidence and stays held.

Downstream software PRs may merge after their required checks/review/exact-master
verification. No missing physical result becomes passed, no closed issue flag is a
substitute for technical evidence, and later defaults/freeze gates are not released.
Retain failures, fixture settings and thresholds. A demonstrated upstream correctness
regression reblocks affected consumers. Physical STOP remains active; software success
is not permission to resume the historical failed physical experiments.

Use normal required CI for approximate runner comparisons; do not add duplicate runners
or repeat CI merely for benchmarking. This authority change itself alters no renderer,
fixture or workflow and supplies no new physical/performance measurement.

Status: canonical evidence contract for PF and SDVK work  
Date: 2026-09-17

## Purpose

ShadeDoomVK changes are unusually vulnerable to "looks good on my test map" validation. This contract defines minimum evidence so visual plausibility, refactor cleanliness or code-shape optimism cannot substitute for correctness.

PF-001 establishes the minimal hardening oracle used by the pre-foundation tranche. SDVK-002 later expands it into the durable full renderer reference/benchmark corpus.

The SDVK-002 implementation is documented in
[renderer observability](SDVK-002-OBSERVABILITY.md), with executable recipes and
commands in [the corpus guide](../../tools/renderer_oracle/README.md). Its
bounded collector, deterministic preparation, state/image comparison and
descriptive benchmark receipts implement the evidence workflow below. Individual
native recipe qualification and issue acceptance remain explicit evidence gates;
CPU preparation success is not a rendered image or performance result.

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


## SDVK-006 renderer visual-time contract

SDVK-006 treats time as renderer presentation evidence, not a gameplay timestep. Acceptance requires a deterministic clock/state-machine fixture and source assertions for PF-010 ownership in addition to the ordinary renderer corpus. Only the visible MainView owner may advance/reset main visual time; later stereo eyes and main-root portals are read-only snapshots; camera textures, light-probe faces, save pictures and their portal descendants expose explicit non-main fallback state and must not consume the next main delta.

Clock qualification includes first/repeated timestamps, finite positive cadence above/below tic rate, long-frame clamp, rollback/non-finite input, pause/resume, level load/restart, wipe/cut and temporary main-view absence. Interpolation qualification includes exact 0/1 endpoints, intermediate monotonic alpha/scale values, disabled/default behavior, `RF_DONTINTERPOLATE`, and a fixed simulation sentinel under different render cadences. A subjective smoothness report cannot replace these state checks.

The hosted software-Vulkan lane remains the routine native qualification path. Physical GPU evidence is optional unless a concrete driver/pacing defect appears; software Vulkan is correctness/repeatability evidence and not a physical-GPU performance claim.

## SDVK-014 increment evidence is not campaign acceptance

[SDVK-014's CPU increment](SDVK-014-CPU-INCREMENT.md) keeps passing fixed-scope
fixtures, retained intended failures and **current blocked counterexamples** in
separate receipt categories. An exit-0 increment collector is not a campaign pass;
`--require-campaign-complete` fails closed while the campaign is unaccepted.
Source hashes pin actual tested files rather than relabelling the base commit as
the changed checkout. Synthetic CPU readback channels, allocator counts and fixture
wall times do not qualify native illumination, device lifetime or physical cost.
Upstream #150 was resolved by PR #152 at `ca254b6ea08228c8408562ebba26bbc1060a0311`.
The [durable identity audit](SDVK-014-DURABLE-IDENTITY-AUDIT.md) establishes a
separate #153 blocker for retained probe-map texels across live descriptor reset.
Its collector exit 0 means named counterexamples were reproduced, not fixed;
`--require-clean` returns 2 while clean identity acceptance is blocked. The
copied-atlas-receipt ABA control is explicitly distinct from native reachability.
Normal CI remains required for any software increment; no benchmark-only duplicate
native run is justified. Audit evidence does not waive software or physical gates.


### SDVK-153 live material reset qualification boundary

The prospective `sdvk153_probe_reset` gate uses the existing Avrea 16-vCPU
software-Vulkan lane once per normal source-changing CI. Fixed input-driver
render counts request live filter/anisotropy changes independently of diagnostic
results. Required raw within-process pair base/generation/epoch/span and content
epoch are not normalized between resets; selected material sampler changes must
also be observed. Two reset captures repeat exactly and final RGB matches an
unchanged-setting control. Existing corpus settings expectations are unchanged
except for these explicitly registered phase-driven scenes.

Emitted uniform diagnostics do not constitute per-texel atlas readback. CPU
allocator/source proofs, hosted emitted-draw evidence and physical performance
are distinct claim classes. Synthetic/compiled input-driver controls are not
ZScript VM execution. Original-source negative evidence remains failed; normal
collector success only means its declared historical failures were reproduced.
Physical STOP remains ACTIVE and #14 cannot be accepted solely from this gate.


### SDVK-156 atlas incarnation qualification

#153 is accepted through PR #155; its earlier candidate/reblocked statements above
are historical. SDVK-156 separately repairs the copied atlas-receipt guard gap
using current-owner/slot/allocation incarnations. The unchanged historical audit
continues executing pinned old atlas and descriptor producers: collector success
means its named old failures were reproduced, and is not a current clean verdict.

The new current-source CPU fixture, compiled mutants, valid packing-equivalence
trace and optional sanitizer run are separate evidence categories, pinned in
`evidence/SDVK-156-ATLAS-IDENTITY-CPU.json`. Current source must reject old receipts
without dereferencing caller-retained item storage, preserve valid geometry and
current-surface tombstones, and pass normal exact-head CI/review/merge verification.
No physical device, extra benchmark workflow or native multi-page acceptance claim
follows from these tests. #14 remains NOT SOFTWARE-COMPLETE and Physical STOP ACTIVE.
