# Postprocess, HDR and future graphical seams

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active HDR/postprocess; PF-010 view identity extracted; temporal substrate still intentionally incomplete  
Primary issues: PF-010, PF-011, PF-019, SDVK-006, SDVK-016 and future post-freeze work

## Existing strengths

Primary files:

- `src/common/rendering/hwrenderer/postprocessing/*`
- `src/common/rendering/vulkan/textures/vk_renderbuffers.*`
- `src/common/rendering/vulkan/vk_postprocess.*`
- `src/rendering/hwrenderer/scene/hw_rendercontext.h`

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

PF-010 does not route postprocess through its new metadata. Existing `RenderViewpoint` `mainview`/`toscreen` branches remain behaviorally authoritative, including the historical save-picture postprocess path. `postprocessEligible` merely describes that inherited distinction for diagnostics/future consumers.

## PF-010 view-identity seam

`HWRenderContext` now makes the scene pass explicit before any future temporal state is added:

- top-level `RenderViewpoint` invocations have a non-zero epoch;
- stereo eyes and recursive scene portals receive distinct identities within that epoch;
- recursive portals retain parent identity, recursion depth, root render type, mirror parity, stereo eye and probe face;
- main view, camera texture, six probe faces and save-picture rendering are separately classified;
- only direct visible `MainView` roots are marked `historyEligible`;
- camera, probe, save-picture and recursive portal passes are not history eligible in PF-010.

The pair `(epoch, identity)` is the renderer pass identity seam. Identity alone is deliberately local to an epoch and may be reused after the next top-level viewpoint begins.

This is conservative by design: PF-010 does **not** declare two different portal or camera passes safe to share persistent history even if their matrices happen to compare equal.

See `docs/shadedoomvk/PF-010-RENDER-CONTEXT-CONTRACT.md`.

## Still missing: temporal history implementation

PF-010 closes the view-classification ambiguity but intentionally does not provide:

- motion vectors;
- previous view/projection matrices per render context;
- history image ownership;
- cross-frame history validity epochs;
- teleport/camera-cut reset policy;
- portal/mirror history transforms;
- camera-texture independent history storage;
- temporal probe processing.

Therefore future TAA, temporal volumetrics, temporal SSR or temporal shadow denoising must **not** be added as a simple post shader that assumes one continuous camera. The future owner must define persistent history lifetime/invalidation on top of PF-010 identity rather than treating PF-010's per-invocation epoch itself as cross-frame history.

SDVK-006 creates renderer visual-time semantics. A later post-freeze temporal issue should combine that time contract with PF-010 view identity and an explicit history-lifetime design.

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

Requires motion/history infrastructure not present as a coherent implementation contract. PF-010 supplies view identity only.

### Temporal denoising

Potentially useful for expensive shadow/volumetric effects, but must follow the same per-view history discipline.

## PF-019 dormant resource rule

Z-min/max/light-tile render resources currently exist even though the scene tiled-light path is dormant. PF-019 may avoid allocating work proven unused in the active configuration, but only after PF-007 capability state and PF-006 pipeline identity make the active path explicit.

## Invariants

1. Preserve HDR precision and current postprocess outputs during PF unless an issue owns a correctness fix.
2. Main-view history must never be implicitly shared with portal, camera-texture, probe or save-picture renders.
3. PF-010 `historyEligible` is a future-use classification, not a temporal implementation or permission to reuse one global history allocation.
4. Future temporal features require explicit cross-frame history ownership and invalidation on discontinuities.
5. Exposure/tonemap/bloom policy should follow a documented HDR light-energy contract, not arbitrary effect-specific compensation.
6. Postprocess custom-shader extensibility remains a compatibility surface.
