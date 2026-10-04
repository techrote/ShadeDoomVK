# PF-112 — Mapped software-image sampled-layout declaration


Status: **native qualification verified; release integration tracked in the source issues**

Issue: [#112](https://github.com/techrote/ShadeDoomVK/issues/112), required by PF-020/#37

Focused integration base: accepted GL master `3f37b63a4fdfb4c95421db951cf81682b5eb92c9`.
The historical negative source is `4df7dea1338f063c6417e024f967bfa4aa23edd4`; this material path is unchanged by the GL repair.
Historical evidence checkpoint: 2026-10-04, candidate4/source890. Four real paletted SWCanvas packets pass independent review for that exact candidate; they do not attest the newer diagnostic. Preparation, failed enclosing gates and partial observations remain history below. Candidate5 native qualification is verified below; release integration is tracked in the source issues.

## Requirement and source-established defect

Preserve the software framebuffer's pixels, palette semantics, filtering, material ownership and normal fence lifetime while making its sampled descriptor agree with its image layout. This is an independently scoped correctness repair, not a PF optimization, quality trade or software-renderer disablement.

At accepted starting master, the supported producer/consumer chain is:

1. `VkHardwareTexture::AllocateBuffer` creates a sampled linear host-visible/coherent R8 or BGRA image and records `VK_IMAGE_LAYOUT_GENERAL`.
2. `SWSceneDrawer::RenderView` maps and writes that image using `GetBufferPitch`.
3. `CreateTexture(nullptr, ...)` records neither an upload nor a layout transition; the existing-image `GetImage` returns it unchanged.
4. `VkMaterial::GetDescriptorEntry` publishes the material through `SetBindlessTexture`, whose old writer always declares `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`.

The mismatch is established from production source and an extracted compiled negative. It is not evidence that a native crash occurred. The mapped image has SAMPLED usage only: copying it as TRANSFER_SRC or silently transitioning it for a diagnostic would replace the contract under test.

The software-paletted SWCanvas path already provisions a real framebuffer plus a separate real palette layer. It is distinct from #110's public `DTA_Indexed` material, which needs its own auxiliary palette row. The candidate must preserve that distinction.

## Candidate decision and smallest coherent change

`VkDescriptorSetManager::SetBindlessTexture(index, view, sampler, imageLayout)` carries the layout into `WriteDescriptors::AddCombinedImageSampler`. Its declaration retains `SHADER_READ_ONLY_OPTIMAL` as the default for existing audited uploaded-image callers. The writer checks runtime bindless capacity as before, then accepts only `SHADER_READ_ONLY_OPTIMAL` or `GENERAL`; it rejects other states before queuing a descriptor. This is the renderer's audited sampled-colour-image boundary, not a claim that these are Vulkan's complete set of legal descriptor layouts.

All four material publication sites pass the selected `VkTextureImage::Layout`: base image, ordered additional layer, global custom layer and #110 entry-owned indexed palette. Thus mapped software images declare GENERAL; uploaded images, including the existing SWCanvas palette and #110 base-palette row, declare READ. The fixed null/BRDF/game-palette, software-colormap and probe callers retain their default READ declaration and their existing shader-readable producers.

The declaration does not transition an image. The wrapper's tracked layout remains authoritative for the audited producer and is copied into the queued descriptor write. It must agree with the image's accessible subresources when sampled; a default argument is not permission to claim READ for a GENERAL producer.

Research finding, checked2026-10-04: the Khronos [descriptor-image reference](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorImageInfo.html) defines this field as the layout at descriptor access. The [subresource query reference](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetImageSubresourceLayout.html) and [subresource-memory reference](https://docs.vulkan.org/refpages/latest/refpages/source/VkSubresourceLayout.html) distinguish linear-image memory offset/row pitch from the renderer's tracked image-access layout. These API facts explain the diagnostic's claim boundary; they do not measure this candidate.

## Preserved compatibility and lifetime

No change is made to `AllocateBuffer`, `MapBuffer`, software writes, `CreateTexture(nullptr, ...)`, `GetImage`, source bytes, palette/translation interpretation, shader selection, per-layer sampling, mip generation, colour space, source resolution, asynchronous upload tickets or PF-005 staging. The software-paletted material retains two real resources: mapped R8 framebuffer in GENERAL and the existing BGRA palette in READ. Mapped true-colour BGRA remains its own existing path.

Ordinary uploaded material layers and #110's index/palette pair still finish in shader-read layout. #110's separate no-mip transition correction remains separately scoped; this declaration does not add another upload or sampling transition.

Descriptor cache keys, PF-003 contiguous range/generation identities, publication count and normal retirement remain unchanged. Each existing cached owner has a stable sampled layout during its valid lifetime; owner reset/reallocation continues to invalidate and retire the associated resources. No blanket cache flush, forced per-frame wait, software disablement or per-frame resource upload is introduced.

## Extracted CPU evidence

`tools/pf_oracle/tests/test_swcanvas_layout_contract.py` and `swcanvas_layout_fixture.cpp` retain the exact accepted-master allocation, map, nullable-create, existing-image and full bindless-writer bodies, plus the material publication block. Native builders/handles and service/container controls are bounded stubs; the producer and descriptor body are not replaced with a hand-written layout oracle.

The original R8 and BGRA cases require the bad state: actual tracked GENERAL paired with declared READ. Current cases require matching GENERAL for mapped images and READ for existing palettes, ordinary uploaded images and the default writer. They cover repeated use without extra upload/transition, extent/format replacement, rejected illegal layouts and out-of-capacity writes. The indexed fixture also checks published READ against each selected uploaded image's tracked state, preserving the original independent missing-layer and non-mip negative cases.

Root's strict native MSVC run passed **56/56 tests in 6.002 seconds**: 11 software-layout tests, 25 indexed-material tests and 20 runtime-runner tests, including original and current compiled bodies. Receipt: `build/pf020-native/layout-indexed-runner-tests.log`. This is deterministic extracted CPU evidence, not a real software frame, GPU validation, screenshot parity or performance measurement.

## Observational native allocation preflight

The #110 candidate-2 command created two private real 640×480 `AllocateBuffer` images, completed the existing transfer wait and queried `vkGetImageSubresourceLayout`. It mapped without writing, copying or sampling and retired them through normal waits. Retained observation:

| Format / bytes per texel | Native offset | Native row pitch | Producer pitch | Mapping / pitch coherence |
| --- | ---: | ---: | ---: | --- |
| R8 / 1 | 0 bytes | 640 bytes | 640 bytes | true |
| BGRA / 4 | 0 bytes | 2560 bytes | 2560 bytes | true |

The historical JSON field `nativeImageLayout` contains the wrapper's **tracked** GENERAL state; `vkGetImageSubresourceLayout` queries memory offset/pitch, not runtime image layout. The two successful observations remove the unmeasured offset/pitch concern for these exact allocations on this device/build. They do not establish a running SWCanvas owner, host-written pixels, a descriptor used by a software frame, presentation or another device's pitch behavior.

## Retained native partial result and failed enclosing gate

`build/pf020-native/pf110-runs/core-nearest-03/native.json` records the #110 candidate-2 raw command PASS: 348 assertions across 23 cases. Its enclosing `receipt.json` proves core validation activated and reports zero real validation errors/warnings, but reports **FAIL** because presentation was missing. The capture sequence's exec/wait scheduling is under repair; a passing raw command does not override that gate. Core-only validation does not prove synchronization validation. Palette-arena restart and actual SWCanvas acceptance remain explicitly separate pending controls.

The above receipt is a historical candidate-2 observation. It does not attest later diagnostic edits or a final source head. Exact final source/build/input/config identities must accompany each later native run. No GPU timings, full-frame budget, repaired P400 behavior or historical CFX/PF-017 requalification are claimed.

## Pending acceptance and fail-closed gate

Before #112 or PF-020 can be accepted, retain production-linked evidence from the actual warm fixed software scene: existing SWCanvas owners and two-resource palette state, sampled descriptor/owner layout coherence, repeated use and normal retirement, actual presentation and observed mode/configuration. Inspection must not manufacture a replacement owner or palette and must not copy the sampled-only mapped image as a transfer source. Any mapped-memory observation must distinguish CPU-written resident bytes from GPU-produced readback.

Complete the strict PF oracle/compiled fixtures and clean final native build, scoped proved core **and synchronization** validation, protected ordinary/palette/indexed controls and native software state/presentation evidence. Retain immutable source/build/input/config/output identities and every failure; obtain independent review and all eight actual exact-head CI jobs, then merge, verify `master` and complete required post-merge checks before closure. Missing evidence is a blocker, not an implied pass. PF-020 and SDVK-001 remain blocked.

## Source and canonical traceability

- `src/common/rendering/vulkan/textures/vk_hwtexture.cpp`: mapped producer, existing-image selection and four material publication sites.
- `src/common/rendering/vulkan/descriptorsets/vk_descriptorset.h/.cpp`: explicit layout/default and guarded descriptor declaration.
- `src/rendering/swrenderer/r_swscene.cpp`: actual SWCanvas framebuffer and separately provisioned palette producers.
- `src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp`: gated per-invocation native allocation and actual existing SWCanvas observations.
- [PF-005 upload contract](PF-005-TEXTURE-UPLOAD-CONTRACT.md), [PF-008 material semantics](PF-008-MATERIAL-SEMANTICS-CONTRACT.md), [material RAG](rag/04-MATERIAL-SHADER-CONTRACT.md), [trap 27](rag/10-KNOWN-TRAPS-DORMANT-PATHS.md#27-mapped-software-framebuffer-declares-an-uploaded-image-layout).
- [#110 source and acceptance notes](PF-110-IMPLEMENTATION-NOTES.md) retain the separate indexed provisioning, guarded restart and release limits. No PF-020 freeze synthesis is part of this focused proposal.

## Retained actual SWCanvas result — candidate4/source890 normal matrix

Four actual mode0 packets pass: nearest and linear under separately proved
core and synchronization validation. Each packet observes two distinct existing
rotating SWCanvas owners/materials at 640x480 with two resources: host-written R8
in tracked/declared GENERAL, and its existing palette in tracked/declared READ.
Actual mapped-memory offset 0 and row pitch 640 agree with the producer. The
observer does not manufacture an owner, create a replacement image/palette,
write mapped bytes or copy the sampled-only framebuffer. Descriptor registry
and selected keys remain unchanged. All four packets pass 407 assertions/27
cases, 21 decoded presentation ROIs, actual overlay acknowledgement, normal
exit and zero requested-validation errors/warnings. See [compact matrix](PF-110-NATIVE-MATRIX-VERIFICATION.json).

Retirement is preserved by unchanged owner rotation/reset, destructor and
normal fence paths, inherited extracted fixtures and clean actual process
exits. The CPU reset service is stubbed: neither it nor these observations
measures a direct post-retirement SWCanvas token query. The genuine restart
uses separate indexed-material tokens and must not be relabelled as that
measurement. Mapped memory contains CPU-written pixels, not GPU readback.

Actual mode1 truecolour BGRA host-write/sample/presentation is unexecuted.
Both formats have production-extracted layout tests and the retained private
native allocation geometry check; only mode0 R8 has the real software frame
proof above. No broader compatibility, performance or human acceptance is
inferred. Required exact-head CI, independent review, verified merge/master
and post-merge checks remain pending before #112 closure.

Candidate5 repeats the normal matrix on its own clean build/source closure; the final proof below preserves these historical candidate4 packets. The genuine indexed-token restart does not measure direct SWCanvas post-retirement tokens. Final exact-head CI/review/merge/master evidence is pending, and this focused repair does not accept PF-020 or unblock SDVK-001.


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
