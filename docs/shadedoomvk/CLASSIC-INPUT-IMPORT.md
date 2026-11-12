# Explicit classic Doom input import

Scope and remaining acceptance: [issue #188](https://github.com/techrote/ShadeDoomVK/issues/188).

This bounded importer plays the **input commands** in a single-player Doom
version-109 short-tic LMP through current ShadeDoomVK game rules. It is not a
vanilla, Crispy or DSDA simulation backend. Original movement trajectories,
monster behavior, damage, completion time and speedrun synchronization are not
guaranteed. A console warning and persistent in-game HUD warning identify that
distinction. The version byte does not identify the recording source port.

```text
vkdoom -iwad <matching-doom2.wad> -playclassicinput <demo.lmp>
```

The equivalent console command is `playclassicinput <demo.lmp>`. It requires
single-player without an already active demo. The ordinary `-playdemo` and
`playdemo` commands retain the native FORM/ZDEM path and still reject a classic
LMP. The explicit importer cannot be combined with `-playdemo`, `-timedemo`,
`-record` or `-loadgame`. It does not turn on benchmark timing or force game tics.

The decoder validates the complete input before changing level or game CVars:
13-byte version-109 header, skill 0–4, Doom II episode 1/maps 1–32 or Doom
episodes 1–4/maps 1–9, player zero alone, non-deathmatch, boolean monster flags,
complete four-byte tic records and a final `0x80` marker without trailing data.
Longtics, Boom/MBF/extended headers, multiplayer/deathmatch, reserved button bits
and pause/save special commands are rejected descriptively. An imported file
cannot issue a savegame or arbitrary native demo command.

The recorded skill and respawn/fast/no-monsters flags select ordinary current
game setup. Generic demo backup restores the non-latched game flags. Because
that inherited backup deliberately excludes latched CVars, the importer privately
captures/restores its original `skill` and `deathmatch` values at end, abort,
new-game/load, switch to another demo or initialization error. This does not
change the native FORM path's inherited restoration behavior.

If `skill` or `deathmatch` already has a pending latched user change, import is
rejected before modifying the level or CVars, with the pending request untouched.
New latched user requests made during import stay queued: immediate restoration
uses `ForceSet`, which does not consume that queue. A later ordinary new game
can apply those requests normally. Other current rules, compatibility
settings, actor scripts, physics and RNG policy remain intact. Matching content
must be supplied by the user; the LMP does not authenticate an IWAD/PWAD or patch.
The importer does not supply an old RNG, secretly enable a compatibility preset,
correct actor coordinates, grant inventory or change gameplay to recover a route.

Each ordinary game tic imports signed eight-bit forward/side/yaw commands into
the current 16-bit input units, multiplying by 256 with defined signed arithmetic.
Attack/use retain their standard bits. Classic weapon groups 0–6 request current
owned-slot selection in slots 1–7; group 7 requests an already owned Chainsaw.
Current slot priorities, ammo rules and inventory-use behavior apply, rather than
claiming original vanilla weapon-toggle semantics. No weapon is created.

The supplied local `lv01-529.lmp` is 914 bytes: version 109, skill 3, episode/map
1/1, player zero, default monster flags, 225 complete tics and the final marker.
Its buttons use only attack/use. CPU decoding is not evidence that the recorded
route synchronizes or completes under current rules. Native positive, malformed
input and native-FORM regression checks remain necessary for integration.

## Implementation and provenance

`src/g_classicinput.h` is a repository-authored bounded decoder, independently
reimplemented from the published byte format. `g_game.cpp` adds an explicitly
selected reader and owns initialization/cleanup. Native FORM parsing, native tic
decoding and native recording bodies remain unchanged and are pinned by CPU
regression checks. `g_statusbar/shared_sbar.cpp` distinguishes the imported input
from the existing native-demo version warning.

Primary format references:

- [id Software DOOM at a77dfb96](https://github.com/id-Software/DOOM/blob/a77dfb96cb91780ca334d0d4cfd86957558007e0/linuxdoom-1.10/g_game.c),
  `G_ReadDemoTiccmd`, `G_DoPlayDemo` and `G_BeginRecording` (the Linux release's
  version number is 110; the common header/tic layout is used as a reference).
- [Chocolate Doom at a2dfd51f](https://github.com/chocolate-doom/chocolate-doom/blob/a2dfd51fcc00d272dc8a17a97ccd6683333ff4ea/src/doom/g_game.c),
  version handling and short-tic decoding.
- Existing ShadeDoomVK `G_BuildTiccmd`, native demo lifecycle, current
  `PlayerPawn.PickWeapon` and `UseInventory` establish current-engine meaning.

No donor source was copied or cherry-picked. The inherited non-FORM rejection
predates ShadeDoomVK; the new entry point is an opt-in input adapter, not a
claim that inherited Doom demo synchronization has been repaired.
