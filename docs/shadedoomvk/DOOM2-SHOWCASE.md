# Doom II and DBP50 material showcase

These optional add-ons use ShadeDoomVK's existing hardware renderer. The
flashlight is a standalone ZScript add-on. The material builders interpret the
artwork in a local copy of Doom II and, optionally, DBP50. The gameplay packs
contain auxiliary normal, metallic, roughness and ambient occlusion layers.
The original sprite and texture artwork, animation, placement and gameplay
still come from the game files.

## Build locally

Use Python 3.11 or later. Material generation also needs NumPy and Pillow
(Pillow 10.1 or later for gallery lettering). The flashlight-only build uses
the Python standard library. Use a new output directory outside the checkout
and keep WAD-derived output local.

From the repository root on Windows, with your own paths:

~~~powershell
py -m pip install numpy "Pillow>=10.1"
py tools/doom2_showcase/build.py --doom2 "D:\Games\doom2.wad" --dbp50 "D:\Games\DBP50.wad" --gallery --out "D:\Games\ShadeDoomVK Addons"
~~~

Omit the DBP50 argument to generate only the Doom II packs. Omit both WAD
arguments and the gallery flag to build only the flashlight. The material
builder checks input hashes because sprite frames, patches and palettes vary
by release. The versions exercised for this add-on are:

| File | SHA-256 |
| --- | --- |
| Doom II IWAD | 31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab |
| DBP50 PWAD | da722cb243d39e2c3736742df4b69fa9d5c3b4d5e0de53f4a5404dae770e0fd2 |

Each game pack targets 427 wall textures, 150 flats, and 1,167 sprite
lumps covering enemies, pickups and weapons. The DBP50 world pack adapts
changed Doom II composites and the sprite pack uses the DBP50 palette.
DBP50-exclusive world textures, projectile and muzzle effects, and sprite
height maps are outside this material pass. The maps are procedural
interpretations of the pixel art.

## Play

Run the launcher with the runtime executable, installed content and output
directory. Add the desktop shortcut switch to install a Windows shortcut.

~~~powershell
.\tools\doom2_showcase\launch.ps1 -Game DBP50 -Exe "D:\Games\ShadeDoomVK\vkdoom.exe" -Doom2 "D:\Games\doom2.wad" -DBP50 "D:\Games\DBP50.wad" -Packages "D:\Games\ShadeDoomVK Addons" -DesktopShortcut
~~~

Use the DoomII mode for standard Doom II, Gallery for the comparison map, or
Flashlight for the standalone add-on. The launcher uses separate configs and
save directories for each mode. For a manual launch, load the optional DBP50
PWAD first, then the matching world pack, matching sprite pack, and
Local-Flashlight.pk3. Enable hardware rendering, dynamic sprite lights and
enhanced sprite and viewmodel lighting. Keep LevelMesh, shadow maps and ray
queries disabled for the tested configuration.

Press **L** to toggle the flashlight and **O** for options. Power, reach,
horizontal and vertical spread, fore-aft/lateral/vertical offsets, yaw and
pitch are configurable. Enable **Flashlight on weapon and actors** to see
the beam on enemies, pickups and the held weapon. The light flag applies to
both the weapon and world actors. Unequal spreads approximate an asymmetric
beam with overlapping cones. The beam does not cast occlusion shadows.

In the gallery, press **F1** to select a page, or use the signs near the
entrance. Each group uses the same source art in diffuse, normal/specular
and PBR treatments under comparable lights. The HTML index lists every
gallery source and its map location.

## Verification

Run the copyright-free CPU checks with `py -B tools/doom2_showcase/test_showcase.py` after installing the material dependencies.

The local hardware smoke covered the gallery and MAP01 in both games.
A matched test room exercised the original imp, zombieman, green armor,
ammo clip, shotgun pickup and first-person pistol with the flashlight.
Renderer records confirmed the PBR material layers on all six and the
enhanced viewmodel path on the pistol. The flashlight's previous controls
were exercised in both titles. This is a bounded add-on smoke test.
SDVK-008 sprite height and the broader renderer programme are tracked
separately.
