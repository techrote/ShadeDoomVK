# PF-010 render-context contract

Status: implementation contract for PF-010 / #27  
Scope: descriptive render-view/pass identity only

## Purpose

ShadeDoomVK re-enters the hardware scene renderer for materially different consumers: the visible main view, camera textures, light-probe cubemap faces, save-picture rendering, and recursive portal/mirror scenes. PF-010 gives those passes an explicit renderer-side identity so later caches, probe work and temporal systems do not have to infer context from globals or from incidental call shape.

The context is observational. It does not select matrices, portal transforms, draw modes, postprocess stages, quality settings or gameplay state.

## Context identity

`src/rendering/hwrenderer/scene/hw_rendercontext.h` defines `HWRenderContext` and `HWRenderContextType`.

Every top-level `RenderViewpoint` invocation begins a non-zero `epoch`. Each scene pass inside that invocation receives a non-zero local `identity`:

- each stereo eye is a distinct root identity within the top-level epoch;
- every recursively traversed scene portal receives another identity in the same epoch;
- a recursive context records `parentIdentity` and increments `recursionDepth`;
- persistent consumers must treat `(epoch, identity)` as the identity pair. The local `identity` may be reused after an epoch transition.

This deliberately avoids coupling identity to frame/tic counters, actor addresses, Vulkan object handles or gameplay state.

## Root classifications

The existing `RenderViewpoint` arguments remain behaviorally authoritative. PF-010 classifies them without changing their meaning:

- `MainView`: `mainview && toscreen`, eligible for the existing main postprocess route and for future persistent main-view history;
- `SavePicture`: `mainview && !toscreen`, preserves the inherited postprocess route but is not eligible for persistent main history;
- `LightProbe`: `side >= 0`, records the cubemap face in `probeFace` and is not history/postprocess eligible;
- `CameraTexture`: the remaining offscreen scene-view route, not history/postprocess eligible;
- `Portal`: recursive scene rendering after portal setup has established its active transform/mirror state.

A portal also preserves `rootType`, `probeFace` and `eyeIndex`, so a portal reached while rendering a probe or camera texture cannot be mistaken for a portal belonging to the visible main view.

## Portal parent and handedness contract

The currently active context is stored alongside the existing `FPortalSceneState` in the hardware draw context. `HWScenePortalBase::DrawContents` creates a child context only after the inherited portal `Setup()` succeeds and before recursive `DrawScene()` begins.

At that point PF-010 snapshots:

- parent identity;
- recursion depth;
- line-mirror parity from `MirrorFlag`;
- plane-mirror parity from `PlaneMirrorFlag`;
- effective mirrored handedness as the inherited XOR of those two parity bits.

The parent context is restored after the inherited portal `Shutdown()` completes. PF-010 does not modify `Setup()`, `Shutdown()`, `SetupView()`, clipping, portal-group displacement or matrix order.

Non-scene portal draw helpers such as horizon/sky surface rendering do not create a recursive scene identity because they do not re-enter `DrawScene()` as another viewpoint.

## Postprocess and future-history seam

`postprocessEligible` and `historyEligible` are descriptive flags, not new control flow.

PF-010 intentionally preserves the inherited `if (mainview)` / `if (toscreen)` decisions in `RenderViewpoint`. In particular, save-picture rendering remains on the historical `mainview` postprocess path while being excluded from future persistent main-view history.

No history image, previous matrix, motion vector, TAA, temporal filter, reset heuristic or camera-cut policy is introduced here. A future temporal owner must key any persistent history by the explicit render context and define its own epoch-validity rules instead of assuming one global camera.

## Output-equivalence boundary

PF-010 does not change:

- `R_SetupFrame` or per-eye projection/view shifts;
- `SetupView` matrix construction;
- portal transform/mirror setup or teardown;
- camera-texture or light-probe entry arguments;
- probe interpolation suppression;
- `IsEnvironmentMapRendering` semantics;
- main scene target/GBUFFER selection;
- `EndDrawScene` or `PostProcessScene` eligibility;
- shader/material/palette/translation behavior;
- sprite presentation, gameplay/tic state, audio or donor/source provenance.

The deterministic PF renderer oracle remains the output/state-equivalence baseline.

## Verification

`tools/pf_oracle/tests/render_context_fixture.cpp` exercises:

- main/camera/save/probe classification boundaries;
- all six probe faces;
- unique identities within one epoch;
- line mirror, plane mirror and double-mirror XOR parity;
- nested portal parent/depth propagation;
- a portal rooted in a probe face;
- epoch transition and safe local-identity reuse.

`test_render_context_contract.py` additionally pins the production routing order: top-level context assignment, existing camera/probe/main/save calls, unchanged view setup/postprocess gates, and portal child construction only after successful portal setup.
