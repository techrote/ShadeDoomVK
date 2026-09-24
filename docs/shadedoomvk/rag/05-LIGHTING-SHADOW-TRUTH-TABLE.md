# Lighting and shadow truth table

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active; PF-011 compatibility math, PF-015 shadow/cache correctness and accepted PF-016 query equivalence incorporated
Primary issues: PF-011, PF-015, PF-016, PF-017, SDVK-009, SDVK-012, SDVK-013

## Dynamic light data

Primary files:

- `src/playsim/a_dynlight.*`
- `src/rendering/hwrenderer/hw_dynlightdata.cpp`
- `src/common/rendering/hwrenderer/data/hw_dynlightdata.h`
- `src/common/rendering/hwrenderer/data/hw_lightcompat.h`
- `src/common/rendering/hwrenderer/data/hw_shadowselection.h`
- `src/common/rendering/hwrenderer/data/hw_visibilitycache.h`
- `src/common/rendering/hwrenderer/data/hw_lightquery.h`
- `src/rendering/hwrenderer/scene/hw_spritelight.cpp`
- scene wall/flat/decal/sprite files
- `wadsrc/static/shaders/scene/lightmodel_*.glsl`

`FDynLightInfo` carries position/color, spot direction/angles, radius, linearity, strength, soft-shadow radius, shadow index and flags. Light arrays distinguish normal, subtractive and additive classes.

## Actor/sprite lighting modes

### CPU aggregate sprite light — active compatibility path

`HWDrawInfo::GetDynSpriteLight` walks a section light list and accumulates RGB contribution. It handles portal-relative positions, spotlights, attenuation, optional actor visibility trace and shadow-map test.

PF-011 records this as an intentionally distinct compatibility path. It floors inverse-square distance with `max(dist, sqrt(radius) * 2)`, consumes raw light linearity and does not apply the GPU list's additive `0.2` pre-scale. These inherited distinctions must not be silently unified with fragment lighting.

PF-015 keeps that math unchanged but hardens the optional static actor/light visibility result: actor movement, the PF-004 LevelMesh `Query` epoch, stable portal-group context and per-light update state all participate in reuse validity.

### GPU/per-pixel light list — active

`HWDrawInfo::GetDynSpriteLightList` owns one candidate eligibility/portal-relative/radius/visibility/packing pipeline. PF-016 replaces sorted per-query membership with `HWGenerationSet<FDynamicLight*>`, preserving first-encounter order. The baseline candidate source remains `BSPWalkCircle`; a local section source is used only after an actual baseline/local selected identity/order/class/group comparison and proof that the circle touches one section in one group. Successful qualification is cached by position, render radius, section and portal group. Any key change re-enters baseline qualification; ambiguous, boundary and cross-group cases stay on BSP.

`AddLightNode` guarantees one node per (light, section), so the already-qualified single-list traversal omits duplicate membership work. Qualification and BSP keep independent generation membership. PF-015 visibility inputs remain checked on every relevant query. `stat actorlightquery` exposes source/qualification/candidate/duplicate/filter/trace counts and timings; `stat actorlightcache` retains cache reasons. Repeated unsupported qualification retains temporary vector allocation costs.

PR #67 is accepted at merge `6091d6739c4b7dc96ef7913c911bf4eba89d7715`, with successful submitted-head/post-merge CI and live portal/model/sprite/visibility/invalidation equivalence. Mode-0 ordinary sprites use the separate aggregate path; per-pixel models invoke this list path and its renderer-private CPU traces even in mode 0. See `PF-016-RUNTIME-EVIDENCE.md` for actual path activation, exact images/state and the production performance gate.

PF-011 names list-packing calibration in `HWLightCompat`: additive GPU color scale `0.2`, normalized byte color channels, uploaded linearity clamped to `[0,1]`, and the sunlight-proxy constants. PF-016 preserves that calibration while optimizing candidate sourcing and duplicate membership, with selected-light equivalence evidence.

PF-015 does not optimize this gathering path. It only changes whether an existing actor/static-light trace result is valid to reuse.

### Models/viewmodels

Models can use per-pixel dynamic light lists; weapon code has its own viewmodel path. SDVK-011 owns later explicit parity/policy.

## Sunlight

Sunlight is represented as a cheap far-away directional-light approximation in dynamic-light data and has separate world/probe/lightmap roles. Actor sunlight visibility can use LevelMesh tracing and cached results.

PF-011 freezes the active proxy as distance `100000`, radius `100000000`, strength `1500`, with shader inverse-square bypass beginning at radius `1000000`. These are compatibility sentinels, not physical distances or intensity units. The fake model light retains the same proxy representation with its inherited adjusted direction/color and trace policy.

PF-015 extends `sun_trace_cache_t` with the PF-004 `Query` epoch and stable portal-group cache context. A world-query mutation forces `TraceSky` again even when the sampled actor/particle position is stationary.

## World occlusion

### CPU LevelMesh trace — active

Actor/static-light visibility can call `level.levelMesh->Trace(...)`. PF-015 keys reuse to the LevelMesh `Query` mutation epoch rather than assuming actor/light movement is the only visibility-changing input.

### Vulkan ray query — active when supported/enabled

