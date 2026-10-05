# PF-020 — PBR missing-probe fallback blocker

Status: **RESOLVED — #113 accepted through PR #117; independent PF-020 freeze pending**

Authority: [#113](https://github.com/techrote/ShadeDoomVK/issues/113), required by [PF-020 / #37](https://github.com/techrote/ShadeDoomVK/issues/37)

Accepted source inspected: `4df7dea1338f063c6417e024f967bfa4aa23edd4`
Audit date: 2026-10-04

## Current decision checkpoint

[#113's delegated contribution decision](PF-113-MISSING-IBL-DECISION.md) is now
recorded: zero IBL for missing token zero, with original mixed-tap weights and
sum order retained. No renormalization or environment substitution is adopted.
[Guarded implementation and native qualification](PF-113-IMPLEMENTATION-NOTES.md)
and [compact measured receipt](PF-113-FINAL-NATIVE-VERIFICATION.json) now pass.
[Release acceptance](PF-113-RELEASE-ACCEPTANCE.json) records all final-head and
post-merge jobs, independent review and verified master. #113 is closed.
The original unresolved-decision audit below remains historical evidence;
PF-020 still requires its separate full freeze acceptance.

## Finding and evidence boundary

The inherited Vulkan PBR consumer can interpret the missing-probe token `0` as a cube-image descriptor index, although fixed descriptors `0` and `1` contain 2D views. The initial multi-probe bake provides a reachable source counterexample. This defect is present at accepted master and is independent of the #110 indexed-material and #112 sampled-layout candidates.

The original notebook recorded authenticated source inspection. The separately retained CPU negative below extends that evidence; no native PBR, validation-layer, device-loss or driver-causation result follows. No original incompatible path was launched on GPU. PF-020 and SDVK-001 remain blocked; the adopted decision is linked above and repair acceptance remains pending.

## Exact source pins

The following are Git **blob SHA-1** identities returned through authenticated GitHub for the accepted commit above. They identify committed source objects, not raw local-file SHA-256 values or a measured native executable/source closure. Line anchors refer to that immutable commit; later candidate line numbers may differ.

| Accepted source and relevant lines | Git blob SHA-1 |
|---|---|
| [UDMF authored indices, 919–924](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/maploader/udmf.cpp#L919) | `2cf9ccfbf64cbdb29e7e0b5c5b05e89cbb8761bd` |
| [Closest sector/side targets, 726–771](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/g_levellocals.h#L726) | `ce93f115eebc837903a1adcf08bb88c3e078f314` |
| [Incremental render/publication order, 33–40](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/common/rendering/hwrenderer/data/hw_lightprobe.cpp#L33) | `73c20dc1eb0f9a083e036267ea17cdf4d3e900e0` |
| [Initial cube pair, 432–450; sampled collection growth, 507–509; 2D fixed views, 180–218](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/common/rendering/vulkan/textures/vk_texture.cpp#L432) | `976edcf98f3ba076504212253d79dc2561883014` |
| [Completed-pass publication, 486–489](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/common/rendering/vulkan/vk_lightprober.cpp#L486) | `eafeecafe4e90c29f4b7c67ef0122f014a25069f` |
| [Fixed descriptors, 202–203; missing-map lookup, 578–602](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp#L578) | `47c9e8b5c7225d9437b0d39d6dc64a16fa810d21` |
| [Uniform lookup, 461](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/common/rendering/vulkan/vk_renderstate.cpp#L461) | `0d42691aef22429e979acbdfbeef2217d856b3cc` |
| [Enabled incremental probe rendering, 450–472](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/src/rendering/hwrenderer/hw_entrypoint.cpp#L450) | `b6c1eacef1df735c295a847c8f59af5c3eb2becc` |
| [PBR zero/live sampling branches, 182–209](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/wadsrc/static/shaders/scene/lightmodel_pbr.glsl#L182) | `d43b6e66af7b5644aec3dc0b0cd24d829891667d` |
| [Cube-sampler declaration, 3](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/wadsrc/static/shaders/scene/binding_textures.glsl#L3) | `95e976ae0cd5aa3a9ee39ee422ede51610c11eed` |
| [Default 2D image-view type, 384–390](https://github.com/techrote/ShadeDoomVK/blob/4df7dea1338f063c6417e024f967bfa4aa23edd4/libraries/ZVulkan/src/vulkanbuilders.cpp#L384) | `7e9223a1ddd57d91e6f005a78aeb5204c2996314` |

## Reachable initial multi-probe chain

The minimized source counterexample requires a fresh two-probe scene without prebaked probe maps, probe rendering enabled, and a visible PBR surface whose nearest authored target is probe `1`.

1. UDMF allocation gives authored probes indices `0`, `1`, and so on. Closest-target assignment can choose `1` for a sector or side.
2. Texture-manager construction initially creates one real sampled irradiance/prefilter pair, for authored target `0`. It does not create sampled pairs for every subsequently authored probe before the first scene draw.
3. `LightProbeIncrementalBuilder::Step()` renders each probe before calling `EndLightProbePass()` after the complete collection. The latter copies the lightprober-owned results and grows the texture-manager sampled collections. The initial probe view, and intervening main views, can therefore draw a surface assigned an as-yet unavailable target `1`.
4. `ApplySurfaceUniforms()` resolves that authored target through `GetLightProbeTextureIndex()`. When the sampled maps are unavailable, the lookup returns token `0`.
5. Without a lightmap, PBR's `else` branch samples `cubeTextures[0]` and `cubeTextures[1]`. With a lightmap and uniform token `0`, it gathers probe indices and unconditionally samples each index and its adjacent prefilter; zero taps reach the same fixed descriptors.
6. Fixed descriptor `0` is `NullTextureView`; `1` is `BrdfLutTextureView`. Their creation uses the builder's default `VK_IMAGE_VIEW_TYPE_2D`, whereas `cubeTextures` is declared `samplerCube`. These are not the live allocator-backed environment pair.

Ordinary authored target `0` is different: the initial real cube pair resolves to a nonzero dynamic pair start. This finding does not claim that every no-probe scene, every PBR draw, or every historical CFX incident executes the incompatible branch.

## Historical decision gap at the original audit

Accepted [PF-012](issues/PF-012.md) and [probe RAG](rag/06-LIGHTMAP-PROBE-PIPELINE.md) establish:

- probe-map token `0` means explicit default/no-probe, not authored ordinal `0`;
- nonzero tokens are allocator-returned irradiance descriptors, paired with prefilter at `start + 1`;
- unavailable and unencodable runtime pairs are excluded from the live selector;
- the retained 512-unit boundary is inclusive and equal-distance ties retain candidate order;
- the active selector is independent of the dormant AABB integration and optional ray-query support.

Those identity rules do not establish the **radiometric contribution** of token `0`, the treatment of mixed valid/zero taps, or a type-safe cube fallback. The old ordinal-derived `2*N+1` draft was explicitly superseded before PF-012 acceptance and is not authority.

At the original audit, the required decision was **OPEN** under #113: state the missing-probe contribution and mixed-tap blending before implementing a typed guard/fallback. Black IBL, authored probe `0`, another environment, and weight renormalization are possible policies, not adopted choices in this notebook. Preserve valid-pair selection, contribution, interpolation and operation order plus [PF-008](PF-008-MATERIAL-SEMANTICS-CONTRACT.md) channel/sampling semantics. If the decision cannot be established, record that precise blocker rather than choosing silently.

## Original verification plan and acceptance limits

Next, resolve and record the contribution decision, then retain the exact accepted-master negative **off GPU**. Extract the actual lookup, initial builder order and PBR sampling branches with source/hash guards; stubs may model service dependencies and sample logging, but must not replace index-selection or sampling/guard logic. Preserve unavailable-uniform and all-zero/mixed-tap counterexamples against the actual fixed 2D views. Protect live allocator-backed pairs, ordinary target `0`, missing-to-available publication, repeated lookup/reset, selector omissions and unchanged 2D null/BRDF/material users.

Only after those CPU/state proofs may the coordinator prepare a clean native build and fresh tiny authored two-probe/PBR scene without prebaked probe lumps. Record actual unavailable-to-published state, production shader identity, view types, bounded zero/mixed/live controls and legal output readbacks. Prove core and synchronization validation activation in separate serialized runs. Retain process exits, failures and exact source/build/input/config/device/artifact identities. No known incompatible original path is to be launched to prove the negative.

Complete the strict PF suite, independent review, eight actual exact-head CI jobs, canonical reconciliation and verified merge/master/post-merge checks before closure. This repair alone does not accept PF-020. Historical CFX/PF-017 STOP and saturation scopes remain sealed; repaired P400 behavior remains untested. No PBR calibration, actor policy, probe-density tuning, full lightmapper campaign, feature suppression or global flush is authorized here.

## Ownership and deduplication

Before #113 creation, authenticated inspection found 21 open issues and one open PR, [draft #111](https://github.com/techrote/ShadeDoomVK/pull/111), on the existing `codex/pf020-native-freeze` coordinator branch. PF-012/#29 and PF-008/#25 are closed; the remaining `pf-012-probe-lightmap` branch belongs to merged PR #59. No independent open issue or competing probe repair PR was found.

SDVK-010/#10 explicitly excludes foundational probe repair and SDVK-014/#14 consumes corrected plumbing. Accepted PR #104's removed-page publication evidence explicitly does not establish downstream PBR sentinel handling. #113 is therefore a separate current-source blocker, not a new actor-lighting feature or a reopened historical crash campaign. Use the existing serial PF-020 coordinator and refresh live ownership before claiming work; #110/#112 may continue independently in their tiny non-PBR material fixture.


## Current CPU negative and focused continuation

The exact original extraction now reproduces the defect under strict MSVC:
20 incompatible fixed-2D-as-cube attempts across275 service/source checks,
including unavailable uniform, all-zero/mixed gathers and actual extracted
initial render-before-publication ordering. The original safety check fails
with exit1 as required. Its synthetic namespace collision and first failed
compile are retained; the derived adapter only separates compilation domains.
See [compact independently reviewed negative](PF-113-ORIGINAL-NEGATIVE-VERIFICATION.json)
and the [adopted sampling amendment](PF-113-MISSING-IBL-DECISION.md).

The focused continuation branch starts from native material/layout master
`1524686e77f1e89dabfb044bf757a2d19566c31c`. Production guarded helpers, current
extracted controls, early actual scene observation and legal native readbacks
are in preparation. None is accepted by the original CPU negative. PF-020 and
SDVK-001 remain blocked; all native and exact-head release gates still apply.
