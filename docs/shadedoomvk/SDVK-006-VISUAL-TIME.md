# SDVK-006 — renderer visual-time and interpolation contract

Status: implementation/qualification candidate on `sdvk-006-render-visual-time`. Acceptance still requires exact-head CI, software-Vulkan qualification, merge and post-merge verification.

## Ownership and clock source

The visual clock is renderer presentation state, not simulation state. `RenderVisualTime::Clock` is a deterministic state machine in `src/rendering/r_visualtime.h`. Production sampling uses `std::chrono::steady_clock` through `MonotonicTimestampSeconds()`; it does not use `I_GetTime`, `I_GetTimeFrac`, `I_nsTime`, `gametic` or `TimeScale` as its delta source.

PF-010 ownership is explicit:

| Context | Visual-time scope | May advance/reset main clock? | Interpolation continuity |
| --- | --- | --- | --- |
| visible MainView, eye 0 | `main-owner` | yes, once per top-level `RenderViewpoint` | main clock state |
| visible MainView, later stereo eye | `main-sibling` | no | same main snapshot |
| portal/mirror rooted in MainView | `main-portal` | no | inherited main snapshot |
| camera texture | `non-main-fallback` | no | own accepted tic fraction; no main-clock dependency |
| light-probe face | `non-main-fallback` | no | own accepted tic fraction; probes already force no interpolation |
| save picture | `non-main-fallback` | no | own accepted tic fraction |
| portal rooted in any non-main root | `non-main-fallback` | no | inherits non-main fallback |

Non-main fallback exposes zero/invalid visual delta and zero accumulated visual time. It is intentionally not a second global timeline. Querying or destroying/recreating a context is pure and cannot consume the next main delta.

## Main-view state machine

`Clock::MaxDeltaSeconds` is **0.2 seconds**. The applied accumulated visual time is the sum of accepted/bounded visual deltas, not raw wall-clock age.

- **First valid frame:** anchor timestamp, delta 0, invalid interpolation, reason `first-frame`.
- **Normal positive delta <= 0.2 s:** delta is exact raw steady-clock difference; accumulated visual time advances by that amount.
- **Repeated timestamp:** valid delta 0, accumulated time unchanged, reason `repeated-timestamp`.
- **Long frame > 0.2 s:** applied delta clamps to 0.2 s, accumulated time advances by 0.2 s, continuity is invalid for that sample, generation advances, reason `long-frame-clamped`.
- **Rollback:** zero/invalid delta, generation advances, the finite timestamp becomes the new anchor, reason `clock-rollback`.
- **Non-finite or negative timestamp:** zero/invalid delta, prior anchor is discarded, generation advances, reason `invalid-timestamp`.
- **Pause:** timestamp is continually re-anchored while accumulated visual time is held; the first paused sample advances generation. Paused wall time is never paid back.
- **Resume:** zero/invalid delta for one sample, new anchor, generation advances, reason `resume`.
- **Interpolation globally disabled (`cl_capfps` or `r_NoInterpolate`):** the visual delta remains usable, while `interpolation_valid=false` and ordinary actor presentation remains at the authoritative current endpoint.
- **Temporary absence of main rendering:** no clock operation occurs. A later main view sees the actual elapsed interval and therefore either resumes normally or takes the explicit long-frame clamp/discontinuity path.

The clock is process/renderer owned rather than Vulkan-device owned. Device/swapchain recreation therefore does not itself destroy the timeline; a long period with no main view is handled by the bounded-stall rule.

## Explicit discontinuities

- `G_DoLoadLevel` resets with `level-load`; this covers ordinary map load, level transition/restart and save/load paths that reconstruct a level.
- `PerformWipe` resets with `wipe` after time is unfrozen and the wipe finishes.
- Existing view cuts call `R_ResetViewInterpolation`. `R_SetupFrame` snapshots the pre-existing `NoInterpolateView` signal into that viewpoint. Only a PF-010 MainView owner may translate it to a `camera-cut` visual-clock reset. Camera textures/probes cannot reset the main clock accidentally.
- The first main sample after any explicit reset has delta 0 and invalid interpolation; accumulated visual time is retained.

## Opt-in alpha/scale interpolation

Two render flags are added without changing defaults:

- `RF2_INTERPOLATESCALE = 0x1000`
- `RF2_INTERPOLATEALPHA = 0x2000`

`AActor::ClearInterpolation()` snapshots `Scale` and `Alpha` every existing interpolation boundary even when the flags are disabled. Enabling a flag therefore does not create a separate simulation update path. `RF_DONTINTERPOLATE` remains authoritative and overrides either new flag.

The hardware sprite presentation path sanitizes the accepted tic fraction to [0, 1]. A main-view discontinuity forces fraction 1 for alpha/scale for that sample. Endpoints are returned exactly; finite intermediate values use a bounded linear interpolation; disabled flags return the authoritative current value exactly. Position/angle interpolation and authoritative `Scale`/`Alpha` storage are unchanged.

This is presentation only. No render delta is read by `P_Ticker`, gameplay movement, actor state advancement, networking, demos or save serialization.

## Script/API surface

`Object.GetRenderDeltaTime()` and `Object.GetRenderVisualTime()` are declared `ui native static`. They expose the last accepted main-view presentation sample only. Invalid delta reads as 0. The API is intentionally UI-scope so it is not a gameplay clock.

C++ consumers use the typed `RenderVisualTime::Sample`, including validity, interpolation validity, generation, clamp flag and discontinuity reason. Hardware consumers use `GetHWVisualTime(const HWRenderContext&)` for PF-010 scope.

## Diagnostics

SDVK-002 observations retain the existing mechanism. Frame and render-context records add a nested `visual_time` object with:

- `scope`
- `advances_main_clock` on contexts
- `delta_seconds`
- `accumulated_seconds`
- `generation`
- `main_frame`
- `delta_valid`
- `interpolation_valid`
- `clamped`
- `discontinuity`

This makes main -> portal -> main and non-main fallback behavior machine-readable without inventing a second evidence channel.

## Donor reassessment

MAD-VKDoom `316b18a4d96b1a120c681d368ac670286234bcc8` supplied the useful concept of bounded renderer delta, but its global previous-time/minimum-clamp implementation is not transplanted: ShadeDoomVK uses PF-010 ownership, no positive minimum delta, explicit pause/reset/rollback states and an unscaled monotonic wall clock.

MAD-VKDoom `7d1f2df404711986a3cc742dad1f9e6e0ac69cde` supplied the useful opt-in previous-scale/previous-alpha presentation concept. ShadeDoomVK retains donor-compatible flag bit positions `0x1000/0x2000`, adds finite/exact-endpoint handling, preserves `RF_DONTINTERPOLATE`, and gates main-view continuity through the new clock. No generalized donor animation system is imported.

## Deterministic qualification

`tools/pf_oracle/tests/visual_time_fixture.cpp` covers first/repeated/normal/long/rollback/non-finite time, pause/resume, load/wipe/cut resets, endpoint/intermediate/disabled interpolation, varied render cadence with a fixed simulation sentinel, main/stereo/portal context sharing, camera/probe/save fallback, nested non-main portals and context recreation.

`test_visual_time_contract.py` asserts production ownership, reset hooks, opt-in flag plumbing, absence from `p_tick.cpp`, UI-only script declarations and SDVK diagnostic fields. Full `tools/check.py`, native software-Vulkan corpus, source/build identity and hosted CI remain acceptance gates.
