# LevelMesh mutation and invalidation matrix

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: PF-004 mutation/allocation contract active; PF-018 performance work must preserve it  
Primary issues: PF-004, PF-018, SDVK-014

`LevelMesh`/`DoomLevelMesh` is the persistent renderer-side world representation used by lightmapping, renderer traces, Vulkan buffers and acceleration structures.

Primary files:

- `src/common/rendering/hwrenderer/data/hw_levelmesh.h/.cpp`
- `src/common/rendering/hwrenderer/data/hw_levelmesh_contract.h`
- `src/rendering/hwrenderer/doom_levelmesh.h/.cpp`
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
| probe set/rebake | unchanged | probe target/index | unchanged | unchanged | probe data changes | probe descriptors/maps |

PF-004 validated this table against production callbacks and made the owned domains inspectable through `LevelMeshMutationEpochs`. The epochs diagnose existing invalidation paths; they do not replace `SurfaceUpdateType`, upload ranges or callback scheduling.

## Existing invalidation vocabulary

`DoomLevelMesh` receives callbacks for floor/ceiling height, textures, decals, sector light and light-list changes. Side/flat blocks carry `SurfaceUpdateType` values `LightLevel`, `Shadows`, `LightList` and `Full`; conflicting partial requests coalesce to `Full`.

PF-004 keeps that vocabulary. `OnSectorChangedTexZ()` now schedules both sidedefs of a two-sided line rather than suppressing sidedef 1 through `else if`. The inherited `OnMidTex3DHeightChanged()` no-op remains explicitly unclaimed: PF-004 does not substitute a broad refresh without source-proven ownership semantics.

## Allocation/update behavior

`MeshBufferAllocator` keeps sorted free ranges and uses first-fit allocation. PF-004 adds PF-002 generation/span tracking plus fail-closed bounds, wrong-span, overlap and double-free checks while preserving the inherited growth policy for PF-018. `MeshBufferUploads` remains the dirty-range authority. Geometry release degenerates old indices before returning validated ranges.

CPU and Vulkan acceleration-structure paths now share `MeshBufferChunkStart()` / `MeshBufferChunkEndExclusive()`. The exclusive end is rounded up, fixing the CPU path that previously selected zero BLAS partitions when a dirty index range fell wholly inside one partition. Vulkan dirty marking is also bounded by the currently allocated BLAS vector while buffer growth is waiting for `CheckBuffers()` to reset/recreate acceleration structures.

## Coupled resources

Lightmap page count influences texture/descriptor resources; probe maps share the lightmap-page concept. Resource rebuilds therefore participate in `02-RENDERER-IDENTITY-LIFETIME.md`.

Tile allocation/release advances the `LightmapProbe` mutation domain. Atlas packing explicitly places rewritten lightmap UV/page vertices in the vertex upload range. Light-list and shadow changes retain the existing `ReceivedNewLight` tile invalidation and advance the diagnostic domain.

## Required invariants

1. Visible world data and renderer query/occlusion data must describe the same current geometry.
2. Free/reallocated ranges must not leave live stale references; allocator diagnostic identities must reject old generations after free/reuse/reset.
3. Dirty-range merging may combine work but may not omit required updates; a non-empty range must touch every CPU/Vulkan BLAS partition it intersects.
4. Lightmap/probe invalidation must be explicit rather than relying on stale data looking plausible; tile/atlas changes advance the `LightmapProbe` domain and atlas UV/page writes are uploaded.
5. Two-sided Doom mutation callbacks must schedule both affected sidedefs; `OnSectorChangedTexZ()` is source-pinned by the PF oracle.
6. PF-018 performance work must preserve the PF-004 mutation contract.

See `docs/shadedoomvk/PF-004-LEVELMESH-CONTRACT.md` for the executable ownership/allocator/AS contract and adversarial fixture coverage.
