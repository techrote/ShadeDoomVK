# SDVK-010 — actor environment/probe qualification contract (v1)

Date: 10 October 2026. Owner: [SDVK-010 / issue #10](https://github.com/techrote/ShadeDoomVK/issues/10). Status: **implementation candidate; hosted/native qualification and final acceptance pending**.

## Existing authorities and reproduced deficiency

- SDVK-007 supplies the accepted final-quad sprite tangent frame for correct world-space normal-map PBR/specular response.
- PF-012 supplies authored light-probe positions, fixed sector/side targets, independent per-lightmap texel-to-live-probe mappings and the bounded 512-unit probe-map policy. It does **not** prescribe actor-card probe selection.
- PF-113 supplies the shader's exact zero-radiance fallback when neither an irradiance/prefilter pair nor a nonzero runtime descriptor is published. Both shader consumers use the same zero guard; no nearest-live substitution and no cubemap descriptor zero access are allowed.
- Existing `HWSprite::DrawSprite` took `actor->Sector->lightProbe.index`. Actors moving within a sector retained that sector-center target, even when a different authored probe was nearer. The Vulkan surface-uniform caller previously forwarded a negative/stale authored ordinal to a producer that can resize its bindless cache using an unsigned index. Both are source-proven failure modes; do not conflate authored ordinal 0 with runtime descriptor token 0.

## Explicit v1 sprite-card selection

1. For ordinary actor **sprite cards**, use the actor's current interpolated **source-level Doom XYZ** pose. Do not compare screen-space/projected card coordinates to untransformed level probe positions.
2. Read only `level.lightProbes` authored positions and ordinals. In a single unambiguous source/render portal group, choose the nearest finite matching-authored probe within an **inclusive 512-unit radius**; squared distances avoid `sqrt`; equal distances retain original level order. This deliberately reuses PF-012's bounded distance threshold but **does not** reuse its lightmap texel weights or descriptor indices.
3. If the level declares multiple displacement/portal groups, source/render portal-group provenance disagrees, or the PF-009 `throughPortalMode` is nonzero, do not choose an arbitrary cross-group XY-near probe. Preserve a **validated existing sector-target ordinal** for that actor, or fail closed. Until individual probes carry portal-group ownership, this is a compatibility fallback, **not a claim that sector target is always topologically correct for linked portals**.
4. Invalid/stale ordinal, absent probes, nonfinite position, far-away candidates and degenerate selection choose an *authored* sentinel **-1**. Valid authored probe **0** must remain distinguishable from absence.
5. `VkRenderState::ApplySurfaceUniforms` proves `0 <= authoredIndex < level.lightProbes.Size()` before calling the **unchanged PF-113-pinned** `VkDescriptorSetManager::GetLightProbeTextureIndex`. Absent/stale ordinals resolve directly to **runtime descriptor zero**, never to a massive cache allocation. A valid selected authored ordinal with missing/incomplete prefilter or irradiance also resolves to runtime zero through PF-113. The selector **does not** substitute another probe in this case.
6. Models retain the inherited sector probe policy. Non-actor sprite cards have no authored actor probe. Surface/lightmap/probe-map coordinates and shader bindings are unchanged.
7. There is **no temporal probe blending**. Transitions at nearest-cell and 512-unit boundaries are deterministic discontinuities. A later smoother must be independently specified/qualified, especially for portal and epoch identities. Each emitted card currently scans the authored candidate list (O(number of authored probes)); a CPU scaling/acceleration decision is separate.

## PBR, sunlight and visibility ownership

`lightmodel_pbr.glsl` retains PF-113 `SampleProbeIrradiance` and `SampleProbePrefiltered`, roughness LOD and the BRDF LUT. The SDVK-007 normal field is consumed without an additional shader tangent override. World-space sunlight and occlusion retain the accepted `HWDrawInfo::GetDynSpriteLightList` / `ActorTraceStaticLight::TraceSunVisibility` route, world query generation and portal-group correctness contracts; `shadowAttenuation` remains the PBR shader's existing direct-light policy. There is **no new shader lighting law, shadow proxy, probe blending or baked GI claim**.

## State-only, emitted-draw qualification

The existing SDVK-002 observer attaches `probe.actor_selection` to the *actual emitted Vulkan draw*, along with the actual submitted authored ordinal, runtime irradiance descriptor, observed bindless identity, published irradiance/prefilter counts and the probe-resource epoch. Provenance fields identify the selected source-world actor pose, candidate count, sector target, source/render portal groups, PF-009 through-portal mode, chosen distance, policy, and explicit fallback. Observer state is reset at draw scope and is default-off. No diagnostic controls renderer policy.

The strict validator rejects:
- invented source-coordinate systems, nonfinite source positions and invalid portal group claims;
- mismatch between selected ordinal and emitted draw uniform;
- selected ordinal outside the current candidate list, wrong portal fallback policy, or radius overrun;
- nonzero runtime descriptor with no authored probe; nonzero draw descriptor without a published pair and inconsistent resource identity;
- missing actual actor/PBR material witness in the full software-Vulkan corpus.

The positive fixture samples two distinct dielectric/metallic actor cards near separate authored probe positions, in the same map sector, with actual asymmetric normal-map/PBR semantic bindings; the no-probe `sprite-mirror` corpus asserts runtime zero. A compiled production-header C++ fixture qualifies deterministic movement within one sector, stable ties, radius boundary, mirror/portal grouping fallback, NaNs, stale indices and unrepresentable deltas.

## Evidence and explicit limits

A complete local `tools/check.py` gate passed on the worktree: PF contract tests (including PF-113 source hash), CFX tests, renderer-oracle fixtures, deterministic native-scene package preparation, repeated identical oracle outputs and four compiled contract fixtures. This is **CPU source/fixture qualification only**. No local Vulkan display/GPU result is attributed to this run. Hosted exact-PR build/source-evidence and software-Vulkan captured state/images remain the release gate.

The existing `sun-probes` recipe requests a sun and publishes probe resources, but does **not** run a full lightmap bake. Its configured `gl_levelmesh=false` and `gl_light_shadows=0` cannot by themselves qualify actual world-sun occlusion or linked-portal crossed-sector probe transitions. Those acceptance criteria must be qualified separately before final issue closure. The current fixtures demonstrate **boundary decision and emitted sprite consumer state**, not a physically measured light-leak fix. Performance and physical hardware modes remain unmeasured.
