# SDVK-009 — non-physical-GPU many-light qualification

Date: 2026-10-09. Owner: SDVK-009 / #9. Status: **non-physical-GPU qualification candidate; physical-GPU confirmation remains required before final #9 acceptance**.

## Scope and authority

This record starts from live `master@cafbad5c45977327ba507bcf5f2dea9c3661f3d3`, which already contains accepted SDVK-004 and merged SDVK-006 source. It deliberately stops before physical-GPU performance conclusions. CPU contracts and software Vulkan may establish correctness, repeatability, workload structure and descriptive timing; they do not establish GPU speedup, final architecture superiority, hardware-tier suitability or final SDVK-009 acceptance.

The accepted PF/SDVK constraints remain authoritative: PF-016 owns actor-query equivalence, PF-017 is an accepted measured no-go with complete candidate restoration, PF-019 keeps the dormant tiled producer off, SDVK-002 owns the observer/state/image policy, SDVK-003 owns donor conflicts, SDVK-004 owns descriptor/resource lifetime pressure and SDVK-006 owns visual time. SDVK-016, not this issue, owns quality-tier light culling.

## Current production execution and scaling map

The production path is consumer-specific rather than one global light list.

| Stage | Current source/symbol | Semantic work | Primary scaling term |
| --- | --- | --- | --- |
| Authored light ownership | `FLevelLocals::lights`; SDVK observer census | all authored dynamic lights across live levels | authored lights / levels |
| Sprite/model candidates | `HWDrawInfo::GetDynSpriteLightList` in `hw_spritelight.cpp` | PF-016 section-local fast path or BSP fallback, first-encounter de-duplication | candidate nodes per actor/object |
| Actor filtering | `ShouldLightActor`, PF-015 visibility and `AddLightToList` | radius, portal-relative position, model/actor policy, optional traces | candidates, portal groups, traces |
| Wall candidates | `HWWall::SetupLights` in `hw_walls.cpp` | side/section light nodes, portal transform, plane/radius/polygon tests | light nodes per wall draw |
| Flat candidates | `HWFlat::SetupLights` in `hw_flats.cpp` | section nodes, portal transform, plane/radius tests | light nodes per flat draw |
| Decal/hack/HUD candidates | `hw_decal.cpp`, `hw_renderhacks.cpp`, `hw_weapon.cpp` | consumer-specific inherited tests | candidate nodes per draw |
| Selected CPU representation | `FDynLightData` / `AddLightToList` in `hw_dynlightdata.cpp` | class-partitioned normal/subtractive/additive `FDynLightInfo` records; point/spot/shadow fields | selected records per consumer |
| Immediate Vulkan upload | `VkRenderState::UploadLights` in `vk_renderstate.cpp` | one 16-byte `ivec4` range plus 80-byte records per successful upload | draws with lights + selected records |
| GPU buffer capacity | `VkRSBuffers::Lightbuffer` | 80,000 range entries and 80,000 records; 1.28 MB + 6.40 MB logical capacity | uploaded ranges/records per frame |
| Shader iteration | `binding_rsbuffers.glsl`, `lightmodel_normal.glsl`, `lightmodel_specular.glsl`, `lightmodel_pbr.glsl`, `vert_main.glsl` | class ranges are iterated when `uLightIndex >= 0` | selected records × affected shader invocations |
| Shadow interaction | existing shadow candidate/row selection before packed records | shadow eligibility/row identity is retained in selected light state | eligible shadow lights, 1,024-row cap |
| LevelMesh | `DoomLevelMesh` + `VkLevelMeshUploader` | separate lightmapper/ray light indexes and dormant tile data; main scene forces tile index off | surfaces/lightmapper lists, not immediate scene ABI |

This structure explains why authored count alone is not a useful many-light metric. Cost-bearing quantities are candidates visited, selected records per consumer, consumer/draw count, portal-relative variants, visibility traces, uploaded ranges/records and shader iterations.

### Existing measured baseline retained

PF-016 already proves the accepted actor-query fast path is output/state equivalent under moving portals/occluders, sprites/models and dense actor populations. Its representative physical workload retained 48,787 selected lights per frame and improved setup time. PF-017 then measured a temporal packed-light reuse/indirection design on the same dense workload and rejected it: all five physical pairs regressed setup (+10.79% pooled median) and whole-frame CPU (+2.42%) despite large byte reuse; the candidate was fully restored. PF-019 independently removed 5,862,384 bytes of dormant Z-min/max/tile payload at 1904x1001 because its consumer was disabled.

Those records are baseline authority, not new SDVK-009 physical evidence.

## Dormant/inherited scalable-light audit

