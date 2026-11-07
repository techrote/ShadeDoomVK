# Renderer delivery and programme pause — 7 November 2026

The owner's final session instruction is to integrate the weapon/gameplay
increment, initially validate it, document other progress at useful pause points,
then stop. The full renderer programme is unfinished. The independent hosted
extra wall draw and small physical reload pixel difference are explicitly
deferred for this delivery. Existing required CI and tolerances remain unchanged.

## Delivered work and final integration boundary

Guarded PRs #171, #172 and #162 are verified on master; the
[backlog record](BACKLOG-INTEGRATION-20261107.md) pins their reviewed heads and
merge trees. Eleven tiny corrections were absorbed into #172, #184 into #162,
and #185 into #172. Fourteen obsolete remote heads were removed under SHA leases.
Original evidence and the non-ancestor #184 head remain retained.

[PR #186](https://github.com/techrote/ShadeDoomVK/pull/186) owns explicit
legacy/sector/enhanced weapon-card and rigid-model lighting, diagnosed fallbacks,
normal/PBR materials and ordinary-input gameplay. Ten physical static captures
passed five independent state/RGB pairs. A fresh physical gameplay process
passed all 128 critical views and nine image joins, including movement, turning,
actual firing/ammo/muzzle reset and A/B/A map/resource transitions. See
[the exact evidence summary](evidence/SDVK-011-GAMEPLAY-PHYSICAL-20261107.json).
Integration still requires final independent review and all normal exact-head
checks before an expected-head merge, followed by verified master presence.

This is initial validation with LevelMesh rendering off and shadows off, no static
bake, HUD POM or physical timing acceptance. #11 remains open for remaining full
criteria. Gameplay simulation and default legacy presentation are preserved.

## Clean paused workstreams

The following are local commits, not merged work or accepted native results.
Paths are relative to the dedicated `C:/ShadeDoomVK` host root; the private
handoffs retain full hashes, test receipts and exact resume instructions.

| Workstream | Clean checkpoint | Actual qualification and remaining boundary |
|---|---|---|
| SDVK-014 controlled-plane ownership | `e3e328c9a9e9cee9d930fc684819469bf02bc80d`, `worktrees/sdvk014-controlled-plane-20261107` | 43 focused tests and six real translation-unit compiles; independently reviewed. No full linked/native qualification or integration. |
| Authored controlled-plane native draft | `fc79a715a06a3ad568d6065304236fc394c263f3`, `worktrees/sdvk014-controlled-native-20261107` | 110 focused tests pass; separate compact BOTH-plane corpus and strict source/facing/UV/owner/material/image gates. No new full link, native run, CI or independent review of this draft layer. |
| Temporary wall-call diagnostic | `fe33c089a9254d2f92da637e3aebf725b41474f8`, `worktrees/sdvk161-wall-signatures-20261107` | Full clean build and one 96-view trace. Extra quad did not recur; 352 pixels differed by at most one channel after reload. Original trace remains FAILED_STOP, without GPU fault. TRACE02 was never approved or launched. Diagnostic is unmerged. |
| Shadow-off many-light/POM partial campaign | `3086b73818295b85d3da2d9b22fa94d5053df3c9`, tree `d0f89f9d44f4e40f44e9eb7d843f063fdd567c26`, `worktrees/physical-campaigns-20261107` | Retains `b337920d` with 76 passing focused CPU tests, then merges only the canonical worker-fixture repair. No new full build, native supervisor suite, GPU execution, push or PR. All eight advanced POM gates remain held; 18 new quality inputs lack typed physical admission. |
| Optional CI packaging #187 | `194c8fe740782817174dc90472fe6df5bfd8cb3b` | Keep Draft: current-master conflicts, preserve SDVK-161 invocation/artifact, fix uploaded checksum pathname; speed benefit unmeasured. |

The opacity hypothesis has only an extracted-source CPU discriminator. No
production opacity patch was applied; its cause of the pixel difference is
unproven. The isolated opacity worktree remains clean at `a774ecbf`. Historical
failed attempts and frozen build/runtime directories are unchanged.

Private handoffs:

- `physical-evidence/resumption-20261107/deferred-161-014-handoff-20261107.json`,
  SHA-256 `032a2ee6cf9a55a42cb68a410d11a37d8a39f8bd971ee594932f97ec71d7c02c`.
- `upstream-comparison/20261107/physical-campaign-pause-3086-01/README.md` and
  `handoff.json`, SHA-256 `f1ce5a72570f4fa13e5748e1a4ea95fa66c1a40f11323741e2c9f3bb4e9718db`.

## Physical boundary on resumption

The [physical resumption record](SDVK-009-PHYSICAL-RESUMPTION-20261107.md)
retains the new SDVK and unmodified stock VKDoom fault observations. The same
System event class on upstream is not proof of a common cause. The GPU returned
to idle; no reboot or hardware settings change was performed. The intended
owner-configured power limit is 90 W. The private kernel dump must not be uploaded.

SDVK-008 quality/cost, SDVK-009 architecture/scaling and SDVK-014 bake/update
physical criteria remain unaccepted. No SDVK-012 or later dependency waiver is
implied. After this delivery, fresh owner/programme/source/CI review and a new
source/build/content/host-pinned plan are needed to resume held experiments;
historical failed packets must never be relabeled or blindly retried.
