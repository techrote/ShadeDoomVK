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
- Five alternating production DBP37 MAP04 pairs on one GTX 1650 SUPER/driver/build configuration all launched and rendered. Identical read-only capacity instrumentation in four complete pairs measured 11,702,876 baseline versus 8,635,124 candidate logical bytes across the ten LevelMesh arrays (âˆ’26.21%); production exports independently repeat the vertex/surface reductions. MAP04 exercises setup allocation/growth, not moving AABB lines or a steady-state CPU gain.
- The targeted GLDEFS-light derivative exercises moving AABB lines. Direct fixed-tic RayTest input/fraction records match 1,630/1,630, production paused world pixels and oriented faces match, and five warm AABB pairs give 310.378 versus 159.175 ns per moved line median (âˆ’48.72%). Whole BeginFrame diagnostic medians are 20.129 versus 20.082 ms/frame (âˆ’0.23%, mixed pairs), so no material whole-path speedup is claimed.
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

### 2026-10-03 — PF-017 current-master integration before physical acceptance

- PR #74 original head `1e0fe5c8` is integrated with repaired master `2399d945`, preserving all 77 intervening commits and accepted CFX-009 neutral removed-slot publication/normal resource retirement. Semantic overlap review retains both PF and CFX evidence; renderer delta against master remains the PF-017 light candidate only.
- Full off-GPU requalification and a separate finite dense-light physical campaign precede any acceptance. Old source/CI/physical measurements cannot establish final integrated acceptance. See [final acceptance record](PF-017-FINAL-ACCEPTANCE.md).
- All historical STOP scopes remain sealed. #34 stays open and PF-019/#36 blocked until valid physical disposition, exact-head CI, merge and master verification.

- **COMPLETED:** PF-001 / #18, PF-002 / #19, PF-003 / #20, PF-004 / #21, PF-005 / #22, PF-006 / #23, PF-007 / #24, PF-008 / #25, PF-009 / #26, PF-010 / #27, PF-011 / #28, PF-012 / #29, PF-013 / #30, PF-014 / #31, PF-015 / #32, PF-016 / #33, PF-018 / #35.
- **FINAL NO-GO DISPOSITION:** PF-017 / #34 rejects/restores integrated light reuse after five physical pairs (+10.79% setup, +2.42% whole-frame); material indexes remain no-go. PR #74 requires exact-head CI/merge/master verification before completion. See PF-017-FINAL-ACCEPTANCE.md.
- **PF-019 READINESS:** #36 becomes dependency-ready after PR #74 no-go is merged and master verified; no PF-019 implementation begins here. **BLOCKED:** PF-020 / #37 on all unfinished PF issues; SDVK-001 / #1 until PF-020 is accepted, merged, verified on `master` and explicitly records `SDVK-001: UNBLOCKED`.
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
## 2026-10-01 - CFX evidence acceptance; PF-020 remains blocked

- CFX-005 / #92 capture evidence and scanner regression were reviewed and merged through PR #93 at `bc1c312691eef93daf9c512588bb14f31dca46d7` after 8/8 CI passed. Three GTX and three P400 target losses, two safe P400 controls and the native display-route discriminator are preserved. 135 raw artifact hashes were checked without mismatch.
- CFX-004 / #79's precise-blocker disposition is reviewed in PR #94, with six post-error CPU collision snapshots and 19 focused adversarial tests. Its master integration preserves both CFX-004 and CFX-005 forensic appendices; this entry does not predeclare the PR merged.
- No renderer repair, semantic change, workaround or new GPU launch is retained. #75 remains open on mapping the captured fault to the consuming shader/resource/submission and exact uploaded bytes/descriptor lifetime. Both physical lane budgets remain exhausted with STOP guards active.
- PF-020 / #37 remains blocked; no PF/SDVK release gate is lifted. The evidence acceptance does not establish application correctness or a driver defect.

### 2026-10-01 — CFX-006 accepted; bounded CFX-007 continuation authorized

- #95/PR #96 reviewed, 8/8 CI green at head `3b530c5cd28c78e76ffcac487b963f4886646509`, merged and verified on master `a6880fdb22e2f3d9ee85f3a86384b48ad7af9373`. Bounded query/resource identities accepted; initiating crash unresolved and PF-020/#75 remain blocked.
- #97/CFX-007 is a separately authorized causal continuation: at most 16 targeted launches and 6 correlated loss/TDR episodes, automatic recovery gate replaces routine human visual checkpoints. Historical six guards remain immutable; no old binary/old lane reopening. See issues/CFX-007.md.
### CFX-007 / #97 bounded causal result — 2026-10-02

PR96 accepted/merged mastera6880fdb precedes the separate owner-authorized GTX1650 SUPER protocol. All old STOP guards remain. Six source-led targets/ten controls consume16 launches and6 loss episodes; automatic recoveries pass, finite STOP active. Safe sync localizes independent LevelMesh INDEX_READ publication defect; candidate corrects both traversal paths and removes hazard with identical safe pixels/protected state, but selected DBP37 still crashes. Further one-factor GPUAV/sync, specialized pipeline and direct-LevelMesh-off tests do not yield sufficient repair. No three-success crash validation; #97/#75/PF020 remain unresolved. PR98 contains bounded tools, partial correctness repair and honest blocker/evidence, not crash closure. Next dependency-ready offline work is supported GPU address-to-resource/executed-pipeline attribution, followed by a separately authorized physical protocol if needed. See CFX-007-INVESTIGATION-NOTES.md and evidence/cfx007-attempts.json.

Subsequent offline continuation implements the opt-in address-binding callback/correlation discriminator. Windows build and52 focused CFX tests pass (compiled callback/query fixtures under MSVC ASan). Actual driver callback activation and newer-binary physical equivalence remain pending; no new launch, budget reset, closure or release-gate change. See CFX-007-ADDRESS-BINDINGS.md and evidence/cfx007-address-offline.json.

### 2026-10-02 — PR98 accepted substrate; CFX-008 #99 opened

PR98 all8 required checks green at0e07a1429939580e03b4201327161a08880ec54a; reviewed, merged and verified on master c6a7197ae48b8d163df9f72783c177ca427505f5. Capture substrate and independent LevelMesh vertex/index synchronization fix accepted; DBP37 causal defect remains unresolved. CFX-007 stays stopped16/6. Owner approved new CFX-008 two-launch/one-loss address-localization scope in #99, preserving all11 historical guards. Fresh merged Windows build, healthy baseline and61 MSVC-ASan CFX regressions pass. New safe activation control must pass exact callback coverage and image/protected-state gates before sole targeted DBP37 run. See CFX-008-ADDRESS-LOCALIZATION.md for live notes.

### 2026-10-02 — CFX-008 safe activation proved; complete-capture gate stops target

Safe control exits0, no loss/TDR, normal automatic recovery/caches restored. EXT address messenger/feature active,1714 binds1718 unbinds, identical1902×993 pixels/protected mesh vs earlier control006. Shared try_lock loses237 rows, so new scope stops1/0 before DBP37. All11 historical guards and new STOP retained. Offline bounded immutable-slot collector repair avoids callback file/mutex waits;65 MSVC-ASan CFX tests and Windows RelWithDebInfo build pass, including8000 concurrent copied callbacks and explicit stalled-drain coverage failure. Repaired hardware smoke/target localization still pending a separate approved scope. #99/#97/#75/PF020 remain unresolved; no crash fix or retrospective fault-address join claimed. See CFX-008 notebook/evidence index and PR100.

### 2026-10-02 — CFX-009 DBP37 source repair reaches physical saturation

- PR100/101 accepted masterc8c8cf6 precedes queued-capture localization. Original and same-binary matched retention-OFF targets fault frame7 at the startup lightmap interval retired frame6; diagnostic retention ON succeeds. Matching CPU mesh and actual SPIR-V negatives remain preserved. No unique executing shader, illegal dynamic descriptor access or NVIDIA defect is assigned.
- #102 / PR104 renderer3916 replaces removed previously published reserved light/probe descriptors with permanent initialized typed neutral views before submission and normal fence-controlled owner release. Existing constructor1×1 pair supplies the fallback; current atlas uploads/baking, dynamic descriptors, shaders, settings and retirement remain intact. Diagnostic lifetime retention stays opt-in and OFF for all candidate validation.
- Three independent exact former reproducer runs exit0, pass frame7/tic18/submission11, retire the same old8MiB interval normally and recover cleanly. Separate core/sync plus capture controls actually activate, report zero diagnostics and preserve exact pixels/protected state.106 focused CFX regressions pass under MSVC ASan; fresh Windows build and renderer-bearing head7de CI8/8 pass. Final evidence head is subject to exact-head CI/review/merge/master verification in PR104/#102.
- Physical validation is saturated3/3. Cumulative14 launches/2 earlier losses; all six candidate launches are loss-free. Old15 guards and stopped protocol results are immutable; final epoch closes with a saturation guard. Complete startup prefixes cover the former fault; later address-cap omissions are explicit. No redundant success or crash characterization launch follows.
- Primary repair acceptance does not close #75/PF-020 or reopen historical campaigns. DBP50/Sunlust/Champions lack shared-cause/disposition evidence; PF-020 still requires complete contract/RAG/regression synthesis and accepted freeze before SDVK-001. See CFX-009-CAUSAL-REPAIR.md and evidence/cfx009-neutral-descriptor-validation.json.

