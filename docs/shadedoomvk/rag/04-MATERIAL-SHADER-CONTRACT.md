# Material and shader contract


Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active; PF-008 semantic identity implemented; PF-013 correctness boundaries accepted; PF-017 node/flat hash lookups rejected after physical profiling
Primary issues: PF-003, PF-008, PF-013, SDVK-005, SDVK-007, SDVK-008

## Current material model

Primary source:

- `src/common/textures/gametexture.h`
- `src/common/textures/material_layer_semantics.h`
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

PF-008 adds explicit `MaterialLayerSemantic` metadata to the existing ordered array. The semantic identities are `Albedo`, `Normal`, `LegacySpecular`, `Metallic`, `Roughness`, `AmbientOcclusion`, `Brightmap`, `Detail`, `Glow` and `Custom`. Custom layers also retain their original authoring slot in `customIndex`.

## Important correction

Per-layer sampling is **already inherited**.

`MaterialLayerInfo` includes `MaterialLayerSampling layerFiltering`; `MaterialLayerSampling` includes `Default`, `NearestMipLinear` and `LinearMipLinear`; GLDEFS/custom-shader parsing can assign sampling overrides; Vulkan chooses override samplers per layer.

Therefore PF-008/SDVK-005 must not treat per-layer filtering as absent.

The PF-020 GLDEFS repair selects each custom texture's free authoring slot before
initializing its omitted-filter default. Declaring another custom texture must
not overwrite a previous slot's explicit sampling override. Both the shared
material/map/class property and legacy HardwareShader property follow this
invariant; sparse authoring slots and historical binding order are preserved.
See [repair and retained negative fixture](../PF-GLDEFS-SAMPLING-REPAIR.md). This
partial repair does not accept PF-020 or the separate indexed-material path.

## PF-008 semantic identity and binding adapter

The semantic tag is descriptive metadata, not a second ordering mechanism. `FMaterial::mTextureLayers` remains the single historical binding order for authored layers consumed by Vulkan; a shader-required auxiliary palette row is not an authored layer.

Representative layouts remain:

- default: albedo, brightmap, detail, glow;
- legacy specular: albedo, normal, legacy specular, brightmap, detail, glow;
- PBR: albedo, normal, metallic, roughness, AO, brightmap, detail, glow;
- custom extension layers append after the fixed sequence exactly as before.

Absent bright/detail/glow textures still use the inherited placeholder texture at their existing binding. Their semantic metadata names the intended channel, not the placeholder resource itself.

Sparse custom authoring slots still compact into the historical binding array. `customIndex` retains the original custom slot so later renderer code does not have to infer authoring identity from compact binding position.

`FMaterial::FindLayer()` is the semantic-to-current-binding adapter. `FMaterial::GetLayerDiagnostic()` exposes binding, semantic, custom slot, source texture, scale/clamp flags and inherited sampling state. See `docs/shadedoomvk/PF-008-MATERIAL-SEMANTICS-CONTRACT.md`.

## Current positional coupling

Shader logic still relies materially on known layer ordering/defines. PBR layer presence is all-or-nothing for the normal/metallic/roughness/AO group in `FMaterial` construction. Placeholder textures are inserted for absent bright/detail/glow layers so shader texture units remain valid.

PF-008 contains rather than removes this compatibility coupling: semantic lookup is explicit, while ordinary material descriptor construction still consumes the inherited array order. Later work may use semantic lookup where safe, but may not silently reorder legacy bindings.

## PF-008 semantic refactor boundary

PF-008 introduces explicit semantic metadata for **existing** channels while preserving:

- existing GLDEFS/material authoring syntax;
- current layer sampling behavior;
- current palette/translation behavior;
- current shader selection;
- current descriptor ordering and placeholder behavior;
- current output for valid existing content.

PF-008 does **not** make height/POM a user-visible feature. SDVK-005 owns first-class height semantics/authoring/default policy after the representation is safe.

