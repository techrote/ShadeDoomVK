# Renderer execution map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active + partial subpaths  
Primary issues: PF-001, PF-010, SDVK-002, SDVK-006

## Top-level frame flow

The hardware view enters through `src/rendering/hwrenderer/hw_entrypoint.cpp`.

High-level flow:

```text
RenderView(player)
  ├─ update changed canvases
  ├─ update camera textures for all levels
  ├─ incrementally render light-probe cubemaps when enabled
  └─ RenderViewpoint(main camera)
        ├─ build FRenderViewpoint / HWDrawInfo state
        ├─ portal-aware SetupView / projection
        ├─ if gl_raytrace: RenderState.RaytraceScene(...)
        └─ otherwise HWDrawInfo::ProcessScene(...)
             ├─ walls/flats/sprites/models/portals
             ├─ normal scene passes / optional G-buffer state
             └─ EndDrawScene / postprocess
```

`RenderViewpoint` is also reused for camera textures and probe cubemap faces. Therefore a future feature must not assume every render is the main screen view.

## Important render-context classes

### Main view — active

- persistent player/camera viewpoint;
- postprocess and 2D end-scene work run for the main view;
- frame interpolation uses `r_viewpoint.TicFrac`.

### Camera texture — active

- rendered through `RenderTextureView` and `RenderViewpoint`;
- not all main-view end-scene/postprocess assumptions apply;
- may run for levels other than the primary level.

### Recursive portal/mirror view — active

Primary code: `src/rendering/hwrenderer/scene/hw_portal.h/.cpp` and draw-context portal state.

Portal state tracks mirror/plane-mirror parity, recursion and view transforms. Effects using world/view orientation or temporal history must account for this context.

### Light-probe cubemap view — active/experimental

`RenderView` incrementally positions a LightProbe actor and renders six 90-degree faces via `RenderLightProbe`/`RenderViewpoint`. Interpolation is temporarily disabled for probe rendering.

This means scene-render code can execute while rendering environmental data, not only visible frames.

### `gl_raytrace` whole-scene viewer path — experimental

`RenderViewpoint` can bypass normal `ProcessScene` and call `RenderState.RaytraceScene`. Do not confuse this experimental viewer path with the ray-query shadow/occlusion primitives used by ordinary rendering.

## Scene object flow

`HWDrawInfo` and scene files under `src/rendering/hwrenderer/scene/` translate Doom scene semantics into render-state operations.

Important files:

- `hw_drawinfo.cpp/.h` — view/scene orchestration, visibility/draw lists, profiling;
- `hw_sprites.cpp` — sprite/model/particle presentation and lighting integration;
- `hw_spritelight.cpp` — actor/particle dynamic-light collection and world visibility traces;
- `hw_walls.cpp`, `hw_flats.cpp`, `hw_decal.cpp` — geometry/material/light paths;
- `hw_weapon.cpp` — first-person sprite/model path;
- `hw_portal.*` — recursive portal/mirror rendering;
- `hw_models.cpp` — model render adapter.

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

## Postprocess

The API-neutral postprocess framework lives under `src/common/rendering/hwrenderer/postprocessing/`; Vulkan resource execution lives under `src/common/rendering/vulkan/`.

Current scene resources include HDR color, normal, fog, depth/stencil and linear depth. Main-view postprocess includes tonemap/colormap/lens/FXAA/custom shaders depending on settings.

## Invariants

1. Rendering code must know whether it is main view, camera texture, recursive portal/mirror or probe render before creating persistent view-history assumptions.
2. Renderer-only time/interpolation must not alter simulation/tic state.
3. Portal recursion can change handedness and world-relative position.
4. Camera/probe renders may exercise material/light/resource paths even when their results are not directly visible in the main frame.
5. PF-010 may refactor context representation but must preserve all current rendering entry cases.
