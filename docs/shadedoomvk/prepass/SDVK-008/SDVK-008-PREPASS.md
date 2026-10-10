# SDVK-008 — bounded height/POM sprite relief: **preparatory checkpoint**

**Status: research and standalone CPU oracle only. NOT SDVK-008 implementation, acceptance, GPU qualification or release.** Date: 2026-10-10. Owner: [#8](https://github.com/techrote/ShadeDoomVK/issues/8). Starting authority: `master@cbff1d10b802e60a56d239338f810f7e1e52920d` (tree `cfc567883e299dd555e1010ce547f3fc0fae5970`). This checkpoint may be reviewed without a production PR and must not be merged/used as evidence of #8 completion.

## 1. Live reconciliation and scope boundary

At prepass inspection, #8 is open and has no comments. SDVK-005/#5 is accepted/merged/verified through #132 and acceptance #134 on the stated master; height is semantic index 10, linear normalized **red** scalar, optional `uHeightTextureIndex == -1` when absent. `HasMaterialHeightMap()`/`SampleMaterialHeight(tc)` exist in `wadsrc/static/shaders/scene/material.glsl`; **stock `SetMaterialProps` does not sample height**. Per-layer sampling is inherited/extended and may differ from nearest albedo; height default is linear min/mag + linear-mipmap, repeat. Indexed/paletted routes omit height. Existing custom descriptor slots must never move.

SDVK-007/#7 and [PR #135](https://github.com/techrote/ShadeDoomVK/pull/135) were **open and unmerged** at read time. Their draft defines a final-quad/signed-UV world-space sprite TBN and fallback. Draft source includes `hw_sprite_tangent.h`, sprite-only surface uniforms, selected `ApplyNormalMap` basis and emitted `sprite-basis` diagnostics. These are *investigative inputs*, not a dependency acceptance or fixed ABI. #8 and #10 still require **accepted #7**. #9's nonphysical preparation and `SDVK-009-GPU-QUALIFICATION-PROTOCOL.md` are present; #9 still needs a finite hardware campaign. This checkpoint changes **no** production shader, uniforms, descriptors, sprite orientation, material authoring, defaults, corpus, CVar, CI or issue status.

Canonical evidence reviewed: `AGENTS.md`, issue #8 and `issues/SDVK-008.md`; SDVK-005 final acceptance/material-height/JSON receipt; open PR #135 diff and `issues/SDVK-007.md`; PF-009 sprite-surface contract, PF-014 issue/acceptance, PF-010 view identity; material, portal and observability RAG; SDVK-002 observer and `tools/renderer_oracle/{README.md,run.py,corpus.json}`; validation/performance contract; #9 physical protocol/driver; material/normal/vertex/fragment shaders, `getTexel`, source uniform and sprite surface; donor register. No exact upstream POM source was copied or imported. General algorithm comparisons use independently expressed textbook mathematics; see references below.

## 2. Minimum **semantic** interface from accepted #7

#8 needs no particular struct, interpolator, C++ uniform field or PR #135 choice. It **does** need, at the fragment for the actual emitted sprite draw:

| Semantic obligation | Why needed / validation |
| --- | --- |
| Sprite-card eligibility and trustworthy basis vs legacy/degenerate fallback | Never enable relief on unknown/derivative-only/non-sprite geometry. Required for height-only sprites too, **not only NORMALMAP builds**. |
| Orthonormal **T** along increasing authored material **U** | Defines horizontal ray direction and X-mirror response. |
| Orthonormal **B** along increasing authored material **V**, or reconstructable from N and parity | Defines vertical ray and Y-flip response; UV +V may point down. |
| World-space plane **N** and parity/handedness ±1 | `B = parity * cross(N,T)` (provided #7 accepts that handedness convention); matches normal-map/PBR lighting. |
| Camera-to-fragment/view vector in same shader world/portal space | Enables `V_ts`; do not confuse Doom gameplay XYZ with Vulkan shader world XYZ. |
| Actual final texture-coordinate orientation/UV mapping and authored sprite subrect | Uses signed UV endpoints, `TextureMatrix`, per-material NPOT transformation if active; prevents wrong atlas/translation addressing. |
| Frame/actor flip and **separate** PF-010 line/plane/portal view parity as observable metadata | Verify no double flipping; reflection of a *view* is not a second UV flip. |
| Same material identity and height-present semantic from #5 | Selects exact no-height route and only its optional height descriptor, no new identity domain. |

**Possible representations**: world T/B/N vectors; world T/N + parity; a pre-normalized fragment-space 3×3 with parity metadata; or a proven equivalent post-#7 adapter. **Not required**: `uSpriteTangent/uSpriteNormal` names/layout, specific vertex order, quaternion/Euler angles, actor yaw, PR #135's v1 `su`/`sv` arithmetic, a new interpolator, gameplay state or a temporal cache. The source of truth remains #7's **accepted final rendered** presentation and mapping. If it offers an explicit basis only for normal-mapped sprites, height-only sprite eligibility is an unresolved integration gap: fall back until the accepted semantic service is exposed.

**Post-merge compatibility checklist** (all must PASS before any production patch): accepted #7 final commit/tree and receipt; basis valid for height-only normal-free cards; T/B/N orthonormal and right mirror parity on face/Y, XY, camera, wall, flat, roll/pitch; Doom eight rotations and both UV flips; line/plane/portal mirroring without second parity multiply; backface treatment; matching world camera/fragment positions and texture space; reliable enable/fallback bit on the *submitted draw*; derivative legacy/model/world routes untouched; normal green-channel convention and PBR response unchanged; accepted no-map pixel/state equivalence. PR #135's current proposed representation is specifically **not** hard-coded by this prepass.

## 3. Candidate algorithms and selected provisional method

| Candidate | Approx. height reads / fragment | Branch/derivative/mirror issues | Holes, alpha, pixels, cost/maintenance |
| --- | --- | --- | --- |
| Single offset / basic parallax | 1 | One displacement, division by `V_z`; simple fixed control | Cannot find first visible feature, reveals holes, low cost; useful cheap alternative if POM rejected. |
| Steep fixed-layer parallax | ≤1+N | One finite conditional traversal; stable inherited gradients possible | Layer quantization; thin-feature skipping; pixel-art stepping; bounded moderate cost. |
| **Fixed shallow POM + secant intersection** | **≤1+N+R** | Same bounded traversal + 1 interpolation + optional R=1–2 midpoint reads; original-UV gradients; signed T/B inherited | Less quantization at small N; still misses narrow peaks, abrupt alpha edges, no true depth; lowest credible high-quality candidate. **Selected.** |
| View-adaptive layer count | 1+N(angle)+R, hard cap mandatory | Divergent dynamic layer count and quality transition; view angle changes temporal sampling frequency | May help cost but adds flicker/branch complexity; defer unless hardware warrants. |
| Relief/binary-search heavy | N+R, possibly much larger | More iterations/refinement; derivatives should remain original-UV based | Better intersections at cost, still cannot guarantee all thin features; unnecessary for shallow sprite cards. |
| Cone / relaxed-cone stepping | variable, bounded only with cap; extra precomputed cone data | Extra authored channel/preprocessing/sampler policy, continuity/discontinuity complications | Cone overshoot/gaps or conservative early stop; conflicts with smallest semantic-only change; **reject for first version**. |
| Self-occlusion/light-ray march | extra `N_light` × applicable light sources | Additional lighting-space basis, branch divergence, many-light multiplier | Can create misleading card self-shadow and big cost; **not part of provisional algorithm**; separable later after stable measures. |

All variants depend on positive/finite view-normal component and semantic TBN; no algorithm fixes actual sprite silhouette, gameplay geometry or alpha cutout automatically. Fixed-layer POM can use either mip-filtered scalar height or author-nearest data; sample *height independently* from albedo. Implicit `texture()` derivative evaluation inside nonuniform traversal is not assumed safe: compute base UV gradients **before** control flow and use `textureGrad` or explicit clamped LOD. The CPU oracle uses explicit bilinear repeat sampling, average-generated mip levels and `lod∈[0,4]`; renderer sampling/derivative agreement is a future qualification item. `lod=0` in the grid is not a physical shader footprint claim.

For pixel-art, do **not** filter albedo merely because height is filtered; scan finite height strata, then sample base/normal/PBR at the **same single resolved UV** with their respective accepted samplers. No new feature should intentionally quantize `V_ts` or animate the steps across frames. Screen-space view changes may still cause unavoidable spatial/temporal aliasing near a step or alpha cutout; reject problematic cases or keep the depth opt-in.

## 4. Mathematical coordinate and depth contract

Let `P` be the actual fragment point, `C` the current portal/view-space camera in the **same world-space shader convention**, and #7's accepted unit `T`, `B`, `N` describing increasing final material U, increasing V and card forward. If the accepted basis is `T,N,s`, obtain `B = s·cross(N,T)`; never infer `s` from portal parity alone. Define

```
W = normalize(C - P)                    # fragment -> viewer
V = normalize( dot(W,T), dot(W,B), dot(W,N) )
V.z must be > 0.20; back-facing, degenerate and edge-on -> base UV
ray = effectiveHeightScale * V.xy / V.z
q(d) = uv_original - d * ray           # d in [0,1] into card
F(d) = d + height_red_linear(q(d)) - 1
find the FIRST bracket F(d_previous) < 0 <= F(d_current)
refine bracket with R fixed bisections; secant interpolate bounded d*
uv_resolved = uv_original - d* * ray
```

`height=1` = top/reference plane (`d*=0`, original UV); `height=0` = bottom (`d*=1`, maximum apparent inward excursion); `height=0.5` = mid-slab; scale zero or absent height -> original UV unchanged. This is a **recessed surface under the rasterized sprite plane**, not vertex push-out, depth-buffer modification, intersection with Doom geometry or collision movement. `-ray` is deliberate: along a view-to-camera vector in local +U/+V, a deeper apparent point lies opposite that direction. Positive U/V mirror orientation is already embedded in #7's texture axes: flipping the frame negates the corresponding tangent component and hence the view component; do not also negate UV/ray in the shader. Rotation/roll/pitch alter the accepted final world T/B/N. Recursive portal camera/view transforms affect `W` in their owning context; the world-space TBN is not reflected *again* solely because the view is mirrored. `viewParity` is only a diagnostic unless final accepted #7 explicitly proves a different semantic convention.

Potential handedness example from the **unaccepted** #135 draft: signed `du=ur-ul`, `dv=vb-vt` and `B=(-sign(dv))*up` with `T=sign(du)*right` imply `s=-sign(du)·sign(dv)`. This is an illustration for review, **not** a required producer representation. Reject an implementation that derives UV frame orientation a second time from actor angles.

Height scale is dimensionless **texture UV displacement**, not physical world height; non-square sprites/texture matrices can make equal U/V scale visually anisotropic. Before production, confirm the actual material texture-coordinate domain, frame subrect, aspect ratio, NPOT and `TextureMatrix` transforms and decide whether a documented material aspect correction is necessary. Unproven modes take exact no-relief fallback; do not alter #5 height semantics.

## 5. Hard bounds, failure table and work policies

| Bound or policy | Research v1 proposal |
| --- | --- |
| Authored scalar depth | positive finite `0 < S ≤ 0.0200` UV units; zero = exact fallback; negative/nonfinite/>limit = explicit no-relief (`NEGATIVE_SCALE`, `INVALID_SCALE`, `SCALE_LIMIT`), never silent huge traversal |
| Grazing | `V.z ≤ 0.20` exact fallback (includes backface); smoothstep depth fade to full scale over `V.z=0.20..0.32`; zero/invalid view/basis fallback |
| Projected card size (optional when available) | `≤16 px` exact fallback; `16..32 px` smooth fade to full; 32+ unmodified. This is a *projected size* criterion, not an ungrounded universal Doom-world distance. |
| Ray excursion | Euclidean `||ray|| ≤ 0.0500` UV, enforced by rescaling effective depth **before** traversal; retain `scale_capped` diagnostic; actual sampled excursion and final UV ≤ same |
| Fixed work | OFF 0; LOW 8 traversal +1 refinement (**≤10** height reads); MEDIUM 12+2 (**≤15**); HIGH 20+2 (**≤23**) including one initial height read. Max 20 traversal, max 2 refinement, no unbounded loop. |
| Derivative/mip policy | original-UV gradients outside divergent control; derived LOD clamped to `[0,4]` and actual texture mip count. Invalid gradients/LOD -> fallback or explicitly validated LOD0 safe mode; do not repurpose albedo sampler. |
| Allowed rect | closed authored sprite UV rectangle (local 0..1 in host); **no repeat wrapping across frame for relief rays** even though the #5 height texture sampler has repeat addressing. Any path sample outside valid rect or final UV outside -> original UV, no clamp-smear. |
| Alpha | effective original alpha/cutout must already qualify; resolved UV must still qualify and stay in rect; else revert to original, never discard/add sprite silhouette because of relief. See §6. |
| Height validity | missing/index −1 -> zero work and original UV; scalar channel normalized red linear. Host validates finite `[0,1]` arrays; future shader checks each sampled value, while normalized UNORM source/GLDEFS failures are owned by #5. Invalid sampled value -> base fallback, not NaN. |

**Failure/equivalence matrix:** `NaN/Inf` in UV -> finite safe sentinel and `INVALID_UV` (outside ordinary valid-UV equivalence); `NaN/Inf` view/scale/LOD -> explicit anomaly fallback with unchanged **finite** original UV; zero-length view, collinear basis, unsupported/legacy mode, nonpositive depth, too-large depth, grazing, too-small size -> exact original UV and zero height samples; 1×1 and constant 0/0.5/1 use the same bounded intersection and no special authoring; binary/step edges may alias or miss thin peaks and require visual acceptance/fallback. A texture with a missing/invalid channel is not given a fabricated usable descriptor. No unknown `uHeightTextureIndex` or stale descriptor is sampled.

The reference checks rect before every height read; shader integration must also ensure a bilinear/mipmap footprint doesn't leak into adjacent **atlas subrects** despite center-UV rect validation. If atlas padding/valid bounds cannot be established, disable relief for that mode. The host's linear-repeat PNM oracle does **not** assert renderer atlas safety.

## 6. Alpha, holes and silhouette invariants

POM changes **only shading lookup coordinates for existing rasterized fragments**. It must never add pixels outside the actual rasterized quad, alter emitted vertices, write pseudo-depth to `gl_FragDepth`, move collision, apply fragment discards that remove previously valid silhouette pixels, or fill original transparent cutout holes.

- Original alpha-transparent/cutout fragment: no relief eligibility; keep inherited alpha/discard behavior.
- Original visible but displaced UV enters alpha-transparent cutout: **fallback original UV for all material channels**, keeping the original visible fragment (do not create an unexpected hole).
- Displaced ray leaves authored frame: fallback original, not repeated height from neighboring frame, not clamped artificial stripe.
- Thin 1–2-texel features/checker height may produce aliasing; retain baseline at rejected edges, not geometry-level guarantees.
- Frame/U/V mirroring: base and candidate alpha tests use the same final UV mapping and same effective sampled alpha semantics, with no double flip.
- Nearest albedo + filtered height: alpha uses the actual inherited base-layer alpha/cutout rule; height can remain linear. A host nearest-mask check is only a controlled surrogate.
- For texture manipulation, blend styles, translation/palette, alpha textures, NPOT/warp/translucent routing where an **effective alpha** pretest identical to inherited `getTexel`, `TM_*`, `DO_ALPHATEST` and postprocessing cannot be established, **disable relief** rather than inventing new alpha/visibility semantics. A shader branch that merely samples `tex.a` but ignores `getTexel` transformations is insufficient.

Even with bounded UV, strict output silhouette conservation may expose visible edge color popping and apparent interior cutout discontinuity under camera movement. Those require targeted native witnesses; they are not solved by this prepass.

## 7. Standalone host prototype, deterministic assets, results

Retained preparatory tools (not engine locations):

- `tools/prepass/sdvk008/reference.py` — independent normalized view, ray-capped fixed-layer POM, optional bisection, scalar/mip sampling, alpha edge gates, explicit fallback reason and result counters. The result exposes resolved UV, height reads, alpha reads, steps taken, refinement, requested work, achieved excursion, computed effective scale, cap flag, selected LOD, intersection depth, anomaly and applied state.
- `tools/prepass/sdvk008/fixtures.py` — pure deterministic P2/P3 ASCII PNM asset generator with SHA-256 manifest: smooth ramp, radial mound, asymmetric wedge, stepped, checker, one-pixel-high ridge, constants 0/0.5/1, directional asymmetric albedo/normal, alpha with transparent borders and hole/thin arm, PBR metallic/roughness/AO; deliberate missing/bad data are negative *non-image* vectors.
- `tools/prepass/sdvk008/test_reference.py` — standard-library unit oracle + reproducible 1,620-case parameter grid over 9 heights × 5 views × 4 independent U/V orientation signs × 3 source UVs × 3 fixed step policies; included mirror-involution, cutout/hole, out-of-rect, constant depth, degenerate, NaN/Inf and mip/adaptive-size negatives.
- `SDVK-008-PREPASS-RESULTS.json` — deterministic grid digest/aggregates and concrete anchor vectors. Assets are generator-owned, not a new production corpus scene; `SDVK-008-FIXTURE-MANIFEST.json` pins generated bytes for subsequent packaging. Generated PNM can be recreated and verified against manifest.

Reproduction from repository root, with **no GPU** and only Python 3.10+ standard library:

```
python3 -m unittest discover -s tools/prepass/sdvk008 -p test_reference.py -v
python3 tools/prepass/sdvk008/test_reference.py --receipt /tmp/sdvk008-grid.json
python3 tools/prepass/sdvk008/fixtures.py --out /tmp/sdvk008-new-pnm --size 32
```

Local executed result on 2026-10-10: **11/11 unittest PASS**; **1,620/1,620 grid valid**, **0 detected numerical anomalies**, max **23** height samples, max allowed `0.05` excursion, 552 resolved/1,068 explicitly unshifted (`FRONT_ON` 324, `GRAZING_OR_BACKFACE` 648, `TOP_PLANE` 96). Grid SHA-256 `c9d64aab54740ad8376bdbbda579d5dc904da8d808833f2df30f8622f14b85d4`. These observations prove the *host algorithm's tested bounds*, not shader correctness, image quality, actual Vulkan sampling, visual temporal stability, latency, GPU fragment invocation counts or device performance. The failure initially found in test setup (incorrect expected rectangular escape at UV 0.23) was fixed by selecting UV 0.215 inside the same rect; no algorithm change was required. Archive this as test-design correction rather than a runtime defect.

## 8. Required later native correctness oracle and diagnostics

Extend accepted `sprite-mirror` scene plus PF fixtures, preserving existing package/hash/IWAD authority. Matrix: front, 30–60° oblique, >78° grazing, forward/backface (if mode permits), translating and pitching camera; eight Doom rotations, signed frame U/V, RF_XFLIP/YFLIP, wall/flat/face-Y/XY/camera; roll/pitch; line/plane mirror and portal recursion; albedo-only/height-only/normal+PBR+height, nearest albedo+linear-height, 1×1 and binary height, cutout holes/thin features/missing or malformed height; moving directional light for normal/PBR response. Pair asymmetric normal maps to detect swapped axes: flat blue normals are insufficient. Some modes may need additional dedicated native scenes; don't claim coverage until actual emitted draw and image witness exist.

**Proposed per-emitted-draw schema:** `SDVK-008-DIAGNOSTICS-DRAFT.schema.json` (not installed into runtime). Fields: exact context epoch/pass, material/semantic shader/index identity, sprite mode and accepted-vs-fallback basis source, frame/UV flips, independent portal mirror parity, algorithm/version/enabled, authored/effective scale, selected 8/12/20 bound, maximum 1/2 refinement, maximum <=23 height reads, observed work only where a genuinely instrumented shader counter exists, UV excursion, alpha/grazing/distance/cap/failure reason, unchanged geometry identity. Default observer is off. Timing runs **must not** introduce atomic per-fragment work counters. If actual samples are unavailable, say so and record only upper bound—not a fabricated actual count.

**Validator invariants:** all emitted numeric fields finite and within bounds; `actualHeightSamples ≤ 1+N+R ≤23` where genuinely measured; no-height/-1 semantic exactly disables and does no relief work; unsupported basis or grazing -> original UV; output UV stays within rect and cap; alpha/cutout identity and visibility match original; mirror changes don't alter parity twice; identical sprite/source/material identity across matched runs; renderer draw/actor/gameplay/position/collision/tic state invariant; selected normal+PBR responses use the *same final UV* and accepted basis; no new descriptor slot or stale generation; timing and state observation modes remain separate. A captured shader *work upper bound* does not establish per-fragment sample count.

## 9. Future production integration seams — **not applied**

1. After #7 acceptance, adapt a **semantic sprite-basis accessor** at the existing `HWSprite::CreateVertices`/`FRenderState` submitted-draw data path; do not modify the producer during open #135. Gate on valid card basis; no generic world/model route.
2. Preserve #5's optional `uHeightTextureIndex`/`SampleMaterialHeight` red-linear mapping and the existing descriptor span; never renumber custom indices or use the missing-height return value as a presence test.
3. Add opt-in, separately named relief settings and a bounded `ResolveSpriteReliefCoord(originalUV)` seam in a future #8 production PR. Establish original UV/gradient **before** NPOT and derivative modifications, and apply a single validated `resolvedUV` coherently to base, normal, legacy specular and metallic/roughness/AO, while guarding texture modes. Do not change inherited no-height `SetMaterialProps` evaluation when disabled.
4. Preserve `ApplyNormalMap`'s accepted #7 TBN and `WITH_NORMALMAP_GREEN_UP` behavior; POM chooses lookup coordinates, **not** a second tangent definition. Existing light, shadow and PBR selection remain intact. Defer self-occlusion and depth buffer modification.
5. Instrument state/emitted draws read-only via SDVK-002 and PF-010 identity, with future schema + validators and native witnesses. Add a shader diagnostic mode only with separate cost attribution; no heavy counters in performance captures.
6. Add shader/CPU source contracts, generated corpus package and exact native software-Vulkan pair comparisons; separately run physical packet. Only then undertake issue acceptance/merge/RAG/ledger reconciliation according to `AGENTS.md`.

## 10. No-height/legacy equivalence preregistration

The strongest future design is a shader specialization/compile-time branch that contains **zero relief operations** when height absent/feature off; otherwise a conditional early path must prove `uv_resolved == uv_original` bit-for-bit and zero height texture reads, with compiler/output evidence. For each accepted sprite mode compare baseline state and **same-device exact RGB** image, fixed camera and package on identical accepted source/build settings except the opt-in: (a) no-height material, (b) legacy sprite without normal mapping, (c) authored height but toggle OFF, (d) authored height scale zero, (e) unsupported basis, (f) grazing. Record actual semantic height index and no extra descriptor, unchanged draw/state/simulation, and zero relief work. Do **not** substitute two identical post-change captures for a true OFF-vs-ON-disabled comparison. Historical-master-vs-current-master pixel equivalence was not itself proven by #5; do not inherit such a claim.

## 11. Physical performance hypotheses and preregistered packet

The provisional work ladder is **OFF 0**; **LOW ≤10 height samples**; **MEDIUM ≤15**; **HIGH ≤23**, independent of user-facing SDVK-016 tiers. These are upper bounds, not constant shader requests or actual cost. Hypotheses for real GPU only: worst fragment cost rises with affected screen coverage and overdraw, step count, height frequency/texel cache locality, oblique rays, number of simultaneous sprites, mip/texture filtering and whether normal/PBR material fetches are on. Angular/distance fallbacks may *reduce* work near grazing; branch divergence can make a scene slower despite smaller average sampled height. Pixel-art albedo and filtered height must be qualified independently. CPU/software Vulkan never substitutes for these measurements.

See **[SDVK-008-PHYSICAL-GPU-PROTOCOL.md](SDVK-008-PHYSICAL-GPU-PROTOCOL.md)** for the future 640×480 dual state/image gate, **1904×1001** actual hardware timings, 120 warmup +120 retained frames per fresh process, three independent serial process repetitions, counterbalanced 11-variant schedule, primary paired OFF comparisons, raw-group/MAD variability rules, build/device/cache IDs and abort conditions. One GTX 1650 SUPER-class physical device is sufficient for the initial representative gate; Quadro RTX 4000 and TITAN RTX are optional separate strata. Batch logistics with #9 are allowed, but #9's current exact *different* source pin cannot be silently treated as the same build. The two issues retain separate correctness and acceptance decisions.

## 12. Open questions and exact post-#7 handoff

**Blocking inputs after #7 merges (recheck live authority):** final accepted commit/tree, exact TBN handedness sign (esp. flat/backface/portal), height-only card basis availability, valid/unsupported mode matrix, normal-map green parity and observed mirror/roll/pitch state; actual material UV transform and authored sprite rect/atlas padding; valid alpha/NPOT/palette/translucent route policy; source of portal-local world camera vector; shader gradient lifetime for `textureGrad`; output resolution at which 0.02 UV/0.05 excursion is useful; whether `16–32 px` fade prevents popping; if the physical GPU has reliable named GPU timestamps for shader cost.

**Next implementer procedure:** Reconcile accepted SDVK-007 release receipt, rerun interface checklist §2 on final source/actual shader diagnostics, evaluate gradients and alpha semantics against inherited `getTexel`, rerun this CPU test suite and fixtures unmodified (or version contract with explicit diffs), translate the bounded ray equations with semantically equivalent sample/rect/fallback accounting, add opt-in production integration **only after** dependencies and exclusions are proved, extend `sprite-mirror`/native observer and validate exact no-height equivalence, then follow the *unexecuted* physical-GPU packet. If final #7 cannot supply one required semantic, keep that mode relief-disabled and record the blocker; do not backfill #7 by guessing PR #135's layout.

## Reference/provenance locators

- [SDVK-005 final acceptance](../../SDVK-005-FINAL-ACCEPTANCE.md), [height contract](../../SDVK-005-MATERIAL-HEIGHT.md), [release receipt](../../SDVK-005-RELEASE-ACCEPTANCE.json); [PF-009 sprite surfaces](../../PF-009-SPRITE-SURFACE-CONTRACT.md), [PF-010 render context](../../PF-010-RENDER-CONTEXT-CONTRACT.md), [PF-014 acceptance issue](../../issues/PF-014.md).
- [Material/shader RAG](../../rag/04-MATERIAL-SHADER-CONTRACT.md), [portal coordinate RAG](../../rag/07-PORTAL-COORDINATE-SPACES.md), [observability RAG](../../rag/11-RENDERER-OBSERVABILITY.md), [SDVK-002 observer](../../SDVK-002-OBSERVABILITY.md), [programme validation](../../06-VALIDATION-PERFORMANCE-CONTRACT.md), [#9 GPU protocol](../../SDVK-009-GPU-QUALIFICATION-PROTOCOL.md).
- [LearnOpenGL — Parallax Mapping](https://learnopengl.com/Advanced-Lighting/Parallax-Mapping) (steep-layer vs linear-bracket POM and known edge artifacts); [Tatarchuk, *Dynamic parallax occlusion mapping with approximate soft shadows* (I3D 2006)](https://doi.org/10.1145/1111411.1111423) (adaptive height sampling/soft-shadow research); [GPU Gems 3 ch. 18, *Relaxed Cone Stepping for Relief Mapping*](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-18-relaxed-cone-stepping-relief-mapping) (cone precomputation/alias trade-offs). **No source code was copied.** The prepass reference implementation is independently written and the repo donor register has no new imported contributor.
