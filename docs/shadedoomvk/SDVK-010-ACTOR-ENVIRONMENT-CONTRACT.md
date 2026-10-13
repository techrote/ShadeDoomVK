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

The positive fixture samples two distinct dielectric (zero-metallic/high-roughness) and metallic (near-full-metallic/low-roughness) actor cards near separate authored probe positions with non-neutral directional normal data, in the same map sector, with actual asymmetric normal-map/PBR semantic bindings; the no-probe `sprite-mirror` corpus asserts runtime zero. A compiled production-header C++ fixture qualifies deterministic movement within one sector, stable ties, radius boundary, mirror/portal grouping fallback, NaNs, stale indices and unrepresentable deltas.

## Evidence and explicit limits

A complete local `tools/check.py` gate passed on the worktree: PF contract tests (including PF-113 source hash), CFX tests, renderer-oracle fixtures, deterministic native-scene package preparation, repeated identical oracle outputs and four compiled contract fixtures. This is **CPU source/fixture qualification only**. No local Vulkan display/GPU result is attributed to this run. Hosted exact-PR build/source-evidence and software-Vulkan captured state/images remain the release gate.

The existing `sun-probes` recipe requests a sun and publishes probe resources, but does **not** run a full lightmap bake. Its configured `gl_levelmesh=false` and `gl_light_shadows=0` cannot by themselves qualify actual world-sun occlusion or linked-portal crossed-sector probe transitions. Those acceptance criteria must be qualified separately before final issue closure. The current fixtures demonstrate **boundary decision and emitted sprite consumer state**, not a physically measured light-leak fix. Performance and physical hardware modes remain unmeasured.


## 13 October 2026 — linked-portal transition qualification candidate

The dedicated `sdvk010-linked-portal-acceptance` lane now has bounded hosted-software evidence for the v1 conservative portal policy. This is **integration-ready evidence, not final SDVK-010 acceptance**: the independent sunlight/world-occlusion lane remains outstanding and final exact-head source/full CI is reserved for the combined acceptance PR.

The deterministic `portal-probes` fixture authors two closed rooms connected by a real bidirectional `Line_SetPortal` linked pair. The linked-group displacement is `[1024, 0]`; each room has a distinct authored probe/sector target, and three fixed PBR actor cards identify the before/on/after samples. The production selector itself is unchanged: because the level has multiple displacement groups, all three cards use `portal-sector-conservative`, including the same-group root draw. Authored ordinal 0 remains a valid live probe and is never conflated with PF-113 runtime descriptor zero.

Native evidence exposed an important PF-009/PF-010 distinction. A sprite rendered by recursive `LineToLine` portal traversal may have `throughPortalMode == 0`: the actor is processed in its destination source/render sector and portal group, while the **render context/viewpoint** already carries the linked displacement. The accepted before/on/after evidence is therefore:

- before TID 5100: sector 0, group 1, authored probe 0, runtime irradiance 267, root/main context at `[-320,0,64]`;
- on TID 5101: sector 1, group 2, authored probe 1, runtime irradiance 281, recursive `LineToLine` context depth 1 at `[704,0,64]`;
- after TID 5102: the same sector/group/probe pair as the on sample, under the same recursive portal-context transform.

For the recursive samples, source actor position and `HWSprite::Process` presentation position remain equal (`[1088,-24,0]` and `[1184,24,0]`). Requiring another per-sprite `-1024` translation would double-apply the portal transform. The state observer now records source/render sectors, actor TID, source/presentation positions, portal-group count and the selector's actual ambiguity predicate in addition to the previously accepted group/thruportal/sector-target/ordinal/runtime-pair/epoch fields. These fields are observation-only and do not alter portal geometry, selector policy, gameplay or descriptors.

Focused host controls additionally reject cross-group nearest substitution, wrong sector target, wrong `throughPortalMode`, an extra actor displacement, wrong/missing `LineToLine` context, double context displacement, authored-0/no-probe conflation, stale probe epoch, missing/reassociated transition samples, wrong group relation and runtime-pair substitution. The production-header selector fixture retains absent, stale/out-of-range, invalid-position and PF-113 runtime-zero fallback cases; no invalid GPU descriptor path is launched.

Exact substantive head `05f20e4f2856cb675f0cf286d08485869859ea8b` passed focused run [38446793761](https://github.com/techrote/ShadeDoomVK/actions/runs/38446793761): CPU/preparation contracts passed, the clean identified branch built on isolated 16-vCPU llvmpipe, two independent 240-warmup/one-retained-frame captures collected, and comparison passed with exact RGB equality (zero changed pixels). Both captures retained authored ordinals `0/1`, runtime irradiance pairs `267/281`, probe epoch `2`, and the same root/`LineToLine` transition state.

Fresh-process comparison keeps selected probe generation/epoch/span, actor/portal state and all non-floor material identities exact. For this fixture only, it excludes an observed run-local `SDVFL` bindless generation plus the manager-wide `TextureEpoch`: those values changed with unrelated texture retirement/reuse while every selected probe identity and the final RGB image remained identical. Regression controls prove probe or non-floor generation/epoch changes are **not** normalized. This is a bounded comparison rule, not a global weakening of SDVK state identity.

Retained native artifact `11839545833` has SHA-256 `4fa911972f9c3f626f78f605be7277a8100c85aae8d6aa431bbf99f4df3c8057`; its lossless evidence tar has SHA-256 `7118ac5aac3ccf4426fff2d2b17f4c9ca93b8dc793a99ab03a6d1978d3ac496c`. The CPU/preparation artifact is `11838308055` with SHA-256 `ce24d6c8360152ea34209f32ee1cc07541a447bced4a05b71d47c41481d68d68`. Machine-readable details are in [the linked-portal qualification receipt](evidence/SDVK-010-LINKED-PORTAL-QUALIFICATION.json).

This hosted software result establishes the bounded linked-portal actor/probe correctness claim only. It supplies no physical-GPU timing/stability claim, no new probe topology, no temporal blending, and no sunlight/world-occlusion acceptance.
