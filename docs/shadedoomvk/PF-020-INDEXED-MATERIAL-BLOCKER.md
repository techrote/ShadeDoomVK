# PF-020 — supported indexed 2D material blocker

Status: **OPEN RELEASE BLOCKER**, tracked as [issue #110](https://github.com/techrote/ShadeDoomVK/issues/110). This is an independent inherited defect found during PF-020 synthesis. It is not covered by the narrow GLDEFS custom-sampling repair and is not waived as future renderer work.

Audit source: `master@4df7dea1338f063c6417e024f967bfa4aa23edd4`, focused branch `codex/pf020-native-freeze`. Evidence below is source/control-flow evidence. No GPU execution, physical failure, crash, visual comparison or performance measurement was performed for this finding.

## Counterexample and source chain

The public ZScript drawing API exposes `DTA_Indexed` and describes its meaning as using an indexed texture with the given translation. A valid ordinary texture drawn from a screen drawing callback with `DTA_Indexed, true` reaches the unsafe descriptor branch. Supplying a valid translation does not provision the missing material layers.

```text
Screen.DrawTexture(validTexture, false, x, y,
                   DTA_Indexed, true,
                   DTA_TranslationIndex, validTranslation);
```

This is a minimized source-derived counterexample, not a retained executed mod or a GPU reproducer. The texture, callback context and translation must be valid in an eventual production fixture.

| Step | Exact current source | Observation |
|---|---|---|
| Public authoring route | `wadsrc/static/zscript/engine/base.zs:473`, `:524`, `:557`; `src/common/2d/v_draw.h:132` | `DTA_Indexed` is a public DrawTexture tag; Screen and FCanvas accept varargs. |
| Actual VM route | `src/common/2d/v_draw.cpp:238–260`, `:1373–1375` | The VM forwards tags to `ParseDrawTextureTags`; that tag sets `DrawParms::indexed`. |
| Actual command construction | `src/common/2d/v_2ddrawer.cpp:444` | `indexed` sets `F2DDrawer::DTF_Indexed`. |
| Material selection | `src/common/rendering/hwrenderer/hw_draw2d.cpp:189–190`; `data/hw_renderstate.h:620–630` | Indexed draw selects `CTF_Indexed` and calls the ordinary material validation/binding boundary. |
| Variant normalization | `src/common/textures/hw_material.cpp:247` | An indexed request becomes precisely `CTF_Indexed`. |
| Layer producer | `src/common/textures/hw_material.cpp:87`, `:93–97`, `:206` | Constructor pushes one albedo layer, selects `SHADER_Paletted`, adds no palette/other layer in that branch, then shrinks the array. |
| Vulkan material construction | `src/common/rendering/vulkan/textures/vk_hwtexture.cpp:461–464` | Vulkan delegates to that constructor and registers the material; it adds no layers. |
| Descriptor consumer | `src/common/rendering/vulkan/textures/vk_hwtexture.cpp:523–537`, `:570–576` | Albedo's indexed flag selects a fixed count of three; consumer subsequently reads layers 1 and 2. |
| Layer access | `src/common/textures/hw_material.cpp:227–232` | `GetLayer` directly indexes the material array. Indexed translation handling changes the texture-cache translation to −1; it does not synthesize layers. |
| Actual render binding | `src/common/rendering/vulkan/vk_renderstate.cpp:463–471` | Material application calls `VkMaterial::GetBindlessIndex`, which reaches `GetDescriptorEntry`; no intermediate palette layer is added. |

The indexed constructor's array contains only element 0. Therefore reads of elements 1 and 2 are outside its constructed elements. `TArray::operator[]` is not a bounds-safe producer substitution, and `ShrinkToFit` is not evidence that the absent layers exist. In a normal first descriptor creation the out-of-range access is reached before any shader can repair the state. Exact physical behavior remains unmeasured.

## Palette and shader semantics checked

`src/common/rendering/vulkan/shaders/vk_shader.cpp:177` maps the paletted material to `shaders/scene/material_paletted.glsl` with `SHADERTYPE_PALETTE` and `PALETTE_EMULATION`. `wadsrc/static/shaders/scene/material_paletted.glsl:3–8` reads the index from albedo and explicitly samples `texture2` for its palette color; `binding_textures.glsl:7` identifies that as binding index 1. There is no conditional fallback in this material shader for an absent palette resource.

`FTexture::GetHardwareTexture` (`src/common/textures/texture.cpp:565–575`) selects a one-byte indexed hardware texture and the −1 cache translation; it does not append palette material layers. The ordinary image lookup and descriptor translation key are not themselves a valid shader palette producer.

The real software-scene presentation path is different. `src/rendering/swrenderer/r_swscene.cpp:72–78` creates `@@palette@@` from `GPalette.BaseColors`; `:101–105` validates a separately created `SWCanvas` material and appends that palette layer. Its wrapper selects `SHADER_Paletted` without giving the albedo `CTF_Indexed` in the common constructor, so normal `NumLayers()` descriptor construction can consume its two real layers. This does not initialize an ordinary texture's `CTF_Indexed` variant. The only other current `AddTextureLayer` call sites are wipe effects. No shared indexed-material palette/translation producer was found in the audited source.

Consequently, replacing the fixed descriptor count with one, suppressing out-of-range reads, or supplying a dummy neutral palette would not establish the promised palette/translation behavior. A safe repair needs an authoritative real palette/translation producer and the correct ordered binding contract. The historical reason for the third indexed binding has not been established; it must not be guessed.

## Ancestry and test gap

The founding `VKDoom@09634479ab5bf9adf691074fffe85a006a398cd0` contains both the one-layer indexed constructor and the fixed-three-layer Vulkan consumer. `git blame` assigns the fixed-three descriptor branch to `ba146ed5e51da7cf666dad42056d6f2bf78035ee` (2021-04-19); `git merge-base --is-ancestor ba146ed5e51da7cf666dad42056d6f2bf78035ee 09634479ab5bf9adf691074fffe85a006a398cd0` exits 0. This finding is inherited, not a demonstrated PF refactor regression or a new donor import.

The earlier Raze-derived common material code had an application-supplied `SetLayerCallback` seam for indexed layers 1 and 2, explicitly because common material code could not define palette selection. The backend update above retained that assumption. `102a189525d29b87cf6c3b33ab134eef1cb4c4bb` (2025-01-09, “Remove dead code in FMaterial”) removed the callback and conditional layer lookup; that commit is also ancestral to the founding baseline. `git grep SetLayerCallback` on its parent finds only the declaration/definition, no registering application caller. Restoring the deleted callback alone would therefore not establish a real producer. The older `wadsrc/static/shaders/glsl/func_paletted.fp` sampled the same `texture2` palette and forced opaque alpha; the historical three-binding consumer is not evidence of an active third-binding shader need in this Doom source.

Two current palette resources must not be confused with the missing layer. `VkTextureManager::SetGamePalette` (`src/common/rendering/vulkan/textures/vk_texture.cpp:266–283`) builds a 512×512 RGB666-to-nearest-palette-color LUT, consumed by `PickGamePaletteColor`; it is not an index-to-palette row. `GetSWColormapView` (`:318–364`) produces a 256×33 index/shade table with a separate base-palette row, consumed through an explicit `uColormapIndex`. Neither is automatically the `texture2` producer for a public indexed material or its requested translation.

PF-008 semantic tests exercise source routing and semantic keys; PF-013 tests exercise RedIsAlpha storage/descriptor interpretation, GGX numerical boundaries and precache flags. Neither constructs the public indexed material variant and executes its real descriptor layer traversal. Ordinary palette-mode rasterization of a normal material is distinct from constructing `FMaterial(..., CTF_Indexed)`; its success cannot close this gap.

## Smallest safe next action and gate

Keep PF-020 and SDVK-001 blocked on #110. First retain a bounded production-linked fixture that constructs the public indexed variant and observes actual layer count/descriptor access, with an ordinary non-indexed control and the real SWCanvas palette control. A source-extracted constructor/consumer fixture can prove the out-of-range state without inducing a GPU fault, but cannot establish visual palette correctness alone.

Then resolve the palette/translation producer contract from source history and the supported public API, implement a focused repair, and verify native output for several palette indices, translation and no-translation, transparency/RedIsAlpha distinctions, filtering/clamp, repeat material creation/descriptor retirement, and the unaffected ordinary/SWCanvas paths. Preserve the original failing producer or mutation as a negative regression. Do not intentionally induce device loss and do not use a CFX physical campaign for this bounded defect.

Translation reuse needs an explicit oracle: current `FTexture::CreateTexBuffer` (`texture.cpp:335–360`) can apply a remap while creating R8 indices, whereas an indexed hardware texture uses translation −1 for its owner/cache and `VkHardwareTexture` retains a single `mPaletteImage`. A future repair must prove that differently translated draws of the same source cannot inherit the first upload's remap. Either a neutral raw-index producer plus a canonical translated-palette consumer, or a correctly partitioned translated-index producer, needs source-established semantics and repeat-order tests. This is a required repair test, not a measurement of current GPU output.

Only after that separate repair is merged, source identity and required checks are verified, and its acceptance evidence is reconciled into the PF matrix may PF-020 reconsider the release gate. This notebook records a blocker; it is not acceptance evidence for a repair.

## Historical repair proposal — rejected after source-order audit

The neutral-index/translated-row proposal below is retained as a rejected approach, not implementation authority. The subsequent [source-order audit and candidate](PF-110-IMPLEMENTATION-NOTES.md) demonstrates that remap must remain before `getTexel` inversion and authored material operations: `BaseColors[255 - Remap[n]]` differs from `BaseColors[Remap[255 - n]]`. The implemented, still unaccepted candidate therefore retains canonical-remap-specific R8 images and a real unchanged base-palette row. Its production-linked CPU checks pass; native output/validation and release gates remain outstanding.

The current indexed upload rule supplies a bounded starting contract: for an active remap it writes `remap->Remap[originalIndex]`, and otherwise retains the original index. Combining that existing producer with the real base-palette lookup gives `GPalette.BaseColors[remap->Remap[index]]` for active translations and `GPalette.BaseColors[index]` otherwise. `FRemapTable::Palette` is separately documented as the ideal true-color palette; substituting it for the existing indexed `Remap` rule would change representation semantics and needs a separate decision.

A focused candidate can preserve one neutral, untranslated R8 index image and create a real 256×1 palette view for the canonical resolved remap, then bind the two actual resources consumed by the current shader. Palette ownership/cache identity and retirement must follow the accepted generation/descriptor lifetime contracts, with bounded reuse; no per-draw resource creation or dummy binding is proposed. The historical third callback binding may be removed only with a demonstrated actual-shader/descriptor contract, while SWCanvas's separately owned two-layer presentation remains intact. Preserve the current paletted shader's opaque-alpha behavior; RedIsAlpha and ordinary palette-mode rendering remain distinct paths.

This proposal still requires implementation and production-linked verification. Decisive translation cases are same-source A/B/A draws in both first-use orders, inactive/identity/invalid translation fallbacks, replacement through `PaletteContainer::UpdateTranslation`, the current luminosity-translation policy, and descriptor cleanup/recreation. Exact palette-index color readbacks must prove the candidate follows the established producer rule and that a warmed first translation cannot contaminate a later one. Style/alpha/clamp and ordinary/SWCanvas controls must prevent accidental broader compatibility changes. No candidate was implemented or measured in this audit.