## PF-013 correctness boundaries

### Indexed RedIsAlpha

`CTF_Indexed` and `CTF_IndexedRedIsAlpha` are both single-byte producers but do not mean the same thing. Ordinary indexed data is a palette index. RedIsAlpha asks image-backed textures for luminance bytes and is consumed by `TM_ALPHATEXTURE` as fixed white RGB with that byte controlling alpha. Vulkan must therefore preserve the interpretation in material/descriptors even though both use `VK_FORMAT_R8_UNORM`.

PF-013 records `mRedIsAlpha` in `FMaterialState` at the existing texture-mode/material binding boundary, gives the hardware texture a distinct RedIsAlpha resident image, and includes the interpretation in `VkMaterial` descriptor identity. Ordinary palette mode still uses `CTF_Indexed`, the existing translation key and no-filter clamp adjustment. Palette-mode `TM_ALPHATEXTURE` samples the R8 red component directly, keeps continuous alpha and bypasses palette-index colormap lookup; true-colour `TM_ALPHATEXTURE` keeps the inherited grayscale rule.

### Sprite precache variants

Sprite precache material identity is the same `scaleflags` contract as live material validation: `CTF_Expand` is always present and `CTF_Upscale` is added when requested. The marking pass must pass that integer flag word to `FMaterial::ValidateTexture`; boolean `true` happens to equal `CTF_Expand` but loses the upscale bit and may mark/create the wrong material variant.

### PBR roughness-zero safety

PF-013 changes only the GGX distribution's numerically unstable denominator representation. For positive roughness the new form is algebraically equivalent:

```text
1 + NdotH² * (a² - 1)
≡ (1 - NdotH²) + NdotH² * a²
```

where the shader's `a = roughness²`. The right-hand form avoids catastrophic cancellation near `NdotH=1` and very small roughness. At exactly zero lobe width the finite sampled-BRDF fallback is `0`, avoiding the inherited `0/0`; no roughness remap, minimum aesthetic roughness, light scale or PF-011 compatibility constant is introduced.

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

PF-113/#113 guards a zero environment pair before cube access or pair arithmetic. Its shared irradiance/prefilter helpers preserve live directions, pair identities, call order, gather coefficients and the rest of PBR. Missing taps contribute zero without renormalization; independent ambient/direct/sunlight terms remain. Explicit irradiance LOD0 and `nonuniformEXT` avoid relying on implicit derivatives or uniform descriptor selection under a divergent zero guard. This exception is justified by the actual one-mip probe view and dedicated LINEAR, zero-bias, non-anisotropic sampler; it is not a change to other material sampling policies. See [the adopted decision](../PF-113-MISSING-IBL-DECISION.md) and the separate native/release qualification.

Compatibility constants such as `PBRBrightnessScale` and ambient-sector-light approximations are part of current visual behavior. PF-011 centralizes/documents those bridges before later policy changes.

PF-013 owns numerical safety at the roughness-zero edge while preserving normal settings.

## Descriptor interaction

`VkMaterial::GetDescriptorEntry` caches bindless ranges keyed by material state such as clamp mode, translation/palette and global shader. Richer materials consume contiguous bindless slots. PF-003 hardens lifetime; accepted PF-017 profiling retains the linear lookup and the fully restored light path before SDVK height layers increase pressure.

PF-008 semantic metadata is not added to descriptor identity because it does not change bound resource state. Vulkan still iterates the ordered layers and chooses each sampler from `GetLayerFilter(i)`. PF-013's RedIsAlpha bit is different: it changes the producer/consumer interpretation of the bound R8 texture, so it is explicitly part of descriptor identity. PF-003 generation/lifetime/reservation rules remain authoritative.

## PF-017 lookup profiling boundary

