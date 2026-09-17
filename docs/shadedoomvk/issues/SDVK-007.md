# SDVK-007 — Explicit sprite-space tangent basis and normal-map conformance

## Purpose
Make sprite normal/specular/PBR orientation correct across Doom's mirroring, rotations and billboard modes before adding relief mapping.

## Autonomous execution prompt
Complete SDVK-007 after SDVK-005. Read all founding docs and use SDVK-002 reference scenes as the oracle. Inspect current derivative/TBN implementation before replacing anything. State the sprite tangent/bitangent/forward and handedness contract first. Dedicated branch → PR → required checks → merge → verify `master`.

## Required work
- Define explicit sprite-local tangent frame semantics.
- Correct mirrored frame handedness; mirroring UVs must not silently invert lighting incorrectly.
- Cover actor rotations, 8/16-direction frames where applicable, billboard modes, wall/flat sprites, roll/pitch paths that use sprite materials.
- Keep geometry surfaces/models on their appropriate existing tangent paths.
- Add diagnostic visualization or state useful for tangent/normal debugging.

## Acceptance criteria
- Reference normal-map lobes rotate/mirror correctly under all declared sprite cases.
- Specular highlight movement agrees with the same basis.
- Legacy un-normal-mapped sprites are unchanged within declared tolerance.
- Positive and deliberately mirrored-negative fixtures are automated.
- PR merged and verified on `master`.

## Dependencies
SDVK-005.