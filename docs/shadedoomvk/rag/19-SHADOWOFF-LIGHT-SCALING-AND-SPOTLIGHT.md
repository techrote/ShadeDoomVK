# Shadow-off many-light measurement and spotlight-shader optimisation

**Authority:** [PR #193](https://github.com/techrote/ShadeDoomVK/pull/193), merged 13 November 2026 as `43b9c84a704df1929ff58b3cc9ff79eac4a32f4f`; [PR #195](https://github.com/techrote/ShadeDoomVK/pull/195), merged the same day as `2cc70f33295881f73c7460364c6fa8e4e546efb3`. Parent [SDVK-009/#9](https://github.com/techrote/ShadeDoomVK/issues/9) is **not physically accepted**; shadow-enabled dense failures remain separate.

**Retrieval queries:** spotlight attenuation, smoothstep, lightdir, 256 dynamic lights, many light scaling, scene.immediate GPU timing, 1025 shadow fault, 100W, dense overlap, physical stop.

## #193: a bounded measurement *protocol*, not a fast lighting engine

The retained `sdvk009-shadowoff-scaling` schedule compares **1, 64, 256 dispersed and 256 overlapping** authored lights at the same 1904×1001 effective extent, with `gl_light_shadows=0`, `vk_rayquery=false` and `gl_levelmesh=false` throughout. Two state/RGB captures per scene (eight total) precede 12 measured process runs in three balanced orderings, with 120 warmed and 120 measured frames each.

The purpose is a valid **shadow-off stratum**: distinguish ordinary light-loop cost from the separately hazardous dense-shadow workload. Four-scene source-content, image/counters, device, quality, events, timer query group and zero-retry identities are pinned. The independent supervisor must validate and lock reference receipts **before** timing begins, then retain raw distributions. It does not magically accept the engine architecture.

Primary sources: `tools/renderer_oracle/sdvk009_shadowoff.py`, `tools/physical_supervisor/{prepare,collector,registered,supervisor}.py`, `docs/shadedoomvk/SDVK-009-SHADOWOFF-SCALING.md`.

## #195: narrow normal-lightmodel shader correction

In `wadsrc/static/shaders/scene/lightmodel_normal.glsl`, the fragment shader already has normalized `lightdir`. The spotlight branch now directly computes `dot(lightdir, light.spotDir.xyz)` and applies the same existing `smoothstep(light.spotOuterAngle, light.spotInnerAngle, spotCosine)`. This removes redundant direction work **only for this normal-material fragment path**.

The change does **not** rewrite vertex, specular or PBR paths, alter light eligibility, enable tiled/clustered lighting, change shadow quality, or introduce a new global light-count budget. Exact offline opaque/alpha shader variants passed SPIR-V validation; the report states equal selected light/draw/descriptor state and exact cross-source RGB on the tested fixtures.

## Reported physical GPU scene intervals (not whole frame)

| Shadow-off active lights | Reported baseline GPU scene.immediate | #195 candidate |
| --- | ---: | ---: |
| 1 point | 0.523 ms | 0.518 ms |
| 64 | 3.341 ms | 3.314 ms |
| 256 dispersed | 19.282 ms | 18.364 ms |
| 256 overlapping | 24.088 ms | 22.407 ms |

PR #193 also reports CPU `RenderView` medians (0.140, 0.252, 0.513, 0.497 ms across those scenes). PR #195 reports **4.8%** and **7.0%** faster dense `scene.immediate` spans on the named GTX 1650 SUPER/100 W fixture. These are narrowly scoped, *author-reported* historical sequential measurements, not newly remeasured in this RAG reconciliation. `scene.immediate` excludes postprocessing and other work; no whole-frame speedup can be inferred. Dense-overlap remains slower than the 16.67 ms 60-FPS frame budget even in this GPU interval.

**Status truth:** shader optimisation and measurement harness are **merged**; general many-light throughput, PBR path optimisation, physical stability, shadow-on scaling and the 1,025-light driver-timeout root cause remain **unaccepted/held**. Preserve the original failed packets and separate acceptance limits. Under the owner's 15 November [local-GPU direction](../LOCAL-GPU-WORKFLOW-20261115.md), ordinary GPU game testing and profiling are expected; avoid blindly repeating the **specific** previously faulting many-light stress workload.

Cross-references: [lighting truth table](05-LIGHTING-SHADOW-TRUTH-TABLE.md), [historical shadow-off protocol](../SDVK-009-SHADOWOFF-SCALING.md), [campaign goal](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md).
