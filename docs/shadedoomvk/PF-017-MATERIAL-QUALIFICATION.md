# PF-017 material workload qualification — 2026-09-24

Decision: **NO-GO for retaining a material lookup change in this run.** PF-017 is not accepted; issue #34 remains open and PF-019 remains blocked. This is a workload/measurement decision, not a measured rejection of a new lookup implementation.

The new Sunlust MAP30 arena produces sustained expensive populations: median 1,201 calls/frame to caches above eight entries, versus the previous Champions scene's 29. However, the estimated large-cache search cost is only 47.13 microseconds/frame, and a subsequent MAP24 arena run timed out with NVIDIA driver errors. No production confirmation or candidate A/B campaign was completed. No production lookup candidate was implemented. The accepted linear scan is retained.

## Baseline, prerequisites and history

The actual local and remote master at start was `84bbbacbc2cea8568e78ac2f0e059ffc5608a897`. Work used dedicated branch `pf-017-material-qualification`. The preexisting untracked `build-relwithdebinfo/` directory was preserved; the accepted executable and resources were copied before instrumentation. There were no preexisting tracked changes.

The complete issue #34 body/comments/timeline and PR #71/#72 bodies, comments and reviews were read. Both PRs have no submitted reviews or inline/issue discussion. Their linked canonical evidence, shared contracts, PF-013 acceptance/tests, ledger and relevant RAG/source were inspected. All **322 historical artifact hashes matched**. The archived machine-readable analyses confirm Champions maxima 15/17, 29 large calls among about 1,780 calls/frame, node +94.8% and flat +36.8% regressions, and zero observed oracle mismatches. Neither index was retained. Universal Entropy was not acquired or measured in the prior run and was not retried here.

PF-003/PF-008/PF-013/PF-016 remain accepted. Their contracts and the full PF-017 light/material/physical/CI acceptance requirements are unchanged. No light prototype or PF-019 work was resumed.

## Exact artifacts and environment

Local raw evidence: `C:/ShadeDoomVK/pf-local-evidence/pf017/material-qualification-20260924`. [The manifest](evidence/pf017-material-qualification/artifact-manifest.json) records exact hashes of patches, scripts, downloaded assets, binaries, logs, images, traces and analyses. These are research artifacts; game assets and binaries are not committed.

| Artifact | Identity |
|---|---|
| Baseline source | `84bbbacbc2cea8568e78ac2f0e059ffc5608a897` |
| Fresh exact-master production executable SHA-256 | `402296ee1d439f2973bb040d3de87e500786497da2de8461d66f9703e64403c6` |
| Diagnostic executable SHA-256 | `54bef07801c0b2a69c7ec46c04fb108259c2f5cee834e912bd8e7007da0335ec` |
| Diagnostic source | Baseline plus `diagnostic.patch` and `vk_pf017probe.h` |
| Patch SHA-256 | `bd110fb2aa16367a821e08f7ec1c2cc7adddc85288501e2d645bbfeb015701e28` |
| Probe header SHA-256 | `707152a1da247851c7c7110799d002f507f23eda7474cc74927a4544e07da952` |
| Candidate commit/binary | **None** |

Hardware: Ryzen 5 2600X, physical GTX 1650 SUPER, NVIDIA driver 616.92 / Vulkan driver 616.368.0, Windows build 26200. Build: VS2022 x64, MSVC 14.44.35207, RelWithDebInfo `/Zi /O2 /Ob1 /DNDEBUG`, dynamic CRT. Runtime output: 1904 × 1001. Baseline build command:

```powershell
cmake --build C:/ShadeDoomVK/source/build-relwithdebinfo --config RelWithDebInfo --parallel 8
```

The same build directory/flags produced the diagnostic and restored accepted builds. Completed-build orphan MSBuild workers were stopped before the first launch. No compilation or unrelated benchmark ran during profiles. All launches disabled mouse input and joystick input, removed keyboard/double/automap binds from isolated configs, and ran `unbindall`; recorded final configs confirm `use_mouse=false`, `m_use_mouse=0` and empty binding sections.

