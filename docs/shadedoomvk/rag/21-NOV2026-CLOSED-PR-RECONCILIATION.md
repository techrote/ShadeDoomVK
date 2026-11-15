# 11–15 November 2026 closed-PR feature reconciliation

**Scope:** GitHub PRs in `techrote/ShadeDoomVK` with `closed_at >= 2026-11-11T00:00:00Z` and through the 15 November 2026 review. **Nine** returned; **nine merged**, **zero closed unmerged**. The reviewed integrated reference is `master@f787f7199fc7560588bb9440b3dd0aa663cb53de`. The art-direction reference is the [owner-approved 14 November Lost 2003 Remaster charter](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md), which is still on its own planning branch. All per-PR features below are in **master** unless marked otherwise.

**Evidence standard:** GitHub PR metadata, changed-file lists, targeted code patches, source-owned implementation notes and the current RAG index were read. CI and physical measurements are distinguished as *PR-reported evidence* unless this review independently executed them. **No new build, native engine run or physical GPU test occurred in this documentation-only review.**

**Retrieval queries:** November 2026 ShadeDoomVK recently merged, RAG refresh, feature inventory, PBR generator, demo input, POM relief, GPU timing, lightmap safety, portal precision, 2003 remaster.

## Closed/merged inventory

| PR / closure UTC | Merge SHA | What master gained | Correct classification |
| --- | --- | --- | --- |
| [#189](https://github.com/techrote/ShadeDoomVK/pull/189) · 12 Nov 10:57 | `00567bae465ab263b9ee9503cdf9c840c41d2028` | v109 classic LMP **input** importer with lifecycle restoration | User-visible, opt-in; **not vanilla sync** |
| [#190](https://github.com/techrote/ShadeDoomVK/pull/190) · 13 Nov 08:44 | `ffb679a955989c0eea7503cf15a60642d05990f2` | Local Doom II/DBP50 normal/PBR assets, flashlight and gallery | User-visible **opt-in asset workflow**, supported WAD hashes |
| [#191](https://github.com/techrote/ShadeDoomVK/pull/191) · 13 Nov 13:03 | `e4a3315f8b044fad97b78f627cb7c03a73c33163` | Correct POM original UV gradients / alpha-preserving displaced RGB | Shader correctness; parent relief remains gated |
| [#192](https://github.com/techrote/ShadeDoomVK/pull/192) · 13 Nov 18:28 | `f4546ee1d21a37473f0a3bc405949bc81253a811` | 3D-floor source/facing lightmap keys, vertices and retirement | Render ownership; retained v5 compatibility limitations |
| [#193](https://github.com/techrote/ShadeDoomVK/pull/193) · 13 Nov 18:29 | `43b9c84a704df1929ff58b3cc9ff79eac4a32f4f` | Exact partial **shadow-off** many-light measurement schedule | Measurement infrastructure, not rendering improvement |
| [#194](https://github.com/techrote/ShadeDoomVK/pull/194) · 13 Nov 18:30 | `d4f34dfdc5a7701ff47d8ea6dbdb14e45c824ffb` | Static bake progress and map-target fail-closed guards | Safety/correctness, not complete native bake acceptance |
| [#195](https://github.com/techrote/ShadeDoomVK/pull/195) · 13 Nov 18:30 | `2cc70f33295881f73c7460364c6fa8e4e546efb3` | Reuse spotlight direction in **normal fragment shader** | Narrow optimisation, not universal light scaling |
| [#199](https://github.com/techrote/ShadeDoomVK/pull/199) · 14 Nov 00:12 | `0ecba708e283e33c381fae329ace7a2cedc6a3f3` | Correct single-precision tolerance at reverse-portal test | **Oracle-only** fix, no renderer geometry change |
| [#202](https://github.com/techrote/ShadeDoomVK/pull/202) · 14 Nov 20:07 | `f787f7199fc7560588bb9440b3dd0aa663cb53de` | Opt-in lightmap/probe GPU interval and query lifecycle guards | Bounded instrumentation, physical acceptance held |

## Per-feature review and outstanding contracts

**#189 — Classic input:** Explicit `-playclassicinput` bypasses native FORM/ZDEM admission *only when requested*. Decoder validates all bytes first and owner-backed settings are restored on exit or interruption. Regression risk is latent game-state/CVar leakage at startup/transition; the PR's negative/transition tests target exactly this. No claim of original speedrun route synchronization. See [RAG 14](14-CLASSIC-INPUT-IMPORT.md).

**#190 — Local PBR, lights and gallery:** The generator does not auto-run when you launch a new build. It must match the source WAD identity, produce `DoomII-NormalPBR.pk3` / `DoomII-SpritePBR.pk3`, and load them with `Local-Flashlight.pk3`. Differentiated metallic/dielectric masks matter more than blanket shiny metal; retained original albedo and sprite outlines are deliberate. The PR-reported hardware smoke is bounded; absent generated packs explains a visually plain preview despite PBR renderer support. The screenshot-fixture Windows ZIP associated with the later **open** #212 should never be mislabeled a full nightly integration test. See [RAG 15](15-DOOM2-DBP50-MATERIAL-FLASHLIGHT.md).

**#191 — POM albedo derivative correction:** The original albedo and UV gradients are now evaluated before conditional marching; eligible displaced RGB uses `textureGrad` and retains original alpha. Source/compiled shader tests address undefined derivatives; full relief acceptability and physical cost remain open. #190's material generator does not yet create sprite height. See [RAG 16](16-SPRITE-RELIEF-ALBEDO-SAMPLING.md).

**#192 — Controlled 3D-floor identity:** Source plane, emitted facing, runtime slot and actual indexed vertex UV/page now agree. Runtime `FF_BOTHPLANES` tiles intentionally **cannot be serialized into historical v5** and require a new bake; don't describe this as full permanent lightmap support for every map. Portal/sloped/inverted cases still require qualified native coverage. See [RAG 17](17-CONTROLLED-3DFLOOR-LIGHTMAP-OWNERSHIP.md).

**#193 — Many-light protocol:** Fixes admissibility and custody of 1/64/256/256 **shadow-off** measurements. It does not unlock the shadow-on driver-risk workload, certify a light architecture or establish performance for PBR. Its 100 W numbers are historical measurements specific to its fixture, not general GPU benchmarks. See [RAG 19](19-SHADOWOFF-LIGHT-SCALING-AND-SPOTLIGHT.md).

**#194 — Static bake fail-closed:** Correctly errors if loading redirects/wrong entry is active, if Vulkan/lightmapping is off for a requested build, or if dirty work stalls. Dirty progress and 1,001-tile batches are verified by a compiled fixture. A source contract is not a full measured, saved, reopened and deleted native map. See [RAG 18](18-STATIC-LIGHTMAP-COMMANDS-AND-GPU-TIMING.md).

**#195 — Spotlight shader:** A normalized direction already computed in `lightmodel_normal.glsl` replaces redundant per-spotlight direction work, retaining smoothstep cone semantics. The PBR/specular paths and light selection do not change. Author-reported GPU `scene.immediate` improvement is approximately **4.8% dispersed / 7.0% overlapping at 256 lights**; dense-overlap remains slow. Do not convert this narrow statistic into a general frame-rate claim. See [RAG 19](19-SHADOWOFF-LIGHT-SCALING-AND-SPOTLIGHT.md).

**#199 — Reverse-portal tolerance:** Only a named oracle assertion changes, accepting float coefficient rounding for a specific authored receiver while preserving strict camera/identity and image/state controls. Not evidence of a portal renderer bugfix; no generic tolerance expansion. See [RAG 20](20-REVERSE-PORTAL-NUMERIC-REGRESSION.md).

**#202 — GPU timing:** Adds `-sdvkobservegpu` on a Vulkan lightmap commandlet and guards query reset, nested timestamp capacity and unsupported-GPU messages. Historical reported bake/probe measurements use an earlier executable; their raw hardware artifacts are not GitHub reviewer-accessible and **must not** be transferred as independent exact-head physical acceptance. #14 remains open. The earlier STOP language is a historical state at the PR #202 decision; subsequent 15 November owner direction authorises ordinary GPU-equipped local work. See [RAG 18](18-STATIC-LIGHTMAP-COMMANDS-AND-GPU-TIMING.md).

## Review findings in priority order

1. **P1 — Development-build composition gap:** PBR generator/flashlight from #190 are *merged and functional* but omitted by minimal SHADOW-001 CI packages. A future owner-evaluation candidate must explicitly generate/load supported user-local material assets and turn on compatible implemented quality features, while isolating diagnostic capture settings. A package that only proves one scene must identify itself as a fixture, never a complete devbuild.
2. **P1 — Branch-status truth:** [R-001 #211](https://github.com/techrote/ShadeDoomVK/pull/211) remains draft/unmerged. [SHADOW-001 #212](https://github.com/techrote/ShadeDoomVK/pull/212) is open/unmerged (GitHub draft flag may differ from its HOLD description); neither is a master feature. The approved [planning PR #210](https://github.com/techrote/ShadeDoomVK/pull/210) is also unmerged. New README must not silently adopt them as existing master defaults.
3. **P2 — Physical evidence precision:** #191/#193/#195/#202 mix CPU, llvmpipe and author-reported physical observations. Preserve exact build/device/workload/provenance; full #8/#9/#14 hardware acceptance, dense-shadow fault and reproducibility remain separately gated. Do not default hazardous shadow-on stress cases into a nightly.
4. **P2 — Persistence/compatibility:** #192's v5 `FF_BOTHPLANES` exclusion, #189's current-rules LMP divergence, and #190's exact-WAD identity are important *user-visible* boundaries that must survive retrieval and release notes.
5. **P3 — RAG index lag:** Existing 01–13 architecture notes are baseline-oriented. This audit adds feature/reconciliation documents 14–21, not a claim to have re-verified every historical RAG byte or all open PRs.

## Adjacent but outside the closure window

[PR #186](https://github.com/techrote/ShadeDoomVK/pull/186) (merged 7 November) supplies viewmodel lighting and gameplay-smoke foundations; read [SDVK-011](../SDVK-011-VIEWMODEL-LIGHTING.md). The owner-approved raster-first [campaign](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) provides artistic direction; it did not itself grant GPU permission at the time. The owner subsequently made normal GPU-equipped local use an explicit standing default on 15 November; see [current workflow](../LOCAL-GPU-WORKFLOW-20261115.md). [PR #210](https://github.com/techrote/ShadeDoomVK/pull/210), [#211](https://github.com/techrote/ShadeDoomVK/pull/211), and [#212](https://github.com/techrote/ShadeDoomVK/pull/212) were **open, not in the closed-PR set** at review.

**15 November owner operating clarification:** Hosted agents and GitHub CI should continue substantial CPU-only/llvmpipe software-Vulkan development and qualification, while the owner uses the actual GPU on their Windows machine for gameplay and visual evaluation. Do not mistake hosted frames for physical GPU performance or block the local evaluation behind generic historical STOP wording. Known fault-triggering stress cases remain individual engineering risks, not a blanket ban. [Current workflow](../LOCAL-GPU-WORKFLOW-20261115.md).

**Unchanged:** No PR was merged/closed/reopened by this documentation review. Master remains untouched pending an explicit future merge; this record and README live on a separate Draft documentation PR.
