# SDVK-161 — source-backed worker handshake discriminator

**RESEARCH ONLY / PRECHECK_ONLY. No renderer acceptance or publication qualification.**

## Why a second, bounded experiment is necessary

The first 16-attempt worker-gate pilot at source
`594bb38ae8a2fd9df444b8600d1f294c294633bb` on
[Actions 43610912930](https://github.com/techrote/ShadeDoomVK/actions/runs/43610912930)
and archived [artifact 14120568607](https://github.com/techrote/ShadeDoomVK/actions/runs/43610912930/artifacts/14120568607)
passed all individual native captures and exact comparisons, but its
independently audited worker starts were **always equal to the total published
job count**, including all nominally early modes. Thus the producer/worker
interleaving hypothesis was **not exercised**. Treat it as an ineffective
experimental intervention rather than evidence excluding the race hypothesis.

## Finite correction of the experimental method

This branch is stacked on the qualified, unchanged, `-nostartup` fixture and
the earlier nonqualifying diagnostic code. Only when
`SDVK161_PASSIVE_WALL_TRACE=1` and retained frame 37 is selected,
`RenderJobQueue::AddJob` permits an explicitly limited producer pause after
the first or fourth published job, waiting **for the worker-start atomic
acknowledgement** before further jobs are queued. In the normal (env disabled)
path, the queue works as accepted. No queued job is dropped, edited, delayed
relative to a different queued job, or re-ordered. After-all mode retains
its delayed release; other production frames remain identical.

The producer pause is bounded to two seconds. The run **fails its
investigation admission** if the worker did not actually start before all
producer jobs were queued, or if an after-all mode starts early. Each
source-level scheduling record stores the queue's actual `Published()`
depth at worker start and after producer completion. All original
32+96 SDVK-161 native state, original images, 35 original negative controls,
strict semantic/RGB gate, intended lifecycle transitions and provenance remain
untouched. Synthetic negative controls deliberately delete a four-vertex draw
and an empty light upload from copies of the trace, proving the detector's
sensitivity but NOT the historical cause.

**Exactly eight native attempts, zero retries**: one independently compared
two-process pair per schedule `immediate`, `after1`, `after4`,
`after_all`, plus six cross-mode forensic comparisons. A job cannot qualify
until its gate is shown to have changed actual worker timing, before/after
native state is admitted and the original source/negative/RGB controls pass.
The published workflow ends in a deliberate PRECHECK_ONLY failure.

If a naturally observed missing draw is captured (80 versus 84 vertices
and 22 versus 23 empty uploads), retain the independent original mismatch
and the specific side/line/portal-context/worker-stage difference, then
investigate the demonstrated dependency. A compiler/runtime timeout, CPU
host change or artificially injected omission is not a causal repair.

If all eight original runs pass despite genuine interleaving contrasts,
hold the missing-wall issue. Do not make a renderer fix, relax the comparator,
merge PR #196/#201 or launch full SDVK-009 publication CI based on
non-reproduction. The historical #627 failure remains binding.
