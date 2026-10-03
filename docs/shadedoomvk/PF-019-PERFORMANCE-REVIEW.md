# PF-019 performance and dormant-resource review

Status: **accepted evidence for PF-019 / #36**  
Baseline: `master@844462c3a4ed5f7037ade1b49d1a28f578077213`  
Implementation branch: `pf-019/dormant-resource-cleanup`

## Decision summary

PF-019 retains one optimization: stop constructing and maintaining the inherited Z-min/max/light-tile producer resources while the accepted renderer does not consume tiled lights. It intentionally retains PF-006 ordered cache topology, shader math and worker scheduling because none has representative evidence supporting a change.

No image-quality, precision, filtering, resolution, light-count, material, portal, gameplay or timing policy changes.

## Profile-before-change evidence

The accepted baseline has two independent source-level proofs that tiled-light output is dormant:

1. `src/rendering/hwrenderer/scene/hw_drawinfo.cpp` keeps the `DispatchLightTiles(...)` call inside the disabled/commented LevelMesh block.
2. `wadsrc/static/shaders/scene/frag_main.glsl` forces LevelMesh `uLightIndex = -1`; dynamic-light loops read `getLightRange()/getLights()` only when `uLightIndex >= 0`.

The producer nevertheless performs work:

- `VkShaderManager` compiles one Z-min/max vertex shader, three Z-min/max fragment variants and one light-tile compute shader;
- `VkRenderPassManager` creates one light-tile compute pipeline plus one Z-min/max render pass, pipeline layout and three graphics pipelines;
- `VkDescriptorSetManager` creates the two dedicated layouts/pools, allocates one tile set plus six Z-min/max sets, and `BeginFrame()` submits nine dedicated descriptor writes in seven update batches;
- `VkRenderBuffers::BeginFrame()` creates six RG32F Z-min/max images and one screen-sized tile buffer whenever the render-buffer dimensions change.

The LevelMesh descriptor layout still exposes storage binding 4. Removing it would alter shader/descriptor ABI even though current shaders do not read it, so PF-019 does not remove the binding.

## Representative allocation measurement

The prior physical PF work uses a 1904x1001 Vulkan output. Applying the baseline source formulas to that exact extent:

- Z-min/max pyramid dimensions after 64-pixel rounding and six halvings: 960x512, 480x256, 240x128, 120x64, 60x32, 30x16;
- RG32F is 8 bytes/texel, for **5,241,600 bytes** of texel payload;
- a tile block is four 32-bit indices plus sixteen 80-byte `FDynLightInfo` records = **1,296 bytes**;
- `ceil(1904/64) * ceil(1001/64) = 30 * 16 = 480` blocks = **622,080 bytes**;
- inherited combined payload = **5,863,680 bytes**;
- dormant candidate payload for the unchanged LevelMesh binding = one block = **1,296 bytes**;
- deterministic avoided payload = **5,862,384 bytes** before Vulkan allocator/image metadata overhead.

The compiled PF-019 fixture pins these values and also checks odd/sub-tile extents plus the enabled path's inherited ceil-divide sizing. This is an allocation/work measurement, not a claim about actual VMA heap residency or whole-frame timing.

## Retained implementation

`VkLightTilePolicy::Enabled` is the single explicit seam and defaults false.

When false:

- Z-min/max images are not created;
- tile/Z-min-max descriptor layouts, pools and seven sets are not created;
- tile/Z-min-max per-frame descriptor rewrites are not performed;
- the five dedicated shader compilations are skipped;
- the four dedicated pipeline creations and Z-min/max render pass are skipped;
- `DispatchLightTiles()` exits before producer work if called;
- `SceneLightTiles` remains a one-block valid storage buffer and LevelMesh binding 4 remains unchanged.

When the policy is true, the preserved source routes recreate the inherited producer resources and the tile buffer uses the original full-grid formula. SDVK-009 owns any future decision to reactivate the consumer.

## Lookup disposition

PF-006 froze semantic identity and deliberately retained `std::map` for pipeline, shader and render-pass caches. PF-019 found no representative engine workload demonstrating that a hash conversion would improve total lookup cost after hashing, allocations and cache locality are included. The existing warm-key correctness fixture proves reconstructed keys hit the same ordered caches, but it is not a performance justification for replacing them.

No lookup implementation is changed. This is a measured-evidence no-go, not a claim that ordered maps are universally faster.

## Shader disposition

No scene shader source is modified. Therefore there is no generated SPIR-V delta to qualify and no compiler-neutral source rewrite to merge. The PF-019 rule requiring disassembly/runtime evidence applies if a shader candidate is proposed; none is.

Skipping compilation of the five dedicated dormant-path shaders is distinct from changing their generated code. Their source remains available for the enable seam.

## Worker/queue disposition

Priority, precache and main-thread pipeline queues retain their PF-006 ordering/lifetime semantics. No representative scheduling trace demonstrated a bounded win worth changing mutex/list/task behavior, so no worker candidate is retained.

## Other dormant work

The audit did not gate additional renderer resources whose consumer status was ambiguous. PF-019 deliberately stops at the source-proven tiled-light producer.

## Equivalence and validation

The retained change does not alter any accepted shader/material/light calculation: the accepted consumer is already disabled and the fragment path already suppresses tile lookup. Binding 4 remains valid and the enable seam preserves the full producer path.

Deterministic verification:

- `tools/pf_oracle/tests/test_pf019_dormant_resources.py` pins the dormant consumer proof, all producer gates, unchanged PF-006 ordered-map topology and binding-4 preservation;
- `pf019_dormant_resource_fixture.cpp` compiles independently and checks disabled one-block sizing, enabled inherited sizing and the 1904x1001 resource delta;
- the complete PF oracle and inherited cross-platform build matrix remain required on the exact final head.

No physical GTX 1650 SUPER run is required for this candidate because no active rendering consumer or shader output changes. This does not reopen any CFX/PWAD saturation lane and makes no GPU frame-time claim.

## Final acceptance

The acceptance gates are complete:

- implementation/evidence head `e496977a47ebb7a4235dba28a7df11128780b0eb`: CI `37108111799`, 8/8;
- PR #107 merge: `44864d9d27495d3992d3a7314f4cb7de6c029b7b`;
- exact merge push CI: `37108571879`, 8/8;
- later current `master@41daecc2a2cf62d674163a0bb3dc5481c8be37b1`: push CI `37109278147`, 8/8, with no intervening change to PF-019 implementation source paths.

No active dependency on the gated resource surfaced. The measured allocation/work reduction is retained; speculative lookup, shader and worker changes remain rejected/omitted. No physical GPU timing claim is made.
