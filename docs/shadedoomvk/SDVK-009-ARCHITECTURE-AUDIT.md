# SDVK-009 — many-light execution map, dormant-path audit and candidate selection

Status: **non-physical-GPU architecture checkpoint; tasks 1–3 complete, later diagnostics/workloads/measurement/prototyping deliberately not started in this checkpoint**.

Authority at this checkpoint: `master@cafbad5c45977327ba507bcf5f2dea9c3661f3d3`. The current runtime renderer source is the SDVK-006 merged source at `39c07d12f59b21c86be86b44f3a0905ffecfd184`; the later SDVK-004 acceptance reconciliation changes documentation/evidence state rather than the lighting runtime paths audited here.

This record does not claim a GPU speedup, no-regression result, hardware-tier suitability or final SDVK-009 acceptance.

## 1. Production many-light execution and scaling map

### Authored light ownership and spatial membership

Dynamic-light instances enter the level-wide intrusive list through `GetLight(FLevelLocals*)` in `src/playsim/a_dynlight.cpp`; actor-authored/state/GLDEFS lights are attached by `AttachLight`, `AActor::SetDynamicLights` and the light-definition application path.

The spatial candidate substrate is built by:

- `FDynamicLight::UpdateLocation()`;
- `FDynamicLight::LinkLight()`;
- `FDynamicLight::CollectWithinRadius()`;
- `AddLightNode()`.

`CollectWithinRadius()` walks touched sections/segments inside the light radius, traverses linked line portals and non-blocking sector portals, and inserts one node per light/section or light/side into `FSection::lighthead` and `side_t::lighthead`. Cross-group positions are obtained with `FDynamicLight::PosRelative(portalGroup)`.

**Scaling:** light movement/radius changes scale with the spatial region touched by that authored light, including reached portal-connected sections/sides. The persistent `Level->lights` list scales with total authored light count; per-section/per-side lists scale with candidate membership rather than total lights.

### Shadow selection

For a visible main view, `CollectLights()` in `src/rendering/hwrenderer/hw_entrypoint.cpp` scans every `Level->lights` entry, keeps active `shadowmapped` candidates, and passes them through `HWSelectShadowCandidates()`.

`src/common/rendering/hwrenderer/data/hw_shadowselection.h` preserves existing order when the candidate count is at or below the fixed 1D shadow-map capacity of 1,024. Only overflow invokes deterministic stable sorting by distance plus semantic tie-break fields, then truncates to 1,024.

**Scaling:** O(total authored lights) every shadow-collecting main view, plus O(S log S) only when eligible shadow candidates exceed 1,024. This capacity/selection contract is accepted PF behavior and is not a SDVK-009 quality-culling opportunity.

### Immediate world walls, flats, decals and render-hack planes

The production non-LevelMesh scene path is the default because `gl_levelmesh` defaults false.

World-surface collection is local-list driven:

- walls: `HWWall::SetupLights()` in `scene/hw_walls.cpp`;
- flats: `HWFlat::SetupLights()` in `scene/hw_flats.cpp`;
- decals: `HWDecalCreateInfo::SetupLights()`;
- auxiliary planes: `HWDrawInfo::SetupLightsForOtherPlane()`.

These paths iterate the relevant prelinked `side_t::lighthead` or `FSection::lighthead`, preserve active/`DontLightMap` policy, perform surface/plane/polygon overlap checks, and call `GetLight()` / `AddLightToList()`. `GetLight()` uses `PosRelative(group)`, so portal-relative position is packed for the actual render group.

The output is one `FDynLightData` with three ordered classes:

1. normal/modulated;
2. subtractive;
3. additive.

**Scaling:** CPU collection scales with the sum of candidate-list nodes visited for visible surfaces. Packing scales with the sum of selected light memberships, not unique authored lights. A light touching many visible surfaces is packed repeatedly.

### Sprites, models and particles

`HWDrawInfo::GetDynSpriteLightList()` in `scene/hw_spritelight.cpp` owns the accepted PF-016 actor/model path.

Both the baseline BSP source and the qualified one-section fast source feed the same filter pipeline:

1. `FDynamicLight::ShouldLightActor()`;
2. `PosRelative(group)`;
3. radius + actor render-radius overlap;
4. first-encounter duplicate suppression when required;
5. PF-015 visibility/trace checks;
6. `AddLightToList(..., forceAttenuate=true, doTrace=...)`.

The baseline uses `BSPWalkCircle()`; after exact qualification an actor may use only its current `section->lighthead`. Models consume the same selected list through `FHWModelRenderer`. Particles use the same machinery when sprite lighting is enabled.

**Scaling:** baseline actor queries scale with touched BSP sections plus candidate light nodes plus required visibility traces. Qualified local queries scale with one section list. Across a dense frame the cost is the sum across illuminated sprites/models/particles; PF-016 already rejected weaker geometric assumptions and preserves exact fallback.

### Packing and Vulkan upload

