# SDVK-014 controlled flat source/facing ownership

## Bounded software follow-on

This increment starts from accepted special-surface master
`d40475519170606e83dec20dc822ceb5a54312ee` (PR #162). It repairs standard
controlled floor/ceiling lightmapping for `FF_BOTHPLANES`, including normal and
inverted source selection. It does not complete parent #14. Review, a full build
and normal exact-head CI remain required before integration. No physical renderer
execution or physical cost/stability acceptance is supplied here.

## Reproduced production constraint

`HWFlat::ProcessSector` can emit both control-model planes with the same facing.
The old `(type, subsector, control sector)` key therefore selected one tile for
two different heights. The accepted #161 guard correctly stopped before merging
the second plane's bounds or use count. Removing that guard would corrupt the
bake; enlarging the key alone would still leave an incorrect immediate renderer.

The immediate path stored one tile per model axis/rover and one vertex stream per
`F3DFloor::planeref`. Opposite facings of the same geometric plane require
different bakes. A shared stream can carry only one set of lightmap UVs/page.
The retained pre-fix producer fails the compiled page/UV ownership check even
when supplied distinct current tiles.

## Production change

- `LightmapTileBinding::ControlPlane` adds the selected model source axis to the
  runtime key of controlled flats. Surface type remains the emitted facing.
  Ordinary flat and wall keys retain the no-control-plane sentinel. Unequal
  geometric planes under the same complete key still stop before mutation.
- Each subsector source-axis table keeps sector slot 0, then slots
  `1 + 2 * rover + facing`, where facing 0 is upward/floor and 1 downward/ceiling.
  Allocation, publication, visible-tile enumeration and immediate vertex origins
  use that same layout.
- `planeref::vindex[2]` selects a render-only index stream for each emitted
  facing. Lightmapped opposite faces have separate vertices; unlightmapped
  opposite faces preserve the shared geometry stream. Normal/inverted selection
  follows the existing `ProcessSector` flag predicates. Source-plane vertex
  ranges include every new stream, so existing height updates and UV uploads
  continue to reach them.
- Controlled bake receivers must match source axis and the actual oriented
  plane. Ordinary height-group seam/padding contributors retain their existing
  differing-plane coverage.

No descriptor range, probe identity, atlas allocator/incarnation, draw fence,
tile UV transform, bake completion rule, geometry winding, gameplay or tic policy
changes. This is repository-owned code, with no donor transplant.

## Retained v5 boundary

The file format, source checksum and structural/duplicate/span checks are
unchanged. The loader reconstructs only the historical source axis implied by
the v5 facing/control tuple. Existing normal supported controlled faces can
still load that retained data.

Every `FF_BOTHPLANES` controlled tile requires a fresh runtime bake: historical
v5 RGB may describe either plane behind the old aliased key. Existing corrected
alternative-plane quarantine also remains. Runtime-only tiles are omitted from
all three save passes (count/entries/pixels), so an unrepresentable runtime key
cannot export a duplicate v5 binding or lend its RGB to a legacy face. Their live
runtime owners, dirty flags and normal bake/copy path remain unchanged.

## Focused evidence and limits

[The CPU receipt](evidence/SDVK-014-CONTROLLED-PLANES-CPU.json) pins the production
working bytes, **42 passing focused tests** (16.937 seconds), retained failed
fixture-compilation attempts and **six passing real translation-unit compiles**.
The latter reuse generated build headers with isolated current source headers;
they are compile-only evidence, not a fresh linked build.

Compiled CPU fixtures execute actual `CreateFlatSurface`, `AddSurfaceToTile`,
publication/retirement, indexed-flat creation, height updates, immediate UV
publication, `LightmapTile::ToUV`, retained admission and serialization code.
The exact old binding and indexed producer are retained with source commit and
SHA-256 in `tools/pf_oracle/tests/fixtures/sdvk014-controlled-plane-pre-fix.json`.
They fail the named distinct-plane and wrong-page/UV controls. Same-key unequal
planes, ordinary output, normal/inverted paths, no-lightmap sharing, source
height spans, current allocation retirement and v5 save omission are checked.

The CPU adapters supply storage and preselected faces; they do not prove a
native authored `FF_BOTHPLANES` draw, pixels, bake convergence or physical cost.
The existing #161 native matrix and all retained failed attempts remain intact.
General sloped/inverted/recursive 3D-floor native coverage, dynamic copied-plane
topology, FF_FIX/Vavoom content semantics and the inherited
`OnMidTex3DHeightChanged` no-op remain unclaimed. Self-sourced vertex range
coverage is a CPU storage check, not acceptance of those content families.
