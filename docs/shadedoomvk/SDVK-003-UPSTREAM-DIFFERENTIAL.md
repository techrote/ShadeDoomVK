# SDVK-003 — pinned upstream differential and selective maintenance policy

Date: 2026-10-09. Owner: SDVK-003 / #3. Status: **accepted, merged and verified** through PR #122 / `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`; the accepted policy is present on verified current `master@a05743fb428c0d7c66defccfb577834d012b4e31`.

## Exact pinned identities

Comparison authority is accepted ShadeDoomVK `master@1ecc3cf73aa2266a1e741f09078b7d089ba8bf89` after SDVK-002 integration. All four recursive Git trees were complete (`truncated=false`).

| Line | Commit | Tree | Blobs |
| --- | --- | --- | ---: |
| founding VKDoom | `09634479ab5bf9adf691074fffe85a006a398cd0` | `f4bd8b126a7014df24812c735db57c7ecdc4b8e9` | 6783 |
| UZDoom trunk | `809e46c25fe2a2f89430de3fbac89626100df384` | `8b2c774dd44ab9d09d06fdd5c652f2797121fad0` | 11850 |
| GZDoom master | `c26ce2e6ca2a0c770f140cb25dde0d30073ca8f7` | `48e75d844b8f305e7752d0892aebf2f1b3128e48` | 7917 |
| ShadeDoomVK master | `1ecc3cf73aa2266a1e741f09078b7d089ba8bf89` | `d12e07da15cccddc7f699c140911a5a6f852c4aa` | 7261 |

The machine-readable receipt is [`evidence/sdvk003-upstream-tree-differential.json`](evidence/sdvk003-upstream-tree-differential.json). It compares exact path/blob identities against the founding VKDoom tree and deliberately does not guess renames or semantic equivalence.

## Exact tree deltas

| Compared with founding VKDoom | Added | Deleted | Modified | Identical path+blob |
| --- | ---: | ---: | ---: | ---: |
| UZDoom | 8260 | 3193 | 1530 | 2060 |
| GZDoom | 1331 | 197 | 697 | 5889 |
| ShadeDoomVK | 478 | 0 | 86 | 6697 |

Recipient-owned paths overlap 86 UZDoom deltas and 79 GZDoom deltas. UZDoom overlap contains 51 renderer and 8 shader paths; GZDoom overlap contains 47 renderer and 8 shader paths. 79 recipient-owned paths differ in both donor trees.

Several VKDoom capability paths used and hardened by ShadeDoomVK have no blob at the same path in either pinned donor tree: `vk_lightmapper.cpp`, `vk_lightprober.cpp`, `hw_lightprobe.cpp`, `hw_levelmesh.cpp`, `vk_descriptorset.cpp`, the lightmap copy shader and the VKDoom PBR scene shader. This is path-level evidence only; it does not claim an equivalent donor feature is absent elsewhere. It is enough to reject wholesale tree replacement because equivalence is unproved.

## Domain differential and dispositions

### Compatibility / scripting / resources

The UZDoom tip adds target-null guards around Strife aimed-missile calls. ShadeDoomVK inspected the recipient body and adapted only the two missing Crusader sweep guards. Donor FIXME prose and unrelated actor-script changes were not copied. Other gameplay/ZScript/resource deltas remain conditional: demo/gameplay determinism, state transitions and content compatibility require focused fixtures before import.

### Vulkan / renderer / shaders

Renderer overlap is recipient-owned conflict by default:

- descriptor publication/lifetime: PF-002, PF-003 and CFX-009;
- LevelMesh identity/mutation/upload: PF-004 and PF-005;
- material sampling/GLDEFS/shader semantics: PF-008 and PF-113;
- render context/portal identity: PF-010 plus SDVK-002 observation;
- lighting/probe/lightmap paths: PF-011, PF-113 and the PF freeze;
- shadow/light selection and reuse: PF-015 through PF-019;
- renderer evidence/source identity: SDVK-002.

**No pinned upstream renderer change is declared to supersede an accepted PF/CFX repair.** Same-path difference is evidence of conflict, not superiority. A future renderer transplant must be isolated in its own issue and prove equivalent-or-better invariants with the owning regression gates.

### Platform / build / security

CMake/project identity, version metadata, CI and compatibility identifiers are owned through SDVK-001. Donor build/toolchain changes may be reviewed individually but may not overwrite those identities. GZDoom's pinned e2k architecture change is a potential portability donor, not imported here.

