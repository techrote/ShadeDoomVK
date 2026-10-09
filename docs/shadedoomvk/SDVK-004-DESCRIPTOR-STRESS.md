# SDVK-004 — rich-material descriptor/lifetime stress qualification

Date: 2026-10-09. Owner: SDVK-004 / #4. Status: **accepted, merged and verified** through PR #126 / `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b`; release evidence is pinned in [SDVK-004-RELEASE-ACCEPTANCE.json](SDVK-004-RELEASE-ACCEPTANCE.json).

## Scope and authority

This qualification consumes the accepted PF-002 generation/epoch model, PF-003 bindless capacity/allocation contract, PF-008 material semantic/sampler contract, PF-012 probe/lightmap identity contract, SDVK-002 observer/corpus, and SDVK-003 upstream ownership policy. It does not introduce a second resource-identity system and does not import descriptor/material renderer code from UZDoom/GZDoom.

Starting source identity for the dedicated branch is verified `master@c8b6db4dedae5da27249b6738f7628cf3a41b80a`.

## Demonstrated integration defect and repair

PF-003 correctly rejected ordinary exhaustion, but `VkBindlessSlotAllocator::Allocate(count)` sized its exact-span free-bucket vector from `count` before proving that a positive span could fit anywhere in the configured dynamic range. A pathological positive span such as `INT_MAX` could therefore attempt a huge host allocation instead of returning the existing bounded allocation failure.

SDVK-004 adds one pre-bucket fit guard:

`count > Capacity - DynamicStart`

The guard is intentionally against the **entire dynamic range**, not the remaining virgin tail. That preserves PF-003 exact-size reuse when `NextIndex` is at capacity but a retired span of the requested size is available. Ordinary allocation, free, generation, reuse, reservation and descriptor publication semantics are otherwise unchanged.

The inherited PF-003 fixture now retains this negative regression.

## Deterministic rich-workload contract

`tools/pf_oracle/tests/sdvk004_rich_descriptor_fixture.cpp` uses the production PF-002/PF-003 primitives directly and models the live descriptor span widths used by Vulkan material construction.

| Workload | Owners/variants | Descriptor span | Dynamic descriptors |
| --- | ---: | ---: | ---: |
| ordinary semantic materials | 128 | 4 | 512 |
| legacy normal/specular materials | 96 | 6 | 576 |
| PBR normal/M/R/AO materials | 96 | 8 | 768 |
| translated/palette/indexed variants | 128 | 2 | 256 |
| hardware-canvas materials | 64 | 1 | 64 |
| PBR + four custom-shader textures | 64 | 12 | 768 |
| environment probe pairs | 64 | 2 | 128 |
| **total** | **640 descriptor owners; 576 materials** | — | **3072** |

The configured effective descriptor count is 4355. With `DynamicStart=259`, the dynamic budget is 4096 descriptors; the deterministic rich workload therefore reaches a **3072 descriptor / 75% dynamic high-water mark**, leaving 1024 dynamic descriptors.

The fixture additionally performs:

- 64 cycles of canvas retirement/recreation;
- 64 translated/palette variant retire/reuse cycles;
- 64 PBR material retire/reuse cycles;
- a complete material + environment-probe descriptor teardown/rebuild equivalent to the descriptor side of sampler invalidation;
- 64 texture-owner, lightmap-owner and probe-owner epoch transitions with stale-token rejection;
- descriptor-manager reconfiguration with allocator-epoch stale-token rejection;
- maximum 128-page fixed lightmap/probe-page publication followed by shrink to 3 pages and fallback publication over retired pages;
- requested/device-limit underflow rejection and update-after-bind pool capacity clamping;
- exact-capacity allocation, exact-size fragmentation, safe exhaustion and an `INT_MAX` allocation request.

Every retired identity is queried deliberately as a negative control. Current identities must remain valid; invalid/double-free counters must remain zero; explicit capacity failures must not invalidate live allocations.

## Live integration assertions

`test_sdvk004_rich_descriptor_contract.py` ties the synthetic pressure model back to production paths rather than treating the allocator in isolation:

- `VkMaterial::DescriptorEntry` retains clamp, translation/remap, global-shader, palette/indexed and RedIsAlpha identity;
- ordinary/legacy/PBR/custom material descriptor counts follow the existing ordered layer model and per-layer sampler overrides;
- indexed/palette materials retain their two-descriptor R8 + palette-row path;
- `SetTextureFilterMode()` retires descriptor consumers through `ResetHWTextureSets()` before sampler recreation;
- descriptor reset frees material variants, software colormaps and environment-probe dynamic pairs through normal PF-003 frees;
- `FGameTexture::CleanHardwareData()` cleans the hardware resource and retires every material descriptor variant, covering repeated hardware-canvas resource recreation;
- lightmap recreation advances `LightmapEpoch`; reserved-page publication uses `VkPlanLightmapDescriptorPublication` and typed fallback pages;
- probe-content reset advances `LightProbeEpoch` while retaining the same environment-map image owners; environment descriptor identity remains an allocator-owned adjacent pair;
- the SDVK-002 observer exposes effective/device/requested descriptor capacity, current/high-water pressure, allocation/reuse/free/failure counters, PF lifetime state and texture/lightmap/probe resource epochs.

