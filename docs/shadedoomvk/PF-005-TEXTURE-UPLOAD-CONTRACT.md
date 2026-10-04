# PF-005 asynchronous texture upload and staging contract

Status: implementation candidate for PF-005  
Date: 2026-09-19

## Purpose

PF-005 hardens the existing optional Vulkan asynchronous texture preparation path and removes the ordinary one-staging-buffer-per-upload allocation pattern. It does not change texture source processing, indexed/truecolor selection, canvas formats, mip generation, sampler/filter policy, material layer meaning, audio, gameplay state, or donor provenance.

## Async job identity

`VkHardwareTexture` now owns a PF-002 `FRendererEpoch` for its upload target generation. `Reset()` advances that epoch before image resources are reset.

A queued async completion carries a `VkTextureManager::FAsyncTextureUploadTicket`:

```text
{ upload ID, manager async epoch, target upload epoch }
```

The main-thread completion order is deliberately strict:

1. consume/check the manager upload ticket;
2. validate the manager async epoch;
3. only then dereference the `VkHardwareTexture` target and validate its target epoch;
4. upload only when both generations are current.

Texture destruction cancels **all** outstanding upload IDs for that owner before `RemoveTexture()` can reset or detach the backend object. This closes the inherited one-match cancellation hole, where destruction removed only the first matching pending upload ID.

A same-object reset/recreate does not need to erase every ticket: its target epoch advances, so an old completion is consumed and rejected rather than being allowed to overwrite the recreated target. Renderer/worker shutdown advances the manager async epoch as before; queued worker/main tasks are joined/cleared through the inherited shutdown path. Worker exceptions are still marshalled to the main thread and rethrown there.

Diagnostics distinguish queued/completed jobs, explicit destruction cancellations, missing-ticket rejects, manager-epoch rejects and target-epoch rejects.

## Persistent upload staging

Ordinary hardware texture create/completion uploads share one lazily-created **64 MiB** CPU-visible transfer-source buffer owned by `VkTextureManager`.

`FRendererUploadStagingPlanner` is a Vulkan-independent bounded allocator model. It returns an aligned `{offset, size}` slice and reports whether the next allocation would wrap over earlier bytes.

Rules:

- ordinary requests `<= 64 MiB` use the persistent arena;
- slices are 4-byte aligned, sufficient for the current R8 and 32-bit base-level texture-copy paths;
- no arena slice exceeds the configured capacity;
- an exact-end allocation is legal;
- before a wrapped slice reuses byte zero, the renderer performs `WaitForCommands(false, true)` **before mapping/writing the reused range**;
- this wait is owned by the staging arena and does not assume that a frame-present wait happened elsewhere;
- requests larger than the arena use a one-shot dedicated staging buffer, then immediately perform the upload-only wait after recording the transfer so oversize fallbacks cannot accumulate unbounded deferred staging memory.

The persistent buffer is renderer-owned. `VulkanRenderDevice` already waits for device idle before manager RAII teardown, so the arena is not destroyed while the GPU can still reference it.

## Transfer and image semantics

PF-005 retained the inherited image transition and copy ordering in `VkHardwareTexture::CreateTexture()` and `UploadTexture()`. Its copy-source change was from `bufferOffset = 0` in a per-upload buffer to the planner-provided offset in the persistent buffer. The later #110 candidate corrects the separate non-mip transition defect described below; that is not a PF-005 optimization or a change to mip/filter policy.

The following remain unchanged:

- indexed textures: `VK_FORMAT_R8_UNORM`, no mip generation;
- ordinary processed truecolor textures: `VK_FORMAT_B8G8R8A8_UNORM`, inherited mip generation;
- hardware canvas format selection (`R32G32B32A32_SFLOAT` HDR / `R8G8B8A8_UNORM` SDR);
- `CTF_CheckOnly` placeholder creation followed by `CTF_ProcessData` async preparation;
- `VkTextureImage::GenerateMipmaps()` policy and ordering;
- bindless descriptor/material ownership established by PF-003.

### #110 indexed producer and sampled-layout correction — candidate / unaccepted

