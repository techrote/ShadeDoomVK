# PF-017 profiling and rejected prototype — 2026-09-24

Status: **NOT ACCEPTED.** This is the historical first-attempt record. The [second attempt](PF-017-REUSE-RESEARCH.md) found a light-only setup benefit without per-reference hashing or shader indirection, but both material hash lookups regressed and complete acceptance remains absent. Issue #34 remains open and PF-019 remains blocked. Experimental renderer/shader changes were restored before each evidence submission.

## Exact source and environment

Accepted baseline: master@66b09a872b9d45b496a27c1bf1406d8a74606cd2, matching remote master at profiling start. Baseline production executable SHA-256: 9774ea1ff5de82c4537d548735bd20c4429bc239caa9e1fecf58b0e345d2be6a.

Rejected candidate: baseline plus the experimental source patch preserved at C:/ShadeDoomVK/pf-local-evidence/pf017/rejected-indirection.patch (SHA-256 e64d28eda6fbbf943c33ff2d6e8d8b838d33048f4c7e336b8e1191d8e0edfadf) and rejected-vk_lightrecordkey.h (SHA-256 c810fbc4b2c1095a8bacdad235574bf11ef4989cba1cb47480a660102776a67e). Candidate production executable SHA-256: e79289a2b0f055de93115f8c97cf6e8bed20cc3f79ad3ece475b7812feba2857. The candidate was intentionally never committed or proposed for merge.

Both binaries used Visual Studio 17 2022, x64, RelWithDebInfo, /Zi /O2 /Ob1 /DNDEBUG and dynamic CRT on the same Windows host. Exact-master baseline was configured with:

    cmake -S C:\ShadeDoomVK\worktrees\pf017-baseline -B C:\ShadeDoomVK\worktrees\pf017-baseline\build-relwithdebinfo -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=RelWithDebInfo
    cmake --build C:\ShadeDoomVK\worktrees\pf017-baseline\build-relwithdebinfo --config RelWithDebInfo --parallel 8

