# SDVK-014 production ownership audit and coverage matrix

## Authority and scope

Audit baseline: `04a3596115eb397d9e7237aa1ff3625ece1bc5b4`, tree
`f337a3de6091e396333a9816c653a7afcd84f3f5`, verified from the exact-master
Renderer source evidence run `38578537600`, artifact `11901562216` (archive
SHA-256 `ca3e472edb2288d016f885f2036ab9634a491d678e411a84653d382e6adb4911`).
The bundle's commit, tree and internal SHA256SUMS match the checkout. Normal
baseline CI `38578537819` passed. No renderer or Vulkan device is run locally.

Issue #14 remains open. Its entry comment, #9's split authority and #10's
final acceptance comment `6167916940` agree with the canonical dependency
record. PR #149 releases **software work only**, not physical acceptance.
#10's accepted substantive tree is `c520fd111c8da5c6714c60a5bc256247e4569577`.
Accepted PF-004 is PR #41, PF-012 is PR #59; PF-113's release receipt pins PR
#117. SDVK-002 observability and SDVK-005 material semantics remain consumers'
authority. SDVK-011 has its separate `sdvk011-viewmodel-lighting` branch; this
campaign does not own its viewmodel policy.

This audit was written **before the new fixtures**. Entries below are source
observations, not an assertion that every path has been exercised. The software
campaign is not accepted by an audit, inherited passing tests or hosted timing.
Physical STOP is ACTIVE; physical cost/scaling/stability are HELD / NOT ACCEPTED;
historical physical fault root cause remains UNDETERMINED.

## Identity model actually present

`DoomLevelMesh` owns semantic side/subsector/control-sector bindings and CPU
`LightmapTile` slots. `LevelMesh::Lightmap` owns the tile pool, free indices,
added-tile/surface queues and `RectPacker`; its `TextureCount` comes from actual
packer pages. A tile's atlas item, page and rectangle are runtime identities,
not its semantic binding. In the audited baseline there is **no per-tile or
per-rectangle durable generation token**. Safety therefore requires that retired
tiles cannot remain producers/consumers. Existing LevelMesh resource and mutation
epochs must not be misrepresented as such a token.

`VkTextureManager` owns actual lightmap/probe images and views. Its LightmapEpoch
advances on whole-atlas CreateLightmap; incremental SetLightmapCount adds pages
without replacing old pages. Image diagnostic IDs distinguish actual allocations.
The PF-003 bindless allocator owns dynamic descriptor generations/epochs/spans.
Reserved lightmap page pairs are republished through the CFX-009 current/previous
page-union contract, with persistent typed neutral views for removed pages.
These are separate identities, not interchangeable equal-valued counters.

Authored `LightProbe::index` is an ordinal, including valid ordinal 0.
`GetLightProbeTextureIndex` resolves a published irradiance/prefilter pair whose
adjacent runtime slots are allocator-owned; missing publication returns 0.
Probe-map R16_UINT texels contain runtime irradiance starts, not ordinals.
PF-113 guards runtime 0 before cube access or pair arithmetic. Environment reset
clears retained image objects and advances LightProbeEpoch; it is not image or
descriptor recreation. The global incremental builder currently records count
and progress, not a map/LevelMesh owner identity; this boundary needs a retained
counterexample before further cross-map probe acceptance.

## Exact production-path map

