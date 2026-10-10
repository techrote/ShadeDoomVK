# SDVK-005 — final acceptance

Date: 2026-10-10. Owner: SDVK-005 / #5. Status: **accepted substantive implementation; acceptance reconciliation PR #134 pending its own merge verification**.

## Disposition and exact implementation identities

SDVK-005 is substantively implemented, merged and verified on the exact implementation tree.

- Starting master: `0a2fbad203549d18ac6e5a61bb4747709637bfde`
- Substantive PR: #132
- Acceptance reconciliation PR: #134
- Final substantive head: `9a87734357d15145ed791d89c4b98db94fb60cb6`
- Tested PR merge ref: `116a45bf47dc4595ead106ce99588723750d4d5d`
- Tested tree: `28f2ef41a99ea6979145030e807c7798c6e01735`
- Substantive merge/master: `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`
- Merged tree: `28f2ef41a99ea6979145030e807c7798c6e01735`
- Tested-tree == merged-tree: **PASS**

No physical-GPU qualification is required or claimed.

## Accepted height semantic contract

`height` is an optional first-class material semantic.

- Semantic identity: `MaterialLayerSemantic::Height == 10`, appended after historical `Custom == 9`.
- Data meaning: normalized scalar **linear data**, sampled from the red channel.
- Default height sampling: linear minification, linear magnification, linear mipmap interpolation, repeat addressing, using the existing `MaterialLayerSampling::LinearMipLinear` override sampler.
- Author overrides: `filter nearest`, `filter linear`, and `filter default`.
- Missing height: no height descriptor is published and shader-visible `uHeightTextureIndex == -1`; `SampleMaterialHeight` returns 0 only when explicitly called.
- Stock material shading does not sample height. No POM, relief, displacement or sprite tangent-basis behavior is introduced.
- Indexed/palette material routes deliberately omit height rather than interpreting scalar height data as palette/index data.

## Compatibility and binding strategy

No historical fixed or custom material binding is renumbered.

Height is appended after all existing fixed and custom bindings. Native authored witnesses include:

| Material case | Preserved historical state | Height binding |
| --- | --- | ---: |
| ordinary albedo-only + height | albedo binding 0 | 4 |
| legacy normal/specular + height | existing normal/specular prefix retained | 6 |
| ordinary PBR + height | existing PBR prefix retained | 8 |
| custom PBR + one historical custom texture | custom texture remains binding 8 / custom index 0 | 9 |
| sprite legacy material | albedo/normal/specular path retained | 6 |

GLDEFS custom-user starts remain 5/7/9. The compiled binding fixture additionally exercises the inherited 15-custom-texture boundary and proves height follows all fifteen rather than stealing an existing slot.

## Per-layer policy qualification

Existing semantic channels retain their inherited default sampling. The new semantic-layer authoring block allows explicit per-channel overrides.

The native `material-stress` and `sprite-mirror` recipes run with `gl_texture_filter=0`, so the base/albedo sampler remains nearest while selected normal/PBR/height layers explicitly resolve to linear min/mag + linear mipmap. The state oracle requires the actual sampler arguments, not just the author declaration.

The accepted mixed-policy witnesses include:

- legacy material: albedo nearest, normal linear+miplinear, height linear+miplinear;
- PBR material: albedo nearest, normal/metallic/roughness/AO/height linear+miplinear;
- custom PBR material: historical custom binding 8 retained, height appended at 9.

## Authoring/parser behavior

The GLDEFS material parser accepts `height "texture"` alongside the existing semantic layers.

Malformed semantic-layer properties and unknown filter values fail through `ScriptError`. A missing referenced height texture follows the existing missing-layer diagnostic and does not create a valid authored height binding.

Automatic material discovery uses `materials/heightmaps/<name>`.

## Shader and native draw witness

`SurfaceUniforms::uHeightTextureIndex` carries the actual relative descriptor index, or -1 when unavailable.

`HasMaterialHeightMap()` and `SampleMaterialHeight()` expose the optional channel to custom/later shaders. The stock `SetMaterialProps` path deliberately contains no height sample.

The authored custom material-stress shader actually calls `SampleMaterialHeight(vTexCoord.st)`, so qualification includes an executed shader consumer rather than declaration-only evidence.

The SDVK material observer emits semantic `height`, binding, requested/actual sampler and `height_texture_index`. Validation rejects any mismatch between the authored height binding and the shader-visible index.

## Descriptor/lifetime qualification

SDVK-005 creates no new identity or allocator system. Height is one trailing member of the existing `VkMaterial` bindless span and retires/rebuilds with that descriptor entry.

The exact-head and post-merge PF contract oracle rerun the accepted PF-002/PF-003/SDVK-004 lifetime/pressure coverage on the SDVK-005 tree. The inherited deterministic stress reaches 3,072 / 4,096 dynamic descriptors (75%), performs 64 rebuild cycles and stale-generation/reuse/exhaustion controls, and preserves explicit bounded failure rather than global flush.

