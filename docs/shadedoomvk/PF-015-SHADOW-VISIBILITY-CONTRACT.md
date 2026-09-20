# PF-015 shadow selection and visibility-cache contract

Status: implementation contract for PF-015 / #32.

## Shadow-map capacity and selection

The inherited dynamic 1D shadow map has 1024 rows and PF-015 does not change that capacity, resolution, filtering or shadow algorithm.

`CollectLights` first gathers every active `shadowmapped` dynamic light. If the eligible count is at or below 1024, the vector is left in inherited linked-list traversal order. That preserves the previous selected set and row assignment exactly for workloads that fit.

Only overflow invokes `HWSelectShadowCandidates`. Its primary relevance key is squared Euclidean distance from the interpolated central main render viewpoint established by `R_SetupFrame`. Stereo eye offsets are deliberately not used because the shadow map is generated once before the per-eye loop. Secondary key fields are light position and authored/render light semantics; they make equal-distance ordering independent of linked-list traversal. Candidates with an exactly equal full key are a selector-semantic equivalence class and `stable_sort` may retain their incoming relative order.

The first 1024 ordered candidates receive shadow rows. Remaining candidates retain the inherited no-shadow-map sentinel and continue through existing non-shadowmapped lighting behavior; PF-015 does not drop the light itself.

Diagnostics expose total linked lights, eligible candidates, selected rows and overflow drops through the existing `stat shadowmap` surface.

## Actor/static-light visibility cache

The cached `ActorList`/`ActorResult` visibility result remains per actor/per light. PF-015 does not replace the cache or actor-light gathering algorithm.

A cached result is reusable only while these trace inputs are equivalent:

- actor position (including the inherited dynamic-lightmap-sector forced refresh);
- PF-004 `LevelMeshMutationEpochs::Query`;
- stable portal-group coordinate context;
- dynamic-light state (`light->updated` remains an explicit per-light invalidator).

`sun_trace_cache_t` now records the accepted PF-004 query epoch and portal group next to its position/result state. When the LevelMesh query epoch advances, a stationary actor/light pair is forced through the existing LevelMesh trace again, so moving sector/polyobject/world occluders cannot leave a stale visibility answer. Sun traces also reject stale query epochs.

PF-010 `HWRenderContext` `epoch`/`identity` are intentionally **not** cache keys. They change for each render invocation/pass even when the world-space trace inputs are identical and would therefore globally defeat cross-frame reuse. PF-010 remains the pass-identity seam; PF-015 uses the stable portal-group displacement context that actually participates in actor/light spatial equivalence. A future consumer whose trace genuinely depends on additional PF-010 pass state must add that state explicitly rather than keying this cache on transient identity by default.

`stat actorlightcache` exposes cumulative hits, misses and actor/world-query/portal/light invalidation reason counts plus sun-cache hits/misses.

## Preserved behavior

PF-015 does not change dynamic-light eligibility, attenuation or PF-011 calibration, shadow texture capacity/resolution, ray-query capability routing, LevelMesh mutation ownership, actor-light duplicate gathering, portal transforms, sprite/material/palette/translation semantics, gameplay/tic state, audio or donor/source provenance.

## Verification contract

The PF oracle includes:

- below-cap and exactly-1024 order-preservation cases;
- >1024 reversed traversal with identical selected semantic set;
- view movement changing the relevant overflow set;
- equal-distance semantic tie ordering;
- stable cache hit;
- PF-004 query-epoch invalidation with stationary actor/light;
- portal-group invalidation;
- actor-position and light-state invalidation.

The source-contract test also pins the production wiring and diagnostics. Full inherited Windows/macOS/Linux build CI remains required before merge.