| Path | Authoritative owner and producer | Identity / invalidation / rebuild | Consumer and fallback |
| --- | --- | --- | --- |
| Static bake | `src/commandlets/lightmapcmd.cpp`, `LightmapBuildCmdlet::OnCommand`; `HWDrawInfo::UpdateLightmaps`; `VkLightmapper::Raytrace` | Real CPU tiles selected, then raytrace/resolve/optional blur/copy; geometry and lighting flags schedule work | `CopyResult` writes current page light/probe attachments; no image-quality reduction is authorized |
| Retained load | `src/maploader/maploader.cpp`, `InitLevelMesh` / `LoadLightmap` | LIGHTMAP v4 binding `(type,typeIndex,controlSector)`, RGB16F data and transforms; `PackLightmapAtlas` assigns new page/coordinates | `VulkanRenderDevice::BeginFrame` uploads pending TextureData; no lump uses ordinary scheduled bake |
| Delete | `DoomLevelMesh::DeleteLightmapLump` | Removes LIGHTMAP from on-disk PWAD only; it does **not** delete/rebuild the live atlas | Current map stays current; a subsequent map load observes the deletion |
| Tile/atlas allocation | `DoomLevelMesh::AddSurfaceToTile`; `LevelMesh::AllocTile`; `RectPacker::Alloc` | Semantic bindings share UseCount; CPU slot reuse and shelf allocation create runtime coordinates | Vertices/decals and bake copy consume tile coordinates; unassigned surface index is -1 |
| Repack/rebuild | `LevelMesh::PackLightmapAtlas`; `RefreshLightmap` / `FullRefresh` | Added tiles are packed; full surface refresh releases/recreates tiles. There is no separate general compaction algorithm | Added surfaces' UV/page vertices are updated and uploaded; old raw indices are not durable identities |
| Multiple pages | `RectPacker::CreateShelf`, `LevelMesh::Lightmap::TextureCount`; `VkTextureManager::SetLightmapCount` | Page expansion retains old page owners; CreateLightmap replaces the atlas under normal fenced retirement | `CopyResult` checks both mesh and Vulkan page ranges; bindless supports at most 128 page pairs |
| Dynamic updates | Doom callbacks, `DoomLevelMesh::BeginFrame`, `HWDrawInfo::UpdateLightmaps` | UpdateType coalesces; geometry updates precede packing, light upload and collision update | Geometry tiles are mandatory; ordinary light/background updates are intentionally budgeted. Zero-lag for every light change is **not yet established** |
| Moving/changing lights | `UpdateLightShadows`, `UpdateSideLightList`, `UpdateFlatLightList`, `UploadDynLights`, `CopyToMeshLight` | Actual portal-relative position, radius, intensity and colour copied; affected tile ReceivedNewLight flags | Existing light-list/trace semantics; disabled-light freshness still needs an end-to-end witness |
| Moving/changing sectors | `OnFloorHeightChanged`, `OnCeilingHeightChanged`, `OnSectorChangedTexZ`, texture/light callbacks | Actual side/flat Full or LightLevel/LightList updates; full updates release old tile associations | Current regenerated surface UVs and query geometry; no broad-refresh substitute for unowned callbacks |
| Polyobjects | `DoomLevelMesh::BeginFrame`, PolySides / PolySegs | Existing full poly-side update and source portal-group light-list creation | Current poly surfaces; full supported-motion acceptance is pending |
| Probe-map generation | `VkLightmapper::UploadProbeSelection`, `CopyResult`; `shaders/lightmap/frag_copy.glsl` | Live ordinal resolution, representable runtime descriptor, same LevelMesh XYZ coordinates | Nearest inclusive 512-unit choice, first tie; fallback runtime 0; dormant probe AABB path stays dormant |
| Ordinal publication | `doom_lightprobes.cpp`; `FLevelLocals::RecalculateLightProbeTargets` | Authored append/recalculation dirties lightmap probe selection; authored 0 is not absence | Accepted SDVK-010 actor source/sector semantics and PF-012 tile selector remain distinct |
| Cubemap pair publication | `LightProbeIncrementalBuilder::Step`; `VkLightprober`; `VkTextureManager::CopyIrradiancemap` / `CopyPrefiltermap` | EndLightProbePass copies both generated families; GetLightProbeTextureIndex requires both views | Adjacent live dynamic pair or runtime 0; same-count new-map freshness is an identified review gap |
| Descriptor generation | `vk_descriptorset.cpp`, PF-003 allocator; `UpdateBindlessDescriptorSet` | Dynamic free/reuse token; lightmap reserved pairs republished before submission; normal fences retire resources | Do not infer validity from a nonzero index; invalid/stale ordinal admission remains to be exercised |
| LevelMesh invalidation | `LevelMesh::Reset`, Doom callbacks / mutation epochs | Reset invalidates resource epoch; geometry/query/lightmap mutation domains remain diagnostic, not substitute scheduling | Existing CPU/Vulkan rebuild and upload ordering; raw per-tile generations are not supplied by this epoch |
| Teardown | `FLevelLocals::ClearLevelData` in `src/p_setup.cpp`; LevelMesh/texture/descriptors owners | Level mesh is deleted and nulled; actual texture/descriptor reset paths retain their separate fence/epoch semantics | Cross-map builder ownership must be proved independently of object-address or probe-count equality |
| Rebake/republication | `RefreshLightmap`, queued Full updates, normal BeginFrame; commandlet bake/save | Recomputed geometry and atlas regions; pending RGB upload and RGBA download must not share a persistent representation | Next load must bind current semantic tiles, not retired entries or old upload payload |
| Missing/incomplete publication | PF-113 sampling guard, CFX-009 removed-page fallback, `GetLightProbeTextureIndex` | Runtime 0 is typed zero-radiance IBL; reserved removed-page pair is actual neutral 2D resources | Does not prove newly allocated, not-yet-written active atlas texels are initialized; that is a separate open audit concern |

