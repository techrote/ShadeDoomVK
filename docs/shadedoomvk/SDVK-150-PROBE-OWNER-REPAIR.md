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

Both contain two actual PBR actor consumers. A normal console script starts A,
uses the inherited delayed-command queue with `wait 20`, then executes
`map SDV15B` in the **same renderer process**. `cl_capfps=true` makes the
bounded tic wait a conservative frame-progress allowance rather than an
unbounded timing guess.

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
