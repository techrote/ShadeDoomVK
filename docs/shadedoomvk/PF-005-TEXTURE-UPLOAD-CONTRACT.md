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

Both `VkHardwareTexture::CreateTexture()` and `UploadTexture()` retain the inherited image transition and copy ordering. The only copy-source change is from `bufferOffset = 0` in a per-upload buffer to the planner-provided offset in the persistent buffer.

The following remain unchanged:

- indexed textures: `VK_FORMAT_R8_UNORM`, no mip generation;
- ordinary processed truecolor textures: `VK_FORMAT_B8G8R8A8_UNORM`, inherited mip generation;
- hardware canvas format selection (`R32G32B32A32_SFLOAT` HDR / `R8G8B8A8_UNORM` SDR);
- `CTF_CheckOnly` placeholder creation followed by `CTF_ProcessData` async preparation;
- `VkTextureImage::GenerateMipmaps()` policy and ordering;
- bindless descriptor/material ownership established by PF-003.

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
