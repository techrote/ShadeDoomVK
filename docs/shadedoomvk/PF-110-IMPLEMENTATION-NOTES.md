# #110 — indexed material candidate and acceptance plan

Status: **source candidate / unaccepted**. This records the focused implementation, prepared route and explicitly bounded native partial evidence. Issue: [#110](https://github.com/techrote/ShadeDoomVK/issues/110). The source chain and ancestral defect are recorded in [the blocker notebook](PF-020-INDEXED-MATERIAL-BLOCKER.md). PF-020 and SDVK-001 remain blocked until the repaired path has complete production-linked state, image, lifetime and exact-head gate evidence.

The audit uses the focused ShadeDoomVK checkout based on `4df7dea1338f063c6417e024f967bfa4aa23edd4`. Numbered source references below identify the audited pre-#110 bodies; candidate code moves them. Current candidate entrypoints are identified by symbol. The separate GLDEFS parser repair is not acceptance evidence for #110.

## Keep translation before the existing shader operations

The authoritative indexed producer is `FTexture::CreateTexBuffer`, `src/common/textures/texture.cpp:335–360`. It obtains `Get8BitPixels(false)`, flips the column layout and, for a positive non-luminosity active translation, changes each byte using `FRemapTable::Remap[byte]`. It does **not** use the ideal `FRemapTable::Palette` used by the true-colour branch at lines 376–381. `palettecontainer.h:32–33` explicitly distinguishes those arrays.

`material_paletted.glsl:4–8` then calls the existing `getTexel`, turns its red component into a palette coordinate, reads binding 1 (`texture2`) and forces output alpha to one. `material_gettexel.glsl:8–72` applies texture modes and authored colour operations before that lookup. Retain this order and shader behaviour, including its opaque palette output; do not introduce sRGB conversion, a different alpha interpretation or an ideal-palette translation as part of the provisioning repair.

**Rejected proposal:** an untranslated shared R8 image plus a translated palette row is equivalent only when the intervening shader transformation commutes with the remap. It is not a safe general repair. For `TM_INVERSE`, existing `.r = 1 - .r` yields:

```text
old:      BaseColors[255 - Remap[n]]
proposed: BaseColors[Remap[255 - n]]
```

For `n=5`, `Remap[5]=10`, `Remap[250]=20`, those indices are 245 and 20. Select unequal actual base-palette colours for the fixture. Colour multiply/add and other shader operations need the same ordering check. The neutral-image/translated-row suggestion in the earlier blocker notebook is provisional and superseded by this counterexample; it must not be promoted to an accepted contract.

## Small coherent resource repair

The focused source candidate implements the audited direction: preserve the actual translated R8 producer, partition its resident images by resolved translation within the existing hardware-texture owner, and publish a real unchanged base-palette row beside each indexed descriptor entry. These are candidate resource rules pending native and release evidence.

1. Keep `FMaterial`'s one actual albedo layer and its public `CTF_Indexed` variant identity. Its current `GetLayer`/`FTexture::GetHardwareTexture` forced `translation=-1` owner is not permission to fabricate layer 1 or 2.
2. Within that owner, select a palette-index image by the effective canonical remap identity. Nonpositive ID, luminosity ID or an inactive resolved table follows the existing unremapped byte policy. A positive invalid ID resolves through `TranslationToTable` to the canonical identity table: preserve that table's actual `Remap` bytes and inactive state rather than assuming invalid input always means a null remap. Any active canonical table selects a distinct translated image. Keep palette-index and RedIsAlpha image interpretation separate, as required by PF-013. A same-source A/B/A sequence must retain both image contents and revisit A correctly regardless of first-use order.
3. An indexed `DescriptorEntry` owns a real 256×1, one-mip, `B8G8R8A8_UNORM` palette image and view containing the current `GPalette.BaseColors` row. There is no translation in this row. Its creation uses the existing staging allocation, image/view builders and `VkImageTransition`. Existing shader binding 1 consumes this row. A row costs 1,024 source texel bytes; Vulkan allocation size is not inferred from that number.
4. Allocate exactly one contiguous PF-003 block of two descriptors, publish the translated index view at offset 0 and the real palette row at offset 1. Do not call `GetLayer(1/2)`, add dummy textures, reduce to one descriptor or consume reserved fixed slots. The old third descriptor has no consumer in `material_paletted.glsl`; removing it is justified by the actual two-resource shader contract, not by suppressing the missing palette.
5. Preserve the ordinary material, ordinary state-driven palette mode, RedIsAlpha, global-shader and separately provisioned SWCanvas paths. `state.mPaletteMode` and `layer->scaleFlags & CTF_Indexed` are different conditions. Retain the PF-017 descriptor equality fields: resolved clamp, remap/luminosity identity, complete `GlobalShaderAddr`, palette mode and normalized RedIsAlpha. Any deliberate new normalization must have an explicit equivalence fixture rather than silently changing unrelated keys.

`VkHardwareTexture::GetIndexedMaterialImage()` maintains separate canonical-remap maps for palette-index and RedIsAlpha interpretation, and `VkMaterial::CreateIndexedPalette()` creates the unchanged base row owned by `DescriptorEntry::IndexedPalette`. `mTextureLayers` remains the ordering authority for authored layers; the auxiliary row has no material semantic or invented layer index. Ordinary default/specular/PBR/custom ordering and placeholders remain intact.

The candidate uses a palette row per existing descriptor-cache entry rather than a global shared palette cache. That retains a clear owner and avoids an additional global invalidation system. Sharing or lookup optimization is not required for this correctness fix, and no performance benefit is claimed.

### Sampling

The index image must be sampled discretely; interpolated index bytes name other palette colours. The existing no-filter normalization in `GetDescriptorEntry:499–506` applies to state-driven palette mode, while the public material-indexed variant has `MaterialLayerSampling::Default`. `getTexel` uses ordinary `texture()` sampling. The candidate must establish a nearest index sampler that retains the requested wrap/clamp behaviour for the actual indexed branch.

The candidate uses an explicit nearest, clamped palette-row sampler. `VkSamplerManager`'s `CLAMP_XY_NOMIP` is not an unconditional nearest policy: lines 146–151 use the configured global magnification filter. `CLAMP_NOFILTER_XY`, built at lines 155–164, provides nearest min/mag sampling and a bounded LOD. The indexed clamp adapter explicitly maps `XY_NOMIP` to `NOFILTER_XY`; blindly adding `NOFILTER` would select `CAMTEX`. A native off-grid/boundary fixture under both nearest and linear global settings must prove that the index lookup does not change. Preserve the existing no-mip R8 upload; do not generate averaged index mipmaps.

The original non-mip `CreateTexture` and `UploadTexture` branches copied into `TRANSFER_DST_OPTIMAL` without the final sampled-layout transition. The candidate adds an explicit transition to `SHADER_READ_ONLY_OPTIMAL` in both non-mip branches, while the existing mipmapped `GenerateMipmaps()` path remains unchanged. Exact original bodies remain negative fixtures. This is a correctness exception to PF-005's historical transition-preservation statement, not a filtering/mip quality trade.

## Translation identity and deferred upload

`PaletteContainer::UpdateTranslation:224–228` calls `AddRemap` and replaces a numerical translation-table entry with a canonical arena pointer. Distinct canonical remaps therefore need distinct resident indexed images and descriptor state even when the public translation ID is unchanged. `CopyTranslation` may alias a canonical pointer; cache reuse in that case is legitimate. An inactive remap must follow the current unremapped producer policy. Luminosity translation is not applied by the indexed producer; do not apply the true-colour luminosity conversion to these bytes.

Canonical pointers are owner-local identities, not persistent identifiers. `PaletteContainer::Clear:158–162` frees the arena; `SetPalette:70–89` mutates the identity remap and base colours. A positive invalid translation resolves to this canonical identity table; the indexed producer applies its actual bytes when active and bypasses it when inactive. During internal restart, `d_main.cpp:4010` deletes texture/material owners before the next `InitPalette:3262`. Preserve that ordering and test it. Do not assume a canonical pointer remains valid across restart or arena reset.

**Deferred-content hazard:** the historical `VkHardwareTexture::CreateImage:211–220` captures the numerical translation ID for the worker. A numerical A→B update before worker production can write B bytes into an image keyed as A. Pointer-keyed lookup alone does not repair that hazard. For indexed input the `CTF_CheckOnly` producer already emits complete R8 bytes; this branch ignores the check/process flags. The candidate's material-specific selector calls `CreateImage(..., allowAsync=false)`, producing and uploading the actual bytes synchronously on the owner thread. It does not queue a later numeric-ID repeat. Generic `GetImage` retains the inherited async path and PF-005 target/manager checks; unrelated asynchronous true-colour and state-driven RedIsAlpha loading are not disabled.

Required identity witnesses include A/B/A and B/A/B on one source owner, same numerical ID replacement, inactive/default/invalid/luminosity policies, repeated cache lookup, proof that public indexed production queues no deferred numeric-ID upload, rejection of old generic upload tickets after reset, and reload after the palette arena is rebuilt. A cache-only test that resolves B after both uploads have finished does not prove the asynchronous policy.

## Retirement and staging

The candidate's `DeleteDescriptors()` frees each descriptor block and calls the entry row's `VkTextureImage::Reset(fb)` before clearing entries. The resources enter `DrawDeleteList`, not immediate native destruction. Hardware-texture `Reset()` retires every translated-index image variant, advances its upload epoch and retains pending-work cancellation. Neither an ordinary material nor an old cached entry may retain a dangling view.

`VkImageTransition` tracks layout. A palette upload should use UNDEFINED → TRANSFER_DST → SHADER_READ_ONLY with the existing transfer-to-fragment access dependency, one mip and the staging allocation's `bufferOffset`. `StageTextureUpload:132–188` provides a bounded arena; wrap waits before aliased staging bytes are overwritten. `FinishTextureUpload:191–200` handles dedicated uploads. The 1,024-byte row fits the ordinary staging path. Use these APIs instead of inventing an untracked staging buffer owner.

`FlushCommands:225–260` publishes pending bindless writes before command submission; `WaitForCommands:266–309` waits the fences before releasing frame objects. `DeleteFrameObjects:322–330` distinguishes transfer-only and draw retirement lists. Test row destruction/reset using this lifetime contract, including descriptor generation changes and no image release before the owning draw fence.

`UpdatePalette:553–558` currently refreshes the tonemap/RGB666 LUT; it is not a general material-row invalidation hook. A candidate must not clear rows globally while published material descriptors survive. The current per-material owner/restart sequence avoids such a shared cache. If a new operation can mutate base-palette bytes while those owners stay live, it needs an explicit scoped rebuild/epoch and production-linked lifetime proof before acceptance, not an emergency global descriptor flush.

## Actual native acceptance route

The candidate prepares `pf_indexedmaterial_validate`, implemented in `src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp`, and synthetic runtime inputs from `tools/pf_oracle/prepare_indexed_material_runtime.py`. Their existence and successful native compilation are not execution or acceptance evidence.

The prepared command runs on the renderer-owner thread after a clean small startup, validates synthetic 16×4 PF110SRC/PF110SA/PF110SB inputs and renders its own 128×20 target through the real `DrawTexture` tag parser → `F2DDrawer` → `Draw2D(F2DDrawer*, FRenderState&, x,y,w,h)` → material → Vulkan shader route. It retains source pixels, tags, numerical translation IDs and canonical identities. The public ZScript equivalent is a registered `RenderOverlay(RenderEvent)` callback using `DTA_Indexed` and **`DTA_TranslationIndex`**; calling `Screen.DrawTexture` outside a draw callback is rejected by the VM at `v_draw.cpp:256`.

The raw command prepares 22 draws covering normal/inverse output, A/B/A and B/A/B first use, numeric-ID replacement/restoration, default/invalid/inactive/luminosity input, off-grid/no-mip sampling, queued-draw retirement and recreation. It reads actual resident R8, base-row and target RGBA bytes, checks complete registered remap rows, actual shader/PF descriptor identity and zero new indexed async jobs. Ordinary state-driven palette/RedIsAlpha checks are descriptor/resident-byte controls, not software-colormap shader parity. The ordinary output is retained without claiming the indexed palette equation applies to it. Missing input emits no draw. These are implemented assertions awaiting native execution; palette-arena restart and real SWCanvas acceptance remain separate production-linked controls.

The overlay's `DTA_Color` control must not be described as direct `getTexel` object-colour tint. `v_draw.cpp` parses it into `parms.color`; `F2DDrawer::SetStyle` combines vertex colour, then indexed `AddTexture` records its luminance in `mLightLevel` and replaces vertex colour with white. `Draw2D` forwards that value via `SetSoftLightLevel`; shader `SIMPLE2D` processing is a separate downstream boundary. The literal translated PF110RA reference therefore uses the same indexed route, translation 0 and identical style/tag. This controls the public authored-colour route without claiming a visible tint effect or native `uObjectColor` ordering. The source-extracted scalar CPU oracle separately covers `getTexel` additive/object-uniform ordering; raw inverse draws exercise the full actual shader's noncommuting transformation.

For exact byte evidence, prefer an own small colour/depth target and explicit readback with production builders/transitions. The colour image needs COLOR_ATTACHMENT and TRANSFER_SRC usage, and the depth/stencil format must come from the actual device capability result. Use neutral draw state for the base-palette equation, then separately exercise inverse and authored colour controls. Restore the prior render target/state after the diagnostic. Clear/end the diagnostic render pass, transition to TRANSFER_SRC, copy to a GPU-to-CPU staging buffer, wait via the normal command manager, map and retain actual bytes. Read back the resident R8 source and palette row as well as the shader result; pair image assertions with published descriptor/view identity.

`RenderTextureView(FCanvasTexture*, callback):415–446` demonstrates existing target switching and production rendering, but its default canvas image allocation does not request TRANSFER_SRC. Do not directly copy that image without establishing the required usage. A dedicated diagnostic target can reuse the same builders and `SetRenderTarget` boundary. No CPU-computed colour may be labelled as a Vulkan result.

`GetScreenshotBuffer:644–662` and the existing `screenshot` command provide presentation evidence. They run the postprocess/present path and convert into RGB bytes; they do not expose exact raw R8/palette data or isolate the material shader. Keep their configuration and output as complementary evidence, not as a replacement for raw-image/state assertions.

A safe scope is a fresh isolated configuration, no autoload/addons, tiny explicit fixture and a bounded process. A small empty/startup scene with a verified local IWAD is sufficient; no dense light workload, CFX crash route or PF-017 campaign is needed. The audit found the local Doom II IWAD, but did not establish a local Freedoom artifact for a claimed Freedoom launch. Hash whichever input the integrator actually selects. Missing input or fixture production is a blocker, not a reason to select a saturated historical workload.

### Validation facilities available locally

Read-only inventory verified Khronos JSON/DLL files under:

```text
C:\ShadeDoomVK\pf-local-evidence\cfx002-tools\vulkan-sdk-1.4.357.0\Bin
```

The manifest advertises layer API `1.4.357`; the DLL is 21,681,592 bytes. The copied SDK supplies `vulkaninfoSDK.exe`, and PATH also resolves `C:\WINDOWS\system32\vulkaninfo.exe`. These are availability observations, not proof of layer activation on the repaired executable. No Vulkan probe or draw was launched for this note.

`tools/cfx_capture.py` supplies a source-available process-scoped validation recipe: `VK_ADD_LAYER_PATH`, `VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation`, `VK_LAYER_SETTINGS_PATH`, loader layer logging and an isolated settings/log file. Its lines 21–27 distinguish core, synchronization and GPU-assisted modes. The later checks require both actual loader insertion and the layer's own CURRENT-VALIDATION-ENABLED report; GPU-assisted mode additionally requires real instrumentation. `vk_debug` alone does not establish any of that. Reuse the recipe in a #110 scoped runner; do not execute a historical CFX campaign or treat its old activation as this run's acceptance.

Run core and synchronization validation in separate bounded #110 executions, after CPU/state proof; any required GPU-assisted check must likewise prove actual instrumentation. Record errors, warnings, activation proof, exit/process cleanup and exact executable/config/layer identities. Missing activation is an explicit unavailable check rather than a zero-error success.

## Acceptance evidence still required

| Claim | Necessary evidence |
|---|---|
| Missing layers repaired | Actual constructor/descriptor body regression fails at pre-fix layer 1; candidate publishes exactly two real resources without fabricated layers. |
| Translation/style preserved | Production indexed byte producer and source-linked inverse/additive/object-uniform ordering; native normal/inverse cases on noncommuting remaps and unequal base colours. Public `DTA_Color` presentation is a separate same-route control, not a native object-uniform tint claim. |
| Resident content follows identity | A/B/A and B/A/B; numerical ID replacement, no deferred public indexed job, generic reset-ticket rejection; raw resident R8 and palette byte readbacks. |
| Correct discrete lookup | Actual shader boundary/off-grid reads under nearest and linear global filters, with nearest index/row samplers and one mip. |
| Protected paths unchanged | Ordinary multi-layer/global-shader, state-driven palette, RedIsAlpha, real SWCanvas two-layer and missing/invalid input controls. |
| Lifetime correct | Same lookup reuses entries; cleanup/reset/recreation changes PF identities, retires all rows/variants after fences and rejects stale upload targets. |
| Native Vulkan correct | Small scoped producer/consumer draw, exact image/state evidence and proved core/sync activation with no validation failures. |
| Release ready | Full strict PF oracle, clean native build, required exact-head CI, independent review, merged/verified master and post-merge checks, with canonical reconciliation. |

Useful existing state accessors are `GetLayerDiagnostic`, `GetBindlessIdentity`, `GetBindlessLifetimeStats`, `GetBindlessAllocationStats`, texture/async epoch statistics and upload-staging statistics. The prepared command emits its own `shadedoomvk-pf110-native-indexed/v1` receipt with actual material/view/sampler/remap/PF-token and readback observations. An external runner must still retain exact executable/source/config/layer identity and process exit; neither that command nor `tools/pf_oracle/runtime_evidence.schema.json` alone provides full release provenance.

The root reports a clean native build and 302/302 PF tests before the pending authored-colour generator/reference delta; the revised generator adds a source-linked route test and requires a fresh rerun/input regeneration. These CPU/build results do not execute the Vulkan diagnostic, prove validation activation or accept #110. Affected PF-005/PF-008/RAG material/trap documents now identify the focused candidate exception while retaining historical accepted scope. This note records no native GPU success, performance result, crash reproduction, merge or change to PF-020 gate status.


## Latest frozen candidate and pending native matrix

Candidate4 supersedes the earlier source/diagnostic preparations above. The
normal diagnostic retains400 assertions/26 cases; opt-in restart BEFORE is
expected403/26 and AFTER400/26 on hardware mode4. These are expected counts
until actual execution. Source-linked tests guard actual `int restart`, normal
`D_Cleanup`/palette reinitialization, two live Span2 tokens after RAII/fence
return, same manager/device/framebuffer, stale-token validation before fresh
diagnostic production, exact safe argv preflight and one-shot atomic restart.
No old resource or palette pointer survives in the checkpoint.

The clean build and391-test strict CPU gate pass. The fresh native matrix must
cover mode4, mode2 and actual mode0 SWCanvas under nearest/linear filters and
separate proved core/synchronization validation. The real restart runner needs
one child, exactly two7-package startup blocks, one persistent Vulkan instance,
actual counter+1, live-to-stale tokens, both raw oracles and final presentation.
See [candidate hashes](PF-110-CANDIDATE-CHECKPOINT.json). Native acceptance is
pending; raw success, presentation, lifetime and exact-head CI remain distinct.

The presentation inverse reference now uses independently literal inverse R8
indices with indexed translation0/normal style. Five ordinary controls retain
global-linear interpolation; equality/pairing to discrete indexed output is a
nearest-only check, while diversity/vertical/presence remain required. Indexed
repeat/inverse/color/alpha gates remain strict at1 presented-RGB byte. All21
decoded ROIs and the actual two-enabled-callback acknowledgement are mandatory.
