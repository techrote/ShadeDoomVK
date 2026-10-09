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

- explicit surface/actor probe index is resolved through `VkDescriptorSetManager::GetLightProbeTextureIndex()` to a runtime bindless irradiance/prefilter pair;
- lightmapped surfaces gather that same runtime irradiance descriptor index from the lightmap-associated `R16_UINT` probe texture.

## PF-012 per-lightmap probe-map contract

PF-012 replaces the inherited `frag_copy.glsl` stub, which returned `0` for every texel, with a bounded live selector in the lightmap copy pass.

The value written to the `R16_UINT` probe map is **not** an authored `LightProbe` ordinal and is **not** derivable from that ordinal by fixed arithmetic. `VkDescriptorSetManager` allocates each live environment probe as a dynamic two-slot bindless block: the returned block start is the irradiance descriptor and the immediately following descriptor is its paired prefilter map.

```text
probe-map value 0             = explicit default / no-probe fallback
authored probe N              = looked up through GetLightProbeTextureIndex(N)
stored non-zero value         = allocator-returned irradiance descriptor
paired prefilter descriptor   = stored irradiance descriptor + 1
maximum storable map value    = 65535 (R16_UINT)
```

If the environment maps for an authored probe are not yet available, `GetLightProbeTextureIndex()` returns `0`; that probe is excluded from the live candidate set until its pair exists. Likewise, an allocator result that cannot be represented by `R16_UINT` is excluded rather than truncated. The candidate buffer is bounded to 32768 entries because every valid live probe consumes an adjacent two-descriptor block and no more pair starts can exist inside the 16-bit addressable value space.

The copy pass uploads a tightly-defined `vec3 position + uint textureIndex` candidate array and passes the live candidate count to the fragment shader. Each texel selects the nearest valid candidate within the inherited **512 world-unit** radius. The radius boundary is inclusive; equal-distance ties retain candidate order. With no valid candidate, no probes, a stale/non-current LevelMesh owner, or an unencodable runtime descriptor identity, selection falls back to value `0`.

The selector is deliberately linear rather than reviving the unfinished GPU AABB traversal. This keeps the correctness path small and explicit; performance/spatial-acceleration work can replace the search later only if it preserves the same mapping/fallback contract.

The lightmapper owner check requires the globally active level mesh to be the same mesh currently installed in `VkLightmapper` before live `level.lightProbes` are consumed. This is a narrow bridge to current map-owned probe state, not a new cross-level identity mechanism.

## Probe AABB

`LightProbeAABBTree` can build a 2D CPU AABB binary tree over probe positions and has CPU closest-probe query code. PF-012 repairs leaf/root semantics, empty-root handling and replaces the inherited fixed traversal stack with a data-sized stack, but `Update()` and `Upload()` remain explicitly dormant.

The production per-lightmap probe-map shader does **not** read `LightProbeAABBTree` nodes. Do not describe or optimize the AABB path as production GPU selection unless a later issue deliberately integrates and validates it against the PF-012 selector contract.

## Probe target assignment

Level sectors/sides also carry nearest authored-probe target indices. `FLevelLocals::RecalculateLightProbeTargets()` assigns targets through a closest-probe path. This is distinct from the per-lightmap texel path: sector/side state keeps authored identity, while the lightmap copy pass resolves that authored identity through the live bindless allocator before writing the `R16_UINT` map.

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
- transition to an empty probe set invalidates the epoch and transfer-clears/re-publishes existing probe maps through `ResetLightProbes()` while keeping their image owners/views/descriptor pairs alive;
- `Full()` has an explicit no-progress guard so a future terminal `Step()` state cannot create an infinite loop.

The per-texel selector itself is independent of Vulkan ray-query support; ray-query-disabled lightmap baking continues to use the existing CPU/fallback collision representation while the same probe-map copy contract applies.

## PBR relationship

`lightmodel_pbr.glsl` uses irradiance for diffuse IBL and the adjacent prefiltered cubemap + BRDF LUT for specular IBL. Probe correctness therefore directly affects apparent roughness/metal response and can mask as a material problem. PF-012 changes only which already-authored runtime probe pair is selected; it does not recalibrate PBR response or define actor probe policy.

PF-113/#113 completes the missing-pair consumer contract in `SampleProbeIrradiance` and `SampleProbePrefiltered`: zero returns zero radiance before cube access or `base+1`. Uniform and gathered branches share those helpers. Mixed zero/live taps retain all four original coefficients and sum order; no weight renormalization or substitute environment is used. Ambient/direct/sunlight `Lo` remains independent, so zero IBL does not imply a black final surface. Live irradiance uses explicit LOD0 on the actual one-mip cube view with LINEAR min/mag, zero bias and disabled anisotropy; prefilter keeps the original roughness LOD. Both descriptor accesses use `nonuniformEXT`, including across divergent zero/live fragments. [Decision and sampling amendment](../PF-113-MISSING-IBL-DECISION.md) distinguish this policy from PF-012's original evidence. [Native qualification](../PF-113-FINAL-NATIVE-VERIFICATION.json) and [verified PR #117 release acceptance](../PF-113-RELEASE-ACCEPTANCE.json) record the bounded missing-to-published result; they do not accept the full freeze.

## Invariants

