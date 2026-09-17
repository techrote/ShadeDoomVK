# LevelMesh mutation and invalidation matrix

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active, central renderer substrate  
Primary issues: PF-004, PF-018, SDVK-014

`LevelMesh`/`DoomLevelMesh` is the persistent renderer-side world representation used by lightmapping, renderer traces, Vulkan buffers and acceleration structures.

Primary files:

- `src/common/rendering/hwrenderer/data/hw_levelmesh.h/.cpp`
- `src/rendering/hwrenderer/doom_levelmesh.h/.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.h/.cpp`
- `src/levelmeshhelper.h`

## Ownership

`LevelMesh` owns generic renderer arrays, allocation/free-list state and dirty upload ranges. `DoomLevelMesh` owns Doom-side mapping and mutation callbacks. `VkLevelMesh` owns Vulkan mirrors/uploads and acceleration structures.

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

This table is an architectural requirement to validate, not a claim that every baseline callback already covers every column.

## Existing invalidation vocabulary

`DoomLevelMesh` already receives callbacks for floor/ceiling height, textures, decals, sector light and light-list changes. Side/flat blocks carry `SurfaceUpdateType` values such as `LightLevel`, `Shadows`, `LightList` and `Full`.

PF-004 should refine this vocabulary rather than create a second unrelated dirty-state system.

## Allocation/update behavior

`MeshBufferAllocator` keeps sorted free ranges and uses first-fit allocation. `MeshBufferUploads` merges dirty ranges. Geometry release degenerates old indices before returning ranges. PF-018 may optimize these structures only after PF-004 freezes ownership/invalidation semantics.

## Coupled resources

Lightmap page count influences texture/descriptor resources; probe maps share the lightmap-page concept. Resource rebuilds therefore participate in `02-RENDERER-IDENTITY-LIFETIME.md`.

## Required invariants

1. Visible world data and renderer query/occlusion data must describe the same current geometry.
2. Free/reallocated ranges must not leave live stale references.
3. Dirty-range merging may combine work but may not omit required updates.
4. Lightmap/probe invalidation must be explicit rather than relying on stale data looking plausible.
5. PF-018 performance work must preserve the PF-004 mutation contract.
