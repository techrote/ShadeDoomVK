# ShadeDoomVK — renderer knowledge / RAG index

**Purpose:** Retrieval-oriented architecture and feature notes for engineers and autonomous agents. Read these for ownership, terms, code navigation and known traps; **always inspect actual current source** before altering behavior. These are not substitutes for tests, merge status or issue acceptance.

**Baseline distinction:** Files 01–13 originated from the founding VKDoom source `09634479ab5bf9adf691074fffe85a006a398cd0` and have accumulated selective accepted source updates. Files 14–21 reconcile merged ShadeDoomVK features through `master@f787f7199fc7560588bb9440b3dd0aa663cb53de` (14 November 2026). Current feature notes do **not** implicitly refresh every historical assertion in 01–13.

## Renderer architecture and invariants (01–13)

| RAG file | Retrieve for |
| --- | --- |
| [01 — Renderer execution](01-RENDERER-EXECUTION-MAP.md) | Frame, view, pass and render flows |
| [02 — Identity / lifetime](02-RENDERER-IDENTITY-LIFETIME.md) | Resource identity, generation and ownership |
| [03 — LevelMesh mutation](03-LEVELMESH-MUTATION-MATRIX.md) | Invalidations, geometry and updates |
| [04 — Material contract](04-MATERIAL-SHADER-CONTRACT.md) | Semantic layer order, sampling, shaders and palette |
| [05 — Lighting / shadow](05-LIGHTING-SHADOW-TRUTH-TABLE.md) | Dynamic lights, actor/probe/shadow modes and fallbacks |
| [06 — Lightmap/probe pipeline](06-LIGHTMAP-PROBE-PIPELINE.md) | Bake, probe selection and resource publication |
| [07 — Portal spaces](07-PORTAL-COORDINATE-SPACES.md) | Mirrored/linked portals, geometry, camera spaces |
| [08 — Vulkan capabilities](08-VULKAN-PIPELINE-CAPABILITIES.md) | Descriptor, pipeline and hardware capability paths |
| [09 — Postprocess / HDR](09-POSTPROCESS-HDR-FUTURE-SEAMS.md) | Future seams, currently active versus dormant |
| [10 — Known traps](10-KNOWN-TRAPS-DORMANT-PATHS.md) | Hazards, unsupported routes, negative evidence |
| [11 — Observability](11-RENDERER-OBSERVABILITY.md) | Oracles, native observations, receipts |
| [12 — Upstream ownership](12-UPSTREAM-SYNC-OWNERSHIP.md) | Donor/sync constraints |
| [13 — Durable identity audit](13-DURABLE-IDENTITY-AUDIT.md) | Probe/atlas incarnation and #14 identity history |

## Current merged-feature supplements (14–20)

| RAG file | Merged PRs | Retrieve for |
| --- | --- | --- |
| [14 — Classic input importer](14-CLASSIC-INPUT-IMPORT.md) | #189 | Version-109 LMP commands played under current rules; lifecycle and admission |
| [15 — Doom II/DBP50 material showcase](15-DOOM2-DBP50-MATERIAL-FLASHLIGHT.md) | #190 | WAD-to-PBR PK3 generation, flashlight, gallery, exact game-art boundary |
| [16 — Sprite relief gradients](16-SPRITE-RELIEF-ALBEDO-SAMPLING.md) | #191 | Safe POM gradients and original alpha |
| [17 — Controlled 3D-floor lighting](17-CONTROLLED-3DFLOOR-LIGHTMAP-OWNERSHIP.md) | #192 | Source/facing keys, UV streams, v5 retention |
| [18 — Static bake and GPU intervals](18-STATIC-LIGHTMAP-COMMANDS-AND-GPU-TIMING.md) | #194, #202 | Commandlet fail-closed guards, opt-in Vulkan timing |
| [19 — Shadow-off scaling and spotlight](19-SHADOWOFF-LIGHT-SCALING-AND-SPOTLIGHT.md) | #193, #195 | Controlled measurements and normal-fragment spotlight optimisation |
| [20 — Portal float regression](20-REVERSE-PORTAL-NUMERIC-REGRESSION.md) | #199 | Local diagnostic float tolerance, no renderer change |

[21 — November closed-PR reconciliation](21-NOV2026-CLOSED-PR-RECONCILIATION.md) is the **nine-PR audit**, exact merge-status/source index, review caveats and acceptance-truth table.

## Source-of-truth and status vocabulary

- **Merged/in master:** source is present in the master commit; may still be opt-in, partial or separately gated.
- **active:** exercised by normal current runtime when configured/eligible.
- **opt-in:** implementation present, requires explicit CVar, content, command or feature mode.
- **partial/experimental:** supported subset only; later acceptance/performance gates open.
- **fallback:** deliberate compatibility route for missing, unsupported or disabled conditions.
- **dormant:** scaffolding exists but production does not use it.
- **proposed/unmerged:** owner-approved plan or candidate in separate PR, **not master**.
- **two normal execution environments:** CPU-only hosted assistants/GitHub CI use software Vulkan (lavapipe/llvmpipe); the owner plays and evaluates on actual Windows GPU hardware. Neither path is a substitute for the other, and ordinary local GPU use needs no ceremonial permission. See [15 November owner clarification](../LOCAL-GPU-WORKFLOW-20261115.md).
- **historical GPU fault record:** evidence of a prior specific incident, not a reclassification of today's ordinary GPU work.

## Editorial and maintenance rules

1. Change/reconcile the impacted RAG file **in the same implementation PR**; include the exact source symbol/path, invariants, fallback, verified tests and negative evidence.
2. Attribute claims to merged source, candidate source, author-reported physical result or new independent run correctly. A source diff alone is not a runtime quality PASS.
3. Preserve historical uncertainty and failed attempts. Never turn an opt-in/local WAD-derived asset into a supposed shipped default; do not redistribute game art.
4. Reconfirm active `master` and pending PR status before updating this index. [The Lost 2003 Remaster](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) is approved art direction on a planning branch, not auto-adopted CI policy.