Paths use the repository's normal `src/common/rendering/hwrenderer/data`,
`src/common/rendering/vulkan` and `src/rendering/hwrenderer` ownership. No fixture
may change a renderer decision through the state observer.

## Robustness matrix and acceptance boundary

| Class | Required cases | Initial source finding / work disposition |
| --- | --- | --- |
| A: static lifecycle | bake, load, repeat load, delete, rebake, reload, absent/invalid retained state | Audit found save loops selecting retired tiles by plausible page number, RGBA readback stored in RGB upload input, and unchecked retained pixel spans. Implement bounded CPU-reproduced fixes; native round-trip acceptance remains separate |
| B: dynamic updates | movement, colour/intensity, disable/enable, sector geometry, polyobjects, repeats | Preserve actual scheduling and quality. Retired-tile scheduling is in the first repair; current-state pixel freshness for all supported changes remains pending |
| C: allocation | single/multiple pages, exact fill, free/reallocate, Clear/rebuild, expansion | Execute the real RectPacker with an independent occupancy oracle. Check exact-height rejection, invalid dimensions before mutation and repeated clear/reuse. Default atlas is 1024, bake staging 2048; do not claim a default 1018-high tile fills staging |
| D: probe lifecycle | publish/reset/rebake, pair/epoch/span, missing/stale/out-of-range ordinal, authored 0/runtime 0 | Preserve accepted PF-012/PF-113. Retain a production-builder same-count new-map counterexample; a confirmed foundational gap reblocks that affected scope rather than accepting it locally |
| E: repeated transitions | bounded bake/use/reset/rebuild and publish/use/invalidate/republish | CPU liveness/allocator loops are not a software-Vulkan repeated capture. No unbounded soak or duplicate runner |
| Topology | ordinary/linked portals, mirrors, 3D floors, Line_Horizon, decals | PortalIndex/SectorGroup and PF-010 context ownership stay intact. Sky/horizon surfaces explicitly have no lightmap tile. OnMidTex3DHeightChanged is still an explicit unowned/no-op limitation, not claimed supported by this repair |
| Materials | albedo, normal, legacy, PBR/AO, height, translated/custom, warped/reflective/translucent | Preserve copied FMaterialState and all SDVK-005 layer/sampler ordering. Existing corpus is regression evidence, not proof of every lifecycle/topology combination. World stock height does not imply POM support |
| Resources | atlas pages, allocations, live tile count, upload size, generations, bounded repetitions | Retain exact counters for executed CPU cases; no GPU memory/performance claim. Shelf fragmentation and untested high-water behaviour are not silently labelled leak-free |
| Native | current source, full normal CI, one existing Avrea 16-vCPU software lane | Source/CPU success is not a native render. No duplicate full run for benchmarking; exact-head native status belongs in the qualification receipt |
| Physical | bake/update cost, scaling, hardware stability, historical fault causality | HELD / NOT ACCEPTED under Physical STOP. Hosted llvmpipe timing is descriptive only |

