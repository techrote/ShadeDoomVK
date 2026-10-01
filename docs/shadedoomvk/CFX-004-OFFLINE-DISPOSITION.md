# CFX-004 / #79: offline disposition and remaining discriminator

Status: **reviewable precise blocker; no causal repair**, 2026-10-01. Parent #75 remains open. PF-020/#37 and SDVK-001 remain blocked. Dedicated branch `cfx004-offline-root-cause`, exact master base `423c656158a2843c64b2071bd2fff5761724a9e6`. This investigation made **zero GPU launches** and changed no renderer/shader/gameplay behavior or machine policy.

## Input and dependency boundary

Use [CFX-003](CFX-003-DBP37-REPRODUCTION.md) and its immutable attempt ledger. Additional CFX-005 physical evidence is the reviewed [PR #93](https://github.com/techrote/ShadeDoomVK/pull/93) handoff at `c786f1c5a31f47427fb30e99cb7396f97ec4cecb`, merged after 8/8 CI green at `bc1c312691eef93daf9c512588bb14f31dca46d7`. It was provisional during the original offline investigation; that dependency is now satisfied. PR #94 integrates this exact master, preserving both forensic appendices. No renderer code differs between the original investigation base and this integration.

All six dumps use EXE SHA-256 `15bf5c71d955308fb331e320a8b872b4ee573d16cb1ea5b3cfbd8e069d08b7fd`, PDB SHA-256 `b9b0b4c141318eed46ff73a5af60babd6155965ce9c0fbc422deb5da9f8b6394`, CodeView GUID `43bfc543-3656-4d78-ac05-9b180ce4da2a`, age **28**. Physical renderer source is `16996e38954b70d0187eecda5a7a0e55a4cc7a49` (binary built from code-equivalent `c6c1a534...`). Capture script commits differ from that renderer identity. Do not apply this layout to historical Sunlust's same GUID with age 14 or another build.

The exact IWAD-slot hash is `8ac958e2...`, preserved as `Doom2.wad`; it is **not verified stock Doom II**. The exact DBP37 input is `d356de75...`. Proprietary content, binaries, geometry bytes and full dumps remain outside Git. [Machine-readable results](evidence/cfx004-offline-disposition.json) record complete input hashes, dump paths/hashes, manifest hashes, array metadata, checks and every CFX-001 incident disposition.

Raw offline output: `C:/ShadeDoomVK/pf-local-evidence/cfx004-offline-20261001/`. Original dumps/manifests were read, not edited. CFX-003's stop and both CFX-005 cumulative three-loss caps remain in force.

## What the captures establish

- GTX 1650 SUPER repeated captures observe an invalid read at `0x1da00000` (4096-byte precision), graphics world checkpoint in submission 10 and later frame-fence return `VK_ERROR_DEVICE_LOST`. The checkpoint/observing call do not isolate the initiating instruction or submission.
- Earlier P400 captures observe invalid write `0x1de00000` (4096-byte precision) plus invalid execute, with device loss returned during submit. These payloads differ from the GTX lane; they are not one proven mechanism.
- Native P400 output also loses the device: frame 8/tic 7, postprocess graphics submission 12 returns -4. Correlated driver event precedes the observing call. No confirmed post-loss checkpoint, EXT address payload or vendor binary was emitted in that attempt. Both displays recovered normally by owner observation. Cross-adapter presentation is not required for this broad failure; a second adapter remained installed, and an identical earlier P400 fault signature is not established.
- Preserved thread stacks are post-return fatal-dialog state. They establish application handling after device loss, not a never-returning Vulkan operation.
- Safe core/synchronization/GPU-assisted activation evidence and accepted #82/#83/#86/#87 fixes remain useful, but the primary capture mode did **not** enable validation. Safe-path clean logs do not prove validity of DBP37's failing workload.

## Focused CPU collision check

`tools/cfx_cpu_dump.py` reads only the pinned full-memory minidump's ModuleList/Memory64List and the matching LevelMesh/CPU collision layout. It checks manifest EXE/PDB hashes and the dump's CodeView GUID/age before using `level` RVA `0xc052b0`, `FLevelLocals::levelMesh` offset `0x290` and `LevelMesh::Mesh` offset `0x38`. Matching private PDB types and `dx level.levelMesh` supplied the layout; native debugger logs are hashed in the result index. This is an identity-gated forensic reader, not a portable arbitrary-build debugger.

- CollisionNode GPU/CPU upload ABI: 48-byte stride, center at 0, extents at 16, left/right/element at 32/36/40. Vertex stride 32; position's three floats start at 0. Source/GLSL inspection agrees; these surfaces and `VkShaderKey` are unchanged between captured source and current base.
- `CPUAccelStruct::Upload()` grows `Mesh.Nodes` backing storage and leaves unused tail data. The checker recomputes its **expected live upload node count** from post-error TLAS and non-null BLAS vector counts (both source node strides 64), then bounds traversal against it. That is stronger than using TArray backing count; it still does not prove the extent actually submitted or visible to the GPU.
- Every logical index before `Mesh.IndexCount` must address an allocated vertex with finite position. Each reachable leaf must name an aligned triangle wholly within that logical extent. Backing index capacity is not an initialized logical range.
- Reachable node links, cycles/shared children, finite bounding boxes and non-negative extents are checked. Full-overlap traversal pushes right then left as GLSL does; the maximum pending stack bounds the shader traversal for this tree even without ray culling. Unreachable backing nodes/padding are not interpreted as live geometry.
- Reads/counts are bounded, split adjacent ranges are supported, absent/truncated/overlapping memory is rejected, and only 32 error examples are retained. Parser bounds are offline limits, never production traversal cutoffs.

| Run suffix | Recomputed live nodes | Reachable nodes | Leaves | Peak pending stack | Errors |
|---|---:|---:|---:|---:|---:|
| 0ddb0be3fb9b | 222889 | 222865 | 111433 | 18 | 0 |
| fb7bc5f7a0a2 | 222889 | 222865 | 111433 | 18 | 0 |
| 8d82fb1ce3d1 | 222889 | 222865 | 111433 | 18 | 0 |
| 649ffe016f4a | 222887 | 222863 | 111432 | 18 | 0 |
| 4490fb662ae2 | 222887 | 222863 | 111432 | 18 | 0 |
| c91d81c1724d | 222889 | 222865 | 111433 | 18 | 0 |

The first row is #78; the next two are GTX CFX-005; the next two are cross-adapter P400; the last is native P400. All have root 46, logical IndexCount 334302, maximum leaf start 334299 and maximum referenced vertex 183405 below vertex count 226975. The 24 non-null BLAS slots are contiguous from zero in all six dumps. The source's null-slot/instance-counter seam is therefore not triggered by these snapshots. Counts/hashes differ across some captures; no byte-equivalence across tics or faulting submissions is asserted.

**Result:** no malformed CPU tree, logical index violation, non-finite referenced position, or 64-entry fallback stack overflow is demonstrated in any of these six post-error snapshots. This is negative evidence for those captured CPU states. It does not validate descriptor targets, mapped-memory visibility, resource lifetime, the actual GPU buffer contents, or a previous transient bad state.

### Reproduce the read-only check

From the repository root, with a preserved dump and its own run manifest:

```powershell
python tools/cfx_cpu_dump.py --dump C:/path/to/run/process.dmp --manifest C:/path/to/run/manifest.json --output C:/ShadeDoomVK/pf-local-evidence/cfx004-offline-20261001/recheck.json
python -m unittest discover -s tools/pf_oracle/tests -p test_cfx_cpu_dump.py -v
```

Exit 0: the specific checks passed; 1: a reported invariant violation; 2: incomplete/unsupported evidence. Never interpret exit 0 as proof of application/Vulkan correctness. Output contains hashes/metadata, not proprietary geometry. The output cannot overwrite the dump or manifest, including through an existing hard-link alias. Review found that path resolution alone missed this alias; the synthetic pre-fix CLI test returned 0 and overwrote its test input. File-identity checks now reject aliases before extraction/writing, with both dump and manifest preservation asserted. No original capture was used for this negative test.

The parser uses Microsoft's [Memory64List](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_memory64_list) and [ModuleList module](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_module) layouts. Its narrow MSVC object layout is independently pinned by this PDB, not inferred from those container definitions.

## Shader/submission and collection gaps

All six timelines have 22 `pipeline-first-use` creation events and the same 11 distinct logged shader QWORD values. Bit 13 (`UseRaytrace`) is clear in each; bit 12 (`UseShadowmap`) is set. These are specialization inputs, not proof of execution. `light_shadow.glsl::shadowAttenuation` can still choose tracing from runtime `LIGHTINFO_TRACE`. `frag_main.glsl` uses `uLightIndex=-1` for the LevelMesh path, but that does not establish every sprite/model/light path's flags. No per-draw runtime light flags survive.

The marker in `vk_renderpass.cpp::CreatePipeline` omits `Layout.AsDWORD`, `SpecialEffect`, `EffectState`, `VertexFormat` and exact draw-to-SPIR-V mapping. Cache hashes/cache-hit keys identify inputs, not a faulting instruction. A graphics checkpoint only identifies the marker's queue stage and buffer/submission relationship.

A narrow source review finds frame delete lists cleared after successful fence checking, and submit-fence slots waited/reset before reuse. A loss throws before normal continuation. This is consistent ordering, not a lifetime proof for every producer/descriptor/reference. No observed invalid retirement transition or speculative repair is retained.

The existing EXT collector silently returns empty on an unsupported/disabled path or either query's error; successful empty data is also possible. NV retrieval emits per-marker records but not post-loss zero counts. Native P400's missing payload is therefore **missing evidence**, not proof that the extension failed, no GPU fault occurred, or no command executed. A future separately reviewed capture revision should log bounded query result/counts, complete pipeline identity, descriptor/buffer generation and submission-correlated upload hashes/ranges. Initialization/synthetic checks can be done offline or on safe paths; they do not authorize another primary launch.

## Causal/minimization disposition

No application-side causal chain reaches all five links:

`input transition -> violated invariant -> GPU-visible invalid state -> consuming operation -> observed failure`.

The observed GPU fault/device-loss endpoints survive; the invalid invariant, resource mapping and consuming operation remain missing. Accordingly:

- **No renderer repair or workaround is proposed.** No cap, feature disable, global idle, cache flush, quality reduction or shader cutoff is introduced.
- No content/pass/resource reduction is retained: there is no demonstrated CPU invariant to preserve and both physical lanes are stopped. Differing fault payloads are not a minimized same-signature result.
- The legal synthetic fixture is an adversarial regression for the checker, **not** a DBP37 crash reproducer or a pre-fix engine failure fixture.
- Compatible decoding of the preserved GTX EXT vendor binary could still map the fault offline. No compatible local decoder has demonstrated that mapping. No new Aftermath integration/driver installation or external vendor submission occurred.
- A vendor-grade valid minimized workload is not available. Driver/implicit-layer causality remains unproven; the raw packet is evidence, not proof of a valid application workload.

**Precise remaining discriminator:** identify the consuming shader/resource/submission for the preserved fault/checkpoint, with the exact uploaded bytes, descriptor ranges/generations and retirement identity. Neither a downstream `VkResult` nor a post-error CPU snapshot supplies that mapping. Continue offline decoding/source work where possible; any new physical discriminator needs a new human-reviewed protocol and safety accounting. Existing STOP markers cannot be bypassed.

## Every CFX-001 incident

No common causal mechanism has been proven, so none is classified SAME PROVEN MECHANISM or DISTINCT PROVEN MECHANISM.

| Incident ID | Relation to primary mechanism | Evidence boundary |
|---|---|---|
| CFX-DBP50-20260920-MAP08 | INSUFFICIENT HISTORICAL EVIDENCE | Original/v1.2 MAP08 driver/TDR evidence lacks application initiating operation and resource mapping. LevelMesh-off failures contradict a universal LevelMesh-required hypothesis, not proof of a different root cause. |
| CFX-DBP50-20260923-1824 | INSUFFICIENT HISTORICAL EVIDENCE | Original/v1.2 MAP08 driver/TDR evidence lacks application initiating operation and resource mapping. LevelMesh-off failures contradict a universal LevelMesh-required hypothesis, not proof of a different root cause. |
| CFX-DBP50-20260923-2259 | INSUFFICIENT HISTORICAL EVIDENCE | Original/v1.2 MAP08 driver/TDR evidence lacks application initiating operation and resource mapping. LevelMesh-off failures contradict a universal LevelMesh-required hypothesis, not proof of a different root cause. |
| CFX-DBP50-V12-20260924-1309 | INSUFFICIENT HISTORICAL EVIDENCE | Original/v1.2 MAP08 driver/TDR evidence lacks application initiating operation and resource mapping. LevelMesh-off failures contradict a universal LevelMesh-required hypothesis, not proof of a different root cause. |
| CFX-DBP37-MAP01-20260924 | CONSISTENT BUT UNPROVEN | Same preserved content/config startup failure on a later instrumented binary; historical dump/application loss observation absent; initiating mechanism unknown. |
| CFX-MAP04-CAPDIAG-20260924 | INSUFFICIENT HISTORICAL EVIDENCE | Timeout with no new driver event, no application error or retained stack. No evidence to equate it with a GPU device-loss mechanism. |
| CFX-SUNLUST-MAP24-20260924 | INSUFFICIENT HISTORICAL EVIDENCE | Arena driver events/partial CPU trace but no fault/resource/submission mapping or process dump; distinct content and workload. |

## Verification and acceptance map

| #79 requirement | Delivered result |
|---|---|
| Primary causal proof / valid vendor reproducer / precise blocker | Precise blocker above; no causal claim or vendor-validity claim |
| Minimization and dead ends | No reduction retained; CPU bounds/tree/stack candidate fails to expose an invalid captured state; native output still loses device with absent fault payload |
| Bounded repair and regression | Explicit no-renderer-code disposition; read-only checker with 19 legal positive/adversarial tests |
| Cross-case disposition | Every one of the seven CFX-001 incident IDs classified above and in JSON |
| Physical limitation | Zero new launches; original and cumulative lane stops remain; no candidate physical verification claimed |
| Parent/programme disposition | #75 remains open on named discriminator; PF-020/#37 remains blocked; no SDVK transition |

Local verification: 19 focused tests pass; deterministic PF oracle matches its baseline twice with identical SHA-256 `2f8d95cf...`. Full local discovery ran 133 tests: 122 Python/source tests pass, 11 existing compiled-fixture tests cannot run because `c++` is absent from this Windows PATH (`FileNotFoundError`). This is **not** a green full local suite. Linux CI's configured compiler must run those fixtures. No engine source was modified, so no new renderer equivalence/GPU run was needed or attempted. CI/review/merge acceptance is a separate gate.
