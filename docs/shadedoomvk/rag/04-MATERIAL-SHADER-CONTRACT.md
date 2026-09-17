# Material and shader contract

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active; semantic refactor planned  
Primary issues: PF-003, PF-008, PF-013, SDVK-005, SDVK-007, SDVK-008

## Current material model

Primary source:

- `src/common/textures/gametexture.h`
- `src/common/textures/hw_material.h/.cpp`
- `src/r_data/gldefs.cpp`
- `src/common/rendering/vulkan/textures/vk_hwtexture.cpp`
- `src/common/rendering/vulkan/samplers/vk_samplers.cpp`
- `wadsrc/static/shaders/scene/material*.glsl`
- `wadsrc/static/shaders/scene/lightmodel_*.glsl`

`FMaterial` builds an ordered layer array and chooses a shader model. The baseline supports:

- base/albedo;
- normal + specular legacy material;
- normal + metallic + roughness + ambient occlusion PBR material;
- brightmap;
- detail map;
- glow map;
- custom shader textures;
- palette/indexed paths;
- warped/canvas special paths.

## Important correction

Per-layer sampling is **already inherited**.

`MaterialLayerInfo` includes `MaterialLayerSampling layerFiltering`; `MaterialLayerSampling` includes `Default`, `NearestMipLinear` and `LinearMipLinear`; GLDEFS/custom-shader parsing can assign sampling overrides; Vulkan chooses override samplers per layer.

Therefore PF-008/SDVK-005 must not treat per-layer filtering as absent.

## Current positional coupling

Shader logic still relies materially on known layer ordering/defines. PBR layer presence is all-or-nothing for the normal/metallic/roughness/AO group in `FMaterial` construction. Placeholder textures are inserted for absent bright/detail/glow layers so shader texture units remain valid.

This works but makes future height/emissive/custom expansion vulnerable to positional assumptions and descriptor pressure.

## PF-008 semantic refactor boundary

PF-008 may introduce explicit semantic metadata for **existing** channels while preserving:

- existing GLDEFS/material authoring syntax;
- current layer sampling behavior;
- current palette/translation behavior;
- current shader selection;
- current output for valid existing content.

PF-008 does **not** make height/POM a user-visible feature. SDVK-005 owns first-class height semantics/authoring/default policy after the representation is safe.

## Sampling/color-space direction

Later semantic defaults should distinguish at least:

- albedo/base: color data, user/pixel-art filtering policy;
- normal: vector data, never interpreted as sRGB color;
- height: scalar linear data;
- roughness/metallic/AO: scalar linear data;
- emissive/brightmap: explicit emission semantics;
- detail/custom: declared semantics or preserved custom behavior.

Do not force every map through albedo filtering/mipmap/color-space behavior.

## Normal mapping baseline

`material_normalmap.glsl` derives a cotangent frame from screen-space derivatives (`dFdx`/`dFdy`) and UV derivatives. This is generic and useful for world geometry but does not define a stable Doom sprite-local handedness contract across mirrored rotation frames.

PF-009 extracts sprite orientation metadata without changing the current normal algorithm. SDVK-007 later implements/validates the explicit sprite tangent basis.

## PBR baseline

`lightmodel_pbr.glsl` implements GGX distribution, Smith geometry, Schlick Fresnel, metallic/roughness/AO, local lights, sunlight and irradiance/prefiltered environment probes.

Compatibility constants such as `PBRBrightnessScale` and ambient-sector-light approximations are part of current visual behavior. PF-011 centralizes/documents those bridges before later policy changes.

PF-013 owns numerical safety at the roughness-zero edge while preserving normal settings.

## Descriptor interaction

`VkMaterial::GetDescriptorEntry` caches bindless ranges keyed by material state such as clamp mode, translation/palette and global shader. Richer materials consume contiguous bindless slots. PF-003/PF-017 harden lifetime and lookup behavior before SDVK height layers increase pressure.

## Invariants

1. Existing content material meaning/output must not change during PF semantic tagging except for explicit PF-013 bugfix cases.
2. Semantic metadata may not become a second contradictory source of layer order truth.
3. Optional/default layers must not create stale bindless references.
4. Indexed/palette/translation behavior is compatibility-sensitive.
5. Sprite mirror/rotation correctness is not proven by a front-facing normal-map image.
