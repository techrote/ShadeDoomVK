# Ordinary-input integrated gameplay smoke

Status: implementation/preparation candidate; no native gameplay result is
claimed until the reviewed source is built and executed. The corpus combines
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

Prepare without executing a renderer:

```text
python tools/renderer_oracle/prepare.py --out build/gameplay-input --scene gameplay-smoke
```

After build/source and execution-plan review, the existing capture interface is:

```text
python tools/renderer_oracle/run.py capture --exe <reviewed-executable> --iwad <legal-freedoom2.wad> --prepared build/gameplay-input --out build/gameplay-run --scene gameplay-smoke --mode state --frames 128 --warmup 32 --timeout 600 --include-stress
python tools/renderer_oracle/run.py validate build/gameplay-run
```

First qualification belongs on the hosted isolated software-Vulkan lane. Its
full plan now has 56 processes: 40 static state captures, 15 descriptive timing
processes and this one gameplay capture. The 20 static pair comparisons remain.
The physical supervisor's fixed-three workload remains unchanged. Its optional
registered workload profile admits this recipe only as one `sdvk011-viewmodel`
state process at 640×480 with 32 warmup and 128 retained frames, no GPU timing or
pair comparison, and all nine required checkpoint images. The actual capture
argv is rederived before the native gate. A sealed registration, independent
packet review and explicit authorization are required before physical execution.
Historical STOPs remain retained.

For ordinary interactive use, load the generated scene PK3 and `+map SDVGPA
+gl_viewmodel_lighting 2` without observer/input-driver flags or capture script.
Use normal bindings to move and fire. The automatic driver is inert by default.