The candidate used the same generator, platform, configuration and flags in C:/ShadeDoomVK/source/build-relwithdebinfo. GPU: NVIDIA GeForce GTX 1650 SUPER, driver 616.92, Vulkan runtime 616.368.0. Captured output: 1904×1001. The same Doom2 IWAD (SHA-256 8ac958e284f85ba1ebdd56030ff1c7eadefc0993bf21a8ef72d6fab959d51a4c), PF-016 dense-light interior WAD (SHA-256 21da7231bc1f81c32d15cda2150c840c6b670299a038a994f498fe680fd1d85e), and initial PF-016 config (SHA-256 b4e4f84eff7f212bf4584e7c417d4e749a628499add91e63ade2c817d0fdbaeb) were used for production pairs. Commands, startup settings, watchdogs, GPU temperatures, executable/content hashes, raw benchmarks and images remain in each local runs/*/run.json.

## Baseline source and lifetime findings

VkRenderState::UploadLights copies one ivec4 range and three contiguous class arrays per consumer into host-mapped LightBufferSSO. FDynLightData is thread-local scratch. AddLightToList packs each source FDynamicLight using its current portal-relative position, colour/class, flags and shadow index. Upload data does not retain source-light identities. Range components are normal start/end, subtractive end and additive end; scene shaders directly fetch lights[i]. VkRenderState::BeginFrame resets upload/data indices. Physical sharing would require a logical-reference buffer and shader fetch indirection, or another representation with proven order/class/lifetime equivalence. Raw transient source addresses are not sufficient identity.

The opt-in accepted-baseline probe, preserved at baseline-diagnostic.patch, counted exact packed records and class-ordered lists. Across 200 steady dense-light frames (100–299), each frame had:

| Metric | Baseline |
|---|---:|
| Consumers / logical records | 840 / 49,473 |
| Normal / subtractive / additive | 42,775 / 6,698 / 0 |
| Distinct packed physical records | 217 |
| Mapped range + record copy bytes | 3,971,280 |
| Median measured memcpy block time | 196,550 ns |

The copy timer covers only the range/array copy block, not full UploadLights or frame time. Packed-byte identity is observational and does not itself prove semantic lifetime safety. A one-frame accepted buffer dump (baseline-lightbuffer-frame200.bin) showed that reusing complete ordered ranges or contiguous subranges would save only 1,189 of 49,473 records (2.40%). This is too little to justify a new lookup on the measured workload.

Previously validated DBP37 MAP04 was profiled for material activity, not as the light-rich acceptance workload. Its steady frame had 72 light-upload calls, 79 logical records and 36 distinct packed records. Visual complexity did not make it representative for PF-017 light upload.

## Material lookup baseline

VkMaterial::GetDescriptorEntry resolves clamp through the source texture, raises indexed/palette clamp to CLAMP_NOFILTER, resolves translation to a luminosity value or palette-remap pointer, then scans clamp, remap, GlobalShaderAddr, palette mode and PF-013 RedIsAlpha interpretation. The cache is scoped to one VkMaterial, separating ordered PF-008 layers/material/samplers by owner. Global shader extension texture state is separated by its address. DeleteDescriptors frees every PF-003 bindless range before clearing variants. A future canonical key must name every currently distinguished field explicitly, use full semantic equality after collisions, and clear alongside descriptor retirement. It must preserve PF-013 indexed-luminance versus palette-index identity.

| Workload | Lookups | Hits / misses | Scan lengths 0 / 1 / 2 / 3 | Max variants per material |
|---|---:|---:|---:|---:|
| Dense PF-016 scene | 263,991 | 263,920 / 71 | 71 / 263,920 / 0 / 0 | 1 |
| DBP37 MAP04 | 42,285 | 41,933 / 352 | 253 / 38,572 / 2,077 / 1,383 | 3 |

DBP37 hit probes totalled 44,251, only 2,318 more than one comparison per hit; misses used 106 comparisons. These live populations do not establish a measurable hash-lookup benefit. No material lookup or default/placeholder sharing change was retained. Optional descriptor sharing was not attempted because no generation-safe, shader-identical saving was established.

## Rejected light-index prototype

The prototype used an explicit twenty-scalar packed-record key (including shader-visible flags/index), full equality after hashing, a frame-local physical-record map, ordered per-consumer integer references and modified shader fetches. The map and reference cursor reset at BeginFrame. A first draft missed the reference reset and lost uploads after two frames; that draft's mismatching image was excluded. The corrected candidate retained 49,473 ordered references and 217 unique records per steady frame. It wrote 211,332 range/reference bytes plus 17,360 physical bytes = **228,692 bytes**, a **94.24% reduction** from baseline mapped writes. Its opt-in full-UploadLights diagnostic median was 3,829,050 ns/frame. This intrusive total is attribution evidence only and cannot be directly compared with the baseline memcpy-only timer.

Warm-up plus five alternating production pairs used C:/ShadeDoomVK/pf-local-evidence/pf017/run-production.ps1 with matched settings and input sequence. Pair order was B/C, C/B, B/C, C/B, B/C. All runs exited 0, captured images and had no new display-driver/WHEA event or fatal renderer log. All **five decoded full RGB image pairs were pixel-identical**. This scene has no additive-light activation, portals or moving lights, and the rejected prototype did not complete the required semantic-identity/adversarial suite. Image equality is bounded evidence, not PF-017 acceptance.

| Built-in timing, ms | Baseline five samples | Candidate five samples | Median change |
|---|---|---|---:|
| S: Setup | 3.529, 3.727, 3.538, 3.919, 3.615 | 8.418, 8.271, 8.499, 12.039, 8.432 | 3.615 → 8.432 (**+133.25%**) |
| All | 18.127, 18.495, 18.226, 18.227, 18.377 | 24.225, 24.094, 24.388, 27.891, 24.204 | 18.227 → 24.225 (**+32.91%**) |
| Finish | 13.920, 14.039, 14.016, 13.550, 14.041 | 14.970, 14.898, 14.966, 14.900, 15.003 | 14.016 → 14.966 (**+6.78%**) |

Every pair worsened in S: Setup and All. Finish includes synchronization and is not isolated GPU timing; its increase gives no evidence that shader indirection is free. The candidate fails the owned-path performance requirement despite byte savings. Raw logs and analysis remain at C:/ShadeDoomVK/pf-local-evidence/pf017/alternating-analysis.json and runs/. That local evidence root also preserves diagnostic/source patches, binary dump, scripts and material counters.

## Acceptance decision and next action

**Reject per-record hash plus shader indirection; retain the accepted contiguous upload and linear material scan.** No PF-017 optimization, required adversarial suite, exact-head PR CI or final-head physical acceptance exists. This is a measured implementation blocker, not a dependency blocker or proof that no other optimization is possible. Issue #34 stays open; PF-019 / #36 stays blocked.

A next attempt should first prove an identity/lifetime scheme that avoids per-reference full-record hashing and a GPU fetch penalty on the dense workload while retaining portal-relative packing, duplicate logical identities, source order and class ranges. It should also identify and measure a real material workload with sustained variant populations above the observed one-to-three range before proposing canonical hash lookup. Only after both owned paths show repeatable benefit should implementation proceed to adversarial state tests, exact image/state comparisons, exact-head CI, final physical A/B and merge acceptance. Do not treat this documentation-only negative result as an implementation gate.
