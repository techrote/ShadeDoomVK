# CFX-010 — PR104 cross-case qualification

Issue: #105; parent: #75. Protocol: [CFX-010](issues/CFX-010.md).
Machine-readable matrix: [cfx010-cross-case.json](evidence/cfx010-cross-case.json).

**Status: PHYSICAL QUALIFICATION SATURATED; final report/CI/review pending.** Each
separate selected route completed in **three independent qualifying processes**.
Seventeen CFX-010 launches comprise five safe controls, nine qualifying targets,
two excluded Sunlust observations and one host startup abort. **Zero new device
loss/TDR events** were observed. All phases are sealed against further launches;
the eighteen prior STOPs remain unchanged and N2 adds a nineteenth saturation STOP.
Carried CFX009+010 totals are **31 launches / 2 prior loss episodes**, not all-time
programme totals. No merge or issue-closure result is claimed here. Initial CI passed
all eight jobs. Final CPU regressions passed **130 tests with MSVC ASan fixtures**;
the final host-manifest metadata checks passed **24 focused tests**. Earlier
126/129 full and 20/23 focused results remain separately preserved. The matrix pins
the actual test receipts and analysis/index references.

## Pinned renderer and scope

Accepted PR104 merge: `d0789c88f88049116022e7b904026cddeaba8ac4`.
The preserved accepted binary was built from
`3916c82f2f87f0173e1b9ad748faac19365a5415`, rather than from the merge commit.
The local source-equivalence record confirms an empty diff for `src`, `libraries`
and `wadsrc`. EXE SHA-256:
`102a3d148e96b28e0b630f86b2a295f8e7fe2638e49e1a189d4b453bfa735d4c`;
matching PDB: `799f69bc6a7f2b8f88a7032fdace537cb7e12af5519b1bb81c7fbfb24eff08a8`.
The matrix pins all eight executable/symbol/runtime files and reconstruction records.

Use the existing production repair with **normal resource retirement and diagnostic
retention OFF**. Do not repeat the accepted DBP37 qualification or replay old
crash binaries. Expected machine: GTX 1650 SUPER, NVIDIA 616.92 / Windows driver
32.0.16.1692, OS build 26200. Every launch must record the actual enumerated
environment and loaded layers; these expected values are not activation proof.

