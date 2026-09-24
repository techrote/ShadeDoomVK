# LevelMesh mutation and invalidation matrix

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: PF-004 mutation/allocation contract active; PF-012 probe-map invalidation and PF-015 visibility-cache consumption incorporated; PF-018 accepted with hybrid best-fit free-span lookup and cached immutable AABB topology, preserving those semantics
Primary issues: PF-004, PF-012, PF-015, PF-018, SDVK-014

`LevelMesh`/`DoomLevelMesh` is the persistent renderer-side world representation used by lightmapping, renderer traces, Vulkan buffers and acceleration structures.

Primary files:

- `src/common/rendering/hwrenderer/data/hw_levelmesh.h/.cpp`
- `src/common/rendering/hwrenderer/data/hw_levelmesh_contract.h`
- `src/common/rendering/hwrenderer/data/hw_aabbtree.h/.cpp`
- `src/rendering/hwrenderer/doom_levelmesh.h/.cpp`
- `src/rendering/hwrenderer/doom_aabbtree.h/.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.h/.cpp`
- `src/levelmeshhelper.h`

## Ownership

`LevelMesh` owns generic renderer arrays, allocation/free-list state and dirty upload ranges. `DoomLevelMesh` owns Doom-side mapping and mutation callbacks. `VkLevelMesh` owns Vulkan mirrors/uploads and acceleration structures.

PF-004 adds an inspectable diagnostic vocabulary over those existing owners:

- `Geometry` — vertex/index allocation and replacement;
- `Surface` — surface, material, uniform and light-uniform state;
- `Lights` — persistent lights, light lists and dynamic-light uploads;
- `Query` — renderer trace/collision and AS-visible world state;
- `Portals` — uploaded portal transform/metadata state;
- `LightmapProbe` — lightmap tile/atlas/probe dependencies.

`LevelMeshMutationEpochs` records domain changes. It is not a second scheduling system: `SurfaceUpdateType`, Doom callbacks, `MeshBufferUploads`, CPU collision updates and Vulkan upload/AS paths remain authoritative.

## Mutation expectations

| Mutation | Geometry | uniforms/material | lights | renderer trace data | lightmap/probe | GPU/AS |
|---|---|---|---|---|---|---|
| floor/ceiling height | update | update | possible membership | update | affected tiles/targets | dirty buffers and AS as needed |
| side/midtexture geometry | update | update | possible membership | update | affected tiles | dirty buffers and AS as needed |
| texture/material change | shape unchanged | update | normally unchanged | unchanged | material/lightmap association may change | uniforms/descriptors |
| sector light level | unchanged | light uniforms | interaction changes | unchanged | dynamic-lightmap policy | light uniforms |
| side/sector light list | unchanged | light refs | update | unchanged | dynamic inputs | light-index/light buffers |
| dynamic light change | unchanged | unchanged | update | unchanged | dynamic inputs | light/dynlight buffers |
| decal change | rendered surface state changes | update | affected lighting | normally unchanged | affected rendering | geometry/uniform ranges as applicable |
| polyobject motion | update | update | membership can change | update | affected dynamic tiles | dynamic AS/update |
| portal transform/topology | portal/related geometry metadata | update | portal-relative positions | traversal semantics | visibility/targets | portal/surface buffers and related AS |
| lightmap atlas repack | unchanged | lightmap coordinates/index | unchanged | unchanged | atlas metadata changes | vertices/descriptors |
| probe set/rebake | unchanged | sector/side probe target | unchanged | unchanged | **all existing per-texel probe mappings stale** | probe descriptors/maps |

PF-004 validated the base table against production callbacks and made the owned domains inspectable through `LevelMeshMutationEpochs`. PF-012 makes the probe-set row executable for runtime debug placement: `addlightprobe` and `autoaddlightprobes` recalculate sector/side targets, mark every existing lightmap tile `ReceivedNewLight`, and advance `LightmapProbe` before the map can be trusted again. The epochs diagnose existing invalidation paths; they do not replace `SurfaceUpdateType`, upload ranges or callback scheduling.

PF-015 consumes the already-authoritative `Query` epoch at actor/static-light and sunlight visibility-cache boundaries. A geometry/query mutation therefore invalidates cached visibility even if actor and light positions remain unchanged. PF-015 does not increment `Query` itself and does not add a second world-dirty mechanism.

## Existing invalidation vocabulary

`DoomLevelMesh` receives callbacks for floor/ceiling height, textures, decals, sector light and light-list changes. Side/flat blocks carry `SurfaceUpdateType` values `LightLevel`, `Shadows`, `LightList` and `Full`; conflicting partial requests coalesce to `Full`.

PF-004 keeps that vocabulary. `OnSectorChangedTexZ()` now schedules both sidedefs of a two-sided line rather than suppressing sidedef 1 through `else if`. The inherited `OnMidTex3DHeightChanged()` no-op remains explicitly unclaimed: PF-004 does not substitute a broad refresh without source-proven ownership semantics.

PF-012 does not introduce another surface-update class. Probe-set changes reuse the existing tile rebake trigger because the lightmap copy stage writes both the lighting result and the associated per-texel probe-map result.

PF-015 similarly does not add a mutation producer. It records the current `GetMutationEpochs().Query` in renderer visibility-cache state and rejects reuse when that value changes.

## Allocation/update behavior

