# ShadeDoomVK execution ledger

Status: planning workflow complete; implementation begins at PF-001  
Started: 2026-09-17  
Planning closure: 2026-09-17

This ledger records significant programme-level planning changes and later gate transitions. Individual issue/PR evidence remains authoritative for implementation details.

## Ledger entries

### 2026-09-17 — founding programme created

- Established baseline `VKDoom@09634479ab5bf9adf691074fffe85a006a398cd0`.
- Created founding documents `00` through `07` and autonomous issues SDVK-001..017 (#1..#17).
- Initial plan placed observability, upstream policy, descriptors and material semantics before headline sprite effects.

### 2026-09-17 — fork/donor audit reconciled

- Confirmed several apparent VKDoom donor forks are ancestral to the ShadeDoomVK baseline.
- Retained non-ancestral donor concepts from jalovisko and MAD-VKDoom as explicit provenance/hypotheses.
- Recorded GriddleVK per-layer sampling as an initially attractive donor concept.

### 2026-09-17 — deep baseline source audit

Key corrections:

- per-layer material sampling is already present in the inherited baseline;
- bindless descriptor reuse already exists but lacks the desired capacity/lifetime diagnostics and hardening;
- per-lightmap probe selection is stubbed to probe 0 and its dormant implementation is unfinished;
- light-tile/cluster scaffolding exists but is dormant;
- HDR/postprocess groundwork is stronger than the founding plan assumed;
- multiple concrete renderer correctness defects and no-quality-change optimization opportunities were identified.

Decision: do not begin SDVK-001 yet.

### 2026-09-17 — pre-foundation hardening programme inserted

- Added `08-PREFOUNDATION-HARDENING-PROGRAMME.md`.
- Added `09-PLANNING-RECONCILIATION.md`.
- Added renderer RAG/reference corpus under `docs/shadedoomvk/rag/`.
- Defined PF-001..PF-020 as a hard pre-SDVK tranche.
- PF-020 becomes the hard release gate for SDVK-001.
- Stable SDVK-001..017 IDs and issue numbers remain preserved.
- New PF issue set uses the expanded autonomous issue contract: objective; scope; non-goals; dependencies; concurrency; canonical context; implementation prompt; acceptance criteria; verification; expected artifacts; blockers/stopping conditions.

### 2026-09-17 — PF/SDVK tracker reconciliation completed

- Created PF-001..PF-020 as GitHub issues #18..#37 and canonical issue-body files.
- Reconciled every SDVK-001..017 live/canonical issue to the same autonomous contract.
- Reframed duplicated founding scope:
  - SDVK-004 is rich-workload descriptor integration/stress after PF hardening;
  - SDVK-005 adds height semantics rather than re-porting inherited per-layer sampling;
  - SDVK-009 evaluates higher-order many-light architecture after PF exact-equivalence CPU optimization.
- Updated README, AGENTS, revised roadmap, issue graph, validation contract and donor provenance.

### 2026-09-17 — independent second review completed

- Added `11-INDEPENDENT-PLAN-REVIEW.md`.
- Verified requested refactor/bug/performance coverage.
- Reviewed issue sizing, duplicate scope, hidden assumptions, unsafe concurrency, tests and stopping conditions.
- Found and repaired two hidden prerequisites:
  - PF-012 now depends on PF-003 so probe/page descriptor correctness cannot run before descriptor reservation/lifetime hardening;
  - PF-017 now depends on PF-013 so material-cache optimization consumes corrected material behavior.
- Rechecked the corrected graph as acyclic.

### 2026-09-17 — final repository consistency pass completed

Verification snapshot before the final consistency-report/ledger commits: `master@9e3d016fff290dfbe3b78490cbc5a1d7f60af2e6`.

- Added `12-FINAL-CONSISTENCY-CHECK.md`.
- Inspected live issue tracker and confirmed the programme mapping remains SDVK #1..#17 and PF #18..#37.
- Inspected canonical issue-body and RAG directories.
- Exact planning-placeholder search returned no result.
- `TEMP` issue search returned no result.
- Open pull-request list was empty.
- Marked `01-INITIAL-IMPLEMENTATION-PLAN.md` historical/non-executable.
- Amended founding brief with PF gate and deep-audit qualifications.
- Recorded that `master` is not currently branch-protected; `AGENTS.md` therefore mandates PR/check/merge discipline independently of repository enforcement. This is not a renderer planning blocker.

## Planning-pass stage checklist

- [x] Reconcile relevant planning conversation history available to this run.
- [x] Inspect current repository and GitHub issue/PR state before broad mutation.
- [x] Determine implementation decomposition is warranted and insert PF tranche before the old graph.
- [x] Identify and repair major omissions/incorrect assumptions from deep source audit.
- [x] Commit complete RAG/reference corpus.
- [x] Reconcile founding docs/AGENTS/README with PF tranche.
- [x] Emit complete PF issue set with canonical issue-body files.
- [x] Reconcile SDVK-001..017 issue bodies and canonical files.
- [x] Review dependencies/concurrency/issue sizing independently.
- [x] Correct findings from independent review.
- [x] Perform final repository-wide consistency pass.
- [x] Record final GitHub issue mapping and implementation gate state.

### 2026-09-17 — PF-001 accepted and merged

- PF-001 / #18 completed through PR #38.
- Required CI passed: deterministic PF renderer oracle plus the inherited Windows, macOS and Linux build matrix.
- Repaired the inherited Linux Clang 11 CI dependency gap by adding `libvpx-dev`.
- Merge commit: `069d25a156c6341de448abf98a99b7ebf059f948`.
- PF-002, PF-006, PF-007, PF-009 and PF-011 became dependency-ready.

### 2026-09-18 — PF-002 accepted and merged

- PF-002 / #19 completed through PR #39.
- Required current-head CI passed: deterministic PF oracle, compiled stale-resource identity fixture, Windows/macOS/Linux build matrix.
- Introduced the renderer generation/epoch substrate and wired bindless, LevelMesh, texture, lightmap, probe and async reset hooks without replacing hot-path integer identities.
- Merge commit: `77d143ae888cbd8fbdd5f86b0fc3207025cdc2a4`.
- The post-merge `master` run also passed the full matrix.
- PF-003 and PF-004 became dependency-ready.

### 2026-09-19 — PF-003 accepted and merged

- PF-003 / #20 completed through PR #40.
- Required deterministic PF oracle and Windows/macOS/Linux build matrix passed before merge; the post-merge `master` run also passed.
- Hardened bindless device-capacity/reservation handling, fixed the lightmap/probe descriptor overlap, and retained exact-size generation-aware reuse without unsafe global flushing.
- Merge commit: `8ee205b6476446bc4552aaa92a47a7450453516c`.
- PF-005 and PF-008 became dependency-ready. PF-012 remained blocked on PF-004, PF-010 and PF-011.

### 2026-09-19 — PF-004 accepted and merged

- PF-004 / #21 completed through PR #41.
- Required current-head CI passed: deterministic PF oracle, compiled LevelMesh allocator/mutation fixture, and the inherited Windows/macOS/Linux build matrix.
- Froze the LevelMesh mutation/allocation contract, added generation/span diagnostics and fail-closed invalid-range handling, repaired CPU BLAS dirty-partition rounding and two-sided texture-Z invalidation, and made lightmap/atlas mutation dependencies inspectable without replacing the existing update machinery.
- Merge commit: `ea64022b3bc71572ecb91d04284cfc4058ce357a`; `master` was verified at that merge commit.
- PF-012 no longer waits on PF-004 but remains blocked on PF-010 and PF-011. PF-015 now waits on PF-010 and PF-011; PF-018 remains downstream of PF-015.
- Residual note: `OnMidTex3DHeightChanged()` remains intentionally unclaimed pending source-proven ownership; PF-004 does not mask that uncertainty with a broad full refresh.

### 2026-09-19 — PF-005 accepted and merged

- PF-005 / #22 completed through PR #43.
- Required current-head CI passed: deterministic PF renderer oracle, compiled staging boundary/stress fixture, and the inherited Windows/macOS/Linux build matrix.
- Hardened async texture-upload lifetime with manager and per-target PF-002 epochs plus all-owner cancellation, and replaced ordinary per-texture staging allocations with a bounded 64 MiB persistent upload arena.
- Arena wrap waits for transfer retirement before reused bytes are mapped; oversize fallback buffers are waited and retired immediately. Texture source processing, formats, filtering, mip policy, material meaning, gameplay/tic, sprite, portal, audio and provenance semantics remain unchanged.
- Deterministic allocation evidence: 1024 × 64 KiB qualified uploads fit one persistent allocation with zero wrap waits through the exact 64 MiB boundary; upload 1025 requires one upload-only wait before byte-zero reuse.
- Merge commit: `5e88be8ab6565fdc079bca6003d57be44ed11096`; `master` was verified at that merge commit.
- PF-019 now has its PF-005 prerequisite satisfied but remains blocked on PF-006, PF-007, PF-017 and PF-018; no new issue becomes dependency-ready solely from PF-005.
- Residual scope: unrelated lightmap/probe staging and download/readback staging remain outside PF-005 under their existing ownership.

### 2026-09-19 — PF-006 accepted and merged

- PF-006 / #23 completed through PR #45.
- Required exact-head CI passed: deterministic PF renderer oracle, compiled old/new key-partition and boundary fixture, and the inherited Windows/macOS/Linux build matrix.
- Replaced whole-object `memcmp`/padding identity for `VkShaderKey`, `VkPipelineKey` and `VkRenderPassKey` with explicitly named semantic state while preserving the old valid-state partition.
- `FRenderStyle` identity now names its repository-defined `BlendOp`, `SrcAlpha`, `DestAlpha` and `Flags` bytes directly; all four bytes remain identity, but union packing, host byte order and `AsDWORD` representation are no longer part of the pipeline-key contract.
- `VkShaderKey::AsQWORD` remains the packed shader-specialization ABI. Generalized/specialized maps, pipeline-library decomposition, worker/precache paths and the opaque Vulkan driver cache remain unchanged; PF-006 makes no lookup-performance claim.
- Adversarial verification covers every meaningful shader/pipeline field, all four render-style bytes at boundary values, old padding/reserved-bit noise, generalized-vs-specialized distinctions and warm ordered-cache reconstruction.
- Merge commit: `ba9422554952355b7d3a0a87595cb994667d2be8`; `master` was verified at that merge commit.
- PF-019 now has its PF-006 prerequisite satisfied but remains blocked on PF-007, PF-017 and PF-018; no new issue becomes dependency-ready solely from PF-006.
- Shader behavior, material meaning, blend/depth/stencil/cull policy, portal behavior, palette/translation behavior, sprite conventions, gameplay/tic state, audio and donor/source provenance remain unchanged.

### 2026-09-19 — PF-007 accepted and merged

- PF-007 / #24 completed through PR #49.
- Required exact-head CI passed: deterministic PF renderer oracle, compiled capability/driver-quirk adversarial fixture, source-routing contract tests, and the inherited Windows/macOS/Linux build matrix.
- Added a single descriptive `VulkanCapabilities` snapshot covering required bindless descriptor-indexing feature bits and limits, ray-query/acceleration-structure state, graphics-pipeline-library support, clip-distance state, scene sample counts, depth/normal render-target fallback choices, device identity and named Intel/AMD quirks.
- Migrated descriptor capacity, sampler quirks, graphics-pipeline-library availability, ray-query capability and scene-MSAA selection to named capability queries while keeping user/configuration policy separate.
- Preserved the inherited Intel sampler classifier including legacy devices, unknown Intel IDs and the exact `0.405.1286` current-driver boundary; preserved the AMD ray-query guard exactly as vendor `0x1002` with `VK_VERSION_MAJOR(driverVersion) < 10`.
- Ray query remains optional with the inherited non-ray-query storage-buffer fallback; graphics-pipeline-library use remains independently controlled by `gl_ubershaders`; PF-003 bindless capacity planning and quality defaults are unchanged.
- Merge commit: `0e19f4aede276f4d9de27497302caed56b3200e5`; `master` was verified at that merge commit.
- PF-010 / #27 became dependency-ready. PF-019 now has its PF-007 prerequisite satisfied but remains blocked on PF-017 and PF-018.
- Gameplay/tic, shader/material meaning, palette/translation, sprite, portal, audio, demo-determinism, source-ownership and donor/provenance semantics remain unchanged.

### 2026-09-19 — PF-008 accepted and merged

- PF-008 / #25 completed through PR #51.
- Required exact-head CI passed: deterministic PF renderer oracle, PF-008 semantic source/compiled boundary coverage, and the inherited Windows/macOS/Linux build matrix.
- Added explicit semantic identity for the inherited albedo, normal, legacy-specular, metallic, roughness, ambient-occlusion, brightmap/emissive-intent, detail, glow and custom material channels while retaining the historical ordered layer array as the sole descriptor-binding order truth.
- Sparse custom extension layers retain their original `0..14` authoring slot through `customIndex`; `FMaterial::FindLayer()` provides semantic-to-current-binding lookup and `GetLayerDiagnostic()` exposes binding/source/sampling state without creating a second ordering mechanism.
- Legacy specular/PBR ordering, placeholder bright/detail/glow resources, custom sampler overrides, indexed/palette/translation paths, warped/canvas exclusions, shader selection and PF-003 descriptor lifetime/reservation semantics remain unchanged. No height/POM authoring or donor import was introduced.
- Merge commit: `cfbd5a2770520a3070f3610a8239b021726a1cb7`; `master` was verified at that merge commit.
- PF-013 / #30 became dependency-ready. PF-017 still waits on PF-013 and PF-016.
- Gameplay/tic, shader/material meaning, palette/translation, sprite, portal, audio, source-ownership and donor/provenance semantics remain unchanged.

### 2026-09-19 — PF-009 accepted and merged

- PF-009 / #26 completed through PR #53.
- Exact implementation head `8f78d5a10fe502d144b09b51f786b97e6e6bb54e` passed Continuous Integration run 65: deterministic PF renderer oracle, adversarial sprite-surface policy/source-contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Extracted observational `HWSpriteRenderSurfaceState` plus the pure `ResolveHWSpriteOrientationPolicy()` adapter so later tangent/POM/shadow/light work consumes one sprite presentation meaning instead of re-deriving frame, UV mirror, billboard, view and portal state.
- Preserved inherited frame selection, geometry, clipping/anamorphosis, UV assignment, material/palette/translation behavior, draw ordering, portal transforms and normal/TBN behavior; no height/POM, sprite-shadow, gameplay, audio or donor/provenance change was introduced.
- Merge commit: `b58f03decfedca12df039c68a5e36d709120bba1`; `master` was verified at that merge commit and post-merge Continuous Integration run 66 passed on the exact merge head.
- PF-014 retains PF-010 as its remaining extraction prerequisite; PF-016 retains PF-011 and PF-015. No issue becomes newly dependency-ready solely from PF-009 because those remaining prerequisites are still open.

### 2026-09-19 — PF-010 accepted and merged

- PF-010 / #27 completed through PR #55.
- Exact implementation head `9116f9f5dff601a9c31bc97c63da39c1116f4739` passed Continuous Integration run 70: deterministic PF renderer oracle, compiled/adversarial render-context fixture and source-routing contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Extracted observational `HWRenderContext` root/portal identity with a per-top-level epoch, per-eye/per-recursive-pass local identity, parent/depth, probe-face/eye, and inherited line/plane mirror parity; the context does not drive transforms, postprocess policy or temporal behavior.
- Merge commit: `489e94e7194dacb7dcc2d7ed615ea9a1839a87c2`; `master` was verified at that exact merge commit.
- PF-014 / #31 became dependency-ready. PF-012 / #29 and PF-015 / #32 now retain PF-011 / #28 as their remaining readiness prerequisite.
- Gameplay/tic, material/shader, palette/translation, sprite, portal-transform, audio, source-ownership and donor/provenance semantics remain unchanged.

### 2026-09-19 — PF-011 accepted and merged

- PF-011 / #28 completed through PR #57.
- Exact implementation head `6c977abec0a9f957d9bc5e0f24d46bb87990950e` passed Continuous Integration run 76: deterministic PF renderer oracle, adversarial/numerical lighting compatibility fixtures, source-contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Named the inherited CPU dynamic-light packing/sun proxy and shader-side PBR/sun/ambient compatibility calibration without numerical retuning; inverse-square operation ordering and intentionally distinct CPU aggregate sprite-light behavior remain frozen.
- Verification covers authoring-strength saturation, normalization/linearity boundaries, GLDEFS and alpha multiplication, additive/subtractive packing, deterministic moving-light attenuation points, spotlight edges, sunlight proxy behavior and direct-PBR/sun/ambient/metallic bridge vectors.
- Merge commit: `1c16f7e76d8927c315c4fc57b8c9e532ca99c84b`; `master` was verified at that exact merge commit.
- PF-012 / #29 and PF-015 / #32 became dependency-ready. PF-016 / #33 now retains PF-015 as its remaining prerequisite.
- No physical-lighting calibration, quality/default policy, light selection, shadow/probe policy, gameplay/tic, material/palette/sprite/portal, audio, source-ownership or donor/provenance semantic change was introduced.

### 2026-09-19 — PF-012 accepted and merged

- PF-012 / #29 completed through PR #59.
- Exact implementation head `a31852b7a7dd6d9cbc0133b07906ca70544e80b8` passed Continuous Integration run 90: deterministic PF renderer oracle, compiled probe-selection adversarial/boundary fixture, source-contract coverage, and the inherited Windows/macOS/Linux build matrix; post-merge `master` run 91 passed at the exact merge head.
- Replaced the inherited lightmap probe-0 stub with a bounded nearest-probe selector that stores the runtime PF-003 allocator-returned irradiance descriptor identity in the `R16_UINT` probe map, keeps 0 as explicit fallback, and leaves the unfinished GPU AABB traversal dormant.
- Fixed non-zero-floor probe midpoint placement, builder terminal/empty/count-change behavior, dormant CPU AABB leaf/root/traversal correctness, runtime probe-map invalidation, and atlas/copy-buffer ownership/bounds checks.
- Merge commit: `8db714d3b5856acb3a4ea09839d4999f20ce5d5d`; `master` was verified at that exact merge commit.
- PF-013 / #30, PF-014 / #31 and PF-015 / #32 remain dependency-ready; no new PF issue becomes dependency-ready solely from PF-012.
- Gameplay/tic, material/PBR calibration, palette/translation, sprite, portal-transform, audio, source-ownership and donor/provenance semantics remain unchanged.

### 2026-09-20 — PF-013 accepted and merged

- PF-013 / #30 completed through implementation PR #61; the acceptance reconciliation is recorded separately after post-merge verification.
- Exact implementation head `cb0e7e6c03d8ffa52de3fd6aa877f7eac9bec4b2` passed Continuous Integration run 98 with the deterministic PF renderer oracle, PF-013 adversarial/source-contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Repaired Vulkan `CTF_IndexedRedIsAlpha` as luminance-as-alpha without aliasing ordinary indexed/palette identity, made the GGX roughness-zero boundary finite without retuning ordinary PBR response, and fixed sprite precache to pass the computed expand/upscale scale flags.
- PF-003 descriptor/generation cleanup semantics remain intact under the 10,000-cycle recreation stress; ordinary translations, layer ordering, material calibration, gameplay/tic, sprite/portal meaning, audio and provenance semantics remain unchanged.
- Merge commit: `b5437e22c4da23bef95651f17ec013a0fe52cb1a`; post-merge `master` Continuous Integration run 99 passed on that exact merge head.
- PF-017 now has its PF-013 prerequisite satisfied and remains blocked only on PF-016. PF-014 / #31 and PF-015 / #32 remain dependency-ready.

### 2026-09-20 — PF-014 accepted and merged

- PF-014 / #31 completed through implementation PR #63; this acceptance reconciliation records the final gate transition after post-merge verification.
- Exact implementation head `3350461964f5ee97e63eb84257b514c171459a1a` passed Continuous Integration run 102 with the deterministic PF renderer oracle, compiled PF-014 adversarial fixture, source-contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Repaired the sprite ceiling sentinel fallback to use `-NO_VAL` consistently and replaced `HWSkyInfo` raw-object `memcmp` equality with explicit semantic-field identity. PF-009 sprite orientation and PF-010 portal-context ordering remain unchanged.
- Merge commit: `42aae69ec97b124970b88b8ddba314a486ac5a55`; `master` was verified at that exact merge commit and post-merge Continuous Integration run 103 passed on the merge head.
- PF-015 / #32 remains the highest-priority dependency-ready corrective issue. PF-014 does not newly unblock another PF issue by itself.
- Gameplay/tic, material/palette/translation meaning, sprite frame/UV selection, portal transforms/recursion, audio, source ownership and donor/provenance semantics remain unchanged.

### 2026-09-20 — PF-015 accepted and merged

- PF-015 / #32 completed through implementation PR #65; this acceptance reconciliation records the final gate transition after post-merge verification.
- Exact implementation head `e3a4e69a0976ba74b13e299cc3035d866209ea42` passed Continuous Integration run 106 with the deterministic PF renderer oracle, compiled shadow/visibility adversarial boundary fixture, source-contract coverage, and the inherited Windows/macOS/Linux build matrix.
- Preserved exact inherited shadow selection and row order for eligible sets up to the physical 1024-row capacity; overflow now selects by squared distance to the interpolated central main view with deterministic spatial/light semantic ties and exposes processed/candidate/selected/dropped diagnostics.
- Actor/static-light and sun visibility cache reuse now consumes the existing PF-004 `LevelMeshMutationEpochs::Query` plus stable portal-group context and inherited actor/light invalidators, so moving world occluders invalidate stationary actor/light visibility without globally disabling caching.
- Merge commit: `1a60a3cbb9360e8b1d74a2764c8472ffd65d044d`; `master` was verified at that exact merge commit and post-merge Continuous Integration run 107 passed on the exact merge head.
- PF-016 / #33 and PF-018 / #35 become dependency-ready. PF-017 / #34 remains blocked on PF-016; PF-019 / #36 remains blocked on PF-017 and PF-018; PF-020 / #37 remains blocked on all unfinished PF issues.
- Gameplay/tic, PF-011 lighting calibration, shadow-map capacity/resolution/filtering, ray-query capability/fallback routing, actor-light gathering policy, portal transforms, sprite/material/palette/translation meaning, audio, source ownership and donor/provenance semantics remain unchanged.

### 2026-09-24 — PF-016 accepted and merged

- PF-016 / #33 completed through implementation PR #67; this reconciliation follows successful post-merge verification.
- Tested renderer implementation: `c2684881a5b0c1b74cb361eced0c35b2ac17b90e`; submitted head: `4c753f92b155ad72aa7e017001bfc4d9f7fd1bb0`. Renderer/test source is identical across those revisions and the merge.
- All eight required PF-oracle/Windows/macOS/Linux checks passed in exact-head run 35984105517 and post-merge run 35990476576.
- Merge: `6091d6739c4b7dc96ef7913c911bf4eba89d7715`, verified on `master`.
- One query pipeline preserves portal-relative filtering, visibility, selected identity/order/class and packing. Generation membership replaces sorted maintenance; unique local traversal skips redundant membership only after exact side-by-side qualification. Position/radius/section/group changes invalidate qualification, and unsupported cases remain BSP.
- Representative production S: Setup median improves 4.137 to 3.761 ms (-9.09%), all five interleaved pairs winning; separate warm distributions improve 4.45%. Five production image pairs and interior/boundary state comparisons are exact.
- Remaining live runtime gates pass: linked displaced groups, cross-group fallback, actual model-list visibility/cache results under moving occlusion, static hits, all light classes/types, models/sprites, radius/section boundaries and qualification invalidation. Eighteen images are pixel-identical; 1,738 selected/packed plus 576 visibility/cache records match at image checkpoints, with 1,450 matching mutation-tic records. A camera-contaminated exploratory pair is preserved/excluded, and input-locked reruns pass.
- Raw evidence is under `C:/ShadeDoomVK/pf-local-evidence/pf016/runtime-20260924` and `repair-20260924`; `PF-016-RUNTIME-EVIDENCE.md` indexes hashes, scripts and limits. All 318 historical artifact hashes were verified unchanged. No new device loss/driver timeout occurred and no full DBP50 MAP08 was launched.
- PF-017 / #34 is now dependency-ready after PF-003/PF-008/PF-013/PF-016; no PF-017 implementation was started. PF-018 status and remaining PF-019/PF-020/SDVK gates are unchanged.
- Residual scope: one Windows/NVIDIA runtime configuration and bounded deterministic checkpoints; retained fallback qualification allocation cost. No shader/light-math/quality, gameplay, palette/material, audio or donor-source ownership change.

### 2026-09-24 — PF-018 runtime qualified; final-head gate pending

- PF-018 / #35 implementation PR #68 was reconciled with PF-016 on current `master@4f6df9843e742c59defcf4ce1a5686271b2b5c75`; tested candidate `7d390a3fb2dbda65688933ab5f868092afec5a41` has only the nine PF-018 implementation files as a delta.
- Five alternating production DBP37 MAP04 pairs on one GTX 1650 SUPER/driver/build configuration all launched and rendered. Identical read-only capacity instrumentation in four complete pairs measured 11,702,876 baseline versus 8,635,124 candidate logical bytes across the ten LevelMesh arrays (−26.21%); production exports independently repeat the vertex/surface reductions. MAP04 exercises setup allocation/growth, not moving AABB lines or a steady-state CPU gain.
- The targeted GLDEFS-light derivative exercises moving AABB lines. Direct fixed-tic RayTest input/fraction records match 1,630/1,630, production paused world pixels and oriented faces match, and five warm AABB pairs give 310.378 versus 159.175 ns per moved line median (−48.72%). Whole BeginFrame diagnostic medians are 20.129 versus 20.082 ms/frame (−0.23%, mixed pairs), so no material whole-path speedup is claimed.
- The original fixture, PF-004 ownership/generation/span and PF-018 fragmentation/best-fit/bounded-growth stress are covered by the compiled deterministic oracle. All eight checks passed on reconciled source head in CI run 36000665523. Doom2-only MAP01 launched on both revisions; an uncapped DBP37 MAP01 startup hang/TDR occurred on baseline and is a separate compatibility issue. One mouse-overlapped test-only capacity timeout is preserved/excluded and a later pair is clean. DBP50 was not retested.
- `PF-018-RUNTIME-EVIDENCE.md` records exact hashes, commands, raw logs and limitations. This is **not** the completed issue gate: final documentation-head CI, merge and post-merge `master` verification are still required. PF-019 remains blocked on PF-017 and PF-018.

### 2026-09-24 — PF-018 accepted and merged

- PF-018 / #35 implementation and evidence PR #68 passed the unchanged acceptance gate. Runtime-tested implementation `7d390a3fb2dbda65688933ab5f868092afec5a41` compared with PF-016-accepted `master@4f6df9843e742c59defcf4ce1a5686271b2b5c75`; final documentation head `84fc7b527e9bcb94dd01a1b9041ee8f02f5548cf` changed only canonical evidence. All eight exact-head checks passed in CI run 36005308547.
- Merge commit `8ad883ada35b80dbf750462dbb4c36b5edf38893` has the exact final PR tree and was verified as local and remote `master`. All eight post-merge checks passed on that exact merge head in CI run 36006321198.
- Frozen contract: PF-004 ownership/generation/span checks and stationary live ranges remain authoritative; best-fit lookup and bounded growth reduce main LevelMesh array capacity on representative DBP37 MAP04; cached immutable leaf→parent AABB traversal preserves direct fixed-tic queries, production geometry and paused world pixels on the moving GLDEFS-light fixture. No dirty-upload batching or whole-frame CPU speedup is claimed. `PF-018-RUNTIME-EVIDENCE.md` retains measurements, raw-log paths and exclusions.
- PF-018 is complete. PF-019 / #36 now waits only on PF-017 / #34; PF-020 / #37 still waits on unfinished PF issues. The baseline DBP37 MAP01 startup TDR, prior DBP50 crashes and one excluded mouse-overlapped diagnostic timeout do not enter the PF-018 benefit claim. DBP37 MAP01/DBP50 compatibility remains separate work.

### 2026-09-24 - PF-017 baseline profiled; candidate rejected

- PF-017 / #34 remains open. Accepted baseline master 66b09a872b9d45b496a27c1bf1406d8a74606cd2 was profiled on the physical GTX 1650 SUPER.
- The dense PF-016 fixture produced 49,473 logical light records but 217 distinct packed records and 3,971,280 mapped copy bytes per steady frame. Complete-list/subrange reuse could save only 2.40%.
- A per-record hash/reference-buffer/shader-indirection prototype cut mapped writes 94.24% yet increased five-pair production S: Setup median from 3.615 to 8.432 ms (+133.25%) and All from 18.227 to 24.225 ms (+32.91%). Every pair regressed; all five full RGB images matched. The prototype was restored, not merged.
- The dense fixture had at most one material variant per material; DBP37 MAP04 had at most three. A hashed descriptor lookup therefore lacks measured benefit and was not implemented. Optional default-resource sharing was not attempted.
- Canonical PF-017-PROFILING-NOTES.md records exact binaries, source patch hashes, commands, local raw evidence, limitations and next action. No PF-017 acceptance/CI/merge gate is claimed. PF-019 remains blocked on PF-017.

### 2026-09-24 - PF-017 second attempt: light benefit observed, material indexes rejected

- Accepted master b5fcab0a4c4847607007a6562c74b28c6e46a4d3 is renderer-identical to baseline binary build 66b09a872b9d45b496a27c1bf1406d8a74606cd2. The second attempt used dedicated branch pf-017-range-reuse-profiling and preserved base/patch/header/binary identities; no experimental renderer commit is proposed for acceptance.
- A source-owned packing-revision/temporal-write prototype avoids per-reference hashing and shader indirection. Five alternating production pairs improve S: Setup median 3.660 to 3.410 ms (-6.83%), all pairs winning and full images exact. Separate diagnostics show 13.83% fewer mapped bytes, byte-exact dense/moving checkpoint buffers and zero packing-oracle mismatches. Physical record layout is unchanged; complete source-ID/lifetime/adversarial proof remains required.
- Real Champions MAP08 content reaches 15 variants (17 using the mod's all-champions setting). Same-executable comparisons show node hash 46.71 to 90.98 ns/call (+94.8%, five pairs) and flat hash 46.20 to 63.21 ns/call (+36.8%, three pairs). Every pair regresses; direct linear-oracle mismatches are zero. Neither hash is retained.
- All experimental renderer changes were restored. PF-017-REUSE-RESEARCH.md and checked-in analyses record exact evidence, content identity, runtime limits, an inaccessible optional larger-variant asset and next action. No general whole-frame speedup, intra-frame physical compaction or descriptor saving is claimed.
- PF-017 / #34 remains not accepted and open. A promising light subset does not satisfy full scope. PF-019 / #36 remains blocked and was not started. The evidence-record PR/check/merge gate is separate from implementation acceptance.

### 2026-09-24 - PF-017 material workload qualification: no implementation retained

- Baseline/local/remote master `84bbbacbc2cea8568e78ac2f0e059ffc5608a897`; dedicated branch `pf-017-material-qualification`. All 322 prior evidence hashes verified unchanged.
- Published Sunlust/Champions with verified Freedoom produces median 1,201 expensive-cache lookups/frame in an authored MAP30 arena, but only about 47.13 microseconds/frame of estimated large-cache search. Starting cameras and DBP37 remain small-cache cases. The previous-hit hypothesis increases large-cache comparisons 1.81%.
- A MAP24 arena timeout with NVIDIA error 153 stopped GPU launches. No production confirmation or candidate pairs exist. The user-supplied stock KEX Doom II IWAD was identified after the failure and remains unprofiled.
- No material lookup candidate was implemented. Diagnostic source was archived/restored; accepted source rebuilt, deterministic oracle matched twice, and unchanged PF-003/PF-008/PF-013/generation fixtures passed with MSVC assertions. Evidence-record CI remains separate from renderer acceptance.
- [PF-017-MATERIAL-QUALIFICATION.md](PF-017-MATERIAL-QUALIFICATION.md) and machine-readable evidence retain the no-go decision, every workload, exact identities, uncertainty and next action. Light work/full acceptance are unchanged; #34 remains open and PF-019 blocked.

### 2026-09-24 - PF-017 off-GPU light-reuse candidate frozen

- GitHub issue #34 was revised from technique-specific requirements to measured outcomes: the slower material hash/index paths are a completed no-go, physical light-record compaction is not mandatory, and a safe documented no-go is valid when an optimization does not pay for itself.
- Draft PR #74 reconstructs the previously measured source-owned packing-revision/temporal-write design on `master@8c9e92458d1b08d8ff00f7c7874441433e63e5a9` without reviving the rejected frame-local hash/indirection representation.
- Frozen renderer/test source head `e028fd88b29aa2d0d82e4e04a09ea644bfa56670` passed all eight jobs in CI run 36047117838. The PF oracle ran 110 tests and the inherited deterministic baseline; Windows Visual Studio Debug/RelWithDebInfo, macOS Debug/Release, Linux GCC 12 RelWithDebInfo, Linux Clang 11 Debug and Linux Clang 15 Release all passed.
- The new deterministic/adversarial contract covers source reincarnation after freelist reuse, distinct equal-byte sources, repeated-source physical positions, packed-state mutation, light-class/group transitions, new PF-010 epochs, inherited portal epochs with foreign-group fallback, unsupported revision-zero fallback, mapped-buffer recreation, range bounds, and epoch/revision wrap/exhaustion fail-closed behavior.
- No GTX 1650 SUPER workload was launched in this pass. This is **not PF-017 acceptance** and PR #74 remains draft/unmerged. The remaining gate is final-source physical A/B performance plus image/state equivalence on the representative light-rich workload; if the benefit does not survive, the candidate must be restored/rejected rather than merged.
- PF-019 / #36 remains blocked until PF-017 is accepted or receives a complete no-go disposition.

## Current implementation gate

- **COMPLETED:** PF-001 / #18, PF-002 / #19, PF-003 / #20, PF-004 / #21, PF-005 / #22, PF-006 / #23, PF-007 / #24, PF-008 / #25, PF-009 / #26, PF-010 / #27, PF-011 / #28, PF-012 / #29, PF-013 / #30, PF-014 / #31, PF-015 / #32, PF-016 / #33, PF-018 / #35.
- **PHYSICAL GATE PENDING:** PF-017 / #34 has a completed material-lookup no-go and an off-GPU-qualified source-owned light-reuse candidate in draft PR #74. Source head `e028fd88b29aa2d0d82e4e04a09ea644bfa56670` passed all eight CI jobs in run 36047117838; final GTX 1650 SUPER A/B performance and image/state equivalence remain required before merge/acceptance.
- **BLOCKED:** PF-019 / #36 on PF-017 acceptance; PF-020 / #37 on all unfinished PF issues; SDVK-001 / #1 until PF-020 is accepted, merged, verified on `master` and explicitly records `SDVK-001: UNBLOCKED`.
- No planning-level blocker remains.

## Future implementation ledger rule

When a PF or SDVK gate issue merges, append a concise entry naming:

- issue/PR;
- merge commit;
- contract changed/frozen;
- verification artifact(s);
- dependencies newly unblocked;
- material residual blocker(s).

Do not record an issue as complete merely because a PR exists or CI ran; acceptance criteria and merge-to-master verification remain mandatory.