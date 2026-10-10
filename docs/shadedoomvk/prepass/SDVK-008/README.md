# SDVK-008 — bounded sprite relief preparatory checkpoint

**Research only. This branch does not implement SDVK-008, accept #8, or qualify physical-GPU performance.** Do not merge it to satisfy issue #8.

Assessed `master`: `cbff1d10b802e60a56d239338f810f7e1e52920d`, tree `cfc567883e299dd555e1010ce547f3fc0fae5970`. At assessment, SDVK-005 was accepted; SDVK-007 / PR #135 remained open and unaccepted. The final #7 tangent-space API is an unresolved prerequisite.

## Read and reproduce

The **individual readable source files are published on this branch**:

- [Full prepass report](SDVK-008-PREPASS.md): basis requirements, algorithm decision, equations, bounds, alpha/silhouette, evidence, integration seams and exact post-#7 handoff.
- [Host prototype](../../../../tools/prepass/sdvk008/reference.py) and [unit tests](../../../../tools/prepass/sdvk008/test_reference.py).
- [Fixture generator](../../../../tools/prepass/sdvk008/fixtures.py) and [generated-asset hash manifest](SDVK-008-FIXTURE-MANIFEST.json).
- [Deterministic CPU results](SDVK-008-PREPASS-RESULTS.json) and [draft diagnostic schema](SDVK-008-DIAGNOSTICS-DRAFT.schema.json).
- [Preregistered physical-GPU protocol](SDVK-008-PHYSICAL-GPU-PROTOCOL.md), designed for hardware logistics shared with SDVK-009 but a separate qualification decision.
- [Frozen self-contained ZIP](SDVK-008-PREPASS-PACKAGE.zip), including all nine original text files and an internal `CHECKSUMS.sha256`, extractable at the repository root. The ZIP is an immutable initial checkpoint snapshot; its enclosed README predates publishing these same source files individually.

ZIP SHA-256: `efec30fd4c14740a188b52b5f1ce0ca00c88f07102382f448409d2b16a91ab92`.

From repository root, with Python 3.10+ and standard library only:

```sh
PYTHONPATH=. python3 -m unittest discover -s tools/prepass/sdvk008 -p test_reference.py -v
python3 tools/prepass/sdvk008/test_reference.py --receipt /tmp/sdvk008-grid.json
python3 tools/prepass/sdvk008/fixtures.py --out /tmp/sdvk008-fixtures --size 32
```

The standalone reference passed **11/11 unit tests** and **1,620 deterministic grid cases** with no detected numerical anomaly; observed work was at most **23 height reads and 0.05 UV distance**. Neither CPU timing nor software Vulkan constitutes a physical-GPU performance claim.

Before production #8: require accepted merged/verified #7; reconcile authoritative sprite T/B/N and parity/portal semantics, eligibility for height-only cards, effective UV/atlas/NPOT path, alpha behavior and the emitted-draw diagnostics; then implement behind disabled-by-default controls, qualify image/state and hardware independently. **#8 remains open; no production files are modified on this branch.**
