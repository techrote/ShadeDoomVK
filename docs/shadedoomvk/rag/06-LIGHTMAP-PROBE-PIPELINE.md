# Lightmap and probe pipeline

## Current downstream software authority — 14 October 2026

The [SDVK-009 gate split](../SDVK-009-SOFTWARE-DEPENDENCY-AUTHORITY.md) permits #11/#14
to consume the existing software-qualified probe/lightmap contracts and accepted SDVK-010
(PR #148, verified master `6aadd8458773014e4333cf93cf4b4269ce5733b3`). Earlier
SDVK-010 candidate/integration-pending notes are historical after that acceptance.
SDVK-009-SW is qualified for these consumers; **State C / provisional no-change** and
**SDVK-009-PHYSICAL held** remain. The dormant tiled path, rejected PF-017 candidate,
probe-zero semantics and fallback/portal/lifetime invariants are unchanged.
Physical STOP remains active; this does not prove physical cost, stability, general
bake robustness or viewmodel parity. A new upstream invariant failure reblocks the
affected consumer rather than being waived by this decision.

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

## SDVK-004 accepted page/probe pressure qualification

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

See [SDVK-004 descriptor stress](../SDVK-004-DESCRIPTOR-STRESS.md) and [release acceptance](../SDVK-004-RELEASE-ACCEPTANCE.json). Exact PR-head and post-merge gates passed. The native `sun-probes` route observed one lightmap page, two irradiance maps and two prefilter maps. No new lightmap/probe identity, emergency flush or retention policy is introduced.

## SDVK-010 actor-card probe selection (accepted software scope)

Unlike world lightmap probe-map texels (PF-012), an ordinary actor sprite emits its **authored ordinal** into Vulkan surface state. `HWActorProbeSelection::Resolve` selects an in-range nearest source-level authored probe within the inclusive 512-unit bound, keyed on interpolated actor pose, deterministic first tie, and no hidden temporal interpolation; ambiguous portal-group/through-portal cards preserve a validated sector target. No authored probe is **-1** (authored zero is valid). `VkRenderState::ApplySurfaceUniforms` checks ordinal range before calling the immutable PF-113 pair producer; the runtime zero sentinel still means missing irradiance/pre-filter and both PBR sample functions return zero IBL. Models remain on inherited sector selection. Inherited PBR coverage and both focused actor lanes passed the combined SDVK-010 gate in PR #148, with exact-tree qualification and verified merge; physical cost and general bake robustness remain outside that acceptance. [Detailed contract](../SDVK-010-ACTOR-ENVIRONMENT-CONTRACT.md).


## SDVK-010 linked-portal actor probe transition (accepted software scope)

The bounded `portal-probes` native fixture qualifies the current conservative actor-card policy across an actual bidirectional linked line portal without changing PF-012 or PF-113 plumbing. In a level with multiple displacement groups, the actor selector treats the domain as ambiguous and preserves the validated source-sector authored target; it does not infer probe ownership from global XY proximity. Authored ordinal 0 remains distinct from runtime descriptor 0. The accepted hosted samples use authored 0/runtime 267 in group 1 and authored 1/runtime 281 in group 2 with one stable LightProbe epoch.

Recursive `LineToLine` rendering demonstrated that PF-009 `throughPortalMode` is not a universal portal-recursion flag. The destination-group actor can be processed with `throughPortalMode=0` while PF-010 context depth/producer and displaced viewpoint prove portal presentation. Probe selection therefore remains keyed to source actor/sector identity; applying the view displacement again to the actor would be incorrect. See [SDVK-010 actor environment contract](../SDVK-010-ACTOR-ENVIRONMENT-CONTRACT.md) and [linked-portal qualification](../evidence/SDVK-010-LINKED-PORTAL-QUALIFICATION.json). This does not accept sunlight occlusion or physical performance.


The combined SDVK-010 scene pair preserves the original sector-target/probe producer. The
sunlight pair requires the same nonzero runtime base and adjacent prefilter allocation (span 2);
the portal pair requires distinct live pairs for distinct authored targets. Authored zero remains
valid and absent/unpublished probes remain runtime zero. Bounded software correctness does not
accept broad bake convergence or physical cost. [Integration contract](../SDVK-010-INTEGRATION-ACCEPTANCE.md).

## SDVK-014 candidate: upload input, readback and cross-map blocker

See the [first CPU increment](../SDVK-014-CPU-INCREMENT.md) and
[production path audit](../SDVK-014-PRODUCTION-AUDIT.md). Pending
`LevelMesh::Lightmap.TextureData` is RGB16 upload input; successful CreateLightmap
consumes it explicitly after synchronous copy into the owner's staging buffer.
Save uses separate checked RGBA16 scratch and only live, allocation-consistent
tile bindings. Retired pool slots cannot schedule background bakes or serialize
old bindings using another tile's reused rectangle. Source/CPU fixtures qualify
these bounded paths, not native pixels, all generations or full campaign behavior.

**Cross-map probe reset/rebake/publication is REBLOCKED by #150.** The global
incremental builder remembers count/progress, not the level owner. Same-count
A→B and A→empty→B both produce zero B capture/reset/pass callbacks after A finishes
five passes. The actual entry guard skips Step's empty-reset path. No compensating
refresh or new probe policy is added here. PF-012 authored/runtime identity and
PF-113 typed-zero/pair contracts remain unchanged; their historical bounded
acceptance does not cover this newly demonstrated transition. Physical STOP is
ACTIVE, physical performance HELD, historical physical root cause UNDETERMINED.


## SDVK-014 retained lifecycle hardening candidate

The SDVK-014 branch strengthens existing ownership without redefining probe or
material semantics:

- retained LIGHTMAP bindings/pixel spans/transforms are validated completely before
  current live tiles are mutated; malformed/duplicate entries remain dirty for the
  ordinary bake path;
- lightmapper tile selection is not completion: dirty flags survive until an
  actually rendered tile has been copied into the active atlas and the destination
  has been republished shader-readable;
- newly expanded lightmap and R16_UINT probe-map pages are initialized to typed zero
  fallback contents before publication, so unwritten regions cannot expose undefined
  allocation contents.

These are lifecycle/publication invariants, not new light selection, sampler,
material, portal or probe-selection policy. Cross-map probe builder owner identity
remains separately blocked by #150.


### 3D-floor side ownership

A 3D-floor wall's control sector is part of its semantic lightmap identity.
`BuildFFBlock` publishes the model control sector, `CreateWallSurface` retains
it, `AddSurfaceToTile` keys the tile with it, and `GetVisibleSurfaces` must
match it when gathering side bake geometry. Matching only side/type can
deterministically mix geometry from distinct 3D floors on the same side.


## SDVK-150 candidate: semantic cross-map probe owner generation

SDVK-014 discovered that the process-global incremental probe builder could treat
two different same-count maps as one completed owner. The repair candidate does
not redefine PF-012 selection or PF-113 pair fallback. It adds an orthogonal
semantic owner token:

- each `FLevelLocals` receives a process-unique probe-set revision;
- teardown and runtime authored-probe additions issue a fresh revision;
- the global builder receives that revision on `Step`/`Full`;
- owner change resets partial/terminal progress and the existing probe resources
  before new-owner capture;
- the RenderView path also presents empty authored sets to the builder.

Probe count remains only a defensive consistency fallback, not owner identity.
Authored ordinal 0, runtime descriptor 0, LightProbe resource epoch and semantic
owner revision remain distinct identities.

The opt-in SDVK-150 observer records actual reset/pass-publication callbacks,
map/revision and irradiance/prefilter family counts without changing decisions.
The focused hosted fixture requires five A publications followed by a distinct
same-count B owner reset and five B publications in one process. See
[SDVK-150-PROBE-OWNER-REPAIR.md](../SDVK-150-PROBE-OWNER-REPAIR.md).

This remains a repair candidate until exact-head CI/native qualification and
reviewed merge. Physical performance remains outside this software witness.


### SDVK-150 fixture clock boundary — 16 October 2026

A simulation-tic wait is not evidence of completed render/probe work. Retained
Avrea run 38870637199 switched away from A before any completed probe pass while
B completed all five. The repair uses a fixture-only post-main RenderOverlay
counter and the ordinary network-event/Level.ChangeLevel route after 32 calls;
it does not read or drive the passive observer. Actual five-pass publication,
owner/pair epochs and final draw assertions remain independently mandatory.
Only this two-map correctness driver changes, not production probe policy,
geometry/material inputs or quality. See the SDVK-150 repair document for the
retained failure pins and CPU pacing counterexamples. Native requalification is
still pending until its normal exact-head CI passes.


### SDVK-153 candidate — raw probe map descriptor stability

The live-filter reset in #153 could recycle a raw atlas texel's descriptor into
a different live adjacent pair. The candidate stops retiring LightProbes at
material-cache boundaries while its image/view/probe-sampler owners are live.
Negative/out-of-range/unpublished-half ordinals do not grow the persistent cache;
ordinal 0 remains valid. #150 still owns content reset and five-pass rebuilding.

New exact-source CPU fixtures cover filter/anisotropy/precache, material pressure,
reversed lookup, exhaustion and bounded owner cycles. A prospective normal
Avrea lane observes emitted pair identities and actual material sampler phases.
It is not GPU probe-map texel readback. See the SDVK-153 repair document; #153
and full #14 acceptance remain pending. Physical STOP is unchanged.


## SDVK-156 atlas lifetime follow-on

The #150 semantic probe-set and #153 persistent descriptor fixes are accepted
(PR #152 and PR #155); preceding candidate notes describe older checkpoints.
Atlas tiles now capture a value receipt from the current RectPacker, with separate
owner and allocation incarnations. Draw/UV, retained-load copy and save/readback
paths validate that receipt instead of trusting a recycled item pointer/rectangle.

Selected bake work captures both destination and scratch receipts. Render/copy
validate both, including scratch geometry, before command/resource use; mesh
switch clears pending selections. Scratch Clear/repack cannot refresh old work.
Post-copy completion ordering, probe descriptor/content epochs, sampler policy,
shader ABI and authored ordinals remain unchanged. Runtime atlas receipts are not
saved; structural load admission still does not prove authored bake freshness.
[SDVK-156](../SDVK-156-ATLAS-INCARNATION.md) records bounded CPU proof and normal-CI
gates, not per-texel GPU readback or the full native multi-page/special-surface
campaign. #14 remains unaccepted; physical requirements remain held.


## SDVK-158 retained bake source identity and multi-page lifecycle

Runtime atlas allocation identity (#156) and persisted bake provenance are
different contracts. A current `RectPackerAllocation` proves that a tile still
owns its runtime region; it says nothing about whether retained RGB was baked
from the current authored level.

SDVK-158 therefore versions the retained LIGHTMAP format to v5 and persists the
same authored-map checksum already established by `MapData::GetChecksum`.
Loader admission compares that digest with `FLevelLocals::md5` before applying
retained transforms, dimensions, completion flags or pixels. Failure leaves
current tiles on their ordinary initial-bake path. Existing range, binding,
finite-transform and duplicate-entry checks remain independently mandatory.

The hosted lifecycle witness keeps CPU atlas page count, Vulkan page count, live
and valid tile counts, dirty partitions, completed tile updates and per-page
occupancy separate. Current vertex sampling publication remains tied to
`tile.AtlasLocation.ArrayIndex` and its vertex upload. The SDVK-158 fixture
requires more than one current page across invalidate/reload cycles and a new
lightmap resource epoch after same-map reload, with no stale current-page
receipt.

The v5 source checksum is intentionally a **minimum** freshness authority:
authored map geometry/thing/light inputs, material bindings and BEHAVIOR source
are covered through the map checksum; external texture/material file bytes
changed behind the same binding are not content-addressed by this contract.
Hosted llvmpipe evidence is correctness/lifecycle evidence only, not physical
GPU bake/update performance.


### SDVK-158 forced rebake admission

The first hosted transition packet showed that CPU scheduling state and
lightmapper admission state are distinct. `NeedsInitialBake` makes a tile
eligible for the background scheduler, while `VkLightmapper::SelectTiles`
requires `ReceivedNewLight` before it allocates scratch/render/copy work.
Setting only the former can produce repeated submissions with no publication and
no dirty-state retirement.

A forced whole-lightmap invalidation therefore sets both flags on every live
tile. This does not claim geometry changed; `GeometryUpdate` remains separate.
Completion remains the accepted #151 contract: the current selected receipt is
rendered/copied, the destination is transitioned back to shader-read, and only
then are dirty flags cleared. SDVK-158 diagnostics distinguish the input tile
count from tiles that actually make that dirty→clean transition.

## SDVK-161 corrected planes and retained v5 interpretation

Selected control-sector planes can differ from the earlier reconstruction based
on facing. A retained v5 source checksum and XY transform cannot distinguish
old RGB baked at that earlier wrong height. Corrected/alternative controlled
planes carry RuntimeBakeOnly and skip retained pixels before transforms, flags
or RGB can change; their ordinary fresh bake remains required. Allocation/free
resets that runtime policy. Ordinary v5 source/structural admission, allocation
incarnations and page/copy transitions remain unchanged.

The [special-surface matrix](../SDVK-161-SPECIAL-SURFACE-LIFECYCLE.md) uses zero
authored probes with gl_lightprobe enabled to exercise the existing empty-owner
reset path. It requires current runtime-zero fallback and advancing owner epochs
on reload, without claiming live authored cubemap or per-texel probe readback.
The required #150/#153 live-probe lanes remain authoritative and required.