1. Probe-map value `0` is the explicit fallback and may not be casually reinterpreted as authored probe 0.
2. Authored probe identity and bindless descriptor identity are distinct: every live probe must be resolved through `GetLightProbeTextureIndex()`, whose returned irradiance slot is paired with the immediately following prefilter slot.
3. Sector/side nearest-probe assignment and lightmap per-texel probe mapping are separate mechanisms with different index meanings.
4. An allocator-returned environment descriptor that does not fit `R16_UINT` must fall back/exclude rather than truncate.
5. Atlas page changes must update both light and probe texture resources/indices safely; copy-time page identity must validate against both CPU page count and Vulkan resources.
6. Probe-set changes/rebakes must invalidate stale per-texel mapping and reset environment-probe resources at owner boundaries.
7. Probe rendering is a non-main render context and must not inherit main-view temporal assumptions.
8. The dormant AABB tree is not the active GPU probe selector.
9. SDVK-010 may qualify environment response only on top of this established plumbing/fallback contract.

## CFX-009 lifetime discriminator (#102)

The complete DBP37 read-fault interval joins the startup lightmap, retired on the one-to-zero atlas transition. Exact post-loss CPU indexed vertices do not request a lightmap; submitted GPU bytes remain unproven. `PARTIALLY_BOUND` permits undefined descriptors when dynamically unused, so the removed reserved views alone do not demonstrate a Vulkan violation.

`VkTextureManager::CreateLightmap` has an explicit experimental `CFX_RETAIN_REPLACED_LIGHTMAPS=1` ownership branch, enabled only with resource diagnostics. It keeps complete replaced light/probe objects until texture-manager teardown, bounded to128 pages with diagnostic failure before overflow. Defaults retain the existing frame-delete path. It changes neither descriptors nor shaders/uploads/waits/quality. The capture runner records the request; actual `lightmap-retention-enabled` / `lightmap-retained` events plus address history must prove activation. This is a causal probe, not a production crash repair. See [notebook](../CFX-009-CAUSAL-REPAIR.md).

## CFX-009 removed-page publication repair (#102 / PR104)

`VkDescriptorSetManager::UpdateBindlessDescriptorSet` now replaces previously published pages removed by atlas shrink with persistent correctly typed views, before submission and normal fence-controlled owner release. `VkPlanLightmapDescriptorPublication` checks the union of previous/current page ranges against the128-page reservation and actual descriptor capacity before writes; `PublishedLightmapPages` advances only after the writer executes. Current atlas views and dynamic descriptors beginning259 keep their existing ownership.

The constructor1×1 pair becomes private `VkTextureManager::LightmapFallback`, outside atlas resizing/baking/retirement. Explicit transfer clears initialize light RGBA16F to zero (no added baked/sunlight) and probe R16_UINT to0 (the existing PF-012 no-probe sentinel), followed by tracked transfer-write→fragment-read publication. This removes references to destroyed reserved views while preserving ordinary atlas retirement. It adds no waits or feature/quality changes. Sentinel0 does not prove arbitrary downstream PBR cube accesses safe; that inherited contract remains outside the demonstrated DBP37 path.

The original and matched retention-OFF runs fail at frame7 after the startup atlas unbind; retention ON succeeds. The source repair then passes three independent exact former reproducer runs with retention OFF, including the same old8MiB interval retiring normally at frame6, and exact safe pixels/protected state plus separate core/sync controls. This supports the descriptor-target retirement compatibility repair without assigning a unique executing shader, illegal dynamic access or NVIDIA driver defect. [Compact validation evidence](../evidence/cfx009-neutral-descriptor-validation.json).

## CFX-000 final disposition

PR #104's publication rule is the accepted lightmap/probe lifetime behavior: current pages publish real views; previously published pages removed by shrink publish the persistent initialized typed fallback pair before submission; the publication count advances only after successful descriptor execution; old atlas owners still retire through the ordinary fence-controlled delete list.

The retained `CFX_RETAIN_REPLACED_LIGHTMAPS` switch is explicitly experiment-only diagnostic infrastructure. Normal production and every accepted repaired/qualified target use retention OFF. The matched retention ON/OFF experiment remains historical causal evidence, not the runtime fix.

DBP37 succeeds 3/3 on the accepted repair, and original DBP50, DBP50 v1.2 and Sunlust/Champions each qualify 3/3 on the repaired GTX 1650 SUPER. These results do not prove that every historical incident dynamically sampled the removed descriptor or shared one mechanism. Repaired P400 behavior remains untested. PF-020 owns final-source regression/freeze verification of this invariant. See [final synthesis](../CFX-FINAL-PROGRAMME-SYNTHESIS.md).

## SDVK-004 page/probe pressure qualification

SDVK-004 exercises the existing ownership/publication rules rather than changing
them. The deterministic contract publishes the full 128-page fixed reservation,
shrinks to three active pages and requires fallback publication over all formerly
live reserved pages. Page 128 remains an explicit out-of-range failure and the
dynamic descriptor range still begins at 259.

Environment probes remain allocator-owned adjacent dynamic pairs. The rich
workload keeps 64 such pairs live while material pressure is present, then
retires/rebuilds them through PF-003 generation tracking. Lightmap recreation
advances `LightmapEpoch`; probe-content reset advances `LightProbeEpoch`
without pretending that retained irradiance/prefilter image owners were
recreated. Repeated stale-token checks cover both owner epochs.

See [SDVK-004 descriptor stress](../SDVK-004-DESCRIPTOR-STRESS.md) and the
[release receipt](../SDVK-004-RELEASE-ACCEPTANCE.json). The accepted post-merge
software-Vulkan probe scene publishes one lightmap page and two irradiance/two
prefilter maps with zero descriptor failures/invalid frees. No new lightmap/probe
identity, emergency flush or retention policy is introduced.
