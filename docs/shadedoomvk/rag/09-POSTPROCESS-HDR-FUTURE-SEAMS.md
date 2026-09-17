# Postprocess, HDR and future graphical seams

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active HDR/postprocess; temporal substrate incomplete  
Primary issues: PF-010, PF-011, PF-019, SDVK-006, SDVK-016 and future post-freeze work

## Existing strengths

Primary files:

- `src/common/rendering/hwrenderer/postprocessing/*`
- `src/common/rendering/vulkan/textures/vk_renderbuffers.*`
- `src/common/rendering/vulkan/vk_postprocess.*`

The baseline already provides unusually useful groundwork for future ShadeDoomVK graphical ambitions:

- HDR `R16G16B16A16_SFLOAT` scene color;
- HDR postprocess pipeline images;
- scene depth/stencil and depth-only view;
- linear depth texture;
- scene normal target;
- fog target;
- SSAO;
- tonemapping modes;
- colormap/lens/FXAA stages;
- custom postprocess shaders;
- ping-pong postprocess texture abstraction.

This makes bloom, exposure work, depth-aware effects and many volumetric/composite experiments much closer than they would be in a purely forward LDR port.

## Current postprocess model

API-neutral `PPRenderState` describes input texture types, filtering/wrapping, outputs, uniforms, blending and optional depth/stencil use. Vulkan maps those abstractions to textures/framebuffers/pipelines.

This separation is worth preserving.

## Missing major substrate: per-view temporal history

The audited baseline does not expose a coherent general contract for:

- motion vectors;
- previous view/projection matrices per render context;
- history image ownership;
- history validity epochs;
- teleport/camera-cut resets;
- portal/mirror history transforms;
- camera-texture independent histories;
- probe-render history exclusion.

Therefore future TAA, temporal volumetrics, temporal SSR or temporal shadow denoising must **not** be added as a simple post shader that assumes one continuous camera.

PF-010 creates explicit render-view/pass identity but does not implement temporal effects. SDVK-006 creates renderer visual-time semantics. A later post-freeze temporal issue should combine both.

## Lighting/exposure relationship

Current PBR code uses compatibility brightness scaling and sector-light approximations. Bloom/exposure quality depends on stable meanings for HDR light energy; PF-011 therefore centralizes the current compatibility bridge before future calibration.

Do not tune PBR constants opportunistically merely to make bloom look better.

## Future opportunities enabled by current buffers

These are aspirations/research directions, not PF requirements:

### Bloom / exposure

Technically straightforward with HDR scene/pipeline buffers after light-intensity/exposure policy is explicit.

### Volumetric fog / shafts

Plausible using linear depth, light metadata and world visibility. A scalable implementation must define portal/view behavior and temporal strategy separately.

### Screen-space reflections

Possible in limited form with depth/normal/HDR data, but correct portal/history/fallback semantics require additional work.

### TAA / temporal upsampling

Requires motion/history infrastructure not present as a coherent baseline contract.

### Temporal denoising

Potentially useful for expensive shadow/volumetric effects, but must follow the same per-view history discipline.

## PF-019 dormant resource rule

Z-min/max/light-tile render resources currently exist even though the scene tiled-light path is dormant. PF-019 may avoid allocating work proven unused in the active configuration, but only after PF-007 capability state and PF-006 pipeline identity make the active path explicit.

## Invariants

1. Preserve HDR precision and current postprocess outputs during PF unless an issue owns a correctness fix.
2. Main-view history must never be implicitly shared with portal, camera-texture or probe renders.
3. Future temporal features require explicit history invalidation on discontinuities.
4. Exposure/tonemap/bloom policy should follow a documented HDR light-energy contract, not arbitrary effect-specific compensation.
5. Postprocess custom-shader extensibility remains a compatibility surface.
