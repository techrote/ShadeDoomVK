# SDVK-007 — final acceptance

Date: 2026-10-10. Issue: [#7](https://github.com/techrote/ShadeDoomVK/issues/7). Substantive PR: [#135](https://github.com/techrote/ShadeDoomVK/pull/135).

**Disposition:** The bounded sprite-only explicit tangent-basis implementation is accepted on the exact merged/requalified master tree. This document becomes the final programme record only after its separate documentation-only reconciliation PR passes checks, merges and the resulting master is verified.

## Identities and implementation contract

| Authority | Identity |
| --- | --- |
| Starting master | `cbff1d10b802e60a56d239338f810f7e1e52920d` |
| Final PR head | `a895dca0a5f356440f79f0631289d2862afe86f3` |
| Tested PR-head tree | `8afa7ce6267abdfe8740cc7de4a72e0e9d510661` |
| Substantive squash merge / exact master | `08ec183e665e7a3100b6cf3a267f5d3b5b494990` |
| Merged-master tree | `8afa7ce6267abdfe8740cc7de4a72e0e9d510661` |
| Tested == merged tree | **PASS** |

`HWSprite::CalculateVertices`' **final PF-009 sprite quad** and signed UV endpoints are the sole world-space basis authority. `HWSprite::CreateVertices` normalizes the right edge, orthogonalizes the negative down edge for up, and takes forward/normal as their cross product. Tangent follows `sign(ur-ul)`; handedness is `-sign(ur-ul)*sign(vb-vt)`. The shader reconstructs bitangent as `handedness * cross(normal,tangent)`. This incorporates Doom rotation, frame mirroring, actor X/Y flips, billboard/face-camera/wall/flat pose and roll/pitch *once*, using already-final vertices.

The two appended per-surface uniforms, `uSpriteTangent` and `uSpriteNormal`, preserve SDVK-005 height and historical fixed/custom descriptor bindings. Only normal-mapped sprite cards select this explicit frame; legacy normal/specular and PBR consumers share the resulting normal. No-map sprites, world surfaces, models, decals, LevelMesh and existing shader/material policy retain inherited routes. PF-010 line/plane mirror parity is independently diagnosed and **not reapplied** as another world-space tangent flip. Invalid/nonfinite/degenerate/nonplanar quads or signed UV spans disable the explicit path and fall back to the old derivative reconstruction. Draw-boundary state is cleared. See [pre-implementation contract](SDVK-007-BASIS-ARCHITECTURE.md).

## Acceptance matrix

- **Directional orientation:** the compiled production-header fixture exercises eight Doom rotations, yaw/pitch/roll combinations, horizontal flat sprite geometry, U/Y and combined flips, and intentionally asymmetric tangent-local normal components so incorrectly reflected X/Y lobes cannot pass accidentally.
- **Negative controls:** zero/invalid UV spans, collinear and nonplanar vertices, infinity, wrong but unit/orthogonal normal vectors, stale fallback axes, invalid mirror parity and PF-009/PF-010 source mismatch are rejected.
- **Actual Vulkan draw:** the read-only `sprite-basis` record binds a PF-009 final-quad source, independently expected tangent/normal and material identity to **submitted** Vulkan per-draw uniforms, not a merely proposed CPU buffer.
- **Lit native material cases:** `sprite-mirror` exercises actual asymmetric directional-normal and legacy normal/specular and PBR draws under per-pixel lighting, plus height-without-POM and no-normal-map controls. Source contracts preserve non-sprite and palette/translation paths.
- **Complete hosted native gate:** ten software-Vulkan scenes, including `sprite-mirror`, `material-stress`, `sun-probes`, dense lighting and `shadow-boundary`, run two independent state/image captures and comparison; native corpus/oracle state and image gates pass. No physical-GPU performance assertion follows.

## Exact qualification

| Tested tree | Renderer source evidence | Continuous Integration | Result |
| --- | --- | --- | --- |
| PR head `a895dca0...` | [38049863197](https://github.com/techrote/ShadeDoomVK/actions/runs/38049863197) | [38049863166](https://github.com/techrote/ShadeDoomVK/actions/runs/38049863166) | **PASS / 9 of 9** |
| Merged master `08ec183e...` | [38051697523](https://github.com/techrote/ShadeDoomVK/actions/runs/38051697523) | [38051697394](https://github.com/techrote/ShadeDoomVK/actions/runs/38051697394), attempt 2 | **PASS / 9 of 9** |

Retained artifacts and SHA-256 digests for both exact trees are in the [release receipt](SDVK-007-RELEASE-ACCEPTANCE.json). The merged native artifact is `11670441947` (406,683,267 bytes; SHA-256 `532dade0c0e0dd28b9962a0eb199ec9a3b7c33ef3227162dc46c7b1882282ae5`). Its PR-head counterpart is `11668954978`.

## Historical adverse evidence (not waived)

1. CI **38047322260**: a valid negative signed-U value was wrongly rejected by a generic nonnegative numeric parser. Repaired the validator boundary.
2. CI **38047456941**: an intentionally incorrect but normalized/orthogonal orientation was accepted. Added exact expected tangent/normal from PF-009 provenance and emitted-draw assertions.
3. CI **38047737451**: native PBR fixture used `ao` rather than actual `ambient-occlusion` semantic. Corrected the expectation without weakening it.
4. **Post-merge CI 38051697394 attempt 1** passed 8/9; Windows Debug `vktool.exe --version` timed out after 20 seconds, following a correct `vkdoom.exe` identity result. **Attempt 2** reran failed job `114218926544`, which passed **both executables** with exact commit `08ec183e665e7a3100b6cf3a267f5d3b5b494990` and clean working tree. Workflow conclusion is success (9/9). The failed attempt remains explicitly retained.

## Limits and dependent issues

This is sprite normal-map tangent correctness, **not** POM/relief, new probe/environment selection, projected shadows, many-light architecture, gameplay change, or general GPU performance. Software Vulkan is bounded correctness/repeatability evidence, not physical hardware qualification. No separate historical-master-versus-SDVK-007 full cross-tree pixel-diff campaign was performed. Degenerate cards retain fallback without claiming equivalent per-pixel normal quality; arbitrary third-party content and all portal modes are not universally pixel-qualified.

After the documentation-only reconciliation itself passes checks, merges and master verification, **#7 is accepted, merged, verified and closable**; **#8 / SDVK-008 and #10 / SDVK-010 become dependency-ready**, without prejudging their own scope. SDVK-009's physical campaign remains independent and open.
