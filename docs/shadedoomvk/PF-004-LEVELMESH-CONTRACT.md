# PF-004 LevelMesh mutation and allocation contract

Status: implementation contract introduced by PF-004  
Date: 2026-09-19

## Purpose

PF-004 freezes the ownership and invalidation contract for the persistent LevelMesh substrate before later allocator, probe, visibility and material work consumes it. The change is intentionally bounded: it preserves Doom simulation and current valid rendering, keeps `SurfaceUpdateType` plus `MeshBufferUploads` authoritative, and adds diagnostics/defensive checks rather than a second invalidation engine.

## Source audit and corrected defects

The PF-004 audit found two concrete divergence hazards inside the issue's existing scope.

### CPU BLAS dirty-partition rounding

`CPUAccelStruct::Update()` previously computed the exclusive dirty partition as `range.End / IndexesPerBLAS`. A dirty range wholly inside one partition therefore produced the same start/end partition and rebuilt nothing. Raster/GPU data could update while CPU renderer traces retained an old BLAS.

PF-004 routes both CPU and Vulkan range-to-partition mapping through `MeshBufferChunkStart()` / `MeshBufferChunkEndExclusive()`. The exclusive end is rounded upward. Boundary fixtures pin one-element, exact-boundary and cross-boundary cases. Vulkan additionally clamps dirty marking to the currently allocated `DynamicBLAS` vector so buffer growth cannot index the old AS vector before `CheckBuffers()` resets/recreates it.

### Texture-Z two-sided callback

`DoomLevelMesh::OnSectorChangedTexZ()` used `if (...) ... else if (...) ...` for the two sidedefs of each line. When both existed, only sidedef 0 was scheduled for `Full` rebuild. PF-004 makes the tests independent, matching the floor/ceiling geometry callbacks and preventing the opposite side from retaining stale surface/query data.

`OnMidTex3DHeightChanged()` remains unchanged: the inherited callback is intentionally empty and its exact gameplay/render ownership is not established by this repair. PF-004 does not invent a broad refresh for an unproven path.

## Ownership domains

`LevelMeshMutationDomain` is a diagnostic epoch vocabulary over the existing mutation machinery:

- **Geometry** — vertex/index allocation and geometry replacement;
- **Surface** — surface/uniform/material/light-uniform state;
- **Lights** — persistent light records, light lists and dynamic-light uploads;
- **Query** — CPU collision/query geometry and AS-visible surface/index state;
- **Portals** — uploaded portal transforms/metadata;
- **LightmapProbe** — tile allocation/release, lightmap dependencies and atlas-coordinate changes.

`LevelMeshMutationEpochs` only records which owned domain changed. It does not decide how an update propagates. `SurfaceUpdateType`, Doom callbacks, `MeshBufferUploads`, `CPUAccelStruct::Update()` and `VkLevelMesh::BeginFrame()` remain the authoritative propagation paths.

`LevelMesh::Reset()` advances both the PF-002 whole-resource epoch and all PF-004 mutation-domain epochs.

## Allocator/lifetime contract

`MeshBufferAllocator` is moved to the dependency-light `hw_levelmesh_contract.h` so its production behavior is directly testable.

The inherited first-fit allocation and growth policy are retained; PF-018 still owns allocator performance. PF-004 adds:

- bounds checks before free;
- exact live-span validation;
- rejection of overlap/double-free and wrong-span free;
- PF-002 `{index,generation,epoch,span}` identity tracking for every non-empty allocation;
- stale-token validation after free/reuse/reset;
- allocation/free/grow/reset/invalid-operation counters;
- fail-closed LevelMesh wrappers before mutating paired geometry ranges.

Zero-length light lists remain valid and consume no allocation identity.

## Raster/query/AS responsibility

For a full side/flat/polyobject rebuild, allocation/free changes add index dirty ranges. During the same `DoomLevelMesh::BeginFrame()`:

1. Doom callbacks/coalesced `SurfaceUpdateType` rebuild current LevelMesh arrays;
2. lightmap atlas work updates dependent UV/page state;
3. `CPUAccelStruct::Update()` consumes dirty index ranges and rebuilds affected CPU BLAS/TLAS state;
4. `VkLevelMesh::BeginFrame()` consumes the same dirty ranges for GPU upload and, when ray query is active, affected Vulkan BLAS/TLAS state.

The shared chunk helper makes CPU and Vulkan partition coverage one executable contract rather than two subtly different formulas.

## Lightmap/probe responsibility

Tile allocation/release and atlas-coordinate changes advance the `LightmapProbe` mutation epoch. Atlas packing explicitly records the vertex upload for the affected surface after writing lightmap UV/page coordinates. Light-list/shadow changes mark dependent tiles through the existing `ReceivedNewLight` path and advance the lightmap/probe diagnostic epoch.

This does not change probe selection; PF-012 owns probe plumbing correctness after PF-004.

## Compatibility and performance boundary

PF-004 does not:

- alter Doom gameplay/tic semantics;
- change material, portal, palette/translation, sprite or audio meaning;
- reduce eligible geometry/lights or rendering precision;
- redesign allocator growth/free-bin policy;
- introduce unconditional full refreshes as a substitute for precise invalidation.

The only content-visible differences should be correction of stale renderer/query state on affected mutations or fail-closed detection of internal allocator corruption.

## Verification

Hosted CI compiles and runs `tools/pf_oracle/tests/levelmesh_contract_fixture.cpp`, which covers:

- normal allocation/free/coalescing;
- wrong-span, double-free, negative and out-of-bounds rejection;
- same-index reuse with generation change and stale-token rejection;
- reset epoch invalidation;
- one-element, exact and crossing BLAS partition boundaries;
- mutation-domain selective marking and reset.

The source oracle pins the production CPU/Vulkan shared partition helper, LevelMesh allocator generation hooks, mutation epochs and the two-sided texture-Z callback. The inherited Windows/macOS/Linux matrix remains required before merge.
