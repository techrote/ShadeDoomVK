# SDVK-007 — sprite tangent-basis final acceptance

Date: 2026-10-10. Issue: #7. **Status: PENDING exact merged-master CI and acceptance-reconciliation checks.** This is a provisional record; it does not close #7 or unblock SDVK-008/010 until the remaining gates pass.

## Authority and exact identities

- Starting verified `master`: `cbff1d10b802e60a56d239338f810f7e1e52920d`.
- Substantive implementation PR: [#135](https://github.com/techrote/ShadeDoomVK/pull/135), branch `sdvk-007-explicit-sprite-tangent-basis`.
- Final implementation head: `a895dca0a5f356440f79f0631289d2862afe86f3`.
- Exact tested PR merge-ref: `880e0f0bc2d92656e3c2c562267c750aa5b79e6a`.
- Exact tested and merged tree: `8afa7ce6267abdfe8740cc7de4a72e0e9d510661`.
- Substantive squash merge: `08ec183e665e7a3100b6cf3a267f5d3b5b494990`.
- **Tested-tree equals substantive merged-master tree: PASS**, by Git tree SHA equality.
- Final acceptance-reconciliation PR: pending publication of this record and the JSON receipt.

## Accepted implementation candidate

The authoritative sprite-space TBN is `sdvk-007-final-quad/v1`. The design/negative baseline was recorded **before production changes** in [SDVK-007-BASIS-ARCHITECTURE.md](SDVK-007-BASIS-ARCHITECTURE.md). In shader-world XYZ, the final PF-009 quad yields unit `right`, `up` and `forward = cross(right,up)`. Signed final `ul/ur/vt/vb` yield `T = sign(ur-ul) * right`, `B = -sign(vb-vt) * up` and `handedness = -sign(ur-ul) * sign(vb-vt)`. GLSL reconstructs B as `handedness * cross(N,T)`; the normal map retains its inherited unsigned decode and green inversion.

The final PF-009 vertices include Doom frame rotation selection, frame mirroring, actor/visual-thinker X/Y flips, face/XY/face-camera policy, wall/flat surface mode and inherited camera-facing/roll/pitch/isometric transforms. No shader-side reinterpretation of those inputs and no vertex, UV, alpha or actor/gameplay transform rewrite occurs. PF-010's line/plane-mirror XOR is a separate **view** parity; it must not double-reflect an already-world-space sprite TBN. `viewParity = handedness * (portalMirrored ? -1 : 1)` is inspected only, never used as an extra transform.

The basis enters the actual normal-map shader through two appended per-draw `SurfaceUniforms` vec4 values, after the existing SDVK-005 height ABI fields. A valid sprite card selects the explicit TBN; non-finite/degenerate/nonplanar sprite quads take the documented inherited derivative fallback. Clearing at sprite and state-reset boundaries prevents leakage into models, other geometry and other views. The existing world/model/voxel/LevelMesh tangent paths are not redesigned. No default height sample, POM, relief or displacement is introduced. Existing custom shader and semantic-material bindings, palette and translation behavior remain authoritative.

## Actual native directional evidence

Full final-head software Vulkan CI **run 38049863166** passed **9/9**. The native artifact is **11668954978** (406,685,258 bytes, ZIP SHA-256 `8529d0e157a91ad59430081e57b2c2bd2d6fa24eb58ffc23a443c408104aef95`). All ten full state/image scenes passed their **two independent captures plus comparison**; timing controls passed. `sprite-mirror` uses asymmetric RG normal-map pixels, eight rotation placements, paired-frame mirroring, wall and flat actors, independent X/Y flips, a line mirror and one fixed coloured point light with per-pixel sprite lighting mode 2.

Each of the two native `sprite-mirror` captures observes **30 actual emitted sprite-basis draws**, all 30 explicit/valid: 26 Y-axis face, two wall and two flat; 15 mirrored-context and 15 ordinary-context draws; six mirrored-frame, eight effective X-flip and two effective Y-flip draws. Frame state reports one active light and 30 actor-light selections. Seven `SDVRA1` legacy normal/specular draws use shader model 3 and height binding 6; two `SDVPA0` PBR draws use shader model 4 and no height; two `SDVLA0` legacy no-normal-map draws use shader model 0. All have an emitted Vulkan light-range index, not merely a material declaration or offline tangent.

The two observed `sprite-mirror` PNGs are identical (640×480, decoded RGB SHA-256 `41dc7f2658bdfc4748cde153a0c1f67c13c3540f937fac879f3dea9be2adf14a`, 0 changed RGB pixels). Exact per-capture source JSON and image file hashes, mirror matrix and shader/material witness counts are in [SDVK-007-NATIVE-STATE.json](SDVK-007-NATIVE-STATE.json). This paired software-renderer result is correctness/repeatability evidence, **not physical-GPU performance evidence**.

The compiled adversarial basis fixture covers yaw rotation in eight steps, independent U/V flip signs, double flips, mirror parity XOR, face/wall/flat final-quad modes, pitch/roll 3D rotations, nonplanar/collinear/nonfinite/UV-zero negatives and deterministic repeatability. PF-009, PF-014, material/height, custom shader, render-context/portal and PF-013 indexed fallback contracts run in the complete CPU oracle. The native fixture does not separately capture a camera-facing pitched/rolled actor or a nested plane-mirror view; those paths inherit the same final-quad derivation, with focused CPU PF-009/PF-010 and signed-mirror contracts rather than a claimed independent native image.

Legacy no-normal-map behavior is protected by unchanged GLSL no-NORMALMAP branch and material bindings plus the current-tree native no-map control; a **historical-master cross-tree pixel diff has not been performed and is not claimed**. Non-sprite equivalence is protected by explicit enable/reset source contracts and repeated whole-corpus state/image results, not a claim that all physical driver behavior was exercised.

## Exact PR-head source/CI evidence

- Renderer source evidence **run 38049863197: PASS**; source ZIP artifact **11668818325** (148,534,137 bytes), SHA-256 `1ee60659340a0cbf314f3e98df7cf40866e1f2aece0cbce3345609fb832e7d6f`; verified `source.bundle` SHA-256 `672c74c732d744ff590fc7088da0f52a20099069dcb1890a8ca793042bd45aa8`.
- Continuous Integration **run 38049863166: 9/9 PASS**. CPU artifact **11668953116** (74,433 bytes), ZIP SHA-256 `a2dc5926a03f46bcf3ee9a07a2404b424529f83b5480486fc87a2b6c70afe7eb`. Native artifact above. All platform build variants passed.

## Exact post-merge evidence (pending final CI result)

- Merged `master@08ec183e665e7a3100b6cf3a267f5d3b5b494990`, tree `8afa7ce6267abdfe8740cc7de4a72e0e9d510661`.
- Renderer source evidence **run 38051697523: PASS**; source ZIP artifact **11669274109** (148,521,374 bytes), SHA-256 `732a473d93bbc14487e22b4bcb3006376473a4225997cc257120864132e75eec`; verified `source.bundle` SHA-256 `c8e065afa8e6c6b0227387ea942b6e4232b1a7ad057af6a6d4c6fdcdc71773ae`.
- Continuous Integration **run 38051697394: in progress** at this draft checkpoint. CPU oracle: PASS. Full job and native checks, artifacts/hashes and final disposition must be reconciled before this document changes to ACCEPTED.

## Retained adverse evidence and repair

- CI run **38047322260**: a new signed-orientation validator incorrectly called a generic `minimum=0` numeric helper for legitimate `-1` tangent/UV handedness values; corrected signed bounds, retaining the negative test.
- CI run **38047456941**: an adversarial wrong-normal case was orthogonal/unit-length and escaped the first validator. Repair records the source PF-009 expected axes and verifies actual emitted Vulkan uniforms against them, instead of treating a plausible orthogonal frame as orientation proof.
- CI run **38047737451**: 8/9 jobs passed; the one software-Vulkan failure retained both `sprite-mirror` captures because the newly authored PBR test demanded semantic name `ao` while the real GLDEFS material correctly published `ambient-occlusion`. Original native ZIP artifact **11668782676**, SHA-256 `843046c4a824f981399f2e07766d2002f2934c9dad28f685a24d1ba114121674`; corrected the *test oracle*, not production semantics. That retained packet already proved 30 correctly bounded emitted sprite basis records.
- Intermediate CI runs cancelled by concurrency after newer commits superseded them are **not** qualification passes. No failed result was waived.

## Scope and downstream gate

Physical-GPU-qualified: **false**. No performance or driver-speed claim. No POM, height relief, many-light architecture, actor IBL/probe policy, projected sprite shadows, quality tiers, global world/model tangent rewrite or gameplay behavior change. PF-009 and PF-010 remain canonical. No external donor code was imported.

On final merged-master source/CI verification and checked-in receipt reconciliation, SDVK-007 can be accepted and #7 closed. Only then do **SDVK-008 and SDVK-010** become dependency-ready; SDVK-009's independent physical-GPU campaign does not block #7.
