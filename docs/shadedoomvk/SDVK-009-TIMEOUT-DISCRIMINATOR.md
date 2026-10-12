# SDVK-009 hosted software timeout discriminator

This is a **diagnostic-only** continuation of issue #9. It is deliberately separate from frozen PR #146 and is incapable of granting that PR's matching-content qualification a pass.

## Frozen renderer and workload

The renderer source is checked out and built from exact PR #146 head `14c2ecefad41374d39a8fb9d369d510251b9dd6e`. The diagnostic harness may live on a later tooling commit, but it must not build that tooling commit as the renderer.

The single native renderer launch preserves the failed control request:

- authored `shadow-boundary` content and settings;
- official sealed Freedoom 0.13.0 content identity used by PR #146;
- 640×480;
- state mode;
- 120 warmup frames plus one retained frame;
- no GPU timestamps;
- no collision snapshot or publication witness;
- one process only, automatic retries zero;
- exactly 600 seconds to successful native completion.

No workload, threshold, selection, shader math, quality setting or acceptance rule is relaxed.

## Failure boundary

If the renderer remains alive at 600 seconds, the harness first writes and fsyncs a timeline receipt with `failure_irrevocable=true`. Only after that durable boundary may it inspect or attach to the process. Evidence collected after the boundary can diagnose the already-failed run but cannot turn it into a pass.

The bounded post-deadline packet contains, where the host permits:

- external `/proc` process CPU/RSS/I/O samples taken at five-second intervals, plus bounded output-file size/mtime progress;
- per-thread `stat`, `status`, `wchan` and kernel `stack`, with parsed CPU ticks;
- process `stat`, `status`, `wchan`, kernel `stack`, `io`, limits and scheduler state;
- bounded open-file-descriptor targets;
- bounded descendant-process state;
- one `gdb -batch` all-thread backtrace attempt, only after the deadline, with a 30-second attach budget;
- explicit process start, failure deadline, diagnostic start and termination UTC timestamps;
- termination method and whether SIGKILL was required.

Unavailable `/proc` or ptrace evidence is retained as an explicit failure/unavailable receipt rather than silently omitted.

## Execution surface

Native execution is permitted only on GitHub-hosted Linux with a single explicitly selected Mesa lavapipe ICD. The existing software preflight must identify one CPU llvmpipe device and required Vulkan features before the renderer process. Physical GPU execution remains prohibited.

The workflow runs only on the dedicated diagnostic branch `sdvk009-timeout-discriminator-20261012`. Normal CI is not retried by this branch push.

## Interpretation

A timeout packet may distinguish continuing CPU/software-GPU work from a stable wait/stall location. It does **not** establish physical-fault causality, shader execution identity, architecture acceptance, performance acceptance, or a successful #146 qualification. Root cause remains `UNDETERMINED` unless later evidence supports a narrower claim.