Height publication therefore inherits the accepted generation/epoch ownership. No independent durable height index, emergency descriptor flush or cross-generation alias is introduced.

## Native state/image qualification

PR-head software-Vulkan artifact: **11661879396**, 406,339,631 bytes, SHA-256 `a8adbf60c24ad40d5f6dd464327214b8be1e8240a5afb2a4e6d7052b615f6ea8`.

Exact merged-master software-Vulkan artifact: **11662978604**, 406,339,907 bytes, SHA-256 `63cbaa7e16ab9ec9a983709c796310f8bda2e925b385ab48498bf825e4e2e6a7`.

Both runs pass the complete ten-scene software-Vulkan state/image qualification:

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

Each scene uses two independent state/image captures and comparison. `material-stress` proves world-surface height present/absent, legacy, PBR, custom shader and mixed filtering. `sprite-mirror` proves the height semantic on the sprite material path in the existing mirror/orientation corpus.

Existing no-height behavior is protected by binding/source contracts and the unchanged stock shader path, plus repeated current-tree native state/image comparison. A separate historical-master-vs-new-master cross-tree pixel diff was **not** performed and is not claimed.

## Exact hosted qualification

### Final implementation head

- Renderer source evidence run **38030309310**: PASS
  - artifact **11661084235**
  - artifact bytes **148,226,840**
  - artifact ZIP SHA-256 `09119822f22eaa9b30c19f26702a16e5936422f2fcf8adcd411013e6648d20e7`
  - source bundle SHA-256 `ce1364229e0c30f339dfa385181cd2004ee3eb7bc76b2eca0a503f63067d8de5`
- Continuous Integration run **38030309307**: **9/9 PASS**
  - CPU artifact **11661074342**, 72,902 bytes, SHA-256 `507dc5bd806995a364e93fd4477aa02a3e0770a6d2185d10d364b521066041fb`
  - software-Vulkan artifact **11661879396**, 406,339,631 bytes, SHA-256 `a8adbf60c24ad40d5f6dd464327214b8be1e8240a5afb2a4e6d7052b615f6ea8`

### Exact merged master

- Renderer source evidence run **38032400496**: PASS
  - artifact **11662896184**
  - artifact bytes **148,182,946**
  - artifact ZIP SHA-256 `9a69c630cbe1caa36849e96710ea6f1d93618b37b2ad58cecf794fb49f06771a`
  - source bundle SHA-256 `2467a51b22d9ff79d6eebf2663bea06b0d6a551d0e635d67c987f6c27c8426f1`
- Continuous Integration run **38032400505**: **9/9 PASS**
  - CPU artifact **11662242038**, 72,902 bytes, SHA-256 `de08a1933a36748c601ba313e2b6d323c98006a3dff377af86e7dc4c048fba3d`
  - software-Vulkan artifact **11662978604**, 406,339,907 bytes, SHA-256 `63cbaa7e16ab9ec9a983709c796310f8bda2e925b385ab48498bf825e4e2e6a7`

## Retained adverse evidence

1. Initial PR publication head `3eef734f0231bca7b0ae3de9ed1e1e8da9accba8` was authored by `github-actions[bot]` via the self-removing bootstrap publication mechanism. Runs **38024107495** and **38024107513** ended `action_required` with zero jobs. This was a GitHub workflow-trigger condition, not renderer evidence.
2. PR head `53e040883e91841ac4b61cbec219e554b77f5428` reached the CPU oracle in run **38029659189** and failed after 697 tests because the bounded PF-020 SWCanvas source-extraction wrapper did not declare the new inert surrounding height locals. Artifact **11661921285**, SHA-256 `d61eaf43641703a9fc9921b1852479cab0291fe84df66b14a05bcc9cbe55eb58`. Production material code was not implicated. The fixture was repaired in `9a87734357d15145ed791d89c4b98db94fb60cb6` and the complete gate requalified.
3. Duplicate retrigger CI run **38029639621** was cancelled by workflow concurrency after a newer run superseded it; it is not counted as qualification evidence.

No failure was waived.

## Scope and limitations

- No POM, relief, displacement or geometry modification.
- No SDVK-007 sprite tangent-basis implementation.
- No SDVK-009 many-light architecture change.
- No SDVK-010 IBL/probe policy change.
- No SDVK-016 quality-tier policy.
- No physical-GPU performance or compatibility claim.
- Native near-device-capacity exhaustion and same-process reload remain bounded by inherited CPU contracts rather than deliberate GPU exhaustion.
- No separate historical-master-vs-SDVK-005 pixel-diff campaign was performed.

## Final gate

The substantive implementation satisfies SDVK-005's acceptance criteria on exact merged master `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`.

After this documentation-only acceptance reconciliation itself passes required checks, merges and its resulting master is verified:

- **SDVK-005 / #5: ACCEPTED, MERGED AND VERIFIED**
- **SDVK-007 / #7: DEPENDENCY-READY**
