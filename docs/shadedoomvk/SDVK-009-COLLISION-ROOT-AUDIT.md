# SDVK-009 offline collision-root audit

This is CPU/source evidence for a bounded renderer defect discovered after the
2026-10-11 frozen physical campaign stopped on the first `shadow-boundary`
capture. It is not a diagnosis of that device loss and does not authorize a
hardware retry. The original failed packet and the original source identity
remain historical evidence.

## Confirmed defect and bounded repair

`CPUAccelStruct::Upload` flattens a TLAS and its BLAS trees into the collision
node buffer consumed by `polyfill_rayquery.glsl`. It normally redirects a TLAS
parent's child links to the corresponding BLAS roots. With exactly one instance,
the TLAS root itself is a leaf and has no parent. The old export left the root
pointing at that TLAS node, whose `element_index`, `left`, and `right` are all
`-1`. The software shader identifies a leaf by `element_index != -1`; after a
bounds overlap it therefore pushed both invalid child indices.

The repair redirects only a TLAS leaf root to the already exported BLAS root.
It preserves the BLAS root's actual offset, triangle indices, node contents,
multi-instance traversal, empty export, workload, settings, and shader code.
It adds no timing instrumentation and has no dependency on the proposed
`scene.immediate` timestamp change.

## CPU verification

`test_collision_upload_root.py` extracts and compiles the exact production
`SwapYZ` and `CPUAccelStruct::Upload` functions with bounded container and device
stubs. It walks the resulting graph, rejects invalid links and cycles before any
dereference, and verifies every expected original triangle is reachable.

On frozen source `0a2fbad203549d18ac6e5a61bb4747709637bfde`, both the one-triangle
single-instance and nonzero-BLAS-root cases failed the graph bounds assertion.
The multiple-instance and empty controls passed. After the repair all four cases
pass. The regression plus the existing level-mesh contract tests passed 10/10
with MSVC C++17, assertions enabled, and warnings treated as errors. Neither test
launches a renderer or a GPU workload.

## Physical fault limits

The failed scene requests `gl_light_shadows=2`, which makes the immediate Vulkan
pipeline select `UseRaytrace`, while `vk_rayquery=false` selects software tree
traversal. Its 1,025 authored lights make traversal cost a plausible separate
investigation target. The 1,024-row shadow-map selection limit does not bound this
ray-trace path: `shadowAttenuationRaytrace` ignores the shadow-map index.

The retained fault addresses have type `4`, the bundled Vulkan enum
`VK_DEVICE_FAULT_ADDRESS_TYPE_INSTRUCTION_POINTER_UNKNOWN_EXT`. That type does
not itself establish an invalid read or write. The capture failed during warmup
before a native state receipt; it does not record the mesh's actual instance
count or collision graph. `CPUAccelStruct` calculates instance count from index
capacity and occupied extent, so a static scene does not necessarily have a
single instance. This repair therefore does **not** establish the cause or
resolution of the frozen failure. A separate diagnosis and reviewed hardware
protocol remain necessary before any new GPU launch.

## Follow-on sparse-geometry audit observations

These source observations are outside the single-root repair. No additional
renderer change or hardware experiment is part of this audit. They require
independent CPU reproduction and review; the failed packet does not establish
that any of these conditions occurred in its scene.

1. **BLAS slot identity during export.** In `CPUAccelStruct::Upload`, the
   `instance` counter advances only inside `if (blas)`. If a null BLAS precedes
   a valid one, `indexStart` and `blasOffsets[instance]` use its compressed
   position rather than its original `DynamicBLAS` slot. The TLAS retains
   original slot identities. A CPU reproducer can extend the existing extracted
   production Upload fixture with slots `[valid, null, valid]`, an internal TLAS
   root whose leaves reference slots 0 and 2, and distinct source triangle
   offsets. Validate every reachable link and require the second BLAS triangle
   to retain `2 * IndexesPerBLAS + local_element_index`. The current code instead
   fills the offset for slot 1 and leaves slot 2's offset at its default value.

2. **Absent BLAS membership during TLAS construction.** In
   `CPUAccelStruct::CreateTLAS`, a missing `DynamicBLAS[i]` adds leaf identity 0
   and a distant sentinel centroid. `CPUAccelStruct::Subdivide` then dereferences
   `DynamicBLAS[instances[i]]` for its bounds. This can duplicate slot 0's
   membership, and slot 0 itself can be absent. A CPU reproducer should extract
   production `CreateTLAS`, record the identities passed to its subdivision
   consumer, and require exactly the live slots for `[valid, null, valid]`,
   `[null, valid]`, and all-null controls. Any subsequent repair must retain
   centroid indexing by original slot identity and explicitly handle an empty
   active set.

