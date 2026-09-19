# PF-005 texture upload lifetime and staging contract

Status: implementation contract for PF-005  
Issue: PF-005 / #22  
Depends on: PF-002 generation/epoch substrate and PF-003 descriptor lifetime contract

## Scope

PF-005 changes ownership and staging mechanics only. It does **not** change texture pixels, translation/palette processing, image formats, mip-count policy, mip generation, sampler/filter policy, descriptor semantics, image layout sequence, gameplay state or source/audio/provenance behavior.

The qualified path is the Vulkan hardware-texture upload path in `vk_hwtexture.cpp`. Oversized transfers keep the inherited dedicated staging-buffer fallback.

## Async completion identity

The inherited asynchronous path used a monotonically increasing integer mapped to a raw `VkHardwareTexture*`. Destruction removed one matching map entry, but reset/recreation did not give queued work a target generation. A completion could therefore be logically stale even while its integer ID still existed.

PF-005 introduces `VkAsyncTextureUploadTracker` in `vk_textureupload.h`:

- a target pointer value is only a lookup key, never sufficient proof of lifetime;
- each live target owns a PF-002 `FRendererResourceGenerationTable` identity;
- each queued job captures both that target identity and the current `AsyncUploadEpoch` token;
- `VkHardwareTexture::Reset()` retires/reactivates the target generation before image objects are reset;
- hardware-texture destruction retires the target;
- owner shutdown invalidates `AsyncUploadEpoch` through the existing PF-002 shutdown hook;
- completion consumes the job and succeeds only when **both** the owner epoch and target generation still validate;
- pointer-address reuse cannot validate an older job because the generation changes across retirement/re-registration;
- job-ID wrap avoids signed overflow and skips live IDs rather than replacing an outstanding job.

The legacy `CreateUploadID` / `CheckUploadID` surface remains temporarily for untouched call sites; the hardware-texture asynchronous path no longer relies on it.

Counters expose queued, applied and stale-rejected completions, target invalidations/retirements and job-ID wrap/collision events. PF-002 lifetime counters remain available for target generations.

## Persistent staging arena

Ordinary texture uploads previously allocated one `VulkanBuffer` in CPU-only memory per image, copied the pixels, submitted it as transfer source, and retained that whole buffer until transfer retirement. The qualified PF-005 path instead owns one lazily-created, bounded 64 MiB CPU-only transfer-source buffer in `VkTextureManager`.

`VkTextureUploadArenaPlanner` assigns 16-byte-aligned, non-overlapping slices. A copy uses the slice offset through `VkBufferImageCopy::bufferOffset`; the image destination, format, dimensions, layout transitions and mip-generation calls are unchanged.

### Reuse/fence rule

The arena is deliberately linear and conservative:

1. allocations advance monotonically and are never reused while their transfer commands may be in flight;
2. if a request fits the arena in principle but no free tail space remains, PF-005 waits at the existing upload-only `WaitForCommands(false, true)` completion boundary;
3. only **after that wait returns** is the planner reset and its epoch advanced;
4. all old slices are then stale and the backing buffer may be reused from offset zero;
5. an individual upload larger than 64 MiB does not grow the arena: it uses the inherited dedicated-buffer path and inherited deferred-deletion threshold.

This makes peak persistent staging memory bounded and makes overwrite-before-retirement structurally impossible without introducing a new Vulkan fence model.

The trade-off is intentional: PF-005 eliminates ordinary per-image Vulkan buffer allocation churn, but it does not claim a new fine-grained ring-fence scheduler. A future optimization may recycle completed ranges earlier only if it can prove the same in-flight ownership rule.

## Instrumentation

The planner records requests, successful acquisitions, oversized fallbacks, upload-boundary waits, resets, reuse events, current bytes and high-water bytes. The manager separately records the actual persistent-buffer allocation count and dedicated oversized fallbacks.

These counters distinguish logical slice requests from Vulkan object allocation. The useful optimization claim is the reduction in **Vulkan staging-buffer allocations**, not a reduction in pixel-copy bytes.

## Deterministic workload evidence

`tools/pf_oracle/tests/texture_upload_contract_fixture.cpp` is a compiled, GPU-independent contract fixture suitable for every CI host. Its burst model feeds 1,024 uploads of 64 KiB through a 4 MiB arena:

- inherited dedicated-buffer model: 1,024 staging-buffer allocations;
- PF-005 persistent-buffer model: 1 backing-buffer allocation for the qualified path;
- arena acquisitions: 1,024;
- high-water: exactly 4 MiB;
- full-arena retirement waits/resets: 15.

The fixture also covers one-byte/alignment/exact-capacity boundaries, zero/oversized/`SIZE_MAX` requests, stale slices after reset, target reset, target retirement, owner-epoch invalidation, pointer-address reuse and job-ID wrap.

This workload is a deterministic allocation/wait model, not a fabricated GPU timing benchmark. PF-001 CI does not have a runnable IWAD/GPU image harness; full Windows/macOS/Linux builds plus the source/contract oracle therefore remain the available cross-host equivalence evidence. Runtime timing/image evidence can be added later without weakening this contract.

## Output-equivalence boundary

PF-005 leaves the following inherited operations unchanged in meaning and order:

- `FTextureBuffer` creation and `CTF_CheckOnly` / `CTF_ProcessData` processing;
- indexed `VK_FORMAT_R8_UNORM` versus truecolor `VK_FORMAT_B8G8R8A8_UNORM` selection;
- image dimensions and mip-count calculation;
- transfer-destination transition;
- buffer-to-image copy extent/subresource;
- inherited `GenerateMipmaps` call and policy;
- sampler/filter/material descriptor code;
- canvas/dynamic texture behavior outside the staging source allocation.

The only buffer-copy semantic addition is a non-zero source `bufferOffset` for suballocated slices. The first slice remains offset zero; every later slice references the exact bytes copied into its own non-overlapping staging range.

## Shutdown and error propagation

PF-005 does not alter worker-loop exception transport. Worker exceptions continue to be converted into main-thread tasks that rethrow through the inherited queue. `StopWorkerThread()` still stops and joins the worker and clears queued tasks; its existing `AsyncUploadEpoch.Invalidate()` makes any captured completion token stale.

No PF-005 path catches or suppresses texture processing exceptions.

## Fail-closed invariants

1. A completion may mutate an image only when its owner epoch and target generation are both current.
2. Target reset/recreation, destruction or owner shutdown makes previously queued work stale.
3. Reused pointer addresses and wrapped job IDs cannot alias a live old job.
4. Persistent staging slices are not reused until the upload-only completion wait has returned.
5. Persistent staging capacity is bounded; oversized requests retain the dedicated fallback.
6. Texture content, formats, mip generation, filtering and material-visible semantics are outside PF-005's change surface.
7. Worker exception propagation and shutdown ownership remain inherited behavior.
