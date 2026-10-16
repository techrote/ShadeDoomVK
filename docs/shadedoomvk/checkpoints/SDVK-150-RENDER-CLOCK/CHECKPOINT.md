# SDVK-150 render-clock repair checkpoint

Status: CPU-tested repair candidate. NOT applied to PR #152. NOT native-qualified.

Failing PR head: `42eba1b100e00ce7411e238536ee1ede3c3481e2`.
Failing normal CI: `38870637199`, Avrea software-Vulkan job `116874272696`.
Retained artifact: `12034085539`, SHA-256 `a248bedafee96f386cd23de7970ada8707183c5dc90fe30a8785098a85c81457`.

## Diagnosis

The process completed its normal screenshot/observer output. The unchanged acceptance oracle rejected `Each probe owner must publish exactly five completed passes`. The actual lifecycle trace contains A owner-reset, zero A pass publications, B owner-reset, and B pass publications 1 through 5. No renderer/device crash is claimed.

The original `wait 20; map SDV15B` recipe counts simulation ticks. `TryRunTics` can run multiple simulation ticks before the next main render. `cl_capfps=true` does not guarantee twenty rendered frames. This fixture therefore failed to establish its own required completed-A precondition.

## Prepared repair

An authored-only EventHandler counts 32 main-view RenderOverlay callbacks, sends one ordinary network event, and requests the normal play-scope level.ChangeLevel transition. It does not read builder progress, descriptors, publication counts or observer success. Missing bake success still causes the scheduled transition and the unchanged five-pass oracle must reject it.

Only MAPINFO and ZSCRIPT members change in the generated PK3. Both serialized maps and all fourteen other members are byte-identical to the failed native fixture. Settings, five passes per owner, 100 warmup frames, one retained frame, 300-second deadline and exact state/RGB comparisons remain unchanged. No renderer source changes.

Local implementation commit: `e3fa40f8c9948d496855572ad3160d067e9d2df5`.
Local implementation tree: `4aa5963b4fedc16b2c38b982836531739de3df9d`.
These are local candidate identities, not PR head or merged-master identities.

Patch SHA-256: `122b62f87660ce0924bc14f5ba151bfebcd02c8ae2fecccf2a0327a11025a4de`.
Compressed patch SHA-256: `58c935f3954b30a54b34758a755a95bb7b6be2eb3fe2f3cd18fa9f9a22d5b909`.

## Validation

Complete `python tools/check.py --output build/sdvk150-render-clock-final`: exit 0; 803 PF tests, 8 CFX tests, 216 renderer-oracle tests, deterministic corpus/PF output checks and four standalone compiled fixtures pass.

The exact-source scheduling fixture covers normal/slow tick rates, delayed event delivery, non-view/wrong-map rejection, hostile and repeated events, and absence of success feedback. Six driver mutants fail for their named reasons. The exact inherited FWaitingCommand reproduces the insufficient-A-publication counterexample. The retained native seven-event record still fails the original five-pass assertion.

The seven driver tests also pass using PF_CXX=clang++. A temporary support-header copy removes only an inherited unused constructor parameter name; production headers and Step, warning policy and decisions remain unchanged.

These compiled C++ service tests do not execute the ZScript VM. Actual ZScript compilation, native driver execution and two clean same-process captures remain pending on the authorized normal Avrea lane.

## Acceptance and next operation

Reconcile PR #152 head before applying the patch to its source branch. Run the normal source/full CI once for the actual applied candidate. Do not rerun the unchanged failing head or merge this checkpoint as though it were the source fix.

Issue #150 and SDVK-014 remain incomplete. Physical STOP ACTIVE. Physical bake/update cost, scaling and stability HELD / NOT ACCEPTED. Historical physical root cause UNDETERMINED.
