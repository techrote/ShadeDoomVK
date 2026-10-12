# LevelMesh mutation and invalidation matrix

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: PF-004 mutation/allocation contract active; PF-012 probe-map invalidation and PF-015 visibility-cache consumption incorporated; PF-018 accepted with hybrid best-fit free-span lookup and cached immutable AABB topology, preserving those semantics
Primary issues: PF-004, PF-012, PF-015, PF-018, SDVK-014

`LevelMesh`/`DoomLevelMesh` is the persistent renderer-side world representation used by lightmapping, renderer traces, Vulkan buffers and acceleration structures.

Primary files:

- `src/common/rendering/hwrenderer/data/hw_levelmesh.h/.cpp`
- `src/common/rendering/hwrenderer/data/hw_levelmesh_contract.h`
- `src/common/rendering/hwrenderer/data/hw_aabbtree.h/.cpp`
- `src/rendering/hwrenderer/doom_levelmesh.h/.cpp`
- `src/rendering/hwrenderer/doom_aabbtree.h/.cpp`
- `src/common/rendering/vulkan/vk_levelmesh.h/.cpp`
- `src/levelmeshhelper.h`

## Ownership

`LevelMesh` owns generic renderer arrays, allocation/free-list state and dirty upload ranges. `DoomLevelMesh` owns Doom-side mapping and mutation callbacks. `VkLevelMesh` owns Vulkan mirrors/uploads and acceleration structures.

PF-004 adds an inspectable diagnostic vocabulary over those existing owners:

- `Geometry` — vertex/index allocation and replacement;
- `Surface` — surface, material, uniform and light-uniform state;
- `Lights` — persistent lights, light lists and dynamic-light uploads;
- `Query` — renderer trace/collision and AS-visible world state;
- `Portals` — uploaded portal transform/metadata state;
- `LightmapProbe` — lightmap tile/atlas/probe dependencies.

`LevelMeshMutationEpochs` records domain changes. It is not a second scheduling system: `SurfaceUpdateType`, Doom callbacks, `MeshBufferUploads`, CPU collision updates and Vulkan upload/AS paths remain authoritative.

## Mutation expectations

| Mutation | Geometry | uniforms/material | lights | renderer trace data | lightmap/probe | GPU/AS |
|---|---|---|---|---|---|---|
| floor/ceiling height | update | update | possible membership | update | affected tiles/targets | dirty buffers and AS as needed |
| side/midtexture geometry | update | update | possible membership | update | affected tiles | dirty buffers and AS as needed |
| texture/material change | shape unchanged | update | normally unchanged | unchanged | material/lightmap association may change | uniforms/descriptors |
| sector light level | unchanged | light uniforms | interaction changes | unchanged | dynamic-lightmap policy | light uniforms |
| side/sector light list | unchanged | light refs | update | unchanged | dynamic inputs | light-index/light buffers |
| dynamic light change | unchanged | unchanged | update | unchanged | dynamic inputs | light/dynlight buffers |
| decal change | rendered surface state changes | update | affected lighting | normally unchanged | affected rendering | geometry/uniform ranges as applicable |
| polyobject motion | update | update | membership can change | update | affected dynamic tiles | dynamic AS/update |
| portal transform/topology | portal/related geometry metadata | update | portal-relative positions | traversal semantics | visibility/targets | portal/surface buffers and related AS |
| lightmap atlas repack | unchanged | lightmap coordinates/index | unchanged | unchanged | atlas metadata changes | vertices/descriptors |
| probe set/rebake | unchanged | sector/side probe target | unchanged | unchanged | **all existing per-texel probe mappings stale** | probe descriptors/maps |

PF-004 validated the base table against production callbacks and made the owned domains inspectable through `LevelMeshMutationEpochs`. PF-012 makes the probe-set row executable for runtime debug placement: `addlightprobe` and `autoaddlightprobes` recalculate sector/side targets, mark every existing lightmap tile `ReceivedNewLight`, and advance `LightmapProbe` before the map can be trusted again. The epochs diagnose existing invalidation paths; they do not replace `SurfaceUpdateType`, upload ranges or callback scheduling.

PF-015 consumes the already-authoritative `Query` epoch at actor/static-light and sunlight visibility-cache boundaries. A geometry/query mutation therefore invalidates cached visibility even if actor and light positions remain unchanged. PF-015 does not increment `Query` itself and does not add a second world-dirty mechanism.

## Existing invalidation vocabulary

`DoomLevelMesh` receives callbacks for floor/ceiling height, textures, decals, sector light and light-list changes. Side/flat blocks carry `SurfaceUpdateType` values `LightLevel`, `Shadows`, `LightList` and `Full`; conflicting partial requests coalesce to `Full`.

