# SDVK-161 — special-surface/material lightmap lifecycle qualification

## Disposition and authority

**Implementation candidate; hosted exact-head acceptance pending.**

This is the bounded software qualification child [#161](https://github.com/techrote/ShadeDoomVK/issues/161)
of [SDVK-014 / #14](https://github.com/techrote/ShadeDoomVK/issues/14). It starts at
`master@130d09ac4267d02359c7c2603ceced723ceac746`, after the hosted-runner migration
in PR #160. Accepted renderer prerequisites include #158 / PR #159, merged as
`7559b65f4ff70f2811e360a934a669f48f33ccf5`, tree
`a56121a6542dff58c4d43b4041805c95240ba2e6`.

Retained v5 provenance, allocation-incarnation receipts, multi-page ownership,
page initialization/copy transitions, current descriptors/probes, actual mesh
submissions, dirty/completion accounting and independent-attempt admission remain
binding. The required #150/#153/#158 native lanes remain in normal CI.

**Physical STOP ACTIVE. Physical GPU bake/update cost, representative scaling and
hardware stability HELD / NOT ACCEPTED. Historical physical root cause
UNDETERMINED.** Software Vulkan supplies correctness evidence only. #14 stays
open; this child does not accept the whole campaign or physical criteria.

## Production ownership and bounded outcomes

The authored `special-surface-lifecycle` scene contains two small maps generated
by `tools/renderer_oracle/sdvk161_fixtures.py`. Authored assets are original RGBA
and map data. The exact two-map exception is independently checked against the
serialized map topology, sector ownership, line specials, winding, material
names and camera structure; other corpus rules remain strict.

| Matrix cell | Actual production path and ownership | Qualification boundary |
| --- | --- | --- |
| Lit decal on PBR+height middle wall | `ProcessDecals` stores semantic type/side/control; `AddSidesToDrawLists` resolves the current tile; `ProcessDecal` consumes the receiver's checked allocation and writes its own overlay vertices/material | No allocation owned by the decal. Actual overlay draw, sampler/material and current receiver UVs are witnessed. A second out-of-range decal actor must not become a receiver. |
| Warp2 material | Mesh wall selects the production warp shader and material layers; lightmap UVs remain world-geometry coordinates separate from warped albedo coordinates | Authored warp speed is zero for exact repeatability. Spatial warp classification is covered; animation-clock behavior is not claimed. |
| Reflective floor | Actual reflective-floor alpha/material submission plus a real plane-mirror render context | Receives ordinary plane lightmapping; reflection context and current empty-probe-owner fallback are explicit. No authored environment cubemap is claimed. |
| Translucent middle wall | Actual immediate translucent wall draw and blend/pipeline/material state | Inherited unlightmapped fallback, with `tile=-1` and no current UV claim. Opaque tile state must not leak into the draw. This does not enable translucent LevelMesh receiver construction. |
| Mirror and linked line portals | Actual portal stencil metadata, inherited PF context ancestry, destination sector/group and translated room geometry | Portal wall geometry is trace/stencil data and has no receiving tile. Linked portal uses the existing 156-special semantics and a 1024-unit displacement. |
| `Line_Horizon` | Actual horizon stencil and first submitted floor/ceiling contents strip, using the selected source plane and bound floor/ceiling material | Contents use their special unlightmapped geometry. A stencil alone does not satisfy acceptance. Both selected planes/materials must be witnessed. |
| Two solid 3D floors in the main view | Actual LevelMesh sides and floor/ceiling faces; receiving sector 6, control sectors 4/5, distinct control materials and source planes | Native target is ordinary opaque solid floors. Current owner/control/plane, per-subsector triangle association, UVs and allocation receipts are required. Recursive portal 3D-flat submission is outside this native claim. |
| Upper/middle/lower wall semantics at differing sector heights | Ordinary target boundary upper/lower bands plus both controlled middle-side receivers on side 34 | Outside sector 1 remains 0–160; target sector 6 is 16–144. Actual upper PBR and lower height-only bands use control -1, while slab sides retain controls 4/5. |
| Inverted/alternative controlled planes | Exact production `CreateFlatSurface`, binding/publication and bake-target CPU replay | Selected source plane and source axis are qualified by CPU regression; the native corpus does not claim general inverted or sloped 3D-floor coverage. |
| Multiple unequal planes sharing one controlled flat binding | `AddSurfaceToTile` rejects before bounds/use-count mutation | Explicit unsupported lightmapped case, including ambiguous `FF_BOTHPLANES`; no plausible shared tile is admitted. No-lightmap rendering is unchanged. |
| Non-sky stack flat portal overlay | Existing immediate flat receiver/table path retained | Source/CPU preservation control only. This child does not claim a new native sector-stack-portal matrix. |

Map A deliberately distinguishes PBR+height (`S161PH`, height binding 8),
heightless PBR (`S161PN`), height-only default (`S161HO`, binding 4), ordinary
albedo (`S161NO`), and Warp2 (`S161WP`, shader selection overrides the authored
PBR group while preserving its separate height semantic). Floor versus ceiling,
upper/middle/lower side types, front/back destination ownership, portal group,
subsector ordinal and control-sector ordinal are separate evidence fields.

Map B has two opaque slabs at 32–48 and 96–112 world units. Both use the same
target-sector boundary sides but distinct control sectors and side materials.
The lower-facing surfaces use control bottoms at 32/96; upper-facing surfaces
use control tops at 48/112. A control model is not the owning destination sector,
and emitted facing is not a substitute for the selected model plane.
The target floor/ceiling at 16/144 additionally expose the ordinary lower band
0–16 and upper band 144–160. `S161HO` belongs to the front lower slot and `S161PN`
to the front upper slot; back-face texture slots remain empty. Submitted vertex
height extrema, type, material, side and owner prove these semantic bands.

The fixed map cameras are A `[-192,0,64]`, yaw 0, and B
`[1060,-176,64]`, yaw 90. B places the slabs directly in the main view and the
reverse linked portal in the same frustum. Its portal must submit the actual
immediate `SDVW` north wall, side 1/sector 0/group 1, using the translated view
`[36,-176,64]`. Both camera recipes and actual per-frame positions/angles are
pinned. Recursive portal views use the inherited immediate BSP renderer;
requiring a LevelMesh producer inside that context would be an unreachable
method claim. No portal renderer policy is changed to satisfy the fixture.

## Production repairs

1. **Per-subsector triangle association.** `CreateFlatSurface` previously wrote
   the whole section allocation's `SurfaceIndexes` after each subsector. The
   last subsector could own earlier triangles. Keep the existing per-triangle
   fan writes and remove the whole-allocation overwrite.
2. **Selected 3D-floor plane.** Geometry now consumes the already selected and
   oriented `HWFlat::plane`, rather than reconstructing it from the control
   sector and emitted facing. `LightmapPlane` publishes the actual source axis
   into the matching immediate flat tile table. Ordinary material flats do not
   inherit an unrelated sector portal destination.
3. **Controlled bake targets.** Equal facing and control ordinal cannot admit a
   neighboring alternative source plane as a bake receiver. Exact plane equality
   applies only to controlled tiles. Ordinary same-height-group neighbors retain
   their existing seam/padding coverage, including slightly differing planes.
4. **Ambiguous controlled binding.** Unequal planes under one flat binding fail
   explicitly, before changing the old tile's bounds or use count. This avoids
   creating a structurally current tile with the wrong geometric meaning.
5. **Corrected-plane retained RGB.** Old v5 retained RGB may have the same source
   digest and XY transform but have been baked at the earlier wrong plane.
   `RuntimeBakeOnly` quarantines affected corrected controlled planes before
   retained transforms, flags or pixels can mutate them. They remain dirty for
   a fresh bake. Ordinary v5 provenance/structural admission remains unchanged;
   allocation/free resets the runtime policy. The format is not globally waived.
6. **Current decal receiver.** Remove the durable numeric tile snapshot from
   decal creation metadata. A read-only semantic `(type, side, control)` lookup
   follows the current side's persistent live surface chain at draw construction,
   validates the tile's semantic binding and current receipt, then retains the
   centralized check at UV consumption. The transient `TileBindings` construction
   deduplication table is cleared every frame and is not a receiver registry.
7. **Wall portal exclusion.** Non-sky mirror/line portal walls previously could
   allocate `ST_NONE` tiles that have neither side-table nor bake-target consumers.
   Keep their geometry, material/trace metadata and portal indices, while
   excluding wall portal draw types from receiving allocations. Non-sky flat
   portal receiver behavior is preserved.
8. **Material descriptor reset.** Filter/precache resets retire material
   descriptors, so both live mesh raster Uniforms and tracer Surface material
   indices must be scheduled for the normal uploader. Height-layer indices are
   refreshed with the raster material. The logical device mesh is authoritative;
   the Vulkan mirror can still name a prior map until `BeginFrame`. Allocator
   free/capacity holes can retain retired pointers and are excluded. Sampler
   replacement precedes upload and subsequent draw/lightmapper use. Atlas,
   geometry and persistent probe descriptor owners are not rebuilt by this reset.
9. **Immediate receiver semantics and observation.** Wall type/control metadata
   is retained for both mesh construction and immediate portal/mirror producers.
   Actual wall and decal writers supply copied XYZ/UV/page values after writing,
   including split vertices. The shared frame store synchronizes worker capture
   and main-thread consumption, with one 4096-vertex limit and next-frame clear.
   A thread-local store would miss worker-produced portal decals. Observation
   remains opt-in and changes no drawing or material eligibility policy.

Supported control-plane reconstruction is additionally replayed through changing
heights and reusable CPU storage. This exercises real construction/publication
and retirement functions, not a second implementation of the binding rules.
The inherited `OnMidTex3DHeightChanged()` no-op remains explicitly unclaimed;
this child does not invent ownership for that callback or enable arbitrary
live 3D-midtexture movement.

## Fixed lifecycle and bounded collection

The opt-in `-sdvk161surfacedriver` is state-only, exclusive with other input
drivers, and requires exactly 32 warmup plus 96 retained main views. It queues
ordinary console inputs at fixed newly presented main-view ordinals and reads
no result to decide whether to advance. The first invalidation is queued after
warmup view 32 and before retained frame 1. Retained frames 1–8 must show actual
admitted updates, completed tiles and clean convergence following this explicit
input. They do not claim observation of the initial construction bake, which may
already have completed during warmup. The 96 retained frames and all twelve
checkpoint positions remain fixed.

| After main views | Input | Intended following state |
| ---: | --- | --- |
| 32 | `invalidatelightmap` | Explicit initial retained-window invalidation after warmup |
| 40 | `invalidatelightmap` | Map A first forced rebake |
| 48 | `gl_texture_filter 4` | Map A linear sampler/descriptor reconstruction |
| 56 | `map SDV161A` | Same-map A level/mesh/atlas/probe reconstruction |
| 64 | `gl_texture_filter 0` | Map A nearest sampler reconstruction |
| 72 | `invalidatelightmap` | Map A second forced rebake |
| 80 | `map SDV161B` | New map and portal/control-sector population |
| 88 | `invalidatelightmap` | Map B first forced rebake |
| 96 | `gl_texture_filter 4` | Map B linear sampler reconstruction |
| 104 | `map SDV161B` | Same-map B owner reconstruction |
| 112 | `gl_texture_filter 0` | Map B nearest sampler reconstruction |
| 120 | `invalidatelightmap` | Map B second forced rebake |

`lm_max_updates=128` and `lm_background_updates=32` are prospective fixture
settings, with `lm_dynlights=false`. No acceptance threshold is adapted to an
observed failure. `gl_lightprobe=true` with exactly zero authored probes executes
the accepted empty-owner reset path; actual runtime probe selection must remain
the explicit zero fallback. Required #150/#153 scenes separately qualify live
authored probe identities and sampler resets.

Frame/context/resource evidence covers all 96 retained frames. Detailed actual
draw witnesses and completed-view PNGs occur at retained frames 8,16,…,96.
Each horizon-contents producer records its first actual submitted strip; remaining
strip rendering continues unchanged. This bounds observation of its 256 strips
and cap without replacing the path with a mock. The fixture policy is explicit
in its manifest and source tests.

Inherited limits remain 65,536 records, 16 MiB total and 16 KiB per record. The
new live tile census additionally rejects more than 64 live tiles. The observer
fails on overflow and never silently truncates ownership evidence. Immediate
writer snapshots have a separate 4096-vertex bound shared across all producer
threads in the selected frame.

## What the witness proves

Actual LevelMesh `drawIndexed` ranges are joined through the current index,
triangle-to-surface, geometry, uniform, light-uniform and material arrays. The
observer records the final bound pipeline, actual texture index and selected
existing descriptor/material layers. Immediate metadata is scoped to the
producing draw and cleared/restored through common-code RAII; it does not create
or resolve descriptors just to produce evidence.

The same-frame census includes current tile binding, page, allocation owner,
incarnation/slot, validity and initial/geometry/light dirty flags. Every receiving
mesh vertex must have the current page and finite `lu/lv` matching the current
tile's production `ToUV` result. The fixed float tolerance is 2^-21 normalized UV,
far below one atlas texel. This is a numerical writer-rounding bound, not an RGB
tolerance. Immediate receiving walls and decals revalidate copies of their actual
producer-written CPU positions, UVs and per-vertex pages at draw emission; the
actual submitted subrange and captured allocation receipt must match the current
tile. No raw vertex pointer survives the producer scope. Every decal
must share its current tile, page and allocation receipt with an actual PH wall
submission in the exact same render context and with the authored receiving
owner. The main view must include both its LevelMesh PH receiver and its decal.
Portal decals may join actual immediate PH wall submissions in their portal
context; a matching main-view tile alone cannot prove that relationship. Every
receiving producer still requires actual current UV evidence.

These are submitted CPU binding/range and actual bound-state witnesses. They do
not claim GPU vertex-buffer byte readback or per-texel probe-map readback. Mesh
data does not store an authored probe ordinal; that field explicitly says so.
Raw immediate probe selector 0 can be valid with an empty authored population,
but current runtime selection and owner epoch still must prove zero fallback.
Sector portal groups and mesh connected-component groups are distinct namespaces.
The inherited context `portal_group` identifies `Viewpoint.sector`, which can
remain the source sector after a linked view is translated. Additive
`line_portal_selection` metadata records the actual selected source/destination
line and group identities used by portal setup. The reverse receiver joins its
owner group to that selected destination group; the legacy context field and
semantic key keep their accepted meaning.

## Independent attempt admission and controls

The normal hosted software-Vulkan job runs two fresh serial attempts. Each must
independently pass its prepared-input hashes, exact build/commit identity,
complete raw interval, ordered lifecycle, current ownership, required draw cells,
dirty-to-complete convergence and all twelve checkpoint PNGs before another
attempt's result can participate in comparison. No partial packet is combined
with another attempt. All twelve decoded checkpoint RGB images and the final
image compare exactly; there is no fuzzy material-specific pixel threshold.

Each attempt also requires exact equality between its completed equivalent
states: A nearest frames 8/16/40/48, A linear 24/32, B nearest 56/64/88/96 and B
linear 72/80. These prove image convergence after invalidation and reconstruction
under the same sampler. Different sampler policies are not compared for equality.
The ordinary screenshot writer runs with its quiet option enabled and typed
`con_notifylines=0`; the driver checks both immediately before capture. Zero
notification lines also suppress ordinary invalidation messages and clear prior
notification entries before they can enter later checkpoint frames. All twelve PNGs must be registered
in the original hashed run artifact manifest; merely discovering files on disk
cannot authenticate a retained attempt.

AO, bounce, sunlight and dynamic lighting are disabled in this compact material
ownership fixture. The images prove material/path compatibility, exact
repeatability and convergence; they are not independently expected nonzero bake
pixels or new AO/bounce/sun qualification. Those lighting policies retain their
existing gates and any remaining SDVK-014 campaign obligations.

Each admitted raw attempt is also copied into named deterministic negative
controls. Mutations target wrong production participation/classification,
material shader, allocation receipt, control owner, selected plane, portal
identity, probe epoch, lifecycle map, missing completion, same-page stale UV and
actual horizon plane/material. Each must fail for its intended invariant.
The twenty-one captured controls also corrupt an ordinary upper slot, lower owner
and upper height. Coherent wrong-material controls borrow complete current
same-frame material and texture-index payloads for the A ordinary wall, decal,
reflective floor and horizon contents; a correct neighboring row cannot excuse
the bad row. Dispatch starts from actual submitted classes and authored side
anchors, then asserts sector, control, portal group, type and side identity;
invalid ownership cannot skip a known cell. Ordinary control-sector geometry
outside the controlled receiver classes is kept distinct. All retain enough
valid structure to challenge plausible ownership and material substitutions.
The map-camera and reverse-portal method controls reject a prior-map viewpoint
or an invented LevelMesh path even when current material and pixels could agree.
`negative-controls.json` pins the source raw hash, changed record/path, before/
after values and mutant hash; the admitted raw file remains unchanged. CPU tests
also reject swapped phases, mixed attempts, missing/borrowed checkpoint images,
wrong topology, stale retained provenance and production root-cause mutants.

## Validation and acceptance record

Normal validation is `tools/check.py` (PF/source/CPU, renderer oracle and authored
corpus), the ordinary platform CI matrix, the existing hosted software-Vulkan
job with this added correctness gate, and the renderer source-evidence workflow.
There is no extra runner or duplicated timing execution. Local work uses CPU
fixtures only; no local renderer/Vulkan device is executed.

The CI job retains `renderer-sdvk161` with both attempts, raw state, all PNGs,
negative-control reports, preparation receipts and qualification output. A failed
attempt remains failed; its evidence is inspected and a source/fixture/oracle fix
goes through normal CI on the next commit. Exact reviewed head and source/native
workflow identities will be recorded in the PR and this acceptance record before
merge. Current native disposition remains **PENDING**, not accepted by comments
or CPU tests alone.

The first hosted head `631e3abcde6fb7c9d6569ffe97c19951b1403fd1` failed at
incomplete retained frame 24 after the filter reset, before a dependent second
attempt. [The committed failure record](evidence/SDVK-161-FIRST-NATIVE-FAILURE.json)
pins the exact source/native tree, workflows, original artifact and captures.
The passive descriptor lookup exposed a retired cached material index. Retained
captures also exposed the transient decal lookup, missing wall UV proof,
notification pixels and pre-retention completion. Extra High source review of
the repairs caught worker/main snapshot ownership and the unreachable portal
mesh requirement. All corrections require a new normal-CI head; the failed
packet remains failed and unchanged.
