# PF-017 final integrated acceptance campaign — 2026-10-03

Status: **INTEGRATED; ACCEPTANCE PENDING.** Issue #34 remains open, draft PR #74 unmerged, PF-019 / #36 blocked.

## Integration and preserved contracts

Live master is `2399d9455772c570e597a5960c626f3bf771baeb`; original PR head is `1e0fe5c8e2cdd25a745b18f210b07b457e1ba124`, 77 commits behind with merge base `8c9e92458d1b08d8ff00f7c7874441433e63e5a9`. All eight old-head and master CI jobs passed. The candidate is integrated through a merge of that exact master, preserving PR #74 history without force-pushing.

The overlapping ledger and identity RAG retain both PF-017 candidate history and all CFX evidence. The only renderer overlap, `vk_renderstate.cpp`, differs from current master only in `UploadLights`. Master changes elsewhere in that file remain intact. All other master renderer changes, shaders, resource/descriptor lifetimes, CFX diagnostics and validation repairs are preserved. In particular, CFX-009 still publishes initialized permanent typed neutral removed-slot descriptors before submission and ordinary fence-controlled atlas retirement, with diagnostic retention OFF.

PF-017 retains source-incarnation snapshots, ordered normal/subtractive/additive records and parallel nonzero revisions, unsupported revision-zero fallback, PF-010 epochs, foreign-group/spot/alpha exclusions, unchanged 80-byte records, physical `LightBufferSSO` layout and shader fetches. No rejected frame-local hash/indirection or material index is revived.

## Finite physical protocol

Private evidence root: `C:/ShadeDoomVK/pf-local-evidence/pf017-final-20261003`. Build baseline and integrated candidate in matched VS2022 x64 RelWithDebInfo, `/O2 /Ob1 /Zi /DNDEBUG`, static CRT OFF. Complete full deterministic/adversarial PF/CFX coverage and exact deterministic oracle before GPU launches.

Use only preserved PF-016 dense interior content/configuration; pin actual output dimensions, camera, source/build/runtime/content/config/cache identities. Warm each binary independently. Five serial physical pairs alternate B/C, C/B, B/C, C/B, B/C. Collect repeated existing `bench` snapshots of S: Setup and whole-frame All/Finish during the warmed frozen scene, plus final full images. No compilation overlaps timed launches. Separate matched instrumentation may collect complete range/packed buffers, source/order/class state and reuse/fallback/write counters; instrumentation deltas and binary identities must be archived and never substituted for clean production performance evidence.

Historical STOP guards are immutable. The completed CFX-009/010 routes stay saturated; no DBP37, DBP50 or Sunlust/Champions launch is authorized here. This user request explicitly authorizes the independent PF-017 workload. Preserve guard hashes and establish a new scope-local STOP on any device loss, TDR/reset, corruption, health anomaly or unexpected validation failure. No automatic GPU retry; continue offline only after a stop.

Accept only repeatable representative setup benefit, no material whole-frame regression, exact images/state/packed semantics, complete adversarial coverage and required exact-final-head CI. If benefit or equivalence fails, restore the light candidate and record the no-go. A safety/host blocker is pending acceptance, not a manufactured optimization no-go. Merge/verify/close #34 only after a valid disposition; do not start PF-019.