PF-004 keeps that vocabulary. `OnSectorChangedTexZ()` now schedules both sidedefs of a two-sided line rather than suppressing sidedef 1 through `else if`. The inherited `OnMidTex3DHeightChanged()` no-op remains explicitly unclaimed: PF-004 does not substitute a broad refresh without source-proven ownership semantics.

PF-012 does not introduce another surface-update class. Probe-set changes reuse the existing tile rebake trigger because the lightmap copy stage writes both the lighting result and the associated per-texel probe-map result.

PF-015 similarly does not add a mutation producer. It records the current `GetMutationEpochs().Query` in renderer visibility-cache state and rejects reuse when that value changes.

## Allocation/update behavior

`MeshBufferAllocator` keeps address-ordered free ranges as the coalescing/validation authority. The PF-018 implementation scans lists of at most eight ranges for deterministic best fit, avoiding index-node churn in lightly fragmented moving-polyobject frames. Larger lists use a `{span size, start address}` index. Both paths choose the lowest address among equal-size spans. PF-004 PF-002 generation/span tracking and fail-closed bounds, wrong-span, overlap and double-free checks remain authoritative; lookup does not create a second ownership model.

PF-018 growth is bounded geometric growth: on a miss, capacity grows by the larger of the required extension and 50% of current capacity, clamped to `INT_MAX`. Existing live allocations remain stationary. `pf018stats` exposes search/candidate counts, small-list/indexed attempts and index mutations, grow events/elements, peak free-range count and peak/used/free capacity for representative-workload comparison.

`MeshBufferUploads` remains the dirty-range authority and retains its existing merge semantics in PF-018. No copy batching/upload rewrite is claimed without byte-identical real-workload evidence; callers can continue to inspect the authoritative merged ranges when collecting upload counts/volume.

The Doom world AABB tree has immutable topology after construction: polyobject motion changes line coordinates and bounding boxes, not child edges. PF-018 therefore caches each tree line's leaf plus each node's parent once after construction. Moving-line updates reconstruct the same historical leaf→root path by following parents instead of recursively searching the complete tree from the root on every changed line. Any future topology mutation must rebuild this cache; bounding-box-only updates do not invalidate it. Observational counters cover cache builds, path lookups/steps, moved lines, updated nodes and cumulative update time.

CPU and Vulkan acceleration-structure paths continue to share `MeshBufferChunkStart()` / `MeshBufferChunkEndExclusive()`. The exclusive end is rounded up, fixing the CPU path that previously selected zero BLAS partitions when a dirty index range fell wholly inside one partition. Vulkan dirty marking remains bounded by the currently allocated BLAS vector while buffer growth is waiting for `CheckBuffers()` to reset/recreate acceleration structures.

## Coupled resources

Lightmap page count influences texture/descriptor resources; probe maps share the lightmap-page concept. Resource rebuilds therefore participate in `02-RENDERER-IDENTITY-LIFETIME.md`.

Tile allocation/release advances the `LightmapProbe` mutation domain. Atlas packing explicitly places rewritten lightmap UV/page vertices in the vertex upload range. Light-list and shadow changes retain the existing `ReceivedNewLight` tile invalidation and advance the diagnostic domain.

PF-012 adds a second boundary check at the actual lightmap copy consumer: a selected tile's `AtlasLocation.ArrayIndex` must be below both `LevelMesh::Lightmap.TextureCount` and the Vulkan texture manager's current lightmap resource vector. Mismatch fails closed before framebuffer/image dereference. The mapped copy-tile staging range is also checked before per-page writes.

## Required invariants

1. Visible world data and renderer query/occlusion data must describe the same current geometry.
2. Free/reallocated ranges must not leave live stale references; allocator diagnostic identities must reject old generations after free/reuse/reset.
3. Dirty-range merging may combine work but may not omit required updates; a non-empty range must touch every CPU/Vulkan BLAS partition it intersects.
4. Lightmap/probe invalidation must be explicit rather than relying on stale data looking plausible; tile/atlas changes advance the `LightmapProbe` domain and atlas UV/page writes are uploaded.
5. A changed probe set makes every existing per-lightmap texel probe selection stale; runtime placement paths must schedule regeneration before those mappings are trusted.
6. Lightmap copy page identity must be valid in both current LevelMesh metadata and current Vulkan resources before use.
7. Two-sided Doom mutation callbacks must schedule both affected sidedefs; `OnSectorChangedTexZ()` is source-pinned by the PF oracle.
8. Any renderer visibility cache whose result depends on LevelMesh trace geometry must reject reuse across a `Query` epoch change; PF-015 pins this at actor/static-light and sun-trace caches.
9. PF-018 allocator indexing/growth must preserve PF-004 generation/span ownership and may not move live ranges.
10. PF-018 AABB caching may change path-discovery cost only: leaf identity, leaf→root order, updated AABBs and trace/query results must remain identical. Any topology mutation requires cache rebuild before cached paths are reused.
11. PF-018 acceptance requires a representative real renderer CPU/memory/resource benefit plus identical protected image/query/state semantics on the changed path. The reconciled implementation demonstrated DBP37 MAP04 array-capacity benefit and targeted moving-AABB query/image equivalence; final-head CI, PR #68 merge and post-merge verification passed on exact recorded SHAs. See `docs/shadedoomvk/PF-018-RUNTIME-EVIDENCE.md` for the exact pair, measurements, exclusions and limits.