## Native and image/state qualification

No physical GPU claim is made by this qualification.

The existing SDVK-002 software-Vulkan corpus is the native qualification route because it already pairs screenshots with machine-readable semantic state and contains the relevant renderer-visible families. SDVK-004 extends the existing `material-stress` recipe in place with eight PBR panels that use a real GLDEFS hardware shader and custom texture binding; nearest/linear custom sampling alternates across those panels, and the state assertions require their authored `custom` layer semantic.

The current eight-scene software-Vulkan lane therefore covers:

- semantic material stress, including real custom-shader texture bindings;
- compositing/camera texture canvas paths;
- probe/sun/lightmap paths;
- portal/view isolation;
- resource-stress state and renderer pressure counters.

The retained `pf-indexed-material` recipe is **not** selected by the hosted
`native_ci.py` eight-scene lane, so SDVK-004 does not relabel
translation/palette behavior as new llvmpipe evidence. Under this issue,
128 translated/palette variants participate in the deterministic descriptor
pressure/rebuild contract and production source assertions preserve the indexed
two-resource path and translation identity. Renderer correctness for that path
is consumed from the already accepted PF-110 qualification: PR #116's recorded
native evidence independently checked 983,040 indexed pixels with zero
mismatches, including translation/palette and restart/lifetime cases. The
accepted GLDEFS custom-sampling parser contract is likewise retained; SDVK-004's
new llvmpipe evidence adds an actual rendered custom-shader binding on top of
that parser contract.

Those gates passed at exact PR head `862ae0f591d60572c2474f0b6f22d44bfbb30e24` in source-evidence run `37962887608` and all-nine-job CI run `37962887060`. PR #126 merged as `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b`; the merged tree is byte-identical to the tested PR merge-ref tree and passed source-evidence run `37974299356` plus all-nine-job CI run `37974299316`. The software-Vulkan resource observations are therefore the current native pressure baseline rather than a parallel diagnostic path.

## Pressure budget for later SDVK work

Later material issues should treat these as the accepted qualified baseline:

- fixed bindless range ends at descriptor 258 inclusive; dynamic allocations begin at 259;
- 128 lightmap pages consume the complete fixed 256-descriptor page reservation, never dynamic slots;
- an environment probe consumes a dynamic adjacent pair;
- the deterministic rich-material baseline consumes 3072/4096 dynamic descriptors (75%);
- capacity is always `min(requested, actual derived device/runtime limit)`, with the limiting Vulkan property retained by diagnostics;
- allocation exhaustion is a bounded explicit failure, never permission to globally flush live descriptor identities;
- exact-size free buckets may produce safe fragmentation; reported free descriptor count is aggregate capacity, not a promise that every requested contiguous span is reusable.

## Acceptance state

The substantive implementation is accepted, merged and verified.

- exact final PR head: `862ae0f591d60572c2474f0b6f22d44bfbb30e24`;
- PR #126 tested merge-ref tree: `9ce95e42441744d2270954bbec25b193d2d019ae`;
- exact-head source evidence: run `37962887608`, PASS;
- exact-head Continuous Integration: run `37962887060`, **9/9 PASS**;
- implementation merge: `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b`, tree `9ce95e42441744d2270954bbec25b193d2d019ae`;
- post-merge source evidence: run `37974299356`, PASS;
- post-merge Continuous Integration: run `37974299316`, **9/9 PASS**;
- post-merge software-Vulkan `material-stress`: 438 current/high-water descriptors, 72 allocations, 4 reuses, 4 frees, 0 failures and 0 invalid frees;
- post-merge `sun-probes`: one lightmap page, two irradiance maps and two prefilter maps;
- all eight authored custom PBR panels are actual draw witnesses with span 9, custom binding 8/index 0 and alternating nearest/linear requests;
- physical GPU qualification is not claimed and was not required because software-Vulkan/native qualification exposed no unresolved hardware-specific defect.

The complete hashes, artifact IDs, inherited indexed-material evidence boundary and retained failed run are in [SDVK-004-RELEASE-ACCEPTANCE.json](SDVK-004-RELEASE-ACCEPTANCE.json).
