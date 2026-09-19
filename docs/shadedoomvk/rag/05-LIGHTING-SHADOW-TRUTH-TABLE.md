# Lighting and shadow truth table

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: mixed active/partial/experimental; PF-011 compatibility math named and documented  
Primary issues: PF-011, PF-015, PF-016, PF-017, SDVK-009, SDVK-012, SDVK-013

## Dynamic light data

Primary files:

- `src/playsim/a_dynlight.*`
- `src/rendering/hwrenderer/hw_dynlightdata.cpp`
- `src/common/rendering/hwrenderer/data/hw_dynlightdata.h`
- `src/common/rendering/hwrenderer/data/hw_lightcompat.h`
- `src/rendering/hwrenderer/scene/hw_spritelight.cpp`
- scene wall/flat/decal/sprite files
- `wadsrc/static/shaders/scene/lightmodel_*.glsl`

`FDynLightInfo` carries position/color, spot direction/angles, radius, linearity, strength, soft-shadow radius, shadow index and flags. Light arrays distinguish normal, subtractive and additive classes.

## Actor/sprite lighting modes

### CPU aggregate sprite light — active compatibility path

`HWDrawInfo::GetDynSpriteLight` walks a section light list and accumulates RGB contribution. It handles portal-relative positions, spotlights, attenuation, optional actor visibility trace and shadow-map test.

PF-011 records this as an intentionally distinct compatibility path. It floors inverse-square distance with `max(dist, sqrt(radius) * 2)`, consumes raw light linearity and does not apply the GPU list's additive `0.2` pre-scale. These inherited distinctions must not be silently unified with fragment lighting.

### GPU/per-pixel light list — active

`HWDrawInfo::GetDynSpriteLightList` collects candidate lights, performs distance/filter/visibility logic and uploads `FDynLightData`. It currently uses `BSPWalkCircle` plus per-section linked lists and sorted duplicate suppression.

PF-011 names list-packing calibration in `HWLightCompat`: additive GPU color scale `0.2`, normalized byte color channels, uploaded linearity clamped to `[0,1]`, and the sunlight-proxy constants. PF-016 may replace collection/dedup internals only with selected-light equivalence evidence.

### Models/viewmodels

Models can use per-pixel dynamic light lists; weapon code has its own viewmodel path. SDVK-011 owns later explicit parity/policy.

## Sunlight

Sunlight is represented as a cheap far-away directional-light approximation in dynamic-light data and has separate world/probe/lightmap roles. Actor sunlight visibility can use LevelMesh tracing and cached results.

PF-011 freezes the active proxy as distance `100000`, radius `100000000`, strength `1500`, with shader inverse-square bypass beginning at radius `1000000`. These are compatibility sentinels, not physical distances or intensity units. The fake model light retains the same proxy representation with its inherited adjusted direction/color and trace policy. PF-015 owns relevant visibility-cache invalidation.

## World occlusion

### CPU LevelMesh trace — active

Actor/static-light visibility can call `level.levelMesh->Trace(...)`.

### Vulkan ray query — active when supported/enabled

Shaders can use acceleration structures and `rayQueryEXT`; a shader-side CPU-tree-style fallback exists when ray query is unavailable.

This represents world/LevelMesh geometry, not automatically alpha-tested sprite silhouette geometry.

## Dynamic 1D shadow map — active

`ShadowMap` stores per-light 1D depth rows in a 1024x1024 texture. The baseline collects up to 1024 active shadowmapped lights. Source contains a TODO noting that lights should be collected spatially so closer lights are preferred.

PF-015 must make cap behavior deterministic and meaningful without silently lowering the shadow quality of the same eligible-light workload.

## Sprite shadows

VKDoom contains simple sprite-shadow behavior/flags, but not the final ShadeDoomVK actor-cast architecture. SDVK-012 remains comparative: blob/proxy, alpha card, depth card and tractable AS participation are evidence candidates.

## Lighting/shadow mode truth

| Capability | Baseline status | Notes |
|---|---|---|
| dynamic point lights | active | legacy + per-pixel/PBR paths |
| spot lights | active | cosine-space smoothstep in light data/shaders |
| inverse-square/linear blend | active | inherited compatibility equation; PF-011 freezes operation ordering |
| actor lighting world occlusion | active/limited cache | CPU LevelMesh trace path |
| world shadow map | active | 1D dynamic shadow map path |
| world ray-query shadows/visibility | active optional | Vulkan capability dependent |
| precise ray-query variant | active optional/experimental | shader key selects precise mode |
| sprite alpha silhouette RT geometry | not a general baseline feature | do not claim otherwise |
| sprite projected/contact shadow | simple inherited + future research | SDVK-012/013 own architecture |
| soft shadow radius | active metadata/path dependent | GLDEFS light property exists |
| tiled/clustered dynamic lighting | dormant scaffold | see `10-KNOWN-TRAPS-DORMANT-PATHS.md` |

## Cache and invalidation concern

`ActorTraceStaticLight` caches per-actor/per-light trace results and actor movement state. A moving world occluder can change visibility even when neither actor nor light moved. PF-015 must reproduce this class and make LevelMesh/occluder generation participate in validity if required.

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
3. Cached visibility must be invalidated when any input affecting occlusion changes.
4. Shadow cap policy must be deterministic and inspectable.
5. Ray-query world occlusion must not be described as full ray-traced sprite geometry.
6. PF work does not choose the eventual SDVK sprite-shadow architecture.
7. PF-011 compatibility scalars/equations are not physical-unit declarations and must not be opportunistically retuned.
8. CPU aggregate sprite and GPU/per-pixel light paths remain separately owned where their inherited input conditioning differs.
