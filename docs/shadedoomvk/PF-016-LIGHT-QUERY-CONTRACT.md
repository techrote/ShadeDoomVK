# PF-016 dynamic-light query contract

PF-016 changes CPU-side actor/model dynamic-light collection only. It does not change light eligibility, attenuation, colour/classification, shadow/PBR policy, portal displacement, gameplay/tic state, materials, palette/translation semantics, audio, or source/provenance ownership.

## Authoritative candidate pipeline

`HWDrawInfo::GetDynSpriteLightList` owns one candidate-processing path for both candidate sources. For every `FLightNode` it preserves the accepted sequence:

1. `FDynamicLight::ShouldLightActor(self)` eligibility;
2. `FDynamicLight::PosRelative(group)` portal-group displacement;
3. radius plus actor render-radius overlap test;
4. first-encounter duplicate suppression;
5. PF-015 actor/world/portal visibility-cache validation and trace when required;
6. `AddLightToList(..., forceAttenuate=true, doTrace=gl_spritelight>0)` with the existing normal/subtractive/additive classification and light fields.

The baseline and local candidate sources may not fork eligibility, portal-relative distance, visibility, or output packing. Duplicate membership is necessary when BSP traversal can encounter a light through multiple lists. After qualification, the local source visits exactly one section list once: `AddLightNode` in `a_dynlight.cpp` reuses the existing `(light, section)` node before allocating a new link, so this traversal is already unique and omits the redundant membership lookup. The independent qualification comparison retains generation membership and remains authoritative.

## Generation-stamped duplicate membership

The old per-query `TArray<FDynamicLight*>` maintained sorted pointer order with `SortedFind` plus insertion even though that order was used only for membership. PF-016 replaces that bookkeeping with renderer-owned `HWGenerationSet<FDynamicLight*>` state on `HWDrawContext`.

`BeginQuery()` advances a 64-bit generation and `MarkFirst(light)` reports first membership in expected O(1) time. Pointer identity is not persisted as a semantic renderer identity: a later query always has a different generation, and generation wrap clears the table before reuse. First-encounter output order remains traversal order because membership never reorders selected lights.

## Exact local-section fast path

The baseline remains `BSPWalkCircle`. A local candidate source is enabled only for an actor whose current `(query position, render radius, section, portal group)` has passed an exact qualification run.

Qualification is two-stage and fail-closed. First, the baseline walk must show that every touched subsector resolves to exactly the actor's current `FSection` and portal group. An empty walk, another section, or another portal group fails immediately. Second, during that same qualification query the accepted baseline selected sequence is recorded after the normal eligibility, portal-relative radius and PF-015 visibility tests. The local `section->lighthead` source is then passed through the same filter/visibility function with an independent generation set. Fast-path eligibility is persisted only when the two selected sequences are exactly equal by light identity, portal-group context, normal/subtractive/additive class and order.

The baseline result remains the rendered result during qualification. A mismatch therefore cannot affect the frame: it records a fallback and keeps future calls on `BSPWalkCircle`. This explicitly satisfies the recorded side-by-side comparison gate rather than substituting a geometric assumption for it.

A successful qualification is cached on the actor's existing renderer trace-cache state. Any movement/center change, render-radius change, section change, or portal-group change invalidates the key and forces baseline qualification again. Light movement does not invalidate the geometric single-section fact, while per-light current position, state and PF-015 world-query visibility validity remain evaluated on every query. Portal-relative light position is still computed at use time with `PosRelative(group)`.

This is narrower than a general section-local shortcut by design. Unsupported and boundary cases fall back instead of guessing.

## Diagnostics and verification

`stat actorlightquery` exposes cumulative baseline/local query counts, qualification passes/fallbacks, visited light-list count, candidate count, duplicate count, filtered count, trace count, and baseline/local/qualification elapsed nanoseconds. `stat actorlightcache` remains the PF-015 visibility-cache diagnostic.

The PF-016 compiled fixture pins generation reset/de-duplication, first-encounter identity/order, selected class/group comparison, portal-group qualification boundaries, empty/multi-section fallback, and dense duplicate equivalence. It also emits a dense synthetic sorted-vs-generation timing sample; wall-clock timing is evidence, not a correctness assertion, so CI scheduling noise cannot make the contract flaky. Source-contract tests pin the live side-by-side baseline/local comparison and fail-closed enablement.