`MeshBufferAllocator` keeps address-ordered free ranges as the coalescing/validation authority. The PF-018 implementation scans lists of at most eight ranges for deterministic best fit, avoiding index-node churn in lightly fragmented moving-polyobject frames. Larger lists use a `{span size, start address}` index. Both paths choose the lowest address among equal-size spans. PF-004 PF-002 generation/span tracking and fail-closed bounds, wrong-span, overlap and double-free checks remain authoritative; lookup does not create a second ownership model.

PF-018 growth is bounded geometric growth: on a miss, capacity grows by the larger of the required extension and 50% of current capacity, clamped to `INT_MAX`. Existing live allocations remain stationary. `pf018stats` exposes search/candidate counts, small-list/indexed attempts and index mutations, grow events/elements, peak free-range count and peak/used/free capacity for representative-workload comparison.

`MeshBufferUploads` remains the dirty-range authority and retains its existing merge semantics in PF-018. No copy batching/upload rewrite is claimed without byte-identical real-workload evidence; callers can continue to inspect the authoritative merged ranges when collecting upload counts/volume.

The Doom world AABB tree has immutable topology after construction: polyobject motion changes line coordinates and bounding boxes, not child edges. PF-018 therefore caches each tree line's leaf plus each node's parent once after construction. Moving-line updates reconstruct the same historical leaf→root path by following parents instead of recursively searching the complete tree from the root on every changed line. Any future topology mutation must rebuild this cache; bounding-box-only updates do not invalidate it. Observational counters cover cache builds, path lookups/steps, moved lines, updated nodes and cumulative update time.

CPU and Vulkan acceleration-structure paths continue to share `MeshBufferChunkStart()` / `MeshBufferChunkEndExclusive()`. The exclusive end is rounded up, fixing the CPU path that previously selected zero BLAS partitions when a dirty index range fell wholly inside one partition. Vulkan dirty marking remains bounded by the currently allocated BLAS vector while buffer growth is waiting for `CheckBuffers()` to reset/recreate acceleration structures.

## Coupled resources

Lightmap page count influences texture/descriptor resources; probe maps share the lightmap-page concept. Resource rebuilds therefore participate in `02-RENDERER-IDENTITY-LIFETIME.md`.

Tile allocation/release advances the `LightmapProbe` mutation domain. Atlas packing explicitly places rewritten lightmap UV/page vertices in the vertex upload range. Light-list and shadow changes retain the existing `ReceivedNewLight` tile invalidation and advance the diagnostic domain.

PF-012 adds a second boundary check at the actual lightmap copy consumer: a selected tile's `AtlasLocation.ArrayIndex` must be below both `LevelMesh::Lightmap.TextureCount` and the Vulkan texture manager's current lightmap resource vector. Mismatch fails closed before framebuffer/image dereference. The mapped copy-tile staging range is also checked before per-page writes.

## Required invariants

1. Visible world data and renderer query/occlusion data must describe the same current geometry.
2. Free/reallocated ranges must not leave live stale references; allocator diagnostic identities must reject old generations after free/reuse/reset.
3. Dirty-range merging may combine work but may not omit required updates; a non-empty range must touch every CPU/Vulkan BLAS partition it intersects.
4. Lightmap/probe invalidation must be explicit rather than relying on stale data looking plausible; tile/atlas changes advance the `LightmapProbe` domain and atlas UV/page writes are uploaded.
5. A changed probe set makes every existing per-lightmap texel probe selection stale; runtime placement paths must schedule regeneration before those mappings are trusted.
6. Lightmap copy page identity must be valid in both current LevelMesh metadata and current Vulkan resources before use.
7. Two-sided Doom mutation callbacks must schedule both affected sidedefs; `OnSectorChangedTexZ()` is source-pinned by the PF oracle.
8. Any renderer visibility cache whose result depends on LevelMesh trace geometry must reject reuse across a `Query` epoch change; PF-015 pins this at actor/static-light and sun-trace caches.
9. PF-018 allocator indexing/growth must preserve PF-004 generation/span ownership and may not move live ranges.
10. PF-018 AABB caching may change path-discovery cost only: leaf identity, leaf→root order, updated AABBs and trace/query results must remain identical. Any topology mutation requires cache rebuild before cached paths are reused.
11. PF-018 acceptance requires a representative real renderer CPU/memory/resource benefit plus identical protected image/query/state semantics on the changed path. The reconciled implementation demonstrated DBP37 MAP04 array-capacity benefit and targeted moving-AABB query/image equivalence; final-head CI, PR #68 merge and post-merge verification passed on exact recorded SHAs. See `docs/shadedoomvk/PF-018-RUNTIME-EVIDENCE.md` for the exact pair, measurements, exclusions and limits.

See `docs/shadedoomvk/PF-018-RUNTIME-EVIDENCE.md` for the paired runtime qualification, `docs/shadedoomvk/PF-004-LEVELMESH-CONTRACT.md` for the executable ownership/allocator/AS contract, `docs/shadedoomvk/PF-015-SHADOW-VISIBILITY-CONTRACT.md` for the PF-015 cache consumer contract, `docs/shadedoomvk/issues/PF-018.md` for the performance candidate/acceptance boundary, and `rag/06-LIGHTMAP-PROBE-PIPELINE.md` for the PF-012 probe-map mapping/fallback contract.