Accepted master retained the per-material linear descriptor-variant scan after physical profiling: the dense PF-016 workload populated at most one variant per material and DBP37 MAP04 at most three. No representative hashed-lookup benefit was demonstrated. The exact state partition and PF-003 cleanup remain unchanged; [PF-017 final acceptance](../PF-017-FINAL-ACCEPTANCE.md) records the accepted measured no-go; earlier profiling counts remain historical evidence.

## Invariants

1. Existing content material meaning/output must not change during PF semantic tagging except for explicit PF-013 bugfix cases.
2. Semantic metadata may not become a second contradictory source of layer order truth.
3. Optional/default layers must not create stale bindless references.
4. Indexed/palette/translation behavior is compatibility-sensitive; palette-index and RedIsAlpha R8 data must not alias.
5. Sprite mirror/rotation correctness is not proven by a front-facing normal-map image.
6. Custom semantic identity includes the original custom authoring slot; compact binding position alone is not semantic identity.
7. Height/POM remains outside PF-008/PF-013.
8. PF-013 roughness-zero safety must not become an implicit PBR calibration or roughness-floor policy.

The second PF-017 attempt exercised published Champions translations with 15-17 variants per material. Node and flat canonical keys (resolved clamp/remap, global shader fields, indexed mode and indexed RedIsAlpha, scoped by VkMaterial owner) matched the linear oracle but regressed measured lookup time by 94.8% and 36.8%. Both prototypes were restored. A high maximum variant count alone does not justify hashing; PF-003 retirement and PF-008/PF-013 boundaries remain unchanged. See [PF-017-REUSE-RESEARCH.md](../PF-017-REUSE-RESEARCH.md).

The material-only qualification on master `84bbbac` found a sustained expensive population in a Sunlust/Champions arena (median 1,201 >8-entry calls/frame), but estimated large-search cost is only 47.13 microseconds/frame and a later NVIDIA failure prevented production confirmation. Ordered locality rejects a naive previous-hit shortcut for that expensive population (+1.81% comparisons). No candidate was implemented; accepted lookup/ownership/retirement remain unchanged. See [PF-017-MATERIAL-QUALIFICATION.md](../PF-017-MATERIAL-QUALIFICATION.md) for measurement uncertainty and the no-go decision.

## CFX final material/shader disposition

The CFX programme does not establish a material-identity or malformed-shader root cause. All 138 logged historical DBP37 cache-hit SPIR-V modules passed structural validation for the source target, and the recognized ordinary lightmap loads in cached fragment modules remained under their immediate lightmap-index guard. Neither result proves the executed shader/SASS or dynamic descriptor correctness.

Sunlust + Champions nevertheless supplies a material-heavy repaired-build route: the reconstructed movement/filter/reload path qualifies 3/3 in CFX-010. That is practical compatibility coverage, not proof that the historical Sunlust event shared the DBP37 descriptor-retirement mechanism. PF material identity, palette/translation, sampler and shader-key contracts remain unchanged by the final CFX synthesis. See [final synthesis](../CFX-FINAL-PROGRAMME-SYNTHESIS.md).

## Accepted #110/#112 material correctness repair contract

Public `DTA_Indexed` reaches one authored albedo layer but the inherited Vulkan consumer attempts missing additional layers. The accepted #110 repair provisions exactly two real resources: canonical-remap-specific R8 indices followed by an entry-owned unchanged base-palette row. Remap remains before the existing inverse/additive/object operations and palette lookup. Nearest/no-mip index sampling and normal fenced retirement are explicit; ordinary layer order, state-driven palette/RedIsAlpha and real SWCanvas remain protected. See [source and acceptance boundaries](../PF-110-IMPLEMENTATION-NOTES.md).

Mapped software framebuffer images stay GENERAL through the existing nullable upload path. The accepted #112 repair carries that actual owner layout into material descriptors, retaining default READ for audited uploaded callers and a READ/GENERAL writer guard. Real paletted SWCanvas retains both original resources; no forced transition, substitute producer or cache flush is added. See [layout contract and native limits](../PF-112-IMPLEMENTATION-NOTES.md).