## Review findings to reproduce, not conceal

Retired tile slots retain plausible page/rectangle/binding fields in the baseline;
freeing the atlas item alone does not prevent all-pool bake/save scans selecting
them. Likewise, pending RGB upload data is not an RGBA readback scratch buffer.
Malformed retained state must be rejected before tile flags/transforms/publication
change, with no out-of-bounds source read or silent partial association.

The current builder's global lifetime crosses maps but its progress state only
notices count changes; RenderView also does not call Step for an empty probe set.
This is a **source-derived candidate blocker**, not a claimed executed Vulkan
failure. A CPU counterexample must retain exactly which transition fails. Do not
rewrite PF acceptance history or claim a historical physical fault explanation.

Further review gaps include active atlas initialization before the first complete
write, missing durable rectangle tokens, and selected-tile completion flags cleared
before actual rendering. They are not waived by fixing one retired-state path.
The campaign cannot be labelled SOFTWARE-COMPLETE while these are unresolved or
without its required native stress/state/capture evidence.

## Executed increment disposition

The [first CPU increment](SDVK-014-CPU-INCREMENT.md) repairs the reproduced atlas
boundary/debug-reset, retired tile, save/readback and pending-upload defects.
The [receipt](evidence/SDVK-014-CPU-INCREMENT.json) retains 22 positive case programs,
15 intended retained-source rejections and two **current blocked** probe cases.
The source-derived same-count owner concern above is now CPU-reproduced and
tracked as **upstream #150**, reblocking cross-map probe acceptance. Other initial
audit gaps remain gaps, not passed criteria. No full software or physical acceptance.

Parallel-work comment `6173487725` confirms #11 owns `hw_weapon.*`, HUD-model
integration and its own observer/fixtures. This increment changes none of them.


## 15 October continuation disposition

Three initial audit gaps are now closed by bounded production changes on the same
branch: retained LIGHTMAP entries are fully admitted before mutating current tile
state; dynamic completion flags are retired only after rendered copy/publication;
and newly expanded light/probe atlas pages are transfer-cleared to typed zero
fallbacks before shader-readable publication. The corresponding source/CPU
negative controls deliberately remove each invariant and must fail for the named
reason.

These changes do not supply a durable per-allocation generation token, cross-map
probe owner identity, native multi-map/multi-page evidence, or special-surface/
material compatibility acceptance. #150 still blocks the affected probe lifecycle.


### Retained 3D-floor/control-sector identity

`LightmapTileBinding::ControlSector` is a sector ordinal produced by
`sector_t::Index()`. Retained LIGHTMAP admission now validates that ordinal in
the sector namespace rather than against subsector count. This closes a semantic
namespace mismatch without broadening support or changing fallback policy.


### Full replacement active-page initialization

The initial/replacement `CreateLightmap` path is now covered in addition to
incremental `SetLightmapCount`. Every new probe-map page receives defined
R16_UINT zero fallback content; light pages with no retained RGB source receive
defined zero light. This prevents full atlas replacement from publishing
undefined-but-plausible probe/light texels before dynamic writes complete.


### 3D-floor side visibility identity

Special-surface review found that 3D-floor wall tiles were keyed by
`(type, side, controlSector)` but side-bake visibility consumed only
`(type, side)`. Because `BuildFFBlock` can emit multiple same-type walls on
one side for different `rover->model` owners, this was a plausible-but-wrong
cross-control-sector bake path. `GetVisibleSurfaces` now preserves
`ControlSector` for side surfaces exactly as it already did for flat surfaces.
