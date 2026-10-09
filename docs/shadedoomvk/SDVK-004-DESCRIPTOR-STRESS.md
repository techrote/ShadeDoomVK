# SDVK-004 — rich-material descriptor/lifetime stress qualification

Date: 2026-10-09. Owner: SDVK-004 / #4. Status: **implementation candidate; exact-head CI/native qualification pending**.

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

No physical GPU claim is made by this candidate.

The existing SDVK-002 software-Vulkan corpus is the native qualification route because it already pairs screenshots with machine-readable semantic state and contains the relevant renderer-visible families. SDVK-004 extends the existing `material-stress` recipe in place with eight PBR panels that use a real GLDEFS hardware shader and custom texture binding; nearest/linear custom sampling alternates across those panels, and the state assertions require their authored `custom` layer semantic.

The native route therefore covers:

- semantic material stress, including real custom-shader texture bindings;
- indexed/palette material paths;
- compositing/camera texture canvas paths;
- probe/sun/lightmap paths;
- portal/view isolation;
- resource-stress state and renderer pressure counters.

Final SDVK-004 acceptance requires the exact PR head to pass the repository CPU contract suite, deterministic corpus preparation, all hosted builds, exact executable/source identity checks and the full Linux software-Vulkan corpus. The resulting software-Vulkan resource observations will be used as the native pressure baseline rather than inventing a parallel diagnostic path.

## Pressure budget for later SDVK work

Later material issues should treat these as the initial qualified baseline, subject to exact-head CI confirmation:

- fixed bindless range ends at descriptor 258 inclusive; dynamic allocations begin at 259;
- 128 lightmap pages consume the complete fixed 256-descriptor page reservation, never dynamic slots;
- an environment probe consumes a dynamic adjacent pair;
- the deterministic rich-material baseline consumes 3072/4096 dynamic descriptors (75%);
- capacity is always `min(requested, actual derived device/runtime limit)`, with the limiting Vulkan property retained by diagnostics;
- allocation exhaustion is a bounded explicit failure, never permission to globally flush live descriptor identities;
- exact-size free buckets may produce safe fragmentation; reported free descriptor count is aggregate capacity, not a promise that every requested contiguous span is reusable.

## Acceptance state

Not yet accepted at this checkpoint. Final acceptance must pin:

1. exact final PR head;
2. focused rich-descriptor fixture result;
3. full `python3 tools/check.py --output ...` result;
4. exact-head Renderer source evidence and all Continuous Integration jobs;
5. full software-Vulkan corpus result and retained resource-pressure observations;
6. merged commit and verified post-merge `master`;
7. updated RAG/ledger/canonical issue status and durable issue #4 acceptance comment.

Physical-GPU qualification remains optional unless software-Vulkan/native evidence exposes a driver/device-limit defect that cannot be resolved without a finite hardware packet.
