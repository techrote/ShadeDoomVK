# SDVK-008 — production integration contract (bounded off-GPU phase)

Status: implementation candidate, **not accepted** until physical GPU performance campaign.
Starting master: `adead010aa40d0f4f8d9ffdb51573005b7f9a964` (accepted SDVK-007, post-merge 9/9 CI and full software-Vulkan corpus).
Source research: `prepass/sdvk-008-relief@34b7a126249aec98168fc188ab113c374a034f80`; 9 textual research/oracle files were copied without changing their contents. Original ZIP/checksum retained on prepass branch, not rebuilt.

## Current source audit before production change

- `HWSprite::DrawSprite` binds `UF_Sprite`, sets material shader/translation, then `CreateVertices` receives final PF-009 quad and signed UV endpoints.
- `ResolveHWSpriteTangentBasis` from accepted #7 computes world T,N,handedness even for **height-only** sprite cards with no normal map. This resolves the research prepass integration question. It has a clear enable/fallback selector in `uSpriteNormal.w`.
- `VkRenderState::ApplySurfaceUniforms` publishes the actual `uHeightTextureIndex` from SDVK-005 at draw emission. Missing height is exactly `-1`; stock `material.glsl` does not yet sample height.
- `vTexCoord` receives `TextureMatrix * vec4(quadUV,0,1)` in `vert_main.glsl`. An optional NPOT emulation transform is applied in `SetMaterialProps`. Therefore POM bounds must be proven in the **post-TextureMatrix** domain. Only finite axis-aligned positive-scale texture matrices can use the bound conversion without another TBN reorientation. NPOT emulation, warped material coordinates, palette/translation-indexed routes and unsupported custom shaders must keep the original texel path.
- `uCameraPos` and `pixelpos.xyz` share the PF-010 world/portal renderer space, also used by PBR/specular. The camera-to-fragment vector projected onto #7's T,B,N is the only relief view derivation. Do not apply line/portal parity again.
- The material/normal/PBR/alpha layers consume the one resolved coordinate in `SetMaterialProps`; stock height is **red linear scalar** from its own existing semantic sampler. Do not duplicate or renumber descriptors.

## Provisional bounded shader behavior

Only opt-in height-bearing sprite materials with a valid explicit final-quad basis, known built-in default/specular/PBR shader, compatible truecolor texture mode, valid frame UV rectangle and nonzero finite depth enter relief. Controls are renderer CVars (default OFF) with separate low/medium/high traversal caps; height is still an authored **per-material** channel. There is no new GLDEFS syntax or material ABI redesign in this phase.

Selected fixed-layer shallow POM (prepass reference): view tangent projection `V=(dot(C-P,T),dot(C-P,B),dot(C-P,N))`; require finite normalized front-facing `V.z>0.20`; depth fade 0.20..0.32; ray `scale * V.xy / V.z`; cap length to 0.05 UV; traverse from 0 to 1 with fixed 8+1 / 12+2 / 20+2 refinement and initial sample; total <=23 height reads. Height 1 intersects front plane and height 0 back plane. All sample candidates and resolved UV must be safely within the authored transformed sprite rectangle including a texture/filter footprint guard. Height uses its semantic red channel and explicit LOD sampled through its own existing layer index; albedo uses inherited filter policy. No alpha channel may open new silhouette pixels: preserve the original texel alpha and revert the colour/normal/material coordinate if resolved alpha fails the original cutoff. No fragment-depth, vertex, gameplay, collision, world shadow or sprite geometry changes.

The C++ per-draw options and texture bounds are append-only `SurfaceUniforms` fields, cleared each sprite/draw; there is no global mutable per-sprite cache. Diagnostic state is read-only and emitted on actual Vulkan sprite draws, identifying candidate/material/height/basis/quality/rect, and differentiating a **theoretical shader sample ceiling** from unmeasured actual fragment invocations. Negative state validation rejects out-of-contract settings, missing basis/height and stale options.

## Qualification and hardware boundary

- Preserve independent unmodified reference/oracle fixtures from the prepass; add C++ state/ABI and GLSL/source fixtures, and native renderer state/images that visibly exercise ON and disabled heightless controls.
- Run all Python/correctness oracles, repository `tools/check.py`, CI and complete software-Vulkan image/state corpus at exact PR head. Report any retained failures and repairs; never use CPU timing as GPU cost evidence.
- Physical measurements are **not** requested now: leave issue #8 open, with cost/variant sweep defined in `prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md`, including raw samples/identity/ON-OFF comparisons on real hardware. SDVK-012 remains dependent on fully accepted #8.
- Source is independently authored using the prepass mathematical reference. No external donor code incorporated; no donor register update required.
