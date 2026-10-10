# SDVK-005 — semantic height authoring and per-layer policy

Status: implementation/qualification candidate on `sdvk-005-height-semantic`. Final acceptance requires exact-head hosted CI/software-Vulkan qualification, merge, exact resulting-master verification and the release receipt.

## Authority and scope

SDVK-005 extends the accepted PF-008 material semantics and consumes SDVK-004's descriptor/lifetime model. It adds an **optional height data channel** only. It does not implement parallax occlusion mapping, displacement, a sprite tangent basis, lighting recalibration or a new descriptor allocator.

Existing content without height has the same fixed semantic/custom bindings and the same default material shader behavior. Height is never sampled by the stock `SetMaterialProps` path. Custom/later shaders opt in through `HasMaterialHeightMap()` and `SampleMaterialHeight()`.

## End-to-end material path

| Stage | Existing authority | SDVK-005 height behavior |
| --- | --- | --- |
| GLDEFS authoring | `GLDefsParser::ParseMaterial` | Adds `height "texture"` and the same bounded `{ filter nearest|linear|default }` policy now available to built-in semantic layers. |
| Automatic authoring | `FGameTexture::AddAutoMaterials` | `materials/heightmaps/<name>` is the canonical auto-height search path. |
| Semantic identity | `MaterialLayerSemantic` | `Height` is appended after `Custom`; all PF-008 enum values remain unchanged. |
| Material construction | `FMaterial::FMaterial` | Height is appended **after every historical fixed and material-custom binding**. It does not participate in selecting default/specular/PBR shader type. |
| Fixed/custom ABI | PF-008 / GLDEFS first-user-texture rules | Historical custom starts remain 5/7/9. No existing custom define is renumbered. |
| Descriptor publication | `VkMaterial::GetDescriptorEntry` | Ordinary height gets one trailing descriptor. Per-map/class/global shader custom descriptors remain before height. Indexed/palette modes deliberately omit height rather than reinterpret linear data as palette indices. |
| Shader access | `SurfaceUniforms::uHeightTextureIndex` | Relative semantic descriptor index, `-1` when absent/unavailable. Appended to the uniform struct so established member offsets remain unchanged. |
| Shader sampling | `material.glsl` | `SampleMaterialHeight(tc)` returns the red channel as normalized scalar data; caller must opt in. Missing height returns `0.0`, with `HasMaterialHeightMap()` providing explicit presence. |
| Diagnostics | SDVK-002 material observer | Records semantic `height`, actual descriptor binding, requested/actual sampler and `height_texture_index`; validator requires the semantic binding to equal the shader-visible index. |
| Lifetime | PF-002/PF-003/SDVK-004 | No new identity system. Height lives inside the same material descriptor span and follows ordinary material deletion/rebuild/generation ownership. |

## Semantic policy

The renderer distinguishes semantic intent from historical binding order. Existing defaults remain unchanged; the new built-in semantic filter syntax is opt-in for existing channels.

| Semantic | Data interpretation | Default sampling | Mips | Address policy | Missing/fallback |
| --- | --- | --- | --- | --- | --- |
| Albedo/base | colour/legacy material input | inherited global material sampler | inherited | inherited material clamp/wrap | existing base texture rules |
| Normal | vector/data | inherited (`Default`) | inherited | inherited; explicit override uses the established override sampler | no normal layer; existing shader fallback |
| Legacy specular | colour/data as existing specular shader expects | inherited (`Default`) | inherited | inherited/override policy | no specular layer; material does not select specular model |
| Metallic | scalar linear data | inherited (`Default`) | inherited | inherited/override policy | no complete PBR set; existing model selection |
| Roughness | scalar linear data | inherited (`Default`) | inherited | inherited/override policy | same |
| Ambient occlusion | scalar linear data | inherited (`Default`) | inherited | inherited/override policy | same |
| Brightmap/emissive | existing emissive semantics | inherited (`Default`) | inherited | inherited/override policy | existing 1×1 fallback placeholder |
| Height | **scalar normalized linear data, red channel** | **LinearMipLinear** | enabled by the explicit override sampler | repeat, matching the existing `MaterialLayerSampling` override sampler | no descriptor, index `-1`; default renderer output unchanged |

