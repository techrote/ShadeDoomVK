# PF-020 ordinary Dense qualification protocol

Status: revised qualification completed at tool head `ef79361822199112ee2179414ce21b812178bca7`; **state/image gates pass, performance concern remains**. This
packet contributes current production CPU-overhead and main-image evidence to
[PF-020](issues/PF-020.md), without accepting its remaining view/sprite/key
equivalence gates. The historical PF017/CFX STOP scopes remain sealed.

## Fixed build/content identity

Only the two qualified local builds are permitted by
`tools/pf_oracle/run_freeze_dense_runtime.py`:

| Variant | Native source / executable SHA256 | Qualified candidate receipt SHA256 |
|---|---|---|
| baseline | `bd2586f51c456fcdb9d04e616a6facf30d47a5ec` / `e5ac64d21b2bbb0f893b6317957660085040ff6ef232f75485d08f3f33a00488` | `097c5457367ad1624f4be6fc205ce8be8e2252c85a4060aa8dfc416c90de268c` |
| candidate | `a113e2bc1644fe5e7e9079b49ef67308f83eecff` / `c287a601a803b467d585c24283edad2986d48f9c295a134a1843c9906a925813` | `7870042972d4a612fc6b1ecfeead3c655f4a40b834142bc6787ce1c66d30d352` |

Both are VS2022 x64 RelWithDebInfo builds. Full recorded Git source closures,
configuration/build logs and all eight build/staged counterparts must verify.
Their non-vkdoom.pk3 staged packages are equal; the uncompressed vkdoom.pk3
content difference is the accepted PBR shader repair. This healthy ordinary
fixture does not author PBR/probes/indexed translations. Neither build's
native diagnostic is invoked.

| Input | SHA256 |
|---|---|
| PF016_DenseLights_Interior.wad,242350 bytes | `21da7231bc1f81c32d15cda2150c840c6b670299a038a994f498fe680fd1d85e` |
| isolated stock Doom2 IWAD,14951361 bytes /2928 lumps | `31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab` |
| historical configuration seed | `b4e4f84eff7f212bf4584e7c417d4e749a628499add91e63ade2c817d0fdbaeb` |

The selected IWAD differs from the augmented historical Dense input; these are
fresh matched runs only. The immutable fixture has832 stationary POSS targets,
216 lights and one player start. The actual benchmark camera must remain
(-1850,0,41), yaw/pitch0; emitted draw/light counters must match the fixed
inventory. Presentation must decode as RGB8 at1904×1001.

## Physical run order and failure disposition

The first baseline warmup at tool head `6af00e847d2c7cb6d6b21ce8425e993eb65d0712`
completed all native/device/settings/count/input gates, but root rejected its
image because CVar query notifications remained across the top. The original
runner PASS receipt and pixels remain immutable in
[retained attempt disposition](PF-020-DENSE-RETAINED-ATTEMPTS.json). None of its
CPU snapshots is scored. No candidate or scored process ran under that head.

Revision: suppress UI notifications through the existing `show_messages=false`
and `con_notifytime=0` controls before startup/query output, while retaining stdout and actual CVar
proof. Re-run relevant guards from a new recorded tool head, then use fresh
`warm-baseline-02` / `warm-candidate-02` directories and pair directories.
This explicitly revised packet has exactly two unscored warmup processes
followed by five pairs:

```text
01 warm baseline
02 warm candidate
03 pair1 baseline, 04 pair1 candidate
05 pair2 candidate, 06 pair2 baseline
07 pair3 baseline, 08 pair3 candidate
09 pair4 candidate, 10 pair4 baseline
11 pair5 baseline, 12 pair5 candidate
```

Each process has its own fresh output directory, isolated live config/save/work
directory, one child handle and90s watchdog. Preparation verifies inputs and
creates a concrete command/config receipt; launch is separate and single-use.
No automatic retry, extra sample, discarded outlier or threshold adjustment
is permitted. A preparation/tool failure is retained and repaired at a new
recorded tool head before an explicitly revised attempt; a host/device failure
stops the physical packet. No global process kill or cache deletion occurs.

Root serializes all native work. No compiler/full-check job competes with the
CPU measurement interval. Existing driver/engine caches are left in place;
these runs do not claim isolated cold-cache measurements. Pre/post device and
Windows event metadata occur outside the measured child interval.

## Matched execution and acceptance

Renderer mode4; ordinary BSP with LevelMesh off; sprite lights2; multithreading
on; filter6; anisotropy0; scale1; uncapped/vsync off; windowed1904×1001. Input is
locked and autoload/autoexec/audio/joystick are disabled. UI query notifications
are disabled through `show_messages=false` and `con_notifytime=0`; stdout remains available.
Production diagnostics
and Vulkan validation are off. Environment sanitization and actual pre-capture
CVar queries are recorded, rather than inferred from a seed alone.

