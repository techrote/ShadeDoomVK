# SDVK-161 — isolated native startup fixture candidate

**Status:** Source + targeted native qualification required. Draft/HOLD; no
renderer, fixture tolerance, or full SDVK-009 publication acceptance implied.

## Scope and causal evidence

Original native SDVK-161 attempts differed on retained texture epoch
(3 versus 4) even when exact RGB and all wall submissions agreed.
The independently collected lifecycle trace identified the exact cause:
`FGenericStartScreen::DoProgress()` sometimes redraws its temporary
startup bitmap, invoking `StartupTexture->CleanHardwareData(true)`,
which retires one extra, legitimately registered hardware texture.
See issue #161, [startup trace](https://github.com/techrote/ShadeDoomVK/actions/runs/43598571683),
and its retained artifact #14115328793. Source-local retirement is
legitimate. Removing `TextureEpoch.Invalidate()` or normalizing lifetime
generations would conceal a valid resource event.

This candidate changes **only** the original
`special-surface-lifecycle` recipe bootstrap by inserting the supported
`-nostartup` command-line flag immediately after `-stdout`. The
accepted `GetGameStartScreen()` implementation bypasses progress-screen
creation when that flag is present. The authored maps, startup map selection,
input commands, other renderer fixture recipes, all 32 warmup views, all 96
retained views, original 12 detailed witness frames, all image checkpoints
and 35 intended-reason negative controls remain unaltered.

The revised command-line argument list is source-pinned, and the previous
one is an explicit failing pre-fix fixture regression. This is a change to
the *authored native fixture input*; it cannot retroactively qualify a prior
packet or justify a production renderer patch.

## Independent qualification gates

1. Full `tools/check.py`: PF, source, deterministic authored corpus, and
   original renderer CPU contracts on the new exact source.
2. Original `tools.renderer_oracle.sdvk161_special_surfaces.qualify()`
   in **four independently registered pairs** (eight original 32+96 native
   processes, never retried), with exact 35 original falsifying controls and
   twelve original checkpoint images per process.
3. Independently validate all eight original run packets, actual executed
   native `-nostartup` argv, original scene/receipt/content/build identity,
   original lifecycle/method and 35 negatives each.
4. Compare **all 28 distinct native attempt pairs** using the unchanged
   `run.compare_runs()` semantic-state projection and exact 640×480 RGB8
   gate. Require all 28 PASS and identical first-retained texture epochs.
5. Retain the full original logs, PNGs, native states, negative reports,
   full comparison deltas and exact build/source identities, including
   failure packets. No late retries or suppression.
6. Separately investigate the original intermittent missing immediate wall
   quad (80 versus 84 vertices, 22 versus 23 empty light uploads) recorded
   in full PR #201 run #627. A green targeted fixture run does not prove
   the intermittent wall problem has disappeared.

## Merge/release restrictions

The targeted workflow runs on the isolated candidate **branch push only**.
It does not trigger the full SDVK-009 publication worker DAG or make
PR #196 or PR #201 ready for merge. Do not create a pull request until
the missing-wall issue is reconciled, since the repository's ordinary PR
workflow would automatically execute the expensive full publication
campaign contrary to the current investigation sequencing. Owner review
and the full exact-head integration qualification remain separate gates.
Physical bake/scaling/stability are unaccepted.