| Component | Classification | Finding / blocker |
| --- | --- | --- |
| `VkLightTilePolicy` | production-active policy seam, default disabled | Correctly prevents producer/resource work while consumer is dormant. Safe seam, not an architecture. |
| six-level Z-min/max images/passes | dormant but mechanically coherent; semantically unqualified | Preserved shader/pipeline code can build a depth pyramid, but viewport/scissor/portal-view assumptions are not qualified for current PF-010 render contexts. |
| `comp_lighttiles.glsl` | **dormant and stale/incorrect for SDVK-009 equivalence** | `LightTileBlock` copies at most 16 complete `DynLightInfo` records per 64x64 tile and stops at 16. Dense eligible overlap therefore silently truncates lights. |
| `frag_main.glsl` tile consumer | dormant/superseded | LevelMesh main scene explicitly assigns `uLightIndex = -1`; tile lookup remains commented out. |
| `DoomLevelMesh::UploadDynLights` | dormant, incomplete | Tile-source packing contains `int portalGroup = 0; // What value should this have?`; this cannot establish current portal-relative semantics. |
| `Mesh.DynLights` / Vulkan binding 4 | dormant data producer/ABI placeholder | PF-019 retains one valid block only to preserve descriptor ABI. It is not production scene-light evidence. |
| `Mesh.LightIndexes` / `CreateLightList` | production-active **for lightmapping/ray-related consumers**, reusable only in part | Eligibility is `light->Trace() || lm_dynlights`, not the immediate wall/flat/sprite semantic filter. It cannot be substituted for scene selected-light lists. |
| `FDynamicLight::levelmesh[4]` / `DoomLevelMesh::GetLightIndex` | active LevelMesh cache, unsafe as general scene identity | Only four portal-group copies are representable; exhausting them returns index `0`, which can alias the first valid light. This is a blocker to using LevelMesh indexes as a scene-light semantic substrate, not permission to drop additional lights. |
| tile descriptors/shaders/pipelines | dormant but preserved | PF-019 gates creation/rewrites/compilation. They may be useful implementation fragments after semantics are redesigned, not safe code to re-enable. |

### Why blind tiled revival is rejected

A correct forward+/clustered/tiled system first needs the same *semantic eligibility* as the current per-consumer path. Screen/depth intersection alone cannot reproduce side/polygon tests, actor policy, portal-relative transforms, PF-015 visibility, trace policy, class ordering and shadow metadata. The inherited implementation lacks that semantic substrate and additionally has a hard 16-record tile truncation. It is rejected before hardware benchmarking because it fails correctness by construction.

## SDVK-009 diagnostics and correctness repair

The accepted SDVK-002 observer is extended only in state mode:

- frame light census: authored, active, spot, subtractive and additive counts;
- actor-query aggregate: queries, candidates, selected, filtered, duplicate rejection and traces;
- immediate Vulkan light-upload state: attempts/success/failures, index/data capacity failures, range/record usage and capacity bytes, class record counts, uploaded bytes, peak records per upload and bounded list-size histogram;
- failed immediate-light upload is a validation failure rather than an invisible accepted fallback.

Timing mode does not perform these per-upload counters. Existing render CPU timing and GPU timestamp collection remain the timing path.

The audit also found and repairs an active boundary defect in `VkRenderState::UploadLights`: the old range-index guard accepted `UploadIndex == MAX_LIGHT_DATA`, one past the last valid `ivec4` entry. A zero-record upload at that point could address the first bytes of the packed light-data region. `VkLightUploadPolicy::Fits` now requires `uploadIndex < count` and uses overflow-safe data-capacity arithmetic; a compiled boundary fixture proves the last valid index and rejects one-past.

This is a correctness repair within #9's upload/fallback scope. It does not alter normal selected-light semantics, capacities or lifetimes.

## Deterministic workload extension

The accepted SDVK-002 corpus remains intact. Two generated, reproducible 256-light scenes extend it:

- `lights-dense-overlap` / `SDV9OVR`: compact 16x16 placement designed to maximize overlapping selected-light pressure;
- `lights-dense-dispersed` / `SDV9DSP`: the same count/type/profile distributed across the room around the solid occluder.

Both use a static deterministic cycle of normal/additive/subtractive point and spot lights, fixed authored colors/angles, the same camera/extent/settings, shadows disabled to isolate many-light list/upload/shader work, and the normal state/image oracle. Existing zero/one/64-light, shadow-boundary, portal/mirror, material, probe and sprite routes remain in the full corpus. PF-016's retained fixture supplies real model-path evidence; the freely generated SDVK-002 corpus does not add a new external model asset merely to inflate coverage.

