# Sprite POM and original-albedo gradient safety (merged correction)

**Source authority:** [PR #191](https://github.com/techrote/ShadeDoomVK/pull/191), merged 13 November 2026 as `e4a3315f8b044fad97b78f627cb7c03a73c33163`. Original head `0e0e513b6bde074743f00cd85b70960da9702f40`. Parent relief programme: [SDVK-008/#8](https://github.com/techrote/ShadeDoomVK/issues/8), **not fully accepted** by this correction.

**Retrieval queries:** POM, parallax occlusion, height maps, sprite relief, image derivatives, textureGrad, dFdx, dFdy, sprite alpha, source art preservation, NPOT.

## What the renderer does

SDVK-008 has an **opt-in** bounded sprite height/relief shader for eligible original sprite cards. The accepted tangent/handedness route and existing per-material height layer support a displacement of **texture lookup**, not vertices, gameplay collision, fragment depth, actual scene geometry or visible source-art resampling. Unsupported materials/camera angles/coordinate domains fall back to original texture lookups. This relief is independent of later projected floor shadows.

At the 13 November correction, the POM code could evaluate implicit albedo derivatives after per-fragment divergent marching; that is undefined/unstable for derivative-dependent sampling on Vulkan.

PR #191 makes the following narrow change:

1. Evaluate the original `material.Base = getTexel(texCoord.st)` and `uvDx=dFdx(texCoord.st)` / `uvDy=dFdy(texCoord.st)` **before** the divergent relief decision, for built-in layered default/specular/PBR shaders.
2. Resolve `SDVKResolveSpriteReliefUV(original, uvDx, uvDy, applied)` with the precomputed gradients, avoiding a second implicit derivative inside the conditional function.
3. If a displaced sample qualifies, fetch it using `textureGrad(tex, relieved, uvDx, uvDy)`, process it through inherited `ProcessBaseTexel` texture-mode handling, replace **RGB only** and keep original alpha.
4. If its alpha fails the existing cutoff, retain original UV/base; no silhouette expansion or new color/translation policy. Unlayered/no-relief routes keep the normal `getTexel` path.

The split between `getTexel` and `ProcessBaseTexel` preserves legacy texture color processing rather than bypassing it in relief mode.

## Source map and protected fallbacks

- `wadsrc/static/shaders/scene/material.glsl` — original sample/gradient capture, branch and alpha-preserving RGB replacement.
- `wadsrc/static/shaders/scene/material_gettexel.glsl` — extracted legacy base-texel manipulation.
- `wadsrc/static/shaders/scene/material_relief.glsl` — coordinate march consumes externally computed derivatives.
- Existing `hw_sprite_tangent.h`, `uHeightTextureIndex`, material semantic mapping and sprite `SurfaceUniforms` govern admission. Height absent is `-1`; this correction does not create any new material channel or PBR pack.
- The `gl_viewmodel_lighting` enhanced HUD path explicitly disables POM/height on weapon cards; do not infer weapon relief from enhanced weapon PBR.

The broader SDVK-008 contract limits depth/view angle, texture rectangle, sampler footprint, shader types, indexed/palette/custom/warped material behavior and mirrored/portal contexts. Refer to [the production contract](../SDVK-008-PRODUCTION-CONTRACT.md) rather than assuming arbitrary content is eligible.

## Qualification boundary

The PR records 93 MSVC-focused CPU/source tests and GLSL→SPIR-V compilation/validation across default, normal/specular, PBR, no-layer and NPOT variants. Its hardware-reference report describes bounded 640×480 source-matched OFF/ON and alpha controls, but explicitly leaves full GPU cost, mirrors/portals and complete #8 acceptance unresolved. A prior stopped physical attempt remains historical failure evidence.

**Do not infer:** all sprite relief variants accepted, authorable height maps in the #190 add-ons, POM active by default, profile-wide performance approval, or elimination of separate driver-risk gates.

Cross-references: [material contract](04-MATERIAL-SHADER-CONTRACT.md), [known traps](10-KNOWN-TRAPS-DORMANT-PATHS.md), [campaign art rules](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md).
