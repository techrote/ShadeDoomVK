# PF-009 sprite render-surface and orientation contract

Status: accepted on `master` via PR #53; implementation merge `b58f03decfedca12df039c68a5e36d709120bba1`  
Scope: renderer-side extraction only

## Purpose

`HWSprite` historically selected Doom sprite rotation, mirror state, billboard policy, final quad geometry, UV orientation, portal-relative presentation and material state in several separate blocks. Later normal-map, projected-shadow and POM work must not independently reconstruct those decisions.

PF-009 therefore publishes one renderer-side `HWSpriteRenderSurfaceState` snapshot and one pure billboard-policy resolver. The snapshot is descriptive: existing `HWSprite` geometry, texture selection, UVs and render state remain authoritative for the current draw.

## Canonical state

`HWSprite::RenderSurface` records the already-selected presentation information needed by later renderer work:

- source kind: actor, particle or visual thinker;
- presentation class: Y-axis face card, XY face card, camera-facing card, wall card, flat card or model;
- the independent inherited `xyBillboard` and `facesCamera` decisions;
- selected actor sprite/frame identity and resolved `FGameTexture*`;
- Doom rotation-frame mirror state separately from effective X/Y UV mirroring;
- final render position, card endpoints, offsets and UV endpoints;
- renderer angles and current view position/orientation;
- translation, render style and effective alpha at snapshot time;
- source and render portal groups, portal traversal mode and current recursive portal/mirror handedness.

The snapshot is refreshed immediately before inherited vertex construction. This is intentional: billboard CVARs are sampled at the same stage as before PF-009, so extraction does not introduce a frame-delayed preference change. Actor/particle queue paths also publish the state for diagnostics and later consumers.

## Billboard policy

`ResolveHWSpriteOrientationPolicy()` centralizes the boolean checks formerly duplicated in `HWSprite::CalculateVertices`.

It preserves these inherited rules exactly:

- actor `RF_FORCEYBILLBOARD` suppresses the global XY preference;
- actor `RF_FORCEXYBILLBOARD` requests XY presentation when FORCEY is absent;
- particle `SPF_NO_XY_BILLBOARD` suppresses only the particle-specific XY route; the inherited global XY preference remains a separate route;
- `hw_force_cambbpref` makes the global face-camera preference authoritative, exactly as before;
- otherwise actor/particle face-camera opt-ins and vetoes retain their historical behavior;
- wall and flat cards retain explicit semantic presentation classes without changing their existing transforms;
- models are classified explicitly so later sprite-surface consumers do not accidentally treat model draws as sprite cards.

The policy returns `xyBillboard` and `facesCamera` independently because the inherited transform can observe both simultaneously.

## Mirror and portal identity

Three concepts are intentionally separate:

1. `frameMirrored` records the mirror bit returned by Doom sprite-frame selection.
2. `uvMirrorX` / `uvMirrorY` record the effective texture-axis flips after inherited sprite flags are applied.
3. `portalMirrored` records `FPortalSceneState::isMirrored()` for the recursive render context.

PF-009 does **not** combine those values into a tangent sign. SDVK-007 owns the future sprite tangent-space definition. Keeping them separate prevents PF-009 from silently choosing TBN semantics while still making all required inputs explicit.

Portal-group identity is also preserved separately from mirror parity. `sourcePortalGroup` describes the actor/particle source sector, `renderPortalGroup` describes the sector supplied to the current render path, and `throughPortalMode` preserves the inherited route discriminator used by sprite processing.

## Geometry and material equivalence

PF-009 does not replace frame selection, sprite clipping, anamorphosis, floorclip/bob behavior, isometric adjustment, wall/flat transforms, UV assignment, draw ordering, material binding, palette/translation handling or alpha/render-style logic.

`UpdateRenderSurfaceState()` copies the final `HWSprite` position/quad/UV/material fields into the snapshot; it does not write those fields back or issue draw/material commands. `CalculateVertices()` consumes only the centralized orientation policy in place of re-running those billboard checks.

Direct-picnum behavior is deliberately left as inherited. PF-009 does not opportunistically repair or reinterpret that path.

## Non-goals

PF-009 introduces no:

- tangent/TBN algorithm;
- height-map or parallax/POM behavior;
- new sprite-shadow algorithm;
- clipping, sky or portal bug fix;
- gameplay orientation/state mutation;
- material retuning or shader-output change;
- donor/upstream import or provenance change.

## Verification

`tools/pf_oracle/tests/test_sprite_surface_contract.py` verifies source integration and that the extraction remains observational. `sprite_surface_policy_fixture.cpp` adversarially covers FORCEY/FORCEXY, global XY, actor/particle face-camera preference and vetoes, simultaneous XY+camera-facing policy, wall/flat classification, particle NO_XY/NOFACECAMERA boundaries and model classification.

Exact implementation head `8f78d5a10fe502d144b09b51f786b97e6e6bb54e` passed Continuous Integration run 65, including the deterministic PF renderer oracle and inherited Windows/macOS/Linux build matrix. PR #53 then merged as `b58f03decfedca12df039c68a5e36d709120bba1`; post-merge Continuous Integration run 66 also passed on that exact `master` commit. The contract is therefore accepted rather than provisional.
