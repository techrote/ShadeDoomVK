# Classic Doom input playback — current-rules adapter (merged)

**Source authority:** ShadeDoomVK `master`, integrated via [PR #189](https://github.com/techrote/ShadeDoomVK/pull/189), merged 12 November 2026 as `00567bae465ab263b9ee9503cdf9c840c41d2028`. Feature issue: [#188](https://github.com/techrote/ShadeDoomVK/issues/188). Reviewed original PR head: `7bd023c8b9edc72c169ca711f6208e54d4b7cf5f`.

**Retrieval queries:** classic LMP, v109 short-tic demo, DSDA input, playclassicinput, playdemo rejection, vanilla sync, latched CVars, movement playback, owned weapon.

## What is actually implemented

The opt-in importer decodes single-player Doom version-109 **short-tic inputs** and feeds them into *current* ShadeDoomVK simulation. It is not a vanilla/Crispy/DSDA simulation or deterministic speedrun playback system. The original map route can diverge under current physics, RNG, monster AI and inventory policy. The UI gives a console warning and persistent HUD warning about this limitation.

- CLI: `vkdoom -iwad <matching.wad> -playclassicinput <run.lmp>`.
- Console: `playclassicinput <run.lmp>`. Native `playdemo`/`-playdemo` remain FORM/ZDEM-only; no hidden format auto-detection.
- Rejects concurrent demo recording/playback, multiplayer, incompatible CLI demo modes, unsupported files and pending latched `skill`/`deathmatch` changes before map/CVar mutation.
- Preflights complete 13-byte header, v109 marker, skill/map/episode, single player, flags, 4-byte tics, exact terminal `0x80`, and no trailing bytes. Rejects longtics, Boom/MBF or other extended layouts, reserved buttons and pause/save specials.
- Reads signed byte forward/side/yaw as current 16-bit units using defined multiplication by 256; attack/use bits map through; weapon requests resolve **owned** current slots rather than grant inventory.
- Saves and restores importer-owned `skill` and `deathmatch` immediately on completion, interruption, failed initialization or transition to another game/demo. Preserves new user-latched requests made during playback. Native demo cleanup is not retrofitted to this implementation.

## Source/ownership map

| Path/symbol | Responsibility |
| --- | --- |
| `src/g_classicinput.h`: `ClassicInput::Parse`, `DecodeTic`, `StartupValues` | Bounded byte admission, tic decode, latched-value snapshot/restore. |
| `src/g_game.cpp`: `G_DoPlayDemo`, `G_ReadDemoTiccmd`, `G_StopClassicInputPlayback`, `playclassicinput` | Explicit activation, game-tic consumption, owned inventory selection, cleanup on lifecycle transitions. |
| `src/d_main.cpp` | Argument admission and mutual exclusions. |
| `src/g_statusbar/shared_sbar.cpp` | Prominent *current rules, not original sync* HUD disclosure. |
| `src/common/console/c_cvars.cpp/.h` | Pending latched-change check without discarding queued user intent. |

**Provenance:** Format adapter was independently reimplemented from the published Doom/Chocolate Doom formats. No copied donor source. The v109 version byte cannot authenticate which port recorded an LMP.

## Tests and evidence

PR #189 records 13 focused admission/lifecycle/compiled CPU tests; 225-tic and 1,022-tic DSDA-sourced inputs; nine native cases retaining 36 images; and two green exact-head workflows ([CI](https://github.com/techrote/ShadeDoomVK/actions/runs/43187965180), [source](https://github.com/techrote/ShadeDoomVK/actions/runs/43187965021)). Earlier failures and cleanup fixes remain in PR history. Native cases exercised map transitions, interruption, restoration, malformed rejection and FORM preservation.

**Do not infer:** vanilla demo synchronization, faithful route/time, guaranteed matching PWAD, recorded physics, benchmark-grade timing, multiplayer support or acceptance of unrelated renderer milestones.

Further reading: [full implementation note](../CLASSIC-INPUT-IMPORT.md), [gameplay smoke](../INTEGRATED-GAMEPLAY-SMOKE.md), [PR #189](https://github.com/techrote/ShadeDoomVK/pull/189).
