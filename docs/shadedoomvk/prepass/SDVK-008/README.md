# SDVK-008 bounded relief — preparatory checkpoint

**Research and standalone CPU-oracle evidence ONLY. Not production implementation, acceptance, or physical-GPU qualification. Do not merge as #8 implementation.**

- Owner: [SDVK-008 / issue #8](https://github.com/techrote/ShadeDoomVK/issues/8).
- Assessed `master`: `cbff1d10b802e60a56d239338f810f7e1e52920d` (tree `cfc567883e299dd555e1010ce547f3fc0fae5970`).
- Prerequisite: SDVK-007 / PR #135 was open/unmerged at prepass time. Its final basis representation/API is **not accepted here**.
- The [complete reproducible ZIP](SDVK-008-PREPASS-PACKAGE.zip) contains, under their future isolated repository paths, `SDVK-008-PREPASS.md`, the proposed relief diagnostics JSON schema, fixture manifest/generator, 1,620-case CPU results, proposed #8/#9-compatible physical-GPU packet, host reference and 11 unit tests. Extract at repo root. `CHECKSUMS.sha256` inside proves each member.
- ZIP SHA-256: `efec30fd4c14740a188b52b5f1ce0ca00c88f07102382f448409d2b16a91ab92`.

Verification after extracting the archive:

```sh
python3 -m unittest discover -s tools/prepass/sdvk008 -p test_reference.py -v
python3 tools/prepass/sdvk008/test_reference.py --receipt /tmp/sdvk008-grid.json
python3 tools/prepass/sdvk008/fixtures.py --out /tmp/sdvk008-fixtures --size 32
```

**CPU result**: 11/11 unit tests, 1,620 deterministic cases, 0 anomalies, <=23 height samples, <=0.05 UV Euclidean excursion. These do not constitute hardware performance, shader correctness, native sprite rendering or SDVK-008 acceptance.

**Handoff**: after #7 acceptance, revalidate exact T/B/N world-space and handedness/portal conventions, normal-map and height-only sprite eligibility, signed effective UV/TextureMatrix coordinates, authored sprite subrect and alpha edge rules, derivative availability and emitted-draw diagnostic seam; then implement and qualify #8 separately. Leave #8 open and production unchanged.
