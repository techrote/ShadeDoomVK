# SDVK-008 — bounded off-GPU POM implementation and qualification

Issue [#8](https://github.com/techrote/ShadeDoomVK/issues/8). Implementation [PR #138](https://github.com/techrote/ShadeDoomVK/pull/138). Starting master `adead010aa40d0f4f8d9ffdb51573005b7f9a964`.

**Status: off-GPU implementation MERGED and PR-head QUALIFIED (9/9 CI, complete software-Vulkan corpus), NOT physical-GPU qualified and NOT full #8 acceptance.** Hardware quality/cost evidence is a hard remaining gate. The nine textual prepass assets were copied without modification from `prepass/sdvk-008-relief@34b7a126249aec98168fc188ab113c374a034f80`; the research ZIP and its SHA-256 remain on the archival branch.

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

## Exact off-GPU implementation result (10 October 2026)

- Initial SDVK-008 PR implementation head `b99cd70dd0e5355d5232a9f5cc848be77b2577c0` passed all nine CI jobs, including native software-Vulkan. After SDVK-010/#137 independently merged, the nine shared files were reconciled with a three-way merge rather than discarding actor probes or weakening relief assertions.
- **Final tested PR #138 head:** `6c0d418e82f34de89084b4175d8aafe0bc024e71`, integrated against accepted SDVK-010 `1b8a6ade684f2d0070dd60dd3dcb3291c34ed6af`. Exact-head renderer source evidence [run 38068791101](https://github.com/techrote/ShadeDoomVK/actions/runs/38068791101) **PASS**. Exact-head full CI [run 38068790984](https://github.com/techrote/ShadeDoomVK/actions/runs/38068790984) **9/9 PASS**: CPU contracts, Windows, macOS, Linux, software Vulkan and paired full-corpus state/image checks.
- **Substantive PR #138 merged** as `master@9536324ce33ea418af5a8efe733b4659f6b4ad9b`; tested/merged tree equality **PASS** (`3123bc7fd3dd9074487cbe3487f9336ef3589003`). Merge-push renderer source evidence [38074510322](https://github.com/techrote/ShadeDoomVK/actions/runs/38074510322) **PASS**. Full post-merge CI [38074510339](https://github.com/techrote/ShadeDoomVK/actions/runs/38074510339) is still pending and cannot be treated as successful until its conclusion is observed.
- **Artifact trace:** PR source `11676456191`, SHA-256 `03e5d208bc8116174f6547f3d975db1bd76538484d505fc217eb460609c42356`; PR native software-Vulkan `11676530794`, SHA-256 `33708094b70bbdab43c3509ca22185d05810e3bec9148ae87bdf0c87b1861089`; PR CPU `11676376390`, SHA-256 `cf41296aad0ad7351669e0e8cea957ce27576f7947664f526f8f43072f4287bd`; post-merge source `11678427062`, SHA-256 `fe4420762f0ae196bbc7121c305725128cbeabc83771cfa1a6ac9cf626ab2fcb`. Digests are of GitHub artifact ZIPs, not physical-GPU traces.
- Historical work: MSVC `FFloatCVar` direct-`std::isfinite` compilation failure fixed by scalar conversion; invalid PF-009 `(ul,ur,vt,vb)` versus relief `(ul,vt,ur,vb)` assertion repaired and independent X/Y flip fixtures added; #137/#138 overlap resolved without deleting either actor probes or relief checks. Earlier canceled superseded CI heads are not presented as passing final-head CI.
- This result proves bounded shader integration and deterministic software-Vulkan draw/state/image behavior under the available corpus, **not** a representative physical-GPU speedup/cost, broad visual usefulness, or final product quality settings. GPU hardware cannot be replaced by llvmpipe or a theoretical 23-sample ceiling.
- **The physical-GPU correctness and cost gate remains OPEN.** GitHub automatically closed #8 on PR #138 merge; #8 was explicitly reopened. No POM release/defaults/physical performance acceptance has been granted. SDVK-012 remains dependency-blocked on full accepted #8.

Read the immutable [machine-readable off-GPU receipt](SDVK-008-OFFGPU-RELEASE-ACCEPTANCE.json) and the separate [preregistered physical campaign](prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md).