The full hosted software-Vulkan route runs paired state/image qualification for all ten authored scenes. It retains the established three-process × 120-frame `lights-one` timing baseline and adds, only in `--full`, three independent 30-frame descriptive timing processes for each SDVK-009 dense scene after 20 warmup frames. Those dense timings are deliberately labeled software-Vulkan descriptive evidence, not physical-GPU performance acceptance.

## Candidate analysis, host prototype and disposition

| Candidate | Correctness / complexity | Off-GPU disposition |
| --- | --- | --- |
| **Current PF architecture (no change)** | Already PF-hardened; simple consumer-specific semantics; duplicate per-draw uploads and shader loops scale with selected lists | **Leading control. Physical confirmation required.** |
| PF-017 temporal record reuse / shader indirection | Correctness research existed, but accepted physical result regressed CPU setup and whole frame; adds identity/lifetime/indirection | **Rejected; do not resurrect.** |
| Reactivate inherited Z-min/max + copied-record tiles | 16-light hard truncation, unresolved portal group, disabled consumer, ~5.86 MB producer payload restored | **Rejected before hardware: cannot preserve equivalence.** |
| Reuse LevelMesh per-surface light indexes for scene shading | Lightmapper eligibility differs; four portal-copy cache can alias index 0; sprites/models require different semantics | **Rejected as a drop-in scene architecture.** |
| Ordered indexed tile/forward+ representation | Host prototype preserves all 256 IDs/order and reduces representative 1904x1001 overlap storage from 9,838,080 copied-record bytes to 519,680 bytes | **Research-only concept, not a runtime candidate.** It does not solve semantic eligibility, and in all-overlap input it still requires 122,880 tile/light loop entries; no shader-work win follows from storage shape alone. |
| Fresh clustered/forward+ redesign | Plausible higher-order scaling only after a shared semantic-eligibility representation exists | **Not justified for speculative production implementation before physical baseline shows a material need.** |

The host prototype is deliberately small and throwaway: it demonstrates the difference between full-record tile copying and ordered index indirection while preserving all 256 IDs and class order. It makes no runtime or GPU-speed claim. It is retained because it narrows any later design effort to the actual unresolved problem: semantic eligibility and whether spatial indirection reduces work after those semantics are preserved.

No candidate wins by dropping lights, changing shadows, quality or gameplay state. No arbitrary light cap is introduced.

### End-of-phase decision: State C — provisional no-change

All currently concrete alternatives are either already physically rejected or fail the source/correctness gate before hardware. The current PF architecture therefore remains the only candidate that is both production-correct and ready for a representative physical campaign.

This is **not** final SDVK-009 acceptance. The remaining question is empirical: whether current PF scaling under the matched sparse→dense workloads is acceptable on representative physical Vulkan. If it is, #9 can accept a no-change disposition. If it is not, the next architecture research must begin from a portal/consumer-correct semantic eligibility substrate rather than re-enabling the inherited 16-light tile path.

## Non-physical verification boundary

Focused host contracts cover:

- PF-016 light-query equivalence and dense duplicate handling;
- lighting compatibility / point, spot, additive and subtractive packing;
- portal/sprite correctness and PF-010 context invariants;
- shadow visibility/capacity rules;
- LevelMesh mutation/light-list contracts;
- PF-019 dormant-resource policy;
- compiled SDVK-009 upload-boundary and indexed-tile model;
- corpus preparation, native-CI orchestration and semantic-state validation.

The prepared SDVK-009 six-scene subset is deterministic and includes zero/one/64/256-overlap/256-dispersed/shadow-boundary workloads. Local focused contracts pass. The aggregate `python3 tools/check.py --output ...` attempt exceeded the local execution window before completion; no individual failure was observed in its partial log, so this is retained as an environment limitation rather than reclassified as a renderer failure. Exact-head hosted source/build identity and full CI/software-Vulkan results are therefore the required release gate for this phase.

## Remaining physical boundary

The later operator protocol is [SDVK-009-GPU-QUALIFICATION-PROTOCOL.md](SDVK-009-GPU-QUALIFICATION-PROTOCOL.md). It deliberately tests only the accepted current PF baseline because no alternative passed the off-GPU correctness gate. Reference state/image qualification stays at the authored 640x480 extent; architecture timing and matched dense state controls use a preregistered 1904x1001 override to maintain PF-016/PF-017 physical continuity. The campaign retains exact source/build/content/settings/cache/run order, raw CPU and named GPU timestamp distributions, state/image checks and the new light/upload counters, with CPU/GPU scaling normalized by actual uploaded/selected work rather than raw authored-light multiples.

#9 must remain open until that campaign is complete and the result is reconciled into an accepted final disposition.
