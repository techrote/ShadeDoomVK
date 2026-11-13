# Controlled-plane native authoring — deferred checkpoint

**DRAFT / NOT NATIVE QUALIFIED / NOT READY TO INTEGRATE.** The owner deferred
additional SDVK-161/RGB investigation and SDVK-014 native work to finish PR #186
weapon/gameplay integration, then stop. This checkpoint preserves completed CPU
work; it does not authorize another GPU run, PR or merge.

The production parent is `e3e328c9a9e9cee9d930fc684819469bf02bc80d`, based on
accepted special-surface master `d40475519170606e83dec20dc822ceb5a54312ee`.
The original e3 worktree and its reviewed source remain unchanged. This separate
branch contains an unqualified follow-on, with no full linked build or normal CI.

## Retained draft

- A separately named `controlled-plane-lifecycle` scene and generator leave the
  accepted `special-surface-lifecycle` recipe and authored bytes unchanged.
  Both original map labels reuse the existing 96-frame/32-warmup driver, its
  invalidate/filter/reload phases and twelve checkpoint images. No C++ input
  driver was added.
- Each compact authored map has eight lines, two sectors and one real line
  mirror. Actual line160 parameters `(161,5,0,255)` request standard solid
  `FF_BOTHPLANES`. Map A uses model heights32/48 below its fixed camera; map B
  uses96/112 above its camera. Generated normal/PBR/height materials exercise
  independent source-plane ownership and sampler resets.
- Admission requires four distinct `(model source axis, emitted facing)` live
  allocations per target subsector, actual main LevelMesh submitted ranges,
  actual mirrored immediate submissions, current UV/page/allocation/mesh owners,
  material descriptors and per-layer samplers, completed rebuild work, and exact
  final/checkpoint RGB. The intended immediate pairs are both upward source
  faces in A and both downward faces in B. These expectations still require
  actual native confirmation; synthetic rows cannot establish native support.
- The accepted normal-only validator recognizes an emitted `control_plane`
  field only when it agrees with its historical normal source axis; retained
  older captures without that field keep their original contract. The separate
  BOTH-plane validator requires the field and all four independent bindings.
- `CreateFlatSurface` uses the checked first map entry instead of a range loop
  with an unconditional break. Its first-entry/empty-map behavior is unchanged;
  the extracted fixture no longer needs its scoped C4702 suppression.

No v5 format/admission/quarantine, allocation, height update, descriptor or
gameplay behavior was changed by this authoring draft. The e3 runtime-only
quarantine and save omission for ambiguous BOTH-plane v5 tuples remain intact.

## CPU evidence and boundary

[The paused CPU receipt](evidence/SDVK-014-NATIVE-AUTHORING-PAUSED-CPU.json) pins
the working source and retained logs:

- 110 focused tests passed, including43 actual production-method controlled-plane
  tests, seven new authored/native-admission controls and60 accepted special-
  surface regressions. Real old binding/UV/retirement counterexamples remain.
- An earlier33-test run passed authored corpus generation and source-authenticated
  preparation, with the same generated map/material assets. The initial six-test
  draft run rejected an invalid material generation correctly but had one wrong
  expected diagnostic regex; that test expectation was corrected and retained.
- Native submission, actual rendered RGB/bake convergence, a fresh linked build,
  exact-head CI and independent review of this new authoring layer remain
  **NOT RUN / PENDING**. The parent's six TU compiles remain evidence for e3,
  not a fresh compile/link claim for this checkpoint.

This does not qualify general `FF_INVERTPLANES`/`FF_FIX`/Vavoom content. Copied,
sloped or overlapping controls, in-place animated-height topology and the
inherited midtexture-height callback remain unclaimed. It does not complete
SDVK-014, accept physical cost/stability, or release any failed physical packet.

## Deferred resumption

After the owner reopens this scope, reconcile with the integrated #186 source,
review the authored matrix and actual producer/consumer assumptions, build the
exact clean candidate and run the hosted software-only qualification CLI
`python -B -m tools.renderer_oracle.sdvk014_controlled_planes` with explicit legal
IWAD/license/build/output arguments. The draft is not wired into normal CI yet.
Any physical capture still needs a new pinned, independently reviewed guarded
packet. Preserve e3, frozen fe33 and all failed/held physical evidence.
