# SDVK-015 — Doom-family compatibility and renderer regression campaign

## Purpose
Demonstrate that the integrated enhanced renderer does not silently break the content language it is meant to improve.

## Autonomous execution prompt
Complete SDVK-015 only after SDVK-008, SDVK-011, SDVK-013 and SDVK-014 are accepted. Read all founding docs and all predecessor evidence. Build on SDVK-002 harness rather than inventing an unrelated test framework. Dedicated branch → PR → required checks → merge → verify `master`.

## Required coverage
Use targeted synthetic fixtures plus representative legally redistributable/testable content patterns for:
- classic IWAD-style maps/sprites and lighting modes;
- sprite rotations/translations/mirroring;
- portals and portal groups;
- 3D floors/render hacks;
- decals;
- canvas/dynamic/translucent textures;
- warped materials;
- models, voxels and particles;
- brightmaps/emissive materials;
- many dynamic lights and many unique multi-layer materials;
- save/load and repeated level transitions where renderer resources are rebuilt.

## Required output
Classify every discovered regression as fixed, explicit enhanced-mode incompatibility with fallback, pre-existing baseline behavior, or unresolved blocker. Preserve minimized reproducer fixtures.

## Acceptance criteria
- Declared compatibility matrix is evidence-backed.
- No known silent corruption/crash/resource-identity bug remains in a declared supported default path.
- Enhanced features fall back explicitly where unsupported.
- Automated regression subset runs in CI.
- PR merged and verified on `master`.

## Dependencies
SDVK-008, SDVK-011, SDVK-013, SDVK-014.