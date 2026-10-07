# SDVK-003 — pinned selective-upstream maintenance checkpoint

Date: 2026-10-07. Status: **partial implementation; broad differential and release acceptance not yet established**.

## Exact identities and lineage limits

| Source | Observed ref | Observation |
| --- | --- | --- |
| ShadeDoomVK | `master@a2d2d293d680895bb8daae86466596b05aaef483` | Branch starting point; accepted SDVK-001 foundation included |
| VKDoom | `nashmuhandes/VkDoom@09634479ab5bf9adf691074fffe85a006a398cd0` | Pinned upstream default-head, dated 2025-11-21; founding ShadeDoomVK ancestor |
| UZDoom | `UZDoom/UZDoom@809e46c25fe2a2f89430de3fbac89626100df384` | Pinned trunk tip, dated 2026-10-04 |
| GZDoom | `ZDoom/gzdoom@c26ce2e6ca2a0c770f140cb25dde0d30073ca8f7` | Pinned master tip, dated 2026-08-10 |

Reference URLs: https://github.com/nashmuhandes/VkDoom/commit/09634479ab5bf9adf691074fffe85a006a398cd0 ; https://github.com/UZDoom/UZDoom/commit/809e46c25fe2a2f89430de3fbac89626100df384 ; https://github.com/ZDoom/gzdoom/commit/c26ce2e6ca2a0c770f140cb25dde0d30073ca8f7 .

GitHub accepted a comparison of the founding VKDoom SHA against ShadeDoomVK's current master and returned changed source/build/docs entries, including `CMakeLists.txt`, `AGENTS.md` and the CI workflow. A direct UZDoom compare against the founding VKDoom SHA returned HTTP 404: **no common-ancestry or complete change-set conclusion follows**. This is not an exhaustive three-repository tree comparison. Full pinned file inventories, rename-aware trees and commit-by-commit provenance remain work to do before claiming acceptance.

## Evidence-led differential — inspected examples, not exhaustive findings

| Domain | Verified concrete observation | Policy / follow-up |
| --- | --- | --- |
| Engine compatibility / resource scripting | UZDoom tip commit `809e46c` alters Strife `crusader.zs`, `inquisitor.zs`, `sentinel.zs` guards. ShadeDoomVK's Crusader sweeps lacked a target-null precondition; UZDoom adds one before each aimed projectile. | Selectively adapt just the two missing guards. Existing Crusader choose guard and other actor files require independent equivalence checks, not a blind three-file transplant. |
| Renderer/Vulkan/backend | ShadeDoomVK's PF-002/003 identities, reserved bindless ranges and removed-slot neutral publication, PF-004 LevelMesh and PF-010 view identities are contract-owned. | Do not wholesale sync rendering files, shader layouts, Vulkan capability toggles or descriptor lifetime logic. Compare exact symbols plus PF tests and native gates before any proposal. |
| Platform/build | ShadeDoomVK changes `CMakeLists.txt` project identity to ShadeDoomVK and adds independent commit/version diagnostics and CI checks. GZDoom's observed tip `c26ce2e` edits `cmake/TargetArch.cmake` for e2k detection. | Classify architecture-detection patch as a potential platform donor, **not** imported; confirm target toolchains, feature scope and build gates first. Preserve SDVK-001 compatibility identifiers. |
| Security | UZDoom's null target guard prevents a scripted invalid-target call; author marks early-return semantics FIXME, not conclusive gameplay behavior. | Keep the defensive source delta narrow and establish runtime behavior/compatibility before declaring a security/correctness fix universally proven. |
| Material/shader/lighting | PF-008's existing per-layer sampling is not missing. PF-011, PF-113 and CFX-009 hardened lighting/probe/descriptor semantics. | Reject assumed 'new upstream wins' behavior. Require output/state and negative fixture equality. |
| Maintenance feature gap | UZDoom exposes `src/curl_loader.cpp/.h` in its pinned `src/` directory; ShadeDoomVK's pinned `src/` listing did not include them. | Treat as a *path-level difference only*, not proof of new functionality or transplant suitability. |

## Ownership classification

**Owned / high-risk (default do not import):** `src/rendering/vulkan/` and related GPU shaders/resource producers; material channel interpretation; descriptor identity/lifetime; LevelMesh/probe/lightmap indices; shadow/light selection; portal/view context; PF and CFX regression harness; `src/version.h`, `src/common/utility/gitinfo.cpp`, build-identity helpers, project CMake identity and compatibility resource/protocol names. This list is conceptual, not an assertion that all paths exist unchanged.

