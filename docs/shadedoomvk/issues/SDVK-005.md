# SDVK-005 — Semantic material layers and per-layer sampling

## Purpose
Create a first-class material contract suitable for crisp pixel albedo plus correctly filtered normal/height/PBR data.

## Autonomous execution prompt
Complete SDVK-005 after SDVK-004. Read all founding docs and inspect `Waffle-Iron-Studios/GriddleVK@97eaa46b69a19966e1a802b15081bcdf56eff718`. Reimplement/generalize the concept rather than preserving a narrow historical enum by inertia. Dedicated branch → PR → CI repair → merge after checks → verify `master`.

## Required work
- Define semantic channels: albedo, normal, height, roughness, metallic, AO, emissive/brightmap and custom extension channels.
- Define correct color-space treatment and default sampler/mip/wrap policy per semantic.
- Allow material-layer-specific sampler overrides while retaining backward-compatible defaults.
- Make `height` a real material semantic with graceful absence/fallback; do not yet implement the final POM algorithm.
- Ensure precache/descriptor/material invalidation handles all layers.
- Add fixtures where pixel-art albedo remains nearest/crisp while normal/height use appropriate filtering.

## Acceptance criteria
- Independent per-layer filtering is observable and tested.
- Existing legacy/PBR materials render through compatible paths.
- Missing/invalid optional layers fail safely.
- Height semantic exists without altering gameplay geometry.
- No new descriptor lifetime regression.
- PR merged and verified on `master`.

## Dependencies
SDVK-004.