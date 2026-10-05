# PF-020 aggregate performance and quality disposition

Date: 2026-10-05. **B4: SATISFIED WITH DECLARED LIMITATIONS.** Independent
contract review finds no remaining aggregate-performance criterion requiring
another native campaign. Final documentation/source checks, review, CI and
verified integration pass separately in the [release acceptance](PF-020-RELEASE-ACCEPTANCE.json). This is no universal
speedup, zero-overhead or no-regression claim.

## Requirement and decision

[PF-020/#37](https://github.com/techrote/ShadeDoomVK/issues/37) requires aggregate
review, traceable equivalent optimizations, preserved quality and passing stress
tests. The [owning contract](06-VALIDATION-PERFORMANCE-CONTRACT.md) requires
same-scene/settings evidence, state/image equivalence and measured benefit for
each proposed optimization's target workload. It specifies no every-pair win,
universal percentage, statistical-significance or new GPU/human/P400 campaign.
The15% CPU threshold is a prelaunch readiness predicate, not a regression limit.

**Decision:** retain every historical finding and assess the final supported
runtime using the complete fresh packet and the bounded PF optimization results
below. Do not sum percentages from different workloads. No accepted change
drops eligible lights, changes selection, filtering/mips/colour space/precision,
lowers resolution or disables an otherwise active feature to gain performance.

## Fresh final-source ordinary comparison

[FinalDense05 measurement](PF-020-FINAL-DENSE-MEASUREMENT.json) qualifies clean
tool `ad8d68072074ac1e621474c108c0c5e4a1b8e207`, native current
`569bdb118c709dac00dc6543570d6840c88dad12` and accepted-master native baseline
`a113e2bc1644fe5e7e9079b49ef67308f83eecff`. Accepted renderer master is
`7d29c7e4d64d61dba05524d9e7f5711ffd915d90`. Complete source/build/input closures
match before/after. Both variants retain ordinary adaptive rendering, Ubertrue,
shadows1, LevelMeshfalse,1904x1001 and the same camera/count/settings/device.
Correctness observers and validation are off; ordinary caches are untouched.

All12 actual medium, unelevated children exit0. Two actual agent-inspected
warmups precede exactly five alternating pairs. All60 raw blocks and40 scores
are retained, with only preregistered per-child index0 excluded. Five pairs
compare9,529,520 pixels with zero mismatch and exact queried/benchmark state.
Independent review rehashes84 outputs, parses all raw timings without the
acceptance parser and independently decodes all12 PNGs. All360 readiness
intervals retain raw deltas:30 per child, accepted indices20..29, maximum
last-window CPU11.711711711711711%. The revised120-interval settling allowance
is never needed in this successful packet.

Measured CPU milliseconds below are means of the five per-child medians;
the measurement JSON also retains every score, pair difference and pooled
mean/median/range. Negative change means the current observation is lower.

| CPU metric | Baseline ms | Current ms | Signed change |
|---|---:|---:|---:|
| All including Finish/wait |18.3481|18.2598|−0.4812%|
| Full Setup |3.6660|3.6319|−0.9302%|
| Sprite Setup |3.6243|3.5910|−0.9188%|
| Render |0.4932|0.4848|−1.7032%|
| Drawcalls |0.1853|0.1853|0.0000%|
| Postprocess |0.0844|0.0807|−4.3839%|
| Finish |14.0463|13.9734|−0.5190%|
| Sprite Render |0.3507|0.3487|−0.5703%|
| Portal |0|0|undefined percentage|

Sprite Setup pair-median differences are−2.3058%,−0.4595%,+1.9485%,+0.2590%,
−3.8872%. All differences are+0.3760%,−0.9698%,−0.7771%,+0.3583%,−1.3882%.
The median of paired percentage differences is−0.4595% Sprite Setup and−0.7771%
All; this is distinct from a ratio of mean medians. Signs are mixed. The first
current scored child includes4.555ms Sprite Setup,4.649ms full Setup and19.860ms
All; those observations remain included. No extreme scored Sprite Setup value
at or above5ms occurs in this packet.

These are quantized CPU `glcycle_t`/CheckBench snapshots. All includes submission
and Finish/wait; slices need not add up to an independent full-frame timer.
Small-slice percentages exaggerate tiny absolute changes. Prelaunch quiet does
not prove in-run background load. Static packages include550 authenticated
Git-source text newline projections among4,746 members: this is not a strict
one-variable byte-identical comparison and cannot establish a unique callback
cause. No GPU timestamp, universal frame budget or statistical inference follows.

## Retained history and aggregate interpretation

- [Original Dense40 scores](PF-020-DENSE-MEASUREMENT.json) show candidate Sprite
  Setup higher in all five historical pairs: median paired+3.91%, All+1.15%.
  The larger pair3 and drifting baselinepair5 remain recorded adverse
  observations. Their cause is unresolved; this result is not deleted,
  recalculated by replacement or attributed to a background process.
- [Selected24 recheck scores](PF-020-DENSE-TARGETED-RECHECK.json) rerun both
  members of prespecified extreme pairs3/4/5. Extreme spikes do not recur;
  Sprite Setup differences are−0.90%,+1.05%,+1.07%, All+1.28%,−0.77%,−0.62%.
  Selection prevents using them as a replacement original aggregate.
- [CPUv4 profiles](PF-020-CPU-PROFILE.json) decode both complete captures with
  zero loss/truncation and qualified engine stacks/scheduler coverage. Sprite
  light-list work dominates whole-lifetime samples that include startup.
  There are no exact steady-phase timing boundaries or causal acceptance.
- [Failed final attempts01/02](PF-020-FINAL-DENSE-CHECKPOINT.json) and
  [attempts03/04](PF-020-FINAL-DENSE-MEASUREMENT.json) retain every completed
  observation and strict quiet rejection. Their4/16/12 scores remain partial;
  they are not combined with each other or with fresh05. No failed receipt is
  relaunched. Revision2 changes bounded preparation patience, with the same
  strict15%/ten-consecutive predicate and fixed scoring.
- Fresh05 supplies the missing complete ordinary final-observer-source
  comparison. Its mixed descriptive CPU observations and exact state/images
  establish no confirmed material adverse final-runtime finding. They support
  the bounded release disposition, not a claim that the original adverse
  observations were false or that callbacks are free.

## Optimization outcomes remain separate

| PF result | Retained benefit / disposition | Limit |
|---|---|---|
| PF005 | Ordinary-upload arena allocation/wrap counts improve with unchanged format/mip processing. | Counts/resource churn; no GPU wall time. |
| PF016 | Qualified representative CPU setup median4.137→3.761ms; separate frames100–399 warm distribution improves4.45%, with actual light/order/state/image equivalence. | Target sprite/model collection; no universal frame gain. |
| PF018 | Matched MAP04 main-array capacity11,702,876→8,635,124logicalB; AABB310.378→159.175ns/movedline with1,630 exact rays. | BeginFrame20.129→20.082ms is mixed; logical bytes are not Vulkan residency. |
| PF019 | Avoided dormant descriptor/image/shader/pipeline construction. | Formula/source evidence; no new native GPU timing or resident-memory claim. |
| PF017 | Integrated candidate loses Setup+10.79% and All+2.42%; completely restored under accepted no-go. | No retained optimization or prototype savings. |

The [evidence matrix](PF-FREEZE-EVIDENCE-MATRIX.md) traces accepted source,
tests, images/state, PRs and limitation records for every PF result. Together
with the fresh complete final-runtime evidence, this satisfies aggregate review
and the declared no-quality-trade contract. Founding feature aspirations,
broader renderer modes, repaired P400, full bake and human visual approval stay
outside the proved bounds. Release requires its own final checks and verified
master integration; SDVK-001 is not implemented by this work.