UZDoom carries security/build/dependency and asset-license changes. Its root license calls out branding, `wadsrc_bm`, `wadsrc_extra` and `wadsrc_widepix` exceptions; the adapted `wadsrc/static/zscript/actors/strife/crusader.zs` path is outside those named exception directories. This PR imports no asset, binary, dependency or license file.

## PF ownership / sync matrix

| Surface | Policy | Required gate |
| --- | --- | --- |
| descriptors, Vulkan resource identity, LevelMesh | **owned / stop on overlap** | PF-002/003/004/005 + CFX where relevant |
| materials, GLDEFS, scene/lightmap shaders | **owned / stop on overlap** | PF-008/011/113 + state/image evidence |
| portals/view/pass identity | **owned / stop on overlap** | PF-010 + SDVK-002 observer |
| lights/shadows/probes | **owned / stop on overlap** | PF-011/015/016/017/019/113 |
| project/build/version compatibility identity | **owned** | SDVK-001 identity/build checks |
| isolated ZScript/parser/compatibility fixes | **candidate syncable** | focused positive+negative fixture + full CPU/build CI |
| isolated platform/toolchain fixes | **conditional** | affected platform build + identity audit |
| donor assets/libraries/dependencies | **conditional/high provenance risk** | license/provenance + dependency review |

The durable RAG policy is [`rag/12-UPSTREAM-SYNC-OWNERSHIP.md`](rag/12-UPSTREAM-SYNC-OWNERSHIP.md).

## Representative selective import

Donor: `UZDoom/UZDoom@809e46c25fe2a2f89430de3fbac89626100df384`, `wadsrc/static/zscript/actors/strife/crusader.zs`.

Recipient base: `a2d2d293d680895bb8daae86466596b05aaef483`. Adaptation commit: `2a9b95f32954b6dff8a32d7f37c4d479e6b0465f`.

Only `A_CrusaderSweepLeft` and `A_CrusaderSweepRight` gained a local `target == null` early return before angle mutation and `SpawnMissileZAimed`. The focused CPU regression verifies guard ordering, preservation of the ordinary attack body, exact evidence pins and fail-closed renderer policy. Hosted builds compile/package the resource. This is the representative selective import required by #3, not general UZDoom synchronization.

## Repeatable maintenance procedure

1. At least monthly, and immediately for relevant security/compatibility advisories, pin recipient and donor commit/tree identities.
2. Fetch complete recursive trees and record exact path/blob deltas. Treat rename/semantic equivalence as a separate source-history question.
3. Classify each candidate as **ancestral/already present**, **recipient-owned conflict**, **candidate syncable**, **conditional**, **reject**, or **unresolved**.
4. For owned renderer overlap, stop unless a focused issue supplies equivalent evidence against the owning PF/CFX/SDVK contracts.
5. Inspect exact donor commit/files/license and adapt the smallest coherent hunk on a dedicated branch. Never force-apply or silently resolve renderer conflicts.
6. Run `python3 tools/check.py --output build/pf-oracle`, the hosted platform matrix and renderer source-evidence workflow. Use native GPU validation only when the actual imported change touches a contract that requires it.
7. Audit the final diff for lost VKDoom/ShadeDoomVK capabilities, compatibility identifiers, asset/license changes and unrelated donor history.
8. Merge only with green final-head checks; verify post-merge `master`, then record the acceptance receipt.

## Acceptance mapping

- Exact refs/deltas: commit/tree pins, untruncated tree receipts and exact counts are recorded.
- Owned/syncable surfaces: explicit matrix above and RAG ownership reference.
- Representative sync: two-guard Crusader adaptation plus focused CPU/source regression.
- PF regression gates: complete CPU oracle/build/source-evidence gates plus issue-specific ownership veto.
- No accidental renderer loss: no renderer donor code is imported; exact conflict paths fail closed.
- Provenance: donor commit/path/adaptation/license disposition is recorded.
- GPU scope: no physical GPU run is required because this PR imports no renderer/Vulkan implementation.

Final acceptance is complete. Exact final PR head `cbc8fa1601123e595483a2ab5d8f9997c36c0768` passed Continuous Integration run `37846204348` and Renderer source evidence run `37846204325`; PR #122 merged as `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`. Current verified `master@a05743fb428c0d7c66defccfb577834d012b4e31` is a descendant of that merge and passed Continuous Integration run `37851016492` plus Renderer source evidence run `37851016448`. SDVK-004 and SDVK-009 may consume this accepted ownership/sync policy subject to their other dependencies.
