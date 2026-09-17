# ShadeDoomVK PF equivalence protocol

Status: PF-001 evidence contract  
Date: 2026-09-17

## Purpose

Pre-foundation refactors and performance work are required to preserve accepted renderer meaning unless an issue explicitly owns a correctness fix. This protocol defines how an implementation demonstrates that preservation without reducing validation to "the screenshot looked similar."

It complements `06-VALIDATION-PERFORMANCE-CONTRACT.md`. PF-001 intentionally establishes a small reproducible floor; SDVK-002 later expands it into a full executable reference-scene/benchmark system.

## Evidence layers

### Layer A — deterministic source/contract oracle

`tools/pf_oracle/run.py` verifies cheap architectural invariants and known pre-fix source reproducers against `tools/pf_oracle/baseline.json`.

This layer runs in ordinary GitHub CI and catches accidental removal or silent mutation of:

- inherited material layer/sampler capability;
- bindless allocation/reuse seams;
- portal-relative actor-lighting seams;
- render-context/portal-mirror seams;
- pinned known-defect markers assigned to later PF issues.

It is **not** proof of runtime renderer correctness. Its job is to make important source-contract changes deliberate and reviewable.

### Layer B — machine-readable runtime state

Executable fixtures should emit JSON conforming to `tools/pf_oracle/runtime_evidence.schema.json` as their diagnostics become available.

For a relevant change, record as applicable:

- exact build commit/backend/device/driver;
- main/portal/mirror/camera/probe render context identity;
- semantic material layers and sampler policy;
- renderer resource slots/generations/high-water counters;
- lights considered/selected/rejected and candidate source;
- probe selection/fallback;
- shadow mode/candidate/selected/LOD state;
- effect-specific CPU/GPU timing/counters;
- image evidence metadata.

A visual match with different selected lights, probe identity, sampler semantics or stale resource generation is not equivalent.

### Layer C — rendered image evidence

Use fixed camera/content/time/settings and pair every image comparison with Layer-B state.

Use exact SHA-256 only when the path is expected to be bit-stable. Otherwise record a documented comparison metric/tolerance. Do not widen tolerance until an unexplained regression disappears.

Hosted GitHub CI is not assumed to provide a trustworthy Doom IWAD + presentation Vulkan GPU environment. PF-001 therefore does **not** claim to create GPU reference images in CI. When a runnable renderer fixture environment is available, its captures plug into the same evidence schema and protocol.

## Reproduction identity

Before comparing two renderer runs, keep constant unless the issue explicitly studies the changed variable:

- repository commit/build configuration except the candidate change;
- map/fixture/content revision;
- camera/view and portal entry state;
- resolution, render scale and quality settings;
- simulation tic/fraction or fixed visual time;
- deterministic seed where randomness exists;
- backend/device/driver for strict performance or pixel comparisons;
- relevant capability/fallback state.

If one of these differs, record it and do not call the result a strict before/after equivalence comparison.

## PF refactor acceptance

For PF structural refactors, accepted equivalence means:

1. source/contract oracle passes;
2. applicable runtime-state fields are equal, or every deliberate structural-ID difference is mapped to the same semantic resource;
3. rendered evidence is equal within its declared metric/tolerance;
4. gameplay/simulation state is unchanged;
5. resource stress exposes no stale/mismatched identity.

A refactor may change internal addresses, allocation order or renderer-local IDs. Such a change is acceptable only when semantic identity/generation diagnostics prove live references still resolve correctly.

## PF correctness-fix transition

A later PF bugfix begins with the known failing fixture/reproducer. When fixed:

1. preserve the regression fixture;
2. change its expected runtime/source state deliberately;
3. update the owning source probe if the pinned defect marker disappears;
4. regenerate/review `baseline.json` in the same PR;
5. document the precise before→after semantic change;
6. prove unrelated fixtures remain equivalent.

The oracle deliberately treats a known defect disappearing without baseline reconciliation as a CI failure. This prevents accidental deletion of the evidence from masquerading as a fix.

## PF performance acceptance

Performance claims require the equivalence rules above plus before/after measurements on the same workload/configuration. Use distributions/percentiles and subsystem counters where available; average FPS alone is insufficient.

PF performance work may not earn a speedup by silently changing:

- eligible/selected lights;
- filter/mip/color-space policy;
- texture/shadow/render resolution;
- numeric precision where output materially changes;
- visible LOD policy;
- enabled features or fallback mode.

## Checked-in PF-001 baseline

`tools/pf_oracle/baseline.json` is the first deterministic PF state/source capture. It is intentionally compact and contains no fabricated GPU measurements. The evidence interpretation is recorded in `PF-001-BASELINE-EVIDENCE.md`.
