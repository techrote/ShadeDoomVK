# Lightmap and probe pipeline

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: lightmapper active; probe pipeline mixed active/partial  
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

`LevelMesh::Lightmap` tracks texture size/page count, tile list, used/free/added tiles and atlas packer. Vulkan texture manager creates per-page light textures and per-page probe-map textures. Descriptor layout reserves a fixed region for these resources in the baseline.

This page-count ↔ descriptor-range coupling is a PF-003/PF-012 boundary condition.

## Environment probes

The level stores `LightProbe` positions/indices. UDMF can provide PBR lightprobe things; debug commands can add probes or auto-add one per sector.

Environment probe rendering is incremental in `hw_entrypoint.cpp`: the engine moves a LightProbe actor to the target location and renders cubemap faces. Vulkan stores irradiance and prefiltered cubemaps for PBR IBL.

PBR shader use:

- explicit surface/actor probe index can select an irradiance/prefilter pair;
- lightmapped surfaces have a path intended to gather per-texel probe indices from the lightmap-associated probe texture.

## Critical baseline limitation: per-lightmap probe map

`wadsrc/static/shaders/lightmap/frag_copy.glsl` currently compiles a `findClosestProbe()` stub that returns `0` for every texel under `#if 1`.

The disabled branch contains an intended probe-node traversal but is not production-ready; it includes unfinished/inconsistent references and cannot be assumed correct merely by switching the preprocessor branch.

PF-012 must treat this as a real incomplete subsystem: reproduce current behavior, define the intended mapping contract, repair or explicitly defer it, and test bounds/index/lifetime behavior.

## Probe AABB

`LightProbeAABBTree` can build a 2D AABB binary tree over probe positions and has CPU closest-probe query code. At the audited baseline, `Update()` and `Upload()` are empty, so integration is partial.

Do not describe the AABB/probe-map system as fully active until PF-012 verifies the actual path.

## Probe target assignment

Level sectors/sides also carry nearest probe target indices. `FLevelLocals::RecalculateLightProbeTargets()` assigns targets through a closest-probe path. This is distinct from the per-lightmap texel probe-map path.

## Confirmed automatic placement defect

`autoaddlightprobes` computes Z as `floorZ + ceilingZ / 2` rather than `(floorZ + ceilingZ) / 2`, so non-zero floor heights place probes too high. PF-012 owns the fix and fixture.

## Incremental builder edge condition

`LightProbeIncrementalBuilder` limits baking iterations. Its `Full()` behavior after a completed terminal state must be regression-tested for progress/termination; PF-012 owns any necessary fix.

## PBR relationship

`lightmodel_pbr.glsl` uses irradiance for diffuse IBL and prefiltered cubemaps + BRDF LUT for specular IBL. Probe correctness therefore directly affects apparent roughness/metal response and can mask as a material problem.

## Invariants

1. Probe index `0` fallback semantics must remain explicit.
2. Sector/side nearest-probe assignment and lightmap per-texel probe mapping are separate mechanisms.
3. Atlas page changes must update both light and probe texture resources/indices safely.
4. Probe reset/rebake must invalidate descriptor/resource identity safely.
5. Probe rendering is a non-main render context and must not inherit main-view temporal assumptions.
6. SDVK-010 should qualify environment response only after PF-012 establishes trustworthy plumbing/fallback.
