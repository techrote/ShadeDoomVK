# PF-008 — Material-layer semantic identity contract

Status: implementation contract for PF-008  
Issue: #25

## Purpose

PF-008 makes the material channels already present in the inherited renderer identifiable by semantic name without changing their historical shader binding order, texture selection, sampler selection, palette/translation behavior, placeholder behavior or visible output.

This is metadata and an adapter around the existing material model. It is not a new authoring model and does not introduce height/parallax/POM.

## Semantic identities

`MaterialLayerSemantic` names the existing channels:

- `Albedo` — the base texture;
- `Normal` — inherited normal map;
- `LegacySpecular` — inherited specular map used by the legacy normal+specular model;
- `Metallic`, `Roughness`, `AmbientOcclusion` — inherited PBR scalar maps;
- `Brightmap` — inherited brightmap/emissive-intent texture;
- `Detail` — inherited detail map;
- `Glow` — inherited glow map;
- `Custom` — an extension texture, with the original authoring slot recorded in `customIndex`.

`MaterialLayerSemanticKey` provides deterministic semantic identity matching. Fixed channels match by semantic name. Custom channels match by semantic name plus authoring slot, including the `-1` anonymous compatibility value used by the legacy three-argument `AddTextureLayer` adapter.

## Binding-order compatibility

PF-008 deliberately does **not** reorder descriptor bindings. `FMaterial::mTextureLayers` remains the single ordering truth for authored material layers consumed by Vulkan. The separately owned auxiliary palette row in the unaccepted #110 candidate below is not an authored layer or a second layer-order mechanism.

Representative inherited layouts remain:

- default material: `Albedo`, `Brightmap`, `Detail`, `Glow`;
- legacy specular: `Albedo`, `Normal`, `LegacySpecular`, `Brightmap`, `Detail`, `Glow`;
- PBR: `Albedo`, `Normal`, `Metallic`, `Roughness`, `AmbientOcclusion`, `Brightmap`, `Detail`, `Glow`;
- custom extension textures append after the fixed sequence exactly as before.

Absent bright/detail/glow textures still occupy their historical binding with the inherited placeholder texture. The semantic tag describes that binding's intended channel even when its source is the placeholder.

Custom texture arrays remain sparse at authoring time and compact in the historical binding array. `customIndex` preserves the original `0..14` custom slot so renderer diagnostics and later code can identify the semantic source without assuming that custom binding `N` came from authoring slot `N`.

`FMaterial::FindLayer()` is the explicit semantic-to-current-binding adapter. `GetLayerDiagnostic()` exposes binding, semantic, custom slot, source texture pointer, scale flags, clamp flags and inherited `MaterialLayerSampling` value without creating a second ordering mechanism.

## Vulkan descriptor and PF-003 lifetime invariants

For ordinary materials, `VkMaterial::GetDescriptorEntry()` allocates one contiguous PF-003 bindless range for the historical layer count and binds layers by array index. It chooses each authored layer's sampler from `GetLayerFilter(i)` and keys descriptor variants by clamp, translation/remap, global shader and palette mode. The #110 candidate's public indexed material has the explicit auxiliary-resource exception below.

PF-008 semantic metadata is **not** added to descriptor identity because it does not alter resource state. Slot allocation, generation/lifetime validation, lightmap reservations and descriptor cleanup remain governed by PF-003.

Indexed/palette paths, translations, canvases, warped materials and state-dependent global-shader extension binding remain unchanged. A global shader custom texture retains its existing custom-array slot as its extension identity; PF-008 does not repack or reinterpret those arrays.

### #110 public indexed material correctness exception — candidate / unaccepted

The preceding compatibility statements describe PF-008's historical scope. [#110](https://github.com/techrote/ShadeDoomVK/issues/110) separately repairs the inherited public `DTA_Indexed` / `DTA_TranslationIndex` path: its actual `CTF_Indexed` material contains only the albedo layer, while the old Vulkan consumer attempted three layers without provisioning the palette needed by `material_paletted.glsl`. This is a confirmed source/compiled-fixture defect, not an observed native crash. See [the blocker](PF-020-INDEXED-MATERIAL-BLOCKER.md) and [candidate implementation notes](PF-110-IMPLEMENTATION-NOTES.md).