See `docs/shadedoomvk/PF-018-RUNTIME-EVIDENCE.md` for the paired runtime qualification, `docs/shadedoomvk/PF-004-LEVELMESH-CONTRACT.md` for the executable ownership/allocator/AS contract, `docs/shadedoomvk/PF-015-SHADOW-VISIBILITY-CONTRACT.md` for the PF-015 cache consumer contract, `docs/shadedoomvk/issues/PF-018.md` for the performance candidate/acceptance boundary, and `rag/06-LIGHTMAP-PROBE-PIPELINE.md` for the PF-012 probe-map mapping/fallback contract.

## CFX-006 packed-upload observation (#95)

`VkLevelMeshUploader::UploadData` can fingerprint the completed staging bytes under the separate CFX resource switch; `VulkanCommandBuffer::copyBuffer` and `FlushCommands::submit-buffer` join staging/destination ranges to the actual recording allocation and later submission. This accounts for transfer command replacement during texture loading. Dirty ranges, memcpy/copy/barriers, CPU collision ownership and uploaded extents are unchanged. Fingerprints have explicit 16 MiB/upload and 64 MiB/run caps and prove prepared CPU bytes, not GPU-consumed bytes. See [CFX-006](../CFX-006-CAPTURE-IDENTITIES.md).

## CFX final LevelMesh disposition

CFX-007 found a real transfer-publication defect in the LevelMesh uploader: transfer writes needed visibility to vertex attribute and index reads as well as shader reads. That separate correctness defect was repaired and safe synchronization validation became clean, but the DBP37 primary crash remained reproducible afterward. Direct-LevelMesh-off and pipeline discriminators also prevent a universal LevelMesh-required crash explanation.

Later matching-PDB CPU snapshot checks found no invalid logical index, reachable tree cycle, non-finite referenced geometry or traversal-stack overflow (peak pending stack 18/64). Those post-error CPU checks do not prove submitted GPU bytes. The final CFX repair is the separate lightmap/probe descriptor-target publication lifetime fix; do not attach the historical crash causality to LevelMesh. See [CFX final synthesis](../CFX-FINAL-PROGRAMME-SYNTHESIS.md).
## SDVK-009 offline single-instance collision export repair — 2026-10-11

`CPUAccelStruct::Upload` redirects a leaf TLAS root directly to its exported BLAS
root; a single instance has no parent link to rewrite. CPU graph tests execute
the production export and prove valid links/original triangle membership for
single-node, nonzero-root, multi-instance and empty cases. This does not diagnose
the retained physical shadow-boundary fault or clear its hardware stop. Sparse
BLAS slot export/TLAS membership were subsequently reproduced separately below.
[Audit and exact reproducer outlines](../SDVK-009-COLLISION-ROOT-AUDIT.md).

## SDVK-009 sparse-triangle centroid identity candidate — 2026-10-11

`CPUBottomLevelAccelStruct` retains original triangle IDs after skipping
`a == b` triangles. Its centroid table must therefore have original-triangle
index extent; both scalar and SSE debug `Subdivide` address it by those IDs.
The constructor initializes that extent and writes `centroids[i]`, while active
leaves and exported original element offsets remain unchanged. Freed geometry
can leave zeroed index holes through `LevelMesh::FreeGeometry`.

Production-extracted CPU regression covers leading/interior holes and no-hole,
all-degenerate and trailing-hole controls; the exact pre-fix constructor remains
a required negative. This bounded source repair has no evidence of physical
fault causality and does not clear the hardware STOP. Sparse/null BLAS slot
identity is addressed by the separate bounded repair below. See the [bounded audit](../SDVK-009-COLLISION-ROOT-AUDIT.md)
and `tools/pf_oracle/tests/test_collision_centroid_identity.py`; hosted candidate
verification and review remain required before acceptance.

## SDVK-009 sparse BLAS slots and empty publication — 2026-10-11

