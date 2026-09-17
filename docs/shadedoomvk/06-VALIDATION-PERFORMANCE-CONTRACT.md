# Validation and performance contract

Status: founding evidence contract  
Date: 2026-09-17

## Purpose

ShadeDoomVK changes are unusually vulnerable to "looks good on my test map" validation. This contract defines the minimum evidence expected from renderer issues so visual plausibility does not substitute for correctness.

## Reference-scene classes

SDVK-002 will materialize the corpus, but later issues must preserve these classes:

### Sprite orientation

- front-facing normal map;
- mirrored rotation frame;
- multiple actor rotations;
- billboard/wall/flat sprite variants where supported;
- pitched/rolled actor cases where relevant.

### Lighting

- zero, one and many dynamic lights;
- colored point/spot lights;
- occluded versus visible light;
- sunlight;
- sector/probe boundary;
- portal-group cases;
- emissive/brightmapped material.

### Materials

- albedo-only fallback;
- normal + specular legacy material;
- PBR metallic/roughness/AO;
- height/POM at shallow and extreme test settings;
- nearest-filtered pixel albedo plus independently filtered normal/height maps;
- missing/invalid layer fallback.

### Shadows

- floor contact;
- wall projection;
- sprite mirror/rotation;
- overlapping actors;
- translucent sprite;
- near/far LOD boundaries;
- world occluder between light and actor;
- portal/3D-floor cases where supported.

### Resource stress

- many unique multi-layer materials;
- repeated level load/unload;
- texture precache/eviction paths;
- dynamic/canvas textures;
- descriptor allocation/reuse;
- multiple lightmap/probe atlases.

## Machine-readable evidence

Diagnostics should make relevant state inspectable, including where applicable:

- active renderer/backend and feature tier;
- frame index/tic fraction/render delta;
- material ID and semantic layers present;
- sampler/mip policy per layer;
- bindless slot and generation/lifetime diagnostics;
- dynamic lights considered/selected/rejected;
- probe index/weight and sunlight state;
- shadow caster/mode/LOD;
- LevelMesh/lightmap/probe atlas identifiers;
- CPU and GPU timing;
- draw/light/shadow counts;
- memory/descriptor counters.

Stable IDs used in diagnostics must not imply durable gameplay identity.

## Image evidence

Image/golden comparisons are useful but must be paired with state assertions. Prefer deterministic fixed camera, fixed seed/time and fixed content.

Exact pixel hashes are acceptable only when the rendering path is expected to be bit-stable. Otherwise use a documented tolerance/metric and preserve the expected image plus machine-readable state to diagnose changes.

## Correctness invariants

A change fails even if visually attractive when it:

- selects a light that should be portal/geometry-occluded;
- mirrors tangent-space normals incorrectly;
- samples height/normal maps through destructive albedo filtering rules;
- reuses a bindless slot while a live LevelMesh/material reference still points to the previous resource;
- loses/falsifies fallback state;
- changes gameplay simulation from a render-only feature;
- silently disables inherited map/mod behavior.

## Performance measurement

Performance claims require before/after numbers on the same build type, scene, resolution and settings. Record at least:

- CPU frame time distribution or representative percentiles;
- GPU frame time when available;
- total/frame dynamic lights and selected lights;
- shadow caster count and shadow resolution/work units;
- descriptor/material count;
- relevant memory/VRAM proxy counters;
- draw calls/geometry counts when a change affects them.

Do not use only average FPS; it hides stalls and outliers.

## Quality tiers

SDVK-016 owns final names/defaults, but the architecture should support at least the conceptual distinction:

- **Compatibility** — inherited/cheap behavior, no required ray query, minimal material/shadow extras;
- **Enhanced** — rich materials, probes, efficient dynamic lights, conservative POM/shadows with broad Vulkan support;
- **High** — ray-query world shadows, richer sprite shadowing/POM and higher-quality soft/contact effects.

A tier must correspond to specific algorithm/resource changes and be visible in diagnostics.

## Hardware fallback

Missing optional Vulkan ray-query/acceleration-structure features must not cause unexplained failure. The renderer should select a documented non-RT world-shadow/occlusion path or refuse only the specific unsupported high-end feature.

## Compatibility campaign

SDVK-015 must combine targeted synthetic fixtures with representative real Doom-family content. It should cover classic IWAD gameplay and renderer-stressing constructs such as portals, 3D floors, decals, translations, canvases, translucency, models, voxels, particles, warped textures and high material/light counts.

## Acceptance philosophy

The programme optimizes for **correct, inspectable, scalable approximations**. A simpler effect with explicit limits is preferable to a more spectacular effect whose resource lifetime, portal behavior or material meaning cannot be demonstrated.
