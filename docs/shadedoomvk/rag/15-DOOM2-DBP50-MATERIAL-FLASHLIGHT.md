# Doom II / DBP50 material generation, flashlight and gallery (merged)

**Source authority:** ShadeDoomVK `master`, [PR #190](https://github.com/techrote/ShadeDoomVK/pull/190) merged 13 November 2026 as `ffb679a955989c0eea7503cf15a60642d05990f2`. Original PR head `a7f5e058d4d177d63b630b40f26a52dbd1a19612`.

**Retrieval queries:** Doom2.WAD, PBR texture generation, material map forge, DBP50, GLDEFS, normal roughness metallic AO, sprite materials, flashlight, Doom 2003 look, gallery, show material modes, ZScript lighting.

## Actual delivered surface

**This is a set of optional, locally built add-ons**, not a baked-in replacement for Doom artwork. ShadeDoomVK's merged renderer already understands material layers, but enhanced *Doom II* assets only appear when the user builds and explicitly loads these PK3s. The build reads an owner-supplied WAD and leaves the underlying albedo, sprites, animation, placement and gameplay unchanged.

- `DoomII-NormalPBR.pk3`: normal/metallic/roughness/AO for **427 wall textures + 150 flats** (577 total authored world slots).
- `DoomII-SpritePBR.pk3`: auxiliary material layers for **1,167** standard sprite lumps including enemies, pickups and weapons.
- `DBP50-NormalPBR.pk3` and `DBP50-SpritePBR.pk3`: separately interpreted DBP50 material packs when supported PWAD is supplied. The world generator adapts changed composites; sprite generation uses the mod palette.
- `Local-Flashlight.pk3`: standalone, adjustable ZScript spotlight, applicable without material packs; default **L** toggles and **O** opens options. Power, reach, horizontal/vertical cone spreads, mount offsets, aim offsets and weapon/actor inclusion are adjustable. It emits light but explicitly opts out of shadowmaps (`NOSHADOWMAP`); it is not an occluding flashlight.
- Optional **82-page** comparison gallery (`DoomII-Material-Gallery.pk3`, `SGSHOW`): original diffuse versus normal/specular/PBR interpretation, HTML source index and in-game page selector **F1**.

## Generator, requirements and reproducible command

From repository root, using **Python 3.11+**, NumPy and Pillow (Pillow >=10.1 for gallery text):

```powershell
py -m pip install numpy "Pillow>=10.1"
py tools/doom2_showcase/build.py --doom2 "D:\Games\DOOM2.WAD" --gallery --out "D:\Games\ShadeDoomVK Addons"
```

The output directory **must not exist**; keep outputs outside source and do not redistribute derived WAD images. The generator validates input hashes. Verified Doom II SHA-256: `31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab`; optional DBP50 SHA-256: `da722cb243d39e2c3736742df4b69fa9d5c3b4d5e0de53f4a5404dae770e0fd2`. Another edition/revision or a modded WAD may reject cleanly; *do not bypass validation to force misleading materials*.

For Doom II, the source-provided launch helper is:

```powershell
.\tools\doom2_showcase\launch.ps1 -Game DoomII -Exe "D:\Games\ShadeDoomVK\vkdoom.exe" -Doom2 "D:\Games\DOOM2.WAD" -Packages "D:\Games\ShadeDoomVK Addons"
```

The helper loads world + sprite packs + flashlight, selects Vulkan `vid_rendermode=4`, `gl_viewmodel_lighting=2`, sprite/dynamic lights, probes and custom shaders; it creates separate configs/savedirs. Its previously tested configuration deliberately sets `gl_levelmesh=false`, `gl_light_shadows=0`, `vk_rayquery=false`. Do not call that a feature-complete future nightly visual profile or an SHADOW-001 demonstration.

## Source/feature map

| Code | Meaning |
| --- | --- |
| `tools/doom2_showcase/build.py` | Build orchestration; optional flashlight-only mode, WAD validation and output/manifest production. |
| `material_generator.py`, `material_profiles_v2.py`, `wall_materials.py` | Palette/composite interpretation and differentiated surfaces (metal plates/switch housing vs painted/dielectric controls/wood/stone). |
| `sprite_materials.py` | Sprite auxiliary layers and GLDEFS bindings; original visible sprite pixel data is not replaced. |
| `dbp50_effective.py` | Effective modded art/context and DBP50-specific material adaptation. |
| `flashlight/ZSCRIPT`, `CVARINFO`, `KEYCONF`, `MENUDEF` | Standalone flashlight thinker, controls, settings and UI. |
| `gallery.py`, `navigation.py` | Comparison map/index and page navigation. |
| `launch.ps1` | User-installed add-on loading and quality profile, not a built-in renderer default. |

## Evidential limits and downstream intent

PR #190 reports local material-pack generation and comparison, three copyright-free CPU checks, a bounded Doom II/DBP50 GPU smoke on a GTX 1650 SUPER, and material/viewmodel diagnostic records for six representative items. This is **not** blanket validation of all 1,167 sprite contexts, all WAD versions, every graphics configuration or physical stability.

No DBP50-exclusive world textures, projectile/muzzle art or sprite height maps are generated in this pass. The PBR output is a procedural *interpretation*, not ground-truth physical measurement; metal/dielectric judgment must remain artist-editable. [MAT-001/#205](https://github.com/techrote/ShadeDoomVK/issues/205) proposes the later interactive Material Forge. The [Lost 2003 charter](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) explicitly preserves sharp original albedo and supports non-photoreal theatrical lighting.

**Common failure pattern:** A standalone engine/shadow test may render correctly but show no generated PBR because it packages only `vkdoom.exe` and the synthetic demo, not these owner-generated PK3s. A flashlight is an opt-in add-on, not proof that the engine is missing dynamic lighting.

Further reading: [showcase user guide](../DOOM2-SHOWCASE.md), [material shader contract](04-MATERIAL-SHADER-CONTRACT.md), [viewmodel lighting](../SDVK-011-VIEWMODEL-LIGHTING.md).
