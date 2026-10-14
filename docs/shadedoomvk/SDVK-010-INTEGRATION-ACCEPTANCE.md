# SDVK-010 — combined actor environment acceptance

Status: **integrated candidate; exact-head required CI, review and verified merge are the acceptance gate**.
Issue: [SDVK-010 / #10](https://github.com/techrote/ShadeDoomVK/issues/10).
Physical STOP remains active. No physical-GPU performance/stability or historical-fault causality is claimed.

## Inputs and scope

The integration starts from `master@0b01f39f0249e2065e0bbee8c6a7f98ea90aba6f` and combines:

| Lane | Qualified handoff head | Scope |
|---|---|---|
| Sunlight/world occlusion | `564dd88c9dcca7023ad10014a82946b7ff097ed5` | PBR traced-sun parity, matched actor fixture, emitted sun/probe state and image oracle |
| Linked portal | `143288ef0cf26b6acdf6c446c35103c32596386a` | Existing conservative selector, source/presentation/context provenance, before/on/after oracle |

The focused evidence is historical input, not acceptance of the combined tree. Sun native run
`38328713247` and offline revalidation `38444141252`, and portal focused run `38446793761`,
are retained unchanged. The original PF-012/PF-113 producer, sampling helpers, zero fallback,
and PF-009 final-quad snapshot remain authoritative. No donor/transplant is introduced.

## Reconciled implementation

The shared emitted-draw observer carries both `actor_selection` and `actor_sunlight`. Portal
source/render sector bookkeeping lives on `HWSprite` outside the frozen PF-009 surface snapshot;
the exact historical snapshot and derived-region preservation checks remain unchanged. The
source/render sectors are passed explicitly to `ActorProbeSelected`, together with actor TID,
source/presentation positions and the existing ambiguity predicate. No selector or transform
policy is changed during integration.

The sole lighting correction is the sunlight lane's PBR parity fix: for the existing packed
`LIGHTINFO_SUN|LIGHTINFO_TRACE` pair, PBR calls the existing `traceSun(L)` before the unchanged
local `shadowAttenuation` rule. PF-113's irradiance/prefilter sampling functions and bindless
producer are byte-pinned as before. Its whole-shader source-preservation test now reverses only
the exact owned SDVK-010 sunlight delta before comparing with the retained original; adversarial
tests reject edits to that delta and unrelated direct/BRDF code.

Both fixture generators and typed assertion contracts are present. `sun-actor-occlusion` maps
to `SDVSOCC`; `portal-probes` maps to `SDVPRT`. Every supplied map guard must equal its authored
map. This fixed a stale `SDVSUN` guard inherited by the portal recipe without moving any actor,
portal, probe, sun ray, camera, image ROI or world occluder.

## Comparison contract

The two lanes previously used different cross-process resource-label policies. The integration
uses one narrower, scene-explicit bijection:

- `sun-actor-occlusion`: only the background `SDVSKY` material generation and texture-manager
  epoch labels are canonicalized by first-seen value;
- `portal-probes`: only the background `SDVFL` material generation and texture-manager epoch
  labels are canonicalized by first-seen value.

The stable material token still includes descriptor index, resource epoch and span. Observed
aliasing and generation/texture-epoch transition patterns remain significant. All other scenes
use the original projection unchanged. Actor materials, selected probe generation/epoch/span,
LightProbe/lightmap/async-upload epochs, portal and sunlight state, failures, stale rejects,
resets and exact RGB remain strict. No failed historical packet is rewritten and no absolute
label is interpreted as physical performance evidence.

The single retained frame cannot prove the absence of arbitrary pre-observation resource churn;
this is a scoped comparison of equivalent emitted actor state, not a general lifetime proof.
Compiled PF resource/fallback tests and the independent SDVK-009 publication gate remain required.

## Required combined hosted gate

`tools/renderer_oracle/sdvk010_acceptance.py` runs inside the **existing normal Linux software
Vulkan CI job** on `avrea-ubuntu-24.04-16-vcpu`. There is no duplicate runner, branch-only native
workflow or benchmark rerun. The preflight verifies exactly 16 allowed CPUs and a single CPU
llvmpipe device, explicitly selected lavapipe ICD, clean exact executable commit and authenticated
historical Freedoom 0.13.0 IWAD. Additional device/layer or CFX overrides fail closed.

The fixed serial plan is two fresh captures for `sun-actor-occlusion`, then two for
`portal-probes`. Each requests **640x480, 240 warmup frames, one retained state/RGB frame,
600 seconds per process**, no GPU timing, collision snapshot or publication witness. Each
capture must pass the actual emitted-state/image assertions. Four copied-record negative
controls are executed on each real retained capture. A pair must pass exact state and RGB
comparison before the next scene becomes eligible. Any failure stops dependent work; automatic
renderer retries remain zero. Failed capture/negative/comparison receipts are retained.

The normal inherited CPU/platform matrix, ten-scene native corpus and SDVK-009 four-process
publication gate still run and are not replaced by this actor gate. The actor evidence is
packaged as `renderer-sdvk010/` inside the normal lossless `renderer-software-vulkan` artifact.

## Acceptance mapping and limits

| Requirement | Combined evidence |
|---|---|
| Sunlight and world occlusion | Matched PBR/probe cards; one traced sun proxy each; supported world-trace shader; authored occluder; frozen relative image patches |
| Irradiance/prefilter identity | Nonzero selected runtime pair, PF-113 adjacent span 2, same live generation/epoch; inherited dielectric/metallic `sun-probes` coverage |
| Portal before/on/after | Real linked groups and distinct sector targets; actual source/presentation pose, recursive `LineToLine` context and single view displacement |
| Ordinal 0 vs runtime 0 | Production-header and validator absent/invalid/out-of-range/missing-pair negatives, plus actual live authored probe 0 |
| Orientation and lifetime preservation | Existing SDVK-007/PF-009 fixtures; unchanged snapshot derivation; strict actor/probe generation and failure state |
| Repeatability and negative sensitivity | Two independent captures per scene, exact RGB/state, copied actual-record negatives and CPU mutation tests |
| Repository acceptance | Required exact-head source evidence + full CI, review, merge and exact-master verification |

The portal fixture samples fixed positions in actual linked views; it does not claim temporal
blending or continuous gameplay path testing. No full lightmapper convergence/stress campaign,
probe ownership redesign, viewmodel policy, physical-GPU qualification or scaling acceptance
belongs to this issue. The fixed state/image tests supply bounded correctness, not proof of all
possible scenes. #8/#9 physical gates remain held; #11/#14 still need their separate #9 dependency
authority decision even after #10's actor semantics are accepted.

## Integration result recording

This document is prospective for the combined tree. Exact tested authored/merge/master SHAs,
source and software artifact digests, run conclusions, review and issue disposition must be
recorded on the integration PR and #10 after the required checks complete. Do not infer acceptance
from a green focused lane, a source-export job, or this document alone.
