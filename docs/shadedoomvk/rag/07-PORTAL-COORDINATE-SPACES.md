# Portal and coordinate-space contract

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active, compatibility-critical; PF-009 sprite-surface and PF-010 render-context extraction incorporated  
Primary issues: PF-009, PF-010, PF-014, PF-015, PF-016, SDVK-007, SDVK-012, SDVK-013

## Why this matters

Doom-family renderer code mixes several coordinate conventions and can render the same semantic object through translated/mirrored portal views. Normal mapping, POM, projected shadows, probe captures and temporal history all depend on getting these spaces and handedness rules right.

## Primary source areas

- `src/rendering/hwrenderer/scene/hw_portal.h/.cpp`
- `src/rendering/hwrenderer/scene/hw_drawinfo.*`
- `src/rendering/hwrenderer/scene/hw_rendercontext.h`
- `src/rendering/hwrenderer/scene/hw_sprites.cpp`
- `src/rendering/hwrenderer/scene/hw_sprite_surface.h`
- `src/rendering/hwrenderer/scene/hw_spritelight.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.*`
- `src/common/rendering/vulkan/vk_lightmapper.*`
- scene vertex/material shaders

## Portal state

`FPortalSceneState` tracks mirror and plane-mirror flags, recursion depth and other portal-scene state. Portal subclasses include line-to-line portals, line mirrors, skyboxes, sector stacks, plane mirrors and horizon portals.

`portalState.isMirrored()` derives handedness from mirror/plane-mirror parity. This already affects culling and, after PF-009, is captured explicitly in each sprite render-surface snapshot for later tangent/shadow consumers. PF-009 does not combine portal parity with UV/frame mirror state into a tangent sign; SDVK-007 owns that policy.

PF-010 also stores the currently traversed `HWRenderContext` alongside `FPortalSceneState`. For recursive scene portals, the child context is created **after** the inherited portal `Setup()` succeeds, so its line-mirror and plane-mirror bits describe the transform that will actually be used by `DrawScene()`. The parent context is restored only after inherited `Shutdown()` completes. This metadata does not alter either setup or shutdown.

## PF-010 parent/recursion identity

Every scene portal child records:

- the same top-level `epoch` as its root viewpoint;
- a distinct local `identity`;
- `parentIdentity` and incremented `recursionDepth`;
- the root render type (`MainView`, `CameraTexture`, `LightProbe` or `SavePicture`);
- inherited stereo-eye and probe-face identity;
- line-mirror parity, plane-mirror parity and their XOR handedness.

A nested mirror therefore cannot be mistaken for its parent merely because it views the same map position. Two active mirror dimensions remain separately inspectable even when their XOR yields non-mirrored effective handedness.

Persistent consumers must use `(epoch, identity)` rather than local identity alone. See `docs/shadedoomvk/PF-010-RENDER-CONTEXT-CONTRACT.md`.

## Portal groups and displacement

Dynamic-light and sprite code often works in a sector `PortalGroup` and uses displacement offsets or `FDynamicLight::PosRelative(group)` to translate light/object positions.

An actor-light fast path that reads only the actor's current section but loses portal-relative group semantics is incorrect even if it works on non-portal maps.

PF-009 records both sprite source and render portal-group identities plus the inherited `thruportal` route discriminator. The state is descriptive and does not replace current displacement logic.

PF-010 context identity is likewise not a replacement for portal-group displacement. It identifies the view/pass in which a renderer query occurs; the spatial query must still use the correct portal-group coordinate semantics.

## Important axis conversions

Doom world conventions and Vulkan/lightmapper structures sometimes reorder Y/Z. Examples include `SwapYZ` helpers and explicit construction such as `FVector3(vp.Pos.X, vp.Pos.Z, vp.Pos.Y)` for some Vulkan viewer paths.

Do not infer a universal axis convention from one shader or C++ type name. PF-010 leaves these conversions and their transform order unchanged; the context contract supplies identity, not another coordinate system.

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

PF-009 makes every item above except the final lighting basis explicit in `HWSprite::RenderSurface`. PF-010 separately identifies the render pass/root/recursion in which that sprite is traversed. These contracts are intentionally orthogonal: sprite frame/UV presentation is not folded into view identity.

PF-009 deliberately does not define sprite tangent space. SDVK-007 consumes this state to define and validate the future normal/right/up/forward basis without having to reconstruct frame, UV, billboard or portal meaning.

## Model orientation

Models use object-to-world and normal matrices; model renderer culling already combines model mirror state with portal mirror state. PF-009 classifies model-backed actors explicitly so downstream sprite-card consumers cannot accidentally apply sprite-surface policy to a model draw.

PF-010 does not change model matrices or culling; future view-dependent caches can additionally key by explicit render context.

## Probe/camera renders

Probe cubemap faces and camera textures re-enter normal scene rendering with different camera/view properties. PF-010 classifies them explicitly and gives every top-level `RenderViewpoint` call an epoch plus per-pass identity. Probe contexts also retain face `0..5`; a portal reached while rendering a probe inherits that root type and face.

Neither camera textures nor probe captures are eligible for future main-view history. PF-010 does not allocate history or alter their render transforms.

PF-009 snapshots the current view position and hardware view angles alongside sprite state; it does not create cross-frame history or assume the view is the main player camera.

## Shadow implications

- world ray-query visibility uses LevelMesh world geometry;
- actor projected/card shadows need portal-relative light/actor positions and mirror-correct silhouette orientation;
- contact bias must be computed in the receiver/world space actually used for the pass;
- a portal view must not accidentally reuse visibility results generated for a different coordinate transform unless the cache key proves equivalence;
- PF-010 supplies a conservative view/pass identity seam but does not itself define visibility-cache equivalence.

PF-009 supplies the orientation/mirror/portal inputs only. It does not add or alter a shadow algorithm.

## Invariants

1. A portal-group translation is part of light/object spatial identity for renderer queries.
2. Mirror parity is part of tangent/culling/projected-shadow handedness but remains separate from frame/UV mirror state until the owning feature defines their composition.
3. Camera texture and probe captures are separate render contexts; probe faces remain individually inspectable.
4. Any persistent cache depending on position/orientation must include enough PF-010 view/portal generation identity to reject incompatible reuse.
5. PF-009/PF-010 are extraction/refactor issues; they do not redefine Doom portal semantics or transform order.
6. PF-009 state is observational: frame selection, quad geometry, clipping, UV assignment, material binding, palette/translation behavior and draw ordering remain inherited.
7. PF-010 portal context is created only after successful inherited portal setup and is restored after inherited shutdown; context metadata must never become a hidden substitute for portal transform state.
