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

## Current implementation gate

- **COMPLETED:** PF-001 / #18, PF-002 / #19, PF-003 / #20, PF-004 / #21, PF-005 / #22, PF-006 / #23, PF-007 / #24, PF-008 / #25.
- **READY:** PF-009 / #26, PF-010 / #27, PF-011 / #28, PF-013 / #30.
- **BLOCKED:** SDVK-001 / #1 until PF-020 / #37 is accepted, merged, verified on `master` and explicitly records `SDVK-001: UNBLOCKED`.
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
