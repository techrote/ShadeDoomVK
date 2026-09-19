# PF-007 Vulkan capability and driver-quirk contract

Status: implementation contract for PF-007 / #24  
Baseline: `master@051d45b751362bdc4d6f446cade6284ab4a59854`

## Purpose

PF-007 replaces scattered Vulkan device/driver interrogation with one descriptive `VulkanCapabilities` snapshot owned by `VulkanRenderDevice`. The snapshot records hardware/driver facts and inherited quirk classifications. It does **not** choose rendering quality, remove workarounds, or make optional Vulkan facilities mandatory.

## Capability snapshot

`src/common/rendering/vulkan/vk_capabilities.h` names the audited capability categories:

- descriptor-indexing feature bits required by the inherited bindless renderer;
- descriptor/update-after-bind limits consumed by PF-003 bindless capacity planning;
- ray-query extension and feature state;
- acceleration-structure extension and feature state;
- graphics-pipeline-library extension and enabled-feature state;
- shader clip-distance feature state for diagnostics/future guarded use;
- the supported scene-MSAA sample-count intersection;
- exact inherited depth/stencil and normal-buffer format support/fallback results;
- device vendor, device ID, device type and driver version;
- Intel sampler and AMD ray-query driver-quirk classifications.

The snapshot is populated once immediately after `VulkanDeviceBuilder::Create()`. Format support is probed once using the same `ImageBuilder::IsFormatSupported()` tests and the same single-sample/4x fallback behavior as the baseline.

## Policy separation

Capability is descriptive; policy remains explicit at the consumer:

- `vk_rayquery` still decides whether a ray-query-capable device may use ray query.
- `vk_amd_driver_check` still permits the inherited AMD driver guard to be overridden.
- `gl_ubershaders` still decides whether a supported graphics-pipeline-library path is used.
- `gl_multisample` still supplies the requested sample count; the registry only selects the best supported count with the inherited algorithm.
- `gl_texture_filter_anisotropic`, texture filter selection, and integrated/discrete default anisotropy remain sampler policy. The registry only supplies device type and Intel quirk classification.
- PF-003 `vk_max_bindless_textures` remains the requested descriptor capacity. The registry supplies the physical descriptor limits used by the existing capacity planner.

PF-007 therefore makes no visual-quality/default change.

## Preserved optional fallbacks

### Ray query and acceleration structure

`VulkanCapabilities::SupportsRayQuery()` deliberately preserves the inherited activation predicate: ray-query extension plus physical ray-query feature. Acceleration-structure state is recorded independently and is not silently added as a new PF-007 requirement. `VulkanRenderDevice::mUseRayQuery` remains `vk_rayquery && SupportsRayQuery()` subject to the inherited AMD driver guard.

When ray query is not enabled, the fixed descriptor layout continues to bind the LevelMesh node storage buffer instead of an acceleration-structure descriptor. Shader traversal fallback ownership is unchanged.

### Graphics pipeline library

`SupportsGraphicsPipelineLibrary()` requires the extension plus the already-enabled graphics-pipeline-library feature, exactly matching the old local check. `gl_ubershaders == false` still disables pipeline-library use even when hardware support exists.

### Render-target formats

Depth/stencil preference remains:

1. `VK_FORMAT_D24_UNORM_S8_UINT`;
2. `VK_FORMAT_D32_SFLOAT_S8_UINT`;
3. fatal if neither inherited support probe succeeds.

Normal-buffer preference remains:

1. `VK_FORMAT_A2R10G10B10_UNORM_PACK32`;
2. `VK_FORMAT_R8G8B8A8_UNORM`;
3. fatal if neither inherited support probe succeeds.

No attachment usage, sample-count, or format preference is changed.

## Preserved driver workarounds and provenance

PF-007 relocates two inherited VKDoom-baseline policies without changing their predicates or effects.

### Intel sampler policy

The current-driver and legacy Intel PCI device-ID sets formerly embedded in `vk_samplers.cpp` now live with the pure classifier in `vk_devicequirks.h`.

For a legacy Intel device, or a listed current-driver device with driver version earlier than `0.405.1286`, the existing rule remains: anisotropy is forced to `1.0` when the selected texture filter contains nearest minification or magnification.

For all other Intel devices, the existing rule remains: filter mode 6 is remapped to 5 and the `NearestMipLinear` override uses nearest minification. Non-Intel devices receive no Intel sampler quirk.

The `0.405.1286` edge, legacy-device behavior, unknown Intel IDs, and non-Intel behavior are explicit adversarial fixture cases.

### AMD ray-query driver guard

The inherited AMDVLK guard remains exactly `vendorID == 0x1002 && VK_VERSION_MAJOR(driverVersion) < 10`. Its existing rationale is retained: the affected ray-query/specialization-constant path can stall the first frame long enough to cause a Windows device loss or a severe Linux freeze. PF-007 does not reinterpret vendor-specific `driverVersion` encoding and does not broaden or remove the workaround.

No donor implementation was introduced by PF-007, so `04-DONOR-PROVENANCE.md` requires no new donor entry.

## Consumers migrated

- `VulkanRenderDevice`: required bindless feature gate, ray-query capability, AMD quirk, selected render-target formats and startup diagnostics.
- `VkDescriptorSetManager`: PF-003 bindless capacity planning consumes the registry descriptor limits.
- `VkSamplerManager`: consumes device type and the named Intel sampler quirk instead of local vendor/driver tables.
- `VkRenderPassSetup`: consumes named graphics-pipeline-library support; `gl_ubershaders` remains separate policy.
- `VkRenderBuffers`: consumes the registry's supported scene sample counts through the inherited best-sample algorithm.

## Diagnostics

`PrintStartupLog()` now emits:

- required bindless, ray-query, acceleration-structure, graphics-pipeline-library and clip-distance capability state;
- whether ray query is actually enabled after user policy/driver guard;
- named Intel/AMD quirk state;
- scene sample-count mask;
- all descriptor-limit values used by PF-003 capacity planning;
- format-support booleans and the selected depth/normal formats.

This makes capability versus policy/fallback decisions inspectable without changing renderer behavior.

## Verification contract

`tools/pf_oracle/tests/vulkan_capabilities_fixture.cpp` covers boundary and adversarial cases for:

- legacy/current/unknown/non-Intel sampler classification;
- Intel driver versions immediately below and at `0.405.1286`;
- AMD driver-major boundary `9 -> 10`;
- every required bindless descriptor-indexing bit independently missing;
- ray-query and acceleration-structure independence;
- graphics-pipeline-library extension/feature conjunction;
- MSAA request clamping, sparse support masks and exact supported boundaries;
- depth/normal format priority, fallback and unsupported cases.

`test_vulkan_capabilities_contract.py` additionally locks the source-routing contract so the migrated consumers cannot silently regress to local vendor/feature/limit checks. The existing deterministic PF oracle remains the visual/state-equivalence guard, and the full inherited Windows/macOS/Linux build matrix remains required before merge.

## Protected semantics

PF-007 does not alter gameplay/tic behavior, shader/material meaning, palette or translation behavior, sprite rotation/mirroring, portals, decals/warps, translucent/canvas behavior, models/voxels/particles, classic-lighting rules, audio, demo determinism, source ownership, or provenance semantics.
