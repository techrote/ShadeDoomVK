# SDVK-158 — retained LIGHTMAP freshness and repeated multi-page transitions

## Disposition

**Implementation candidate. Hosted exact-head acceptance pending.**

Parent SDVK-014 remains open. This increment is deliberately bounded to retained
LIGHTMAP authored-source freshness plus repeated/multi-page lifecycle correctness.
It does not complete the later special-surface/material matrix and does not
authorize or infer physical GPU performance.

Assessed parent is `master@d6b089d53bf53295604757f3924ce9ad3517ad3a`,
tree `8d3b6b928cb109abaaf24ce25858843d948a0216`.

## Minimum retained-freshness contract

LIGHTMAP is upgraded from version 4 to version 5. The persistent header is:

```text
int32    version = 5
uint32   tileCount
uint32   pixelCount
uint8    sourceDigest[16]
TileEntry tiles[tileCount]
uint16   rgb[pixelCount * 3]
```

`sourceDigest` is the engine's existing `MapData::GetChecksum` result already
stored as `FLevelLocals::md5` before map loading. That authority is deliberately
non-circular:

- UDMF: exact `TEXTMAP` bytes;
- binary maps: map label/header, THINGS, LINEDEFS, SIDEDEFS and SECTORS;
- BEHAVIOR is included when present;
- generated node data is excluded;
- LIGHTMAP itself is excluded.

For this minimum contract, the digest therefore authenticates the authored map
geometry, authored thing/light inputs, sector/side material bindings and map
behavior source that define the bake. `LIGHTMAPVER` separately identifies the
engine-side retained format/bake interpretation contract.

### Explicit limit

This is **not** a general content-addressed asset system. Replacing external
texture/material resource bytes while preserving the same authored map binding is
not authenticated by `MapData::GetChecksum`. Such external-resource freshness is
outside this minimum v5 contract and must not be silently described as covered.

## Fail-closed load ordering

`MapLoader::LoadLightmap` now:

1. rejects every pre-v5 or unknown LIGHTMAP version;
2. reads the v5 source digest;
3. compares it byte-for-byte with the current level source checksum;
4. returns false on mismatch **before** reading/admitting retained tile ownership
   into current transforms/extents/completion state;
5. retains the existing complete structural admission pass for bindings, ranges,
   transforms, duplicate bindings and pixel spans;
6. only then applies admitted retained transforms/pixels and clears completion
   flags for those admitted tiles.

Returning false preserves the existing ordinary path: current tiles retain their
fresh bake state and are packed/baked normally. No stale retained state is
partially applied before fallback.

`Lightmap.RetainedTilesLoaded` records only entries that passed both source
provenance and structural admission. It is passive qualification state and does
not alter rendering policy.

## Repeated/multi-page native fixture

The hosted SDVK-158 fixture contains one large authored UDMF room and an embedded
version-5 LIGHTMAP. The retained ceiling and floor are each 513×513 texels using
the exact production `SetupTileTransform` math, including the +0.1 origin bias.
Two 513×513 allocations cannot share one 1024×1024 atlas page in either axis, so
the fixture requires at least two current pages. Ordinary wall tiles are left
unretained/dirty, preventing the fixture from passing solely by copying prepared
pixels.

A state-only, opt-in and outcome-blind input driver queues ordinary console
commands after fixed newly presented main-view ordinals:

| Main views | Input |
| ---: | --- |
| 56 | `invalidatelightmap` |
| 88 | `map SDV158` (same-map retained reload) |
| 120 | `invalidatelightmap` |

The driver reads no renderer result and cannot decide whether to advance.
Acceptance comes from passive resource records.

## Passive lifecycle witness

Each retained state frame records:

- CPU atlas texture size/page count;
- current Vulkan lightmap page count;
- live/current-valid/invalid tile counts;
- accepted retained tile count;
- `NeedsInitialBake`, `GeometryUpdate` and `ReceivedNewLight` partitions;
- completed `UpdateLightmaps` tile count for that frame;
- per-page live tile occupancy;
- current page-bound receipt validity;
- Lightmap resource epoch and LevelMesh mutation epochs.

The gate requires every retained frame to have at least two current pages, exact
CPU/Vulkan page-count agreement, zero invalid live receipts and complete
per-page accounting. Both invalidation phases and the reload phase must perform
real completed tile work and finish with all three dirty categories clear.
Same-map reload must replace the Vulkan lightmap resource epoch while retaining
valid current-page ownership.

Two independent clean-state processes execute the full invalidate → reload →
invalidate schedule and must repeat exact semantic state and final RGB.

## CPU/source falsifiers

The retained lifecycle suite requires:

- exact source-digest equality passes;
- first-byte and last-byte digest mutations fail;
- a deliberately bypassed equality check fails its named negative;
- v5 digest admission occurs before any retained tile mutation;
- save writes the current level digest and accounts for the 16-byte header field;
- the source checksum authority contains the declared authored map inputs and
  excludes LIGHTMAP/generated node lumps;
- existing retained structural admission, post-copy completion and page
  initialization negatives remain intact.

The dedicated native-oracle tests additionally reject single-page substitution,
invalid live receipts, missing completed tile work, incomplete dirty convergence,
missing reload epoch replacement, missing retained admission and changed driver
boundaries.

## Remaining SDVK-014 boundary

After this increment, the major remaining software campaign item is the supported
special-surface/material lifecycle matrix (decals, warped/reflective/translucent,
portals/Line_Horizon/3D floors and semantic material/height combinations) plus any
negative controls it exposes.

Physical GPU bake/update cost, representative scaling and hardware stability
remain separately **HELD / NOT ACCEPTED**. **Physical STOP remains ACTIVE.**
Historical physical root cause remains **UNDETERMINED**.
