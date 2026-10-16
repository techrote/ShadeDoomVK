# SDVK-156 — durable atlas allocation-incarnation receipts

## Disposition and authority

Bounded implementation under issue #156 / parent #14, based on accepted
`master@ad0833696804e57672ec425d2c33bf36732d05f1`, tree
`ee9b0cffc10316a95a4cc74d2cfd4c0462cd2e29`. PR #155 / #153 is accepted;
its persistent probe descriptor ownership and fixed-sampler ordering are unchanged.
The earlier #150 semantic probe-set owner repair is also unchanged.

This report records the implementation and CPU qualification at publication.
Exact-head normal CI, review, merge and matching-master verification remain the
publication acceptance gates; their final identities belong in the #156 acceptance
receipt. This increment is **not SDVK-014 software completion**.

Physical STOP remains **ACTIVE**. Physical GPU cost, scaling and stability remain
**HELD / NOT ACCEPTED**. Historical physical root cause is **UNDETERMINED**.
No renderer or Vulkan device was launched in the local coding environment.

## Defect and claim boundary

The PR #154 audit copied a `LightmapTile` receipt, freed its real atlas allocation,
and forced allocation of the same item object with the same page and rectangle.
The copied tile passed the old shape/range guard against the new allocation.
`Clear` followed by identical allocation reproduced the same ABA. Ordinary
current-surface `ReleaseTiles` / `FreeTile` tombstoning was already working.

These are deliberately injected stale-receipt counterexamples, not a demonstrated
naturally reachable stale native surface, wrong GPU pixel or physical crash cause.
A new guard must reject these copied receipts even when all allocator geometry
is plausible. It must not turn a historical failing fixture into a claimed pass.

## Receipt contract

`RectPacker::Alloc` now returns the value type `RectPackerAllocation`:

| Field | Meaning and issuer |
| --- | --- |
| `Owner` | Process-unique nonzero packer incarnation, assigned on construction using an atomic monotonic sequence. Destruction/reconstruction at the same address cannot reuse it. |
| `Slot` | Index into the current owner's retained item storage; never a caller-dereferenced pointer. |
| `Incarnation` | Nonzero owner-local allocation serial, incremented on every successful allocation, including exact fits and reused items. |

Copying a receipt preserves its captured identity; it does not refresh it.
Nonempty is not live. `IsLive`, `TryGetRegion`, `GetRegion` and `Free` resolve
against the **current owning packer**. Owner, nonzero serial and slot bounds are
checked before item storage is accessed. The live item's serial must then match;
free space and retired storage are rejected. `TryGetRegion` leaves its output
unchanged on failure; `GetRegion` fails explicitly; invalid `Free` returns false
without touching the replacement owner's allocation.

`Free` and internal coalescing clear retired item serials. `Clear` clears item
serials and pages but never resets the allocation sequence. Both the owner
sequence and allocation sequence refuse exhaustion before wrapping; allocation
exhaustion is checked before shelf/page/item mutation. Copy/move of a packer is
deleted, preventing duplication of an owner namespace. Packer mutation retains
the existing externally serialized execution model; only owner issuance is atomic.

A receipt authenticates runtime allocation identity, **not authored content** and
not hostile input. It is neither serialized into LIGHTMAP lumps nor sent to a
shader. Reserved descriptor/page epochs, probe-content epochs and authored
probe-set revisions keep their existing separate meanings.

## Producer and consumer audit

A full source search for `RectPacker`, `AtlasLocation`, tile-array references and
`ToUV` established the following current production paths. The exact source files
are hashed in the [CPU receipt](evidence/SDVK-156-ATLAS-IDENTITY-CPU.json).

