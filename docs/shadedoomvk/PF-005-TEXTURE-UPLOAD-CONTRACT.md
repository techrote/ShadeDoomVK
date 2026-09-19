# PF-005 texture upload lifecycle and staging contract

Status: implementation qualification in progress  
Date: 2026-09-19

## Qualified source surface

The live Vulkan texture implementation is under `src/common/rendering/vulkan/textures/`, not the obsolete `src/common/gpu/vulkan/` path recorded in an earlier planning note. The relevant production files are `vk_texture.cpp/.h`, `vk_hwtexture.cpp/.h` and `vk_imagetransition.cpp/.h`; transfer completion is owned by `vulkan/commands/vk_commandbuffer.cpp/.h`.

PF-005 does not broaden into material identity, palette/translation meaning, mip/filter policy, portal ownership, gameplay/tic semantics, audio, provenance or protected asset/source-data paths.

## Source-qualified hazards

The current async path creates a placeholder image, allocates an integer upload ID in `VkTextureManager`, performs `FTexture::CreateTexBuffer` on the worker and queues a main-thread completion. `PendingUploads` presently stores only `id -> VkHardwareTexture*`. Destruction removes one matching pending ID, while `VkHardwareTexture::Reset()` does not itself invalidate an already-issued completion. A target that is reset/recreated while remaining alive therefore has no PF-002 target-generation proof attached to the completion. The integer ID is also independent from the existing manager async epoch.

Ordinary `VkHardwareTexture::CreateTexture()` and `UploadTexture()` each allocate a dedicated CPU-only transfer-source `VulkanBuffer`. The buffer is moved to `TransferDeleteList`, which keeps it alive until `VkCommandBufferManager::WaitForCommands()` has waited the submitted fences and replaces the delete list. This is safe but forces repeated Vulkan/VMA allocations for texture bursts. The 64 MiB delete-list threshold then forces a whole transfer wait to bound deferred memory.

The existing worker catches exceptions and rethrows them through a main-thread task. PF-005 must preserve that behavior.

## Generation-safe completion contract

Every async completion must carry two PF-002 epochs:

1. a manager async epoch, invalidated on worker shutdown/manager teardown; and
2. a target upload epoch, invalidated whenever a `VkHardwareTexture` is reset or retired.

The pending-ID registry remains the first destruction guard: retired targets must have *all* pending entries removed. A completion is executable only while its ID is registered and both captured epochs are current. Validation occurs before dereferencing upload destination state. Reuse of the same address cannot make an old completion current because the target epoch changes on reset/recreation.

Upload IDs use a non-zero 64-bit sequence with explicit rollover to 1; zero remains the unset value.

## Bounded persistent staging contract

The qualified ordinary texture-upload path uses manager-owned persistent CPU-visible transfer-source buffers. A buffer may be reused only after a transfer wait/fence completion has retired the batch that last referenced it. In-flight buffers are never overwrite candidates.

The pool is bounded to 64 MiB total retained capacity, with an individual pooled-buffer ceiling of 16 MiB. Oversized or budget-exceeding requests retain the existing one-shot `TransferDeleteList` path. For a qualified request, reuse selects the smallest retired buffer whose capacity is at least the requested size. If no safe retired slot exists and budget remains, a new pooled buffer is allocated. If the pool is full and all suitable storage is still in flight, the implementation may perform the existing transfer-only wait, retire all submitted pool slots, and retry; this wait is explicit and instrumented.

This design reduces repeated allocation churn while preserving the command manager's existing fence authority. It does not infer safety from frame number, `RENDER_ContextIndex`, wall-clock time or CPU queue completion.

## Layout/copy contract

PF-005 does not change pixel generation, translation, mip count or filtering. New images still transition from `UNDEFINED` to `TRANSFER_DST_OPTIMAL`; copies retain the caller's `VkBufferImageCopy` region; mip generation remains unchanged; sampled images return to `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`. Hardware-canvas/render-target images continue to use the existing tracked `VkTextureImage::Layout` transition machinery and must be descriptor-safe before sampling.

## Instrumentation

`VkTextureUploadStats` records queued/completed/stale jobs, staging allocations/reuses/drops, transfer waits, pooled bytes and pool high-water. These counters are diagnostics only and do not drive texture policy.

The dependency-light `vk_texture_upload_contract.h` freezes the generation-ticket, non-zero-ID, best-fit and bounded-admission rules. `tests/pf005_texture_upload_contract_fixture.cpp` adversarially covers target reset, manager invalidation, ID rollover, undersized/exact/smallest-sufficient reuse selection, zero/oversized/budget-edge admission and a repeated-burst allocation model. The representative model issues 1024 one-megabyte uploads in 128 fence-retired batches of eight: baseline one-shot allocation count is 1024, while the bounded retirement/reuse model requires eight initial allocations, a >99% modeled allocation reduction without allowing pre-retirement reuse.

The existing deterministic PF oracle remains the content/state equivalence guard; the normal Windows/macOS/Linux build matrix remains required before merge.

## Acceptance boundary

PF-005 is not complete merely because the scalar contract fixture passes. Completion additionally requires the production Vulkan path to consume these rules, CI to compile the integration on all existing build configurations, the deterministic PF oracle to remain unchanged, required checks to pass, and the merged commit to be verified on `master` before #22 is closed.
