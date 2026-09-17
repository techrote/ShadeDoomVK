# SDVK-006 — Render-frame time and opt-in visual interpolation substrate

## Objective
Provide a high-frame-rate renderer visual clock and compatibility-safe opt-in visual interpolation without changing Doom gameplay/tic determinism, using PF-010's explicit render-context model.

## Scope / required work
- Inspect current timing/interpolation after PF; adapt MAD render-delta/interpolation concepts only where still useful.
- Define rendered-frame delta/time semantics for main and non-main render contexts; reset/clamp across load/wipe/pause/camera discontinuities.
- Expose renderer/script visual-time access with explicit non-gameplay semantics.
- Add opt-in alpha/scale interpolation where compatible and useful; preserve legacy default behavior where required.
- Ensure camera textures/probe renders/portal recursion do not corrupt main-view timing/history state.
- Add deterministic endpoint/discontinuity tests and diagnostics.

## Non-goals
No gameplay timestep change; no TAA/motion vectors/temporal history; no generalized animation rewrite.

## Dependencies
SDVK-001, SDVK-002.

## Concurrency guidance
May overlap SDVK-004/005/009 on separate files. Later animated material/temporal work consumes this contract.

## Required context
Read `AGENTS.md`, PF-010 and PF freeze evidence, execution/portal/HDR RAG, MAD donor commits in provenance register, SDVK-002 oracle and canonical body.

## Autonomous implementation prompt
Complete SDVK-006 autonomously. Define visual-time semantics first, adapt only relevant donor concepts, preserve tic/gameplay determinism, test discontinuities/non-main views, branch→PR→checks→merge→verify `master`→donor/RAG/ledger→close.

## Acceptance criteria
Visual delta/time well-defined/diagnosable; load/wipe/pause/cut cannot cause uncontrolled jumps; opt-in alpha/scale interpolation smooth and compatible; non-main renders do not contaminate main visual time; gameplay/demos remain frame-rate independent; PR merged/verified.

## Verification
Fixed simulation with varying render rates, pause/wipe/load/camera cut, portal/camera/probe render contexts, interpolation endpoints, demo/game-state equivalence.

## Expected artifacts
Visual-time API/diagnostics, interpolation implementation/tests, timing docs/RAG/provenance/ledger updates.

## Blocking / stopping conditions
Stop if an interpolation path modifies authoritative simulation state or if a single clock cannot represent a non-main context safely; use explicit context-local/fallback semantics instead.
