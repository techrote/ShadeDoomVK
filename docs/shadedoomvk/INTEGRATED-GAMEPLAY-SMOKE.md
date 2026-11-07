# Ordinary-input integrated gameplay smoke

Status: initial physical gameplay correctness passed on the frozen source
identified below; normal exact-head CI and guarded integration remain required.
The corpus combines
the existing authored live-player PBR room, classic and PBR world sprites,
normal/PBR weapon materials, colored local lights, actor environment probes,
sunlight and a line mirror with actual movement, firing and map/resource rebuilds.
All new content is authored here. Supply a legal Doom2-compatible IWAD such as
Freedoom and retain its hash/license through the ordinary capture harness.

This is one explicit `gameplay-smoke` recipe, two authored maps (`SDVGPA` and
`SDVGPB`), 32 warmup views and 128 retained views. Only the matching opt-in
`-sdvkgameplaysmoke` driver can issue its fixed commands. It uses ordinary
`+forward/-forward`, `+right/-right`, `+attack/-attack`, console `wait` game tics
and `map`; it never writes player movement, aim, ammo, gameplay time or a forced
camera. `cl_capfps=true` selects the engine's ordinary 35-FPS waiting policy,
with no `singletics`, fixed interpolation or simulation override. A later phase
fails closed if an earlier wait/key release or map transition is still pending.

| Retained view | Completed-view evidence | Next ordinary input |
|---|---|---|
| 8 | Initial live player/weapon, ammo, resources and PNG | Forward for six game tics, release |
| 24 | Actual player displacement and changed PNG | Turn right for four tics, release |
| 40 | Actual yaw change | Attack for eight tics, release |
| 56 | Actual Clip depletion and muzzle-light reset | Load map B |
| 80 | Map B, reset inventory and fresh current LevelMesh/probe resources | Attack for eight tics, release |
| 96 | Actual map-B ammo depletion | Reload map A through ordinary `map` |
| 120 | Reset inventory, third distinct mesh owner and muzzle reset | No further input |

The weapon uses actual `A_FireBullets` with Clip ammo and existing
`A_Light1/A_Light0`. Both ready and firing sprites have authored PBR materials.
Passive observation reads the real player position/yaw, ready weapon, inventory
amount, input state and `player.extralight`. Missing movement, turning, ammo
consumption, visible enhanced draws, muzzle light/reset, completed map ownership
or checkpoint images fails admission. Probe absence during initial rebuild is
explicit; checkpoints require the new owner's actual published pair. The driver
never reads these outcomes to manufacture a pass.

Seven fixed quiet PNGs and the first actually observed muzzle view in each map
come from the ordinary screenshot writer after completed main views and before
the next input. Each muzzle image must join a same-frame PBR firing draw, positive
actual extralight and ammo decrease, and differ from its preceding ready image.
No attack is prolonged to obtain a screenshot. Their original file pins and decoded RGB hashes
are retained. Initial/moved images must differ. Ordinary tic/render scheduling
remains observable, so this corpus does not register an exact cross-process
dynamic state or image comparison. Existing static camera and exact comparison
gates remain unchanged. There is no new physical-performance, POM, static-lightmap
bake, general GI or arbitrary-mod compatibility claim.

All 128 frame, player, resource and emitted viewmodel snapshots remain retained.
The four large per-draw families (`material`, `probe`, `pipeline`, `shadow`) are
retained only for the seven fixed checkpoints and first actual muzzle view in
each map. Selection is latched before that frame's first draw from ordinary
player extralight; it never changes input or extends a firing phase. Each player
snapshot declares its selection, and admission derives the same exact nine
frames from actual player state. Their material/probe/pipeline/shadow records
and first-muzzle PNG joins are mandatory. Other recipes retain full diagnostics.
The 16 MiB record-store limit remains unchanged. A CPU replay fixture preserves
all 223 payload rows from the retained real legacy capture, demonstrates the
prior 128-frame overflow, and checks the selected policy with additional
maximum-size gameplay and checkpoint records reserved at their full cadence. This is a capacity
regression test; it does not qualify a native gameplay run or performance.
The structural admission exception is explicitly bound to this validated recipe:
all 128 critical snapshots remain mandatory, and only the four detail families
use the nine frames derived from actual player/map/extralight state. A retained
4be native capture supplies the CPU regression: its original attempt remains
`FAILED_STOP` because the former structural gate required detail on every frame.
Replaying those unchanged records with the corrected gate is a CPU validation
result, not a new native run or acceptance of the failed attempt.
The retained payload exhausts the old policy at frame 39. The selected replay
uses 9,890,888 bytes against the unchanged 16,777,216-byte limit, including those
maximum-size reservations, and verifies the stored frame IDs after serialization.

Prepare without executing a renderer:

```text
python tools/renderer_oracle/prepare.py --out build/gameplay-input --scene gameplay-smoke
```

After build/source and execution-plan review, the existing capture interface is:

```text
python tools/renderer_oracle/run.py capture --exe <reviewed-executable> --iwad <legal-freedoom2.wad> --prepared build/gameplay-input --out build/gameplay-run --scene gameplay-smoke --mode state --frames 128 --warmup 32 --timeout 600 --include-stress
python tools/renderer_oracle/run.py validate build/gameplay-run
```

The hosted isolated software-Vulkan lane supplies repeatable CI correctness
coverage. Its full plan now has 56 processes: 40 static state captures, 15 descriptive timing
processes and this one gameplay capture. The 20 static pair comparisons remain.
The physical supervisor's fixed-three workload remains unchanged. Its optional
registered workload profile admits this recipe only as one `sdvk011-viewmodel`
state process at 640×480 with 32 warmup and 128 retained frames, no GPU timing or
pair comparison, and all nine required checkpoint images. The actual capture
argv is rederived before the native gate. A sealed registration, independent
packet review and explicit authorization are required before physical execution.
The owner's 7 November correction authorizes a fresh source-matched physical
campaign; this small workload may run after its build and prospective plan are
reviewed while normal hosted CI is pending. A required CI failure still blocks
integration. Historical STOPs remain retained, and the dense-shadow fault is a
separate unresolved workload.

For ordinary interactive use, load the generated scene PK3 and `+map SDVGPA
+gl_viewmodel_lighting 2` without observer/input-driver flags or capture script.
Use normal bindings to move and fire. The automatic driver is inert by default.

## Initial physical validation and pause

The fresh generation-07 process at source
`8ce112bb6aaf6e7068e2715170afda7a2960ca8a` exited 0. All 128 critical
frame/player/resource/viewmodel snapshots and nine required images passed their
native admission. The actual detail frames were 8/24/40/41/56/80/81/96/120;
12,251,041 retained bytes and 8,105 records fit the unchanged limits, with zero
dropped records. Movement reached x=57.62, turning reached yaw=-8.7891 degrees,
Clip dropped 40 to 39 on both maps, and muzzle light returned to zero. Current
LevelMesh owners were 3/5/7 across A/B/A. All 104 ready and 24 firing weapon
draws used the enhanced PBR path. Image joins included the two actual firing
views rather than synthetic poses.

The [evidence summary](evidence/SDVK-011-GAMEPLAY-PHYSICAL-20261107.json) keeps
the successful fresh attempt distinct from the earlier structural-gate STOP.
This single ordinary-tic capture has no exact cross-process dynamic comparison
or GPU timing claim. LevelMesh rendering and shadows were off; no static bake,
HUD POM or dense-shadow stability is qualified. The owner directed delivery of
this initially validated gameplay increment and then a
[documented pause](PROGRAMME-PAUSE-20261107.md), with the separate special-surface
repeatability work deferred.
