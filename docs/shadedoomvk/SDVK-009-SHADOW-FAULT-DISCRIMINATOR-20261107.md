# SDVK-009 warmup extent discriminator — 7 November 2026

**Prospective diagnostic, not a fault repair or physical acceptance.** The new
owner-authorized generation-02 campaign at renderer `9cf86b92dac3ae784eea0554d24ca18a43a3120c`
completed compositing, then stopped on its first shadow-boundary process. No
shadow repeat ran. The retained assessment reports nvlddmkm event 153 and 103
Vulkan type-4 address rows. Type 4 is an **unknown instruction pointer**, not proof
of an invalid memory read, a unique shader, a driver cause or hardware failure.
No completed shadow state/image, CPU collision snapshot or CFX warmup trace was
available. The fault-frame extent and actual selected lights remain unknown.
The packet and prior physical STOPs remain unchanged. This source change runs no
experiment and does not authorize one.

## Source-backed bootstrap finding

The failed stdout logs startup `Resolution: 1520 x 825` despite CLI 640x480.
`V_InitScreenSize` sets `vid_defwidth/vid_defheight` from CLI arguments
(`v_video.cpp:319–343`), while initial Windows window placement uses separate
`win_w/win_h`. If absent, these default to 80% of monitor **outer** dimensions
(`win32/base_sysfb.cpp:294–298`); client borders explain the observed startup size.

This does **not** establish an oversized first world frame. `V_Init2` prints the
startup resolution before execution of `+exec`. The existing capture script's
`vid_setsize 640 480` is deferred during startup (`c_dispatch.cpp:264–286`), then
executed synchronously by `C_RunDelayedCommands` (`d_main.cpp:3540`) **before**
`G_InitNew` (`d_main.cpp:3627`) and the first ordinary world `D_Display`.
`SetWindowSize` adjusts from client to outer dimensions and reads the client back.
Source order therefore supports a resize before world drawing; actual failed
runtime viewport/submission evidence is still missing.

Read-only `AdjustWindowRectEx` on the current host returns outer 656x519 for
client 640x480 with the engine's style/ex-style. The completed compositing engine
independently persisted `win_w=656`, `win_h=519`. A separate private draft adds
only those two values and `win_maximized=false` to immutable input config copies.
These values are host/DPI dependent, not portable client dimensions. Setting
`win_w=640,win_h=480` would reduce the client and is not an equivalent workload.
Initial-window normalization alone is not an evidenced TDR repair. A stock/current
comparison must declare the same policy on both sides.

## Narrow production diagnostic

With existing CFX tracing enabled, `VulkanRenderDevice::BeginFrame` now emits one
`frame-extents` row after allocations and before shadow/world draws. It records
the native client, `DFrameBuffer`, screen/scene viewport and allocated screen/scene
buffer dimensions, plus shadow mode and actual ray-query routing. It covers
warmup rather than waiting for the retained frame. CFX frame/tic/submission
identities remain in the existing trace columns. This is application-recorded
state, not a driver execution trace or historical fault attribution.

Tracing remains off by default. There is no new GPU copy, submit, wait, light cap,
quality change or traversal change. The existing trace's bounded records, tail
rotation and omission semantics remain; a rotated/missing prefix cannot establish
complete warmup coverage. Existing NV checkpoint markers may further separate
the legacy shadow-map producer from scene tracing if the device supports them.

## Prospective packet difference; not executable instructions

A fresh independently reviewed supervised packet would have to pin a newly
built clean renderer commit/tree/EXE and declare all changes before launch:

| Field | Prospective value / retained limit |
|---|---|
| Content, lights, shading | Original scene PK3/IWAD, 1,025 authored lights, shadow mode 2, `vk_rayquery=false`, all original quality settings |
| State capture | 640x480, 120 warmup frames, one retained frame, 180-second deadline; no retry |
| `CFX_TRACE_FILE`, `CFX_RUN_ID` | Fresh stage-owned trace path and unique generation identity |
| `CFX_RESOURCE_TRACE`, `CFX_WITNESS_DIR` | Remain absent; no post-use GPU readback |
| Native extension | Existing trace activation requests optional `VK_NV_device_diagnostic_checkpoints`; availability must be recorded |
| Optional CPU snapshot | Existing `-sdvkcollisionsnapshot` is state-only; current strict fixed-three packet rejects extra capture fields/argv. A reviewed explicit registration/argv derivation is required before using it; do not bypass that guard. |
| Initial window | Preserve the original policy for the stock comparison unless a separate changed policy is explicitly reviewed for both engines |

The current fixed-three supervisor also has one campaign-wide sealed environment.
Successive renderers would reopen a single `CFX_TRACE_FILE` with truncation.
Stage-owned paths or an explicit archival boundary need reviewed registration;
merely enabling one global path cannot establish complete campaign coverage.

The stock-engine comparison precedes this possible instrumented experiment.
Neither a successful startup nor a diagnostic capture constitutes SDVK-009
physical acceptance. Normal exact-head qualification and independent experiment
review remain required.

Focused CPU validation: 21 existing hardware-upload/publication controls pass.
The changed renderer translation unit compiles with MSVC using candidate source
headers and baseline generated headers. This is a compile check, not a linked
executable identity or a physical run. Private preparation failures and the final
compile receipt are retained under `prepared-workloads`; no GPU was executed.
