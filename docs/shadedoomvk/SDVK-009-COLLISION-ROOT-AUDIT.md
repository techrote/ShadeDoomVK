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

Sparse/null BLAS slot export and TLAS membership observations 1 and 2 were
subsequently reproduced independently below. The frozen failed capture has no native collision
state proving degenerate holes occurred. This repair does **not** establish
physical fault causality or resolution, does not permit a hardware retry, and
does not lift the host STOP. #9 remains open and physically inconclusive.

## Confirmed sparse BLAS slot and empty traversal repair candidate

After the separate post-reboot `a7c5df6f7a3c529cb2d8f659dade79f45e2dfdaa`
physical diagnostic also failed on its first shadow-boundary process, a CPU-only
investigation executed that exact source's `CreateTLAS`, `Subdivide`, `Upload`
and public `FindFirstHit` wrapper. This isolated repair starts at that revision;
neither physical packet is modified. No renderer or GPU is launched by the
reproduction. Neither failure completed native collision state, so the presence
of sparse BLAS slots in either failed scene remains unestablished.

The exact pre-fix functions and original license are retained in
`tools/pf_oracle/tests/fixtures/collision_sparse_slots_pre_fix.cpp`;
`collision_sparse_slots_evidence.json` pins their normalized source/function
SHA-256 values and original logical-check results. Checked BLAS handles and
containers throw before null/out-of-range dereferences. Graph walkers reject
invalid links, cycles, duplicate membership and wrong original triangle offsets.
The subdivision algorithm itself is unmodified and uninstrumented.

| Original BLAS slots | Pre-fix TLAS construction | Independent pre-fix export |
|---|---|---|
| `[live,live,live]` | Correct identities/centroids | Complete correct graph |
| `[null,live,live]` | Stops before dereferencing null slot 0 | Four wrong leaf element offsets; graph cycle/alias |
| `[live,null,live]` | Duplicates slot 0; omits slot 2 | Two wrong leaf element offsets; graph cycle/alias |
| `[null,null,null]` | Stops before dereferencing null slot 0 | Explicit empty graph when independently supplied |
| `[live,live,null]` | Duplicates slot 0 | Complete correct graph when independently supplied |
| Zero occupied slots | Empty root -1 | Empty root -1 |
| `[null,null,live]` | Stops before dereferencing null slot 0 | Two wrong leaf element offsets; invalid graph |

Each live test BLAS has a nonzero root and two distinct original element
offsets. Export is tested both with production-built TLAS membership and with
an independently constructed valid TLAS, separating the two defects. Wrong
copied element offsets are counted before graph traversal, so a bad graph cannot
mask that independent failure. Five allocated BLAS slots include unused trailing
capacity; reused centroid capacity is poisoned before construction.

The minimal repair advances the export slot counter for every slot, including
null entries; only live original slot IDs enter TLAS subdivision; centroid
storage retains the original occupied slot extent and writes each live slot at
its own index. Skipped centroid entries are zero and never selected. BLAS
triangle identities, slot partition size, bounds, subdivision/splitting,
traversal of nonempty trees, workloads and quality settings are preserved.
No donor code is imported. No-hole TLAS/export snapshots, including bounds,
root links and original triangle offsets, must equal the retained pre-fix graph.

Omitting all absent slots exposes the existing empty-root endpoint: the CPU
query wrapper called traversal with root -1, and both software GLSL entry points
likewise pushed `nodesRoot == -1`. The connected repair checks this known empty
sentinel before traversal in CPU `FindFirstHit`, software `TraceAnyHit`, and
software `find_first_hit`. Empty input now produces the existing no-hit result
(`false`, or fraction 1 / triangle -1 / zero barycentrics). No hardware-ray-query
branch, stack policy, bounds algorithm or general invalid-root policy changes.

Independent review found the connected publication boundary: production
`MeshBufferUploads::Add(0,0)` discards the range, and `VkLevelMeshUploader` neither
budgets nor uploads the root header without a nonempty node range. An initial
empty tree could therefore leave an uninitialized GPU header, and a live-to-empty
transition could retain a stale positive root despite the GLSL guards. For an
export with zero tree nodes, the repair keeps root -1 and publishes one fully
initialized **unreachable storage-only node** (zero center/extents/padding,
left/right/element index -1). The existing positive-range/header upload path then
publishes the empty sentinel without a new dirty-state lifecycle. This storage
count of one is not live membership or collision geometry; traversal must still
perform zero node accesses. No fake node is traversed or read beyond allocation.

`test_collision_sparse_slots.py` compiles old/current exact production functions
and executes seven cases through construction, independent export, combined
construction/export and the public CPU query boundary: 56 scenario executions.
`test_collision_empty_shader.py` compiles the exact two GLSL entry bodies as C++
with checked node-access/vector stubs: ten executions, preserving original empty
negatives, empty buffers with stale allocated nodes, nonempty leaf/internal hit
and miss controls, and zero-distance behavior. All nonempty results and access
counts must equal pre-fix behavior. The CPU recursive-query stub verifies public
dispatch and its empty guard, not geometric intersections. The shader test proves
source control flow, **not GLSL/SPIR-V compilation or GPU execution**. Exact-head
hosted native software-Vulkan CI must compile and exercise the changed shader.
`test_collision_empty_publication.py` executes exact production range Clear/Add,
uploader GetTransferSize/UploadNodes, old/current CPU Upload and real node/header
member definitions: eight old/new scenarios cover initial empty, live-to-empty,
empty-to-live-to-empty and hardware-ray-query upload bypass. It requires the old
missing/stale header, repaired root -1, correct dummy fields and exact transfer
byte accounting. This is CPU staging/publication evidence, not submitted GPU
bytes. General Update lifecycle behavior, reconstruction of either failed static
graph and general invalid-link/deep-stack safety remain outside this evidence.

