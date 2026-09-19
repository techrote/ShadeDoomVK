# PF-003 bindless descriptor contract

Status: implementation contract introduced by PF-003  
Date: 2026-09-19

## Purpose

PF-003 hardens VKDoom's existing bindless combined-image-sampler allocator without changing material meaning or selecting fewer resources. It preserves the inherited exact-size free-bucket reuse, adds PF-002 generation validation, fixes the lightmap/probe reservation overlap, and derives descriptor-set capacity from the selected Vulkan device.

## Sources and provenance

### Donor concept

`jalovisko/VkDoom@033a3c5cb35c82708e4eeb3619373c33ddc40b75`

Useful concepts adapted:

- expose `vk_max_bindless_textures` as a restart-time requested cap;
- clamp requested capacity to physical-device limits;
- make exhaustion diagnostics actionable.

ShadeDoomVK does not copy the donor capacity formula verbatim. The donor uses ordinary sampled-image limits only. The ShadeDoomVK set is created with `VK_DESCRIPTOR_SET_LAYOUT_CREATE_UPDATE_AFTER_BIND_POOL_BIT_EXT` and its binding uses update-after-bind plus variable descriptor count, so PF-003 includes relevant descriptor-indexing properties and scene-pipeline reservations.

### Vulkan specification research

Current Khronos Vulkan documentation used for the capacity model:

- https://docs.vulkan.org/spec/latest/chapters/descriptorsets.html
- https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceDescriptorIndexingProperties.html
- https://docs.vulkan.org/spec/latest/chapters/limits.html

Relevant facts:

- a combined image sampler counts against both sampler and sampled-image limits;
- pipeline layouts that include update-after-bind sets are constrained by the corresponding update-after-bind descriptor-indexing limits together with ordinary limits from non-update-after-bind sets;
- `maxPerStageUpdateAfterBindResources` counts resources from sets created with and without the update-after-bind-pool flag;
- `maxUpdateAfterBindDescriptorsInAllPools` bounds descriptors allocated from update-after-bind pools.

## Required descriptor-indexing features

The renderer now fails before descriptor-set construction unless all bindless features it actually uses are enabled:

- `descriptorBindingPartiallyBound`;
- `descriptorBindingVariableDescriptorCount`;
- `descriptorBindingSampledImageUpdateAfterBind`;
- `runtimeDescriptorArray`;
- `shaderSampledImageArrayNonUniformIndexing`.

This closes the previous mismatch where the feature check omitted two features required by the bindless layout flags.

## Descriptor address-space layout

The layout is defined in `vk_bindless.h`.

    [0, 3)       fixed shader resources
    [3, 259)     lightmap/probe-page descriptors
    [259, N)     dynamic material / colormap / environment-probe allocations

Constants:

- fixed descriptors: **3**;
- maximum lightmap atlas pages: **128**;
- descriptors per lightmap page: **2** — one light texture and one probe-index texture;
- lightmap/probe descriptors reserved: **256**;
- first dynamic descriptor: **259**;
- minimum configured/effective capacity: **260**.

The founding baseline started dynamic allocations at `3 + 128 = 131`, while `UpdateBindlessDescriptorSet()` consumes two descriptors per page. A map with more than 64 lightmap pages could therefore write into the dynamic range. PF-003 fixes this by deriving the dynamic start from `128 * 2` and rejects page counts above the declared 128-page contract.

Environment probes are different: each environment probe uses a two-descriptor **dynamic** allocation for irradiance + prefiltered cubemaps. They do not live in the fixed lightmap-page reservation.

## Device capacity model

`VkPlanBindlessCapacity()` computes a device limit from the most restrictive applicable candidate.

For combined samplers/sample images, the scene pipeline already exposes two fixed combined samplers, so two are reserved from:

- max(normal, update-after-bind) per-stage sampler limit;
- max(normal, update-after-bind) per-stage sampled-image limit;
- max(normal, update-after-bind) pipeline-layout sampler limit;
- max(normal, update-after-bind) pipeline-layout sampled-image limit.

The aggregate update-after-bind resource candidate reserves **15** non-bindless scene resources, matching the fixed set plus the larger LevelMesh/RSBuffer scene-set footprint visible to one graphics stage.

The remaining candidates are:

- `maxPerStageUpdateAfterBindResources - 15`;
- `maxUpdateAfterBindDescriptorsInAllPools`.

The lowest candidate is recorded as the limiting capability.

    effective capacity = min(vk_max_bindless_textures, derived device limit)

A requested value below 260 is a configuration error. A device-derived value below 260 is an unsupported-device error. The renderer does not silently shrink fixed or lightmap reservations to make such a device start.

## Allocation/reuse model

`VkBindlessSlotAllocator` owns the dynamic range.

- allocations are contiguous;
- freed allocations are bucketed by exact descriptor count;
- a reused block is taken only from the matching size bucket;
- every activation/retirement uses PF-002 generations;
- invalid/double/reserved-range frees are rejected;
- exhaustion returns failure to `VkDescriptorSetManager`, which emits a detailed fatal error rather than flushing live resources.

Diagnostics expose:

- requested/device/effective capacity;
- limiting device property;
- dynamic start;
- current descriptors;
- high-water descriptors;
- free descriptors;
- allocation/reuse/free/failure/invalid-free counts;
- PF-002 lifetime generation counters.

## Descriptor writes

All `SetBindlessTexture()` writes are bounds-checked against effective capacity.

`UpdateBindlessDescriptorSet()` validates:

- page count <= 128;
- computed page-descriptor end <= dynamic start;
- computed page-descriptor end <= effective capacity.

These checks make the reserved/dynamic boundary an executable invariant rather than arithmetic convention.

## No-flush rule

PF-003 explicitly rejects the MAD-VKDoom emergency global-flush pattern as a recovery mechanism. LevelMesh/material structures can retain raw descriptor indices; reclaiming the whole address space without invalidating every consumer can make an old index resolve to unrelated new data.

Exhaustion is therefore a precise controlled failure until a future issue introduces a proven safe ownership-wide remap strategy.

## Verification

`tools/pf_oracle/tests/bindless_allocator_fixture.cpp` covers:

- fixed/lightmap/dynamic compile-time boundaries;
- device-limit clamping and limiting-source selection;
- user cap below device maximum;
- invalid requested/device capacities;
- exact-size free-bucket reuse;
- generation change after reuse;
- stale-token rejection;
- full-capacity exhaustion;
- reserved-range free rejection;
- double-free rejection.

The PF source oracle separately pins the production capacity/reservation hooks.
