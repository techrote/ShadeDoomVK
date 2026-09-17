# SDVK-004 — Bindless descriptor capacity, reuse and stale-reference hardening

## Purpose
Make rich multi-layer materials safe before they multiply Vulkan descriptor pressure.

## Autonomous execution prompt
Complete SDVK-004 after SDVK-002 and SDVK-003. Read all founding docs and donor register. Inspect exact donor commits `jalovisko/VkDoom@033a3c5cb35c82708e4eeb3619373c33ddc40b75` and `MrRaveYard/MAD-VKDoom@e2de04134c4654d38dd4b5452a0306036a5e0911`; treat the latter's stale LevelMesh-index warning as a required negative fixture, not a solution to copy. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Add device-limit-aware configurable descriptor capacity with accurate diagnostics.
- Instrument current allocation/high-water/free behavior.
- Design and implement safe slot release/reuse if required by measured lifetime behavior.
- Prevent stale LevelMesh/material references when slots/resources are recycled; use generation/lifetime validation or an equally demonstrable mechanism.
- Stress repeated loads/unloads, many unique PBR materials, canvases and lightmap/probe resources.
- Fail clearly and safely when physical/device limits are reached.

## Acceptance criteria
- Capacity respects Vulkan device limits.
- Descriptor exhaustion test no longer requires an unsafe global flush.
- Reuse cannot make a live reference resolve to an unrelated texture/material in tested paths.
- Resource diagnostics expose current/high-water usage and failures.
- Stress fixture runs in CI at tractable scale.
- PR merged and verified on `master`.

## Dependencies
SDVK-002, SDVK-003.