Shaders can use acceleration structures and `rayQueryEXT`; a shader-side CPU-tree-style fallback exists when ray query is unavailable.

This represents world/LevelMesh geometry, not automatically alpha-tested sprite silhouette geometry. PF-015 does not change capability routing or the non-ray fallback.

## Dynamic 1D shadow map — active

`ShadowMap` stores per-light 1D depth rows in a 1024x1024 texture. PF-015 preserves exactly 1024 rows.

When the active shadowmapped eligible set is <=1024, selection and row order remain inherited linked-list order. Only overflow invokes `HWSelectShadowCandidates`: squared distance to the interpolated central main render viewpoint is the primary relevance metric, followed by deterministic position/light-semantic tie fields. This removes linked-list traversal accident from non-equivalent overflow selection while preserving the entire below-cap workload.

Exact full-key ties are selector-semantic equivalents; stable ordering is retained inside that equivalence class. Shadow-map generation occurs once before stereo eye iteration, so the central pre-eye viewpoint—not a left/right eye offset—is the relevance origin.

`stat shadowmap` reports processed, eligible candidate, selected and dropped-overflow counts.

## Sprite shadows

VKDoom contains simple sprite-shadow behavior/flags, but not the final ShadeDoomVK actor-cast architecture. SDVK-012 remains comparative: blob/proxy, alpha card, depth card and tractable AS participation are evidence candidates.

## Lighting/shadow mode truth

| Capability | Current status | Notes |
|---|---|---|
| dynamic point lights | active | legacy + per-pixel/PBR paths |
| spot lights | active | cosine-space smoothstep in light data/shaders |
| inverse-square/linear blend | active | inherited compatibility equation; PF-011 freezes operation ordering |
| actor lighting world occlusion | active/keyed cache | CPU LevelMesh trace; PF-004 Query + portal-group validity |
| world shadow map | active | 1D 1024-row dynamic shadow map; PF-015 deterministic overflow |
| world ray-query shadows/visibility | active optional | Vulkan capability dependent |
| precise ray-query variant | active optional/experimental | shader key selects precise mode |
| sprite alpha silhouette RT geometry | not a general baseline feature | do not claim otherwise |
| sprite projected/contact shadow | simple inherited + future research | SDVK-012/013 own architecture |
| soft shadow radius | active metadata/path dependent | GLDEFS light property exists |
| tiled/clustered dynamic lighting | dormant scaffold | see `10-KNOWN-TRAPS-DORMANT-PATHS.md` |

## Cache and invalidation contract

`ActorTraceStaticLight` retains the existing per-light sorted actor/result cache. PF-015 adds a small actor-side stamp rather than globally clearing caches:

- actor-position/dynamic-sector change invalidates as before;
- PF-004 `LevelMeshMutationEpochs::Query` change invalidates world-occlusion results;
- stable portal-group change invalidates coordinate-context reuse;
- `light->updated` invalidates that light as before.

PF-010 render-pass `epoch`/`identity` are not included because they change every invocation and are not inputs to the current LevelMesh world trace. Keying on them would turn the cache into a systematic miss. PF-010 still supplies the pass-identity seam; if future tracing uses additional pass state, that state must be keyed explicitly.

`stat actorlightcache` reports cumulative hits/misses and actor/world-query/portal/light invalidation reasons plus sun-cache hits/misses.

## Light math compatibility

The canonical PF-011 contract is `docs/shadedoomvk/PF-011-LIGHTING-COMPATIBILITY-CONTRACT.md`.

Active compatibility calibration is now named rather than implied by scattered literals:

- authoring/current radius maps to render radius at `2x`; inverse-square strength remains `min(1500, render_radius^2 / 10)`;
- GPU inverse-square and linear attenuation retain the same equation and floating-point operation ordering;
- PBR dynamic/sun radiance uses `LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE == 2.5`;
- the PBR ambient-sector approximation remains `2.25`, with metallic ambient-specular approximation `0.40`;
- normal/subtractive/additive packing semantics remain unchanged, including the GPU-only additive `0.2` scale.

These are renderer compatibility units, not lumens/lux/candela. PF-011 deliberately did not recalibrate lighting, exposure, bloom or authoring defaults.

## Invariants

1. A performance optimization must preserve the eligible/selected light set for its declared equivalent mode.
2. Portal-relative light positions/groups must remain correct.
3. Cached visibility must be invalidated when any input affecting occlusion changes; PF-004 `Query` is authoritative for LevelMesh world-query mutations.
4. Shadow cap policy is deterministic and inspectable; <=1024 retains inherited set/order, overflow is view-distance relevant.
5. Ray-query world occlusion must not be described as full ray-traced sprite geometry.
6. PF work does not choose the eventual SDVK sprite-shadow architecture.
7. PF-011 compatibility scalars/equations are not physical-unit declarations and must not be opportunistically retuned.
8. CPU aggregate sprite and GPU/per-pixel light paths remain separately owned where their inherited input conditioning differs.
9. PF-010 transient pass identity must not be used as a cache-busting surrogate when stable spatial/query inputs prove equivalence.

See `docs/shadedoomvk/PF-015-SHADOW-VISIBILITY-CONTRACT.md` for the executable PF-015 selection/cache contract.