`AddLightToList()` in `hw_dynlightdata.cpp` packs the accepted 80-byte `FDynLightInfo` record, including:

- portal-relative position;
- normal/subtractive/additive class;
- attenuation flag;
- spot parameters;
- shadow-map index and trace/shadow flags;
- GLDEFS intensity;
- actor-alpha multiplier where applicable;
- linearity, strength and soft-shadow radius.

`VkRenderState::UploadLights()` writes one four-int range record plus all selected `FDynLightInfo` records into the host-mapped `LightBufferSSO`. The buffer has `MAX_LIGHT_DATA == 80000` range slots and 80,000 record slots. `BeginFrame()` resets the range/data cursors.

When either cursor/capacity check fails, `UploadLights()` returns `-1`; the draw then has no valid dynamic-light range. This is an inherited bounded fallback/overflow state, not permission for a new architecture to silently drop otherwise eligible lights.

**Scaling:** mapped upload bytes are approximately 80 bytes per selected logical record plus 16 bytes per consumer range. PF-017 measured the dense PF-016 workload at 840 consumers / 49,473 logical records / 3,971,280 mapped bytes per frame. Repeated membership therefore dominates bytes even when the unique packed-light population is small.

### Shader consumption

Immediate scene shaders use `getLightRange()` and direct `getLights()[i]` access from `wadsrc/static/shaders/scene/binding_rsbuffers.glsl`.

Depending on shader mode, normal/subtractive/additive ranges are iterated in vertex or fragment lighting code (`vert_main.glsl`, `lightmodel_normal.glsl`, `lightmodel_specular.glsl`, `lightmodel_pbr.glsl`). Shadow/spot/attenuation work happens inside the accepted light functions.

**Scaling:** GPU light-loop work is selected-light count multiplied by the relevant shaded vertex/fragment population. The current CPU spatial lists reduce the candidate set before upload, but there is no higher-order GPU light-list culling in the default immediate scene path.

### LevelMesh split

With `gl_levelmesh=true`, BSP traversal records seen sectors/sides rather than building ordinary immediate wall/flat objects. The current LevelMesh scene fragment path deliberately forces `uLightIndex = -1` in `frag_main.glsl`; the formerly intended `DispatchLightTiles()` block remains commented out in `HWDrawInfo`.

LevelMesh still owns separate light structures for lightmapping/ray queries. Those are not the production immediate scene-light consumer and must not be treated as an already-correct scalable scene-light architecture.

## 2. Dormant/inherited scalable-light audit

| Component | Classification | Current truth / blocker |
| --- | --- | --- |
| `VkLightTilePolicy::Enabled` seam | production-active policy guarding a dormant facility | PF-019 intentionally sets it false. One valid `SceneLightTiles` block remains only to preserve LevelMesh descriptor binding 4 ABI. |
| Z-min/max pyramid | **dormant but reusable only in part** | Six RG32F depth-range images, shaders, descriptors and pipelines remain source-complete behind the PF-019 gate. No accepted scene consumer uses them. The depth-reduction primitive may be useful to a later forward+/cluster prototype, but re-enabling it alone provides no lighting behavior and adds render work/resources. |
| `comp_lighttiles.glsl` | **dormant and incorrect against current SDVK-009 equivalence** | Each 64x64 tile physically stores only 16 copied `DynLightInfo` records. Each class loop breaks at 16 with no overflow list/fallback, so dense overlap silently drops eligible lights. |
| `DoomLevelMesh::UploadDynLights()` -> `Mesh.DynLights` | **dormant/incomplete scene-light producer** | Under default `lm_dynlights=false`, traced lights are diverted to the lightmapper `Mesh.Lights` path and are absent from the tile input. Non-traced records are packed using a hard-coded portal group 0 with an existing `// What value should this have?` marker. Thus the dormant tile source is neither shadow/trace complete nor portal equivalent. |
| LevelMesh scene binding 4 / `LightTileBlock` | **dormant ABI placeholder** | The descriptor remains valid, but `frag_main.glsl` forces `uLightIndex=-1`; scene shaders do not consume the tile output. |
| `Mesh.LightIndexes`, `AllocLightList()`, `CreateLightList()` | **production-active for lightmapping; reusable concept/allocator only** | Lists are variable-length and are updated from side/section light-link changes, but membership is restricted to `light->Trace() || lm_dynlights`, not the immediate scene-light contract. The buffer is bound to lightmapper/viewer shaders, not the scene shader layout. |
| `DoomLevelMesh::GetLightIndex()` portal variants | **unsafe for general scene reuse** | Each `FDynamicLight` caches only four LevelMesh portal-group entries. On exhaustion the function returns index 0 rather than providing an unbounded/equivalent representation. This is incompatible with SDVK-009's general portal-equivalence requirement. |
| `LevelMeshLight` | **active lightmapper format; stale/incomplete for immediate scene lighting** | It does not encode the accepted `FDynLightInfo` class/flag contract: no normal/subtractive/additive class ranges, attenuated flag, shader shadow index/flags, linearity, strength, trace/sun flags or equivalent immediate packing semantics. Direct substitution would change lighting. |
| `LightIndexBuffer` | **active lightmapper resource; reusable implementation pattern only** | It proves that growable per-surface integer lists and incremental upload ranges already exist, but it is not bound as the immediate scene-light reference buffer. |
| Z-min/max/tile descriptor/pipeline/shader allocations | **superseded while consumer dormant** | PF-019 correctly avoids their allocation/compile/update cost while retaining source and the re-enable seam. |

