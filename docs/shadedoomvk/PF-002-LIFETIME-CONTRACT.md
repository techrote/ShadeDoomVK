# PF-002 renderer lifetime and generation contract

Status: implementation contract introduced by PF-002  
Date: 2026-09-17

## Purpose

ShadeDoomVK has several renderer-owned integer identities that are cheap and appropriate in hot paths, but unsafe to treat as durable semantic identities once their storage is recycled or reset. PF-002 introduces a small validation layer that later PF issues can consume without replacing those integers with heavyweight objects.

The contract has two primitives in `src/common/rendering/hwrenderer/data/hw_resourcegeneration.h`.

## Per-slot generation identity

`FRendererResourceGenerationTable` tracks recyclable indexed blocks.

A durable diagnostic/reference token is:

```text
{ index, generation, epoch, span }
```

Operations:

- `Activate(index, span)` marks a block live and returns its current identity.
- `Retire(index)` makes the old identity stale and advances the slot generation.
- `Reset()` invalidates every prior identity by advancing the table epoch.
- `Current(index)` returns the live identity when one exists.
- `IsCurrent(token)` performs a read-only validity check.
- `Validate(token)` checks validity and increments `StaleRejects` on failure.

The table also records activation, retirement, reset, stale-rejection, invalid-retire and duplicate-activation counters.

The generation value is deliberately opaque. Callers compare it; they do not infer age or ordering from its magnitude.

## Owner-wide epoch

`FRendererEpoch` is the cheaper contract for resources that are invalidated as a domain rather than individually recycled.

- `Snapshot()` returns an `FRendererEpochToken`.
- `Invalidate()` advances the epoch.
- `Validate(token)` rejects a stale token and records the rejection.

This is intended for reset boundaries, not per-object identity.

## Wiring established by PF-002

| Domain | Current hook | Invalidation event | Later owner |
|---|---|---|---|
| dynamic bindless blocks | `VkDescriptorSetManager::Bindless.Generations` | `FreeBindlessSlot`; reuse through `AllocBindlessSlot` | PF-003 |
| LevelMesh owner state | `LevelMesh::ResourceEpoch` | every `LevelMesh::Reset()` | PF-004 |
| Vulkan texture resource domain | `VkTextureManager::TextureEpoch` | hardware/postprocess texture removal; manager deinit | PF-005 / later resource work |
| lightmap texture domain | `VkTextureManager::LightmapEpoch` | full `CreateLightmap(...)` rebuild; manager deinit | PF-003/PF-012/PF-014 |
| environment-probe texture domain | `VkTextureManager::LightProbeEpoch` | `ResetLightProbes()`; manager deinit | PF-012 |
| async texture work domain | `VkTextureManager::AsyncUploadEpoch` | worker shutdown; manager deinit | PF-005 |

Material descriptor destruction already funnels through `FreeBindlessSlot`, so descriptor identities retire when a `VkMaterial` deletes its descriptor entries.

## Deliberately not converted in PF-002

The following remain raw/current representations until their owning issues establish the correct scope:

- LevelMesh vertex/index/uniform/surface/light-list allocation ranges — PF-004;
- upload IDs and per-target async texture generation — PF-005;
- fixed bindless slots and capacity/reservation arithmetic — PF-003;
- lightmap/probe descriptor slot reservation policy — PF-003/PF-012;
- frame-local dynamic-light pointer/index identity — PF-016/PF-017;
- shadow-map slot identity — PF-015;
- Vulkan native handles — remain Vulkan ownership objects, not PF generation tokens.

PF-002 does not require a long-lived token where the lifetime is already strictly frame/local-owner scoped.

## Threading rule

The generation/epoch primitives are intentionally not internally synchronized. Their current mutations occur on renderer-owner paths. Any later cross-thread consumer must synchronize access at its owning subsystem boundary rather than adding hidden locks to every generation check.

PF-005 must therefore use the accepted async queue synchronization when applying per-target upload generations.

## Validation rule

A stale reference is a normal validation failure, not a generation-number error. The deterministic fixture at `tools/pf_oracle/tests/resource_generation_fixture.cpp` proves:

1. a live slot identity validates;
2. retirement invalidates the old identity;
3. reuse produces a different generation;
4. table reset invalidates all old identities through the epoch;
5. duplicate activation does not leave an old identity valid;
6. stale/invalid operations increment diagnostics;
7. owner-wide epochs reject pre-reset snapshots.

The PF oracle pins the source hooks so later refactors must update the contract deliberately.

## Compatibility/performance rule

PF-002 does not change which texture, material, light, probe or surface the renderer selects. Generation checks are currently on allocation/reset/diagnostic paths, not per-fragment/per-vertex rendering paths. Later issues may consume tokens only where the validation benefit justifies their storage/check cost.

## Failure rule

Never solve a stale identity by globally flushing resources while leaving live consumers with raw old indices. If a later subsystem cannot identify its owner/reset boundary precisely, it must stop and refine that ownership contract rather than weakening validation.