**Candidate syncable after demonstrated isolation:** targeted game scripting defect guard, individual protocol-independent parser fixes, non-renderer UI/localization, documented isolated portability/security checks, third-party build-tool fixes with compatible pinned dependencies. A syncable *class* is not approval for a particular patch.

**Conditional review:** gameplay/ZScript semantics (demo determinism and affected actor states), networking/saves, content resources, CMake/dependencies, Vulkan device/platform support, renderer interop. Require feature-specific owner and fixtures before transplant.

## Representative selective import evidence

Donor: UZDoom pinned head `809e46c25fe2a2f89430de3fbac89626100df384`, changeset modifies three Strife actor scripts. Recipient at branch base: ShadeDoomVK `a2d2d293d680895bb8daae86466596b05aaef483`; recipient file `wadsrc/static/zscript/actors/strife/crusader.zs`, original blob `daee0d2e9af96f83ab2b8088e396510e2e2cf156`.

Dry-run/mapping: compared the donor's patch and **actual recipient file lines**. Both recipient functions `A_CrusaderSweepLeft` and `A_CrusaderSweepRight` directly mutate angle and call `SpawnMissileZAimed(..., target, ...)` with no local target check. Anchors each matched exactly once; patch applies one `if (target == null) return;` ahead of mutation in each function. Donor's speculative `FIXME` comments are not copied: the source guards, not an unverified claim about gameplay correctness, are adapted. No other actor, resource, C++ or renderer file is imported. Recipient branch commit `2a9b95f32954b6dff8a32d7f37c4d479e6b0465f`, resulting blob `10ff41c18a8273d2f47cba2cef70aeb01111e2f1`.

This is an **actual narrowly adapted patch**, not a full upstream cherry-pick. Static anchor checks passed during application; an actor-level Strife runtime fixture is *not* established. Do not declare equivalent behavior under lost-target states until that fixture runs. Existing GPL/third-party notices are retained, and no donor license files are replaced. Need a focused final license/source audit before merging.

## Repeatable maintenance procedure

1. Monthly (or urgent security/compatibility incident), freeze exact recipient SHA, donor repo/ref/date, commit URL, parent/ancestry and exact file/tree digests; separately check lineage with Git rather than inferring ancestry from matching filenames. Reject inaccessible/re-written donors.
2. Produce domain-separated rename-aware changed-file and symbol reports for compatibility, backend/Vulkan, shader/resource, platform/dependencies/security, and renderer; include deletions, file-mode changes, generated assets and third-party license changes. Record counts, exclusions and missing history, never extrapolate from latest-commit examples.
3. Assign each change a named owner and verdict **already ancestral / owned-conflict / safe candidate / conditional / reject / unresolved**. Link PF contract and test oracles. Mark upstream supersession only if its fix demonstrably subsumes the recipient defect under the same constraints and negative fixtures.
4. For each approved candidate open a one-purpose branch from current master. Run `git merge-base`, `git diff --check`, `git apply --check` or a three-way dry run with explicit rejects, then inspect changed AST/symbols and license provenance. Do not use force application or silently resolve overlapping renderer hunks.
5. Import smallest patch with source SHA and adaptation explanation. Run `python3 tools/check.py --output build/pf-oracle` and the full Windows/Linux/macOS PR matrix. For actor changes, add a synthetic lost-target transition fixture and preserved ordinary attack/AI state; for renderer changes require the relevant PF/CFX oracle, exact pass/view/resource state assertions, baseline/negative image comparison and approved native GPU tests where the acceptance contract demands them.
6. Audit file lists for any removal or downgrade of VKDoom-specific features, shader resources, fallback capabilities, ZScript engine versions, config/save/demo/network signatures and license/copyright notices. On overlap with hardened contracts: stop, isolate, log a targeted issue and require independent equivalent-evidence review.
7. Merge after required checks plus independent review. Verify exact merge-tree, post-merge CI, provenance register, RAG and execution ledger. Record accepted/rejected candidates and next review date. Preserve declined donor patches without applying them.

## Open acceptance gaps

This checkpoint does not claim a complete VKDoom/UZDoom/GZDoom commit/file differential, renderer-feature preservation audit across donor trees, formal PF supersession mapping, isolated Strife runtime tests or completed full CI. Those must be completed before #3 may close. The branch/PR should remain open if any of these remain unresolved. No physical GPU tests were conducted in this step.