## Published workload shortlist and provenance

The shortlist deliberately combined authored monster-dense maps with an existing small-cache comparison, rather than selecting content from timing results. `protocol.json` was saved before the first profile. Map THINGS inspection identified Sunlust MAP24/MAP30 as dense repeated-monster populations. Their starting cameras were measured first and failed qualification. Two additional authored combat-area cameras were then selected by spatial monster populations, before measuring those camera sequences.

- **Sunlust**, Ribbiks and Dannebubinga, Aug 7 2015: [author page](https://www.rbkz.net/doom/) and [archive readme](https://www.gamers.org/pub/idgames/levels/doom2/Ports/megawads/sunlust.txt). Downloaded unmodified from the corresponding `sunlust.zip` archive. WAD SHA-256 `6a90becf56040896fd2876a29f60a7a528d9802b081e0a1cc7d7cc65d546a964`. Published Doom II/Boom mapset; HMP is among the author's recommended ordinary difficulty settings. The intended HMP protocol actually selected UV, as corrected below. MAP24 and MAP30 contain many repeated monster sprites, making Champions translations a plausible expensive lookup workload.
- **Champions**, archived `mk-champions[20210309].pk3`, SHA-256 `08da7bdc92dae1378b84cf28d21ecba533a0f007b7de28cb46336399d251737f`. Provenance is retained in [the previous research record](PF-017-REUSE-RESEARCH.md). The author forum currently denied automated access; local published ZScript/CVARINFO/MENUDEF were inspected. Normal difficulty-based `champion_OverrideChance=-1` and all other mod defaults were used. No modified mod, forced colour, injected monster, or uniform random lookup distribution was used.
- **AUGER;ZENITH / DBP37**, Doomer Boards Community, July 23 2021, existing `C:/ShadeDoomVK/dbp37/DBP37_AUGZEN.wad`, MAP04. Its included author readme and exact WAD hash are retained. The scene previously showed small material populations and provides a comparison with substantial material/content variety.
- **Freedoom Phase 2 0.13.0** supplied the base assets for every measured run. [Official download](https://freedoom.github.io/download.html) and release checksum were obtained. ZIP SHA-256 `3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59` matches the publisher checksum; WAD SHA-256 `a8772e088847032510d97ba2312406a6998f21cbab44d4ff10696faa9c0ecd4b`. Freedoom explicitly supports Doom II mods. This is a verified substitute asset base, **not stock Doom II**.

During the run the user supplied `C:/ShadeDoomVK/ogwads/doom2.wad`. It has an IWAD header, 2,928 lumps, 14,951,361 bytes, SHA-256 `31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab`, and MD5 `64a4c88a871da67492aaa2020a068cd8`. That size/MD5 matches the KEX rerelease in the [libretro content database](https://github.com/libretro/libretro-database/blob/master/dat/DOOM.dat). It was verified after the GPU failure and **was not profiled**. The older file named Doom2.wad still has a PWAD header and is not assumed to be stock.

## Reproducible configuration and windows

Every run.json contains its exact arguments, binary/content/config hashes, start/end times and driver events. Initial renderer configuration is the same archived PF-016 config, SHA-256 `b4e4f84eff7f212bf4584e7c417d4e749a628499add91e63ade2c817d0fdbaeb`, with isolated input locks and uncapped/no-vsync overrides. Actual difficulty is **Ultra-Violence (`+skill 3`, zero-based)**, RNG seed 12345, no autoload and no sound. `god` keeps observation alive; monsters continue normal authored behavior. No freeze or notarget was used. These are controlled observation sequences, not recordings of a completed ordinary playthrough.

The final source audit caught an initial protocol-label error: HMP requires `+skill 2` (or the distinct one-based command-line option `-skill 3`). The immutable preregistered protocol and HMP THINGS inspection are preserved, with [a machine-readable correction](evidence/pf017-material-qualification/configuration-audit.json). All actual launch logs consistently specify `+skill 3`; none of these measurements may be described as HMP. Champions' default spawn chance depends on the active skill, so this deviation also affects population representativeness. A subsequent HMP campaign would be new evidence, not a relabeling of these runs.

| Phase | Fixed sequence |
|---|---|
| 0 | Load/startup and 70-tic warm-up |
| 1 | 210 tics stationary live rendering; built-in `bench` |
| 2 | Forward 35 tics, turn right 35 tics, stationary 70 tics |
| 3 | Texture filter 0 for 70 tics, then original filter 6 for 70 tics |
| 4 | Reload the same map and render 70 tics |

All results use whole phase windows, with no favorable frame selection. Frames crossing a phase boundary can contribute to both phases; phase frame counts are therefore not additive. The MAP30 arena starts with console `warp 0 -256`, facing the map's original 90-degree heading; its bench location is `(0,-256,369)`. MAP24's additional camera was `warp -4800 8400`; it failed and is excluded from completed-result statistics. Camera warps reach authored geometry without adding content, but do not establish normal progression/route equivalence.

Example reproduction, after restoring the archived diagnostic and reviewing the runtime failure:

```powershell
& C:/ShadeDoomVK/pf-local-evidence/pf017/material-qualification-20260924/run.ps1 -Name NEW-UNIQUE-RUN -Map MAP30 -Content sunlust -Champions -Warp '0 -256'
```

The runner currently refuses further launches because `STOP-LAUNCHES.txt` records the driver failure. This record does not instruct bypassing that guard.

## Lookup identity and probe boundaries

Current accepted `VkMaterial::GetDescriptorEntry` first resolves translation as luminosity integer or palette-remap pointer, applies `FGameTexture::GetClampMode`, applies palette no-filter adjustment, and normalizes RedIsAlpha as `mPaletteMode && mRedIsAlpha`. Accepted equality distinguishes resolved clamp, resolved remap/luminosity, all `GlobalShaderAddr` fields (`num`, `type`, `name`, including otherwise unused values), indexed mode and normalized indexed-RedIsAlpha.

The owning VkMaterial supplies source texture, scale/material identity, historical ordered layers and per-layer samplers. `ValidateTexture`'s indexed and expand/upscale normalization is unchanged. Misses allocate the same contiguous bindless range and write historical layer order, including global-shader extensions and placeholders. `DeleteDescriptors` frees every PF-003 range before clearing variants; sampler changes and precaching call the manager's reset path; destruction removes the owner. Hardware image reset retains PF-005 epochs and all three PF-013 image interpretations. No default-resource sharing was attempted.

The diagnostic executes the accepted linear scan directly; it does not substitute a lookup algorithm. It records actual hit position/comparison count without adding a counter to every comparison, per-owner incarnation/reset boundaries, raw requests, canonical miss keys, returned bindless index/generation/epoch/span, and PF-008 ordered layer/source/sampling diagnostics. Binary records retain actual order and frequency. Raw pointers are run-local identity only. The raw `globalRepeat` flag counts consecutive hits and omits an immediate repeat after a miss; it must not be interpreted as complete global key locality. Reported shortcut/key-change conclusions use the independently reconstructed owner-local sequence, including misses and resets. No padding/raw object representation is hashed. There is no candidate oracle work in the timed region because there is no candidate.

## Measured workload qualification

Phase 1 complete-run results, including failed-to-qualify starting views:

| Workload | Calls / frames | Population p50 / p95 / max | Hit comparisons p50 / p95 / p99 / max | Median >8 calls/frame | Search estimate, microseconds/frame |
|---|---:|---|---|---:|---:|
| DBP37 MAP04 + Champions | 957,151 / 2,058 | 1 / 2 / 3 | 1 / 2 / 2 / 2 | 0 | 7.48 |
| Sunlust MAP24 start + Champions | 128,040 / 46 | 2 / 2 / 2 | 1 / 1 / 2 / 2 | 0 | 9.75 |
| Sunlust MAP30 start + Champions | 63,887 / 15 | 2 / 2 / 3 | 1 / 2 / 2 / 3 | 0 | 14.89 |
| Sunlust MAP30 arena + Champions | 238,321 / 13 | 1 / 15 / 18 | 1 / 3 / 11 / 18 | **1,201** | **147.82** |
| Sunlust MAP24 arena + Champions | Incomplete: timeout/driver events | Excluded | Excluded | Excluded | No claim |

The MAP30 arena **qualifies for expensive-population diagnosis**: expensive calls persist throughout the fixed stationary window and account for about 32% of estimated search time. It does not qualify as final representative performance evidence: it has only 13 phase-1 rendered frames, very slow live progression, ongoing texture creation, a warped observation camera, no production confirmation and no completed paired campaign. Starting-view high total monster counts did not qualify.

The arena has 237,769 hits and 552 misses in phase 1. Mean hit comparisons are 1.4393. Complete lookup-weighted population, hit/miss comparison and hit-position histograms, percentiles, sampled populations and per-frame distributions are retained in [qualification-summary.json](evidence/pf017-material-qualification/qualification-summary.json) and raw per-run analyses. Startup and reload contain large precache bursts; they are not included in the sustained window.

| Arena phase-1 cost attribution | Microseconds/frame |
|---|---:|
| Resolved-state construction, sampled estimate | 160.43 |
| All variant search, sampled estimate | 147.82 |
| Search in populations >8, subset of preceding row | 47.13 |
| Miss allocation/texture resolution/descriptor writes, directly timed | 3,450.25 |
| Vector append/growth maintenance, directly timed | 10.30 |

The sum is approximately 3.77 ms/frame of attributed material work; most is miss construction, which a faster hit index would not remove. Allocation includes synchronous `GetImage` and descriptor-write preparation, not merely the slot allocator. No allocation or memory saving is claimed. Accepted entries are 32 bytes on MSVC x64; even 18 entries occupy 576 bytes of logical vector elements. Capacity/growth are logged per key; the hypothetical shortcut/index would add owner storage and maintenance not present in this baseline.

Across the complete arena run, trace consistency validates 689,295 calls and 2,111 canonical key definitions, with 1,194 owner births, 1,193 destruction events and 5,218 reset callbacks (including empty caches). Per-owner epochs disambiguate reused addresses. All reconstructed populations, comparison counts, semantic uniqueness and returned bindless identities match the recorded trace; zero consistency errors. The remaining owner at process shutdown is not interpreted as a leak. These observations do not certify candidate semantics or unexercised global/palette/RedIsAlpha cases.

## Measurement uncertainty and rejected shortcut hypothesis

The old per-call timer issue is material here. The new probe calibrates 100,000 adjacent `steady_clock` reads per run. Complete-run empty-read means range 22.191–23.205 ns, median 0 ns and p95/p99 100 ns: the clock is too coarse for individual lookup latency. A deterministic xorshift samples 1/64 calls; timing covers state resolution and search separately. Every miss times construction and vector maintenance. Trace bookkeeping/serialization and key/layer diagnostics occur outside those regions.

Reported sampled estimates retain raw sums and sample counts, and subtract the per-run empty-read mean by population, clipped at zero. Some low-frequency populations have no samples; those are explicitly counted and not evidence of zero cost. Timer subtraction cannot remove branch, cache-pollution or trace-write perturbation. Therefore the microsecond figures are attribution estimates, not nanosecond-precision acceptance measurements. Physical probe overhead versus uninstrumented production remains unquantified because the GPU campaign stopped.

An independent C++17 replay implements the accepted semantic scan with 32-byte entries, preserving recorded ordered keys, owner/epoch boundaries, misses and growth. It uses two warm-ups and ten whole-trace batches, with clocks only at phase boundaries and verification outside reported batches. All four complete traces pass binding/population checks. Arena phase 1 is 1.4412 ms median/batch for 238,321 lookups (1.4136–1.8615 ms range), or 110.86 microseconds per recorded live frame including replay traversal/maintenance overhead. Other complete phase-1 batches are 2.80, 12.57 and 24.41 microseconds per recorded frame for DBP37, MAP24 start and MAP30 start. Raw traversal floors and checksums are retained in [replay-analysis.json](evidence/pf017-material-qualification/replay-analysis.json). This corroborates a small owned search cost, but hot trace replay is not live-renderer benefit or production-build confirmation.

A one-entry previous-hit shortcut was investigated by exact comparison accounting, without implementing it in production. Overall owner-local repetition is 89.90%, but **large-cache hits repeat only 24.08%**. Testing the previous entry first and then the original scan while skipping that tested entry would increase large-population comparisons from 73,760 to 75,093 (**+1.81%**), before branch/index overhead. Small populations would save 25,033 comparisons over 223,540 hits; this does not establish a physical win. [The locality analysis](evidence/pf017-material-qualification/locality-comparison-bound.json) preserves every workload result. No threshold was inherited from the old prototype; >8 is a reporting bucket for historical comparison, not a proposed dispatch threshold. No new hash or flat-index experiment was repeated.

A standalone last-hit shortcut would also not fulfill PF-017's explicitly required canonical hashed lookup. The contract is not silently rewritten to accept that narrower mechanism. No alternative candidate is justified by these data and incomplete physical measurement.

## Failure, verification and remaining gates

At 18:55:42 and 18:55:43 local time, the MAP24 arena profile recorded NVIDIA `nvlddmkm` error 153, GPUID 700; the 60-second watchdog subsequently terminated the process. There was no successful completion or baseline reproduction. **Cause is unassigned**: do not label this a lookup regression, Freedoom defect or diagnosed device-loss bug. The full log, event payloads, partial trace and phase-1 image remain preserved. No further GPU launches occurred. Planned no-Champions controls, stock-IWAD profiles and production confirmation were not run; this incompleteness is explicit rather than hidden by successful starting-view results.

The exact experimental patch/header and diagnostic binary were archived. The three modified tracked source files were restored from the baseline, the new probe header removed, and accepted production source rebuilt successfully. Renderer, shaders, oracle/tests and CI are identical to baseline. The deterministic PF oracle passes twice with byte-identical JSON. Python discovery runs 102 tests: 91 pass and 11 cannot launch the missing `c++` executable. Separately, the unchanged material-correctness (PF-013), material-layer (PF-008), bindless allocator (PF-003) and generation fixtures build and pass on installed MSVC with assertions enabled. This is not an all-local-tests-pass claim.

This evidence-only PR must pass all eight inherited checks on its exact final head, merge, and pass master/post-merge verification. Those checks validate the record and unchanged renderer; they cannot replace missing physical implementation acceptance. Exact CI/merge identities are retained in the PR history.

Next concrete action: preserve and isolate the MAP24 driver failure separately; establish clean production controls on the verified KEX Doom II IWAD, then reproduce the MAP30 arena population with a bounded normal camera route and a stable warm interval. Quantify probe overhead against production and use batching/sampling that resolves the owned cost before choosing another mechanism. If a material candidate becomes justified, perform the full direct-linear-oracle semantic/adversarial matrix and at least five alternating physical pairs with small-cache controls on the exact candidate head. Until then, **no material candidate is accepted**. Full PF-017 still requires the light representation/upload benefit and exact source/order/class/lifetime proof, optional sharing proof if attempted, complete PF-013/material identity/reset coverage, paired images/state, final physical checks and full implementation PR acceptance. No partial PF-017 implementation is merged by this record.
