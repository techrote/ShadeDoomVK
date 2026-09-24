# PF-017 second attempt: source-owned reuse and real material variants

Date: 2026-09-24. Decision: **NOT ACCEPTED**. Issue #34 remains open; PF-019 / #36 remains blocked.

This follow-up to [the first rejected prototype](PF-017-PROFILING-NOTES.md) found a promising light packing/write-reuse approach without per-reference hashing or shader indirection. It also measured a published mod with 15-17 material variants. Both tested canonical hash lookups were slower than the accepted linear scan. All experimental renderer changes were restored before submitting this evidence record. No PF-017 implementation is being merged.

## Exact source, environment and artifacts

- Current accepted master at this attempt's start: b5fcab0a4c4847607007a6562c74b28c6e46a4d3.
- Baseline production binary was built from 66b09a872b9d45b496a27c1bf1406d8a74606cd2. The difference to accepted master is six documentation files only; renderer, shader and test sources are identical. Do not label that binary as a build of b5fc.
- Experiments were uncommitted changes on pf-017-range-reuse-profiling, based on b5fc. **There is no candidate commit SHA or exact-head implementation acceptance.** Base SHA plus preserved patch/header and binary hashes below identify the tested artifacts.
- Same Visual Studio 2022 x64 RelWithDebInfo configuration (/Zi /O2 /Ob1 /DNDEBUG, USE_STATIC_CRT=OFF), Ryzen 5 2600X, Windows 11 build 26200, GTX 1650 SUPER, driver 616.92 / Vulkan 616.368.0, 1904 x 1001 output.
- Local evidence root: C:/ShadeDoomVK/pf-local-evidence/pf017. Raw CSV, logs, launch records, screenshots, buffer dumps, patches, binaries and scripts remain there. The checked-in [artifact manifest](evidence/pf017-reuse-research/artifact-manifest.json) records their hashes; paths are relative to that root. Compact machine-readable analyses are checked in beside it.
- Every reported production/lookup pair completed with exit 0 and no new display-driver/WHEA event. No compilation ran concurrently with the five reported light pairs or material timing pairs.

| Artifact | SHA-256 |
|---|---|
| Baseline production executable | 9774ea1ff5de82c4537d548735bd20c4429bc239caa9e1fecf58b0e345d2be6a |
| Light-only production patch, token-reuse-production.patch | bb64a2dcb178b7fe7dead30b4dcfc06945e1cfa10eb8f1aab3a4e3b8489144ff |
| Light-only production executable, token-prod/vkdoom.exe | 86f92ba90955300d15807ec13a61f8ad0158b4f640ffe41cbe0dc4bb12991b31 |
| Node lookup diagnostic patch, material-diagnostic-final.patch | ee1dc6c824d387f5c5eb8e8390f6d13d60169da136477f6f5cdb7f7553f9adff |
| Node key header, material-key-prototype.h | d8a8be7c503bee7a147e6fa66f220b105db3d9c635173795924a8b9dbd049c96 |
| Node lookup executable, material-diag/vkdoom.exe | da9324d7f5b3029ab660520f43444b7b38c1f3542abd84c0c11a4b0b5cbf6283 |
| Added light-oracle patch, token-material-diagnostic-v2.patch | 59a4843051b774de277853abfa43088e0f50e0c451a87187dc6e63d16db0ae13 |
| Light-oracle executable, token-diag/vkdoom.exe | c50ebf9975a437089c4a0dd74ccca22dbd966c95ffca029b238de6463ba556f9 |
| Flat lookup diagnostic patch, flat-token-diagnostic.patch | ffa529c41a4c612acfc559be7fc63eeade1979d16243ab94b5a435fd6065ff05 |
| Flat key/index header, flat-vk_materialkey.h | 5c6bcd2b87de8de3fc8e7cac073609a68d164509411f5c6911a8d7b4c8f2d064 |
| Flat lookup executable, material-flat-diag/vkdoom.exe | 4684541f6f7a7413bda6e76d0ac08afe51b32befd0b0b39bf707b3cc3b6bd570 |

