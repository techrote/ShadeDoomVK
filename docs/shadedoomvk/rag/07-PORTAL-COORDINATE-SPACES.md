# Portal and coordinate-space contract

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active, compatibility-critical; PF-009 sprite-surface extraction implemented pending acceptance  
Primary issues: PF-009, PF-010, PF-014, PF-015, PF-016, SDVK-007, SDVK-012, SDVK-013

## Why this matters

Doom-family renderer code mixes several coordinate conventions and can render the same semantic object through translated/mirrored portal views. Normal mapping, POM, projected shadows, probe captures and temporal history all depend on getting these spaces and handedness rules right.

## Primary source areas

- `src/rendering/hwrenderer/scene/hw_portal.h/.cpp`
- `src/rendering/hwrenderer/scene/hw_drawinfo.*`
- `src/rendering/hwrenderer/scene/hw_sprites.cpp`
- `src/rendering/hwrenderer/scene/hw_sprite_surface.h`
- `src/rendering/hwrenderer/scene/hw_spritelight.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.*`
- `src/common/rendering/vulkan/vk_lightmapper.*`
- scene vertex/material shaders

## Portal state

`FPortalSceneState` tracks mirror and plane-mirror flags, recursion depth and other portal-scene state. Portal subclasses include line-to-line portals, line mirrors, skyboxes, sector stacks, plane mirrors and horizon portals.

`portalState.isMirrored()` derives handedness from mirror/plane-mirror parity. This already affects culling and, after PF-009, is captured explicitly in each sprite render-surface snapshot for later tangent/shadow consumers. PF-009 does not combine portal parity with UV/frame mirror state into a tangent sign; SDVK-007 owns that policy.

## Portal groups and displacement

Dynamic-light and sprite code often works in a sector `PortalGroup` and uses displacement offsets or `FDynamicLight::PosRelative(group)` to translate light/object positions.

An actor-light fast path that reads only the actor's current section but loses portal-relative group semantics is incorrect even if it works on non-portal maps.

PF-009 records both sprite source and render portal-group identities plus the inherited `thruportal` route discriminator. The state is descriptive and does not replace current displacement logic.

## Important axis conversions

Doom world conventions and Vulkan/lightmapper structures sometimes reorder Y/Z. Examples include `SwapYZ` helpers and explicit construction such as `FVector3(vp.Pos.X, vp.Pos.Z, vp.Pos.Y)` for some Vulkan viewer paths.

Do not infer a universal axis convention from one shader or C++ type name. PF-010 should document concrete boundary conversions in code near their interfaces.

## Sprite orientation spaces

For sprite material work distinguish:

- gameplay actor orientation/yaw;
- selected Doom sprite rotation frame;
- frame-mirror result and effective X/Y UV mirror state;
- face/wall/flat sprite presentation;
- inherited XY-billboard and face-camera policy (independent booleans);
- render-view position/orientation;
- portal-group source/render identity;
- portal/mirror handedness;
- world-space normal/right/up/forward used by lighting.

PF-009 makes every item above explicit except the final lighting basis. `HWSprite::RenderSurface` is the canonical renderer-side snapshot and `ResolveHWSpriteOrientationPolicy()` is the pure inherited billboard-policy adapter. See `docs/shadedoomvk/PF-009-SPRITE-SURFACE-CONTRACT.md`.

PF-009 deliberately does not define sprite tangent space. SDVK-007 consumes this state to define and validate the future normal/right/up/forward basis without having to reconstruct frame, UV, billboard or portal meaning.

## Model orientation

Models use object-to-world and normal matrices; model renderer culling already combines model mirror state with portal mirror state. PF-009 classifies model-backed actors explicitly so downstream sprite-card consumers cannot accidentally apply sprite-surface policy to a model draw.

## Probe/camera renders

Probe cubemap faces and camera textures re-enter normal scene rendering with different camera/view properties. A view-history or screen-space effect must key history by render context rather than treating every RenderViewpoint call as one continuous main camera.

PF-009 snapshots the current view position and hardware view angles alongside sprite state; it does not create cross-frame history or assume the view is the main player camera.

## Shadow implications

- world ray-query visibility uses LevelMesh world geometry;
- actor projected/card shadows need portal-relative light/actor positions and mirror-correct silhouette orientation;
- contact bias must be computed in the receiver/world space actually used for the pass;
- a portal view must not accidentally reuse visibility results generated for a different coordinate transform unless the cache key proves equivalence.

PF-009 supplies the orientation/mirror/portal inputs only. It does not add or alter a shadow algorithm.

## Invariants

1. A portal-group translation is part of light/object spatial identity for renderer queries.
2. Mirror parity is part of tangent/culling/projected-shadow handedness but remains separate from frame/UV mirror state until the owning feature defines their composition.
3. Camera texture and probe captures are separate render contexts.
4. Any cross-frame cache depending on position/orientation must include enough view/portal generation identity to reject incompatible reuse.
5. PF-009/PF-010 are extraction/refactor issues; they do not redefine Doom portal semantics.
6. PF-009 state is observational: frame selection, quad geometry, clipping, UV assignment, material binding, palette/translation behavior and draw ordering remain inherited.
