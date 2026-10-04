# PF-020 final-source freeze checkpoint — release blocked

Date: 2026-10-04. **PF-020: NOT ACCEPTED. SDVK-001: BLOCKED.** [Draft PR #111](https://github.com/techrote/ShadeDoomVK/pull/111) records reviewable synthesis work. It is not eligible to merge as a passing freeze.

## Source and ownership

The accepted renderer master is `7d29c7e4d64d61dba05524d9e7f5711ffd915d90`, the verified merge of [PR #117](https://github.com/techrote/ShadeDoomVK/pull/117). All PF-001–019 and accepted CFX disposition merges are ancestors. The sole mutable source repository is ShadeDoomVK, checkout `C:/ShadeDoomVK/campaign-worktrees/pf020-native-freeze`, branch `codex/pf020-native-freeze`. Sibling source repositories and historical source worktrees are read-only.

The freeze branch integrates accepted master at `204c666ba6e1f97438f8aec36f67ef66ddcaf718`; `dc58b3aa1d66050286fafc999cb505aa82e7d889` adds release/reconciliation documentation. Engine, shader, library and build content is unchanged from accepted master. Subsequent focused documentation/tool heads require their own recorded checks; no new engine build or runtime result is implied by a documentation commit.

Root owns integration and native execution. Disjoint agents review source/evidence and prepare the guarded ordinary-runtime tool. Physical children run serially; compiler/check jobs do not compete with measured runtime windows.

## Independently accepted defect repairs

| Finding | Accepted release | Verified scope and boundary |
|---|---|---|
| GLDEFS authored-slot sampling isolation | #114 / [PR #115](https://github.com/techrote/ShadeDoomVK/pull/115), `3f37b63a4fdfb4c95421db951cf81682b5eb92c9` | [Historical compiled verification](PF-GLDEFS-SAMPLING-VERIFICATION.json) preserves original/current producer controls. [Final release acceptance](https://github.com/techrote/ShadeDoomVK/issues/114#issuecomment-5977683648) records all eight actual exact-head/post-merge jobs and independent review. |
| Public indexed palette provisioning / mapped software layout | #110/#112 / [PR #116](https://github.com/techrote/ShadeDoomVK/pull/116), `1524686e77f1e89dabfb044bf757a2d19566c31c` | Twelve normal and two genuine restart processes,294 ROIs and983,040 independently recomputed indexed pixels with zero mismatches; all release checks. [Receipt](PF-110-RELEASE-ACCEPTANCE.json). Unmeasured mode1 BGRA/direct SW retirement token/performance remain unclaimed. |
| Missing PBR probe pair / typed consumer | #113 / [PR #117](https://github.com/techrote/ShadeDoomVK/pull/117), `7d29c7e4d64d61dba05524d9e7f5711ffd915d90` | Adopted zero-IBL policy and unchanged mixed coefficients/order; LOD0 and NonUniform contract; exact unsafe-original CPU negatives; actual publication-window draws and twelve private controls each in separate core/sync native runs. [Release receipt](PF-113-RELEASE-ACCEPTANCE.json), [measurement-time qualification](PF-113-FINAL-NATIVE-VERIFICATION.json). |

#113's accepted runtime packet uses Windows/NVIDIA GTX1650SUPER, actual Vulkan API1.4.351 and reported driver616.368.0; Windows driver616.92 is recorded separately. Candidate2 is a fresh VS2022 x64 RelWithDebInfo build of `a113e2bc1644fe5e7e9079b49ef67308f83eecff`, EXE SHA256 `c287a601a803b467d585c24283edad2986d48f9c295a134a1843c9906a925813`. All2,535 measured engine inputs and eight build/staged counterparts bridge to exact repair head and accepted master with documented text/raw-byte identities.

Both native runs exit0 and pass23,603 checks. Actual separate core/synchronization validation has zero Khronos errors/warnings; five loader notices per run and active OBS/NVIDIA implicit layers are recorded. No GPUAV, P400, LevelMesh/uber output parity, full-frame parity, full-bake robustness or GPU timing claim follows. Known-unsafe original missing/divergent PBR routes were never launched.

All eight actual required PR-head jobs and all eight merge-push jobs pass for each accepted release; exact commit/CI/review identities are in its linked receipt. Issues110/112/113/114 are closed. Their correctness acceptance does not preaccept the full freeze.

## Current final-source CPU/build checkpoint

`build/pf020-native/pf020-final-checks-01/receipt.json` records source-equivalent `204c666ba6e1f97438f8aec36f67ef66ddcaf718`: strict PF440/440, CFX8/8, four standalone stress fixtures and two byte-identical oracle outputs, all exit0. PF suite log SHA256 is `c684b41d734cf5f7e799a7bd6c97e8282b5080496d1c5c14726784a1a79272dd`; CFX log SHA256 is `049dd0efb4f2eef52b969b4187e3086aa249a396fa4d37e8f12e7ddf842c9bbd`.

The checkout changed two diagnostic files' line endings. Before checks, root restored only their exact measured LF bytes after proving CRLF projection equals both Git content and the accepted raw pin. This preparation and rejected direct-shell launcher are retained in `build/pf020-native/pf020-final-preparation.json`. The corpus receipt honestly retains the unchanged Git stat-cache M markers; refreshing those two index entries produced no staged/content diff. It is not labelled an initially clean Git-status run. A fresh clean final-head corpus is required after the new runtime tool/tests and documentation are frozen.

The existing clean native build bridges all2,535 inputs:231 raw and2,304 documented CRLF projections, including two legacy encodings and two forced-text terminal-NUL files. Git/text equality is not silently substituted for measured raw identity. No engine source change occurred during this reconciliation.

## Remaining freeze gates

The [evidence matrix](PF-FREEZE-EVIDENCE-MATRIX.md) maps every PF disposition, CFX prerequisite, retained measurement and limitation. The owning [PF-020 issue](https://github.com/techrote/ShadeDoomVK/issues/37), [canonical issue](issues/PF-020.md), [validation contract](06-VALIDATION-PERFORMANCE-CONTRACT.md) and [equivalence protocol](PF-EQUIVALENCE-PROTOCOL.md) govern acceptance.

1. **B4: missing applicable view-equivalence packet.** [PF-010 verification](issues/PF-010.md) requires actual main, portal/mirror, camera texture and six probe-face contexts with matrices/portal state and before/after images. Its accepted record supplies compiled context/source fixtures and CI, but no corresponding Layer-B/C packet is cited. Unchanged source can transfer an existing measured result; it cannot invent an absent one. PF016 linked-group lighting images and PF113 immediate-specialized readbacks do not cover these view comparisons. The required bounded packet must pin source/build/content/time/settings, record actual context type/identity/parent/parity, matrices and postprocess eligibility, pair images with a declared metric/tolerance and map deliberate structural-ID differences. Availability of safe before/after fixtures and capture seams is being checked. PF006/PF009 also require explicit applicable evidence mapping.
2. **B4: current aggregate/runtime review.** A new healthy ordinary Dense comparison is being prepared with all production diagnostics/validation disabled. No such new runtime result has yet been measured. Its source/build/content/settings, actual camera/counts/dimensions, raw CPU benchmark windows and images must pass the guarded protocol before a workload-specific conclusion.
3. **B2/B3: final focused head.** Complete the clean strict corpus/tool tests, source closure and independent canonical/RAG/all-links audit on the frozen documentation/tool head. Correctly describe dormant light-tile storage as allocated/valid, not initialized payload; `uLightIndex=-1` prevents consumption. No engine initialization requirement is added for that inactive consumer.
4. **B5: final integration.** Only after all applicable proof passes: exact-head independent review and all eight actual required jobs, eligible PR merge, verified master and required merge checks, then issue closure. No passing freeze merge exists; SDVK001 remains blocked.

## Performance, quality and retained history

The aggregate review preserves heterogeneous measured outcomes rather than summing percentages: PF005 allocation counts; PF016 representative CPU setup benefit; PF018 bounded AABB/resource benefit with mixed whole-path timing; PF019 avoided dormant construction. PF017's integrated candidate regresses setup10.79% and All2.42% and is fully restored. Earlier partial/prototype savings are not retained improvement. CPU built-in bench clocks are not GPU timestamps, and no universal current renderer GPU/frame budget has been established.

The fresh ordinary Dense workload uses healthy content and the accepted material baseline. It is a new qualification, not a strict repeat of the historical Dense IWAD identity, a PBR-cost baseline, an indexed cold-upload benchmark, or a reopening of PF017/CFX STOP scopes. Fixed declared inputs, two warmups and five alternating pairs are the bounded target; failures are retained without automatic retries or a fabricated performance threshold.

Quality/compatibility gates remain intact: no reduced lights/effects, filtering/mip/colour-space/precision/LOD/resolution changes, altered gameplay or portal/probe/shadow policy, hidden fallback, or worker changes. CFX's accepted removed-page typed-neutral publication and ordinary fence retirement remain authoritative. DBP37 repaired GTX coverage is3/3, and accepted original DBP50/v1.2/Sunlust scopes retain their bounded results. Repaired P400 behavior is untested. All historical STOP/saturation guards remain sealed.

The [initial checkpoint54e9a1b3](https://github.com/techrote/ShadeDoomVK/blob/54e9a1b3bd95046faa80566340c31e8ddbaac99b/docs/shadedoomvk/PF-FREEZE-MANIFEST.md), original source-controlled receipts and disposable local evidence retain initial compiler failures, source findings, material/probe preparation failures, rejected presentation gates and later corrected attempts. They are historical records, not current open repair statuses. No original receipt/log/build identity is rewritten or relabelled.

## Next action

Finish and review the guarded ordinary Dense launcher/tests, freeze its source checkpoint, run the clean corpus, then perform serial native warmup/control qualification before paired measurements. In parallel, identify the exact missing supported-view evidence prerequisite and prepare a bounded safe reproduction if possible. Keep PR111 draft and the freeze blocked until its own full contract passes. Local artifacts hold evidence only; current remote humagent remains the human-task inbox. No human action is currently required.
