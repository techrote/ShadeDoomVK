# PF-016 remaining runtime-equivalence validation — 2026-09-24



Verdict: **PASS / PF-016 accepted after implementation merge and successful post-merge CI.**

Implementation [PR #67](https://github.com/techrote/ShadeDoomVK/pull/67) merged as `6091d6739c4b7dc96ef7913c911bf4eba89d7715` and was verified on `master`. All eight required jobs passed both [submitted-head run 35984105517](https://github.com/techrote/ShadeDoomVK/actions/runs/35984105517) and [post-merge run 35990476576](https://github.com/techrote/ShadeDoomVK/actions/runs/35990476576). This document is the subsequent acceptance reconciliation; no renderer code changes accompany it.

Raw evidence root: `C:/ShadeDoomVK/pf-local-evidence/pf016/runtime-20260924`. Relative artifact references below are relative to that local evidence directory, not this repository document.



Baseline `f7d531026de5bd33181946cd91040d5f54438103`; candidate/submitted head `4c753f92b155ad72aa7e017001bfc4d9f7fd1bb0`; renderer implementation `c2684881a5b0c1b74cb361eced0c35b2ac17b90e`. The submitted source/test tree equals the measured implementation. Main checkout initially remained at `31cf32b3995dbeabaeaaad02058b4c5de966410d`, tree-identical to remote master. Existing PF-018 worktrees were inspected and left untouched.



## Runtime comparisons



Isolated Windows VS2022 x64 RelWithDebInfo diagnostic builds; same Doom2 IWAD, generated fixture/content, initial config, Vulkan GTX 1650 SUPER / NVIDIA 616.92 (runtime 616.368.0), camera (-448,0,41), yaw/pitch 0, actual 1904x1001 output. Although command arguments request 960x640, saved window settings produce the recorded 1904x1001 images on BOTH revisions; comparison uses actual dimensions. Simulation checkpoints are map tics 15/45/75/105/135/165. Identical diagnostic hooks disable render interpolation so geometry is discrete at each checkpoint. Runs are serial with a 30-second watchdog. No timing claim uses these diagnostic binaries.



Final acceptance series is exactly the six directories named `*-locked-*` in `runs/`. They disable mouse input before map load, clear keyboard bindings, cap at 35 fps, disable worker rendering, and print the constant player position/yaw six times per run. All exit 0 with no device loss, watchdog timeout or new display-driver/WHEA event.



| Pair | Ordered selected/packed records at image checkpoints | Visibility/cache records | Exact full-frame image pairs |

|---|---:|---:|---:|

| Moving polyobject, gl_spritelight=0 | 502 | 288 | 6 |

| Moving polyobject, gl_spritelight=2 | 684 | 0 (intentional shader/list mode) | 6 |

| Static control, gl_spritelight=0 | 552 | 288 | 6 |



All **1,738** selected/packed records match in order, all **576** normalized visibility/cache records match, and all **18** full RGB images match with maximum delta 0 (no crop or tolerance). Another **1,450** ordered selected/packed records match at the five exact mutation tics 30/60/90/120/150 in each pair. Query actor positions, radii, groups and model flags match at the image checkpoints. Raw state dumps include source light TID, identity/order/class, source/query group, original/portal-relative coordinates, spot status, every explicitly packed field, actual renderer trace inputs/results and cache validity reasons.



## Activation gates (all PASS)



- Linked line portals assign groups 1 and 2 with displacement (1536,0,0). Source light 105 at (2144,100,28) is selected at (608,100,28) for group 1, including a successfully qualified local query (actor 16).

- Actor 19 has render radius 2600 and visits group 2 while its own group is 1; runtime qualification rejects it and uses BSP fallback. Actor 13 (radius 96) also exercises a section-boundary fallback; ordinary radius-16 actors exercise the local path.

- Actual `ActorTraceStaticLight::TraceLightVisbility` calls `LevelMesh::Trace` from model list queries in mode 0. Both visible and occluded results occur. Gameplay LineTrace is not used.

- Stationary actor 11 / light 101 retain identical positions/directions. Visibility is false at tic 15, true at 45 and false at 135 as the polyobject moves. Logs show worldChanged=1, actorChanged=0, portalChanged=0 and lightChanged=0 at those retraces. Query epochs advance. The static control demonstrates cache reuse with hit=1 and no actual retrace at the same checkpoints.

- Additive, subtractive, point and spotlight identities/classes/order and packing match. Real generated OBJ models use the changed list path in mode 0; sprite and model list paths run in mode 2.

- Previously qualified actor 17 loses the local path on position change at tic 30, section change at 60 and portal-group change at 120. Actor 16 loses it on render-radius change at 60. Exact key mismatch, local=0 and qualification/fallback results are preserved; restored supported positions requalify.



## Identity normalization



Light TIDs map six unique authored sources, each with exactly one attached light. Selected/packed records are compared byte-for-byte with no normalization. Process-local section pointers are mapped by first encounter only for QUERY records. PF-004 query epoch values are process-local mutation serials (startup/render counts can differ), so visibility comparison maps their numeric value to the identical geometry/simulation checkpoint; raw values remain in logs and validity reasons remain compared. Candidate qualification can perform an extra visibility invocation; only duplicate *identical* visibility records collapse for semantic comparison. No distinct trace input, result, cache decision or invalidation reason is discarded. `analysis.json` documents and verifies this normalization.



## Historical and excluded evidence



Fixture drafts, logs and generator versions remain preserved. Earlier drafts established coverage but did not activate all gates; `analysis-v3.json` records missing activation explicitly. One later mode-2 pair was invalidated by the user's reported accidental mouse/camera movement around 11:52. Its six image mismatches and tic-15 visible actor-population mismatch are preserved in `camera-contamination.json`, `analysis-camera-contaminated.json` and `mismatch-mode2-moving-15.json`. That uncontrolled pair is INCONCLUSIVE, excluded from acceptance; the input-locked pair passes without changing renderer code or widening tolerances.



## Performance and CI



No renderer repair was necessary. The original production binaries and all 318 hashed historical raw artifacts in `repair-20260924/run-artifact-sha256.json` were verified unchanged. The representative production result remains 4.137 to 3.761 ms median S: Setup (-9.09%), all five interleaved pairs winning; separate 300-frame warm distributions improve 4.45%; all five production image pairs are exact. Interior and boundary each retain 97,575 matching selected/packed records.



All eight required CI jobs passed on exact submitted head in run 35984105517; `pr-premerge.json` freshly confirms them. The restored-source PF oracle passes all 22 invariants with zero unexpected results. Renderer source and tests still match implementation c2684881a exactly. No full DBP50 MAP08 or MAP15 launch occurred in this campaign.



## Audit and reproduction



`make_fixture.py` writes the moving fixture; `--static` omits the polyobject. It reuses the preserved WAD serialization helpers in `../../inputs/make_shadedoomvk_testwads.py`. Models and skin are generated locally. Final PK3 files are `fixture-moving.pk3` and `fixture-static.pk3`, with hashes in matching JSON manifests. For a run, copy the appropriate preserved PK3 to `fixture.pk3`, then invoke `run.ps1 -Variant baseline|pf016 -Rep NEW_LABEL -Mode 0|2`; never overwrite an existing run. `instrument.py CHECKOUT` reconstructs the exact diagnostic patches from that checkout's HEAD and preserves initial source bytes in `originals/`. Compile RelWithDebInfo before copying binaries/resources to the explicitly named diagnostic directories. `analyze.py` reproduces final comparisons and path gates; `transition-comparisons.json` retains mutation-tic comparisons. `identity-audit.json`, both build logs, executable/resource hashes, command scripts, initial/exit configs, raw logs/state and all images remain local.



Diagnostic executable hashes: baseline `80c71a4f2d7d1554aaa8e65c05ee1c68afc92a7d85e5bf8a56870a75a2f69714`; candidate `f4651dc3b526c0b43a1178f3a398a36f10ea256705ebbc0521042095ed057834`. Production hashes: baseline `7385754e18ac7a5bf7e043f610d8f7aae2ae1cb148396f4fb8fd0bc0c4af8ace`; candidate `7300e538f87ff34672172c67a374bea745d9759e6ba341e1af1fa9b3fc44e3de`.



Source files were restored byte-for-byte after diagnostics. Existing build directories are explicitly marked `DIAGNOSTIC-OUTPUT.txt`; their executable must be rebuilt before production use. Preserved production binaries remain separately named in the historical repair directory. No diagnostic code is submitted.



Remaining limits: one Windows/NVIDIA device; six discrete image checkpoints and five mutation checkpoints, not exhaustive content coverage. CPU-list visibility is exercised through real models because mode-0 ordinary sprites use the separate aggregate path. The static control is necessary because polyobject processing advances world-query epochs even during stationary phases. Fallback qualification allocation cost remains unchanged. PF-017 is now dependency-ready: PF-003, PF-008, PF-013 and PF-016 are accepted. No PF-017 implementation was begun. PF-018 status is unchanged; PF-019/PF-020 and SDVK-001 retain their remaining gates.

