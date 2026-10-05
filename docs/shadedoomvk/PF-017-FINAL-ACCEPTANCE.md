# PF-017 final physical disposition — 2026-10-03

**LIGHT-PATH NO-GO: reject and restore source-owned temporal reuse.** The exact integrated candidate lost its representative benefit in every one of five complete alternating GTX 1650 SUPER pairs. PR #74 retains evidence/history, but its final renderer, shaders, inherited tests and CI configuration are byte-identical to repaired master `2399d9455772c570e597a5960c626f3bf771baeb`. No optimization or incidental renderer fix remains.

## Integration and source qualification

Original PR head `1e0fe5c8e2cdd25a745b18f210b07b457e1ba124` was 77 commits behind master, with merge base `8c9e92458d1b08d8ff00f7c7874441433e63e5a9`. Merge integration `8a9a3dcb654fe197214040088e194981e6c02214` preserved accepted intervening correctness, validation and resource/descriptor lifetime repairs. The three shared paths were reviewed semantically; `vk_renderstate.cpp` differed from repaired master only in candidate `UploadLights`. CFX-009 permanent initialized neutral removed-slot descriptor publication, ordinary fence-controlled atlas retirement, CFX diagnostics and CFX-010 evidence were preserved. Diagnostic retention stayed OFF.

