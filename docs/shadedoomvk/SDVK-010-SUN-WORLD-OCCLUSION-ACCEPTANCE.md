# SDVK-010 — actor sunlight and authored world occlusion

Status: **candidate implementation; native acceptance requires retained hosted software-Vulkan proof**. This lane is independent of linked-portal transition acceptance and must not close issue #10.

## Authority and exact scene

Source: `master@0b01f39f0249e2065e0bbee8c6a7f98ea90aba6f`, issue #10, merged #137 and accepted PF-011/012/113 and SDVK-007 semantics. The separated branch is `sdvk010-sun-occlusion-acceptance`.

The new corpus recipe `sun-actor-occlusion` / map `SDVSOCC` is a distinct scene. Existing `sun-probes` and all portal fixtures are unchanged.

- 640×480, fixed camera `[-192,0,80]`, yaw/pitch/roll 0, FOV 90.
- Identical non-fullbright PBR dielectric `SDVOA0` actor cards TID 2020 and 2021; flat grey source RGBA, same authored tangent normal `SDVN`, same metallic/roughness/AO layers; no point-light confounder.
- Source positions `(0,-88)` (sunlit) and `(0,88)` (occluded), both in the same original sector and portal group.
- One authored probe at `(0,0,80)`. Both actual actor cards must bind authored ordinal **0** and the **same nonzero runtime irradiance + adjacent prefilter resource generation/epoch**; missing pair/runtime-zero is a failure, not a control pass.
- Authored ZDRayInfo 9890: azimuth 330°, pitch 45°, sunlight intensity 1. Its world-space direction is `[-0.6123724357,+0.3535533906,+0.7071067812]`.
- One-sided solid wall column `x[-96,-48], y[96,160]`, under a sky ceiling at world Z=256; the northern actor's ray passes the slab at y≈116–143, while the southern actor's ray passes at y≈−60..−33. Neither camera ray crosses the column at those X coordinates.
- Existing renderer modes: `gl_levelmesh=true`, `gl_spritelight=2`, `gl_light_shadows=2`, `lm_sunlight=true`, `vk_rayquery=false`. This selects the already-supported software geometry tracing route, **not** a physical ray-query or an invented sunlight algorithm.
- Two independent clean-state captures, each one retained state/image frame after the already established 240-frame startup warmup; no deliberate change to probe publication policy.

## Defect corrected

The PBR `ProcessLight` inherited special handling for the far-away synthetic sun proxy only bypassed local shadow maps. Although normal-light GLSL already traced `LIGHTINFO_SUN|LIGHTINFO_TRACE` through `traceSun`, the PBR shader never called that same world-geometry trace for the actor sun proxy. The minimal candidate correction calls the **existing** `traceSun(L)` for exactly that flag pair, before the unchanged local-light shadow attenuation branch. No PBR BRDF, probe lookup, sampler, normalization, shadow quality, local-light filtering, or portal policy is recalibrated.

## Provenance and limits

A state-only per-sprite counter is derived from the **packed sunlight proxy in the actual uploaded per-pixel light range**. At immediate Vulkan draw emission, the existing probe record now includes `actor_sunlight` (TID, packed sun count, traced-sun count, uploaded range/index and source/render group). Existing `actor_selection`, PF-113 irradiance descriptor identity/epoch, PBR material semantic bindings, real Vulkan pipeline shader shadow mode, resource sun direction/intensity, and LevelMesh generation join to this card.

This records the **requested** sunlight world-trace shader path, not a CPU prediction of per-fragment GPU visibility. The fragment result is supported separately by retained RGB from preregistered symmetric sprite-centre patches:

- southern/sunlit card: `(x=467,y=267,half-width=8)`;
- northern/occluded card: `(x=173,y=267,half-width=8)`.

The image test requires strictly greater **relative RGB sum** in the sunlit patch. No arbitrary absolute brightness margin is used. Every compared pixel is decoded through the existing PF RGB8 decoder; exact image/state repeatability follows the current native oracle contract. If these ROIs miss the actual card geometry or fail the relative sunlight test, **acceptance fails**; do not quietly retune the ROI on that same evidence to obtain a pass.

## Negatives and integration

The CPU contract rejects wrong sun ray, disabled world trace, changed actor/probe identity, invalid or stale descriptor generation, missing/misclassified packed trace and upload, absent/non-finite sun resource provenance, missing material, same/wrong image order, and modified preregistered ROIs. The native oracle fails closed on absent probe pair or world-mesh/shader route. CPU synthetic negatives only test the validator; they are not proof of an actual hardware shader result.

This lane does **not** change linked-portal sector-target/through-portal policy. The parallel portal transition branch remains a distinct SDVK-010 acceptance requirement. Keep both independent for the later single integration CI. Hosted llvmpipe correctness never grants physical GPU performance, architecture acceptance, or physical fault causality. **Physical STOP is active; historical root cause UNDETERMINED.**