### 2026-10-02 — CFX-010 cross-case physical qualification saturated

- Accepted PR104/master `d0789c88f88049116022e7b904026cddeaba8ac4` is the pinned baseline. Preserved renderer source3916 and its EXE/PDB/runtime are unchanged; diagnostic retention OFF, normal retirement, no new renderer fix or workaround.
- Original DBP50 MAP08, separate v1.2 MAP08 and the full Sunlust MAP24/Champions movement/filter/reload route each complete **3/3 comparable independent processes**. Actual target attempts are3/4/5 respectively. Five safe controls plus12 targets total17 CFX010 launches, zero new loss/TDR. Three incomplete/host-confounded observations remain excluded and fully documented rather than treated as GPU failures or qualified successes.
- Every qualified target observes neutral removed-slot publication before successful fence/list release/old-atlas unbind, with complete flushed address callbacks through teardown. Generic resource tracing is a bounded startup prefix. Safe host controls verify protected scene state; the final v1.2 readback control has identical pixels. Sunlust's earlier safe comparison retains animated-region variation, not an exact-image claim.
- All18 previous STOP hashes remain unchanged. Final scope closes `QUALIFICATION_SATURATED`, carried CFX009+CFX010 counts31/2 (two prior losses; not programme-wide counts), with a new saturation STOP and closure proof. Physical testing ends at three successes per case. PR106/#105 report/tooling is accepted: PR #106 merged as `2399d9455772c570e597a5960c626f3bf771baeb` after exact-head 8/8 CI and independent evidence/report review; CI itself supplies no GPU evidence.
- Practical current-build coverage is demonstrated without shared-mechanism or isolated PR104 attribution. Historical content/config/cache/layer gaps and untested P400 repair coverage remain explicit. Parent #75/PF020 stay open for comprehensive synthesis/contract freeze; no SDVK feature or NVIDIA submission follows. See [CFX010 report](CFX-010-CROSS-CASE-QUALIFICATION.md) and [matrix](evidence/cfx010-cross-case.json).

### 2026-10-03 — PF-017 integrated candidate rejected; complete no-go proposed

- Exact candidate `8a9a3dcb` integrates repaired master `2399d945` and passes 254 CPU/ASan tests plus CI run37090637554 (8/8) before GPU use. Five complete serial alternating production pairs all regress setup; pooled +10.79% setup and +2.42% whole-frame, above preregistered 2% frame threshold. Five full images match exactly.
- Complete candidate source/tests restored: final src/libraries/wadsrc/tests/workflows match repaired master byte for byte. CFX neutral removed-slot descriptor publication, normal retirement, diagnostics and validation contracts are preserved. Material lookup remains linear/no-go; optional default sharing not worthwhile.
- Fifteen total launches across preserved host/protocol/measurement scopes, zero new loss/TDR/health anomaly. Baseline-only diagnostic metadata failure stops all further physical launches; CPU ASan proves added identity vectors were not cleared. Candidate counters/source/range/packed checkpoints remain unmeasured, so full candidate physical correctness is not claimed. No optimization is retained. All old STOPs stay sealed; CFX/PWAD campaigns are not reopened.
- Restored-source full suite 245/245 passes without skips; deterministic oracle repeat exact. Complete raw timing distributions, source/build/workload/health/image hashes, private inventory and independent offline audit are in [final report](PF-017-FINAL-ACCEPTANCE.md). Final exact-head CI, PR #74 merge and master verification receipts govern #34 closure and PF-019/#36 readiness. PF-019 is not started; #75/PF020/SDVK gates remain unchanged.


### 2026-10-03 — PF-019 dormant-resource candidate qualified off-GPU; merge gate pending

- PF-019 / #36 baseline is accepted `master@844462c3a4ed5f7037ade1b49d1a28f578077213`. Source proof confirms the tiled-light producer has no active accepted consumer: draw-info dispatch is commented and the LevelMesh fragment path forces `uLightIndex = -1`.
- Candidate branch `pf-019/dormant-resource-cleanup` introduces one explicit `VkLightTilePolicy::Enabled` seam, false by default. The dormant configuration skips six Z-min/max images, tile/Z-min-max descriptor resources and per-frame rewrites, five dedicated shader compilations and four dedicated pipeline creations. The preserved LevelMesh binding 4 receives one valid `LightTileBlock` placeholder.
- At the representative PF-017 1904x1001 output, inherited source formulas account for 5,241,600 bytes of RG32F Z-min/max texels and 622,080 bytes of tile storage. The candidate retains 1,296 bytes and avoids **5,862,384 bytes** before allocator overhead for that screen render buffer. This is a deterministic allocation/work claim, not GPU wall-time or heap-residency evidence.
- PF-006 ordered key maps are unchanged because no representative lookup evidence justified a hash conversion. No shader arithmetic or worker-queue candidate is retained; no additional ambiguous resource is gated.
- `PF-019-PERFORMANCE-REVIEW.md` plus the compiled policy/source-contract fixture own the disabled/enabled sizing and preservation proof. No physical GPU campaign is opened: the retained change removes only source-proven unconsumed producer work and leaves shader/material/quality state unchanged.
- Final PF-019 acceptance is **not yet recorded here**. Exact-head CI, PR review/merge, verified post-merge `master`, final ledger receipt and #36 closure remain mandatory. PF-020 / #37 is not started.

### 2026-10-03 — CFX-000 final synthesis

- Live reconciliation advances the synthesis base to `master@44864d9d27495d3992d3a7314f4cb7de6c029b7b`, the PF-019 / PR #107 merge. Source review confirms the accepted CFX removed-slot neutral publication path remains present. #36 is separately open pending PF-019 post-merge master verification; this CFX task neither accepts PF-019 nor starts PF-020.
- DBP37 primary acceptance remains 3/3 exact former-reproducer success with retention OFF, normal startup atlas retirement, matched safe/core/sync controls and the removed-slot neutral descriptor publication repair. The unique executing shader/SASS, illegal dynamic access, exact submitted GPU bytes and a unique NVIDIA defect remain unproved.
- CFX-010 final accepted state is three qualified successes each for original DBP50, separate v1.2 and full Sunlust/Champions, across 17 processes total (five controls, twelve targets) and zero new loss/TDR. The three excluded host/capture observations remain excluded.
- P400 repaired-build qualification was not performed. The historical P400 lane is saturated at three target losses and materially different reported signatures; this is a residual limitation, not a repaired claim and not a reason to reopen physical testing.
- [Final human synthesis](CFX-FINAL-PROGRAMME-SYNTHESIS.md) and [machine matrix](evidence/cfx-final-incident-matrix.json) audit all six #75 criteria as PASS. Closure still requires the synthesis change's own fresh post-reconciliation non-GPU CI, independent review, merge and master verification.
- CFX is not an independent PF-020 blocker after synthesis acceptance. PF-020 remains subject to PF-019's separate completion receipt and then its own full freeze contract. #103 remains a downstream owner/vendor decision because no NVIDIA defect is established.


### 2026-10-03 — PF-019 accepted and merged