`filter default` on height means the height semantic default (`LinearMipLinear`), not the global albedo sampler. `filter nearest` and `filter linear` select the existing PF-008 override samplers. Existing channels use their inherited `Default` unless the author explicitly supplies a filter block.

This makes `gl_texture_filter=0` pixel-crisp albedo coexist with independently linear normal/PBR/height data without changing old content.

## Authoring examples

```text
material texture EXAMPLE
{
    normal "EXAMPLEN" { filter linear }
    metallic "EXAMPLEM" { filter linear }
    roughness "EXAMPLER" { filter linear }
    ao "EXAMPLEAO" { filter linear }
    height "EXAMPLEH" { filter linear }
}
```

Existing material-custom texture indices are unchanged:

```text
material texture CUSTOMEXAMPLE
{
    normal "N"
    metallic "M"
    roughness "R"
    ao "AO"
    shader "shaders/custom.fp"
    texture Extra "EXTRA" { filter nearest }
    height "H" { filter linear }
}
```

For PBR the historical `Extra` define remains binding 8; height follows at binding 9 and is accessed semantically through `SampleMaterialHeight`, not by inventing another fixed texture number.

## Compatibility and failure rules

- Missing height is valid and changes no default rendering.
- Missing referenced height texture follows existing GLDEFS missing-layer diagnostics and produces no height descriptor.
- Unknown semantic-layer properties or filter values are parser errors.
- Height is not bound on indexed/palette descriptor routes; palette/translation semantics therefore remain the accepted PF-110/PF-013 behavior.
- Material and global custom texture binding numbers are not shifted.
- Height descriptor publication failure follows the existing bounded PF-003 allocator failure; no global flush or aliasing fallback is introduced.
- Canvas/warped special paths retain their existing material rules; no height effect is forced onto them.

## Deterministic qualification

The accepted `material-stress` native scene is extended rather than duplicated:

- albedo-only controls remain without height;
- legacy normal/specular gets a height-authored case;
- ordinary PBR gets a height-authored case;
- all eight existing custom-PBR panels retain custom binding 8 and add height at binding 9;
- `gl_texture_filter=0` keeps the base sampler nearest while selected normal/PBR/height layers request actual linear/miplinear Vulkan samplers;
- the authored custom shader calls `SampleMaterialHeight`, providing an executed custom-shader consumer in addition to descriptor/state evidence;
- the existing material-stress resource counters continue to exercise SDVK-004 descriptor ownership/pressure.

The accepted `sprite-mirror` scene adds height to one real rotated sprite material, proving the same optional semantic is bound on the sprite material path while the remaining rotations are height-absent controls.

CPU/source contracts retain PF-008 enum identities, historical 5/7/9 custom bindings, indexed/palette separation, malformed filter failure paths and the invariant that stock material code does not sample height.

## Acceptance boundary

Software Vulkan is sufficient for SDVK-005 because this issue owns semantic/resource correctness rather than a hardware-performance result. A physical GPU is required only if qualification exposes a concrete hardware/driver-specific defect that cannot be resolved from CPU contracts and software Vulkan.

Final acceptance must publish `SDVK-005-FINAL-ACCEPTANCE.md` and `SDVK-005-RELEASE-ACCEPTANCE.json`, pin exact PR/master trees and artifacts, retain adverse attempts, and mark SDVK-007 dependency-ready only after merged-master verification.


## Verified final disposition

The implementation described above is accepted through substantive PR #132. Exact-head source evidence and CI passed; the resulting master `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1` has the identical tested tree and passed exact post-merge source evidence plus **9/9** CI including software Vulkan. See [SDVK-005-FINAL-ACCEPTANCE.md](SDVK-005-FINAL-ACCEPTANCE.md) and [SDVK-005-RELEASE-ACCEPTANCE.json](SDVK-005-RELEASE-ACCEPTANCE.json) for the pinned evidence, retained failures and limitations.

No POM/displacement/TBN behavior is accepted by this issue. No physical-GPU gate remains for the height semantic itself.