3. **Triangle identity versus compact centroid storage.**
   `CPUBottomLevelAccelStruct::CPUBottomLevelAccelStruct` skips triangles whose
   first two vertex indices are equal. For retained triangles it pushes the
   original triangle identity `i` into `scratch.leafs`, while compactly appending
   only retained centroids. Both the SSE and scalar overload bodies of
   `CPUBottomLevelAccelStruct::Subdivide` read `centroids[triangles[i]]`. With a
   skipped triangle preceding retained triangles, that identity can exceed the
   populated centroid range or name another triangle's centroid. A CPU
   reproducer should execute the exact constructor on an index array with a
   zeroed first triangle followed by at least two distinct valid triangles;
   check every requested original triangle identity against the populated
   centroid table at the subdivision boundary. Repeat with an interior hole
   and no-hole/all-degenerate controls. Merely checking allocated vector
   capacity is insufficient: the original `reserve(num_triangles)` can leave
   such reads inside allocated memory while outside the populated range.

The existing production `LevelMesh::FreeGeometry` explicitly zeroes freed
indices while retaining the occupied index high-water mark. Thus sparse and
degenerate ranges are valid lifecycle inputs to investigate, even though their
presence in the frozen static fixture is unestablished. CPU graph/identity
validation and source-qualified safety review should precede any future
hardware protocol. The hardware STOP remains active.

## Confirmed sparse-triangle centroid identity repair candidate

The third follow-on observation above was independently reproduced on CPU on
2026-10-11, then repaired on a separate branch based on verified
`master@322925d8fa1486d62db0d072310a50748bc0b1ce`. The constructor, leaf builder,
scalar subdivision and SSE debug subdivision were byte-identical after newline
normalization at that master and frozen `0a2fbad203549d18ac6e5a61bb4747709637bfde`.
The retained pre-fix constructor SHA-256 is
`81c95f63fe26d71b465f46163c9b3c64042726891d2db0941df8d9e524a60898`.
[Machine-readable original evidence](../../tools/pf_oracle/tests/fixtures/collision_centroid_pre_fix_evidence.json)
retains the exact function hashes and original CPU result summaries.

The standalone reproducer executes the exact production constructor and both
subdivision bodies. Its sole access instrumentation replaces each executable
`centroids[triangles[i]]` with a checker of populated size and the expected
original triangle's centroid. It logs an in-range identity mismatch, and throws
before any unpopulated read. This is a logical-index reproduction, not a claim
that a CPU crash or GPU fault was observed by the fixture.

| Four original triangle slots | Pre-fix scalar and SSE debug result |
|---|---|
| No hole: `[0,1,2,3]` | Correct centroid identities; complete valid tree |
| Leading hole: `[hole,1,2,3]` | Index 1 names original 2; index 2 names original 3; index 3 is outside populated size 3, inside capacity 4 |
| Interior hole: `[0,hole,2,3]` | Index 2 names original 3; index 3 is outside populated size 3, inside capacity 4 |
| All degenerate | No centroid reads; empty tree, root -1 |
| Trailing hole: `[0,1,2,hole]` | Correct centroid identities; complete valid tree |

The bounded repair initializes centroid storage to `num_triangles` entries and
writes each retained centroid at its original identity `i`. Skipped entries are
zero initialized and never added to the active leaf list. Original triangle
identities, leaf element offsets, subdivision/traversal code, degeneracy policy,
draw/light workload and quality settings are preserved. No donor code is added.

`test_collision_centroid_identity.py` retains the exact pre-fix constructor and
executes it and the current constructor with the current production scalar/SSE
subdivision bodies: five cases, two constructors, two paths on x86 (20 scenario
executions). Reused scratch capacity is poisoned to distinguish populated size
from allocated capacity. Pre-fix leading/interior negatives are required;
repaired cases require correct centroids, valid reachable original triangle
membership, and zero skipped entries. Non-x86 targets test the production scalar
path. MSVC C++17 assertions-enabled focused collision/LevelMesh tests pass 12/12.
Hosted build/CI and independent review remain required; this is a repair
candidate, not an accepted qualification transition.

The original standalone script, generated units, binaries, logs and source hash
manifest remain separately retained locally at
`C:/ShadeDoomVK/physical-evidence/20261011/sdvk009-sparse-centroid-cpu/`, with a file
checksum inventory. The original worktree copy remains available under
`campaign-worktrees/sdvk009-collision-guard/analysis/sdvk009-sparse-blas/` for
reproduction against its unchanged source. Neither location is a claim of durable
remote evidence storage.

Sparse/null BLAS slot export and TLAS membership observations 1 and 2 remain
separate unresolved follow-ons. The frozen failed capture has no native collision
state proving degenerate holes occurred. This repair does **not** establish
physical fault causality or resolution, does not permit a hardware retry, and
does not lift the host STOP. #9 remains open and physically inconclusive.