Assertions-enabled MSVC C++17 focused collision/LevelMesh gate passes 14/14,
including the earlier root-export and scalar/SSE centroid regressions. Standalone
generated units, binaries and per-scenario logs are retained locally at
`C:/ShadeDoomVK/physical-evidence/20261011/sdvk009-null-blas-cpu/`;
run `python tools/pf_oracle/tests/test_collision_sparse_slots.py --retain PATH`
in a developer compiler environment to regenerate them. Exact old shader source
is retained as `collision_empty_shader_pre_fix.glsl`. Local retention is not a
claim of durable external raw storage.

This is a CPU-proven source repair candidate pending independent review and
exact-head CI. It is **not a diagnosis or resolution of either physical fault**.
All hardware remains stopped, #9 remains open/physically inconclusive, and no
performance, architecture, quality or dependent acceptance gate advances. Any
future physical experiment requires a separately reviewed, newly pinned source,
build and shader-package identity; this candidate authorizes no launch or retry.

## CPU collision backing and reset lifetime repairs — 2026-10-12

Independent offline source review of verified master
`3b7da0739fa8254c80cb0adaa8ee55b00c95676f` reproduced two additional lifecycle
defects. Neither failed physical capture retained its runtime graph, and neither
reproducer represents that missing graph. These are source defects with no
established physical fault causality.

`CPUBottomLevelAccelStruct` retains raw vertex/index backing pointers.
`LevelMesh::AllocGeometry` can grow either real `TArray` without moving live
element identities. The old `CPUAccelStruct::Update` only rebuilt dirty index
partitions unless repartitioning was necessary; unchanged BLAS trees retained
old backing addresses. A legal forced relocation left 16 unchanged BLASs stale
out of 17 live instances for vertex-only, index-only and joint growth. A
vertex-only backing relocation with no dirty index range likewise retained all
16 stale bindings. The production query reached its triangle-intersection
boundary with stale storage; the CPU fixture stopped before dereferencing it.
Unchanged, dirty-without-relocation and full-repartition controls passed.

The bounded correction detects backing address or populated vertex-count
changes before the index-dirty early return. It rebinds each existing live BLAS
to current vertex storage and its **original slot's** current index start, and
refreshes the vertex count. It preserves tree nodes, roots, bounds, triangle
identities, dirty partition selection and subdivision. It does not rebuild
unchanged trees merely because storage moved. Within the existing lifecycle,
queries occur after `Update`; it does not add permission to query between
geometry mutation and that synchronization point.

`LevelMesh::Reset` cleared populated vertex/index arrays but retained
`Mesh.IndexCount` and pending upload spans. The real base construction order is
`Reset -> AddEmptyMesh -> CreateCollision`; `DoomLevelMesh::SetLimits` then calls
`Reset` again before creating real surfaces and recreating collision. The old
12-index high-water mark survived an empty reset or a three-index replacement;
the production collision constructor attempted a BLAS span beyond populated
index storage. Pending base-mesh ranges likewise remained `0..12` for the empty
or smaller arrays. Separately seeded stale surface/uniform/light/dynamic-light
spans proved that reset arrays could retain invalid uploader source extents.

Reset now clears `IndexCount` and the ten upload domains for arrays it actually
clears/resizes: Vertex, UniformIndexes, Index, SurfaceIndex, Surface, Uniforms,
LightUniforms, Light, LightIndex and DynLight. Node and Portal ranges/storage are
retained. The existing caller must recreate collision before querying or
publishing a reset mesh; recreation regenerates and dirties collision nodes.
No uploader clamp, skipped live update or general invalid-state fallback is
added. Supported callers recreate collision after Reset before its next query
or Update; Reset does not promise reuse of an old `Collision` object. Arbitrary
queries between geometry allocation and collision Update remain unsupported.

`test_collision_backing_lifetime.py` executes exact production scalar collision
construction, update, export and geometric query functions with real `TArray`,
allocator, `AllocGeometry`, `Reset`, `AddEmptyMesh` and range functions. The exact
old constructor/Update/Reset and function hashes remain in
`collision_backing_lifetime_pre_fix.cpp/.json`. Its 22 old/current scenarios
require the original stale-binding/high-water/upload-span failures, actual
current hit/miss results, unchanged-tree snapshots, no-index-dirty handling,
repartitioning, empty/smaller/same-size reset and base-to-Doom constructor order.
Production `VkLevelMeshUploader::UploadRanges` byte planning is executed for
valid spans; a logical source-span checker stops invalid input before pointer
formation, and a byte sink checks planned source extents. Node/Portal dirty
ranges must survive reset. Other renderer field types and vector/backend
interfaces are bounded shape stubs; the fixture is scalar CPU evidence, not
submitted Vulkan bytes, GPU execution or the actual failed graph.

Assertions-enabled MSVC C++17 focused gate passes 15/15, preserving earlier
single-root, centroid, sparse-slot, empty traversal/publication and LevelMesh
negative controls. [Machine-readable candidate evidence](evidence/sdvk009-collision-lifetime-20261012.json)
pins the source functions, retained local outputs and limits. Original offline
probes, attributable fixture compiler warning, repaired scenario units/binaries
and logs remain under
`C:/ShadeDoomVK/physical-evidence/20261012/offline-shadow-20261012/independent-collision/`.
Review and complete exact-head hosted CI remain required before merge. Hardware
STOP stays active; #8/#9/#10 remain open and no physical acceptance advances.