| Path | Producer/consumer responsibility and current protection |
| --- | --- |
| `hw_rectpacker.*` | Only public allocator boundary. No public raw-item allocation/free API remains. Region snapshots are issued only through checked resolution. Internal shelf/item pointers are allocator-owned implementation details. |
| `DoomLevelMesh::AddSurfaceToTile` → `LevelMesh::AllocTile` | Creates a fresh, unallocated semantic tile and registers its surface owners. `AllocTile` rejects a copied/nonempty atlas receipt before pool mutation. No runtime owner ID comes from disk. |
| `LevelMesh::PackLightmapAtlas` | Packs pending new tiles, resolves the newly issued receipt and publishes page/X/Y plus the captured allocation. Retired/already-allocated entries and duplicate pending allocations are refused rather than silently overwriting an issued receipt. Existing live tiles retain their allocation when new tiles are appended. |
| `LightmapTile::HasLiveAtlasAllocation` / `HasValidAtlasRegion` | Liveness requires the current packer; the complete guard additionally requires exact current page/rectangle equality and existing extent/bounds checks. It never dereferences a pointer retained in the tile. |
| `LevelMesh::GetLightmapTile` / `ValidateLightmapTile` | Checked current-owner access, including const export/debug callers. Invalid tile indexes or stale/malformed atlas receipts fail before coordinate consumption. |
| `PackLightmapAtlas` mesh-vertex publication; `hw_vertexbuilder.cpp`; `hw_walls_vertex.cpp` | Resolve a checked tile before lightmap UV/page publication. The geometry-building wall route already uses `lightmaptile = -1` while no atlas allocation exists. Valid UV arithmetic is unchanged. |
| `hw_decal.cpp` (both vertex paths) | Checks the underlying current tile before inheriting its atlas coordinates. No decal material, alpha, projection or lighting semantics changed. |
| `HWDrawInfo::PushVisibleTile`; background bake scan; `lightmapcmd.cpp` | Visible enqueue uses the checked accessor. Pool scans admit only current live allocations; the actual selected-bake boundary validates the full region before use. Borrowed pointers are confined to the synchronous frame/bake call, not durable receipts. |
| `VkLightmapper::SelectTiles` | Validates destination identity before allocating scratch space. Each selected tile independently captures destination and scratch receipts. Scratch `Clear` creates new allocation incarnations on the next batch. Existing page-zero selection, padding and dirty/completion behavior are preserved. |
| `VkLightmapper::Render` / `CopyResult` | Prevalidate selected receipts before render commands and before destination resource indexing/copy. The captured destination must still belong to the selected tile; scratch page/X/Y/extents must still match. No old scratch/destination work can inherit recycled allocations. Completion remains after actual copy and the existing final barrier. |
| `VkLightmapper::SetLevelMesh` | Clears selected work and copy lists before changing mesh. Rechecking an old captured destination against a new current mesh rejects it before touching an old/dangling tile pointer. |
| `MapLoader::InitLevelMesh` / `LoadLightmap` | Constructs a new mesh, admits retained semantic entries, packs fresh runtime allocations, then validates each destination before pixel-copy address arithmetic. Existing two-phase structural admission and on-disk format are unchanged. |
| `DoomLevelMesh::SaveLightmapLump` | Validates all live tile receipts before readback/serialization; retired entries remain excluded. Runtime receipts are not persisted. RGB upload versus RGBA readback separation is preserved. |
| `GatherTilePixelStats`, background census | Count only allocations live in the current owner; these are descriptive CPU counts, not independent pixel/provenance evidence. |
| `PrintSurfaceInfo` / `DumpMesh` | Checked accessor before page/rectangle/UV export; const correctness is retained. |
| `ReleaseTiles` → `FreeTile` | Decrement current surface ownership; at last reference, checked atlas Free must succeed, clear the receipt, tombstone the pool tile, then clear the surface index. Retired slots remain reusable; binding, extents and dirty state are not resurrected. |
| `FullRefresh` / side and flat rebuilding | Queues ordinary surface rebuilds; it is not live whole-atlas compaction. Rebuild effects use the same release/new-tile/pack chain above. |

`LightmapTile::SetupTileTransform` and retained-entry width/height assignment are
pre-allocation producers. Dirty-flag invalidation and semantic surface lookup do
not themselves consume an atlas allocation. Existing surface/tile integer indexes
remain owner-managed logical references with current-surface tombstoning, not new
standalone generation-bearing surface handles. Arbitrary forged/dangling borrowed
pointers supplied outside the documented synchronous lifetime are not supported.
This change specifically closes the copied **atlas allocation receipt** ABA; it
is not a blanket memory-safety proof for every mesh pointer or GPU use.

## Repack, page reuse and rebuild semantics

There are two real packer owners: persistent `LevelMesh::Lightmap.AtlasPacker`
and transient bake-scratch `VkLightmapper::packer`. Their namespaces must never
alias, even for identical first slot/serial/rectangle values.

The persistent packer is incrementally populated. It does not currently compact
live tiles. Requesting an already allocated tile as a fresh pending allocation
now stops before its receipt can be overwritten; a future compactor must retire
and republish all affected consumers under an explicit contract. Scratch repack
is real and uses `Clear` every batch: old selected scratch receipts reject while
unchanged destination receipts remain live. Free/reallocation and whole owner
recreation reject stale receipts independently of page count or geometry reuse.

