# SDVK-010 — Probe/environment lighting qualification for actors

## Current disposition — 14 October 2026

**Software correctness accepted; issue #10 closed as completed.** PR #148 merged as
`6aadd8458773014e4333cf93cf4b4269ce5733b3`, exact tested tree
`c520fd111c8da5c6714c60a5bc256247e4569577`. Source run 38493635271 and normal CI
38493635327 passed; both new actor pairs and their real-record negatives passed.
[Final acceptance record](https://github.com/techrote/ShadeDoomVK/issues/10#issuecomment-6167916940).
The earlier candidate/pending notes below are history, not the current gate.
Downstream #11/#14 now consume this acceptance together with
[SDVK-009-SW](../SDVK-009-SOFTWARE-DEPENDENCY-AUTHORITY.md); Physical STOP remains active.

## Objective
Qualify actor/sprite environment lighting, sunlight and PBR IBL on top of PF-012's corrected/bounded probe plumbing and SDVK-007's accepted orientation basis.

## Scope / required work
- Consume PF-012 truth about sector/side probe targets, per-lightmap probe maps, probe-0 fallback and AABB integration; do not re-port ancestral probe features.
- Validate actor probe assignment/selection at sector/spatial/portal boundaries and during movement.
- Validate diffuse irradiance and prefiltered/specular response on semantic PBR sprite materials with orientation-correct normals.
- Validate sunlight diffuse/specular and world-occlusion interaction using accepted PF visibility semantics.
- Investigate/fix actor-specific abrupt transitions, light bleeding or stale probe identity exposed by deterministic scenes.
- Define explicit actor fallback when probes are absent, incomplete or disabled.
- Expose probe source/index/transition/fallback diagnostics.

## Non-goals
No foundational probe-map plumbing repair (PF-012), no complete lightmapper stress campaign (SDVK-014), no new GI claim, no viewmodel policy (SDVK-011).

## Dependencies
SDVK-002, SDVK-007. PF-012 is inherited via PF-020.

## Concurrency guidance
May overlap SDVK-008/009. SDVK-011 and SDVK-014 depend on its accepted actor/environment semantics.

## Required context
Read `AGENTS.md`, PF-012 evidence, probe/lightmap/portal/material RAG, SDVK-002/007 evidence and canonical body.

## Autonomous implementation prompt
Complete SDVK-010 autonomously. Start from corrected PF probe plumbing, qualify actor assignment/IBL/sun/occlusion/fallback on deterministic scenes, fix only demonstrated actor-environment defects, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Actor probe/environment response predictable/diagnosable and orientation-correct; boundary/portal fixtures have explicit expected assignment/transitions; sunlight/occlusion coherent; stale probe identity absent during rebuild/movement; fallback compatible; PR merged/verified.

## Verification
Move actors across sectors/probe boundaries/linked portals; metallic/rough/dielectric normal-mapped sprites; sunlight occlusion; probe absence/reset; compare diagnostics/images.

## Expected artifacts
Actor probe/environment qualification fixes/tests, transition/fallback contract, diagnostics, probe/material RAG and ledger updates.

## Blocking / stopping conditions
If PF-012 plumbing is found unsound, classify as foundational regression and block this issue rather than compensating in actor shading. Do not invent interpolation/blending aesthetics without a documented design decision.

## 10 October 2026 — implementation/qualification candidate

The dedicated branch `sdvk-010-actor-probe-environment` consumes accepted SDVK-007, PF-012 and PF-113 and defines its explicit [actor environment v1 contract](../SDVK-010-ACTOR-ENVIRONMENT-CONTRACT.md). The bounded source-space nearest authored-probe policy uses interpolated actor positions, a 512-unit radius and deterministic tie/fallback semantics. Linked/ambiguous portal group presentation remains conservative sector-target selection; invalid/unpublished indices yield zero IBL via the existing unchanged PF-113 producer. World/model, gameplay, sunlight tracing and PBR BRDF/binding semantics are not changed.

Positive/negative compiled fixtures, state-only emitted Vulkan draw diagnostics and new PBR actor/probe corpus controls are implemented. Full local CPU contract checks passed. **This is not issue acceptance**: exact-head hosted source/CI, live native `sun-probes` qualification, actual sunlight occlusion, linked-portal transition proof, release review and verified master are outstanding. Do not close #10 or claim general actor-environment correctness based on the preparatory checks alone.


## 13 October 2026 — parallel sunlight/world-occlusion lane

The isolated branch `sdvk010-sun-occlusion-acceptance` is based on verified `master@0b01f39f0249e2065e0bbee8c6a7f98ea90aba6f` and owns only the outstanding actor sunlight/world-occlusion gate. It adds a dedicated `SDVSOCC` fixture with matched PBR actor material/probe identity, a one-sided authored world occluder, state-only packed traced-sun provenance, strict PF-113 two-descriptor probe-pair identity, relative preregistered native image discrimination, and exact repeatability. Source review also found and narrowly corrects the demonstrated PBR omission of the already-accepted `LIGHTINFO_SUN|LIGHTINFO_TRACE -> traceSun` branch present in the normal light model.

The linked-portal transition lane remains independent. Do not close #10 or run the combined full CI from this sunlight branch alone. Physical STOP remains active and hosted llvmpipe results are correctness-only.


## 13 October 2026 — sunlight lane integration-ready

The sunlight/world-occlusion branch has completed focused qualification. Native run `38328713247` produced two retained independent lavapipe captures; both passed the actor/probe/sun/image assertions and had identical RGB. Its wrapper failure was isolated to process-local material/texture-manager generation labels in the generic cross-process comparator. Corrected offline revalidation `38444141252` passed with `state_equal=true`, `changed_pixels=0`, no new native execution, and retained artifact `11836882592`.

The lane is ready for integration with the separate linked-portal acceptance branch. Do **not** close #10 or merge this branch directly to master. The combined tree still needs the single normal required CI run after both lanes are integrated. Physical STOP remains active.

## 13 October 2026 — linked-portal acceptance lane integration candidate

The dedicated `sdvk010-linked-portal-acceptance` branch has completed its bounded linked-portal actor probe-transition scope on substantive head `05f20e4f2856cb675f0cf286d08485869859ea8b`.

Focused run **38446793761 PASS** established, on isolated hosted llvmpipe:

- a real bidirectional linked `Line_SetPortal` topology with distinct portal groups and sector probe targets;
- actual emitted before/on/after PBR actor draws;
- the v1 conservative sector-target policy with authored ordinals 0 and 1;
- distinct live runtime irradiance/prefilter pairs and stable probe epoch;
- root versus recursive `LineToLine` PF-010 context ownership;
- no cross-group nearest substitution and no double portal transform;
- deliberate host-side negative controls for portal mode/group/sector/sample/pair/epoch errors;
- two independent native captures with exact RGB equality and bounded semantic repeatability.

The native investigation corrected the **test oracle**, not renderer portal policy: recursive line-portal presentation may keep PF-009 `throughPortalMode=0` because the child view/context already carries the linked displacement. Requiring another actor translation would be a double transform.

This lane remains unmerged by design. Full repository source evidence/CI and final #10 closure are reserved for integration with the parallel sunlight/world-occlusion acceptance lane. Physical STOP remains active and no hardware-GPU claim follows.


## 14 October 2026 — combined integration gate

The two previously qualified lanes are combined on `sdvk010-integration-acceptance` from
`master@0b01f39f0249e2065e0bbee8c6a7f98ea90aba6f`. See the
[combined acceptance contract](../SDVK-010-INTEGRATION-ACCEPTANCE.md) for exact lane inputs,
conflict resolutions, preserved PF-009/PF-113 source boundaries and the fixed four-process plan.
Both actual actor scenes and copied-record negative controls now execute once in the existing
Avrea 16-vCPU software job, alongside the inherited required gates. Independent focused evidence
is not substituted for this exact-tree qualification. Keep #10 open until full CI/source evidence,
review and verified merge genuinely pass. #8/#9 physical acceptance remains held.
