# Renderer identity and lifetime map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: PF-002 generation/epoch substrate active; PF-003/PF-004/PF-005 subsystem hardening active; PF-012 probe-map identity contract active; PF-013 material-interpretation identity active; PF-017 source-owned light-packing candidate off-GPU-qualified, physical acceptance pending  
Primary issues: PF-002, PF-003, PF-004, PF-005, PF-012, PF-013, PF-017, SDVK-004

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

`VkMaterial` caches descriptor variants by clamp mode, palette/translation, global-shader address and, after PF-013, the palette-mode RedIsAlpha interpretation bit. Destruction/removal returns bindless allocations to size buckets.

### PF-013 material interpretation identity

The renderer has two semantically different single-byte texture producers: ordinary indexed textures store a palette index, while `CTF_IndexedRedIsAlpha` stores image luminance for the fixed-colour alpha path. They may share Vulkan `R8_UNORM` storage format but they are not interchangeable identities.

PF-013 therefore gives a `VkHardwareTexture` separate normal/palette-index/RedIsAlpha resident-image variants and records `mRedIsAlpha` in `FMaterialState` when palette mode consumes `TM_ALPHATEXTURE`. `VkMaterial::DescriptorEntry` includes that bit in its variant identity so a bindless slot prepared for palette indices cannot be silently reused for luminance-as-alpha, or vice versa. Ordinary translation identity remains part of the existing descriptor key.

Material destruction still calls `FreeBindlessSlot()` for every descriptor variant and clears the cache. Texture reset still advances the PF-005 upload epoch and now resets all three image interpretations. The PF-003 generation allocator remains the authority for recycled dynamic descriptor slots; PF-013 does not introduce a second lifetime system.

## PF-002 generation substrate

PF-002 adds `hw_resourcegeneration.h` with two deliberately small primitives:

- `FRendererResourceGenerationTable` for recyclable indexed blocks. Durable diagnostic tokens carry `{index, generation, epoch, span}`; retirement/reuse/reset makes older tokens fail validation.
- `FRendererEpoch` for owner-wide reset domains where individual slot generations are unnecessary.

The primitives expose stale-rejection and lifecycle counters and are not internally synchronized. Current owners mutate them on renderer-owner paths; later async consumers must use their subsystem synchronization.

Current wiring:

- dynamic bindless block allocation/free tracks generations in `VkDescriptorSetManager`;
- `LevelMesh::Reset()` advances a LevelMesh resource epoch;
- `VkTextureManager` advances separate texture, lightmap, environment-probe and async-upload epochs at their real reset/destruction boundaries;
- `VkHardwareTexture` advances a per-target upload epoch on reset, consumed by PF-005 async upload tickets.

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

PF-004 makes this boundary explicit without turning hot elements into heap objects. `MeshBufferAllocator` assigns PF-002 generation/span identities to each non-empty recyclable range; invalid, wrong-span and duplicate frees fail closed, and stale diagnostic identities fail validation after retirement/reuse/reset. `LevelMeshMutationEpochs` records geometry, surface, light, query, portal and lightmap/probe domain changes while the existing Doom callbacks, `SurfaceUpdateType` and `MeshBufferUploads` remain authoritative. CPU/Vulkan acceleration-structure dirty partitioning now shares one exclusive-end contract. See `docs/shadedoomvk/PF-004-LEVELMESH-CONTRACT.md`.

## Lightmap/probe identity

Lightmap atlas pages and probe maps become adjacent bindless texture entries in the reserved lightmap range. Environment probes instead obtain dynamic two-slot bindless blocks (irradiance + prefiltered map) on demand.

PF-012 makes the three probe-index domains explicit instead of treating them as interchangeable integers:

1. **Authored probe ordinal** — `LightProbe::index`, used by map/sector-side probe ownership.
2. **Runtime environment descriptor identity** — `VkDescriptorSetManager::GetLightProbeTextureIndex(authoredIndex)` allocates/returns a dynamic two-slot block start for irradiance; the paired prefilter map is `start + 1`. This value is allocator-owned and is not derivable from the authored ordinal.
3. **Per-lightmap probe-map texel** — `R16_UINT` stores that runtime irradiance descriptor identity directly; value `0` is the explicit default/no-probe fallback.

Because the probe-map format is 16-bit, only allocator-returned irradiance descriptor indices in `1..65535` are representable. A probe whose maps do not yet exist resolves to `0`; a runtime descriptor outside the representable range is excluded rather than truncated. Since each live environment probe consumes an adjacent descriptor pair, at most 32768 candidate pair starts can exist in the 16-bit-addressable region, independent of allocator base or authored numbering.

The active lightmap-copy path reads the live probe set only when its current `VkLightmapper` LevelMesh owner matches the globally active level mesh. It resolves each authored probe through `GetLightProbeTextureIndex()` before uploading candidates. Selected atlas pages are checked against both the LevelMesh page count and current Vulkan lightmap resources before dereference. Probe placement changes mark lightmap tiles dirty and advance the `LightmapProbe` mutation domain so old texel mappings cannot silently survive a changed probe set.

