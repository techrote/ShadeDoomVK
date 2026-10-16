# Durable identity audit addendum — SDVK-014

Assessed master: `ca254b6ea08228c8408562ebba26bbc1060a0311` (16 October 2026).
Status: **audit reproduced blocked invariants; NOT a production repair**.

This is the current audit supplement to RAG 02 (identity), 03 (LevelMesh) and 06
(lightmap/probes). Historical accepted contracts are not rewritten. The #150
semantic owner repair is accepted via PR #152; its older candidate notes no
longer describe current status. A distinct **#153 live descriptor-reset blocker**
now affects the persistent probe-map consumer.

## Index is not durable owner identity

`UploadProbeSelection -> frag_copy.glsl -> lightmodel_pbr.glsl` carries raw
runtime pair bases through R16_UINT atlas texels. `ResetHWTextureSets`, called
by live `SetTextureFilterMode`, retires those pairs without invalidating the
texels. Real slot reuse can leave an old texel pointing at another *live*,
nonzero, adjacent span-2 pair. PF-003 generation checks work only for consumers
that actually retain/check a generation token; raw texels do not.

`ResetHWSamplers` concerns hardware material samplers, not the separate probe
samplers. Do not assume retiring environment descriptors is harmless when only
a material filtering setting changes. `StartPrecaching` shares the reset route;
its ordering also belongs to #153's repair review. Do not add a blanket flush,
observer-driven refresh or silent IBL fallback to conceal this failure.

## Atlas shape is not allocation incarnation

`RectPackerItem*`, page and rectangle can all be reused identically. A copied old
`LightmapTile` can pass `HasValidAtlasRegion` against the new allocation. That
helper validates shape/range, not semantic owner history. The audit injects the
copied receipt; it does not claim a reachable stale production draw.

Ordinary last-reference `ReleaseTiles` frees/nulls the item, then `FreeTile`
tombstones its slot before reuse and clears the surface reference. Preserve this
ordering. `FullRefresh` queues surface rebuilds, not whole-atlas compaction;
`PackLightmapAtlas` packs added tiles. Do not infer active repack support from a
scratch packer's `Clear` implementation.

## Distinguish other identities and evidence boundaries

- Reserved light/probe page pairs have removed-page typed fallback publication;
  full lightmap image replacement advances its epoch and initializes new pages.
  Appending pages retains the existing prefix. These controls do not protect
  dynamic environment bases embedded in older texels.
- Probe-content epoch, image/view owner, dynamic slot generation/span, authored
  ordinal and #150 semantic set revision are distinct. Nonzero is not identity.
- Saved `LIGHTMAP` keys/transform/RGB spans are rebound to current runtime
  allocations. The format does not authenticate bake freshness using a source
  geometry/light/material digest. Structural admission is not content freshness.
- Green counterexample tests mean the audit is reproducible. They do not mean
  the renderer is clean. `sdvk014_identity_audit.py --require-clean` returns 2.

See [the report](../SDVK-014-DURABLE-IDENTITY-AUDIT.md) and
[the source/output receipt](../evidence/SDVK-014-DURABLE-IDENTITY-AUDIT.json).
Native repeated/multi-page and surface/material qualification remains separate.
#14 stays open. Physical STOP ACTIVE; physical performance HELD / NOT ACCEPTED;
historical physical root cause UNDETERMINED.


### SDVK-153 candidate follow-on

The original audit is preserved as historical evidence with pinned pre-fix
producer fragments. `sdvk014_identity_audit.py` now labels that replay explicitly;
it must still reproduce its blocked original invariants. Current behavior is
qualified separately by `test_sdvk153_descriptor_lifetime.py` and
`sdvk153_evidence.py`. The candidate preserves device-owned probe slots across
material resets and fixes fixed-slot sampler re-publication order, without
claiming that the independent atlas ABA or bake-content digest gap is repaired.
Native/exact-head acceptance and #153 blocker release are still pending.