The focused source candidate preserves that one authored albedo layer and publishes two real resources in one PF-003 block: translated one-mip `R8_UNORM` indices at offset 0 and an entry-owned, one-mip 256×1 `B8G8R8A8_UNORM` base-palette row at offset 1. The row is auxiliary shader data, not `GetLayer(1)`, a new semantic, a dummy layer or a repacking of ordinary/PBR/custom bindings. Its alpha is opaque, matching the existing paletted shader. Translation remains in the index-byte producer before `getTexel` inverse/colour operations; a translated palette row would change that order.

`VkHardwareTexture::GetIndexedMaterialImage()` retains active canonical-remap variants within the existing indexed hardware owner. Nonpositive, luminosity and inactive translations use the inherited unremapped byte policy; a positive invalid ID follows its actual resolved identity table rather than being assumed null. Numeric-ID replacement therefore selects the current canonical remap. Palette-index and RedIsAlpha interpretations remain separate. Index and row sampling are nearest with one mip; the candidate explicitly maps `CLAMP_XY_NOMIP` to `CLAMP_NOFILTER_XY`, avoiding accidental `CLAMP_CAMTEX` filtering while preserving the requested wrap/clamp axes. Ordinary per-layer override policy is unchanged.

Descriptor cleanup frees the PF-003 range and sends its row view/image to normal fence-controlled retirement; hardware reset retires every indexed variant. Ordinary state-driven palette mode, RedIsAlpha, global shaders and the separately provisioned SWCanvas route remain protected controls. Native image/state/validation, restart/SWCanvas controls, exact-head checks, review and merge verification are pending; these candidate statements do not accept #110 or PF-020.

### #112 sampled layout follows the selected image — candidate / unaccepted

[#112](https://github.com/techrote/ShadeDoomVK/issues/112) is a separate layout-declaration repair, not a PF-008 semantic/order change or #110 palette substitution. `VkDescriptorSetManager::SetBindlessTexture()` now takes an explicit image layout, defaults existing callers to `SHADER_READ_ONLY_OPTIMAL` and rejects layouts other than that state or `GENERAL`. Each of the four material base/layer/global-custom/indexed-palette bindings passes its selected owner's tracked `Layout`. The default remains appropriate for the audited uploaded fixed, colormap and probe images.

The existing software-paletted SWCanvas material keeps two independently produced layers: the host-written R8 framebuffer in `GENERAL` and its existing palette image in shader-read layout. Ordinary uploaded BGRA/R8 layers and the #110 owned palette row retain shader-read declarations. Shader selection, authored ordering, sampling, source pixels, palette/translation interpretation, cache keys, PF-003 tokens and fence retirement are unchanged. Original extracted bodies retain the wrong GENERAL/READ pairing; current extracted bodies pass R8/BGRA, repeated-use, resize and ordinary-image controls. Actual warm SWCanvas owners/presentation and native validation remain pending, so this is **TESTED BUT UNACCEPTED**, not acceptance of PF-020. [Detailed evidence and gates](PF-112-IMPLEMENTATION-NOTES.md).

## Sampling and authoring

`MaterialLayerSampling` remains inherited functionality. Existing GLDEFS/custom shader sampling overrides are preserved and continue to flow through `CustomShaderTextureSampling` and Vulkan sampler selection.

No existing material syntax is changed. PF-008 adds no color-space default changes and no sampler default changes. SDVK-005 owns later first-class height authoring and broader per-semantic authoring policy.

## Diagnostics and verification

`MaterialLayerDiagnostic` exposes machine-readable semantic/binding/source/sampling state. The PF oracle source-contract test verifies:

- every existing channel is explicitly tagged;
- legacy specular and PBR channel order is unchanged;
- placeholder bright/detail/glow bindings remain present and ordered;
- custom layer sampling is preserved and original custom slot indices survive compaction;
- Vulkan still consumes ordered layers and per-layer samplers rather than sorting by semantic identity;
- no height/parallax/POM semantic is introduced.

The compiled adversarial fixture checks every semantic name, invalid-enum diagnostics, fixed-channel matching and custom-slot boundaries including slots 0 and 14 plus the anonymous `-1` compatibility slot.

## Provenance and protected semantics

No donor code is introduced by PF-008. Per-layer sampling was already present in the VKDoom baseline; the GriddleVK entry in `04-DONOR-PROVENANCE.md` remains historical provenance only.

Gameplay/tic state, material authoring meaning, shader selection, palette/translation semantics, sprite conventions, portals, audio, source ownership and donor provenance are unchanged.