`CPUAccelStruct::CreateTLAS` includes only live original BLAS slots and retains
centroids indexed by the original occupied slot extent. `Upload` advances the
original slot identity across null entries, preserving original triangle offsets.
Empty CPU/software-shader traversal returns the existing no-hit sentinel before
accessing nodes. An empty software export retains root `-1` and one initialized,
unreachable storage node: production `MeshBufferUploads::Add` ignores zero-length
ranges, so this storage range is necessary for the existing Vulkan uploader to
publish the empty root header. It represents no live geometry or triangle.

Production-extracted regressions retain old sparse/null failures and verify
no-hole graph equivalence, empty entry behavior, real range semantics and planned
header/node transfer bytes for initial empty and live-to-empty publication.
CPU staging tests do not prove GPU consumption, full geometric queries or the
actual failed scene's graph. General update lifecycle and deep-stack/invalid-link
safety remain unqualified. Neither physical failure is diagnosed or resolved;
hardware STOP remains active. [Bounded audit](../SDVK-009-COLLISION-ROOT-AUDIT.md).

## SDVK-009 CPU collision backing/reset lifetime — 2026-10-12

BLAS geometry references are current-storage bindings, while triangle IDs and
BLAS slots remain stable identities. `CPUAccelStruct::Update` detects vertex or
index backing relocation (and populated vertex-count changes) before its dirty
index early return, and rebinds retained live BLAS pointers at original slot
offsets. Storage movement alone does not rebuild or change their trees/bounds.
CPU queries retain the existing requirement to run after collision Update.

`LevelMesh::Reset` clears occupied `IndexCount` and pending spans for its ten
reset array domains (Vertex, UniformIndexes, Index, SurfaceIndex, Surface,
Uniforms, LightUniforms, Light, LightIndex, DynLight). Retained Node/Portal
storage/ranges are unchanged. The caller recreates collision after rebuilding
geometry before its next query, Update or publication, as `DoomLevelMesh`
construction already does. Queries between allocation and collision Update
remain unsupported.

Exact production CPU regressions preserve pre-fix stale-pointer/high-water/span
negatives, unchanged trees, no-index-dirty and repartition controls, and real
base-to-Doom reset ordering. Neither failed physical capture supplied its graph;
these lifecycle fixes establish no physical fault cause or resume permission.
See [audit](../SDVK-009-COLLISION-ROOT-AUDIT.md) and
`tools/pf_oracle/tests/test_collision_backing_lifetime.py`.

## SDVK-009 deterministic collision publication bytes — 2026-10-12

The software shader ABI includes a 16-byte collision root header and 48-byte
`CollisionNode` records. Explicit padding in those records is not traversal
state, but the uploader and CFX fingerprint operate on the complete copied byte
range. Production publication must therefore define those padding bytes before a
complete-range fingerprint can be compared deterministically.

`CPUAccelStruct::Upload` now writes zero to all three explicit node padding
fields and `VkLevelMeshUploader::UploadNodes` value-initializes the four-word
header before assigning `root`. Compile-time checks pin the header, collision
node and `FFlatVertex` byte sizes to the std430 shader contract. The exact
pre-fix padding omission is retained as an executable negative by pre-seeding
destination storage and requiring that mutated production path to fail.

This does not change any shader-consumed field and is not physical-fault
causality. Actual descriptor/pipeline binds, exact bound SPIR-V identity and
post-use destination readback remain the next hosted publication-witness gate.
See PR #145, `tools/pf_oracle/tests/test_collision_upload_root.py`,
`tools/pf_oracle/tests/test_sdvk009_publication_contract.py` and
`../SDVK-009-OFFLINE-SHADOW-INVESTIGATION.md`.

## SDVK-009 bound publication/readback candidate — 2026-10-12

`CPUAccelStruct` exposes the object/event identity only after the original
exclusive snapshot has finished. The optional publication witness builds a
bounded readback plan from that state: the original root word, reachable nodes'
defined center/extents/link words, occupied indices including holes, and XYZ
words at original referenced vertex slots. It does not read padding, unused
tails or unrelated vertex attributes. The 16-byte root prefix, 48-byte node
stride and 32-byte vertex stride remain unchanged.

The Vulkan manager appends the readback after the ordinary commands in their
existing submission. Source/staging ownership covers its exact existing fence;
mapping and checked non-coherent invalidation follow the successful normal wait.
Logging failure cannot shorten ownership. Vertex/index transfer-source usage is
added only in the opt-in witness mode. No traversal, upload range, light policy,
pre-shadow wait or ordinary allocation identity is repaired by this diagnostic.

Post-use equality with a reconstructed hosted CPU snapshot does not prove the
values seen by every preceding shader load, reproduce either failed physical
graph or explain a timeout. The [bound witness contract](../SDVK-009-BOUND-PUBLICATION-WITNESS.md)
defines the independent command/SPIR-V joins and software-only qualification;
physical STOP and the ungranted #8/#9/#10 acceptance gates remain active.