- PF-019 / #36 implementation/evidence head `e496977a47ebb7a4235dba28a7df11128780b0eb` passed required CI run `37108111799` 8/8 and merged through PR #107 as `44864d9d27495d3992d3a7314f4cb7de6c029b7b`.
- The exact merge commit passed post-merge push CI run `37108571879` 8/8. Later current `master@41daecc2a2cf62d674163a0bb3dc5481c8be37b1`, after CFX final synthesis, also passed push CI run `37109278147` 8/8; the intervening synthesis changed documentation/tests, not PF-019 implementation source.
- Accepted change: the source-proven dormant Z-min/max/light-tile producer is gated behind `VkLightTilePolicy::Enabled`, false by default, while LevelMesh descriptor binding 4 remains valid through one 1,296-byte block and the complete producer path remains available for SDVK-009 reactivation.
- At 1904x1001 the source formulas avoid 5,862,384 bytes of Z-min/max/tile payload before allocator overhead, plus five dormant shader compilations, four dedicated pipeline creations, seven dedicated descriptor-set allocations and nine per-frame dedicated descriptor writes.
- PF-006 ordered maps, scene-shader math, worker queues and ambiguous resources are unchanged because no representative evidence justified speculative changes. No quality policy changed and no physical GPU campaign was required or opened.
- PF-019 is complete. CFX-000 / #75 is also accepted/closed through PR #108 on current master. After #36 tracker closure, PF-020 / #37 has no remaining external PF/CFX prerequisite; it becomes dependency-ready for its own fail-closed freeze synthesis. SDVK-001 remains blocked until PF-020 itself passes and explicitly unblocks it.


## PF-020 independent GLDEFS repair — 2026-10-04

