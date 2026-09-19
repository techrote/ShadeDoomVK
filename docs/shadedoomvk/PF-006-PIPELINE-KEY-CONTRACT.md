# PF-006 Vulkan pipeline/shader key contract

Status: implementation contract introduced by PF-006  
Date: 2026-09-19

## Purpose

PF-006 removes renderer-cache identity dependence on C++ object representation for `VkShaderKey`, `VkPipelineKey` and `VkRenderPassKey`. Key equality and ordering now derive from explicitly named renderer state only. The change is an identity refactor: shader behavior, pipeline state selection, material meaning, render-pass construction and gameplay/tic semantics are not changed.

## Sources and provenance

This implementation is derived from the existing ShadeDoomVK/VKDoom key construction and cache use on the PF-006 base. No donor code is copied or adapted, so `04-DONOR-PROVENANCE.md` requires no new donor entry.

Primary implementation sources:

- `src/common/rendering/vulkan/vk_keyidentity.h`;
- `src/common/rendering/vulkan/shaders/vk_shader.h`;
- `src/common/rendering/vulkan/pipelines/vk_renderpass.h`;
- `src/common/rendering/vulkan/pipelines/vk_renderpass.cpp`;
- `src/common/rendering/vulkan/vk_renderstate.cpp`.

## Canonical identity

`VkKeyIdentity` contains representation-independent state records:

- `ShaderState` names every meaningful `VkShaderKey` specialization/layout field;
- `PipelineState` names every meaningful graphics-pipeline field plus canonical shader state and `FRenderStyle::AsDWORD`;
- `RenderPassState` names depth/stencil presence, sample count, draw-buffer count and draw-buffer format.

The public Vulkan key classes expose `CanonicalState()` and implement ordered-map equality/ordering through these records. Padding, tail padding and reserved/unused bitfields are not cache identity.

This deliberately keeps the existing `std::map` cache topology. PF-006 makes no lookup-performance claim; PF-019 owns later pipeline-worker/cache optimization after identity is frozen.

## Shader specialization ABI

`VkShaderKey::AsQWORD` remains the packed shader specialization word consumed by pipeline creation. PF-006 does not reinterpret or reorder its meaningful bits. `AddPreRasterizationShaders()` and `AddFragmentShader()` continue to send the lower and upper 32-bit halves as specialization constants.

The packed word is therefore still shader ABI, but it is no longer used as the complete C++ cache equality/order contract.

## Generalized shader cache

The inherited generalized shader cache intentionally uses a narrower key than a specialized shader. PF-006 preserves that partition explicitly through `ShaderState::GeneralizedCacheKey()`:

- the seven meaningful shader-layout bits retain their original positions in the low 32 bits;
- `EffectState` retains the upper-word placement;
- low eight bits of `SpecialEffect` and `VertexFormat` retain their former placements;
- specialized-only texture/fog/light/shadow flags remain outside generalized cache identity exactly as before.

This preserves built-in/user shader distinctions and generalized/specialized behavior without depending on `Layout.AsDWORD` reserved bits.

## Pipeline libraries and workers

PF-006 does not change pipeline-library decomposition or background compilation:

- specialized and generalized pipeline maps remain separate;
- vertex-input, vertex-shader, fragment-shader and fragment-output libraries retain their existing normalization rules;
- fragment-library precache still queues through `RunOnWorkerThread(..., true)`;
- specialized pipeline work still uses the priority worker path;
- main-thread completion still installs the produced pipeline into the same semantic key slot.

Because copied keys compare by named state rather than bytes, worker handoff no longer depends on padding preservation.

## Vulkan driver pipeline cache

`pipelinecache.zdpc` is the Vulkan driver pipeline-cache blob returned by `VulkanPipelineCache::GetCacheData()` and supplied through `PipelineCacheBuilder::InitialData()`. The C++ renderer key objects are not serialized into that file.

PF-006 therefore does not introduce a renderer-key disk-format migration and does not invalidate or reinterpret the Vulkan driver cache format.

## Verification

`tools/pf_oracle/tests/pipeline_key_contract_fixture.cpp` models the former valid zero-initialized object representation and compares it with the new semantic state partition. It covers:

- every meaningful shader-key field independently, including multi-bit boundaries;
- every meaningful pipeline-key field;
- representative render-pass sample/draw-buffer/format states;
- built-in/user/effect and LevelMesh/ray-precision generalized distinctions;
- warm ordered-map lookup after key reconstruction;
- adversarial old padding and reserved-bit noise which formerly changed `memcmp` identity but must not create a renderer-state split.

`tools/pf_oracle/tests/test_pipeline_key_contract.py` additionally pins the production source routes, preserves shader specialization constants, worker/library/cache paths and compiles/runs the boundary fixture under the PF oracle job.

The deterministic PF oracle remains the output/state baseline. The full inherited Windows, macOS and Linux matrix remains required before acceptance.

## Preserved semantics and limitations

PF-006 changes no shader source, blend/depth/stencil/cull policy, material selection, portal behavior, palette/translation behavior, sprite conventions, audio, gameplay/tic state or source provenance.

`VkPPRenderPassKey` is not one of the three keys assigned to PF-006 and is not changed by this contract. Postprocess pipeline semantics remain outside this corrective issue.
