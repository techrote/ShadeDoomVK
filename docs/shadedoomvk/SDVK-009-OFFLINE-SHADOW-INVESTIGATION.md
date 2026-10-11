# SDVK-009 offline shadow-boundary investigation, 12 October 2026

**Physical STOP remains active. Root cause is UNDETERMINED.** The CPU repairs
and hosted reconstructed graphs below do not establish the cause or resolution
of either physical fault. #8/#9/#10 remain open; architecture is INCONCLUSIVE,
scaling UNMEASURED, physical/performance acceptance false. No local renderer,
vktool, version invocation or Vulkan device is part of this investigation.

## Authority and integrity

The initial live authority is `master@3b7da0739fa8254c80cb0adaa8ee55b00c95676f`,
tree `276b1167db72dcb84d71c4d2248c4c438c737c88`, freshly fetched on 12 October.
All issue #9 comments, #8/#10 state, PRs #140–143 including discussion/review/file
pages, and exact-master CI were retrieved again. The two master workflows
`38138137725` (source) and `38138137721` (all nine CI jobs) are successful.

Fresh local records are under
`C:/ShadeDoomVK/physical-evidence/20261012/offline-shadow-20261012/`.
`input-integrity.json` checks 275 recorded hash/size references, 218 distinct
files and 38 recursively referenced JSON records, including all four sealed
archives: zero missing files or mismatches. It does not rewrite original receipts.
The public anchor is [issuecomment-6109158124](https://github.com/techrote/ShadeDoomVK/issues/9#issuecomment-6109158124).
The root records have SHA-256:

| Record | SHA-256 |
|---|---|
| programme-resume-report.json | `5a2e598298248048aebcfc064ba329564e865a8941d573ebc0a2af06afe51e28` |
| resume-public-verification.json | `04321c7f2a6be55aa5d363248c04b72372345490c9cd42971719369064a661cf` |
| sdvk009-actual-graph-cpu-audit-20261011T120825Z-a6f8cc09.json | `ff771ced9e14f9ef0ce93f3856268858773cc9673a4c352ad6fd251cd15fda18` |
| post-reboot-v2-kd-independent-review/review.json | `0ab30f59ecaa2772d7cbca786ed6183a74d33ce06cdb952750ad572313836fa7` |

## Fault timeline

| UTC on 11 October | Evidence and boundary |
|---|---|
| Before 00:45 | Frozen clean `0a2fbad203549d18ac6e5a61bb4747709637bfde`, executable `10e61cf536b0b67b5396121606a6b3be8cb943a7d70d5fb2d93604b361e53fb0`: twelve captures/six exact pairs complete. |
| 00:45:41.9748864 | First shadow-boundary process emits type-4 fault records and hangs; nvlddmkm event153. No timing or retry follows. |
| 00:45:42 / 00:45:46.494182 | Saved original dump session / WER event. These are collection/report times, not a recovered executing shader timestamp. |
| After first failure | PR140 repairs single-leaf root export. PR142 repairs sparse centroid identity. PR141 retains software fixture failures and tooling corrections; no physical #8 launch. |
| 10:49:17.5 | Separate host restart. User restores the previous 90 W limit after reboot reset; no other hardware change is inferred. |
| 11:06:06 | Separate a7 diagnostic preregistration, later revision2 pins event baseline7543 before any scene. Clean source `a7c5df6f7a3c529cb2d8f659dade79f45e2dfdaa`, executable `4a10cf525a5e65e60c035f4f7270a708bf659e64bf5faad9fb920fd0a1475531`. |
| Before 11:07:58 | Compositing completes on the identified physical device. |
| 11:07:58.733706–11:08:49.994962 | First shadow capture process receipt interval. It fails during 120-frame warmup, before native state/image completion. |
| 11:08:48.1048128 | New nvlddmkm153 record7671; monitor verifies executable path/hash and owned collector parent, terminates only PID13676. Second shadow, full campaign, timing and #8/#10 processes do not launch. |
| 11:08:48 / 11:08:52.428277 | Saved second dump session / WER event. Maximum observed 50 C at90 W is telemetry, not proof of stability or exclusion of hardware failure. |
| After second failure | PR143 repairs independently reproduced sparse BLAS membership/export and empty traversal/publication. CPU and llvmpipe pass; no physical causality or resolution follows. |

Both saved WATCHDOG dumps are LiveKernelEvent0x141 with bucket
`LKD_0x141_IMAGE_nvlddmkm.sys`, driver-relative owner `0x1939ff0`, image version
`32.0.16.1692`, and TDR collection/reset/scheduler stacks. Signed packaged KD,
public-symbol cache and compatible driver image are verified by the old receipts.
No additional generic dump probes are justified: private recovery types and
associated EPROCESS memory were already unavailable; proprietary secondary TDR
bytes remain losslessly retained and undecoded. `nvDumpConfig+795a80` is nearest
export notation. Matching PE headers do not establish all loaded driver bytes.
Raw dumps, driver images and private diagnostic logs remain local.

## Hypotheses and falsifiable tests

| Hypothesis | Support | Contradiction / limit | Missing evidence | Falsifiable offline test / disposition |
|---|---|---|---|---|
| Childless single-leaf TLAS root causes invalid shader links | Exact old production export fails bounded graph controls | Repair is in a7, which separately faults again | Failed runtime instance count/root | Preserve PR140 old/current graph tests; reject as a sufficient explanation of both failures. |
| Sparse centroid IDs corrupt BLAS build | Leading/interior holes fail old scalar/SSE tests | Repair is in a7; failed scene has no recorded holes | Fault-frame occupied indexes and centroids | Preserve PR142 logical-range/identity negatives. Proven source defect; not a sufficient explanation alone. |
| Sparse/null BLAS slots produce bad exported links | PR143 old functions duplicate membership and compress offsets | No failed graph; software success is platform-bounded | Actual slots/roots/dirty history | Replay production constructors/Update on captured reconstructed arrays; compare original slot identities. Physical contribution unresolved. |
| Empty graph header remains stale | Exact old staging path drops zero range | Authored scene contains world geometry; no empty state recorded | Root/header at relevant submission | Preserve initial-empty/live-to-empty uploader and shader negatives. Physical contribution unestablished. |
| Backing-array relocation leaves CPU BLAS dangling | New legal growth probe detects unchanged BLAS bound to retired vertex/index storage | GPU export uses original element IDs; no captured relocation at fault | Failed CPU allocation/update history | Production ctor/Update/query old/current tests, vertex-only/index-only/both growth and no-growth/repartition controls. Independent CPU defect; no GPU causal attribution. |
| Reset preserves old high-water/dirty spans | Exact Reset→smaller/empty rebuild exceeds populated index or upload-source extent | Failed map may rebuild enough geometry to cover original spans | Runtime reset/rebuild extents | Exact Reset/allocator/range/uploader old/current tests and same-size controls. Independent lifecycle defect. |
| Stack overflow/cycle or extreme traversal work | GLSL has unchecked stack64 and no cycle/iteration guard; 1025 authored lights can trace | Authored light count does not determine graph depth; general deep-tree safety unqualified | Failed graph and executed rays/shader | Structural cycle/link/original-membership checks and worst all-overlap DFS pending-stack bound on reconstructed exports. Synthetic depth65 must fail; passing reconstruction cannot clear physical hypothesis. |
| Transfer/resource/descriptor publication defect | Invalid GPU bytes could fault while CPU graph is valid; historical CFX had a distinct repaired defect | Current source includes transfer→shader/vertex/index barriers and neutral descriptor lifetime repair | Actual submitted/consumed bytes and faulting instruction | Verify exact staging extents/header/offset/ABI contracts; hosted correctness only. Source cleanliness does not prove GPU consumption. |
| Driver compiler/runtime or hardware instability | Two correlated NVIDIA engine timeouts on same device/driver/path | Bucket/owner/temperature cannot distinguish causes | Symbol-qualified command/shader attribution or hardware evidence | Inspect retained artifacts and shader compilation; no further generic dump probe supplies the missing evidence. Keep unresolved, no speculative driver/hardware changes. |

## Production path and extraction fidelity

`MapLoader::LoadLevel` parses TEXTMAP via `ParseTextMap`, builds missing nodes via
`FNodeBuilder`, then builds subsectors/sections/visibility and invokes hardware
VBO/`InitLevelMesh` callbacks. The retained SDVSHDW WAD contains only marker,
TEXTMAP and ENDMAP: 8 vertices/lines/sides, one sector, 1029 things including1025
lights. It contains no serialized BSP/GL nodes or collision arrays. Existing
vktool enters the game loop and is not a CPU-only map bypass.

`LevelMesh` first creates a twelve-index placeholder and collision structure.
`DoomLevelMesh::SetLimits` resets the mesh before production wall/flat dispatch.
`CreateSurfaces` visits original sides and sectors; `CreateWallSurface` and
`CreateFlatSurface` use the real `HWWall`/`HWFlat` dispatcher triangulation and
`AllocGeometry`, with source vertex/index identities retained. Backing extents
come from the production allocator, while `IndexCount` is an occupied high-water
mark. `FreeGeometry` zeros freed indexes without compacting that mark. TArray
growth does not establish initialized scalar or vertex backing-tail contents.

`CPUAccelStruct` partitions using full `Indexes.size()`, not triangle count;
InstanceCount uses IndexCount. BLAS skips `a==b` triangles, retains original
triangle identities, and indexes centroids accordingly. TLAS includes only live
original slots. Software export redirects leaf roots to BLAS roots and preserves
original element offsets; an empty export publishes root−1 via one initialized
unreachable storage node. `DoomLevelMesh::BeginFrame` performs callbacks/surface
rebuilds and atlas/light work before `Collision::Update`. Thus construction-only
replay cannot establish warmup update history.

`VkLevelMeshUploader` budgets `sizeof(header)+range.Count()*48` for node uploads,
writes the16-byte root header at0 and node ranges at `16+Start*48`, and uploads
vertex/index ranges at their original offsets/strides (32/4). Growth copies old
buffers with transfer ordering; BeginFrame publishes transfer writes to shader,
vertex-attribute and index reads. These are source/staging contracts, not proof
of consumed physical bytes. The shader sees std430 48-byte collision nodes and
32-byte vertices. `gl_light_shadows=2`, `vk_rayquery=false` selects software
`TraceAnyHit`; the1024 shadow-map rows do not cap those ray traces. Both software
entry points have stack64 and push right then left without a general bounds guard.
Segmented first-hit tracing is bounded by segment distance under finite inputs;
ordinary any-hit traverses the whole intersecting graph until hit/miss.

A faithful standalone map→mesh harness would need production resource/script/
texture/material/level initialization, node generation and dispatch, plus a
reviewed CPU render-state adapter replacing the current screen/VBO callbacks.
It is not implemented by pretending authored geometry already is a mesh. The
smaller implemented step captures production CPU collision state on hosted
explicitly identified llvmpipe and replays the actual collision implementation
locally without a renderer/device. This is **reconstructed hosted production
state**, never either failed physical runtime graph.

## Snapshot/replay contract

`-sdvkcollisionsnapshot PREFIX` is opt-in and refuses hardware-ray-query export.
Each construction, dirty Update and unchanged Update writes a new exclusively
created `PREFIX-EVENT.bin`. Object/event IDs are monotonic within one process;
multiple base/derived collision constructions remain separate identities.
State captures of shadow-boundary in hosted native CI request it; timing and
ordinary runtime paths do not serialize. Failures are explicit, never a repair
or silent traversal fallback. Workload/light/shader/quality policy is unchanged.

The `SDVKCL01` schema has16 little-endian uint32 header fields and11 tagged
sections. Full backing extents, occupied index high-water, original slot/root
identities, free/dirty ranges and semantic BLAS/TLAS/export nodes are retained.
VERT stores original vertex ID plus binary32 XYZ bits in shader x/z/y order;
only vertices referenced by nondegenerate occupied triangles are read. INDX
retains every occupied slot including zeroed holes. Unused backing tails,
unreferenced positions, non-position attributes and native padding are
**UNKNOWN/UNREAD**, not assumed initialized or zero. Replay allocates the full
backing extents and poisons unknown data without renumbering consumed identities.

`tools/collision_replay.py` validates structure, referenced finite geometry,
membership/roots/child links, original triangle offsets and worst pending stack,
then compiles the complete production collision implementation with actual vector,
vertex and collision headers and bounded CPU screen/timing/mesh adapters. Only
the opt-in serialization body is excluded in replay. Construction and sequential
Update state are compared per object. Free-range and dirty-publication extents
are checked; uncovered stale storage is reported explicitly. No hand triangulation
or synthesized failed scene is used. Tests include deliberately corrupt graph,
layout/range/identity/stack/empty cases and immutable writer output.

## Resume disposition and held diagnostic protocol

Disposition: **HOLD / no defensible physical resume basis yet**. The new CPU
lifecycle repairs and reconstructed software graph validation close engineering
gaps; they cannot recover unrecorded physical state or attribute the TDR. The
smallest remaining step is independently assess the hosted reconstruction and
old-source replay negatives, then establish a reviewed GPU-publication/shader
attribution discriminator or a justified symbol-qualified analysis. Repeating
the physical experiment merely because CPU/software tests pass is insufficient.

If later evidence supports a physical diagnostic, it needs a fresh immutable
source/tree/build/shader/content/operator manifest and **explicit user approval
to lift STOP for that diagnostic only**. The prospective serial order is one
compositing control then shadow-boundary/1 then shadow-boundary/2, each640×480,
120 warmup, one retained frame,180s limit; preserve the original content/settings
and exact state/RGB pair oracle. No full campaign, timing, #8 or #10 follows
automatically even after diagnostic success. A separate acceptance/disposition
and authorization must precede the full41-process campaign.

Launch ownership must record the collector PID, renderer child PID/creation
time, exact absolute executable path and SHA-256, and a receipt/stop latch shared
by every subsequent spawn gate. Termination requires verifying all ownership
fields; never kill by image name. Reuse the independently reviewed monitor only
after pinning its exact bytes and rerunning CPU failure/changed-baseline controls.
Require the identified GTX1650SUPER/vendor4318/device8583/type2/PCI07:00.0,
driver616.92/raw2585198592 and current90 W readback; mismatch stops, never changes
settings. Poll telemetry every1s and native Windows events every5s with10s reader
timeouts, carrying one event baseline across stages. Stop/latch on device/fault/
validation output, new NVIDIA/Display event, reader/continuity failure, nonfinite
telemetry, temperature≥80 C, identity/power mismatch, process failure or timeout.
Polling plus reader time is the latency bound; it is not instantaneous protection.
Retain preregistration, original/readback inputs, all stdout/stderr, native state/
images, telemetry/events, PID ownership/termination and collector/supervisor
receipts, including incomplete output. Zero automatic retries. This document
does not register or execute that future experiment.
