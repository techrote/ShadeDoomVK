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

PF-008 deliberately does **not** reorder descriptor bindings. `FMaterial::mTextureLayers` remains the single binding-order truth for authored layers consumed by Vulkan. A shader-required auxiliary palette resource is not an authored material layer.

Representative inherited layouts remain:

- default material: `Albedo`, `Brightmap`, `Detail`, `Glow`;
- legacy specular: `Albedo`, `Normal`, `LegacySpecular`, `Brightmap`, `Detail`, `Glow`;
- PBR: `Albedo`, `Normal`, `Metallic`, `Roughness`, `AmbientOcclusion`, `Brightmap`, `Detail`, `Glow`;
- custom extension textures append after the fixed sequence exactly as before.

Absent bright/detail/glow textures still occupy their historical binding with the inherited placeholder texture. The semantic tag describes that binding's intended channel even when its source is the placeholder.

Custom texture arrays remain sparse at authoring time and compact in the historical binding array. `customIndex` preserves the original `0..14` custom slot so renderer diagnostics and later code can identify the semantic source without assuming that custom binding `N` came from authoring slot `N`.

`FMaterial::FindLayer()` is the explicit semantic-to-current-binding adapter. `GetLayerDiagnostic()` exposes binding, semantic, custom slot, source texture pointer, scale flags, clamp flags and inherited `MaterialLayerSampling` value without creating a second ordering mechanism.

## Vulkan descriptor and PF-003 lifetime invariants

For ordinary materials, `VkMaterial::GetDescriptorEntry()` continues to allocate one contiguous PF-003 bindless range for the historical layer count and binds layers by array index. It still chooses each sampler from `GetLayerFilter(i)` and still keys descriptor variants by clamp, translation/remap, global shader and palette mode.

PF-008 semantic metadata is **not** added to descriptor identity because it does not alter resource state. Slot allocation, generation/lifetime validation, lightmap reservations and descriptor cleanup remain governed by PF-003.

Within PF-008's accepted metadata-only change, indexed/palette paths, translations, canvases, warped materials and state-dependent global-shader extension binding remained unchanged. The focused public-indexed and descriptor-layout correctness exceptions below are separately owned by #110/#112. A global shader custom texture retains its existing custom-array slot as its extension identity; PF-008 does not repack or reinterpret those arrays.

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

## Focused #110/#112 material corrections — repair contract

The supported public `DTA_Indexed` material has one authored albedo layer. [#110](https://github.com/techrote/ShadeDoomVK/issues/110) replaces its inherited three-descriptor/missing-layer consumer with exactly two real contiguous PF-003 resources: the canonical-remap-specific one-mip R8 index image and an entry-owned opaque 256x1 BGRA base-palette row. Translation remains in the index bytes before existing inverse/additive/object-colour shader operations; moving it to the row is not equivalent. The row has no invented semantic layer or authoring slot. Index and palette lookup remain discrete under both global filters. Ordinary layer ordering, placeholders, state-driven palette, RedIsAlpha and separately provisioned SWCanvas remain protected. See [identity, producer and retirement evidence](PF-110-IMPLEMENTATION-NOTES.md).

[#112](https://github.com/techrote/ShadeDoomVK/issues/112) passes the actual selected owner's tracked layout at all four material publication sites. The bindless writer defaults to READ for audited uploaded-image callers and guards READ/GENERAL. Real paletted SWCanvas retains its existing mapped R8 GENERAL plus palette READ pair; layout declaration adds no producer, transition, pixel reinterpretation, cache key or retirement rule. See [software-image evidence limits](PF-112-IMPLEMENTATION-NOTES.md).

Candidate4's normal native matrix is historical evidence for its exact source. Candidate5 native qualification is verified below; release integration is tracked in the source issues; no final acceptance, performance gain or PF-020/SDVK-001 unblock is recorded here.


## Verified candidate5 native qualification

The final clean candidate passes all twelve normal mode/filter cases and both
genuine one-process core/sync restarts, with zero requested-validation errors or
warnings, unchanged pins and all294 presentation ROIs. Strict PF393/393, four
standalone contracts, CFX8/8 and deterministic source oracles pass.
See [source and acceptance scope](PF-110-IMPLEMENTATION-NOTES.md) and
[compact independently reviewed qualification](PF-110-FINAL-NATIVE-VERIFICATION.json) for hashes, methods,
retained failures and unmeasured mode1/SW-retirement/performance limits.
Focused release integration is tracked in #110/#112; PF-020 and SDVK-001 remain
separate blocked gates.
