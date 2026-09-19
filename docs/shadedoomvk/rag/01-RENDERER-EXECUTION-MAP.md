# Renderer execution map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active + partial subpaths; PF-009 sprite-surface and PF-010 render-context extraction incorporated  
Primary issues: PF-001, PF-009, PF-010, SDVK-002, SDVK-006

## Top-level frame flow

The hardware view enters through `src/rendering/hwrenderer/hw_entrypoint.cpp`.

High-level flow:

```text
RenderView(player)
  ├─ update changed canvases
  ├─ update camera textures for all levels
  ├─ incrementally render light-probe cubemaps when enabled
  └─ RenderViewpoint(main camera)
        ├─ classify PF-010 top-level context / begin context epoch
        ├─ build FRenderViewpoint / HWDrawInfo state
        ├─ portal-aware SetupView / projection
        ├─ if gl_raytrace: RenderState.RaytraceScene(...)
        └─ otherwise HWDrawInfo::ProcessScene(...)
             ├─ walls/flats/sprites/models/portals
             ├─ recursive scene portals derive child context after Setup
             ├─ normal scene passes / optional G-buffer state
             └─ EndDrawScene / postprocess
```

`RenderViewpoint` is also reused for camera textures, probe cubemap faces and save-picture rendering. PF-010 makes this distinction explicit through `HWRenderContext`; callers must not infer that every scene pass is the main screen view.

## Important render-context classes

### Main view — active

- persistent player/camera viewpoint;
- postprocess and 2D end-scene work run for the visible main view;
- frame interpolation uses `r_viewpoint.TicFrac`;
- PF-010 classifies it as `MainView` and marks only this root type eligible for future persistent main-view history.

### Camera texture — active

- rendered through `RenderTextureView` and `RenderViewpoint`;
- not all main-view end-scene/postprocess assumptions apply;
- may run for levels other than the primary level;
- PF-010 classifies it as `CameraTexture`, with a separate top-level epoch/identity and no history eligibility.

### Recursive portal/mirror view — active

Primary code: `src/rendering/hwrenderer/scene/hw_portal.h/.cpp` and draw-context portal state.

Portal state tracks mirror/plane-mirror parity, recursion and view transforms. PF-010 adds a descriptive `Portal` child context after successful portal `Setup()` has established the live transform/parity and before recursive `DrawScene()`. The child records parent identity, recursion depth, root type, eye/probe-face state and both mirror parity bits. Effects using world/view orientation or temporal history must account for this context.

### Light-probe cubemap view — active/experimental

`RenderView` incrementally positions a LightProbe actor and renders six 90-degree faces via `RenderLightProbe`/`RenderViewpoint`. Interpolation is temporarily disabled for probe rendering.

PF-010 classifies each face as `LightProbe`, records face `0..5`, and excludes it from main-view history/postprocess eligibility. Recursive portals reached from a face keep that probe root/face identity.

This means scene-render code can execute while rendering environmental data, not only visible frames.

### Save-picture view — active

`WriteSavePic` reuses the `mainview=true, toscreen=false` path. PF-010 names it `SavePicture`: it retains the inherited postprocess route but is not eligible for future persistent main-view history.

### `gl_raytrace` whole-scene viewer path — experimental

`RenderViewpoint` can bypass normal `ProcessScene` and call `RenderState.RaytraceScene`. It retains the same PF-010 root-context classification as the viewpoint that selected it. Do not confuse this experimental viewer path with the ray-query shadow/occlusion primitives used by ordinary rendering.

## PF-010 identity boundary

`src/rendering/hwrenderer/scene/hw_rendercontext.h` defines the observational context contract.

- every top-level `RenderViewpoint` invocation begins a non-zero context epoch;
- each stereo eye and recursive scene portal receives a distinct local identity in that epoch;
- portal children inherit the root classification and record `parentIdentity`/`recursionDepth`;
- `(epoch, identity)` is the persistent consumer key; identity alone may be reused after an epoch transition;
- context metadata does not drive matrices, transforms, draw modes or postprocessing in PF-010.

See `docs/shadedoomvk/PF-010-RENDER-CONTEXT-CONTRACT.md`.

## Scene object flow

`HWDrawInfo` and scene files under `src/rendering/hwrenderer/scene/` translate Doom scene semantics into render-state operations.

Important files:

- `hw_drawinfo.cpp/.h` — view/scene orchestration, visibility/draw lists, profiling;
- `hw_rendercontext.h` — PF-010 root/portal identity and eligibility metadata;
- `hw_sprites.cpp` — sprite/model/particle presentation and lighting integration;
- `hw_sprite_surface.h` — PF-009 semantic sprite-presentation enums and pure billboard-policy resolver;
- `hw_spritelight.cpp` — actor/particle dynamic-light collection and world visibility traces;
- `hw_walls.cpp`, `hw_flats.cpp`, `hw_decal.cpp` — geometry/material/light paths;
- `hw_weapon.cpp` — first-person sprite/model path;
- `hw_portal.*` — recursive portal/mirror rendering;
- `hw_models.cpp` — model render adapter.

PF-009 adds the observational `HWSprite::RenderSurface` snapshot immediately before inherited vertex construction. It records selected frame/material identity, final card/UV state, billboard decisions, view/orientation inputs and portal/mirror identity for later renderer consumers; it does not replace frame selection, clipping, transforms, material binding, draw ordering or normal/TBN behavior.

## Render-state → Vulkan

API-neutral `FRenderState` calls feed `VkRenderState` in `src/common/rendering/vulkan/vk_renderstate.cpp`.

`VkRenderState::Apply()` materializes:

- surface uniforms;
- matrices;
- pipeline/render-pass selection;
- viewport/scissor/stencil/depth-bias;
- push constants;
- vertex/index/buffer sets.

Pipeline/shader state is keyed in `vk_renderpass.*` and `vk_shader.*`.

PF-010 does not add context bits to pipeline identity: the extracted state is a future cache/history seam, not a shader/pipeline behavior change.

## Postprocess

The API-neutral postprocess framework lives under `src/common/rendering/hwrenderer/postprocessing/`; Vulkan resource execution lives under `src/common/rendering/vulkan/`.

Current scene resources include HDR color, normal, fog, depth/stencil and linear depth. Main-view postprocess includes tonemap/colormap/lens/FXAA/custom shaders depending on settings.

PF-010 exposes descriptive `postprocessEligible` and `historyEligible` flags but preserves the inherited `mainview`/`toscreen` control flow exactly.

## Invariants

1. Rendering code must know whether it is main view, camera texture, recursive portal/mirror, probe render or save-picture pass before creating persistent view-history assumptions.
2. Renderer-only time/interpolation must not alter simulation/tic state.
3. Portal recursion can change handedness and world-relative position; PF-010 records both line/plane parity only after inherited portal setup establishes them.
4. Camera/probe renders may exercise material/light/resource paths even when their results are not directly visible in the main frame.
5. PF-010 context is observational: it must not alter transform order, output, postprocess routing or gameplay state.
6. PF-009 sprite-surface state is descriptive only; existing geometry/material/output paths remain authoritative until their owning later issues explicitly change them.
7. Any persistent view-dependent cache must use enough PF-010 identity to reject cross-root/cross-recursion reuse; `identity` without `epoch` is insufficient.