Each diagnostic patch is a complete tracked-file delta against the base, not an incremental patch. New headers are archived separately; the light-oracle patch requires the node key header. Production light measurements contain no material lookup changes or verification diagnostics.

Build command for each candidate, after applying its exact patch/header:

~~~powershell
cmake --build C:\ShadeDoomVK\source\build-relwithdebinfo --config RelWithDebInfo --parallel 8
~~~

Initial configuration and exact baseline build commands are in the first profiling record. Scripts copy the same initial PF-016 config into each new run, preserve arguments and executable hashes in run.json, and use a 45-second watchdog. Preexisting runs are never overwritten.

## Light representation and rejected full-byte comparison

Accepted LightBufferSSO storage is allocated and mapped by VkRSBuffers; BeginFrame resets write cursors rather than creating a physical buffer for each consumer. Each upload appends a four-integer range and contiguous normal/subtractive/additive FDynLightInfo arrays. Shaders consume those arrays directly. The baseline remains 840 consumers, 49,473 logical records, 217 distinct packed states, and 3,971,280 range/record bytes per steady dense frame.

A first alternative retained an 80-byte CPU shadow per record, compared each ordered class at its previous physical offset, and skipped unchanged mapped writes. With the same diagnostic executable and PF17_NO_REUSE=1 selecting accepted copies, frames 100-299 gave:

| Full UploadLights diagnostic, median/frame | Accepted copies | Full-byte shadow reuse |
|---|---:|---:|
| Mapped writes | 3,971,280 bytes | 0 bytes |
| Compared bytes | 0 | 3,971,280 |
| CPU time | 146,050 ns | 345,000 ns |

This approach is rejected: scanning the copied bytes costs more than copying them. Runs are range-diag-interior-{baseline,reuse}-profile; source is range-reuse-diagnostic.patch. These full-function timers must not be compared to the first attempt's memcpy-only timer. Offline inspection also found only five adjacent identical complete lists (377 records); that observation did not justify a new lookup.

## Source-owned packing revisions and temporal write reuse

The promising light-only prototype works as follows:

1. Each FDynamicLight owns four packing snapshots for existing attenuation/trace combinations, containing the accepted packed record, class, portal group, context epoch and monotonic packing revision.
2. An active PF-010 context epoch is scoped around rendering after shadow-map collection and attenuation update. First qualified use in a new context runs the accepted packing code. Changed packed state/class/group assigns a new revision. Later qualified uses within the context reuse that source-owned snapshot.
3. Only non-spot lights without RF2_LIGHTMULTALPHA, in their own portal group, qualify. Foreign-group, spot, alpha-dependent, sunlight and unsupported cases use accepted packing and revision zero. Existing light allocation clears snapshots; equal bytes in different source objects do not establish shared identity.
4. FDynLightData retains exact ordered arrays/classes and adds ordered eight-byte revision arrays. The mapped-buffer owner retains revision/range shadows. At the same physical offset, an unchanged qualified class skips its write. Any unqualified record makes its entire class take the accepted copy path. New regions copy.
5. Buffer offsets, per-consumer ranges and shader fetches remain unchanged. No per-reference full-record hash or extra shader fetch is introduced.

This is **source packing reuse and temporal mapped-write reuse**, not intra-frame physical compaction: all 49,473 physical record positions remain allocated. It does not demonstrate many consumer references sharing one uploaded physical record. Revision comparisons, CPU shadow storage and per-light snapshots are real overheads.

PVS worker traversal completes before observed packing/upload; packing in the exercised path is serialized. Temporary portal sprite rotations are one reason spots remain excluded. Full mutation, nested-context, allocation/reset/recreation and revision-wrap proofs are still required before retaining this prototype.

### Five alternating production pairs

Warm-ups preceded pair order B/C, C/B, B/C, C/B, B/C. Runs use run-production.ps1, -Fixture interior, and repetitions token-pair01 through token-pair05. Example:

~~~powershell
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-production.ps1 -Variant baseline-prod -Fixture interior -Rep token-pair01
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-production.ps1 -Variant token-prod -Fixture interior -Rep token-pair01
~~~

