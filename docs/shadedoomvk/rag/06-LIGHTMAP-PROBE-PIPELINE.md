# Lightmap and probe pipeline

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: lightmapper active; PF-012 per-lightmap probe selection repaired; experimental probe AABB remains dormant  
Primary issues: PF-004, PF-010, PF-012, SDVK-010, SDVK-014

## Lightmapper

Primary files:

- `src/common/rendering/vulkan/vk_lightmapper.h/.cpp`
- `src/common/rendering/hwrenderer/data/hw_levelmesh.*`
- `src/rendering/hwrenderer/doom_levelmesh.*`
- `wadsrc/static/shaders/lightmap/*`

`VkLightmapper` contains raytrace, resolve, blur and copy stages. It can use Vulkan ray query when available and a fallback collision representation otherwise. LevelMesh lightmap tiles are atlas-packed and assigned to surfaces.

Map-level capabilities include sunlight, ambient-occlusion and bounce data/policy plus dynamic-lightmap configuration.

## Lightmap resources

`LevelMesh::Lightmap` tracks texture size/page count, tile list, used/free/added tiles and atlas packer. Vulkan texture manager creates per-page light textures and per-page probe-map textures. Descriptor layout reserves a fixed region for these resources.

PF-003 defines the page/descriptor range contract: every lightmap page consumes a light descriptor plus its adjacent probe-map descriptor. PF-012 additionally validates every selected atlas page against both the current LevelMesh page count and the current Vulkan lightmap resource vector before it is dereferenced. A mismatch fails closed rather than writing into an unrelated page.

## Environment probes

The level stores `LightProbe` positions/indices. UDMF can provide PBR lightprobe things; debug commands can add probes or auto-add one per sector.

Environment probe rendering is incremental in `hw_entrypoint.cpp`: the engine moves a LightProbe actor to the target location and renders cubemap faces. Vulkan stores irradiance and prefiltered cubemaps for PBR IBL.

PBR shader use:

- explicit surface/actor probe index can select an irradiance/prefilter pair;
- lightmapped surfaces gather a per-texel environment descriptor index from the lightmap-associated `R16_UINT` probe texture.

## PF-012 per-lightmap probe-map contract

PF-012 replaces the inherited `frag_copy.glsl` stub, which returned `0` for every texel, with a bounded live selector in the lightmap copy pass.

The value written to the `R16_UINT` probe map is **not** an authored `LightProbe` ordinal. It is the shader-visible environment-cubemap descriptor index consumed by `lightmodel_pbr.glsl`:

```text
probe-map value 0        = explicit default / no-probe fallback
authored probe N         = irradiance descriptor 2*N + 1
paired prefilter map     = irradiance descriptor + 1
maximum authored N       = 32767
maximum stored value     = 65535
```

The copy pass uploads a tightly-defined `vec3 position + uint textureIndex` candidate array and passes the live candidate count to the fragment shader. Each texel selects the nearest valid candidate within the inherited **512 world-unit** radius. The radius boundary is inclusive; equal-distance ties retain candidate order. With no valid candidate, no probes, a stale/non-current LevelMesh owner, or an unencodable descriptor identity, selection falls back to value `0`.

The selector is deliberately linear rather than reviving the unfinished GPU AABB traversal. This keeps the correctness path small and explicit; performance/spatial-acceleration work can replace the search later only if it preserves the same mapping/fallback contract.

The lightmapper owner check requires the globally active level mesh to be the same mesh currently installed in `VkLightmapper` before live `level.lightProbes` are consumed. This is a narrow bridge to current map-owned probe state, not a new cross-level identity mechanism.

## Probe AABB

`LightProbeAABBTree` can build a 2D CPU AABB binary tree over probe positions and has CPU closest-probe query code. PF-012 repairs leaf/root semantics, empty-root handling and replaces the inherited fixed traversal stack with a data-sized stack, but `Update()` and `Upload()` remain explicitly dormant.

The production per-lightmap probe-map shader does **not** read `LightProbeAABBTree` nodes. Do not describe or optimize the AABB path as production GPU selection unless a later issue deliberately integrates and validates it against the PF-012 selector contract.

## Probe target assignment

Level sectors/sides also carry nearest probe target indices. `FLevelLocals::RecalculateLightProbeTargets()` assigns targets through a closest-probe path. This is distinct from the per-lightmap texel probe-map path and keeps authored-probe identity rather than the `2*N+1` environment descriptor encoding.

Runtime `addlightprobe` and `autoaddlightprobes` changes recalculate those sector/side targets **and** invalidate all existing lightmap tiles for probe-map regeneration, advancing the LevelMesh `LightmapProbe` mutation domain. This prevents an updated probe set from leaving plausible-looking stale per-texel mappings.

## Automatic placement

PF-012 fixes sector automatic placement to use the true vertical midpoint:

```text
(floorZ + ceilingZ) * 0.5
```

The previous `floorZ + ceilingZ / 2` expression was wrong whenever the floor height was non-zero.

## Incremental builder and reset semantics

`LightProbeIncrementalBuilder` still performs up to five inherited bake iterations. PF-012 makes terminal behavior explicit:

- completed builders return without spinning;
- a probe-count change resets indices/collection/iteration state and calls `ResetLightProbes()` before rebaking;
- transition to an empty probe set also retires/reset previously allocated probe resources;
- `Full()` has an explicit no-progress guard so a future terminal `Step()` state cannot create an infinite loop.

The per-texel selector itself is independent of Vulkan ray-query support; ray-query-disabled lightmap baking continues to use the existing CPU/fallback collision representation while the same probe-map copy contract applies.

## PBR relationship

`lightmodel_pbr.glsl` uses irradiance for diffuse IBL and prefiltered cubemaps + BRDF LUT for specular IBL. Probe correctness therefore directly affects apparent roughness/metal response and can mask as a material problem. PF-012 changes only which already-authored probe pair is selected; it does not recalibrate PBR response or define actor probe policy.

## Invariants

1. Probe-map value `0` is the explicit fallback and may not be casually reinterpreted as authored probe 0.
2. Authored probe `N` maps to irradiance descriptor `2*N+1`; its paired prefilter descriptor is the next slot.
3. Sector/side nearest-probe assignment and lightmap per-texel probe mapping are separate mechanisms with different index meanings.
4. Atlas page changes must update both light and probe texture resources/indices safely; copy-time page identity must validate against both CPU page count and Vulkan resources.
5. Probe-set changes/rebakes must invalidate stale per-texel mapping and reset environment-probe resources at owner boundaries.
6. Probe rendering is a non-main render context and must not inherit main-view temporal assumptions.
7. The dormant AABB tree is not the active GPU probe selector.
8. SDVK-010 may qualify environment response only on top of this established plumbing/fallback contract.
