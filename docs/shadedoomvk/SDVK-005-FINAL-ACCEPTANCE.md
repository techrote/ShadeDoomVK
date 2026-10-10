# SDVK-005 — final acceptance

Date: 2026-10-10  
Owner: SDVK-005 / #5  
Disposition: **ACCEPTED, MERGED AND VERIFIED** for the substantive implementation. Acceptance reconciliation is published as PR #133; this record becomes the durable programme acceptance receipt when PR #133 is itself merged and verified.

## Exact integration identity

- Starting authority: `master@0a2fbad203549d18ac6e5a61bb4747709637bfde`
- Substantive PR: #132
- Final implementation head: `9a87734357d15145ed791d89c4b98db94fb60cb6`
- Tested PR merge ref: `116a45bf47dc4595ead106ce99588723750d4d5d`
- Tested tree: `28f2ef41a99ea6979145030e807c7798c6e01735`
- Substantive merge/resulting master: `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`
- Resulting master tree: `28f2ef41a99ea6979145030e807c7798c6e01735`
- Exact tested-tree / merged-tree equality: **PASS**
- Acceptance-reconciliation PR: **#133**.

## Height semantic contract

`height` is an optional first-class material semantic. It represents normalized **linear scalar data** sampled from the texture red channel; it is not color data. No dedicated image format or precision is imposed by SDVK-005.

Authoring supports explicit GLDEFS `height` declarations and automatic `materials/heightmaps/<material-name>` lookup. Semantic material declarations may request `filter nearest`, `filter linear` or `filter default`. Existing channels keep their inherited default policy. Height's default is `LinearMipLinear`: linear minification/magnification, linear mip selection and the inherited override sampler's repeat addressing.

Absent height is harmless: no height descriptor is published, `uHeightTextureIndex == -1`, and `SampleMaterialHeight` returns 0 only when an opt-in shader calls it. The stock material path does **not** call the helper, so adding the semantic does not change ordinary rendering by itself.

Malformed semantic properties and invalid filter values are parser errors. A named height texture that cannot be resolved is reported and is not installed into the material.

## Compatibility-preserving binding strategy

The implementation does not insert height into any historical fixed or custom binding range. `MaterialLayerSemantic::Custom` remains enum value 9 and `Height` is appended as value 10. Historical custom authoring starts remain 5/7/9.

`FMaterial` appends height after every existing fixed and material-custom layer. Vulkan publishes the same order and records the actual relative descriptor position in `SurfaceUniforms::uHeightTextureIndex`. When a global shader replaces the ordinary custom set, material height is appended after the global shader's existing custom textures.

Palette/indexed material routes deliberately omit height and expose index -1, preventing linear height data from being reinterpreted as palette indices. Height does not participate in Default/Specular/PBR shader-model selection.

## Implementation summary

The accepted implementation:

- extends `MaterialLayers` / `FMaterialLayers` with optional height and per-semantic sampling state;
- adds GLDEFS height authoring, automatic height-map lookup and optional semantic filter overrides;
- preserves existing material-layer order while appending height;
- extends Vulkan material descriptor publication with a separate height index;
- appends the height index to the CPU/GLSL `SurfaceUniforms` ABI without changing established field offsets;
- exposes `HasMaterialHeightMap` and `SampleMaterialHeight` for custom/later shaders;
- extends SDVK-002 material diagnostics to observe actual height binding, resource and selected sampler state;
- extends deterministic material-stress and sprite-mirror native fixtures with height-present, height-absent and mixed-sampling cases.

No POM, displacement, explicit sprite TBN, lighting recalibration or quality policy is included.

## Semantic compatibility matrix

| Case | Expected contract | Evidence | Result |
|---|---|---|---|
| Albedo only / no height | no height layer; index -1; historical binding/sampler behavior | universal native material observer + material-stress | PASS |
| Legacy normal/specular + height | height appends at relative binding 6 | native `SM0001` | PASS |
| PBR + height | height appends at binding 8 | native `SM0006` | PASS |
| Custom PBR + height | historical custom stays binding 8; height is binding 9 | native `SM0002/10/18/26/34/42/50/58` | PASS |
| Pixel-crisp albedo + filtered data | albedo nearest while normal/PBR/height use independently authored linear+miplinear sampling | native `SM0001/SM0006/SM0002` | PASS |
| Sprite + height | sprite material keeps existing route; height binding 6 | native sprite-mirror `SDVRA1` | PASS |
| Indexed/palette | no height descriptor; index -1 | production contract + inherited indexed/PF tests | PASS |
| Missing/invalid height authoring | missing resource stays unbound; malformed property/filter rejected | deterministic parser/source contract | PASS within stated native limit |

The native validator requires every observed authored height layer to have exactly the same binding as the shader-visible `height_texture_index`. Every observed material without authored height must report -1. This is checked from actual material draw records, not merely from generated declarations.

## Native height witnesses and sampling

The `material-stress` scene contains 64 authored materials and eleven height-authored cases. It runs with `gl_texture_filter=0`, allowing a direct mixed-policy witness:

- `SM0001`: albedo nearest, normal linear+miplinear, height linear+miplinear at binding 6;
- `SM0006`: albedo nearest, normal/metallic/roughness/AO/height independently linear+miplinear, height at binding 8;
- `SM0002`: custom PBR retains custom binding 8; height appends at 9; the actual custom shader calls `SampleMaterialHeight`.

The `sprite-mirror` scene adds height to `SDVRA1`; the native material observer verifies binding 6 and the linear+miplinear sampler while the existing mirrored/rotated sprite path remains active.