The script selects PF16TST in PF016_DenseLights_Interior.wad, disables cap/vsync, runs bench, waits 350 tics, pauses and captures timing and clean images with identical configuration/input sequence.

| Pair | Baseline S: Setup (ms) | Reuse S: Setup (ms) | Full RGB image |
|---|---:|---:|---|
| 1 | 3.710 | 3.451 | exact |
| 2 | 3.573 | 3.480 | exact |
| 3 | 3.527 | 3.318 | exact |
| 4 | 3.660 | 3.386 | exact |
| 5 | 3.679 | 3.410 | exact |
| Median | **3.660** | **3.410 (-6.83%)** | 5/5 exact |

[Pair analysis](evidence/pf017-reuse-research/token-alternating-analysis.json) also records Setup 3.713 -> 3.478 ms, All 17.888 -> 17.724 ms, Render 0.530 -> 0.567 ms, Drawcalls 0.174 -> 0.178 ms, Postprocess 0.085 -> 0.104 ms and Finish 13.546 -> 13.550 ms medians. The owned benefit is sprite setup, including packing/upload. This is not isolated GPU timing or a general whole-frame speedup claim.

### Measured writes and observed equivalence

Separate diagnostics (token-diag-interior-verification, frames 100-299) retain 840 consumers, 49,473 records and normal/subtractive/additive counts 42,775 / 6,698 / 0. They write **3,422,000 mapped bytes/frame**, saving **549,280 bytes (13.83%)**: unchanged subtractive arrays plus ranges. Normal classes have unsupported records and safely copy. The prototype compares 67,024 bytes of revision/range state per frame and records 840 unqualified-class fallbacks.

Packing records 49,688 calls/frame, 36,077 snapshot hits and 13,263 fallback calls, with zero direct packing-oracle mismatches. The oracle repacks each proposed hit using accepted code and compares the full shader-visible record and class; it is disabled in production timings. Full instrumented upload median is 254,000 ns/frame: no standalone UploadLights CPU improvement is claimed.

The full frame-200 range/record dump is byte-identical to baseline: SHA-256 6e273052f80d9b179fd069ec0c5532cf0193b08eec2674f323736b65465df5c0. This proves boundaries, order and packed state at that checkpoint, not durable identity for equal packed records. [Dense analysis](evidence/pf017-reuse-research/token-state-analysis.json) labels diagnostic columns.

Existing PF-016 runtime fixtures were reused without altering authored light movement/portal content:

~~~powershell
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-token-runtime.ps1 -Variant baseline-diag -Fixture moving -Mode 1 -Rep oracle
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-token-runtime.ps1 -Variant token-diag -Fixture moving -Mode 1 -Rep oracle
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-token-runtime.ps1 -Variant token-diag -Fixture static -Mode 0 -Rep fallback
~~~

The runner selects PF16RT, locks input, uses r_multithreaded 0, gl_levelmesh true, lm_dynlights false, gl_fakemodellight false, the specified sprite-light mode and a 35 fps cap. The moving fixture's final image and frame-200 buffer match exactly (buffer SHA-256 ddcd07a656cdd85ec7a02abce06672a0a4ec46906ab7dacd3324073336c9377c). The moving oracle records 41,665 calls, 16,934 hits, 22,043 fallbacks and **zero mismatches**. Static mode 0 records 36,737 calls, 13,350 hits, 20,699 fallbacks and **zero mismatches**; no separate baseline image pair is claimed for that mode. [Runtime analysis](evidence/pf017-reuse-research/token-runtime-analysis.json) records both.

The packed-byte oracle does not log durable selected-source IDs across every consumer/tic. These bounded observations do not replace positive/negative/adversarial identity, duplicate-source, class-transition, portal, reset/destruction/recreation and ambiguous-lifetime tests. No PF-017 acceptance suite was added for a prototype not being retained.

## Real material workload and canonical key

The earlier one-to-three-variant workloads were insufficient. This attempt uses published **Champions**, whose authored ZScript applies champion translations to actual monsters, on playable local MAP08 content.

