# SDVK-150 — probe builder semantic owner repair

## Disposition

**REPAIR CANDIDATE / NOT YET ACCEPTED.**

This document records the upstream repair for issue #150 discovered during
SDVK-014. It does not close #14 or #150 and does not qualify physical GPU work.

Audited repair base: `master@097ad33a39fd4c56c7cf9964de87425fd5e5c66f`,
the verified merge of SDVK-014 PR #151. Repair branch:
`sdvk150-probe-owner-identity`.

Physical STOP remains ACTIVE. Physical bake/update cost, scaling and hardware
stability remain HELD / NOT ACCEPTED. Hosted llvmpipe is software correctness
evidence only. Historical physical fault root cause remains UNDETERMINED.

## Demonstrated pre-fix defect

The renderer owns one process-global `LightProbeIncrementalBuilder`. The inherited
builder tracked only probe count and bake progress. After map A completed five
passes for two probes, map B with two different probes could inherit terminal
progress and publish nothing. The ordinary entry path also skipped `Step()` while
the authored set was empty.

The retained exact pre-fix source reproduces:

- completed A → same-count B;
- completed A → empty → same-count B;
- partial A pass → same-count B;
- `Full()` across same-count owner replacement.

Independent unchanged-owner, changed-count, direct-empty and fresh-builder
controls distinguish ownership failure from a broken callback sink.

## Semantic owner identity

Probe count, object address and nonzero descriptor state are not owner identities.

`FLevelLocals` now carries an authored probe-set revision issued by a
**process-unique monotonic generator**. Each distinct level object starts with a
fresh revision, and each actual authored-set mutation receives another fresh
revision. Zero is never issued; wrap fails closed before token reuse.

Production revision boundaries covered by the repair:

- `FLevelLocals` construction — distinct map/level owner;
- `ClearLevelData()` before authored probes are cleared;
- runtime `AddLightProbe()`, including the additions used by
  `autoaddlightprobes`.

Map-authored 9892 probes are therefore distinguished by the new level owner's
initial revision; runtime additions advance the same semantic generation.

Authored ordinal 0 remains an ordinary authored probe. The owner revision is not
an ordinal, runtime descriptor index, LightProbe epoch, descriptor generation or
LevelMesh epoch.

## Builder transition contract

`LightProbeIncrementalBuilder::Step` and `Full` receive the semantic revision.

On revision change, before any new-owner capture:

1. install the new revision;
2. reset probe-count/progress state;
3. call the existing `ResetLightProbes()`;
4. return without mixing an old partial pass into the new owner.

The next call begins the new owner from probe 0. Equal counts therefore cannot
retain terminal or partial progress.

The existing count-change reset remains only as a defensive fallback for an
unowned producer bug. The same-count acceptance fixture explicitly rejects any
use of that fallback.

The entry point now calls `Step` for empty authored sets as well as nonempty
sets, so A → empty → B cannot hide the empty owner transition.

## CPU acceptance matrix

The exact production Step/Full definitions are compiled with CPU callback sinks.
The current repair candidate must pass:

- unchanged-owner terminal no-work;
- changed-count fallback;
- direct empty reset;
- genuinely fresh builder control;
- completed same-count A → B;
- completed A → empty → same-count B;
- partial-pass A → same-count B;
- `Full()` same-count A → B.

The exact historical header plus Step/Full bytes remain retained separately. The
historical source must still fail the four owner-sensitive cases for their named
reasons. No hand-written approximation is accepted as the negative.

## State-only native witness

The ordinary observer gains one opt-in flag: `-sdvkprobeownertrace`.

It records only actual ownership-boundary state after existing builder actions:

- semantic owner reset;
- empty-resource reset where applicable;
- defensive count reset;
- completed pass publication after `EndLightProbePass()`.

Each record retains current map, semantic owner revision, authored count, pass
progress, LightProbe epoch and actual irradiance/prefilter resource-family counts.
The trace is bounded to 64 events and is emitted only in state mode. It never
changes a renderer decision, scheduling, quality, probe selection or resource
lifetime.

## Hosted same-process protocol

The focused corpus scene `probe-owner-transition` contains two authored maps in
one PK3:

- `SDV15A`: two probes at A positions;
- `SDV15B`: two probes at distinct B positions.

