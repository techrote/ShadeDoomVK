# SDVK-010 offline preparatory helpers

**Not production code. Does not implement, bake, select or validate native actor IBL.** These standard-library-only Python programs are source-controlled research inputs for [SDVK-010 prepass](../../../docs/shadedoomvk/prepass/SDVK-010/SDVK-010-PREPASS.md).

`generate.py` creates a deterministic, newly authored 54-image PNG set and machine-readable `manifest.json`/ `offline_goldens.json`: six asymmetric major-axis orientation faces (+/-X,Y,Z), six uniform-neutral faces, two six-face independently colored probe sets, and 6*5 RGB8 high-contrast specular reference mips (16x16 down to 1x1, CPU box filter). The face labels are **reference coordinate labels**, not Vulkan cubemap orientation or sampler proof. The rendered lightprober actually captures scenes; production probe injection is NOT a feature or output of this script.

`generate.py::world_texel_nearest_live` reproduces the accepted PF-012 bounded 512-world-unit nearest *lightmap texel* selector using allocator-returned runtime descriptor bases; it is not an actor probe selector. Its synthetic authored0→runtime713 / authored1→runtime1201 example deliberately prevents ordinal arithmetic and confirms runtime0 fallback. `reflect_view` is a shader-world unit-vector oracle for `reflect(-V,N)`, and `prefilter_lod` is roughness*4 (no tuning). The transparent reference PNG channel values may be interpreted differently under an actual sRGB/linear loader: use live observation before setting exact radiance goldens.

`validate.py` checks a *proposed* nonproduction `sdvk010-actor-probe-observation/v0` event packet, with live pair capacity, same-owner PF-003 pair identity, explicit missingness, unit normal/view/reflection, reflection equation, roughness LOD, portal fields and reset-domain monotonicity. This is a **synthetic host semantic checker**, not a proof that the live observer emits the proposed fields. The `lightmap-gather` mode is only structurally checked at this stage. Future native work MUST add four actual map-tap identities and weights and compare those in the accepted renderer oracle. A structural PASS means neither native publication nor actor behavior is qualified.

`test_prepass.py` covers known-good/negative descriptor pairs, authored0 vs runtime0, selector boundary/ties, generation/reset rules, finite reflection/roughness and deterministic authored PNG hashing. No third-party modules or graphics hardware needed.

## Commands

```bash
python3 tools/prepass/sdvk010/generate.py --out /tmp/sdvk010-reference
python3 -m unittest discover -s tools/prepass/sdvk010 -p "test_prepass.py" -v
python3 tools/prepass/sdvk010/validate.py /path/to/proposed-emitted-draw.json
```

The last command requires later emitted-draw evidence (its JSON shape is specified at `docs/shadedoomvk/prepass/SDVK-010/diagnostics.schema.json`); none is in this checkpoint. The prepass authoring test does not run the renderer.

## Generated files and provenance

Run `generate.py --out DIRECTORY` in any clean directory. It writes 54 PNG files plus `manifest.json` and `offline_goldens.json`. All files are generated with local Python `struct` + `zlib`, no copied game assets. The generated directory is intentionally **not versioned**: its code, input constants and hashes generated at execution fully specify the data. `manifest.json` includes per-file SHA-256; running twice should byte-match.

**No PF/SDVK production modules are imported. No `master` commits/branches, shader bindings or renderer settings are modified.** After SDVK-007 receives verified final acceptance, #10 may reuse these as reference textures and convert selected designs into native PK3 fixtures in a *separate implementation task*, with actual shader-world face axes calibrated.
