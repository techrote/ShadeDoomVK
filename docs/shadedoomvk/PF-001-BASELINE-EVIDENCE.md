# PF-001 baseline evidence

Status: implementation baseline for PF hardening oracle  
Date: 2026-09-17  
Implementation branch base: `master@e8a7e1b9e26c00753a123360510c4e0f119168b1`  
Founding VKDoom lineage: `09634479ab5bf9adf691074fffe85a006a398cd0`

## What this baseline is

PF-001 creates a deterministic **source/contract state capture** suitable for ordinary CI before later issues have runtime renderer diagnostics/reference maps. The canonical capture is:

`tools/pf_oracle/baseline.json`

It contains ten deliberately small probes. Six protect inherited architecture/capability seams; four preserve known pre-fix defect markers until their owning PF issues repair them.

This file does not claim GPU image evidence was produced in hosted CI. The runtime/image evidence shape is defined separately by `tools/pf_oracle/runtime_evidence.schema.json` and `PF-EQUIVALENCE-PROTOCOL.md`.

## Passing architecture invariants

| Probe | Category | Owner | Meaning protected |
|---|---|---|---|
| `bindless-block-reuse` | resource lifetime | PF-003 | inherited bindless allocation/free/reuse seam remains present |
| `material-layer-sampling` | material | PF-008 | inherited per-layer sampling support remains present |
| `material-pbr-layers` | material | PF-008 | inherited normal/metallic/roughness/AO material data remains represented |
| `portal-mirror-handedness` | portal | PF-010 | portal/mirror handedness seam remains explicit |
| `portal-relative-actor-lighting` | lighting | PF-016 | actor lighting retains portal-relative positioning + world visibility seam |
| `render-context-entrypoints` | view context | PF-010 | main scene, camera-texture and probe rendering entrypoints remain distinguishable in source |

These are not assertions that the eventual PF refactors are already complete. They pin useful inherited behavior so those refactors must migrate it deliberately rather than accidentally delete it.

## Expected known defects

| Probe | Owner | Baseline observation | Required later transition |
|---|---|---|---|
| `probe-map-probe-zero-stub` | PF-012 | active lightmap probe lookup still contains the probe-0 stub path | preserve a reproducer, implement/bound intended selection, update oracle baseline deliberately |
| `indexed-red-is-alpha-todo` | PF-013 | Vulkan palette material path still records missing `CTF_IndexedRedIsAlpha` handling | add compatibility fixture/fix and update baseline |
| `sprite-clip-top-sentinel` | PF-014 | sprite clip path initializes `top` with `-NO_VAL` while fallback checks `NO_VAL` | preserve clipping regression fixture/fix and update baseline |
| `shadow-cap-traversal-order` | PF-015 | 1024 shadow-light cap is still traversal-order based with source TODO for nearer preference | define deterministic relevance policy/fix and update baseline |

A known-defect probe being reproduced is **not** a claim that the defect is acceptable. It means the pre-fix baseline is still intact and its later owner has not accidentally lost the reproducer.

## Expected oracle result

The checked-in baseline records:

```text
probe_count                 10
invariant_passed             6
known_defect_reproduced      4
unexpected                   0
```

CI must also produce byte-identical canonical JSON on repeated runs from the same source checkout.

## Why these probes were selected

PF-001 is intentionally smaller than SDVK-002. The set covers every hardening class needed immediately by PF-002..PF-019 without trying to create a source-code mirror:

- renderer resource reuse;
- semantic/material infrastructure;
- dynamic-light and portal-space seams;
- main/non-main render contexts;
- probe/lightmap correctness;
- sprite clipping/state correctness;
- capped shadow selection.

Later issues should add only minimized durable probes/fixtures where they materially improve falsifiability.

## CI and runtime limitations

The inherited GitHub workflow builds the engine on Windows/macOS/Linux but does not provide a known IWAD/content fixture, interactive window or guaranteed presentation Vulkan GPU. Requiring a renderer screenshot there would produce a brittle or misleading test.

PF-001 therefore makes hosted CI authoritative for the source/contract baseline and unit-tests the oracle itself. Runtime state/images become authoritative only when produced by an actual executable fixture environment under the equivalence protocol.

## Change rule

A later PF issue that legitimately changes one of these contracts must update, in one reviewed change:

- implementation/source;
- regression/runtime fixture where applicable;
- `probes.json` semantics if the marker changes;
- `baseline.json`;
- affected RAG/reference document;
- issue/PR evidence explaining the semantic delta.

Never delete/weaken a probe solely to restore green CI.