Both contain two actual PBR actor consumers. The process starts A normally.
A fixture-only ZScript `EventHandler` counts **32 post-main `RenderOverlay`
callbacks**, then sends one ordinary network event. Its playsim `NetworkProcess`
handler calls `Level.ChangeLevel("SDV15B", 0, CHANGELEVEL_NOINTERMISSION |
CHANGELEVEL_NOAUTOSAVE)` in the **same renderer process**. Duplicate, manual,
wrong-player and wrong-map requests are ignored. The nosave UI counter saturates
at 32. The natural level-transition route replaces the former console `map`
command; no intermission or unrelated autosave capture is introduced.

This is an input driver, separate from the state-only observer. It never reads
builder progress, publication events, descriptors or observer counters, and never
changes bake decisions or retries an incomplete bake. The fixed frame allowance
covers the one-frame actor creation, one owner-reset call and ten probe-capture
calls needed for two probes and five passes. The remaining frames must be
unchanged-owner no-work. A regression that skips publication still fails the
independent five-pass oracle; the driver does not wait until it passes.

The source-audited route is `D_Display -> RenderView -> DrawTopStuff ->
EventManager::RenderOverlay`. Cubemap faces and wipe-only presentations do not
invoke this callback. The ordinary adaptive simulation clock, `cl_capfps=true`,
100 observer warmup frames, one retained frame, 300-second process deadline,
geometry/material/probe inputs and exact RGB/state comparison policy are unchanged.
This fixture is correctness-only and rejects timing mode before launching.

### Retained failure of the original tic-based driver

Normal run **38870637199**, Avrea job **116874272696**, built merge ref
`0cd4760e5d8c1ff1030bb13921fa057171a56de3`, tree
`73959c095342e8313b12da3d419b29b53412115d`, matching PR head
`42eba1b100e00ce7411e238536ee1ede3c3481e2`. Its first SDVK-150 capture completed
and then failed the unchanged lifecycle oracle: A reset but published **zero**
passes; B reset and published passes **1..5**. The stderr log is empty and the
normal screenshot/observer completion marker is retained. No renderer/device
fault is indicated by this packet.

The previous `wait 20; map SDV15B` driver counts simulation tics. The adaptive
play loop may execute multiple tics before the next render; a frame-rate cap is
not a lower bound on render progress. Consequently the claim that `cl_capfps`
made 20 tics sufficient was false. Merely increasing the tic wait would retain
the invalid scheduling assumption.

The archive **12034085539** is pinned by SHA-256
`a248bedafee96f386cd23de7970ada8707183c5dc90fe30a8785098a85c81457`.
The raw observation SHA-256 is
`60a24c47373e4e18f12f45360e0b768e5db11c498eb8700243bdb589675af73f`.
An unmodified selection of its lifecycle rows is retained in
`tools/renderer_oracle/tests/fixtures/sdvk150-tic-wait-failure.json`; it must
continue to fail. No failed receipt is relabelled as accepted.

The new CPU schedule fixture executes the actual generated driver bodies with
bounded C++ service doubles and exact production Step/Full. One-tic-per-view
control passes both drivers, but a 20-tic burst reproduces the original A=0/B=5
failure. The frame driver passes cadences 1, 2, 8, 20, 35, 100 and 4096 tics per
view with A=5/B=5 and one queued/applied transition. With the historical builder,
it still fails A=5/B=0. A deliberately shortened two-frame driver also fails.
These tests are not ZScript VM or Vulkan execution; hosted compilation/execution
of the unchanged public event APIs remains a required native gate.

Acceptance requires actual lifecycle state in order:

- A semantic owner reset;
- A pass publications 1..5;
- B semantic owner reset with a distinct owner token;
- B pass publications 1..5;
- no count-reset fallback for either equal-count owner;
- B LightProbe epoch greater than A;
- matched irradiance/prefilter families for every completed pass;
- final B draw state consumes live authored ordinals 0 and 1.

Two independent clean-state same-process captures must then compare exactly in
final B state and RGB. Cross-process comparison normalizes only the process-local
owner-revision labels bijectively; map/order/distinctness, LightProbe/resource
epochs, pair counts and all other semantic state remain exact.

This focused qualification runs inside the **existing normal Avrea 16-vCPU
software-Vulkan job**, reusing its build, llvmpipe isolation and authenticated
Freedoom content. It adds no duplicate full CI or benchmark-only runner.

## Remaining acceptance boundary

Until exact-head source evidence, normal CI, the focused native gate, review,
merge and exact-master verification pass, #150 remains open and SDVK-014
cross-map probe lifecycle acceptance remains blocked.

Even after software qualification, SDVK-014's physical GPU cost/scaling/stability
requirements remain separately held under Physical STOP.
