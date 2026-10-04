# #110 — indexed material candidate and acceptance plan


Status: **accepted through PR #116; verified master and exact post-merge checks passed**.
Issue: [#110](https://github.com/techrote/ShadeDoomVK/issues/110). The source contract and ancestral supported-path defect are recorded in that issue. Candidate4's twelve normal packets and failed original restart are retained history below; they do not attest the newer restart seam.

The focused proposed integration base is accepted GL master `3f37b63a4fdfb4c95421db951cf81682b5eb92c9`; renderer negative bodies were audited at `4df7dea1338f063c6417e024f967bfa4aa23edd4` and are unchanged by that GL repair. Numbered source references identify historical pre-#110 bodies; current entrypoints are identified by symbol. This focused material repair is separate from PF-020 freeze acceptance and SDVK-001 unblock.

## Keep translation before the existing shader operations

The authoritative indexed producer is `FTexture::CreateTexBuffer`, `src/common/textures/texture.cpp:335–360`. It obtains `Get8BitPixels(false)`, flips the column layout and, for a positive non-luminosity active translation, changes each byte using `FRemapTable::Remap[byte]`. It does **not** use the ideal `FRemapTable::Palette` used by the true-colour branch at lines 376–381. `palettecontainer.h:32–33` explicitly distinguishes those arrays.

`material_paletted.glsl:4–8` then calls the existing `getTexel`, turns its red component into a palette coordinate, reads binding 1 (`texture2`) and forces output alpha to one. `material_gettexel.glsl:8–72` applies texture modes and authored colour operations before that lookup. Retain this order and shader behaviour, including its opaque palette output; do not introduce sRGB conversion, a different alpha interpretation or an ideal-palette translation as part of the provisioning repair.

**Rejected proposal:** an untranslated shared R8 image plus a translated palette row is equivalent only when the intervening shader transformation commutes with the remap. It is not a safe general repair. For `TM_INVERSE`, existing `.r = 1 - .r` yields:

```text
old:      BaseColors[255 - Remap[n]]
proposed: BaseColors[Remap[255 - n]]
```

For `n=5`, `Remap[5]=10`, `Remap[250]=20`, those indices are 245 and 20. Select unequal actual base-palette colours for the fixture. Colour multiply/add and other shader operations need the same ordering check. The earlier neutral-image/translated-row proposal is rejected by this counterexample and must not be promoted to an accepted contract.

## Small coherent resource repair

The focused source candidate implements the audited direction: preserve the actual translated R8 producer, partition its resident images by resolved translation within the existing hardware-texture owner, and publish a real unchanged base-palette row beside each indexed descriptor entry. Native qualification and release acceptance are recorded below; historical preparation and failed packets remain preserved.

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

## Prepared native route — historical preparation and protected scope

The candidate prepares `pf_indexedmaterial_validate`, implemented in `src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp`, and synthetic runtime inputs from `tools/pf_oracle/prepare_indexed_material_runtime.py`. Their existence and successful native compilation are not execution or acceptance evidence.

The prepared command runs on the renderer-owner thread after a clean small startup, validates synthetic 16×4 PF110SRC/PF110SA/PF110SB inputs and renders its own 128×20 target through the real `DrawTexture` tag parser → `F2DDrawer` → `Draw2D(F2DDrawer*, FRenderState&, x,y,w,h)` → material → Vulkan shader route. It retains source pixels, tags, numerical translation IDs and canonical identities. The public ZScript equivalent is a registered `RenderOverlay(RenderEvent)` callback using `DTA_Indexed` and **`DTA_TranslationIndex`**; calling `Screen.DrawTexture` outside a draw callback is rejected by the VM at `v_draw.cpp:256`.

The earlier command preparation covered 22 draws, before the later actual object/add controls, covering normal/inverse output, A/B/A and B/A/B first use, numeric-ID replacement/restoration, default/invalid/inactive/luminosity input, off-grid/no-mip sampling, queued-draw retirement and recreation. It reads actual resident R8, base-row and target RGBA bytes, checks complete registered remap rows, actual shader/PF descriptor identity and zero new indexed async jobs. Ordinary state-driven palette/RedIsAlpha checks are descriptor/resident-byte controls, not software-colormap shader parity. The ordinary output is retained without claiming the indexed palette equation applies to it. Missing input emits no draw. These are implemented assertions awaiting native execution; palette-arena restart and real SWCanvas acceptance remain separate production-linked controls.

The overlay's `DTA_Color` control must not be described as direct `getTexel` object-colour tint. `v_draw.cpp` parses it into `parms.color`; `F2DDrawer::SetStyle` combines vertex colour, then indexed `AddTexture` records its luminance in `mLightLevel` and replaces vertex colour with white. `Draw2D` forwards that value via `SetSoftLightLevel`; shader `SIMPLE2D` processing is a separate downstream boundary. The literal translated PF110RA reference therefore uses the same indexed route, translation 0 and identical style/tag. This controls the public authored-colour route without claiming a visible tint effect or native `uObjectColor` ordering. The source-extracted scalar CPU oracle covers `getTexel` additive/object-uniform ordering; later candidate4 actual shader object/add controls are recorded below. Raw inverse draws exercise the full actual shader's noncommuting transformation.

For exact byte evidence, prefer an own small colour/depth target and explicit readback with production builders/transitions. The colour image needs COLOR_ATTACHMENT and TRANSFER_SRC usage, and the depth/stencil format must come from the actual device capability result. Use neutral draw state for the base-palette equation, then separately exercise inverse and authored colour controls. Restore the prior render target/state after the diagnostic. Clear/end the diagnostic render pass, transition to TRANSFER_SRC, copy to a GPU-to-CPU staging buffer, wait via the normal command manager, map and retain actual bytes. Read back the resident R8 source and palette row as well as the shader result; pair image assertions with published descriptor/view identity.

`RenderTextureView(FCanvasTexture*, callback):415–446` demonstrates existing target switching and production rendering, but its default canvas image allocation does not request TRANSFER_SRC. Do not directly copy that image without establishing the required usage. A dedicated diagnostic target can reuse the same builders and `SetRenderTarget` boundary. No CPU-computed colour may be labelled as a Vulkan result.

`GetScreenshotBuffer:644–662` and the existing `screenshot` command provide presentation evidence. They run the postprocess/present path and convert into RGB bytes; they do not expose exact raw R8/palette data or isolate the material shader. Keep their configuration and output as complementary evidence, not as a replacement for raw-image/state assertions.

A safe scope is a fresh isolated configuration, no autoload/addons, tiny explicit fixture and a bounded process. A small empty/startup scene with a verified local IWAD is sufficient; no dense light workload, CFX crash route or PF-017 campaign is needed. The audit found the local Doom II IWAD, but did not establish a local Freedoom artifact for a claimed Freedoom launch. Hash whichever input the integrator actually selects. Missing input or fixture production is a blocker, not a reason to select a saturated historical workload.

### Scoped validation requirement

The existing runtime runner uses process-scoped Khronos validation settings with loader insertion and the layer's own CURRENT-VALIDATION-ENABLED proof. `vk_debug`, an installed layer, or historical CFX activation alone proves neither core nor synchronization validation for this candidate. Run core and synchronization separately and retain exact layer/executable/input/config identities, messages, normal process exit and output hashes. GPU-assisted instrumentation is a separate claim; none is inferred here.

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

## Presentation policy and guarded restart — newer candidate pending

The inverse presentation reference uses independently literal inverse R8 indices with indexed translation0/normal style. Five ordinary controls retain configured global-linear interpolation. Equality/pairing to discrete indexed output is a nearest-only check; bounded diversity, vertical structure and presence remain required for ordinary linear controls. Indexed repeat/inverse/color/alpha gates remain strict at 1 presented-RGB byte. All 21 decoded ROIs and the actual two-enabled-callback acknowledgement are mandatory.

Frozen source `bd2586f51c456fcdb9d04e616a6facf30d47a5ec` contains the diagnostic seam repair after candidate4's guarded failure. It preflights exact pinned `-iwad`, `-file`, `+exec`, `+map` pairs using the real `FArgs::TakeValue` on a copy, preserves every other option, verifies original argv stayed unchanged during BEFORE, then commits the identical pair removal before dispatching the existing `debug_restart`. It does not change ordinary restart, renderer cleanup, palette initialization or resource retirement.

A genuine acceptance run requires one child and two actual 7-package archive startup blocks, counter+1 and the same Vulkan instance/device/descriptor manager. The checkpoint retains value tokens, not old pointers. AFTER must test the two selected old tokens as stale before fresh diagnostic production, after normal map warm-up. This is not a guard before every engine producer. Both raw oracles, final decoded presentation and proved core/synchronization activation remain required. Lifetime allocation/free counters are cumulative process observations; they must not be confused with the selected-token live-to-stale assertion. Candidate5 native qualification is verified below; release integration is tracked in the source issues.

## Retained normal native matrix — candidate4/source890, 2026-10-04

All twelve retained fixed mode/filter cases pass: mode4 hardware truecolour, mode2
hardware palette and mode0 real paletted SWCanvas, each under global nearest0
and linear2, with separate proved core and synchronization validation. Every
process exits normally with zero requested-validation errors/warnings and
unchanged source/build/input closure. Hardware packets contain 400 assertions
across 26 cases; software packets contain 407 across 27. Total: 4,828 assertions
across 316 cases. All 252 presentation ROIs and actual overlay acknowledgements
pass; the independent audit recomputes 737,280 indexed pixels with zero mismatch.
See [compact matrix verification](PF-110-NATIVE-MATRIX-VERIFICATION.json).

The inverse reference's presented indexed difference is0 in all twelve packets.
Ordinary linear controls retain actual configured filtering; their comparison
with discrete indexed output is observational. No tolerance was broadened.

The first genuine-restart attempt fails safely before its raw diagnostic or
restart: startup's `CollectFiles("-file", nullptr)` moves the package pair to the
end, and inherited `RemoveArgs` leaves the terminal filename behind. The exact
preflight rejects that state. Engine exit 0, one archive startup and no BEFORE
raw output do not constitute restart acceptance. The packet is retained in
[the restart attempts receipt](PF-110-RESTART-RETAINED-ATTEMPTS.json). The newer
source-linked diagnostic seam uses exact `TakeValue` pair removal before the
existing `debug_restart`; fresh candidate5 build/core/sync restart proof is
required. No original packet is overwritten.

These are bounded correctness results, not GPU timing, global frame budget,
human approval, historical CFX/PF-017 requalification or repaired P400 evidence.
Independent focused release CI, merge/master and post-merge checks are pending.
The independent PF-020 freeze remains outside this repair's acceptance.

The candidate4/source890 raw cases also retain actual shader object/add controls against both the preserved operation-order oracle and a rejected pre-remap ordering. Public `DTA_Color` remains a separate luminance/white-vertex route; these witnesses must not be conflated. The normal matrix receipt records selected descriptor retirement/recreation, while the genuine arena restart is a distinct candidate5 acceptance gate.


## Verified candidate5 native qualification

The final clean RelWithDebInfo build corresponds to committed source
`bd2586f51c456fcdb9d04e616a6facf30d47a5ec`. All 2,528 engine inputs are verified
against that Git tree through exact raw or declared text newline equivalence.
Executable SHA256 is
`e5ac64d21b2bbb0f893b6317957660085040ff6ef232f75485d08f3f33a00488`.

All twelve normal mode/filter cases pass with 4,828 assertions / 316 cases,
including four real paletted mode0 SWCanvas packets. Both genuine one-process
restart controls pass under separately proved core and synchronization
validation: two exact seven-package startups, real counter 0 to 1, persistent
Vulkan device/manager, two retained tokens live to stale before the fresh
diagnostic producer, and 403 BEFORE / 400 AFTER assertions in each run. All
fourteen processes exit normally with zero requested-validation errors/warnings,
unchanged source/build/input pins and 294 decoded presentation ROIs.

The strict native PF suite passes 393/393 with zero errors/skips. Four strict
standalone contracts, CFX classifier 8/8 and two byte-equal source oracles pass.
[Compact final qualification](PF-110-FINAL-NATIVE-VERIFICATION.json) retains hashes/counts/status and
separate independent native audits. Earlier successful and failed packets
remain immutable history.

Mode1 BGRA software frame execution and a direct post-retirement SWCanvas token
query remain unmeasured. Observed software memory contains CPU-written bytes;
tracked sampled layouts are not a driver layout query. Restart lifetime counters
include normal owner activity; selected old-token checks occur before the fresh
diagnostic producer, after normal map warm-up. No GPU timing, total-frame budget,
cross-mode image equality, human approval, historical campaign or P400 proof is
inferred. Focused review/CI/merge/master/post-merge acceptance is tracked in
[#110](https://github.com/techrote/ShadeDoomVK/issues/110) and
[#112](https://github.com/techrote/ShadeDoomVK/issues/112). PF-020 and SDVK-001
remain separate blocked gates.


## Focused release acceptance — 2026-10-04

[PR #116](https://github.com/techrote/ShadeDoomVK/pull/116) merged as
`1524686e77f1e89dabfb044bf757a2d19566c31c` after independent exact-head review
and all eight actual PR jobs passed at `9df93b6d`. Remote master and ancestry
were verified, with unchanged engine/tool inputs. All eight actual push jobs
then passed at the exact merge SHA, and #110/#112 were closed as complete.
See [compact release acceptance](PF-110-RELEASE-ACCEPTANCE.json).

The qualification and failed-attempt receipts above retain their original
measurement-time statuses. Earlier pending-gate statements describe those
preparations; this receipt records their eventual completion. Software,
performance, human-review and historical-campaign limits remain unchanged.
PF-020/SDVK-001 stay blocked by the separate #113 repair.