Environment-probe reset remains owned by `VkTextureManager`'s PF-002 environment-probe epoch. `LightProbeIncrementalBuilder` now also resets those resources when the probe count changes or falls to zero. Existing descriptor pairs continue to point at their probe image objects across image clears; probe-set changes invalidate per-lightmap selection so obsolete authored candidates are not retained merely because an old descriptor remains addressable.

The experimental `LightProbeAABBTree` is not part of this live identity path; its `Update()`/`Upload()` remain dormant.

## Dynamic-light identity

Doom `FDynamicLight` objects are translated into `FDynLightInfo` lists and/or LevelMesh light records. Actor light collection may deduplicate by light pointer and then upload copied structs. Shadow maps also assign a finite shadow index.

Pointer identity is currently meaningful inside a frame/cache but must not become a persistent serialized identity.

### PF-017 source-owned temporal packing candidate

PR #74 keeps shader-visible `FDynLightInfo` arrays and `LightBufferSSO` offsets unchanged while attaching four packing snapshots to each live `FDynamicLight` incarnation, one for each existing force-attenuation/trace combination.

- A snapshot is owned by the actual `FDynamicLight` object incarnation, not by packed-byte equality. The existing `GetLight()` allocation/freelist path zeroes the complete object after allocation/reuse, so a recycled address cannot inherit the previous source's snapshot.
- Each changed packed record/class/group obtains a process-monotonic non-zero packing revision. Revision `0` means unqualified/fallback. Revision exhaustion fails closed instead of wrapping to a stale token.
- PF-010 top-level render epochs bound snapshot reuse. First qualified use in a new epoch executes the accepted packer; unchanged state may retain its revision. Portal recursion inherits its parent's PF-010 epoch, but foreign portal-group packing is deliberately unqualified.
- Spot lights, `RF2_LIGHTMULTALPHA` records, foreign-group records, sunlight and any record without a valid active context use accepted packing/copy behavior with revision `0`.
- `FDynLightData` preserves exact class/order and carries a parallel revision sequence. Persistent mapped-buffer shadows are meaningful only at the same physical record offsets; an entire class skips its mapped write only when every current revision is non-zero and equals the shadow at that exact position.
- Recreating `VkRSBuffers` recreates the mapped buffer and initializes revision/range shadows together. Ordinary `BeginFrame` resets write cursors but intentionally retains shadows describing the still-resident mapped bytes.
- Epoch rollback/reuse and revision wrap/exhaustion permanently disable the corresponding reuse mechanism for safety rather than accepting ambiguous identity.

This is renderer-local transient identity only; it is never a gameplay or serialized identity. Source head `e028fd88b29aa2d0d82e4e04a09ea644bfa56670` passed the complete off-GPU eight-job CI matrix in run 36047117838. Final PF-017 acceptance still requires the physical GTX 1650 SUPER performance/equivalence gate; until then this contract is a candidate on PR #74, not accepted `master` architecture.

## Async texture lifetime and staging

PF-005 replaces direct async upload-ID use at the `VkHardwareTexture` call site with a generation-aware ticket carrying the manager async epoch plus a per-target `FRendererEpoch` snapshot. The main-thread completion consumes/validates the manager ticket before it dereferences the target; a target reset advances the target epoch so work prepared for the previous incarnation is rejected. Destruction cancels **all** outstanding IDs for that owner before removal, closing the inherited one-match cancellation hole. Worker exception propagation and shutdown queue joining/clearing remain unchanged.

Ordinary texture create/completion uploads now share a lazily-created 64 MiB CPU-visible transfer-source arena. A Vulkan-independent staging planner assigns non-overlapping slices. Before a wrapped slice reuses byte zero, the Vulkan owner performs an upload-only wait, so in-flight bytes cannot be overwritten. A request larger than the arena uses a one-shot buffer and is waited/retired immediately rather than accumulating unbounded deferred staging memory.

The planner records requests, arena slices, reuses, wrap waits, oversize/invalid requests, bytes requested and high-water bytes; the Vulkan owner records physical persistent/dedicated allocations and dedicated waits. Exact texture formats, source processing, mip generation and material meaning remain unchanged. See `docs/shadedoomvk/PF-005-TEXTURE-UPLOAD-CONTRACT.md`.

## Lifetime transitions that require explicit treatment

- level load/unload;
- texture precache/cleanup;
- material destruction/recreation;
- sampler/filter changes that invalidate material descriptor variants;
- lightmap atlas recreation/page-count changes;
- probe cubemap reset/rebake;
- probe-set placement/count changes that invalidate per-lightmap texel selection;
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
4. Probe-map value `0` is fallback, not authored probe 0; authored probe identity must be resolved through the runtime bindless allocator before its irradiance descriptor is written to the map.
5. A changed probe set must invalidate per-lightmap texel selection before old mapping is trusted.
6. Async completion must consume/validate manager lifetime before dereferencing a target and must validate the target generation before upload/bind.
7. Staging bytes may not be reused until all transfer commands that reference those bytes are retired.
8. PF refactors must preserve content-visible texture/material meaning unless a correctness issue explicitly owns the change.
9. Single-byte texture storage format alone is not material identity: palette-index and RedIsAlpha/luminance variants must remain distinct through resident-image and descriptor caching.