[#110](https://github.com/techrote/ShadeDoomVK/issues/110) is a separate public indexed-material correctness repair. In the focused source candidate, `VkHardwareTexture::GetIndexedMaterialImage()` resolves an active canonical remap, selects its owner-local R8 variant and calls `CreateImage(..., allowAsync=false)`. The actual indexed `CreateTexBuffer` branch already produces complete bytes; synchronous production/upload prevents a deferred numerical translation ID from being replaced before it supplies bytes to an image keyed by the earlier remap. This scoped policy does not disable the ordinary asynchronous true-colour or state-driven RedIsAlpha path or relax PF-005 tickets/epoch checks.

The candidate also adds the missing explicit `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` transition after non-mip copies in both `CreateTexture()` and `UploadTexture()`. The inherited no-mip branch otherwise left the copied image in transfer-destination layout. Mipmapped images retain `GenerateMipmaps()`; indexed images retain one mip and discrete lookup. Exact original no-mip bodies remain negative fixtures. This fixes layout authority rather than changing source bytes, resolution, colour space or filtering quality.

The real 256×1 base-palette row owned by each indexed descriptor entry uses `StageTextureUpload`, its returned `bufferOffset`, existing image transitions and `FinishTextureUpload`. Arena wrap waits and oversize retirement remain authoritative. Hardware reset advances the upload epoch and retires all canonical indexed variants; descriptor cleanup retires its auxiliary row through the normal draw fence. No shared palette cache or emergency global descriptor flush is introduced. See [implementation notes](PF-110-IMPLEMENTATION-NOTES.md) for identity and protected-path evidence requirements. Native Vulkan image/state/validation and exact-head release gates are pending; this is not acceptance evidence.

### #112 mapped software-image descriptor declaration — candidate / unaccepted

[#112](https://github.com/techrote/ShadeDoomVK/issues/112) separately addresses the inherited mapped software framebuffer's layout mismatch. `AllocateBuffer()` creates its sampled linear host-visible/coherent image in `GENERAL`; `MapBuffer()`, the software write, `CreateTexture(nullptr, ...)` and the existing-image `GetImage()` path do not turn it into an uploaded shader-read image. The old bindless writer nevertheless declared `SHADER_READ_ONLY_OPTIMAL`.

The focused candidate gives `SetBindlessTexture()` an explicit layout argument, with the existing shader-read layout as its default. All four material publication sites pass the selected `VkTextureImage::Layout`; the writer accepts `GENERAL` and `SHADER_READ_ONLY_OPTIMAL` and rejects other states before queuing a descriptor write. Ordinary uploaded images and the #110 auxiliary palette row still publish shader-read layout. No producer, mapped software pixels, sampling, upload arena, async policy, cache or fence behavior changes. The real SWCanvas R8 framebuffer and separately provisioned BGRA palette remain two resources. See [candidate notes and evidence limits](PF-112-IMPLEMENTATION-NOTES.md): extracted CPU checks pass, but actual warm SWCanvas/presentation/core-plus-sync and final acceptance gates remain pending.

## Counters and boundedness

The planner exposes requests, arena slices, reuse count, wrap waits, oversize requests, invalid requests, bytes requested and high-water bytes. The Vulkan owner additionally records persistent-buffer allocations, dedicated-buffer allocations and dedicated waits.

The arena has a fixed 64 MiB persistent ceiling. The only temporary amount beyond that ceiling is one currently-recorded oversize fallback, which is waited and retired immediately.

## Deterministic workload evidence

`tools/pf_oracle/tests/upload_staging_fixture.cpp` exercises exact-boundary, alignment-gap, wrap, oversize, zero/invalid request and 10,000-request stress cases.

Its representative burst model uses 1024 uploads of 64 KiB each:

- inherited ordinary path: 1024 Vulkan staging-buffer allocations before the old 64 MiB deferred-delete cliff;
- PF-005 arena: one persistent Vulkan staging-buffer allocation, 1024 non-overlapping slices, zero arena-reuse waits through the exact 64 MiB boundary;
- upload 1025: one upload-only wait before byte-zero reuse, then the same persistent buffer is reused.

This is an allocation/wait contract benchmark, not a claim about GPU wall-clock speed on hosted CI. Runtime counters are retained so hardware runs can measure real upload traffic without changing the renderer contract.

## Adversarial verification

The PF-005 oracle coverage checks:

- destruction cancels every owner ticket, not just one;
- target reset advances the PF-002 target epoch;
- manager ticket validation precedes target dereference;
- shutdown still invalidates the manager async epoch and preserves exception propagation;
- wrapped arena bytes are waited before being mapped again;
- exact capacity, alignment padding, oversize fallback and invalid requests;
- 10,000 varied arena requests never return an out-of-bounds range;
- create and completion uploads both use the arena and preserve copy/mipmap ordering;
- indexed, truecolor and canvas format policy remains unchanged.

## Protected semantics

PF-005 is renderer-resource work only. It does not alter gameplay/tic semantics, source texture processing meaning, material/layer selection, palette/translation meaning, sprite semantics, portal behavior, audio, or provenance/licensing text.

## Residual scope

PF-005 does not convert unrelated lightmap/probe staging allocations, download/readback staging, or general command-buffer deferred destruction into this arena. Those paths have different ownership/data-shape requirements and remain owned by their recorded later issues. The raw integer upload-ID helpers remain private implementation details beneath generation-aware tickets; callers cannot bypass the ticket contract.
