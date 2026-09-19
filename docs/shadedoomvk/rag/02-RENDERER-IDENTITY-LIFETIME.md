# Renderer identity and lifetime map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: PF-002 generation/epoch substrate active; subsystem hardening continues  
Primary issues: PF-002, PF-003, PF-004, PF-005, SDVK-004

## Core rule

Renderer indices are implementation identities, not semantic/gameplay identities. If an index is recyclable, every long-lived consumer must either be invalidated before reuse or carry sufficient generation/owner context to reject stale use.

## Texture/material chain

```text
FGameTexture / FTexture
   │
   ├─ FMaterial (API-neutral layer ordering + shader choice)
   │    └─ VkMaterial
   │         └─ DescriptorEntry variants
   │              └─ contiguous bindless slots
   │
   └─ VkHardwareTexture
        └─ VkTextureImage / Vulkan image+view
```

Important baseline files:

- `src/common/textures/gametexture.h`
- `src/common/textures/hw_material.h/.cpp`
- `src/common/rendering/vulkan/textures/vk_hwtexture.h/.cpp`
- `src/common/rendering/vulkan/descriptorsets/vk_descriptorset.h/.cpp`

`VkMaterial` caches descriptor variants by clamp mode, palette/translation and global-shader address. Destruction/removal returns bindless allocations to size buckets.

## PF-002 generation substrate

PF-002 adds `hw_resourcegeneration.h` with two deliberately small primitives:

- `FRendererResourceGenerationTable` for recyclable indexed blocks. Durable diagnostic tokens carry `{index, generation, epoch, span}`; retirement/reuse/reset makes older tokens fail validation.
- `FRendererEpoch` for owner-wide reset domains where individual slot generations are unnecessary.

The primitives expose stale-rejection and lifecycle counters and are not internally synchronized. Current owners mutate them on renderer-owner paths; later async consumers must use their subsystem synchronization.

Current wiring:

- dynamic bindless block allocation/free tracks generations in `VkDescriptorSetManager`;
- `LevelMesh::Reset()` advances a LevelMesh resource epoch;
- `VkTextureManager` advances separate texture, lightmap, environment-probe and async-upload epochs at their real reset/destruction boundaries.

See `docs/shadedoomvk/PF-002-LIFETIME-CONTRACT.md` for the exact contract and deliberately unconverted identities.

## Bindless identity

PF-003 hardens the bindless address space and allocator. The executable contract lives in `src/common/rendering/vulkan/descriptorsets/vk_bindless.h` and is documented in `docs/shadedoomvk/PF-003-BINDLESS-CONTRACT.md`.

Address space:

```text
[0, 3)       fixed resources
[3, 259)     up to 128 lightmap/probe-page pairs
[259, N)     dynamic material/colormap/environment-probe blocks
```

This corrects the founding baseline's `3 + 128` dynamic start: each lightmap page consumes **two** descriptors, so the old range could overlap dynamic allocations above 64 pages.

Dynamic blocks use exact-size free buckets through `VkBindlessSlotAllocator`. Allocation/free drives PF-002 generations; a stale token cannot validate after retirement/reuse. Invalid or duplicate frees are rejected rather than re-enqueued.

Effective capacity is:

```text
min(vk_max_bindless_textures, derived Vulkan device limit)
```

The device limit accounts for combined-sampler + sampled-image limits, update-after-bind aggregate limits and the fixed scene descriptors already present in the pipeline layout. The limiting capability, requested/effective capacity, current/high-water/free descriptor counts and reuse/failure counters are inspectable.

`UpdateBindlessDescriptorSet()` rejects more than 128 lightmap pages and verifies that page writes end before the dynamic range. `SetBindlessTexture()` rejects out-of-capacity writes.

Global emergency descriptor flushing remains prohibited because LevelMesh/material consumers can retain raw indices.

## LevelMesh identity

`LevelMesh` owns CPU-side arrays for vertices, surfaces, uniforms/material state, light uniforms/lists, lights, dynamic-light data, indices, collision nodes and probe nodes. Allocation structs use raw integer offsets/ranges. `DoomLevelMesh` separately records source Doom-side associations for sides/flats/subsectors/tiles.

Vulkan `VkLevelMesh` mirrors/upload-ranges into GPU buffers and may build BLAS/TLAS acceleration structures.

Long-lived indices therefore span at least:

```text
Doom semantic object
 → DoomLevelMesh surface/block metadata
 → LevelMesh array range/index
 → GPU buffer offset/index
 → shader-visible material/light/probe/texture indices
```

PF-004 must make invalidation/ownership explicit without turning every hot element into a heavyweight heap object.

## Lightmap/probe identity

Lightmap atlas pages and probe maps become bindless texture entries. Environment probes also obtain two adjacent bindless entries (irradiance + prefiltered map) on demand.

Probe index `0` is used as a fallback/sentinel in multiple places. Code that introduces typed handles must not casually reinterpret it as an ordinary fully equivalent probe without examining the relevant shader/path.

## Dynamic-light identity

Doom `FDynamicLight` objects are translated into `FDynLightInfo` lists and/or LevelMesh light records. Actor light collection may deduplicate by light pointer and then upload copied structs. Shadow maps also assign a finite shadow index.

Pointer identity is currently meaningful inside a frame/cache but must not become a persistent serialized identity.

## Async texture lifetime

`VkTextureManager` has worker/main queues plus `CreateUploadID`/`CheckUploadID`. Destroying a `VkHardwareTexture` removes matching pending upload identity so a later main-thread completion can be rejected.

This is a useful pattern but remains raw-pointer/ID based and each upload currently allocates staging resources independently. PF-005 generalizes the lifetime/cancellation model and staging memory ownership.

## Lifetime transitions that require explicit treatment

- level load/unload;
- texture precache/cleanup;
- material destruction/recreation;
- sampler/filter changes that invalidate material descriptor variants;
- lightmap atlas recreation/page-count changes;
- probe cubemap reset/rebake;
- LevelMesh geometry/surface/light-list reallocation;
- BLAS/TLAS rebuild/update;
- canvas/dynamic texture resize/recreate;
- Vulkan device/render-buffer reset;
- asynchronous upload completion after logical resource destruction.

## Required diagnostics after PF

For recyclable resource classes expose, where practical:

- slot/index;
- generation/epoch;
- owner/resource class;
- current allocation count / high-water mark;
- free/reuse count;
- stale-reference rejection count;
- global reset/epoch changes;
- last invalidation reason in debug builds.

## Invariants

1. Reusing an index may never cause a live old reference to resolve to an unrelated new resource.
2. A global flush is not safe if LevelMesh/material state keeps old indices.
3. Descriptor and lightmap/probe index arithmetic must be bounds-checked against actual Vulkan/device/runtime capacity.
4. Async completion must verify target lifetime before upload/bind.
5. PF refactors must preserve content-visible texture/material meaning unless a correctness issue explicitly owns the change.
