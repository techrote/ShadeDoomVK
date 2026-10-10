# SDVK-007 — baseline architecture and sprite tangent-space contract (v1)

## Authority / negative baseline

This record was created on the dedicated #7 branch from verified `master@cbff1d10b802e60a56d239338f810f7e1e52920d`, **before production code changes**. The SDVK-005 accepted height/material contract, PF-009 sprite presentation and PF-014 clipping/portal correctness contracts remain authoritative.

In `src/rendering/hwrenderer/scene/hw_sprites.cpp`, actor processing calls `GetSpriteFrame` after choosing the Doom rotation, then publishes `RenderSurface.frameMirrored`, `uvMirrorX` and `uvMirrorY`, selects texture coordinates from `GetSpriteUL/UR/VT/VB`, and records portal parity. `UpdateRenderSurfaceState` runs at queue/creation time and `CalculateVertices` refreshes it just before final vertex generation. `ResolveHWSpriteOrientationPolicy` in `hw_sprite_surface.h` owns the independent XY/face-camera policy and type (face Y, face XY, face-camera, wall, flat, model). Roll, pitch, isometric, face-camera and flat-specific transforms all finish in `CalculateVertices`. `CreateVertices` uploads final quad vertices and their signed U/V endpoints. These are the sole authoritative rendered orientation/texture mapping, not reconstructed game angles.

`HWSprite::DrawSprite` binds `UF_Sprite` through `SetMaterial`; the non-model path calls `state.SetNormal(0,0,0)`, then `CreateVertices`, then the triangle-strip draw. `VkRenderState::ApplySurfaceUniforms` publishes the per-draw material/height uniforms; its submitted draw is observed by `SdvkDiagnostics::VulkanDraw`. The stock `SetMaterialProps` calls `ApplyNormalMap` for normal-mapped materials. The old `material_normalmap.glsl::cotangent_frame` uses derivatives of position/UV and `normalize(vWorldNormal)`. A sprite's explicit zero normal makes that path degenerate; a symmetric normal map cannot prove its direction. Legacy specular and PBR then consume `material.Normal`. The zero-normal+derivative path is the **retained negative baseline**, not accepted orientation evidence.

Non-sprites retain the inherited derivative/material path: world walls, flats, decals, LevelMesh, models, voxels and unrelated geometry own their own vertex-normal/model transformation. The sprite path must not modify their uniforms or geometry.

## One authoritative v1 basis convention

Use the **final PF-009 quad** after every inherited presentation transform. All vectors below are in Vulkan shader world XYZ (Doom world X, vertical Y, Doom world Y), the same space as `pixelpos`; texture axes use the actual signed endpoints, not guessed frame names.

Given final vertex positions `p0` (top-left texture corner), `p1` (top-right), `p2` (bottom-left), and endpoint UVs `(ul,vt)`, `(ur,vt)`, `(ul,vb)`:

- `right = normalize(p1-p0)`; `up = -normalize((p2-p0) - dot(p2-p0,right)*right)`; `forward = normalize(cross(right,up))`.
- `su = sign(ur-ul)`, `sv = sign(vb-vt)`. `tangent = su * right`; `bitangent = -sv * up`, i.e. **increasing texture V points down the card**.
- `handedness = -su*sv`; reconstruct `bitangent = handedness*cross(forward,tangent)`. Therefore `mat3(tangent,bitangent,forward)` transforms authored tangent normals into shader world XYZ.
- Preserve the inherited normal-map unsigned decode and `WITH_NORMALMAP_GREEN_UP` green-channel inversion; no change to colour/alpha/translation/image sampling.
- Doom rotation selection and face/XY/wall/flat/pitch/roll/isometric transforms rotate **the final geometry**. Do not independently reconstruct a yaw/pitch/roll in the shader. Actor/frame mirroring, RF_XFLIP/RF_YFLIP and visual-thinker flips already affect **signed UVs**, hence `su`/`sv`. No second flip is applied.
- Portal/line/plane mirror parity comes from `RenderSurface.portalMirrored` and the PF-010 XOR context. A reflected *view* does not change the world-space card UV mapping or re-flip its tangent; parity is recorded separately. The derived **view parity** can be diagnosed as `handedness * (portalMirrored ? -1 : +1)`; do not multiply the world-space tangent by portal parity a second time.
- For non-model sprite quads, use a bounded per-draw explicit basis. If an axis is nonfinite, tiny/degenerate, nearly collinear or UV span is too small/nonfinite, publish `mode=fallback`, zero explicit enable flag, and use the inherited derivative shader. Do not invent an axis. Keep model and non-sprite modes on their inherited path.
- Represent the basis with two per-surface vectors: `uSpriteTangent = vec4(worldT, handedness)`, `uSpriteNormal = vec4(worldN, explicitMode)`. The fragment shader reconstructs B and selects this frame only for normal-mapped sprite draws. Append these after SDVK-005 height ABI fields; keep all historical fixed/custom bindings and normal-free shader output unchanged.
- Reset per-draw enable before/after sprites so one sprite, portal or view cannot contaminate the next. Diagnostics should bind PF-009 source/rotation/mirrors/UV/mode to the **actually emitted draw's** uniform and shader/material identity; never use diagnostics to decide rendering policy.

## Required counterexamples / proof

A directional normal `(nx, ny, nz)` with unequal nonzero X/Y components is an exact sign and handedness oracle. Test 8 rotation states, single/double frame/actor X and Y flips, face-Y/face-XY/camera/wall/flat, varying yaw/pitch/roll, isolated/nested mirror XOR, signed-UV degeneracy and nonfinite input. Compare map-to-world `T*nx + B*ny + N*nz`, not symmetric screenshots. Retain a deliberately invalid/zero inherited normal baseline. A reversed-UV X fixture must invert X slope, not Y, and combining two flips must restore original parity; portal view mirroring must not double-invert in world space.

Qualify native `sprite-mirror` with actual emitted-draw diagnostics plus material semantic assertions for legacy normal+specular, PBR, height-present (height still unused for relief) and no-normal-map controls. Unqualified modes or unavailable image/physical evidence must be recorded explicitly and **may not** be promoted to acceptance. No POM, shadow or many-light changes.
