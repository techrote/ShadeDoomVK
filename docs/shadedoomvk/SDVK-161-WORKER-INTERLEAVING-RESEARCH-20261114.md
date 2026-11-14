# SDVK-161 — Recursive immediate-wall worker interleaving research

**Nonqualifying research. No renderer fix / tolerance change / merge authorization.**

## Preserved baseline

This study is stacked on the **qualified fixture-only** SDVK-161
`-nostartup` candidate `426387eeac04f629c9510ffa5e23537e6ef4acc2`.
Its independently successful targeted campaign (8 genuine original native
attempts, original 35 negatives each, all 28 strict exact state/RGB comparisons)
is retained unchanged. Neither main, PR #196 nor PR #201 is modified.
The full SDVK-009 publication CI must **not** run without an independently
demonstrated causal repair and explicit integration authorization.

The historical defect is the real, individually admitted run #627 frame-37
80 vs 84 immediate wall vertices plus 22 vs 23 empty light uploads,
without a corresponding final RGB difference. The same signature occurred
at frame 4 on earlier master. 16 individually admitted `-nostartup`
frame-4/37 passive-trace captures (CI 43604073338) reproduced neither,
so the exact missing wall owner is still unknown.

## Falsifiable hypothesis

In `src/rendering/hwrenderer/scene/hw_bsp.cpp`, recursive
`HWDrawInfo::RenderBSP` launches one producer/consumer worker. BSP
traversal enqueues wall/flat/sprite/portal jobs, the worker calls
`HWWall::Process` to create immediate draw-list entries, and the
consumer/producer must rendezvous before normal `RenderScene` draws.
The queue is single producer / single consumer and uses atomic
publication indices. That code shape does **not** show a lost job;
it also does not exclude a worker-visible state dependency that
changes geometry or draw selection under a different interleaving.

Only under the explicitly enabled wall-observer diagnostic, at retained
frame **37** in recursive immediate views, the worker is released
(i) immediately, (ii) after 1 job has been published, (iii) after 4 jobs,
or (iv) only after all producer jobs including termination are
published. This changes **when** the worker starts, not **which** job
is published, its order, or any production renderer setting. All
four modes use the same original authored `-nostartup` fixture,
32+96 real views, 12 native detailed witnesses, fixed input schedule,
unmodified 35 original negatives, semantic comparator and exact RGB gate.
Every worker release has an actual source-POD event retaining the
published-job count and count seen at worker startup. A bounded
separate per-line wall/draw/light sidecar records frames 4 and 37 only;
unselected native frame observations remain complete. The original
frame counts and actual light-upload ledger are joined to the sidecar
and must agree. Missing or forged one-wall/one-upload mutations reject.

## Finite experimental design

- Exactly 16 independently preregistered original 96-frame native attempts,
  zero retries. Two pairs per mode, four modes, source-matched binaries.
- Original native per-attempt validation, original lifecycle/checkpoint
  validation and 35 original captured negative controls always active.
- Eight within-mode exact state+RGB original comparisons; additionally
  24 cross-mode first-attempt comparisons are *forensic only*.
- Source-reconciled wall side/line/type/portal-context, queued vs submitted
  stages, initial worker queue depth, all indexed successful light uploads.
  A missing 4-vertex wall with its own missing empty upload is the target.
- If the discrepancy reproduces naturally and the removed wall/producer
  is attributable to a specific interleaving, freeze the real failing pair,
  create a minimal source-level pre-fix regression, identify the upstream
  race and repair its actual owner before any normal qualification.
- If no real discrepancy is reproduced, STOP/HOLD; no fictional cause,
  no artificial omission misrepresented as a genuine bug, no batch rerun,
  no renderer patch or claim that the intermittent defect is fixed.
- The diagnostic workflow ends with a deliberate PRECHECK_ONLY failure.
  Its red status does not by itself indicate failing native correctness.

## Method limitations

The earlier missing-wall failure was hosted on AMD EPYC 7763; the
successful targeted fixture campaign ran on different hosted CPU types.
Runner host variability and the diagnostic probe can change scheduling.
Passing outcomes do not exclude the historical one-frame defect.
Do not conflate incidental run success with a demonstrated causal fix.
This branch has no publication authority, no physical GPU qualification
and no permission to merge.