### Why the inherited tiled path is dormant

Current source makes the reason explicit rather than mysterious:

- the old LevelMesh depth-only/tile-dispatch block is commented with “replace this with classic light lists”;
- the live LevelMesh fragment shader disables tile lookup;
- PF-019 then gated the now-unused producer resources after proving there was no active consumer.

It is therefore not a temporarily-disabled complete forward+ implementation. It is an abandoned/incomplete experiment with a retained producer seam.

### Direct-reactivation blockers

A responsible revival would have to solve all of the following before evaluation:

1. replace the fixed 16-record tile with deterministic variable-length or explicit non-dropping overflow behavior;
2. include traced/shadow-relevant lights rather than the current split producer;
3. pack positions for the correct portal/render group rather than group 0;
4. reconcile normal/subtractive/additive ordering and all `FDynLightInfo` flags;
5. define exact behavior for portals and recursive/non-main contexts;
6. provide resource/lifetime ownership under current PF-002/PF-003 contracts;
7. bind/consume the result in scene shaders without silently changing unsupported paths;
8. prove the added depth/tile passes earn their cost on physical hardware.

That is architectural reconstruction, not a switch flip.

## 3. Candidate selection after the source audit

### Rejected before prototyping: blind dormant-tile revival

Rejected. The 16-light truncation alone violates issue invariants. The traced-light and portal-group defects independently prevent equivalence.

### Rejected before prototyping: direct LevelMesh surface-list reuse

Rejected as a direct scene-light implementation. The dynamic list allocator itself is useful, but its membership policy, four-group light identity cache, light record format and descriptor consumers are lightmapper-specific and do not match the immediate PF lighting contract.

### Not selected as the first prototype: per-record upload deduplication / hash indirection

PF-017 already measured this design family. Its corrected frame-local physical-record map reduced mapped writes by 94.24% but regressed dense-scene setup by 133.25% and whole-frame CPU by 32.91%. The later source-owned temporal-reuse variant also failed the final physical campaign and was restored. SDVK-009 must not repackage either rejected idea as new architecture evidence.

### Leading smallest credible alternative: bounded forward+ prototype over the accepted immediate-light representation

The smallest remaining architecture that changes the scaling mechanism rather than merely reshuffling upload bytes is a **new variable-length forward+ light-list prototype for the immediate world-surface path**, with the unchanged PF architecture retained as the control and fallback.

The prototype should deliberately reuse only safe concepts from the dormant work:

- retain the accepted `FDynLightInfo` packing/semantics rather than `LevelMeshLight`;
- reuse the concept of screen tiles and, only if measurement justifies it, the existing Z-min/max depth-reduction primitive;
- use variable-length/indexed tile lists with explicit capacity accounting and no arbitrary 16-light truncation;
- build the candidate without PF-017's per-reference full-record hashing;
- keep sprite/model/particle lighting on the accepted PF-016 path initially;
- fail back to the current immediate per-draw path for portal/non-main/unsupported contexts until exact portal-group equivalence is implemented and proven;
- preserve current shadow selection and `FDynLightInfo.shadowIndex` semantics;
- make any new list/index resources frame/context-owned and bounded under PF lifetime rules.

This candidate is intentionally narrower than “replace the renderer with clustered lighting”. It can answer the key hardware question—whether reducing dense world-surface shader iteration earns the additional culling/list machinery—without first rewriting actor lighting, lightmaps, shadow selection or quality policy.

A true clustered depth-slice hierarchy is not selected for the first prototype because it adds another spatial dimension, more resource/layout policy and more correctness surface before a 2D/depth-bounded forward+ mechanism has demonstrated value.

### First-class control: no change

The current PF architecture remains a first-class candidate. If the forward+ prototype cannot prove exact state/image equivalence off-GPU, or if its CPU/setup/resource cost is already unattractive, it should be rejected before physical hardware and SDVK-009 should proceed to a provisional no-change GPU confirmation campaign.

## Checkpoint boundary

Tasks completed here:

1. production light-path/scaling map;
2. dormant Z-min/max/tile/list infrastructure audit;
3. selection of the smallest credible architecture to prototype.

Deliberately not started in this checkpoint:

- new diagnostics/counters;
- new dense-light fixtures;
- CPU/software-Vulkan baseline measurement;
- forward+ implementation;
- equivalence qualification;
- physical-GPU protocol/final decision.

Issue #9 remains open.
