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

The baseline and local candidate sources may not fork this logic.

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