One semicolon command chain applies the locked settings/size, settles35 ticks,
records one excluded warm bench snapshot, warms350 ticks, pauses and settles60
ticks, records four bench snapshots separated by190 ticks, disables overlays,
queries settings, settles35 ticks, captures a screenshot, waits35 ticks and
emits completion before normal quit. These waits are requested protocol units,
not an assertion that an unobserved simulation/frame counter was captured.

Every child must exit0, finish the full chain and pass immutable source/tool/
input/package/STOP identities, actual adapter/settings/camera/count checks and
valid nonblank decoded PNG. Any failed gate preserves its raw receipt/logs and
prevents a passing paired conclusion. Requested overlay disablement alone is
not proof of a clean picture; root inspects the actual warmup capture before
the scored pairs.

For each of the five pairs, require exact decoded RGB equality (zero differing
pixels/channel error) at equal1904×1001. The room, actors and paused view are
static. If equality fails, record the difference and inspect its cause; do not
increase tolerance until it passes. The broad view/sprite/key evidence gap
remains independently open even if these main images match.

Retain all four scored CPU snapshots per child. Report raw values and per-run
medians for sprite Setup, Setup and All including Finish/wait, then the five
matched ratios and their median/range. No invented numerical pass/win target
is imposed; a measured regression remains a finding requiring explanation.
Built-in bench clocks are CPU snapshots, not GPU timestamps or a per-frame
distribution. FPS is context only.

## Measured disposition

The two fresh warmups and all five declared pairs complete:12 processes,
20 scored CPU snapshots per variant, unchanged input/source/package/STOP pins
and expected actual device/settings/camera/draw-light counts. All12 decoded
RGB images have SHA256
`ce28813599b98a19dd2bba4456e4acf587e29f9f18813547de1ae3ca69e22151`;
five scored pairs compare9,529,520 pixels with zero mismatches. Root inspected
both warmup images and confirmed query notifications are absent.

Candidate sprite Setup is higher in all five pairs: median paired increase
3.91%, range0.86–13.73%. CPU All including Finish/wait is higher by median1.15%,
range0.003–7.98%. Baselinepair5 itself drifts upward. All samples remain;
neither the large pair3 nor the drifting pair5 is excluded. These are measured
CPU snapshot differences, with cause unproved and no performance acceptance.
Each child contributes only four scored snapshots. All includes Finish/wait,
and the elapsed RDTSC timers can include preemption. Pair4 All medians differ
by0.0005ms, below the native0.001ms printed precision; its positive sign has
no demonstrated meaning. GPU power/temperature vary between runs, with no
continuous CPU-clock or scheduling trace. Independent raw-packet audit passes
within these limits; it does not establish causality or statistical significance.
The [compact measurement packet](PF-020-DENSE-MEASUREMENT.json) retains raw
values, exact order/build/content/source identities and limitations.

Bounded profiling must investigate the concern before optimization or a
no-regression claim. The earlier notification-bearing warmup remains a
separately rejected, unscored attempt. The full freeze remains blocked on this
concern and its separate applicable view/sprite/key evidence gaps.

## Limits and publication

The owner subsequently reported concurrent 3D-print slicing with CPU bursts
and explicitly requested reruns of extreme tests after slicing finished.
The separately preregistered targeted recheck selects original pairs3/4/5,
each containing a scored sprite Setup sample at least5.0ms. Repeat both sides
of each selected pair once, preserving alternating order and all original
samples/receipts. Two whole-process warmups remain unscored; the new six
scored children contribute24 snapshots in a separate packet. This descriptive
selection is not an exclusion rule or a new performance threshold. Source,
sealed binaries, settings, exact image gate and90s owned-child guard remain
unchanged; builds/tests/offline analysis pause during physical windows.
Quiet preparation records at least30 and at most120 one-second aggregate CPU
intervals, requiring the final ten below15% before native launch. That is a preparation condition,
not a performance gate or proof every source of interference was absent.
Failed preparation is retained. Rerun outcomes and possible slicing
interference do not replace the original measurement or establish causality.
The [targeted actual packet](PF-020-DENSE-TARGETED-RECHECK.json) records24 new
scored snapshots and three exact image/state pairs. Its sprite Setup differences
are−0.90%,+1.05%,+1.07%, with no recurrence of the extreme original spikes.
All original samples and both failed quiet preparations remain retained.

No founding-baseline→current whole-renderer speedup, GPU budget, PBR cost,
indexed cold-upload cost, packed ordered-light state, mirror/camera/probe-face
parity, sprite vertex/frame/UV equivalence, key cache partition, P400 or human
visual acceptance is inferred. Compact source-controlled metadata may publish
hashes/counts/timers and dispositions; private content/raw pixels/logs stay in
disposable evidence staging. Original receipts are immutable.