## Provenance

The local-source concept is adapted from the recorded `MAD-VKDoom@2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5` research lead, but this implementation is independently bounded by ShadeDoomVK's PF-009/PF-011/PF-015 contracts. No donor source is cherry-picked and no unresolved donor portal assumption is imported.

## Local repair validation (2026-09-24)

The original PR head `90b8de0ac56fc2daa1bb22f0411a6f2d40b0f9a8` failed representative sprite-setup timing despite cheaper local queries than its own fallback population. The previous internal timing compared different actors and was not an end-to-end A/B. Current master `f7d531026de5bd33181946cd91040d5f54438103` has the same source tree as the historical baseline `31cf32b3995dbeabaeaaad02058b4c5de966410d`.

Actual Vulkan-path diagnostics found that the interior fixture already visits one section per baseline query: both revisions scan 179,928 candidates and pack 48,787 selected lights for 833 queries per frame. Warm visibility calls, duplicate rejections, allocations and fallback are zero. The original local path still performed 48,787 hash membership operations per frame without eliminating a duplicate. A hash-only ablation reduced setup cost but did not beat baseline; eliding only the proven-redundant qualified-local lookup did.

Five interleaved RelWithDebInfo pairs with identical frame-only logging produced per-run warm setup medians of 3.876270/3.881421/4.133544/3.886331/4.113935 ms baseline and 3.713339/3.730444/3.680725/3.732130/3.712254 ms repair. The median of run medians improves 4.45%, and every pair improves. Each sample uses frames 100–399. All five full 1904×1001 clean images are pixel-identical. Separate diagnostic binaries match 97,575 selected-identity/order/group/class and packed-light records at frame 200 in each of the interior and boundary fixtures, with identical full images. Pointer addresses are preserved as run-local evidence and normalized to explicit source-light semantics for cross-process comparison.

The boundary diagnostic still takes 440 BSP fallbacks and 393 local queries per frame, rejects the same 28,544 duplicates, and selects the same 48,787 lights. It also identifies 5,190 temporary selection-vector allocations (1,864,000 requested bytes) per frame in repeated fallback qualification. This repair does not change fallback qualification or its allocation policy. Portal displacement, PF-015 visibility/cache invalidation including moving occluders, light filtering and packing remain byte-for-byte unchanged. The local fixtures contain no portals and run `gl_spritelight=2`, so their zero CPU visibility calls are not presented as new live portal/occlusion coverage; those contracts retain their compiled/source regression coverage.

Raw logs, frame distributions, diagnostic patches/binaries, semantic state, settings/hashes and images are retained locally under `C:/ShadeDoomVK/pf-local-evidence/pf016/repair-20260924`. `analyze.py` reproduces `analysis.json`. Intrusive diagnostic stage timers are attribution evidence only, not acceptance timing. Full DBP50 MAP08 was not launched. PF-016 is not accepted or merged by this local record; uninstrumented validation and required CI remain separate gates.

### Uninstrumented confirmation

Implementation commit `c2684881a5b0c1b74cb361eced0c35b2ac17b90e` was rebuilt after commit. The final uninstrumented candidate executable SHA-256 is `7300e538f87ff34672172c67a374bea745d9759e6ba341e1af1fa9b3fc44e3de`; baseline is `7385754e18ac7a5bf7e043f610d8f7aae2ae1cb148396f4fb8fd0bc0c4af8ace`. Five uncontended, warm, interleaved confirmation pairs produced baseline `S: Setup` snapshots 4.609, 4.074, 4.234, 3.971, 4.137 ms and repair 3.854, 3.761, 3.715, 3.749, 3.781 ms. Medians are **4.137 / 3.761 ms (-9.09%)**, p90 4.459 / 3.8248 ms and p95 4.534 / 3.8394 ms. Every pair improves. All five full images are pixel-identical. These built-in snapshots are separate from the per-frame distributions above and are not interval averages or FPS-derived values.

The final confirmation excludes an earlier exploratory exact-build series that overlapped hash/image analysis; those raw runs are retained. All qualified launches exited 0 without timeout, fatal renderer log or new display-driver event. The local representative CPU/state/image gate is **PASS**. PR update and required CI were initiated only after this gate passed. PF-016 remains open, unmerged and not accepted; this documentation-only follow-up changes no renderer source from the tested implementation commit.
