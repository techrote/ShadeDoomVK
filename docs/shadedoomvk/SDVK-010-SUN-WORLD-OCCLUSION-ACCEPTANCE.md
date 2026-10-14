# SDVK-010 — actor sunlight and authored world occlusion

Status: **focused software-Vulkan acceptance passed; integration-ready sunlight lane**. This lane is independent of linked-portal transition acceptance and must not close issue #10.

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


## Pre-native review hardening

Source review preserved the demonstrated PBR parity correction and found two evidence-contract defects before any native acceptance run:

- the dedicated `SDVSOCC` scene had inherited `SDVSUN` as its observed-map guard; this is corrected and catalog validation now requires every map guard to equal its authored map exactly;
- actor environment ownership now requires the emitted nonzero runtime descriptor base to equal the observed bindless resource index with **span 2**, explicitly covering the PF-113 irradiance base plus adjacent prefilter descriptor under one generation/epoch. Synthetic negatives reject wrong span and mismatched runtime base.

The focused branch qualification may therefore fail only on its actual source/build/native assertions; these preflight contract defects are no longer allowed to masquerade as sunlight results.


## First retained native packet and repeatability correction

Focused run `38328713247` completed **two independent native captures** before reporting failure. Each capture independently passed the scene/state assertions and the preregistered relative actor image test. Both final RGB images were bit-identical. The generic cross-process comparator failed only because the generated `SDVSKY` material's bindless generation label was 3 in the first fresh process and 4 in the second; the actor material `SDVOA0` remained generation 1 in both, and the authored probe pair remained runtime index 283 / generation 1 / epoch 2 / span 2 in both.

A proposed workaround that referenced IWAD `SKY1` is rejected because this authored corpus requires its scene textures to remain self-contained and must not introduce IWAD pixel dependence. Instead the generic comparator now canonicalizes **only material-resource generation labels**, bijectively per stable material/index/epoch/span. This preserves repeated/changed generation transition patterns and leaves every probe generation and all epochs strict. CPU negatives prove a changed material generation lifecycle still differs and a changed probe generation is never normalized.

The two original native captures are therefore revalidated offline under the corrected comparison rule; no second native execution is required or justified.


### Offline revalidation failure diagnosis

The first corrected offline revalidation still failed for one additional run-local field:
the renderer-owner `texture_epoch` was 3 versus 4. This is the texture manager's
absolute process-local invalidation generation; it tracked the same extra startup
texture retirement that produced the `SDVSKY` generation offset. The two captures
still matched on `probe_epoch=2`, lightmap epoch 4, async-upload epoch 1, LevelMesh
epochs, actor/probe pair generation/epoch/span, and exact RGB.

The comparator therefore canonicalizes the **texture-manager epoch label** bijectively
within each process, preserving its transition/aliasing pattern. Probe generations and
probe/lightmap/async epochs remain strict. A regression proves that an altered texture
epoch transition pattern still fails, as do changed probe generation or probe epoch.


## Focused qualification result

The bounded focused qualification is complete.

- Native run `38328713247` / job `115073297046` built the exact sunlight implementation on Avrea 16-vCPU with lavapipe only. CPU/source/negative controls, dependency setup, build identity and both independent native captures completed. Retained artifact `11781502590`, digest `sha256:f0323b3a4ef8c7a120ef245d575df192794c47a15dc55ee6853f37b6ad9fb8e9`.
- Both native captures independently passed the actor/probe/sun/image assertions and produced bit-identical RGB. The original wrapper reported FAIL only because the generic state comparator treated process-local material/texture-manager generation labels as cross-process semantic values.
- Offline revalidation run `38444141252` on the corrected comparator passed with `state_equal=true`, `changed_pixels=0`, and `native_execution=false`. Retained revalidation artifact `11836882592`, digest `sha256:07c75b22c8e6e07cc6bad47cde0168c4984e6c1f847bad9073db015bb8e6606e`.
- The comparator correction is narrow: material-resource generations and the texture-manager epoch are normalized bijectively, preserving transition/aliasing patterns. Probe generations, probe/lightmap/async epochs, LevelMesh state, stale/failure diagnostics and exact images remain strict.

No physical GPU execution occurred. This lane is ready to integrate with the separately qualified linked-portal lane; it is not an independent authorization to close #10 or merge directly to master.