CPU multi-page tests fill three pages, recycle an identical region on the middle
page while preserving its neighbors, then clear/rebuild the same page numbers.
This is allocator/current-source CPU evidence, **not** execution of the remaining
native multi-page lightmap transition campaign.

## Falsifiable qualification

`test_sdvk156_atlas_identity.py` compiles the real allocator and tile type plus
exact current bodies for tile allocation/free/packing/access, Doom release, and
lightmapper selection/owner-switch/selected validation. Surface arrays, upload
notifications and Vulkan-adjacent services are explicitly CPU fixtures; they are
not substituted renderer execution.

Twenty positive case programs cover copied Free ABA, copied Clear ABA,
same-address owner recreation, foreign/malformed receipts, stale/duplicate Free,
coalescing, multi-page reuse, incremental packing, copied-tile admission,
malformed region, scratch repacking, retired pending destinations,
repack-without-retirement rejection, duplicate pending publication, scratch
region mismatch, selected tile/receipt mismatch, owner-switch pending work,
allocation exhaustion, owner exhaustion and bounded rebuild cycles. (The two
exhaustion cases are separate; the authoritative count/names are in the receipt.)

Eight separately compiled production mutants must fail for their named invariant:
repeated serial issuance; omitted serial comparison; Clear restarting the serial;
omitted owner comparison; unchecked stale Free; unchecked tile consumption;
omitted selected destination comparison; and wrapping allocation serial.
A compiler error or arbitrary crash is not an accepted negative result.

The existing PR #154 fixture is unchanged. Exact pre-156 allocator/header/tile
and compatible earlier fixture-driver bytes are pinned under
`tools/pf_oracle/tests/fixtures/sdvk156-pre-fix/`. The original same-item/same-region
Free and Clear controls still exit 11 with `stale-atlas-receipt-accepted`, while
current production rejects the same misuse and accepts the replacement owner.
Older pre-151 boundary/retirement negatives remain separately executable too.
Two trailing-whitespace comment lines in the pinned old sources are deliberately
preserved byte-for-byte; active-source changes pass the whitespace check.
The historical audit collector still reproduces historical failures; green
collector execution and `--require-clean` status must not be relabeled as current
renderer cleanliness.

Valid-output equivalence runs an identical allocation/free trace against the
retained and current allocators: **2,560 allocations, 32 Clear cycles, 2,592 trace
lines; byte-identical page/X/Y/width/height outputs**. Trace SHA-256:
`3a729968aa9af27adfab9487b3286704d179d23c3732a9d29c4659aad5f440c0`.

The bounded current-source rebuild fixture executes **128 cycles / 512 allocations
and 512 retirements**, retaining **four tile slots, four item objects and one page**
without growth after the first cycle. GCC and Clang focused suites pass. All
20 current case programs also pass Clang ASan/UBSan with leak detection, including
an actually dangling old tile pointer rejected after owner destruction/switch.

On this 64-bit CPU fixture ABI, the receipt changes from an 8-byte pointer to a
24-byte value; item and tile objects each increase by 16 bytes (72→88 and 176→192).
The validation-enabled packer is 80→96 bytes. These measured `sizeof` values are
not a portable ABI guarantee or measured native CPU/GPU cost. No physical
performance/scaling/stability result follows.

Reproduction (CPU only):

```sh
python -m unittest tools.pf_oracle.tests.test_sdvk156_atlas_identity
PF_CXX=clang++ python -m tools.pf_oracle.sdvk156_evidence --sanitizers --out /tmp/sdvk156-fresh.json
python tools/check.py --output /tmp/sdvk156-full-check
```

The normal required CI remains unchanged, including source evidence, platform
builds and the existing isolated Avrea software-Vulkan corpus, SDVK-010,
SDVK-150 and SDVK-153 gates. No duplicate benchmark runner, new native acceptance
threshold, fixture-driven owner refresh, quality reduction or emergency flush is
introduced. Hosted success is integration/correctness evidence for that lane,
not per-texel GPU identity readback or physical acceptance.

## Remaining parent-campaign boundaries

This increment does not provide a LIGHTMAP geometry/light/material freshness
digest, introduce live atlas compaction, complete native repeated/multi-page
transitions, or qualify the full supported special-surface/material matrix.
Probe selection, shader layouts, material/sampler semantics, portal transforms,
viewmodel policy, gameplay and lighting quality are unchanged. #14 remains
**OPEN / NOT SOFTWARE-COMPLETE**, with physical requirements explicitly held.
