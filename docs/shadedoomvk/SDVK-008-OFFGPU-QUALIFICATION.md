# SDVK-008 — bounded off-GPU POM implementation and qualification

Issue [#8](https://github.com/techrote/ShadeDoomVK/issues/8). Implementation [PR #138](https://github.com/techrote/ShadeDoomVK/pull/138). Starting master `adead010aa40d0f4f8d9ffdb51573005b7f9a964`.

**Status: off-GPU implementation candidate. NOT physical-GPU qualified, NOT full #8 acceptance.** Hardware quality/cost evidence is a hard remaining gate. The nine textual prepass assets were copied without modification from `prepass/sdvk-008-relief@34b7a126249aec98168fc188ab113c374a034f80`; the research ZIP and its SHA-256 remain on the archival branch.

## Source mapping

- `HWSprite::CreateVertices`: obtains the already-accepted SDVK-007 final-quad basis even when material has height but no normal. Publishes conservative relief *candidate* options (depth, quality, signed UV endpoints) only for built-in default/specular/PBR actor cards. Clears state on each draw boundary. No actor, quad, UV or gameplay modification.
- `FRenderState::SetSpriteRelief / ClearSpriteRelief`: two appended vec4 slots after the SDVK-007 T/N fields, compatible with SDVK-005 `uHeightTextureIndex`, existing fixed/custom descriptors, world/model shaders and per-layer sampling.
- `material_relief.glsl::SDVKResolveSpriteReliefUV`: only opt-in, height-present, basis-valid, truecolor, axis-aligned positive-scale TextureMatrix, non-NPOT, built-in material route. Constant-cap shallow POM with one initial read, 8/12/20 steps and 1/2 refinements (10/15/23 maximum height reads). Input V is camera-to-fragment world vector projected onto accepted T/B/N; no second frame, actor or portal flip. Front-facing Z >0.20 with smooth depth fade to 0.32. Depth 0 < S <=0.0200 UV, maximum ray excursion 0.0500 UV, base-gradient-derived LOD 0..4; unsafe transform, rect, footprint, invalid/unknown height, view, angle, excursion, alpha or geometry returns original UV.
- `material.glsl::SetMaterialProps`: uses the *same* final resolved UV for color, normal, PBR/specular/detail/glow/bright layers. Preserves original alpha regardless of RGB offset; if the displaced texel is transparent at inherited alpha cutoff, falls back to the exact original color/UV. Rasterized silhouette, clip/depth, geometry and gameplay never change.
- Read-only `sprite-relief` diagnostic emitted after Vulkan draw, recording material/shader, height descriptor, canonical PF-009 signed UV bounds, context mirror, quality/depth, basis eligibility and the **theoretical per-fragment maximum**. It does not claim actual samples or GPU performance. Validator rejects contradictory/stale/perpetually enabled candidates and improper height/shader identities.

## Controls

`gl_sprite_relief_depth`: archived renderer float, **default 0** (OFF). 0 < depth <=0.0200 is the only enabled range; nonfinite/negative/excessive values disable. This is a dimensionless texture-UV shift, **not** Doom world units.

`gl_sprite_relief_quality`: archived renderer int, default 2, with 0=OFF, 1=low (8+1), 2=medium (12+2), 3=high (20+2). Unknown values disable. A material **must have authored SDVK-005 height** to use either setting. This phase intentionally does not redesign GLDEFS syntax or commit SDVK-016 quality-tier policy. Hardware may reject these provisional settings.

## Qualification boundaries

- The independent prepass Python reference, fixture generator, 11 unit tests and 1,620-case prepass grid are retained, not falsely described as production renderer tests.
- Production source/ABI/emitted-state CPU contracts and adversarial negative controls are in `tools/pf_oracle/tests/test_sdvk008_relief_contract.py`.
- `sprite-mirror` is extended in-place to request explicit relief on the existing SDVRA1 height+normal+specular actor and to demand actual emitted Vulkan height-bearing eligibility, bounded quality, a mirrored context, and heightless PBR/no-map negative controls. The full software-Vulkan suite repeats native captures/state+image comparison; CPU reference and draw-state declarations alone cannot establish visual utility.
- Additional physical quality/cost qualification (including PBR+height, intense grazing, alpha/cutouts, mip/UV subrects, multiple overdrawn cards, temporal motion, measured shader GPU groups and capability fallback) is explicitly **outstanding**. Do not infer GPU throughput from the static 23-read ceiling or llvmpipe.
- Optional height-driven self-occlusion and all sprite shadow casting are deferred pending physically justified cost/quality. No default active visual effect.
- The [prepass physical protocol](prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md) defines eleven OFF/ON timing variants, raw data, independent processes, quality modes, hardware identity, exact software correctness and final no-go gates. This implementation candidate does not modify or silently waive that protocol.

## Evidence and exit condition

Record exact PR-head and post-merge CPU/CI/source/native IDs on this page and issue #8 **after actual completion**. Stop at **OFF_GPU_QUALIFIED; PHYSICAL_COST_PENDING**, keep #8 OPEN, and keep #12 blocked on full accepted #8. Do not claim successful shader compilation, native image comparison, or merged-master verification from the presence of this report alone.