These state assertions execute for every observed frame in the state captures. A declaration that never reached the intended draw path cannot satisfy them.

## Descriptor/lifetime qualification

SDVK-005 does not create a new resource identity domain. Height is a trailing member of the existing `VkMaterial` bindless allocation and is retired/rebuilt with that descriptor entry.

The accepted SDVK-004 authority remains unchanged:

- 4,096 dynamic descriptor capacity;
- 3,072 live/high-water deterministic stress descriptors (75%);
- 64 retire/reuse/rebuild cycles;
- stale-generation rejection and exact-size fresh-generation reuse;
- explicit exhaustion without emergency/global flush.

The complete PF/SDVK CPU oracle passes on the SDVK-005 final head and on the exact merged tree, including PF-003 and SDVK-004 lifetime/pressure contracts. Native resource observations also pass descriptor range/high-water validation. No new durable height index, global flush or cross-generation alias is introduced.

## State/image qualification

Exact-head and exact merged-master software-Vulkan qualification both pass the complete ten-scene authored state/image corpus:

- compositing;
- lights-zero;
- lights-one;
- lights-many;
- lights-dense-overlap;
- lights-dense-dispersed;
- shadow-boundary;
- material-stress;
- sun-probes;
- sprite-mirror.

Each scene uses two independent clean-state captures and comparison. Material-stress and sprite-mirror use the corpus's exact-RGB same-device policy and exact semantic-state assertions.

There was **no separate pre-SDVK-005 versus post-SDVK-005 screenshot campaign**. Compatibility for height-absent content is therefore not misrepresented as a cross-revision pixel result: it is established by preserved semantic enum/binding order, unchanged defaults for pre-existing channels, height index -1 when absent, the stock shader's lack of height consumption, focused compatibility fixtures and the complete current native corpus.

## Exact-head hosted qualification

Renderer source evidence run **38030309310**: PASS.

- source artifact: **11661084235**, 148,226,840 bytes;
- artifact ZIP SHA-256: `09119822f22eaa9b30c19f26702a16e5936422f2fcf8adcd411013e6648d20e7`;
- source bundle SHA-256: `ce1364229e0c30f339dfa385181cd2004ee3eb7bc76b2eca0a503f63067d8de5`.

Continuous Integration run **38030309307**: **9/9 PASS**.

- CPU artifact **11661074342**, 72,902 bytes, SHA-256 `507dc5bd806995a364e93fd4477aa02a3e0770a6d2185d10d364b521066041fb`;
- software-Vulkan artifact **11661879396**, 406,339,631 bytes, SHA-256 `a8adbf60c24ad40d5f6dd464327214b8be1e8240a5afb2a4e6d7052b615f6ea8`.

## Exact post-merge master qualification

Renderer source evidence run **38032400496**: PASS.

- source artifact **11662896184**, 148,182,946 bytes;
- artifact ZIP SHA-256 `9a69c630cbe1caa36849e96710ea6f1d93618b37b2ad58cecf794fb49f06771a`;
- source bundle SHA-256 `2467a51b22d9ff79d6eebf2663bea06b0d6a551d0e635d67c987f6c27c8426f1`.

Continuous Integration run **38032400505**: **9/9 PASS**.

- CPU artifact **11662242038**, 72,902 bytes, SHA-256 `de08a1933a36748c601ba313e2b6d323c98006a3dff377af86e7dc4c048fba3d`;
- software-Vulkan artifact **11662978604**, 406,339,907 bytes, SHA-256 `63cbaa7e16ab9ec9a983709c796310f8bda2e925b385ab48498bf825e4e2e6a7`.

The post-merge tree exactly equals the qualified PR tree.

## Retained failures and repairs

No failed evidence was discarded:

1. Initial bot-authored bootstrap publication head `3eef734f0231bca7b0ae3de9ed1e1e8da9accba8` caused source/CI runs **38024107495 / 38024107513** to end `action_required` with zero jobs. The source tree was republished unchanged under a normal user-authored commit.
2. CI run **38029659189** on `53e040883e91841ac4b61cbec219e554b77f5428` failed the PF oracle because the bounded SWCanvas source-extraction harness omitted new inert height locals around the expanded production material body. CPU artifact **11661921285**, SHA-256 `d61eaf43641703a9fc9921b1852479cab0291fe84df66b14a05bcc9cbe55eb58`. The harness context was repaired in `9a87734357d15145ed791d89c4b98db94fb60cb6`; production material code was not changed by that repair.

## Scope and limitations

- No physical GPU was used or required. No GPU-performance claim is made.
- No POM, displacement or sprite tangent-basis implementation is included.
- Malformed height declarations are covered by deterministic parser/source contracts; no dedicated malformed native launch was necessary.
- Global-shader height publication is source/CI-qualified but does not have a separate dedicated native global-height fixture.
- Sprite height is exercised natively; no new model-height asset was added.
- The optional same-process material-stress reload sequence is not part of the hosted native lane; PF-003/SDVK-004 remain the rebuild/reuse authority.

These limits do not leave an SDVK-005 acceptance criterion dependent on representative physical-GPU behavior.

## Dependency disposition

**SDVK-005 is accepted, merged and verified.** After this acceptance record is itself merged and verified, #5 may close and **SDVK-007 / #7 is dependency-ready**.

SDVK-008 and SDVK-010 remain blocked by SDVK-007. SDVK-009 retains its independent physical-GPU qualification boundary.