[#114](https://github.com/techrote/ShadeDoomVK/issues/114) isolates the four-line
custom-texture default-slot repair and strict native CPU helper migrations from
the blocked synthesis. The exact original parser retains both counterexamples;
the focused tree passes272/272 native PF tests, four strict standalone fixtures,
CFX8/8 and deterministic oracle equality. No GPU/visual/performance claim or
PF-020/SDVK-001 acceptance follows. See [repair](PF-GLDEFS-SAMPLING-REPAIR.md) and
[compact verification](PF-GLDEFS-SAMPLING-VERIFICATION.json); required exact-head
CI, merge/master and post-merge verification govern independent acceptance.

Final independent release acceptance: exact head `5c3b2895888e5af18fac5a51e4e0988fe5a88fa4` passed all eight actual jobs in [run37183408191](https://github.com/techrote/ShadeDoomVK/actions/runs/37183408191). PR #115 merged as `3f37b63a4fdfb4c95421db951cf81682b5eb92c9`, verified on remote master, and all eight exact merge-push jobs passed in [run37184391659](https://github.com/techrote/ShadeDoomVK/actions/runs/37184391659). [Acceptance comment](https://github.com/techrote/ShadeDoomVK/issues/114#issuecomment-5977683648) records independent exact-head review and closure. The earlier compact verification remains measurement-time history with its original pending integration limits; it is not rewritten as a release receipt. Full PF-020 remains separate and blocked.

## Independent #110/#112 material correctness candidates — 2026-10-04

This focused preparation is based on accepted GL master `3f37b63a4fdfb4c95421db951cf81682b5eb92c9`. It preserves the accepted GLDEFS repair and does not publish a PF-020 freeze, probe contribution decision, optimization or gameplay/quality change.

The candidates provision public indexed materials with canonical-remap R8 plus an owned real base-palette row, complete non-mip sampled transitions, and declare the actual READ/GENERAL layout at material descriptor publication. Ordinary materials, async uploads, palette/RedIsAlpha and existing SWCanvas ownership remain protected. See [#110 source and acceptance notes](PF-110-IMPLEMENTATION-NOTES.md) and [#112 layout notes](PF-112-IMPLEMENTATION-NOTES.md).

Historical candidate4/source890 retains twelve normal mode/filter packets: 4,828 assertions across 316 cases, 252 decoded presentation ROIs, separately proved core/synchronization validation with zero errors/warnings, and independent 737,280 indexed-pixel recomputation with zero mismatch. [Compact normal verification](PF-110-NATIVE-MATRIX-VERIFICATION.json) preserves exact source/build/input identities and the mode1/SW-retirement/performance limits.

The original genuine-restart attempt remains FAIL: GPU initialization occurred, the terminal package guard rejected startup argv before its raw BEFORE command or actual restart, and engine exit 0 did not pass the enclosing runner. [Retained attempt](PF-110-RESTART-RETAINED-ATTEMPTS.json) is unchanged. Frozen newer source `bd2586f51c456fcdb9d04e616a6facf30d47a5ec` repairs only the guarded diagnostic pair-removal seam; historical candidate4 success is not reattributed to it.

Status: **native verified repair; integration tracked in the source issues**. Candidate5 clean build, normal/restart and strict CPU qualification pass below; exact-head CI, review, merge/master and post-merge integration are tracked in the source issues. The coordinator will append those final receipts separately; PF-020/#37 and SDVK-001 remain outside this focused acceptance.


## Verified candidate5 native qualification

The final clean candidate passes all twelve normal mode/filter cases and both
genuine one-process core/sync restarts, with zero requested-validation errors or
warnings, unchanged pins and all294 presentation ROIs. Strict PF393/393, four
standalone contracts, CFX8/8 and deterministic source oracles pass.
See [source and acceptance scope](PF-110-IMPLEMENTATION-NOTES.md) and
[compact independently reviewed qualification](PF-110-FINAL-NATIVE-VERIFICATION.json) for hashes, methods,
retained failures and unmeasured mode1/SW-retirement/performance limits.
Focused release integration is tracked in #110/#112; PF-020 and SDVK-001 remain
separate blocked gates.


## #110/#112 accepted material/layout repair — 2026-10-04

PR #116 passed independent review and all eight exact-head jobs at `9df93b6d`,
merged as `1524686e77f1e89dabfb044bf757a2d19566c31c`, and passed all eight
post-merge push jobs after remote master/ancestry verification. #110/#112 are
closed. [Release receipt](PF-110-RELEASE-ACCEPTANCE.json) links the retained
source/native qualification and immutable original failures.

The separate #113 repair continues from this master with a reviewed explicit
zero-IBL/LOD0/NonUniform decision and independently verified strict CPU original
negative. Guarded production/native acceptance remains pending. PF-020 and
SDVK-001 remain blocked; no historical CFX/PF-017/P400 or performance gate is
reopened or inferred from these results.


## #113 guarded probe repair native-qualified — 2026-10-04

Runtime source `a113e2bc1644fe5e7e9079b49ef67308f83eecff` passes a fresh
source-pinned Vulkan build, strict PF440/440, CFX8/8, four standalone contracts
and deterministic oracles. Two serialized GTX1650SUPER core/sync processes
pass23,603 checks and12 private controls each, actual missing→published scene
command/uniform observations and zero Khronos validation errors/warnings.
Independent source/build/package closure, raw float mathematics and18 retained
SPIR-V validations pass. Loader notices and early622×433/later640×480 extents
are explicitly recorded. See [scope](PF-113-IMPLEMENTATION-NOTES.md) and
[compact measured qualification](PF-113-FINAL-NATIVE-VERIFICATION.json).

First build and CPU-wrapper failures remain immutable with their dispositions.
PR#117 final review/CI and verified merge/master/post-merge integration remain
pending. This qualification does not accept PF-020/#37, SDVK001, performance,
human visual approval, P400 or historical CFX/PF017 gates.


## #113 accepted; PF-020 synthesis resumed — 2026-10-04

PR #117 final head `c37c2d6132a86299f674de5c4126402311b5e1d2` passed
independent review5405434084 and all eight jobs in run37193338914. Merge
`7d29c7e4d64d61dba05524d9e7f5711ffd915d90` is verified on remote master,
with exact engine/tool equality and all2,535 frozen inputs bridged. Exact
post-merge run37194078630 passed all eight jobs; #113 is closed.
[Release acceptance](PF-113-RELEASE-ACCEPTANCE.json) preserves bounded
native results, original failures and unmeasured performance/visual/P400 limits.

The serial PF-020 coordinator resumes `codex/pf020-native-freeze`, preserving
old checkpoint54e9a1b3 through reconciliation204c666ba with accepted master.
Its full strict PF440/440, CFX8/8, four standalone contracts and identical
oracle repeats pass. A recorded checkout line-ending disposition preserves
measured raw bytes; no renderer program or committed source content changed.
Canonical/RAG reconciliation and final-source aggregate/equivalence review
continue. PF-020 is not accepted; SDVK001 remains blocked. Earlier pending
PF017/material/probe ledger entries are dated historical snapshots, not
current work directions. Historical STOP/saturation scopes remain sealed.

## PF-020 ordinary Dense packet — 2026-10-04

Tool/source checkpoint `ef79361822199112ee2179414ce21b812178bca7` passes the
clean strict PF480/480, four standalone fixtures, CFX8/8 and identical oracles.
Its engine content remains accepted master7d29. Two fresh warmups and five
alternating ordinary Dense pairs complete on GTX1650SUPER:40 scored CPU
snapshots, actual fixed camera/count/settings/input proofs and five exact RGB
image pairs,9,529,520 pixels/zero mismatches. The first notification-bearing
warmup remains rejected/unscored with its original raw PASS receipt intact.
[Protocol](PF-020-ORDINARY-DENSE-PROTOCOL.md),
[retained disposition](PF-020-DENSE-RETAINED-ATTEMPTS.json) and
[measurement packet](PF-020-DENSE-MEASUREMENT.json).

Candidate sprite Setup is higher in all five pairs: median paired+3.91%,
range0.86–13.73%; CPU All including Finish/wait median+1.15%,
range0.003–7.98%. All samples remain; cause and performance acceptance are
unproved. Independent raw-packet audit passes. All includes Finish/wait;
elapsed timers can include preemption, and the pair4 All sign is below printed
precision. All eight exact tool-head CI jobs pass in run37196660221. These
checks do not accept the freeze. Profile before optimizing. No GPU timestamp/budget, PBR/indexed
cost, packed-light state, key/cache, sprite-emission or offscreen-view parity
follows. PF020/SDVK001 remain blocked; no historical STOP lane is reopened.

## PF-020 CPU capture and view evidence preparation — 2026-10-04

Two fresh unelevated native Dense diagnostic children complete with named CPU
recordings, normal exits and successful owned stops in capture05. Independent
named/default WPR status is idle. Only the fixed catalog-verified profiler
controller was elevated under explicit owner permission; configuration/policy
was not changed. Original denied/cancelled/parser-failed attempts remain retained.
The [manifest](PF-FREEZE-MANIFEST.md) pins both ETLs. Zero scored samples are
added. At capture time decoded coverage was pending; its separate bounded
disposition is recorded below. CPU cause/performance acceptance remains unproved.

The [view protocol](PF-020-VIEW-EVIDENCE-PROTOCOL.md) records the opt-in actual
scene/sprite observer, private same-format camera/probe sampling, production
key/cache recording and strict source-derived original seams. These engine
additions require their own fresh builds/native proof; earlier480/accepted-build
receipts do not validate them. Fixture placement and CPU controls are preparation,
not actual linked/mirror/camera/probe/user-shader traversal or image equivalence.
PF020/SDVK001 stay blocked; draft111 remains ineligible to merge as a passing freeze.

The owner reported concurrent CPU spikes from slicing and requested specific
extreme-test reruns after it finished. [Targeted recheck](PF-020-DENSE-TARGETED-RECHECK.json)
repeats both sides of original pairs3/4/5 once:8 physical children including2
unscored warmups,24 scored CPU snapshots and three exact image/state pairs.
Sprite Setup differences are−0.90%,+1.05%,+1.07%; total including Finish/wait
is+1.28%,−0.77%,−0.62%. The large spikes did not recur. Original samples and
failed quiet preparations remain retained; no replacement aggregate, causal
attribution, statistical significance or performance/GPU acceptance follows.

## PF-020 bounded CPU decoding and capture-time state repair — 2026-10-04

The separate v4 decoder changes only its4M event cap to32M and passes both
capture05 traces with zero loss/truncation,99.963%/99.970% target stacks,
100% resolved engine frames and exact recorded target/module/PDB identities.
Actual decode resources and owned exits pass. Whole-lifetime sprite light-list
samples do not provide phase boundaries, a timing cause or performance
acceptance. The [public metadata receipt](PF-020-CPU-PROFILE.json) preserves
the original capacity failures and an unexercised wrapper cleanup limitation.

Frozen50a4b554 passes all570 strict PF tests, CFX8/8, four standalone fixtures,
identical oracles and all eight exact-head jobs. Fresh current build02 succeeds
after the public nested texture-manager enum scope was corrected; failed build01
is retained. Review identifies a separate qualification gap: first semantic
scene rows need not describe a later captured producer invocation. The observer
now retains its actual completed view, and the ordinary screenshot readback
retains corresponding RGB/state. These additions and the bounded launcher need
fresh frozen-head builds and real core/sync, traversal/cache/image verification.
PF020/SDVK001 and draft111 remain closed to passing-freeze acceptance.

## PF-020 first native launcher qualification — 2026-10-04

Frozen observer head41c63ff passes clean PF605/605, CFX8/8, four standalone
fixtures and identical oracles; both exact-source current/original-seam native
builds03 pass. First core packet01 launches one real medium, unelevated GTX
child and exits0, but fails its observer/fixture gate. The actual screenshot
shows the title sequence, no frontend scenes/sprites were observed, and the
Vulkan dump rejects unequal Windows argv and console prefix representations.
All outputs/inputs and the original runner/builds remain retained as failed
qualification; no second child or image equivalence is claimed.

The source-backed launcher repair uses early `+map`, a consistent console-safe
prefix, and `+logfile` for actual startup capabilities. Actual queries remain
mandatory for every requested setting; the six built-ins declared with flags0
are required absent from the normal-exit INI, while archived settings retain
exact values. Corrected retries get fresh packet/cache directories and verify
every sealed engine/build input. Reviewed RAG candidate/integration prose is
marked historical or reconciled to accepted PR116; completed CPU decoding no
longer appears as pending work. PF020/SDVK001 remain blocked.

## PF-020 fixture reached, strict diagnostic failure retained — 2026-10-04

Clean launcher/tool head1be5127 passes PF609/609, CFX8/8, four standalone
fixtures, identical oracles and all eight exact-head jobs in run37214800451.
Core packet02 launches only its first unelevated GTX child against frozen41c63
build03. The actual map, both camera outputs, six probe faces and main screenshot
complete; core validation reports zero errors/warnings, actual pipeline-library
support is recorded, and the renderer exits0. Strict scene JSON decoding fails
because byte-sized frame0 was streamed as a raw NUL. No paired, synchronization,
generalized or freeze acceptance follows. All failed outputs remain unchanged.

The observer converts the actual uint8_t frame to a JSON number. Compiled guards
use that real byte type in both source variants. The parser retains EFF_NONE=-1
only in SpecialEffect and validates the complete production shader cache key
(type/SHA1/final-source-size), rather than demanding a bare SHA1. Source edits
require fresh frozen exports/builds and fixture identities before the next
native attempt. PF020/SDVK001 stay blocked and PR111 stays draft.

Repaired source0791911 then passes clean PF612/612, CFX8/8, four standalone
fixtures and identical oracles; fresh exact-source native builds04 both pass
with source exports and regenerated fixturev5 sealed. A reviewed tool guard
compares nonempty full production shader-binary key sets including all actual
null-scene/worker lookups, independently of access counts and hit outcomes.
This supplements native semantic shader/pipeline partitions. Fresh paired
core/synchronization and supported generalized proof remain pending.

Clean tool4997491 passes PF613/613, CFX8/8, four standalone fixtures and
identical oracles. Core packet03 reaches strict scene/key/image acceptance for
its first unelevated GTX child, with zero core validation errors/warnings and
normal exit, but rejects the event file's forward-slash prefix versus Windows
Path string spelling. All six actual load/save records and failed outputs stay
unchanged; no later child launches. The tool now uses exact private artifact
Path/link/size validation and event-file identity, preserving cache lifecycle,
hashes and positive warm evidence. New native qualification was required at that
historical checkpoint.

### 4 October 2026 — bounded native proof and final-source host blocker

Runtime569/source export07/builds07 qualify fresh default Core06/SYNC01 and
supported Uber/library Core01/SYNC01, with16 actual medium/unelevated exits0,
zero requested validation findings, exact cold/warm260 semantic rows,eight actual
producer images/main RGB,37 specialized/115 Uber binary keys and455 Uber family
identities. Every Uber child completes304+37=341 workers/publications. Independent
raw/image/source/build and generic-program/family review passes within bounded
scope. [Exact successful and retained failed identities](PF-020-VIEW-MEASUREMENT.json).
Clean tooldf667 checks15 pass PF644/644, CFX8/8, four compiled contracts, identical
oracles and all eight exact-head hosted jobs.

[Final Dense attempts](PF-020-FINAL-DENSE-CHECKPOINT.json) retain FAIL prelaunch
quiet maxima31.51% and28.61% against15%. After a separately recorded readiness
PASS, one explicitly fresh attempt runs two actual healthy/no-overlay warmups;
both images are agent-inspected and exact. One baseline scored child validates
four retained scores, but no current scored child or complete pair exists. Source/
input/package/STOP closures remain exact; all5 packages authenticate4,746 source
members with550 exact text newline projections and no arbitrary binary transform.
No final performance/aggregate acceptance, cause, GPU time or human approval is
inferred. No further physical campaign this session. Finish final focused docs/
checks and durable stop record; PF020/SDVK001 remain blocked and PR111 draft.

### 5 October 2026 — complete final-source CPU comparison and aggregate disposition

Sealed FinalDense03/04 remain FAIL at strict quiet preparation, retaining16/12
scored snapshots and all completed logs/images/state. Revision2 at clean pushed
`ad8d68072074ac1e621474c108c0c5e4a1b8e207` permits one continuous30–120-interval
settling observation, preserving the strict15%/ten-consecutive predicate, every
reading/raw delta, fixed scoring and rejection before native launch. Independent
source review and23 focused controls pass, including failed-observation retention.
Checks18 pass PF651/651, CFX8/8, four compiled contracts and identical oracles;
all eight exact-head jobs pass in run37252799838. Native runtime569/build07 is
unchanged. No source/quality/host-setting waiver or old receipt relaunch occurs.

[FinalDense05](PF-020-FINAL-DENSE-MEASUREMENT.json) passes12 medium unelevated
exits0,60 raw blocks/40 retained scores and five exact image/state pairs with
9,529,520 pixels/zero mismatch. Both actual warmups are inspected. All360 raw
CPU intervals verify; every readiness observation finishes at30, maximum final
ten11.711711711711711%. Independent raw audit rehashes84 output files, parses
all60 blocks and independently decodes all12 PNGs. Before/after closure is exact.
Mean of paired CPU medians is18.3481→18.2598ms All including Finish/wait,
3.6660→3.6319ms full Setup and3.6243→3.5910ms Sprite Setup; pair signs are mixed.

[Independent aggregate disposition](PF-020-AGGREGATE-DISPOSITION.md) satisfies
B4 within the owning contract's bounds. Original adverse40, selected24, complete
whole-lifetime CPU profiles and all failed/partial packets remain separate and
unchanged. Bounded PF005/016/018/019 benefits and PF017 restoration are retained;
no universal speedup/no-regression/zero-overhead, phase cause, GPU performance
or human approval claim follows. Final publication-head source/canonical/checks,
independent review, CI and verified master integration remain required before
PF020 closure/SDVK001 permission. No SDVK001 implementation is included.

### 5 October 2026 — verified PF020 release / SDVK001 unblocked

PR111 merged as `e185e60b04fe37ec84a18c5a85eec6722b541b71` after clean publication60d8 checks19
(PF651/651, CFX8/8, four compiled contracts and identical oracles), independent
exact-head raw/canonical/source/aggregate reviews and all eight actual final-head
jobs in run37256093249. Authenticated remote master, runtime/publication ancestry
and exact whole-tree equality are verified. All eight exact merge-push jobs in
run37256839102 and clean full merge-head checks20 pass.
[Release receipt](PF-020-RELEASE-ACCEPTANCE.json) pins source/check/review/CI and
retains native/CPU evidence plus every historical failure/adverse finding.

**PF020: ACCEPTED, MERGED AND VERIFIED. SDVK001: UNBLOCKED.** This is the bounded
freeze gate, not a universal performance/GPU/human/P400/broader-mode claim or
implementation of a founding feature. The followup changes acceptance records
only and preserves every runtime input. No further CPU campaign or human action
is required by the current evidence.

### 7 October 2026 — SDVK-001 foundation implementation

SDVK-001 / #1 consumes verified PF-020 master `f21fe672cb54c8db3dca8977822d7697493c71ff`.
The primary `C:/ShadeDoomVK/source` checkout was fast-forwarded and a dedicated
`sdvk-001-foundation` branch created; historical PF checkouts/builds/evidence
retain their original identities. [Foundation contract](SDVK-001-FOUNDATION.md)
records project `0.1.0-dev` identity separately from inherited content/config/
save/protocol identifiers, per-build Git metadata and early `--version` diagnostics.
[Build instructions](../BUILDING.md) and shared CPU/dependency/identity helpers
reconcile the Windows/Linux path with the eight-job inherited CI matrix.

Release acceptance and SDVK-002/003 readiness require the foundation PR's passing
checks, merge and verification on master; they are not inferred from this
implementation entry. The issue/release record must pin those completed gates.

### 7 October 2026 — verified SDVK-001 foundation acceptance

PR #119 merged as `7f34f15827f3cc98685d1af303d212ed5edc2b47` after clean publication
`498acdeb7650161215049eeab8bfebdc1f13aed9` passed 665 local tests, CFX 8/8, four
compiled contracts, identical oracle outputs and all eight hosted jobs in run
37636588993. The actual CI checkout's tree equals that publication. Authenticated
remote/local master integration and exact merged-tree equality are verified;
all eight exact merge-push jobs in run37638506103 also pass. The documented fresh
Windows build and both merged-master executable identity checks pass.

[Foundation release receipt](SDVK-001-RELEASE-ACCEPTANCE.json) pins commits, jobs,
logs and retained Windows artifacts. Actual startup checks exposed and repaired
missing versioned names in the authenticated ZMusic archives and a pre-main
macOS `FStringData` aligned-allocation failure. Native debugger and failing/
passing production-method controls remain traced. Project diagnostics preserve
founding/PF lineage; compatibility-sensitive identifiers and notices remain intact.

**SDVK-001: ACCEPTED, MERGED AND VERIFIED. SDVK-002/003: UNBLOCKED.** This
foundation adds no renderer feature or upstream engine import. PF's historical
qualification/performance limits remain unchanged. Acceptance-documentation
integration follows ordinary PR/check/merge discipline and changes no runtime.

### 7 October 2026 — SDVK-002 observability implementation and qualification

SDVK-002 / #2 starts from verified foundation master
`a2d2d293d680895bb8daae86466596b05aaef483` on a dedicated branch. The
[observability contract](SDVK-002-OBSERVABILITY.md) describes eleven deterministic
scene recipes over eight classes, nineteen retained CPU contracts, bounded
native state/timestamp collection, fixed-camera capture, paired state/image
comparison and raw-sample benchmark receipts. Existing PF generators, negative
fixtures, native control protocols and historical failures remain preserved.

Independent review added explicit negative controls for record-order loss,
ambiguous parent labels, partial per-frame coverage, missing material state,
incorrect sampler/resource identities and fabricated workload/readback claims.
The local software Vulkan capability probe succeeds; this container rejects
Unix socket creation before Xvfb can start, so it cannot supply a display-based
native capture. The hosted software Vulkan lane is the documented runtime path.

This entry records implementation progress, not acceptance. Current-head checks,
native corpus comparisons/baseline, PR merge and verified master must be recorded
before issue closure or dependent SDVK-004/006/009/014 readiness changes.

### 2026-10-07 — SDVK-003 upstream maintenance checkpoint (not accepted)

- SDVK-001 / #1 confirmed closed and accepted; SDVK-003 began from `master@a2d2d293d680895bb8daae86466596b05aaef483`.
- Pinned VKDoom, UZDoom and GZDoom heads and examined representative compatibility/build deltas; full cross-lineage differential is **pending**, and cross-repo UZDoom compare to the VKDoom founding commit returned 404.
- Adapted two UZDoom Crusader target-null guards on dedicated SDVK-003 branch; no broad upstream merge, renderer modification or native GPU run.
- Created bounded differential/ownership policy and donor entry; full regression verification, review, CI/merge and final acceptance are still required. #3 remains open; SDVK-004/009 remain dependency-blocked.

### 2026-10-08 — SDVK-003 differential acceptance candidate

- Reconciled PR #122 onto current master `1ecc3cf73aa2266a1e741f09078b7d089ba8bf89`; the branch preserves SDVK-002 observability/source-evidence infrastructure.
- Complete untruncated recursive-tree comparison pins VKDoom/UZDoom/GZDoom/recipient commits and tree SHAs. Relative to founding VKDoom, UZDoom records 8260 added/3193 deleted/1530 modified blobs and GZDoom 1331/197/697; exact domain counts and overlap paths are checked in as machine-readable evidence.
- 86 recipient-owned paths overlap UZDoom and 79 overlap GZDoom; renderer/shader overlap is fail-closed. No PF/CFX supersession is claimed and no renderer donor code is imported.
- The representative UZDoom Crusader adaptation is bounded to two null-target guards and has a focused CPU/source regression. Root-license and named asset-exception scope were audited; no asset/binary/dependency import is present.
- Final acceptance requires exact final-head hosted checks, PR merge and post-merge master verification. No physical GPU run is required for this non-renderer import.


### 9 October 2026 — SDVK-002 accepted after fresh-process reproducibility repair

- Substantive PR #121 merged as `1ecc3cf73aa2266a1e741f09078b7d089ba8bf89` after complete observability/corpus/benchmark qualification.
- A later acceptance-document run retained a fresh-process `shadow-boundary` comparison failure rather than waiving it. Investigation proved allocator-local selected shadow row numbers and a coincident player/fixed-camera sprite-rotation ambiguity.
- Repair PR #124 head `584dc4f1f3450069bd5b9679cd2aef2703c1e399` preserves rejection/aliasing/semantic state, normalizes only selected frame-local row identity and moves the generated player start behind the fixed camera. Exact-head source evidence run `37848620578` and CI run `37848620479` passed; all nine CI jobs were green.
- PR #124 merged as `a05743fb428c0d7c66defccfb577834d012b4e31`. Exact post-merge Renderer source evidence run `37851016448` and Continuous Integration run `37851016492` passed. The software-Vulkan lane completed two captures plus comparison for all eight authored workloads, including the repaired shadow boundary, and the three-process timing baseline passed.
- Historical failed packets remain retained. Software Vulkan is correctness/repeatability evidence, not physical-GPU performance acceptance.

**SDVK-002: ACCEPTED, MERGED AND VERIFIED. SDVK-004/006/009: dependency-ready subject to their remaining declared dependencies.**

### 9 October 2026 — SDVK-003 upstream policy accepted and gate reconciled

- Exact final PR #122 head `cbc8fa1601123e595483a2ab5d8f9997c36c0768` passed Continuous Integration run `37846204348` and Renderer source evidence run `37846204325`.
- PR #122 merged as `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`; the bounded Crusader guards, complete pinned donor differential, ownership/conflict policy, provenance and regression evidence are present on current master.
- Current `master@a05743fb428c0d7c66defccfb577834d012b4e31` is a descendant of the SDVK-003 merge and passed source evidence run `37851016448` plus all-nine-job CI run `37851016492`.
- No renderer donor code or physical-GPU claim is introduced by SDVK-003. PF/CFX ownership vetoes remain authoritative.

**SDVK-003: ACCEPTED, MERGED AND VERIFIED. SDVK-004/009: upstream-policy dependency satisfied.**


### 9 October 2026 — SDVK-006 renderer visual-time implementation candidate

- Reconciled from `master@c8b6db4dedae5da27249b6738f7628cf3a41b80a`; #6 had no prior branch/PR/comments. Dedicated branch `sdvk-006-render-visual-time` records design before production changes.
- Added a deterministic renderer clock with 0.2 s long-stall bound, explicit first/repeat/rollback/non-finite/pause/resume/load/wipe/cut states, accumulated applied visual time, generation and validity diagnostics. Production samples an unscaled `steady_clock`, not Doom tic time or `TimeScale`.
- PF-010 MainView is the only clock owner. Stereo siblings and MainView portals read the same snapshot; camera textures, probe faces, save pictures and non-main portal descendants receive invalid fallback state and cannot advance/reset the next main delta.
- Added default-off `RF2_INTERPOLATESCALE`/`RF2_INTERPOLATEALPHA` presentation flags, exact endpoint/finite handling and existing `RF_DONTINTERPOLATE` precedence. Authoritative actor values/tic advancement/demo/network/save semantics are unchanged.
- Added UI-only render-time script access, SDVK-002 `visual_time` diagnostics and deterministic CPU/source contracts. The standalone state-machine fixture was compiled with C++17 warnings-as-errors before publication.
- MAD-VKDoom timing/interpolation commits were reassessed and minimally adapted; the donor global clock/minimum clamp and unrelated animation systems were not imported.

This is an implementation/qualification candidate, not acceptance. Required next gates are complete `tools/check.py`, hosted software-Vulkan/native identity, full exact-head PR CI, merge, exact resulting-master verification and final #6 acceptance record.

### 9 October 2026 — SDVK-006 live-master reconciliation after SDVK-004

SDVK-004 / PR #126 merged independently as `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b` while PR #127 was qualifying. #6 was reconciled onto that exact master without taking descriptor/material-stress ownership. The only overlapping path was `rag/11-RENDERER-OBSERVABILITY.md`; both SDVK-004 pressure-observation reuse and SDVK-006 visual-time observation/comparison policy are retained. All SDVK-004 renderer-oracle corpus/prepare/run changes remain from master. Exact-head qualification is restarted on the reconciled merge head.


### 9 October 2026 — SDVK-004 rich descriptor lifetime accepted and SDVK-005 unblocked

- SDVK-004 / #4 started from verified `master@c8b6db4dedae5da27249b6738f7628cf3a41b80a` after SDVK-002/003 acceptance.
- The focused implementation retained PF-002/PF-003 resource identity and fixed one demonstrated failure path: an impossible positive bindless span could grow exact-size free-bucket storage before proving that span could fit. The accepted guard rejects spans larger than the entire configured dynamic range before bucket sizing; normal exact-size reuse, generation/epoch semantics and allocator architecture remain unchanged.
- Deterministic qualification holds 576 material variants plus 64 probe pairs, reaches 3,072/4,096 dynamic descriptors (75%), performs 64 repeated canvas/palette/PBR recycle cycles, full descriptor rebuild, texture/lightmap/probe epoch invalidation, full 128-page fixed reservation/shrink, device-limit clamping, fragmentation, bounded exhaustion and `INT_MAX` negative controls. Retired identities are deliberately rejected as stale; invalid-free count remains zero.
- The accepted SDVK-002 `material-stress` corpus was extended with eight real PBR custom-shader texture bindings using binding 8/custom index 0 and alternating nearest/linear requests. State evidence keeps PF-008 fixed layer ordering and asserts custom bindings separately rather than normalizing them into the authored prefix.
- Historical CI run `37962321008` is retained as failed evidence: a new catalog validator accidentally reused the catalog-wide `seen` set and weakened the duplicate-scene negative control. The fix isolates `seen_custom_layers`; no renderer assertion was weakened.
- Final PR #126 head `862ae0f591d60572c2474f0b6f22d44bfbb30e24` passed Renderer source evidence run `37962887608` and Continuous Integration run `37962887060` with 9/9 jobs, including the full software-Vulkan corpus and timing baseline.
- PR #126 squash-merged as `d356a311cf6044275e3ccedf7c1ab9e1f7858e9b`; merge tree `9ce95e42441744d2270954bbec25b193d2d019ae` exactly equals the tested PR merge-ref tree. Exact merged-master Renderer source evidence run `37974299356` and CI run `37974299316` passed, again 9/9.
- Retained llvmpipe material-stress pressure: requested/effective 16,536 descriptors, derived device limit 999,985, 438 current/high-water dynamic descriptors, 72 allocations, 4 reuses, 4 frees, zero allocation failures/invalid frees and 142 hardware textures. `sun-probes` observed one lightmap page plus two irradiance and two prefilter resources.
- The hosted eight-scene lane does not execute the retained `pf-indexed-material` recipe. Translation/palette native correctness remains consumed from accepted PF-110 evidence plus SDVK-004's 128-variant pressure/source contracts; no new llvmpipe indexed claim is manufactured.
- No physical-GPU qualification or performance improvement is claimed; software Vulkan is bounded correctness/repeatability evidence. No donor renderer code was imported.

**SDVK-004: ACCEPTED, MERGED AND VERIFIED. SDVK-005: DEPENDENCY-READY.** SDVK-006 and SDVK-009 remain independently dependency-ready.

### 9 October 2026 — SDVK-009 non-physical many-light qualification candidate

- Reconciled live authority at `master@cafbad5c45977327ba507bcf5f2dea9c3661f3d3`; SDVK-004 is accepted and SDVK-006 source is merged. No pre-existing SDVK-009 branch/PR/comments were found. Dedicated branch: `sdvk-009-many-light-qualification`.
- Mapped the production dynamic-light path from consumer-specific wall/flat/decal/sprite/model/HUD selection through class-partitioned `FDynLightData`, immediate Vulkan range/record upload and shader iteration. Existing PF-016 actor-query/portal/visibility semantics remain authoritative.
- Audited the dormant LevelMesh/Z-minmax/tile scaffold. Direct revival is rejected before hardware: each 64x64 tile stores at most sixteen copied light records; the dormant producer still has unresolved portal-group zero; main scene consumption is disabled; active LevelMesh surface lists use lightmapper-specific eligibility and a four-portal-copy source cache that can return index zero on exhaustion.
- PF-017's physically measured temporal reuse/indirection no-go remains rejected. A host-only ordered-index tile model preserves all 256 IDs/order and materially reduces representative storage, but does not reduce worst-overlap loop entries or solve semantic eligibility; it is research evidence only, not production code.
- Added state-only reusable many-light census/query/upload diagnostics and made immediate light-upload capacity fallback fail the state oracle. Timing mode remains free of per-upload bookkeeping.
- Found and repaired one active bounded correctness defect: `VkRenderState::UploadLights` accepted `UploadIndex == MAX_LIGHT_DATA`; the shared pure guard now requires a strictly in-range range-table index and overflow-safe record capacity.
- Added deterministic 256-light overlap and dispersed mixed point/spot normal/additive/subtractive workloads without changing the retained eleven-scene bytes. Hosted `--full` software-Vulkan qualification now includes those state/image routes and three short descriptive timing processes per dense scene, explicitly non-physical.
- Focused host contracts for light query, compatibility, shadows, portals/sprites, LevelMesh, PF-019 dormant resources, SDVK-009 capacity/indexing, corpus/native orchestration and validation pass locally. A prior aggregate `tools/check.py` attempt exceeded this local execution window before completion; it is retained as an environment limitation, not a test failure. Exact-head hosted CI/software Vulkan remains the release gate.
- Provisional end state is **C / no-change pending physical confirmation**. All concrete alternatives are already physically rejected or fail off-GPU correctness. The finite later campaign is preregistered in `SDVK-009-GPU-QUALIFICATION-PROTOCOL.md`. #9 remains open; no GPU speedup/no-regression/final acceptance is claimed.


### 10 October 2026 — SDVK-005 height-semantic implementation candidate

- Started #5 from live `master@0a2fbad203549d18ac6e5a61bb4747709637bfde` after accepted SDVK-004/006 and merged SDVK-009 nonphysical preparation. No prior SDVK-005 branch/PR/comments existed.
- Height is added as an optional semantic appended after historical fixed/custom bindings; old custom shader bindings remain unchanged. The Vulkan descriptor entry exposes an actual relative height index and refuses to reinterpret height on indexed/palette routes.
- Built-in semantic layers gain opt-in nearest/linear/default filter authoring while existing defaults remain unchanged; height defaults to filtered mipmapped linear scalar data. Stock material shading does not consume it.
- The SDVK-002 material observer records height binding/sampler/resource state and requires the shader-visible height index to agree. Existing material-stress and sprite-mirror authored native workloads are extended for height-present/absent, mixed-filter, custom-shader and sprite evidence.
- Focused SDVK-005, PF-008, GLDEFS, indexed-material and renderer-oracle contracts are being qualified. This is implementation progress only; exact-head hosted checks, software Vulkan, merge and post-merge verification remain acceptance gates.


### 10 October 2026 — SDVK-005 accepted; SDVK-007 dependency unblocked

- SDVK-005 substantive PR #132 final head `9a87734357d15145ed791d89c4b98db94fb60cb6` passed Renderer source evidence run `38030309310` and Continuous Integration run `38030309307` with 9/9 jobs.
- PR #132 squash-merged as `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1`; merged tree `28f2ef41a99ea6979145030e807c7798c6e01735` exactly equals the tested PR-head tree.
- Exact merged-master source evidence run `38032400496` passed and CI run `38032400505` passed 9/9, including the complete ten-scene software-Vulkan state/image lane.
- Accepted height semantics are optional linear scalar data appended after historical fixed/custom bindings. Existing GLDEFS custom starts 5/7/9 remain unchanged; stock material shading does not sample height; custom/later shaders use the semantic height helper and shader-visible dynamic index.
- Native material-stress proves legacy/PBR/custom height bindings and independent sampling; custom PBR retains binding 8 and appends height at 9. Sprite-mirror proves the sprite material route.
- PF-002/PF-003/SDVK-004 generation/lifetime ownership remains authoritative; the exact-head oracle reruns the 3,072/4,096 descriptor-pressure and rebuild/stale/exhaustion contracts.
- Initial bot-authored `action_required` runs and the bounded SWCanvas extraction-harness failure are retained; no renderer failure was waived.
- No physical-GPU qualification was required or claimed.
- Acceptance reconciliation is PR #134 with [human-readable](SDVK-005-FINAL-ACCEPTANCE.md) and [machine-readable](SDVK-005-RELEASE-ACCEPTANCE.json) evidence.

**SDVK-005: ACCEPTED, MERGED AND VERIFIED after PR #134 reconciliation verification. SDVK-007: DEPENDENCY-READY.**

### 10 October 2026 — SDVK-007 implementation and qualification in progress

- Start `master@cbff1d10b802e60a56d239338f810f7e1e52920d`; SDVK-005 accepted and reconciled, PF-009/014 orientation/portal prerequisites accepted. Dedicated `sdvk-007-explicit-sprite-tangent-basis` branch, substantive PR #135.
- Pre-implementation trace captured the degenerate inherited sprite normal-map baseline (`SetNormal(0,0,0)` + derivative `cotangent_frame`) and pinned the final PF-009 quad/signed-UV/portal-parity substrate in `SDVK-007-BASIS-ARCHITECTURE.md`.
- Adds sprite-only T/N/sign/enable surface uniforms and GLSL selection with no new vertex/interpolator or height/POM work; all normal-free, non-sprite and model routes retain inherited behavior.
- Read-only Vulkan emitted-draw diagnostics and finite/orthogonal/mirror parity validators; directional 8-rotation/flip/camera fixtures; extends existing native `sprite-mirror` with directional normal, PBR, height and unmapped controls.
- **Not an acceptance record.** Exact-head source/full 9-job CI, complete software-Vulkan state/image and exact merged-master reconciliation remain gates; downstream SDVK-008/010 are still blocked until they pass. No physical-GPU run is required for this issue.
 
### 10 October 2026 — SDVK-007 final acceptance and merge reconciliation

- Final substantive PR #135 head `a895dca0a5f356440f79f0631289d2862afe86f3` passed Renderer source evidence run **38049863197** and CI run **38049863166** (9/9 including software Vulkan). Squash-merged `master@08ec183e665e7a3100b6cf3a267f5d3b5b494990` has exactly the same tree `8afa7ce6267abdfe8740cc7de4a72e0e9d510661`.
- Post-merge source evidence **38051697523** passed. Initial merged-master CI **38051697394** was 8/9: Windows Debug `vktool.exe --version` exceeded a 20-second timeout after `vkdoom.exe` identity passed. This failure was **not waived**. Rerun attempt **2** of exact same SHA, Windows Debug job **114218926544**, passed both executable identity checks with correct clean-commit metadata; CI now concludes **success / 9 of 9**.
- Native software-Vulkan artifact **11670441947** retains the full ten-scene state/image capture and comparison, including lit asymmetric directional normal-map, PBR/specular and no-normal-map `sprite-mirror` controls. Invalid signed UV, orthogonal-but-wrong normal, portal parity and degenerate fallback negative evidence is preserved. Earlier CI failures **38047322260**, **38047456941** and **38047737451** were repaired and requalified, never waived.
- The v1 sprite-only basis follows PF-009 final quad and UV sign, with PF-010 mirrored-view parity **diagnostic-only** and derivative fallback on invalid cards. Height/POM, material bindings, world/model paths and gameplay remain unaffected. [Final report](SDVK-007-FINAL-ACCEPTANCE.md) and [release receipt](SDVK-007-RELEASE-ACCEPTANCE.json) pin source/native artifact SHA-256 and exact CI.
- This documentation-only acceptance reconciliation requires its own checked merge and master verification before closing #7. No physical-GPU or cross-tree pixel-diff assertion.

**SDVK-007 / #7: ACCEPTED, MERGED AND VERIFIED after checked acceptance publication. SDVK-008 / #8 and SDVK-010 / #10: dependency-ready at that gate.** SDVK-009's independent physical campaign remains open.

### 10 October 2026 — SDVK-008 bounded software-Vulkan implementation, pending hardware

- Accepted #7 tangent and accepted #5 red-channel height were reconciled against dedicated branch `sdvk-008-bounded-sprite-relief`, from `master@adead010aa40d0f4f8d9ffdb51573005b7f9a964`. Nine unmodified text/reference research and physical protocol files from `prepass/sdvk-008-relief@34b7a126249aec98168fc188ab113c374a034f80` preserved on implementation branch; prepass research ZIP remains intact on archival branch.
- Draft [PR #138](https://github.com/techrote/ShadeDoomVK/pull/138) contains opt-in **default-OFF** bounded sprite shallow POM from accepted final-quad TBN, per-material height semantic, append-only per-draw uniforms and low/medium/high 10/15/23 maximum samples. Alpha, frame UV subrect, filter footprint, angle/depth, NPOT/custom/legacy and non-sprite safeguards fail closed without gameplay or geometry changes.
- The original independent CPU prepass oracle and 1,620-case numeric grid are retained; production CPU ABI/negative fixtures and `sprite-mirror` emitted-draw diagnostic/state rules added, retaining complete SDVK-002 ten-scene state/image qualification. All source/CI/native runs remain subject to exact-head verification; no stage is declared passed by merely appearing in this ledger.
- [Production contract](SDVK-008-PRODUCTION-CONTRACT.md), [off-GPU report](SDVK-008-OFFGPU-QUALIFICATION.md), prepass [physical GPU protocol](prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md) and updated material/portal/observability RAG specify responsibility and evidence. Do not mislabel software-Vulkan CPU timings or theoretical sample maxima as physical-GPU performance.
- **Issue #8 remains open with physical-GPU image, cost and quality qualification outstanding**, even if optional production implementation eventually merges on tested master. **SDVK-012 remains blocked** until full #8 acceptance.
### 10 October 2026 — SDVK-010 actor probe/IBL implementation candidate

- Reconciled verified `master@adead010aa40d0f4f8d9ffdb51573005b7f9a964`, accepted SDVK-007 and inherited PF-012/113. Dedicated branch `sdvk-010-actor-probe-environment`. No prior SDVK-010 implementation branch or PR identified.
- Reproduced static sector-target actor probe selection despite in-sector actor motion; found negative/stale authored ordinal risk at Vulkan bindless lookup call site. The pure production selector follows interpolated source-level actor XYZ with a deterministic nearest 512-unit rule, validated ordinal, first-tie policy and conservative linked-portal sector fallback. Missing/out-of-range authored probe becomes -1; PF-113 runtime zero and exact irradiance/prefilter sampling remain unchanged. Other source/model/gameplay paths unaffected.
- Implemented read-only actual Vulkan draw `probe.actor_selection` provenance/epoch and strict emitted-state validation. Extended existing `sun-probes` with distinct PBR actor cards near authored probe0/probe1; `sprite-mirror` tests no-authored-probe fallback. Compiled production-header and negative source/state fixtures prevent stale published descriptor, parity, wrong coordinate system and lost live material evidence.
- **Complete local CPU gate passed** on the candidate: PF source/contract tests, CFX tests, renderer-oracle suite/corpus, two identical oracle outputs and four compiled contract fixtures. PF-009 historical region and PF-113 protected lookup remain unchanged; negative-stale protection is at the calling Vulkan draw boundary.
- **Not acceptance.** Exact hosted builds/native software Vulkan, actual sunlight world-occlusion/linked-portal transition evidence, final PR merge and verified master remain outstanding. The current sun-probe fixture requests sunlight but is not a qualified full-bake or hardware GPU campaign; do not close issue #10 or unblock SDVK-011/014 on this entry. [Owning contract](SDVK-010-ACTOR-ENVIRONMENT-CONTRACT.md).

### 10 October 2026 — SDVK-008 substantive off-GPU implementation merged; hardware gate remains

- PR #138 final integration head `6c0d418e82f34de89084b4175d8aafe0bc024e71` reconciled current SDVK-010 probe contracts, preserving both lanes across nine shared files. Final source-evidence run **38068791101 PASS**; final full CI **38068790984 9/9 PASS** including complete software-Vulkan corpus. Tests cover emitted POM eligibility, accepted basis, mirrored X/Y UVs, original-alpha/no-height controls and sample-work bounds.
- Substantive squash merge `master@9536324ce33ea418af5a8efe733b4659f6b4ad9b`; tested-PR and merged-master tree **equal** (`3123bc7fd3dd9074487cbe3487f9336ef3589003`). Merge-push source-evidence **38074510322 PASS**; merge-push full CI **38074510339 PASS (9/9)** on exact merged commit (Linux software Vulkan and all platforms).
- Production remains opt-in **OFF by default**, with bounded shallow POM, shader path and actual draw eligibility diagnostics. Earlier MSVC CVar and X/Y UV tuple-control failures were repaired and retained; direct hardware scene/image and GPU timing/quality were **not performed**.
- Hardware correctness/cost remains the **hard #8 acceptance gate** under [preregistered SDVK-008 physical-GPU protocol](prepass/SDVK-008/SDVK-008-PHYSICAL-GPU-PROTOCOL.md). Machine-readable [off-GPU evidence](SDVK-008-OFFGPU-RELEASE-ACCEPTANCE.json) and [off-GPU report](SDVK-008-OFFGPU-QUALIFICATION.md) pin immutable artifact/source identities. GitHub automatically closed #8 on merge; it was explicitly reopened, as final acceptance is outstanding. SDVK-012 remains BLOCKED.

### SDVK-008 physical tooling checkpoint — 2026-10-11 (acceptance unchanged)

Dedicated `sdvk008_physical.py` and deterministic finite fixture recipes implement
bounded collection, exact source/content/device continuity, OFF/ON witnesses and
preregistered timing statistics. Full mode refuses incomplete advanced fixture
gates; partial correctness is explicit and never reaches timing. A separate
hosted CPU-llvmpipe smoke is added for real fixture grammar/effect/direction/alpha
validation, with a distinct receipt and all physical flags false. Host tests do
not count as native or physical evidence. The local physical session is stopped
after the programme owner's SDVK-009 GPU fault; this tooling lane launched no
local GPU workload. #8 remains OPEN, no mode/default is accepted, and #12 remains
blocked. [Bounded checkpoint](SDVK-008-PHYSICAL-TOOLING-CHECKPOINT.md).

### 11 October 2026 — SDVK-009 physical failure retained; hardware stop

- Verified starting master `41340ac5790c9cbf690fcd0c49338b5bb6c84927`: source evidence `38081839068` PASS and full CI `38081839116` PASS 9/9. Independently built clean frozen #9 `0a2fbad203549d18ac6e5a61bb4747709637bfde` and #8 `9536324ce33ea418af5a8efe733b4659f6b4ad9b` with separate worktrees/builds/packages.
- Executed #9 first on actual Vulkan GTX 1650 SUPER / driver 616.92. Twelve renderer processes completed, six exact state/image pairs passed at 640×480. Thirteenth process (`shadow-boundary`, first capture) emitted Vulkan fault records and hung; Windows nvlddmkm event153 corroborates instability. Retained failed process and forced-termination status, zero retries, zero timing processes. Temperature maximum 52°C; existing 90 W limit unchanged.
- **FAILED_DEVICE_FAULT / architecture INCONCLUSIVE**. No physical scaling, performance acceptance or #9 closure. Root cause undetermined. All later physical launches on this host stopped; #8/#10 hardware not launched. [Report and bounded evidence](SDVK-009-PHYSICAL-20261011.md) pin full local archive/hash and explicitly lack durable remote raw storage.
- Windows CRLF identity parsing and runtime byte/device continuity tooling are corrected. A separate opt-in scene GPU timestamp instrumentation candidate addresses an audited measurement gap; it is unmeasured and requires a new exact source/build/preregistered experiment.
- #8/#9/#10 remain OPEN; #11/#12/#14 remain blocked. No accepted architecture, quality/default or dependency transition is inferred from tooling tests or partial physical evidence.

### 11 October 2026 — sparse BLAS centroid identity repair candidate

- Isolated branch `sdvk-009-sparse-centroid-identity` starts from verified `master@322925d8fa1486d62db0d072310a50748bc0b1ce`. CPU execution independently confirms a constructor/subdivision logical-index defect shared with frozen `0a2f`: leading/interior degenerate holes retain original triangle IDs but compact centroid storage supplies another triangle's centroid and then an index outside populated size, even inside reserved capacity.
- The bounded repair initializes centroid storage by original triangle extent and assigns retained centroids at original IDs. Triangle selection, leaf offsets, subdivision/traversal, workloads and quality controls are unchanged. Exact pre-fix constructor/hash and original result summaries are retained; no donor code is imported.
- Production-extracted regression executes pre-fix/repaired constructors across leading/interior holes and no-hole/all-degenerate/trailing-hole controls, scalar and SSE debug paths on x86: 20 scenario executions. Focused assertions-enabled MSVC collision/LevelMesh CPU gate passes 12/12. Hosted source/build/CI and independent review remain pending; no merge or acceptance is predeclared.
- This is **not physical fault causality or resolution**. The frozen failed packet proves no degenerate-hole state; null BLAS export/TLAS membership remain unresolved follow-ons. Hardware STOP remains active, #9 remains open/physically inconclusive, and no performance or dependent-gate transition is claimed. [Exact bounded audit](SDVK-009-COLLISION-ROOT-AUDIT.md).
