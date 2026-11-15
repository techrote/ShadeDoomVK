# SHADOW-002 — light-relative sprite silhouette shadows

**Status:** implementation and native qualification candidate for [PR #215](https://github.com/techrote/ShadeDoomVK/pull/215). Default OFF; owner visual acceptance and merge approval remain outstanding. Parent goal: [#204](https://github.com/techrote/ShadeDoomVK/issues/204).

## Renderer and material baseline

The branch starts at `master@f787f7199fc7560588bb9440b3dd0aa663cb53de`, containing the accepted [PR #195](https://github.com/techrote/ShadeDoomVK/pull/195) renderer and the original [PR #190](https://github.com/techrote/ShadeDoomVK/pull/190) PBR/flashlight work. The material-generation algorithms in `tools/doom2_showcase` remain unchanged. The rejected floor-decal implementation in PR #212 has not been reused.

A local dynamic light is the emitter, a light-facing source-alpha sprite is the caster, and an actual shaded world fragment is the receiver. Intersection with opaque source alpha attenuates **only that emitter's direct contribution**, in the normal, specular and PBR paths. Sector ambient, probe/IBL, other emitters and the existing world-shadow calculation keep their own contributions. Walls, floors and steps already rendered by the immediate path can receive the shadow; no receiver decal or extra floor mesh is generated. No ray-query capability is required for the actor silhouette test.

## Source appearance and alignment

Each eligible actor uses its current animation frame and the rotation selected from the **light**, through the ordinary `GetSpriteAngle` / `GetSpriteFrame` rules. Camera position and orientation do not choose the caster. Source alpha is filtered separately into a **64×128 binary mask**; the visible sprite's albedo, material maps, UVs and normal-map basis are unchanged.

The caster uses unexpanded source-image coordinates and adjusted source offsets, source/actor scale, effective frame/X/Y flipping, authored sprite/world offsets, floor clipping and bob. The horizontal alpha direction follows `HWSprite`'s existing UV convention. The main display interpolation fraction samples actor position, angle and scale consistently. Identity-based receiver exclusion prevents a camera-facing actor sprite from intersecting its own differently oriented light-facing shadow card; other actors can still shadow it in per-pixel sprite-lighting mode.

The proxy is a flat light-facing alpha card, not a volume or a reconstructed three-dimensional monster. Its light-facing rotation changes at the source sprite's authored angular/frame boundaries. Coverage is binary per emitter, with filtered source-alpha edges; there is no light-size penumbra model.

## Bounded storage and lifetime

The core `FDynLightInfo` retains the original **80-byte** CPU/GLSL stride. Its three previously unused padding words carry a side-buffer start, count and receiver-specific enable mask. Shadow alpha is not copied into every surface's light record.

The dedicated storage buffer holds at most **4,096 caster records per render frame**, each **1,072 bytes**, for **4,390,912 bytes** total. Each light selects at most four nearest eligible casters. Worker threads atomically reserve disjoint ranges and finish before draw submission. Exhaustion omits that light's new actor occlusion, retaining its existing illumination/world shadows, and increments an observable overflow counter. No range wraps or overwrites an earlier draw's data.

A process-unique render-buffer epoch fences CPU light-cache entries, including after device recreation. The epoch closes at `EndFrame`, so the early LevelMesh update cannot write into the previous submitted frame. A source-alpha cache is bounded to 64 entries per worker and keys the existing LevelMesh resource owner/generation, immutable image identity, dimensions and alpha cutoff. It retains CPU mask values rather than GPU descriptors or owning actor references.

The GLSL checks the complete side-buffer range before any access. Both immediate and LevelMesh descriptor layouts bind the same read-only storage slot; the dormant tiled record layout retains the 80-byte core ABI. `resources.actor_shadows` reports enable state, dimensions, capacity, uploaded/overflow caster counts, frame epoch and bytes. These are CPU-authored submission diagnostics; the native image gate independently checks shader-visible effects.

## Supported path and explicit fallbacks

The qualified target is the **immediate Vulkan renderer** (`gl_levelmesh false`) with opaque upright, shootable actor sprites. The owner launcher requests per-pixel sprite lighting. Enabling actor shadows selects specialized per-light shaders even if the ordinary generalized pipeline fallback is enabled, so a temporary fallback cannot silently remove the effect.

Unsupported sources omit their new caster and retain their ordinary rendering: models/voxels, direct `picnum` overrides, wall/flat/rolled/isometric or angular-visibility sprites, invisible actors, partial-opacity/fuzz/additive styles, custom/warped/canvas textures, oversized sources/scales and degenerate geometry. Non-shootable decorations/corpses are outside this first supported caster set. Source actor, light and receiver must share the same portal group; transported lights do not acquire an unqualified straight-line shadow across linked groups. This preserves their existing lighting rather than guessing a portal ray path.

The early LevelMesh/tiled dynamic-light path, raytraced world renderer and camera-dependent sprite clipping effects are not qualified actor-shadow receivers. Legacy vertex-lit sprites retain their inherited receiving-light behavior; they can still cast onto supported world fragments. Same-group mirror views use world-anchored caster data, but broad portal/camera-texture/probe-scene coverage remains an explicit acceptance limit.

## Windows playtest

Download the `shadow002-windows-source-matched` artifact from the successful **SHADOW-002 Windows research build** for the PR's current commit, extract it, and run **RUN-WINDOWS.cmd**. Choose your own Doom-family IWAD. The package contains the executable, all built engine PK3 resources, original flashlight, source manifest and a standalone material generator. Python installation is not required.

The bundled generator runs the original PR #190 algorithms locally against the selected structurally validated IWAD. Generated materials are cached under that WAD's SHA-256; the WAD and generated copyrighted art are not uploaded. The build qualifies the frozen generator against the original Python entry point on synthetic `MAP01` and `E1M1` IWAD families. This is format-family coverage, not a promise that every custom or damaged WAD supplies all required material lumps.

The launcher fails visibly if faithful PBR generation is unavailable. `-SkipMaterialBuild` and `-LegacyLighting` are explicit diagnostic fallbacks. A normal launch starts the game menu so both Doom II and episode-based IWADs work; optional `-Map MAP01` or `-Map E1M1` starts a chosen map directly. The local configuration is isolated from the owner's normal engine settings.

From PowerShell in the extracted package:

```powershell
.\Play-Windows.ps1 -Iwad 'C:\Games\Doom\DOOM2.WAD' -Map MAP01
```

Compare the same scene with `gl_actor_light_shadows false` and `gl_actor_light_shadows true` in the console. Toggle the original flashlight and move around a monster. Check that the silhouette follows the emitting light, that walking the camera around a stationary scene does not rotate the cast shadow, and that PBR/normal response, controls, weapons and sound retain the accepted baseline behavior. The feature remains default OFF in the engine until owner acceptance.

## Reproducible qualification

CPU controls execute the **production C++ alpha-mask builder**, including transparent holes, asymmetric source orientation, filtering, bounds and bit packing. Independent ray tests check real floor/wall receivers, endpoints, alpha holes and emitter-specific attenuation. ABI controls cover the unchanged core layout, side-buffer shape and shader integration. Package tests validate native resource completeness and IWAD structural failures.

`tools/dynamic_shadows/native_capture.py` builds original synthetic assets and captures actual software-Vulkan images. Its fixed receiver patches test normal/specular/PBR direct-light removal, unrelated blue illumination and green ambient retention, floor and wall holes, asymmetry/mirroring, camera changes, a solid-mask positive, invisible-caster OFF parity and visible-sprite self-shadow controls. Source identity, CPU Vulkan device, camera/map/configuration and nonzero uploaded-caster diagnostics are required. A dark-pixel count alone is not accepted.

Example on a software-Vulkan Linux host with Xvfb and Freedoom:

```sh
xvfb-run -a -s '-screen 0 640x480x24 -nolisten tcp' \
  python3 -m tools.dynamic_shadows.native_capture \
  --exe build/vkdoom --iwad /usr/share/games/doom/freedoom2.wad \
  --iwad-license /usr/share/doc/freedoom/copyright \
  --out build/shadow002-native --expected-commit "$(git rev-parse HEAD)"
```

The ordinary compiler matrix and existing software-Vulkan corpus remain required. The focused capture gate runs within the existing software-Vulkan job and retains screenshots, state and machine-readable verdicts. The separate Windows workflow verifies the submitted head and publishes a complete owner-playable package.

## Acceptance boundary

Hosted/native software evidence can qualify implementation correctness within these fixtures. It cannot substitute for the owner's Windows GPU visual judgement or establish representative GPU cost. Do not merge this PR or close #204 until that acceptance is given. Record exact tested commit/workflow/artifact identities in the PR; keep historical failed captures intact when diagnosing a failed gate.
