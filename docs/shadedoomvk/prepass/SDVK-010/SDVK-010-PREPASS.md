# SDVK-010 — actor probe/environment lighting preparatory prepass

**Status:** research/fixture-design checkpoint only; **NOT SDVK-010 implementation or acceptance**.  
**Assessed live master (reconciled mid-prepass):** `08ec183e665e7a3100b6cf3a267f5d3b5b494990` (10 October 2026). **Prior fully verified acceptance base:** `cbff1d10b802e60a56d239338f810f7e1e52920d`. The new master contains #135's merge; #7 remains OPEN and its final acceptance/post-merge verification are not yet established here.  
**Issue:** [#10](https://github.com/techrote/ShadeDoomVK/issues/10), open; no comments at inspection.  
**Blocking acceptance gate:** [PR #135 / SDVK-007](https://github.com/techrote/ShadeDoomVK/pull/135) **MERGED** as `08ec183e665e7a3100b6cf3a267f5d3b5b494990` (former head `a895dca0a5f356440f79f0631289d2862afe86f3`), but [issue #7](https://github.com/techrote/ShadeDoomVK/issues/7) remains **OPEN**. Merged source is live interface, **not yet verified final accepted #7**; no #10 implementation is authorized in this prepass.  
**Accepted authorities:** PF-002/003/004/009/010/012/014, PF-113 missing IBL, SDVK-002 and SDVK-005. SDVK-009 physical campaign remains outside scope.  
**Production changes:** none. This checkpoint must not be merged as SDVK-010 implementation or close #10.

## Contents

1. Authority and evidence grading — distinguishes proven PF/production behavior from hypotheses.
2. Producer-to-consumer execution map — authored targets, dynamic descriptor pairs, probe-map texels and reset.
3. Render-path partition — walls/flats, sprites/models, HUD, particles and sunlight paths.
4. Spatial/portal transition table — exactly what is and is not currently guaranteed.
5. SDVK-007 orientation handoff — semantic world-space inputs without choosing #7's representation.
6. Irradiance/PBR/sun audit — equations, constants and shader samples; no recalibration.
7. Qualification corpus — planned deterministic inputs, assertions and blocking oracle questions.
8. Lifetime/diagnostics/validator contracts — reuse existing PF identities; never observe by mutating.
9. Correctness versus aesthetics — defects #10 owns and decisions it must not invent.
10. Integration/conflict map — #135 exact overlap and safest post-merge order.
11. Qualification method — software Vulkan, two captures, output and state interpretation.
12. Post-#7 handoff — exact rebase/re-read/confirmation gates.

## 1. Authority and evidence grading

This is a source-reading prepass against the SHA above, not a rendered qualification. Statements marked **accepted upstream** have repository acceptance plus source support; **observed source** describes present implementation but is not an actor correctness result; **hypothesis** requires native proof; **decision** remains unresolved. Critical readings: `AGENTS.md`; `docs/shadedoomvk/issues/{PF-012,SDVK-010,SDVK-007}.md`; `docs/shadedoomvk/{PF-002-LIFETIME-CONTRACT,PF-003-BINDLESS-CONTRACT,PF-004-LEVELMESH-CONTRACT,PF-009-SPRITE-SURFACE-CONTRACT,PF-113-MISSING-IBL-DECISION,SDVK-002-OBSERVABILITY,SDVK-005-FINAL-ACCEPTANCE,06-VALIDATION-PERFORMANCE-CONTRACT,10-EXECUTION-LEDGER}.md`; `docs/shadedoomvk/rag/{02-RENDERER-IDENTITY-LIFETIME,04-MATERIAL-SHADER-CONTRACT,05-LIGHTING-SHADOW-TRUTH-TABLE,06-LIGHTMAP-PROBE-PIPELINE,07-PORTAL-COORDINATE-SPACES,11-RENDERER-OBSERVABILITY}.md`.

PF-012 accepted PR #59, merge `8db714d3b5856acb3a4ea09839d4999f20ce5d5d`, fixes *per-lightmap texel* selection; it explicitly did **not** implement actor-specific probe policy, spatial blending or new GI. PF-113/PR #117 later makes unavailable probe radiance *exactly zero* on both branches, without sampling fixed 2D slots 0/1 as cubemaps. SDVK-002 provides observer/corpus and software-Vulkan infrastructure, not #10 acceptance. SDVK-005 established semantic material/height data without adding actor IBL. Merged #7 source is now available on master, but its **final accepted and verified orientation contract** remains unresolved while #7 is open.

## 2. Producer → descriptor → consumer

### 2.1 Source chain

```text
authored UDMF lightprobe thing 9892 / runtime addlightprobe / autoaddlightprobes
  -> level.lightProbes: LightProbe{position,index} (AUTHORED ordinal, including 0)
  -> FLevelLocals::RecalculateLightProbeTargets()
       sector.lightProbe.index / sidedef.lightProbe.index (AUTHORED target)
  -> LightProbeIncrementalBuilder::Step/Full()
       hw_entrypoint.cpp::RenderView probe actor -> RenderLightProbe(face=0..5)
  -> VkLightprober::GenerateIrradianceMap/GeneratePrefilterMap/EndLightProbePass
  -> VkTextureManager::CopyIrradiancemap/CopyPrefiltermap
       Irradiancemaps[authored] + Prefiltermaps[authored] image/views
  -> VkDescriptorSetManager::GetLightProbeTextureIndex(authored)
       AllocBindlessSlot(2) -> RUNTIME pair base B (irradiance), B+1 (prefilter)
       unavailable -> runtime 0 fallback, before publishing a pair
  -> (A) immediate sprite/wall/flat uniform uLightProbeIndex = B
     (B) VkLightmapper::UploadProbeSelection -> frag_copy.glsl per-texel R16_UINT=B
  -> scene lightmodel_pbr.glsl:
       uniform B, OR four gathered per-texel bases with original weights
       SampleProbeIrradiance(B,N), SampleProbePrefiltered(B,R,lod)
  -> PF-113: B==0 -> zero irradiance & zero prefilter without descriptor access
  -> PF-002/PF-003 slot generation, LevelMesh owner/LightmapProbe mutation,
     VkTextureManager LightProbeEpoch/LightmapEpoch, typed atlas fallback
```

Actual source anchors: `src/rendering/hwrenderer/doom_lightprobes.cpp::AddLightProbe,InvalidateLightmapProbeSelection`; `src/common/rendering/hwrenderer/data/hw_lightprobe.{h,cpp}::LightProbeIncrementalBuilder::Step,Full`; `src/rendering/hwrenderer/hw_entrypoint.cpp::RenderView`; `src/common/rendering/vulkan/vk_lightprober.cpp::{GenerateIrradianceMap,GeneratePrefilterMap,EndLightProbePass}`; `src/common/rendering/vulkan/textures/vk_texture.{h,cpp}::{CopyIrradiancemap,CopyPrefiltermap,ResetLightProbes,CreateLightmap}`; `src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp::GetLightProbeTextureIndex`; `src/common/rendering/vulkan/vk_lightmapper.cpp::{UploadProbeSelection,Copy*}`; `wadsrc/static/shaders/lightmap/frag_copy.glsl::findClosestProbe`; `wadsrc/static/shaders/scene/lightmodel_pbr.glsl`.

### 2.2 Separate index/identity domains — never reinterpret

| Name | Owner / meaning | Valid values and pitfalls |
|---|---|---|
| Authored probe index | `LightProbe.index`, sector and side `lightProbe.index` | Ordinal **0 can denote an actual authored first probe**. It is not the bindless fallback token. |
| Runtime irradiance descriptor base | `GetLightProbeTextureIndex(authored)` | Allocator-returned pair base `B`; **0 = fallback/unavailable**, valid nonzero `B` is dynamic, normally >=259, **not** `2*ordinal+1`. |
| Prefilter descriptor | Same allocation | **`B+1` only after proving `B>0`, pair span=2, capacity/generation/current owner**. |
| Probe-map R16_UINT texel | `frag_copy.glsl` / lightmap copy | Stores `B` directly; 0 fallback, 1..65535 representable, outside range **excluded**, not truncated. |
| Lightmap page pair | Fixed reservation | 128 pages *2 descriptors, fixed region [3,259), alternating baked radiance texture/probe-map; separate from dynamic environment pair. |
| Dynamic descriptor identity | PF-002/003 | `{index,generation,epoch,span}`; recyclable slot number alone is insufficient to prove validity; pair must belong to same current allocation. |
| LightProbeEpoch | `VkTextureManager` | Advances on `ResetLightProbes()`, including probe count→0; content reset is **not identical** to descriptor slot retirement. |
| LightmapEpoch | `VkTextureManager` | Advances on `CreateLightmap(...)` and teardown; tracks atlas page resource owner, not sprite probe semantics. |
| LevelMesh owner / LightmapProbe domain | `LevelMesh`, PF-004 | Whole-resource epoch on Reset; LightmapProbe mutation on probe-set/tile changes; must not be confused with renderer-view epoch. |
| PF-010 view context | `HWRenderContext` | Per-pass epoch/identity, root/depth/mirror context; diagnostic/render-view identity, **not persistent actor probe owner**. |

**Accepted PF-012 selector:** `HWProbeSelection::FindClosest` and GPU `frag_copy.glsl::findClosestProbe` choose *nearest live* probe within **inclusive radius 512** in LevelMesh world XYZ. Strictly nearer updates; equal-distance tie keeps first eligible candidate. Missing, out-of-range or owner mismatch returns 0. Candidate struct `vec3 position + uint runtimeTextureIndex` is 16 bytes (std430); maximum 32,768 live representable pair starts; GPU `LightProbeAABBTree::Update/Upload` is deliberately dormant. There is **no accepted continuous spatial probe blend in this selector**. PBR's four-tap **lightmap textureGather interpolation is a separate already-accepted sampling operation**, not an actor crossfade.

**Important unresolved actor default:** `HWSprite::DrawSprite` passes authored 0 when an actor sector is absent (also on particle paths). `LightProbeTarget::index` defaults 0 and the runtime resolution treats authored ordinal 0 as legitimate when a first probe is published. Therefore “sector missing” is **not proven** to mean “no probe” when authored0 exists. A later targeted diagnostic/control must distinguish actor-source absence from authored probe0 without changing the PF-012 fallback meaning. Record as hypothesis/possible defect, not as accepted behavior.

### 2.3 Bake, reset, owner guards

`VkLightprober` convolutes captured environment into 32x32 single-mip RGBA16F irradiance cubes and 128x128 RGBA16F prefilter cubes with five mip levels (`MAX_REFLECTION_LOD=4`). The faces are captured through the probe root render context. `EndLightProbePass` copies published faces into `VkTextureManager` probe images; only then can a valid pair be resolved. `LightProbeIncrementalBuilder::Step` is bounded to five inherited iterations and resets on count changes, including 0; `Full()` has progress guard. `InvalidateLightmapProbeSelection` marks every tile `ReceivedNewLight` and advances `LevelMeshMutationDomain::LightmapProbe` on runtime authored probe placement. `VkLightmapper::UploadProbeSelection` requires its mesh to match the globally current level mesh; each candidate's runtime pair must already be live. `VkTextureManager::ResetLightProbes` advances LightProbeEpoch and clears/re-publishes image contents; old descriptor slots may legitimately remain allocated to their old, now-cleared image owners. **Do not require a new slot generation on every content reset.** Conversely, if a slot *is retired/reused*, PF-003 generation mismatch must reject the stale record.

Atlas shrink follows CFX-009/PR #104 typed fallback publication: removed lightmap pages receive initialized RGBA16F=0 / probe R16_UINT=0 views from `VkTextureManager::LightmapFallback`, then prior owners retire through normal fences; `PublishedLightmapPages` advances after descriptor write. Atlas page count validated against CPU page metadata and current Vulkan resources at lightmap copy. No second actor lifetime scheme.

## 3. Distinct render consumers (observed source; qualify later)

| Draw family | Probe selection / IBL | Other light / shadow / fallback |
|---|---|---|
| World wall | `hw_walls.cpp` sets side authored target; if valid lightmap texture and uniform probe 0, shader gathers four per-texel runtime bases, else uniform target | Normal/material based; per-lightmap baked data, local lights and sunlight policy depend on active shading mode |
| World flat / 3D-floor surface | `hw_flats.cpp` sets sector authored target; lightmap path can supply per-texel map | Separate floor/ceiling geometry/light/sky tests; do not assume same target at a moving 3D floor |
| Ordinary actor sprite | `HWSprite::DrawSprite` -> `SetLightProbeIndex(actor&&actor->Sector ? sector->lightProbe.index : 0)` -> `VkRenderState::ApplySurfaceUniforms` resolves dynamic pair; generally **not** the world lightmap texel selector | `HWSprite::PutSprite` chooses CPU aggregate vs GPU/per-pixel lists; sector light/colormap, `gl_spritelight`, `gl_light_sprites`, fullbright, fog and sun conditional |
| Actor drawn with model/voxel | Probe target set in common `DrawSprite`; model rendered via `FHWModelRenderer::RenderModel` and model normal/object matrix, not sprite-card TBN | Distinct per-pixel model enable / fake model light and culling; qualify separately, do not reuse #7 card orientation |
| Particle / visual thinker | `ProcessParticle` sets explicit particle source state; `DrawSprite` passes authored target 0 if no actor | Particle light sampling gated by `gl_light_particles`; sector/particle lit state and fog differ; 0 may alias authored probe0 |
| HUD weapon/viewmodel | `hw_weapon.cpp` separate draw, light list/aggregate, HUD model/sprite shading; observed path does not set actor probe target here | **Out of #10:** SDVK-011 owns viewmodel policy. Capture non-regression only |
| Decal / translucent / canvas | Own material/draw flags and shader paths; may inherit bound state but are **not evidence** of actor target correctness | Only compatibility regression controls unless a demonstrable leak from actor draw |

`VkRenderState::ApplySurfaceUniforms` currently resolves every draw's `mLightProbeIndex` by `GetLightProbeTextureIndex` and writes `uLightProbeIndex`. This *read path has potential allocation when first seen*; future **observation must not call it anew**. Observe the already-resolved immediate draw uniform and PF-003 tokens, as PF-113 diagnostics do.

## 4. Spatial, sector and portal semantics

Classification legend **A** accepted PF invariant, **S** source-supported likely current actor behavior, **Q** unresolved question to qualify before a golden, **D** new policy decision needed. This table is a **test plan, not assumed screenshots**.

| Case | Expected probe identity/transition | Grade / decision gate |
|---|---|---|
| Same actor sector, static targets / same probe | Uniform authored sector target and resolved current runtime pair stable; camera alone does not redefine actor's target | S; observe two cameras and same actor position |
| Two adjacent sectors | A sprite follows its authoritative `actor->Sector->lightProbe.index` at sector transition, *not necessarily* a 512-radius nearest-position boundary | S; compare actual target recalc and actor subsector, including on-line boundary ownership |
| Lightmap probe-map boundary | World texels use discrete <=512 nearest live selector and original 4-tap PBR gather weights; actors do not automatically inherit it | A for world; D for actor blending |
| Moving actor within one sector | No promised continuous nearest-probe update merely from XY movement | S; log actor sector and target each step |
| Moving camera with static actor | View-reflection direction/billboard normal may change; world actor authored target should not be replaced just from camera motion | S; exceptions: camera-dependent normal/reflection is physical |
| Moving floor / sector or 3D floor | Distinguish mutated LevelMesh tiles and target recalculation from actor sector membership; no invented update frequency | Q; log geometry Query & LightmapProbe mutation epochs |
| Same XYZ in different portal groups | Portal group is semantic query context; nearby XYZ cannot justify cross-group actor target | Q; **PF-012 world copy selector has no portal-group key**, so do not misstate it as portal-isolated |
| Line portal / linked displacement | Preserve `sourcePortalGroup`, `renderPortalGroup`, `throughPortalMode`, and `Displacements.getOffset`; diagnose actor position in both source and render coordinates | Q; ensure actor authoritative target isn't guessed from translated camera |
| Stacked portal / recursive | Distinct PF-010 child/root context and portal transform order; no global cross-pass probe cache | Q; confirm supported portal variant before declaring runnable |
| Line/plane mirror | Mirror parity may change view and reflection screen appearance; may not permanently rewrite actor/probe ownership | A for PF-010 context; Q for actual actor IBL output |
| Probe absent/unpublished/disabled | Runtime pair 0 contributes **zero IBL radiance**; sector/direct/sun terms can remain, final pixel need not be black | A for PF-113 shader; Q for precise actor-source fallback classification |
| Probe reset/rebuild / level transition | Relevant epochs/domain invalidated; old retired pair must never be silently sampled and new published pair or explicit zero must be diagnosed | A for identity contract, Q actor evidence |

**Probe blending is NOT specified for actors.** World **lightmap** PBR mixes four texel samples at retained bilinear weights; that cannot be transplanted as arbitrary actor interpolation. Candidate future policy (D): discrete sector target, discrete spatial target, sector-weighted blend, or another authored selector. Require explicit design authority and compatibility evidence before changing semantics.

Testable hypotheses: H01 actor sector stability (S); H02 exact boundary change under actual sector membership (S); H03 no retired descriptor reused with prior generation (A); H04 absent 0 bypasses both cube samples (A); H05 portal group cannot authoritatively leak unrelated selection (Q); H06 camera motion does not change authored actor target (S); H07 view mirror cannot mutate probe owner (Q); H08 probe publication is missing→live only after both views exist (A); H09 3D-floor movement changes required world query/atlas identities (Q); H10 no “automatic actor blend” without accepted policy (A as non-feature). `fixtures.json` names observations and scene expectations.

## 5. SDVK-007 orientation handoff — semantics only

For directional actor PBR IBL, the eventual implementation needs a stable per-fragment **lighting-space normal** `N`, view-to-camera unit vector `V`, reflection vector `R=reflect(-V,N)`, and sunlight direction `L`, **all in the same shader world space** as `pixelpos.xyz` and captured irradiance/prefilter cube directions. Necessary properties:

1. A normal-map tangent vector is interpreted through the **accepted #7** tangent→world transform, including sign of U/V, Doom rotation, billboard, wall/flat mode, pitch/roll, and frame/actor UV mirroring. Degenerate or unsupported modes need an explicit documented legacy/derivative fallback.
2. For non-sprite models, use the *model* normal matrix and existing model contract; world surfaces maintain existing world/LevelMesh basis. Do not coerce these into sprite-card coordinates.
3. Convert once into shader-world XYZ (Doom X, **vertical Y**, Doom Y), consistently for `N,V,R,L`; LevelMesh lightmap copy positions instead remain in their own verified LevelMesh XYZ layout, and raytrace `SwapYZ` applies only at its existing boundaries.
4. Account for portal displacement of actor/view position without applying reflection sign twice. Mirror view parity is distinct from persistent semantic probe ownership.
5. Qualify direction at six cube axes, a non-symmetric off-axis vector and asymmetric normal texture, with known camera and actor positions.

Merged #135 currently provides (without asserting #7's final acceptance) a final-quad TBN and opt-in explicit per-draw vectors in `hw_sprite_tangent.h` / `material_normalmap.glsl`. It is *interface awareness only*. When #7 is finally accepted, re-read then-current merged `SDVK-007-BASIS-ARCHITECTURE.md`, actual draw uniforms, shader world/view transformations, fallback mode and native qualification. **Do not choose/modify #7's representation in this prepass.** Legacy/non-normalmapped, unsupported sprites, models, HUD and palette materials remain separately classified.

## 6. Environment-light math audit (no tuning)

**World inputs.** `vert_main.glsl` emits `pixelpos.xyz` after `ModelMatrix`, `vWorldNormal` after `NormalModelMatrix` and `vLightmapIndex=LightmapsStart+2*page` for valid pages. `material.glsl::SetMaterialProps` calls `ApplyNormalMap`. In the prior verified `cbff1d10` master, `material_normalmap.glsl` decodes normal RGB as `sample*255/127 -128/127`, flips green, and builds derivative cotangent frame using world derivatives; #7 must replace only accepted sprite modes. Normal-free path normalizes `vWorldNormal`. The pre-#7 derivative path with sprite zero normal is **not** proof of orientation correctness. Current live master already contains #135's proposed explicit sprite mode, but final #7 issue acceptance and post-merge checks remain outstanding.

**Diffuse IBL.** `lightmodel_pbr.glsl::ProcessMaterialLight`: `N=material.Normal`; irradiance= `textureLod(cubeTextures[nonuniformEXT(B)],N,0).rgb` (one-mip 32x32 irradiance cube, specified linear filtering). `diffuse=irradiance*albedo`; `F=fresnelSchlickRoughness(clamp(dot(N,V),0,1),F0,roughness)`, `F0=mix(0.04,albedo,metallic)`, `kD=(1-F)*(1-metallic)`; multiply total indirect by material AO. Unavailable `B==0` -> zero diffuse IBL. No color/photometric reinterpretation or extra normalization.

**Specular IBL.** `R=reflect(-V,N)`, `MAX_REFLECTION_LOD=4.0`; `prefilter=textureLod(cubeTextures[nonuniformEXT(B+1)],R,roughness*4)` for live pair only; 128x128 prefilter cube with 5 mips. `envBRDF=texture(textures[BrdfLUT], vec2(clamp(dot(N,V),0,1),roughness)).rg`; `specular=prefilter*(F*envBRDF.x+envBRDF.y)`. Indirect `ambient=(kD*irradiance*albedo+specular)*AO`, final `max(ambient+Lo,0)`. For lightmapped branch, `textureGather(uintTextures[vLightmapIndex+1],vLightmap.xy)` gives four `B` tokens with weights `(1-tx)(1-ty), tx(1-ty), (1-tx)ty, tx ty`; missing tap contributes zero with **no renormalization**. Fixed 2D slots0/1 must never be sampled as cube. **This branch distinction is a required state oracle.**

**Sunlight / world occlusion.** `SunDir` is the shader direction toward the sun used in `dot(N,SunDir)`. PBR sunlight (when `sunlightAttenuation>0`) uses GGX/Smith/Schlick with `SunColor*SunIntensity*2.5*sunlightAttenuation*max(dot(N,L),0)`; the non-PBR shader `lightmodel_normal.glsl` also applies `max(dot(N,SunDir),0)`. Sector/direct contribution `Lo` remains independently active: `uDynLightColor`, local light list `ProcessLight`, and synthetic ambient sector light (compatibility factors 2.25 and metal 0.40), so no-probe final is *not* required black. `hw_spritelight.cpp::ActorTraceStaticLight::TraceSunVisibility` can call `LevelMesh::TraceSky(worldPosition,level.SunDirection,65536)` and key cached visibility by actor position, PF-004 world Query epoch and stable portal group; `GetDynSpriteLightList` also has an explicit `(level.lightmaps && gl_spritelight>0) || TraceSunVisibility(...)` branch for `AddSunLightToList`. That shortcut makes **sun/world occlusion behavior mode-dependent; never claim all actors are always CPU-TraceSky occluded**. Shader `light_trace.glsl::traceSun` uses world LevelMesh ray traversal/portal transform where used; `lightmodel_normal.glsl` local sun flags choose trace conditional; PBR `ProcessLight` intentionally bypasses shadow-map attenuation for the large-radius sun proxy. The exact PBR `sunlightAttenuation` upstream assignment and any duplicate proxy/direct contribution require post-#7 emitted-draw proof, including gl_spritelight/lightmaps/rayquery permutations. Verify sun world→shader axis sign with facing + backfacing normal controls, world occluder, portal group and mirror.

**Cubemap convention:** do not infer a face ordering from PNG file names. `VkLightprober` face camera transforms plus compute convolution `lightprobe/comp_{irradiance,prefilter}_convolute.glsl` establish the runtime convention; later directional fixture must first calibrate the actual capture→sampling mapping. Reference cube faces are separately authored in `tools/prepass/sdvk010/generate.py` (+/-X, +/-Y, +/-Z); these are **reference patterns, not automatically loaded native cubemaps**. Current engine bakes from rendered scenes; installing reference faces into production probe images is **not authorized** here.

## 7. Planned deterministic qualification corpus

`fixtures.json` is a **proposal** with fixture IDs, inherited scene reuse and precise state assertions. Begin from accepted `tools/renderer_oracle/prepare.py` `sun_probes` (two real UDMF 9892 probes, 9890 sun, no prebaked lumps), `sprite_mirror` (mirrored rotations, wall/flat, true line mirror), `material_stress` (semantic PBR/normal/height controls) and `tools/pf_oracle/prepare_pbr_probe_runtime.py` (PF-113 tiny publication state). Add a separate bounded SDVK-010 generator *after* #7, not now.

Required cases: F01 uniform published neutral; F02 two sectors, two distinct probe targets; F03 actor movement across exact boundary in integer/half-step positions; F04 probe-map nearest boundary for world and independently the actor sector path; F05 portal groups at same apparent XYZ with linked offset; F06 absent/unpublished/disabled; F07 probe reset + pair reuse/epoch; F08 sunlit normal directions + flipped normal; F09 sun occluder vs open sky across Query epoch; F10 dielectric/metallic × low/high roughness × normal-mapped sprite; F11 #7 sprite orientation including mirror/roll/flat/face (expected pixel oracle deferred); F12 3D-floor/sector-motion/portal mirror scene if engine-support confirmed; F13 resource recreate/load/unload/128-page shrink; F14 negative nonzero authored ordinal but unavailable runtime pair, including authored0 real and actor-source-absent; F15 camera movement with stationary actor and stable authoritative target.

For each test retain: test scene PK3 SHA, authored probe positions and indices, actual computed sector/side targets, actor TIDs and positions, model/sprite type, camera/view context and portal groups, `gl_lightprobe`, `gl_spritelight`, `gl_levelmesh`, `gl_ubershaders`, `vk_rayquery`, probe publication point, exact descriptor pair tokens+identity, normal and reflection direction, sun settings, prefiltered LOD, shader/pipeline identity, and two independent captures. Do not hardcode guessed sector target membership or portal dispatch. `tools/prepass/sdvk010/generate.py` emits repeatable authored PNG references, a golden manifest and host-side PF-012-only selector/reflection tables; it does **not** generate Vulkan-native captures or assert that reference PNGs were installed as cubes. Corresponding `test_prepass.py` and `validate.py` are explicitly host/offline only.

## 8. Resource stress, observer and validator contract

See companion `LIFETIME-STRESS.md`, `diagnostics.schema.json`, `fixtures.json` and `tools/prepass/sdvk010/validate.py`.

**Required read-only proposed event:** one emitted actor/material draw containing actor/map/section/sector, render surface kind, sector target (authored index or `unknown`), source/render portal groups/displacement and PF-010 context, sampled `uLightProbeIndex` (runtime), presence of lightmap gather, current PF-003 `{index,generation,epoch,span}` for BOTH pair slots, independent `LightProbeEpoch`, `LightmapEpoch`, `LevelMesh` owner + `LightmapProbe` mutation, fallback reason and published resource/view type. Attach PBR roughness/metallic/AO, basis mode from **accepted** #7, N/V/R diagnostic sampling as practical, sun vector/intensity/world occlusion result/source, shader and feature switches. Never **resolve** a probe, allocate a descriptor, recalculate targets or change shader decisions *for diagnostics*. Existing read-only SDVK-002 `SdvkDiagnostics` and PF-113 emitted-draw `vk_pbrprobediagnostics.cpp` are the seams.

**Validator hard rejects** (after availability is explicitly known):
- runtime zero mislabeled as live irradiance/prefilter, or as an authored ordinal; fallback missing explicit reason;
- runtime `B>0` with missing current irradiance+prefilter views, wrong cube view type, `B+1` not same owned span=2, out-of-capacity pair or resource generation/epoch mismatch;
- stale pair after retirement/reuse even if numeric slot coincides; no silent prior view;
- probe-map value not [0,65535], invalid current atlas page, mismatched LevelMesh owner, stale LightmapProbe mapping after placement;
- portal-group semantic context lost/incorrect for actor selection, or mirror view overwriting persistent semantic owner;
- nonfinite/zero-length when normalized N, V, R; inconsistent cube-space transformation; prefiltered LOD outside [0,4] for valid roughness 0..1;
- probe reset/rebuild without relevant `LightProbeEpoch`/mutation transition; distinguish valid same-slot cleared image from retired descriptor;
- resource absence silently substituted with previous frame's plausible sample;
- observed sun visibility cache reused after PF-004 Query epoch or stable portal-group change;
- no two independent native captures, missing material/orientation state, or image-only evidence advertised as accepted semantics.

**Scope exception:** a missing probe can legitimately retain nonzero direct/sector/sun `Lo`. Never reject a nonblack image solely because IBL fallback was zero.

## 9. Correctness versus aesthetics

**#10 correctness candidates**: wrong authored target given accepted sector policy; crossed portal group; stale retired descriptor; missing-to-live publication mismatch; wrong cube axis/handedness; normal/reflection vector space mismatch; unrelated specular pair; roughness-mip range invalid; incorrect sun direction/occlusion; stale atlas map; missing typed zero fallback; mode-specific shadow/light leakage. Prove with a minimized failing pre-fix state/image and corrected oracle before production edit.

**Out-of-scope aesthetic decisions**: actor probe blending/crossfade radius and curve, probe density/priority reauthoring, environment brightness/exposure calibration, metallic/roughness tuning, specular artistic intensity, sector-to-probe interpolation, altered sunlight defaults, wide-scale GI claims. Retain current PF-011 calibration until separate design decision. World lightmap four-tap gather **is not** an aesthetic design proposal to extend to actors.

## 10. Integration seams and #135 conflict assessment

PR #135 (merged source; former head `a895dca0...`) touched `hw_sprites.cpp`, `hw_renderstate.h`, `hw_surfaceuniforms.h`, `material_normalmap.glsl`, shader binding/layout, `vk_sdvkdiagnostics.cpp`, `hw_sdvkdiagnostics.{cpp,h}`, observer `tools/renderer_oracle/{prepare.py,corpus.json,validate.py,observation.schema.json,run.py}`, and RAG/ledger. **Expected direct overlap** post-#7: `hw_sprites.cpp` (actor selection/portal state), `hw_renderstate.h` and `hw_surfaceuniforms.h` (draw uniforms), `vk_sdvkdiagnostics.cpp` / `hw_sdvkdiagnostics.*`, shader `layout_shared.glsl` and `material_normalmap.glsl` (read accepted normal, avoid rewriting), `tools/renderer_oracle/*`, RAG/ledger. **Possible overlap**: `material.glsl`, `lightmodel_pbr.glsl`, `vk_renderstate.cpp`, shader `binding_struct_definitions.glsl`, `hw_sprite_tangent.h` (consume interface only, normally do not alter), `hw_spritelight.cpp` sun diagnostics. **Largely independent producer sources**: `doom_lightprobes.cpp`, `hw_lightprobe.*`, `vk_lightprober.cpp`, `vk_lightmapper.cpp`, `vk_texture.cpp`, `vk_descriptorset.cpp`, `frag_copy.glsl`, `tools/prepass/sdvk010/*`; PF-012 producer modifications are **not** authorized without reproducing a distinct foundational regression.

Merge order: (1) finish and *accept* #135/SDVK-007 (including its verification and RAG contract); (2) base a new SDVK-010 implementation branch on exact **post-#7-acceptance verified** master; (3) reread accepted #7, source and observer schema; (4) establish/approve actor selection and fallback semantics in targeted state-only fixtures; (5) implement smallest demonstrated actor consumer fixes on branch, with no speculative PF producer or style changes; (6) qualify software Vulkan and full CI; (7) only then PR→merge→master verification→issue closure. This prepass branch remains a standalone research checkpoint and is **not** itself the implementation PR.

## 11. Planned software-Vulkan correctness gate

No physical-GPU run is required for #10 unless a demonstrated hardware-specific defect creates one. On the same software-Vulkan build/driver/config: use **two truly separate processes** per scene, identical scene hashes/settings and deterministic fixed camera, tic, renderer time and actor positions. Record raw exact actor/sector/portal and resource identities, plus the output images and linear HDR/float readbacks where available. Compare current run-to-run images exactly only when bit-stability is demonstrated; retain same-driver exact RGB or strict justified channel tolerances with provenance. Descriptor numeric tokens may be normalized bijectively for independent-process comparison while preserving *same pair relationship* and exact generations, epoch, span, fallback and authored index. Separately verify source schema and emitted actor draw; a generated PNG, synthetic oracle or PF-113 helper alone **does not qualify** production runtime actor IBL.

Require positive and adversarial negatives (fallback, wrong probe face, stale generation, cross-group alias, mirror misorientation, sun occluder, mixed zero/live taps). Present false cases only in offline state tests; never deliberately dereference stale/incorrect Vulkan descriptors.

## 12. Handoff required immediately after SDVK-007 acceptance

1. Re-fetch exact verified master SHA, issue #7/#10, #135 merge commit and last reviews; confirm #7 accepted and #10 still open; create a **new implementation branch from accepted master**, not this prepass branch.
2. Reread `docs/shadedoomvk/SDVK-007-BASIS-ARCHITECTURE.md`, PF-009/014 material/portal RAG, merged `hw_sprite_tangent.h`, `hw_sprites.cpp`, `hw_renderstate.h`, `hw_surfaceuniforms.h`, shader `material_normalmap.glsl`, shader layout/binding and diagnostics. Verify exact supported/fallback sprite modes and world-space N/V/R convention; regenerate orientation goldens only against **accepted** behavior.
3. Reread `VkDescriptorSetManager::GetLightProbeTextureIndex`, `VkLightmapper::UploadProbeSelection`, `frag_copy.glsl`, `VkTextureManager::ResetLightProbes`, PBR shader and CFX-009 fallback; check index 0 authored vs runtime, pair generations and reset epoch before any actor change.
4. First native qualification prove actual sector/side targets, actor/particle null-sector behavior, lightmap vs uniform PBR branch, portal displacement and direct/sun path; obtain native cube face/axis mapping from capture/convolution, not reference-image filenames.
5. Reconcile changes/conflicts in #135's observer corpus/schema and shader basis; add read-only diagnostics to accepted observer, fail-closed host validator and bounded extended `sun-probes` / `sprite-mirror` native fixtures with two captures.
6. Decide any actor blending, cross-group probe selection change or missing-sector policy **explicitly** in a design record before implementation. Fix only reproduced correctness failures; retain PF-012/PF-113 and PF-011 compatibility contracts.
7. Run complete source/CPU/CI + software-Vulkan state-and-image corpus at exact candidate and merged master. Document failures, no-GPU limitations and remaining aesthetic questions; only an accepted merged/verified #10 implementation can unblock #14.

**Checkpoint limitation:** This prepass contains authored *reference cubemap PNG generators* and an offline corpus/validator; it neither installs reference cubes in Vulkan nor confirms actor environment pixels. The exact route to author/reinject a native cube and portal-group-specific sector target requires demonstration by the post-#7 implementation task.