- [Publisher/mirror description](https://www.gamingroom.net/games/patches-addons-editores/champions/) links the [author forum](https://forum.zdoom.org/viewtopic.php?t=60456).
- Download: https://www.gamingroom.net/wp-content/uploads/2024/07/champions.zip; archive SHA-256 870517eb5f7f78c7dc010b7f59224711113755b0eaa548ca10fe62da63b2b4bd.
- Inner mk-champions[20210309].pk3, preserved as champions.pk3: SHA-256 08da7bdc92dae1378b84cf28d21ecba533a0f007b7de28cb46336399d251737f. Mod source is not copied into the renderer.
- IWAD-slot input C:/ShadeDoomVK/pf-local-evidence/inputs/Doom2.wad: SHA-256 8ac958e284f85ba1ebdd56030ff1c7eadefc0993bf21a8ef72d6fab959d51a4c. **Its file header is PWAD; this record does not identify it as verified stock Doom II content.** Exact local content/hash define the workload. No compatibility investigation is included.
- Initial config SHA-256 b4e4f84eff7f212bf4584e7c417d4e749a628499add91e63ade2c817d0fdbaeb. Use -rngseed 12345, god; notarget; warp 1900 -1000 and unchanged mod content. Default champion_OverrideChance is -1; exposed value 256 was used only for an additional population profile.

Accepted linear-path population runs:

| Champions MAP08 profile | Calls | Hits / misses | Hit / miss probes | Maximum variants/material |
|---|---:|---:|---:|---:|
| Default chance | 1,812,711 | 1,812,070 / 641 | 2,204,051 / 1,272 | 15 |
| All champions (256) | 2,077,504 | 2,076,721 / 783 | 2,497,417 / 2,050 | 17 |

Default still has 1,481,196 lookups of a one-entry cache. Maximum population alone does not imply expensive average lookup. This increases real variant activity but does not establish benefit from hashing.

Both prototypes use named fields **after** accepted clamp/translation resolution: resolved clamp; remap/luminosity identity; GlobalShaderAddr num, type and name; indexed mode; normalized PF-013 indexed-RedIsAlpha interpretation. Equality checks every field; no raw representation/padding is hashed. The owning VkMaterial retains PF-008 texture/layer/material and sampler distinctions. Keys clear with the original descriptor vector after PF-003 range retirement. Default/placeholder sharing and slot savings were not attempted.

Small caches retain accepted linear scan. Above eight entries, the node version uses std::unordered_map; the flat version uses explicit-field hashing, a power-of-two open-addressed table, semantic equality and linear probing. An oracle outside the timer performs accepted scan and checks the exact returned vector index/bindless range. Zero observed mismatches do not certify unexercised clamp/global-shader/layer/reset or deliberate collision cases.

### Matched material lookup timing

Each candidate is compared with accepted linear lookup **inside the same diagnostic executable**, selected by PF17_MATERIAL_LINEAR=1. Light code, probes, executable and settings are constant. Timing starts before key construction/lookup after accepted state resolution; the linear oracle runs after timing. Clock overhead is included equally. This measures lookup, not descriptor allocation or frame time.

Warm-ups precede alternating linear/hash pairs. The script freezes after 70 tics then performs the common bench/capture sequence. Analysis selects frames greater than 1000 containing >8-variant lookups: 29 such calls per steady frame, about 1,780 total calls/frame, steady large populations up to 11, run maximum 15. Values are total measured large-lookup time divided by large calls per run.

~~~powershell
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-material.ps1 -Variant material-diag -Map MAP08 -Warp '1900 -1000' -Rep linear-pair01 -Linear
& C:\ShadeDoomVK\pf-local-evidence\pf017\run-material.ps1 -Variant material-diag -Map MAP08 -Warp '1900 -1000' -Rep hash-pair01
# Use material-flat-diag for the flat table; alternate order on pair 2.
~~~

| Pair | Node linear / hash (ns/call) | Flat linear / hash (ns/call) |
|---|---:|---:|
| 1 | 44.53 / 97.12 | 48.54 / 59.76 |
| 2 | 47.75 / 100.33 | 46.20 / 63.21 |
| 3 | 46.33 / 90.98 | 43.23 / 67.05 |
| 4 | 46.71 / 86.85 | - |
| 5 | 49.53 / 90.96 | - |
| Median | **46.71 / 90.98 (+94.8%)** | **46.20 / 63.21 (+36.8%)** |

Every pair regresses. All frames in reported runs have **zero direct linear-oracle mismatches**. [Node analysis](evidence/pf017-reuse-research/material-node-analysis.json) and [flat analysis](evidence/pf017-reuse-research/material-flat-analysis.json) retain exact totals and binary hashes. Neither implementation is justified by this workload. No whole-frame material claim or complete PF-013 matrix certification is made.

## Acceptance mapping and remaining blocker

| Requirement | Evidence / disposition |
|---|---|
| Same consumer identities/order/classes | Packed ranges/order/classes match dense and moving checkpoints; durable source-ID and adversarial lifetime proof incomplete. |
| Less upload/buffer work with owned benefit | Temporal writes decrease 13.83%; production sprite setup improves 6.83%. Intra-frame physical compaction is not implemented. |
| Beneficial canonical material lookup with exact state | Tested keys match linear results, but both indexes regress. Complete semantic/adversarial matrix unrun. |
| PF-003 default sharing | Not attempted; no descriptor slot/resource saving claimed. |
| Exact output/state | Five dense production images and one moving pair exact; checkpoint buffers exact; packing oracle passes. Bounded research evidence. |
| PF oracle, final implementation CI, physical final-head gate | Inherited tests unchanged; research-record CI cannot substitute for unperformed implementation gates. No final PF-017 renderer head proposed. |
| Issue and dependent gate | **Not accepted. #34 open; PF-019 blocked.** |

The exact blocker is **no measured beneficial material lookup on available real content**, plus incomplete light sharing/lifetime acceptance. The light-only prototype does not satisfy the explicit hashed-lookup/representation scope by itself; this record does not weaken scope to accept a subset. Accepted contiguous uploads, shaders, linear lookup and PF-003/PF-008/PF-013/PF-016 behavior remain the safe working path.

Next concrete action: obtain/profile real content with sustained larger/higher-probe material populations before more lookup design. Universal Entropy 3.666b is one possible authored translation workload: [author download page](https://www.moddb.com/mods/universal-entropy/downloads/universal-entropy-3666b), file uni_entropy_pk3.zip, published MD5 8323c85b361e3cef9bf0b7ff4a1d31e5. Its normal download returned HTTP 403 and the browser tool failed to start (Windows sandbox helper error 206); it was not obtained or measured. This access limitation is not evidence of a potential speedup.

If a beneficial material approach is found, resume archived source-owned light reuse with explicit identity, mutation, nested-context, wrap, reset/recreation and fallback tests; compare per-consumer source IDs/order/classes and packed state; repeat physical A/B on the final implementation and run inherited CI before acceptance. Preserve shader-direct layout unless a separately measured representation improves it safely. Do not begin PF-019.

## Research-record verification

After preserving the experimental patches and binaries, all eight modified tracked source files and the added key header were restored/removed. Renderer, shader and oracle/test sources match accepted master b5fc (and baseline binary source 66b) exactly. The ordinary workspace RelWithDebInfo build was rebuilt successfully from that accepted source; experimental binaries remain explicitly separated under the evidence root.

The unchanged deterministic PF baseline passed twice with identical JSON outputs. Local unittest discovery ran 102 tests: 91 passed and 11 compiled fixtures could not start because the required c++ executable is absent on this Windows host. This is not an all-tests-pass claim; the inherited Linux PF-oracle CI job remains required along with all seven Windows/macOS/Linux builds on the submitted evidence PR head. Existing PF-013 regression coverage is unchanged.

The evidence submission changes documentation and archived measurement JSON only. Its exact-head/post-merge CI results are recorded in the linked PR and issue history. Passing those checks validates this research record and the unchanged accepted renderer; it does not supply missing PF-017 implementation acceptance.