Candidate4's normal packets are retained history. Candidate5 native qualification and verified PR #116 merge/post-merge integration are recorded in [the release receipt](../PF-110-RELEASE-ACCEPTANCE.json). Neither repair accepts the independent PF-020 freeze or changes gameplay, filtering or quality policy.


## Verified candidate5 native qualification

The final clean candidate passes all twelve normal mode/filter cases and both
genuine one-process core/sync restarts, with zero requested-validation errors or
warnings, unchanged pins and all294 presentation ROIs. Strict PF393/393, four
standalone contracts, CFX8/8 and deterministic source oracles pass.
See [source and acceptance scope](../PF-110-IMPLEMENTATION-NOTES.md) and
[compact independently reviewed qualification](../PF-110-FINAL-NATIVE-VERIFICATION.json) for hashes, methods,
retained failures and unmeasured mode1/SW-retirement/performance limits.
Focused release integration is accepted through PR #116 at master
`1524686e77f1e89dabfb044bf757a2d19566c31c`, with exact-head and post-merge checks
in [the release receipt](../PF-110-RELEASE-ACCEPTANCE.json). PF-020 release and SDVK-001 permission follow the separate
[freeze manifest](../PF-FREEZE-MANIFEST.md); focused repair acceptance is not the freeze.

## SDVK-004 accepted rich-material pressure qualification

SDVK-004 preserves the PF-008 ordered material-layer and sampler contract while
qualifying descriptor pressure. The CPU stress model includes ordinary,
legacy-specular, PBR, translated/palette, canvas and PBR-plus-four-custom-layer
spans; material descriptor cache identity continues to include resolved clamp,
translation/remap, global-shader address, palette mode and indexed RedIsAlpha.

The reusable `material-stress` renderer corpus now contains eight PBR panels
with a real GLDEFS hardware shader and a custom texture binding named
`SDVKExtra`. The parser maps that authored name to the inherited bindless
`textureN` slot, and the panels alternate nearest/linear custom sampling.
Native state assertions keep the PF-008 fixed authored prefix unchanged and
assert each custom layer separately at binding 8 with custom index 0 and its
authored nearest/linear sampling request. An image therefore cannot pass while
the custom resource silently disappears or its binding is reordered. This
extends evidence coverage; it does not change GLDEFS syntax, shader/material
semantics or filtering policy.

See [SDVK-004 descriptor stress](../SDVK-004-DESCRIPTOR-STRESS.md) and [release acceptance](../SDVK-004-RELEASE-ACCEPTANCE.json). Exact-head and merged-master software-Vulkan image/state gates passed. Eight custom PBR panels were actually drawn with their custom binding/index and requested sampling preserved. The hosted lane does not execute `pf-indexed-material`; accepted PF-110 evidence remains the indexed/translation native authority.


## SDVK-005 optional height semantic

SDVK-005 extends PF-008 by appending `MaterialLayerSemantic::Height` after every existing semantic/custom identity. Historical fixed/custom descriptor positions remain authoritative; GLDEFS custom starts stay 5/7/9. `FMaterial::FMaterial` appends height last and does not use it to choose Default/Specular/PBR shader models. Vulkan publishes it only on ordinary true-colour material routes and records the actual relative index in `SurfaceUniforms::uHeightTextureIndex`; indexed/palette routes report `-1`. Stock `SetMaterialProps` does not sample the channel. Custom/later shaders opt in with `HasMaterialHeightMap` / `SampleMaterialHeight`.

Existing built-in channels keep inherited `Default` sampling. The GLDEFS semantic-layer syntax may explicitly request `nearest`, `linear` or `default`; height's new default is linear min/mag + linear mipmap using the existing override sampler. This permits pixel-crisp default albedo with independently filtered data channels. Height is normalized linear scalar data from the red channel. See [SDVK-005 material height contract](../SDVK-005-MATERIAL-HEIGHT.md).