Before GPU use the integrated candidate passed 254 deterministic/adversarial PF/CFX tests with real MSVC ASan fixtures, inherited lifetime/allocator/mesh/probe/light fixtures, and two identical deterministic PF oracle results. Its [exact-source CI run](https://github.com/techrote/ShadeDoomVK/actions/runs/37090637554) passed all eight jobs. This qualifies the integrated source for measurement; it does not establish physical correctness acceptance.

Source/lifetime, ordered classes, packed 80-byte records, portal/PF-010 context, physical LightBufferSSO layout and fallback contracts were preserved during integration. The final no-go restores these paths exactly to accepted master. Neither frame-local hashing/indirection nor material lookup indexes are retained.

## Matched physical performance

Sources: baseline `2399d9455772c570e597a5960c626f3bf771baeb`, candidate `8a9a3dcb654fe197214040088e194981e6c02214`. Both builds used VS2022 x64 RelWithDebInfo, `/O2 /Ob1 /Zi /DNDEBUG`, static CRT OFF. EXE/PDB and runtime resource hashes are pinned in [production analysis](evidence/pf017-final-acceptance/production-analysis.json). Independently built PK3 container bytes differed due archive metadata; every uncompressed resource entry matched. Both packaged runs used the same validated baseline resource containers and ZMusic DLL.

Only the established PF-016 dense interior workload ran: seed 12345, camera (-1850,0,41), yaw/pitch 0, 832 sprites, five walls/two flats, actual output 1904×1001, uncapped production, vsync OFF, inherited multithreading and sprite-light settings. Exact content/config/scripts are pinned per preregistration. Each serial run restored the same baseline pipeline/shader caches, archived after-caches and restored originals. Both variants had independent warmups; timing excluded the first snapshot. Four warmed `bench` snapshots per run were spaced 190 tics, exceeding its five-second debounce, after 350-tic warmup, pause and settle. No game instances or builds overlapped.

| Pair/order | Baseline S: Setup ms | Candidate S: Setup ms | Baseline All ms | Candidate All ms |
|---|---:|---:|---:|---:|
| 1 B/C | 3.7085 | 4.1220 | 18.0080 | 18.4115 |
| 2 C/B | 3.6800 | 4.0835 | 18.0955 | 18.3085 |
| 3 B/C | 3.6770 | 4.0835 | 17.8815 | 18.3740 |
| 4 C/B | 3.6980 | 4.0860 | 17.9730 | 18.3310 |
| 5 B/C | 3.7060 | 4.1130 | 17.8980 | 18.3340 |

Twenty warmed samples per variant give pooled **S: Setup 3.697 → 4.096 ms (+10.79%)** and **All 17.9245 → 18.359 ms (+2.42%)**. Zero pairs improve setup; every pair also regresses whole-frame median. The preregistered material whole-frame threshold was 2%. Raw samples, min/p05/median/p95/max distributions, timings and health receipts are committed. These are existing CheckBench CPU clocks; no standalone GPU timestamp measurement is claimed.

All five complete final RGB images match exactly, with zero differing pixels at 1904×1001. PNG and decoded pixel hashes are preserved; images remain in the private evidence root. Full candidate state/packed-buffer correctness is **not accepted**, for the separate diagnostic limitation below. The timing evidence alone rejects retention under #34's measured-outcome contract.

## Launch accounting, stops and diagnostic limitation

All three roots under `C:/ShadeDoomVK/pf-local-evidence/` remain preserved and indexed:

- `pf017-final-20261003`: one baseline startup host abort. Packaging had failed for the candidate DLL before an erroneously continued baseline launch; Chrome remained foreground. No completed workload/timing/image claim. STOP preserved.
- `pf017-final-20261003-exclusive`: after the user's explicit exclusive-computer retry authorization, validated packaging and one temporary attached-thread SetForegroundWindow request achieved owned foreground without input synthesis or policy changes. One healthy baseline warmup completed, but sampling expected 21 snapshots despite CheckBench's five-second debounce. Scope stopped; this observation is excluded. The subsequent independently preregistered measurement phase corrected sampling offline.
- `pf017-final-20261003-measurements`: two valid warmups, ten valid production runs (five pairs), then one baseline diagnostic checkpoint run. All production exits, foreground ownership, cache restoration and health receipts pass. Total across phases: **15 launches**, zero new loss/TDR/reset/health anomaly; candidate diagnostic launches: **zero**. No DBP37, DBP50, Sunlust/Champions or CFX saturation route was launched.

The baseline diagnostic run exited normally but its added oracle reported unexpected failures. Physical launches stopped immediately and remain stopped. Offline ASan reproduction proves the hook failed to clear its parallel identity vectors in baseline FDynLightData::Clear; Consumer labeled identity-length errors as buffer failures before packed-byte comparison. Identical mapped bytes reproduce the failures with stale metadata, and aligning metadata clears them. This is a diagnostic defect, not demonstrated baseline corruption. Both source trees were restored byte for byte, and no diagnostic code is retained.

Baseline copy-site observations were 3,971,280 mapped bytes, 2,520 writes and 49,473 logical records (42,775 normal, 6,698 subtractive, zero additive). **Final candidate mapped bytes/writes, fallback/reuse counters and paired source/order/class/range/packed checkpoints are unmeasured.** No moving-fixture or complete final physical state gate is claimed. Historical byte savings are not substituted. Broken instrumentation and CPU proof are archived separately from clean timing binaries. No physical retry followed the failure.

All historical STOP guards, including completed CFX scopes and both prior host/protocol stops, retain their exact hashes; the final stop is sealed. Initial sandbox test permission failures, the stopped-scope CPU-temp failure, instrumentation preparation/compile attempts and source-restoration receipts are retained. The restored suite passes **245 tests, zero skips/errors**, using an isolated CPU temp directory outside physical STOP scopes. Two restored deterministic oracle files are identical.

## Acceptance mapping and final repository gate

Light-path disposition is a measured no-go, with the entire candidate reverted to accepted repaired renderer source. Material hashing/indexing remains the separately measured no-go in [material qualification](PF-017-MATERIAL-QUALIFICATION.md); accepted linear lookup remains. Default/placeholder sharing is **not worthwhile on current evidence** and no change is retained. Consequently retained light/material semantics, shader packing, portal contexts, quality and CFX lifetimes are exactly those of repaired master, without relying on incomplete candidate diagnostic evidence.

[Machine-readable evidence](evidence/pf017-final-acceptance/production-analysis.json), [independent offline audit](evidence/pf017-final-acceptance/independent-offline-audit.json), [diagnostic disposition](evidence/pf017-final-acceptance/diagnostic-disposition.json) and [complete private artifact inventory](evidence/pf017-final-acceptance/private-artifact-manifest.json) preserve the decision and its limits. The independent CPU audit recalculates raw medians, directly compares decoded RGB bytes, verifies indexed artifacts/health, serial intervals, unchanged guards and empty source/test/CI diff against master.

Historical submission: this report proposed a no-go, conditional on [PR #74](https://github.com/techrote/ShadeDoomVK/pull/74)'s exact-head checks, merge and master verification. Those gates subsequently completed. Final head `e8eee1e4863c7dbc28ac725b873b09ce5e66e1c5` passed8/8 in [run37094446019](https://github.com/techrote/ShadeDoomVK/actions/runs/37094446019); merge `844462c3a4ed5f7037ade1b49d1a28f578077213` passed8/8 in [run37095080988](https://github.com/techrote/ShadeDoomVK/actions/runs/37095080988). PF-017 / #34 is **ACCEPTED NO-GO / CLOSED**, with the complete light candidate restored and linear material lookup retained. No rejected prototype benefit or unmeasured candidate diagnostic is promoted to accepted evidence.

PF-019 and CFX final disposition have since been accepted separately; their current receipts are in the [execution ledger](10-EXECUTION-LEDGER.md). PF-020 remains its own fail-closed freeze gate and SDVK-001 remains blocked. This reconciliation changes historical status wording only; all measurements, exclusions, STOP guards and physical-programme boundaries above remain authoritative.
