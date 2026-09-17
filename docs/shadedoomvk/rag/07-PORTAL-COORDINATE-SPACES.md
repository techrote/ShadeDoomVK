# Portal and coordinate-space contract

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active, compatibility-critical  
Primary issues: PF-009, PF-010, PF-014, PF-015, PF-016, SDVK-007, SDVK-012, SDVK-013

## Why this matters

Doom-family renderer code mixes several coordinate conventions and can render the same semantic object through translated/mirrored portal views. Normal mapping, POM, projected shadows, probe captures and temporal history all depend on getting these spaces and handedness rules right.

## Primary source areas

- `src/rendering/hwrenderer/scene/hw_portal.h/.cpp`
- `src/rendering/hwrenderer/scene/hw_drawinfo.*`
- `src/rendering/hwrenderer/scene/hw_sprites.cpp`
- `src/rendering/hwrenderer/scene/hw_spritelight.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.*`
- `src/common/rendering/vulkan/vk_lightmapper.*`
- scene vertex/material shaders

## Portal state

`FPortalSceneState` tracks mirror and plane-mirror flags, recursion depth and other portal-scene state. Portal subclasses include line-to-line portals, line mirrors, skyboxes, sector stacks, plane mirrors and horizon portals.

`portalState.isMirrored()` derives handedness from mirror/plane-mirror parity. This already affects culling and must later participate in sprite tangent/shadow orientation.

## Portal groups and displacement

Dynamic-light and sprite code often works in a sector `PortalGroup` and uses displacement offsets or `FDynamicLight::PosRelative(group)` to translate light/object positions.

An actor-light fast path that reads only the actor's current section but loses portal-relative group semantics is incorrect even if it works on non-portal maps.

## Important axis conversions

Doom world conventions and Vulkan/lightmapper structures sometimes reorder Y/Z. Examples include `SwapYZ` helpers and explicit construction such as `FVector3(vp.Pos.X, vp.Pos.Z, vp.Pos.Y)` for some Vulkan viewer paths.

Do not infer a universal axis convention from one shader or C++ type name. PF-010 should document concrete boundary conversions in code near their interfaces.

## Sprite orientation spaces

For future sprite material work distinguish:

- gameplay actor orientation/yaw;
- selected Doom sprite rotation frame;
- UV mirror/flipped-frame state;
- face/wall/flat sprite billboard mode;
- render-view facing direction;
- portal/mirror handedness;
- world-space normal/right/up/forward used by lighting.

PF-009 extracts these into a canonical render-surface/orientation state without changing current normal lighting. SDVK-007 uses that state to define explicit sprite tangent-space behavior.

## Model orientation

Models use object-to-world and normal matrices; model renderer culling already combines model mirror state with portal mirror state. Sprite work should learn from this explicit transform handling rather than derive orientation only from screen-space derivatives.

## Probe/camera renders

Probe cubemap faces and camera textures re-enter normal scene rendering with different camera/view properties. A view-history or screen-space effect must key history by render context rather than treating every RenderViewpoint call as one continuous main camera.

## Shadow implications

- world ray-query visibility uses LevelMesh world geometry;
- actor projected/card shadows need portal-relative light/actor positions and mirror-correct silhouette orientation;
- contact bias must be computed in the receiver/world space actually used for the pass;
- a portal view must not accidentally reuse visibility results generated for a different coordinate transform unless the cache key proves equivalence.

## Invariants

1. A portal-group translation is part of light/object spatial identity for renderer queries.
2. Mirror parity is part of tangent/culling/projected-shadow handedness.
3. Camera texture and probe captures are separate render contexts.
4. Any cross-frame cache depending on position/orientation must include enough view/portal generation identity to reject incompatible reuse.
5. PF-009/PF-010 are extraction/refactor issues; they do not redefine Doom portal semantics.