N0 raw evidence root: `C:\ShadeDoomVK\pf-local-evidence\cfx010-cross-case-20261002\`.
N1 root: `C:\ShadeDoomVK\pf-local-evidence\cfx010-cross-case-20261002-foreground\`.
N2 root: `C:\ShadeDoomVK\pf-local-evidence\cfx010-cross-case-20261002-settle\`.
Each invocation gets an isolated configuration, save/output directory, manifest,
preregistration and artifact index. Restore the pinned cache baseline independently;
archive the resulting cache and restore the original bytes. Historical cache bytes
and active layer state are unknown.

## Independent cases

| Case | Selected historical route | Preserved settings | Current result |
|---|---|---|---|
| Original DBP50 | MAP08, startup → wait 120 tics → screenshot → wait 2 → quit | Actual historical client 1264×681; tic paced (`cl_capfps=true`, `vid_maxfps=60`); VSync OFF; MSAA 4; LevelMesh OFF | **3/3 qualified**, 3 targets |
| DBP50 v1.2 | Separate MAP08 content; same finite startup route | 1264×681; same cap/VSync/MSAA/LevelMesh; mouse disabled, bindings cleared and background rendering enabled | **3/3 qualified**, 4 targets including one host abort |
| Sunlust + Champions | MAP24, seed 12345, skill 3 (Ultra-Violence), warp −4800,8400; full phased route below | 1904×1001; uncapped; VSync OFF; MSAA 4; LevelMesh OFF; mouse disabled/background rendering enabled | **3/3 qualified**, 5 targets including two N0 exclusions |

Both DBP50 cases load the preserved `Doom2.wad` in the IWAD slot. Its hash identifies
a **PWAD-header input, not verified stock Doom II**. Original and v1.2 PWAD hashes
differ; neither can stand in for the other. Original mouse/background policy differs
from v1.2. Their historical skill, seed and numeric camera are unknown and remain
unspecified. `vid_maxfps=60` with `cl_capfps=true` describes tic pacing, not proof
of measured 60 FPS. The 25-second watchdog bounds each finite startup route.

Sunlust retains **Freedoom2 0.13.0 → Sunlust → Champions**. The archived launched
configuration is reconstructed byte for byte; its historical manifest had named
the earlier, untransformed configuration. The 60-second route watchdog applies to:

1. Warp, god mode and preserved input/background/cap settings; wait 70 tics.
2. Benchmark; wait 210; phase 1 screenshot.
3. Move forward 35; turn right 35; wait 70; phase 2 screenshot and position/angle.
4. Texture filter 0 for 70, then 6 for 70; phase 3 screenshot.
5. Reload MAP24; wait 70; phase 4 screenshot; wait 2; normal quit.

The historical script has 632 explicit wait tics. The reviewed screenshot drain adds
two tics immediately after phase 3 screenshot, before MAP24 reload, for 634. This is
a capture scheduling adjustment, with unchanged renderer and movement/filter commands.
Right means **turn**, not strafe. The historical
failure only preserved the phase 1 black-world/HUD image; CPU records show phase 2
began, but do not prove completed movement, GPU execution or actor/line activation.
There is no use/fire/spawn command. Require all four images and phase progression;
loading MAP24 or reproducing the black phase 1 image alone is insufficient. Do not
claim visible arena/monster activation unless the current artifacts establish it.

## Preserved N0 observations

| Target | Run ID | Durable interpretation |
|---|---|---|
| Original DBP50 001 | `cfx-20261002T182533Z-030fb57c17c0` | Route completed, decoded 1264×681 MAP08 image, exit 0, recovery/cache pass; counts once |
| DBP50 v1.2 001 | `cfx-20261002T183249Z-b90f1b96f603` | Separate content, same completion checks, exit 0, recovery/cache pass; counts once |
| Sunlust 001 | `cfx-20261002T183607Z-3867284170d2` | Movement/filter/reload and normal exit observed; phase 3 image missing, so incomplete and excluded |
| Sunlust drain 001 | `cfx-20261002T185326Z-ce61c7b3c6d1` | Four 1904×1001 images and exit 0 observed; focus interference/watchdog race invalidate qualification and exclude it |

Both DBP50 targets observed neutral removed-slot publication at frame 6/submission 8,
then a successful fence/submission 10 and ordinary startup atlas unbind at frame 6,
base `0x1da00000`, reported span 8 MiB. Retention was OFF; fallback owners survived
to teardown. Their address traces contain 10,963 callbacks each with no omission,
fully flushed through frame 110. Resource tracing stopped at frame 32/tic 43 after
8,192 events, so later resource/descriptor/pipeline history is incomplete. Both retain
the malformed-geometry warnings. These are practical successes, not shared-cause proof.

Sunlust001's phase 3 screenshot was queued as a game action, then overwritten by the
immediate map command before screenshot processing. Source analysis and missing
capture output explain the absent image. The current phase 2 image shows a textured
arena and Champions-marked monsters, but unique historical activation remains unknown.
Startup publication preceded ordinary frame 6 atlas retirement. All 30,380 address
callbacks were flushed through teardown; resource coverage ended at frame 21/tic 74.

Drain001 serviced the image with the two-tic drain. Its trace rendered 1,042 frames
while simulation tic 565 stayed fixed for **31.932 seconds**, then tics resumed and
final submits/fences returned successfully. Archived `i_pauseinbackground=true`
allows simulation to pause on focus loss despite background rendering. The owner's
focus/title-bar observation agrees with that source contract; exact focus timing was
not instrumented. Normal exit raced the 60-second watchdog, which retained a TIMEOUT
manifest. A zero-byte unreadable dump and failed original artifact index are real
harness failures, not usable dump evidence. Supplemental salvage index verifies 30
readable artifacts and preserves the excluded failed dump metadata. No renderer/GPU
hang is established by this attempt. Its address cap ends at frame 434/tic 565, with
24,160 later callbacks omitted; resources ended at frame 21/tic 91.

N0's STOP (`a3e9c62c…`) and stopped state remain immutable, including their original
executor classifications. Both manual Sunlust analyses and the foreground readiness
review are pinned in the matrix. N0 added seven launches and zero losses to the carried
CFX009 14/2 ledger: **21 launches / 2 losses in this continuation chain**, not all-time
programme totals. All archived recovery gates, including the post-stop gate, passed.

## N1 foreground results and host activation blocker

The new sibling phase pins the same accepted renderer/content/config/cache identities,
17 historical STOP guards and the 21/2 opening counts. It preserves
`i_pauseinbackground=true`; foreground verification and monitoring must establish
actual window ownership and continued simulation, with no operator focus/title-bar
interaction. The matching control, run `cfx-20261002T193002Z-233945b2603f`, completed
on tool head `5406c47ab2ec0096f9952e800f4b998e978eaa02`: one focus request, verified
at `1790969404610` ms UTC before the first captured frame at `1790969405229`.
Its 39 checks and native event hooks observed only normal terminal window/focus release,
with no omitted focus events. It exited 0 with full recovery/cache restoration,
retention OFF and 3,404 address callbacks fully flushed without omission through
frame 15. This control ended at continuation count **22/2**. The subsequent three
target invocations bring the stopped N1 phase to **25 launches / 2 losses**, including
eleven CFX-010 launches and zero new losses. These are recorded counts, not planned
launch allowances or declarations that future targets will succeed.

Protected mesh state equals the earlier safe control. Both images are 1904×1001;
**pixel identity is false**: 23,089 of 1,905,904 pixels differ, bounding box
`(666,481)-(1065,840)`, with 331 differing pixels above row 620 and none in the
bottom HUD area. The operator's visual comparison found the same camera/world with
weapon-raising/animated-region variation; that interpretation is not an exact image
equality assertion. The safe analysis/index references are pinned in the matrix.

| N1 target | Run ID | Result |
|---|---|---|
| Sunlust foreground 001 | `cfx-20261002T193327Z-27c6d24e25d9` | Valid full route, four images, exit 0, recovery/cache pass; first qualifying Sunlust success |
| Original DBP50 002 | `cfx-20261002T193700Z-dd889cac572d` | Valid independent startup route/image, exit 0, recovery/cache pass; second qualifying original success |
| DBP50 v1.2 002 | `cfx-20261002T193850Z-bdbdee113a1b` | HOST_ABORT before first frame/map route; excluded from successful qualification |

Sunlust foreground001 completed movement/turning, both filter phases and MAP24 reload,
with all ordered markers and four decoded 1904×1001 images. Root's visual review of
phase 2 observed the arena, Champions-marked green monsters and a red projectile:
current post-phase-1 workload activation is established, without proving unique
historical activation. All 31,032 address callbacks were flushed without omission
through frame 190/tic 631/submission 2,114. Resources ended at frame 21/tic 75.
Neutral publication at frame 6/submission 7 preceded the successful fence/list release
and normal lightmap/probemap unbind at frame 6/submission 9; the lightmap span was
8 MiB at `0x1da00000`. Foreground checks remained uncontaminated. Retention was OFF.

Original002 independently completed the preserved settings/content/route with a
fresh 1264×681 image. Normal publication/retirement ordering persisted; 10,959 address
callbacks were fully flushed through frame 110/tic 121/submission 219, with no
omission. Resource tracing ended at frame 32/tic 43. Both valid N1 targets have no
negative traced Vulkan return or new device-loss/TDR/NV/OS health evidence; this
capture mode does not activate Khronos validation.

V1.2-002's native foreground request returned false; readback was window `0x0`,
PID 0, with zero monitoring checks. The host gate boundedly stopped the child and
recorded `HOST_ABORT`, exit 1. Its CPU trace contains only three frame-0 initialization
records, no frame/submit/map execution; the address file contains only its header.
The map route and renderer settings were therefore not exercised. The executor
classified application error and stopped on missing writer/flush evidence. Pre/post
health and cache restoration passed, without TDR/NV153/new OS fault. This is a host
activation/qualification blocker, **not evidence that PR104 is insufficient**.
The N1 STOP, state, manifest, index, output and recovery references are preserved.
Supplemental manual analysis verifies all 25 indexed files and confirms an expected
forced early cutoff, with no demonstrated storage corruption. Exit 1 follows the
host's bounded process termination; no application CPU exception was observed.
The precise cause of the immediate NULL foreground readback is unresolved, and
operator interference on this particular invocation is not established. The smallest
offline candidate is a bounded readback-only settling interval after the same single
focus request, retaining owned-window/GUI-state, event and pre-first-frame checks.
No additional focus requests, simulated input or renderer/pause-policy change is implied.

Prior rendering-background settings alone are insufficient proof of simulation
progress. Neither N0 Sunlust observation nor the v1.2 host abort counts toward the
three required clean routes. That finding led to the reviewed N2 readback correction
and matching control below; neither stopped directory was resumed. No pause-policy
change was made.

## N2 bounded readback continuation and saturation

The fresh sibling phase pins the independent host-startup review `191ebebd…`, the
same accepted renderer/settings/route/cache and **18 preserved STOP guards**, carrying
N1's 25/2 totals. It permits one foreground request followed only by a **250 ms
readback-only settling interval**, with owned/alive/visible/GUI checks, native event
monitoring and pre-first-frame verification retained. It introduces no renderer,
pause-policy, simulated-input or repeated-focus change. The owner offered exclusive
use; the opening bounds new launches to **2026-10-02 20:05 UTC**, without unattended
extension. Root remains the only physical operator.

Matching v1.2 safe control `cfx-20261002T195513Z-b62c79eb9dda` passed on tool head
`5b8636e1…`: one request, first readback successful, 78 monitor checks and only normal
terminal release. It exited 0 with healthy recovery and restored caches, retention
OFF. Its decoded 1264×681 image is **pixel identical** to the earlier matching v1.2
control, and protected mesh state is identical. All 5,873 address callbacks were
flushed without omission through frame 105; resource coverage remains bounded.
The analysis `0e5b6849…` and index are pinned in the matrix. This safe control ended
at **26/2** in the continuation chain. It proves safe activation/scene equivalence,
not that an actual delayed native readback or the remaining target routes succeeded.

The physical tool head passed 23 focused tests and 129 full CFX tests with MSVC ASan
fixtures. Final host-manifest metadata work subsequently passed 24 focused and 130
full CFX/ASan tests, without another GPU launch. Tool-head CI run **37057736783**
passed **8/8 jobs**. Final report-head CI and review are pending. The five subsequent N2 targets all completed normally with full
required images/markers, healthy gates and restored caches, reaching saturation:

| N2 target | Run ID | Final frame / tic / submission | Address callbacks |
|---|---|---:|---:|
| v1.2 003 | `cfx-20261002T195722Z-3dbb2b6f0eeb` | 110 / 121 / 219 | 10,963 |
| Sunlust foreground 002 | `cfx-20261002T195856Z-8d6b343af40c` | 178 / 633 / 2,045 | 30,313 |
| Original DBP50 003 | `cfx-20261002T200220Z-d1b5f633c32c` | 110 / 121 / 219 | 10,963 |
| v1.2 004 | `cfx-20261002T200346Z-7dbe17888e6a` | 110 / 121 / 219 | 10,963 |
| Sunlust foreground 003 | `cfx-20261002T200434Z-ed1bbca89986` | 191 / 632 / 2,112 | 31,421 |

Every qualified target has fully flushed address callbacks through teardown, zero
omitted/contended address callbacks, no negative traced Vulkan return and no new
TDR/NV/OS health evidence. Resource traces remain prefixes: DBP50 ends at frame 32/
tic 43; Sunlust foreground trials end at frame 21/tic 75, frame 20/tic 75 and
frame 21/tic 73. These limits prohibit a claim of complete late descriptor/upload/
pipeline history despite complete address capture.

All nine qualifying runs preserve neutral publication before ordinary atlas retirement,
with retention OFF. The DBP50 trials publish at frame 6/submission 8 before the fence/
list release/unbind at submission 10; Sunlust publishes at frame 6/submission 7 before
submission 9. Sunlust002's old 8 MiB lightmap base is **`0x1de00000`**, with its
2 MiB probemap at `0x1e600000`; other qualifying trials use `0x1da00000` and
`0x9e00000`. Each exact owner/lifetime is recorded; legal allocation variation does
not contradict normal retirement or support unique causal attribution.

All three qualifying Sunlust runs complete movement/turning, filter cycle and reload,
with four phase images and current post-phase-1 textured arena/Champions activity.
The same authored script and pinned settings yield slightly different actual phase 2
positions/angles. These are comparable route executions, **not identical actual camera
states or pixel outputs**. Preserve every recorded position/image; historical unique
activation remains unknown. Benchmark snapshots also vary despite the prescribed
warp/benchmark camera: trials 001/003 report 2 walls, 2 flats and 0 sprites; trial
002 reports 2,778 walls, 1,623 flats and 869 sprites. Do not describe their activation
or benchmark snapshots as identical; every trial's actual route/image/state evidence
remains separately preserved.

The local `closure-proof.json` (`04a579df…`) seals nine qualifying analyses/indexes,
five controls, three exclusions and the unchanged prior guards. Final state
`e2cbc01f…` is `QUALIFICATION_SATURATED` with no pending attempt/analysis; new STOP
`19471bb0…` prohibits additional launches in this scope. The matrix pins their full
hashes and every target reference. Physical evidence is sufficient for these finite
routes; final report integration/CI/review remains a separate gate.

## Historical differences and interpretation

The selected original DBP50 failure used source `31cf32b…`; v1.2 used `f7d5310…`
with the preserved historical binary. Sunlust used `84bbbac…` plus a temporary
PF17 lookup probe. The current accepted renderer contains other intervening fixes,
and bounded capture replaces that historical probe. Six Sunlust PK3/DLL runtime
files are unchanged, but the EXE/PDB are different. Script changes isolate output,
add phase/current-position markers and remove unavailable temporary probe commands.
No current success can attribute all differences solely to PR104.

Practical qualification asks whether each **credibly reconstructed finite route**
completes on the accepted renderer. It does not establish a shared historical cause,
prove that no other crash path remains, or identify an NVIDIA defect. A single success
is an observation. At most three independent comparable successes qualify a route;
stop at three. Repetition does not recover missing historical identities or activation.

## Evidence and bounded coverage

Record manifest/input hashes, actual dimensions/settings/camera/seed, stdout/stderr,
Vulkan environment/layers, CPU stages/submissions/fences, resource/descriptor/pipeline
events, address-binding history, phase images, cache transaction, recovery and index
hash verification. Where capture covers the relevant transition, record removed-slot
neutral publication before ordinary old-owner destruction, including normal retirement
and absence of retention events. CPU publication records are not GPU descriptor readback.

| Stream | Bound and implication |
|---|---|
| CPU timeline | 100,000 records; rotated tail may discard startup/capability rows |
| Resource trace | 8,192 events from process start; later events omitted after the prefix cap |
| Address bindings | 32,768 callbacks from process start; snapshots expose cutoff/flush/omission/writer status |
| Upload hashes | 16 MiB per upload / 64 MiB per run; budget omissions must be disclosed |
| GPU checkpoints | Owned marker payloads, bounded at 100,000; recording is distinct from confirmed GPU execution |

Compare the first cap/rotation with each route phase and any fault cutoff. Complete
startup capture does not establish full Sunlust phase 2/reload coverage. A clean finite
route can provide practical coverage with disclosed late omissions; a capped trace
cannot prove complete lifetime history or localize an uncovered fault. Never invent
post-cap events. Clean validation output is not proof of correctness.

Returned device loss may yield EXT device-fault data, NV checkpoints and address
snapshots. A call that never returns instead requires the bounded watchdog and a
matching-PDB process dump before termination. Healthy runs need not produce loss-only
fault/checkpoint/dump artifacts. Preserve proprietary content, binaries and raw dumps
locally, outside public Git.

## Recovery and completion

This is supervised adaptive testing with one physical operator, one informative
invocation at a time and no automatic retries. Preserve all historical STOPs and
ledgers, including completed CFX009 totals of 14 launches / 2 losses. Run the full
GPU/driver/NVML/Vulkan/session/process/storage/OS gate before/after each launch and
after any loss. Stop physical work for a hard/no-return hang, incomplete recovery,
GPU disappearance, persistent observed corruption, new WHEA/BSOD/hardware-health
evidence, unstable session, corrupt/uninterpretable evidence, storage failure or
operator instruction. Continue useful offline analysis after a stop.

For each case, fill the matrix with pass, preserved residual failure or an explicit
blocker; never substitute CI for a GPU result. Preserve one informative failure and
its narrowest next question before further experiments. Completion does not close
#75/PF020 or automatically establish common causation. **All three finite routes are
physically saturated; no further launches in this scope.** The repaired renderer has
not been physically qualified on the P400 or other GPUs/drivers in CFX-010. Shared
historical causation, unique initiating shader and isolated PR104 attribution remain
unproven; no NVIDIA defect diagnosis is made. Final PR/CI/review/merge receipts may
be added separately without rewriting the sealed physical evidence.
