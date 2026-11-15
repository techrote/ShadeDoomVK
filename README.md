# ShadeDoomVK — The Lost 2003 Remaster

> **Doom II as a PC gamer in 2003 might have dreamed it:** unmistakably original pixels, richly interpreted metal and stone, striking local lights, and dramatic, readable shadows. Preserve the game; enhance the illusion.

ShadeDoomVK is an experimental Vulkan-first Doom-engine fork of VKDoom. Its direction is the [owner-approved Lost 2003 Remaster campaign](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) (14 November 2026): a deliberately artificial, artist-directed 2.5D remaster, not a photorealistic rewrite or an excuse to replace classic sprites with models.

Original sprite silhouettes, animation, albedo pixels and Doom-family gameplay are the starting point. Material maps, lighting, optional sprite relief and independently processed shadow proxies add depth **without erasing the artwork**. Doom 3 and early Splinter Cell are references for dramatic hard-edged illumination, not code or asset dependencies.

**Project version:** `0.1.0-dev`. **Build executables:** `vkdoom` and `vktool`. **Founding lineage:** VKDoom `09634479ab5bf9adf691074fffe85a006a398cd0`.

## What works today on master

| Capability | State and where to find it |
| --- | --- |
| **Vulkan dynamic world and actor lighting** | Integrated local lights, sprite lighting, compatibility modes and probe sampling. [Lighting contracts](docs/shadedoomvk/rag/05-LIGHTING-SHADOW-TRUTH-TABLE.md). |
| **Normal/specular/PBR layers** | Engine support is present; **Doom II/DBP50 packs are opt-in and generated from your own WAD**. [Material showcase](docs/shadedoomvk/DOOM2-SHOWCASE.md). |
| **Adjustable flashlight** | `Local-Flashlight.pk3` from merged [PR #190](https://github.com/techrote/ShadeDoomVK/pull/190). Press **L** to toggle, **O** for options after loading it. |
| **Enhanced weapon and HUD lighting** | Legacy/sector/enhanced modes, including applicable normal/PBR materials. `gl_viewmodel_lighting 2` requests enhanced; unsupported routes fall back. [SDVK-011](docs/shadedoomvk/SDVK-011-VIEWMODEL-LIGHTING.md). |
| **Opt-in sprite relief / POM** | Displaced material lookup for eligible height-bearing sprite cards; original alpha preserved. Not a geometry/displacement system, and not automatically supplied by the Doom II material generator. [RAG](docs/shadedoomvk/rag/16-SPRITE-RELIEF-ALBEDO-SAMPLING.md). |
| **Baked/dynamic lightmaps, probe foundations** | Source/facing 3D-floor ownership, guarded static bake command and opt-in GPU interval tooling; full #14 physical acceptance remains open. [RAG](docs/shadedoomvk/rag/17-CONTROLLED-3DFLOOR-LIGHTMAP-OWNERSHIP.md). |
| **Classic LMP input playback** | Explicit `-playclassicinput` for supported v109 single-player inputs under **current** engine rules, not faithful vanilla synchronization. [Guide](docs/shadedoomvk/CLASSIC-INPUT-IMPORT.md). |
| **Renderer diagnostics and CI** | Native oracles, source and capability checks, retained failure evidence. [RAG index](docs/shadedoomvk/rag/README.md). |

**Not yet on master:** the [R-001 pragmatic CI rewrite (#211)](https://github.com/techrote/ShadeDoomVK/pull/211) and the [SHADOW-001 projected floor sprite shadows (#212)](https://github.com/techrote/ShadeDoomVK/pull/212) are **open/unmerged**. Hosted software-Vulkan shadow demonstrations exist, but that does not make projected shadows a master default, a full-featured release or physical-GPU acceptance. The [campaign/planning PR #210](https://github.com/techrote/ShadeDoomVK/pull/210) is also open/unmerged.

## Try the material-and-lighting showcase (Windows)

You need your own **legally acquired** Doom II IWAD, a compatible built ShadeDoomVK executable and **Python 3.11+** with NumPy/Pillow. The generator supports identified WAD revisions; its tested Doom II SHA-256 is `31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab`. Unsupported revisions fail explicitly; do not disable validation to force unreviewed art.

From the repository root in PowerShell, after [building the Windows executable](docs/BUILDING.md):

```powershell
py -m pip install numpy "Pillow>=10.1"
py tools/doom2_showcase/build.py --doom2 "D:\Games\DOOM2.WAD" --gallery --out "D:\Games\ShadeDoomVK Addons"
.\tools\doom2_showcase\launch.ps1 -Game DoomII -Exe ".\build\windows\RelWithDebInfo\vkdoom.exe" -Doom2 "D:\Games\DOOM2.WAD" -Packages "D:\Games\ShadeDoomVK Addons"
```

**Adjust the example paths.** The output folder must not exist before generating. The generator produces `DoomII-NormalPBR.pk3`, `DoomII-SpritePBR.pk3` and `Local-Flashlight.pk3`; `--gallery` also produces the comparison gallery. Material layers cover **427 wall textures, 150 flats and 1,167 sprite lumps** for the supported input. They are locally derived content; neither the WAD nor derived Doom art is committed or distributed here. The generator also supports an optional source-matched DBP50 PWAD for separate material packs.

The included launch helper loads the material packs and flashlight, enables the Vulkan renderer, dynamic/sprite lights, custom shaders and enhanced viewmodel lighting, and uses separate saves/configs. Its older, narrowly qualified showcase preset uses `gl_levelmesh=false`, `gl_light_shadows=0` and `vk_rayquery=false`. **Those are settings of that specific legacy launcher, not a requirement to disable GPU effects in new evaluation builds.** Press **L** to turn on the flashlight and **O** to tune it. For the gallery see [the full instructions](docs/shadedoomvk/DOOM2-SHOWCASE.md).

### Building ShadeDoomVK

The [build guide](docs/BUILDING.md) documents Visual Studio 2022/MSVC on Windows, Linux and macOS dependencies, binaries, provenance checks and CPU test commands. Windows x64 default build:

```powershell
cmake -S . -B build/windows -G "Visual Studio 17 2022" -A x64 -DPK3_QUIET_ZIPDIR=ON
cmake --build build/windows --config RelWithDebInfo --parallel 3
python tools/check.py --output build/checks-windows
python tools/check_build_identity.py --build-dir build/windows --config RelWithDebInfo
.\build\windows\RelWithDebInfo\vkdoom.exe --version
```

The engine cannot include Doom II copyrighted IWAD data. Shader/material compatibility varies by game revision, add-on and scene; consult the capability/fallback notes rather than treating an absent visual effect as proof that its code is missing.

## Visual quality and evaluation-build contract

The target is a **playable nightly-style integrated developer build**: use the source-matched executable, load all supported user-local material packages, and **enable every implemented mutually compatible visual enhancement by default** with deliberately tuned parameters. Provide normal player movement, audio and HUD, explicit presets and per-feature toggles, a sample/gallery, a manifest of which features really loaded, and straightforward instructions. Automated capture fixtures must remain separate.

**This is the owner's forward-looking evaluation-build requirement, not a claim that today's repository CI or downloadable packages already satisfy it.** An unavailable feature, incompatible map/material, unmerged PR or hazardous workload must be declared rather than silently enabled, disabled or misrepresented. Raster-first projected shadows are the primary 2003 aesthetic target; hardware ray tracing is not a prerequisite.

**Two normal test environments (owner clarification, 15 November 2026):** assistants and GitHub runners can continue extensive **CPU-only / lavapipe/llvmpipe software-Vulkan development and CI**. The owner uses **real GPU hardware** on their Windows machine for playable graphics evaluation and tuning. Software Vulkan is not a physical-GPU benchmark, and local GPU playtests should never be crippled by an inherited blanket STOP or print-only launcher. A known reproducible driver fault warrants scenario-specific engineering care, not a ban on normal play or a requirement for special authorisation. See [current GPU workflow](docs/shadedoomvk/LOCAL-GPU-WORKFLOW-20261115.md), [campaign charter](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) and [recent-merge reconciliation](docs/shadedoomvk/rag/21-NOV2026-CLOSED-PR-RECONCILIATION.md).

## Documentation map

- [RAG architecture and feature index](docs/shadedoomvk/rag/README.md) — current source paths, feature contracts, fallbacks, invariants and provenance.
- [11–15 November merged-PR audit](docs/shadedoomvk/rag/21-NOV2026-CLOSED-PR-RECONCILIATION.md) — nine closure decisions and what genuinely shipped.
- [Doom II / DBP50 showcase guide](docs/shadedoomvk/DOOM2-SHOWCASE.md) — verified content hashes, generator, flashlight settings and gallery.
- [Campaign charter](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md) — art direction and future issue slate; still on planning branch.
- [Execution ledger](docs/shadedoomvk/10-EXECUTION-LEDGER.md) and [AGENTS.md](AGENTS.md) — source/approval gates, ongoing programme and agent rules.

## Licence and lineage

GPL-3.0 with inherited third-party notices and donor provenance in [the repository register](docs/shadedoomvk/04-DONOR-PROVENANCE.md). ShadeDoomVK is not affiliated with id Software; game content and third-party art require their own licenses. Do not copy proprietary game material into the repository or CI artifacts.
