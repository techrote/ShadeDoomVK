# CFX-008 offline shader-cache audit — 2026-10-02

No game/GPU was launched for this check. While capture-repair CI ran, source inspection and the preserved target003 inputs tested a concrete remaining hypothesis: malformed cached SPIR-V returned during the known failing startup.

`VkShaderCache::Compile` keys by shader type and top-level source SHA1, and `GetFromCache` verifies current included-lump checksums. `OnInclude` can filter included text, but a source search found no active `IncludeFilter(...)` caller, so no current filtered-include collision is demonstrated. `GLSLCompiler::Compile` selects Vulkan1.2 /SPIR-V1.4 for API>=1.2; the actual GTX1650 SUPER runtime meets that path. These facts do not prove every key/dependency is correct or that the compiler/device agree on every semantic input.

The preserved baseline shader cache SHA256 `84a1cf4d06c62b487a7771e175e86a7e730ab436e98fbef4db7174b6ccbe8ecd` (11323798 bytes) parses completely as version2,230 entries, no duplicate keys/trailing/truncated data. Historical target003 `cfx-20261002T102203Z-e3c017b04823` logs138 unique cache-hit keys; all exist in that exact baseline. Every returned module has SPIR-V magic/header and passes installed SPIRV-Tools v2026.3 (`v2026.3.rc1-0-gb707790a`) with:

```text
spirv-val.exe --target-env vulkan1.2 -
```

**138 validated, zero validator failures.** No relaxed/scalar-layout override was added. This weakens the specific malformed-cache/SPIR-V structural hypothesis on those logged hits. A cache hit or valid module is not GPU execution proof, dynamic resource/index validity, descriptor lifetime correctness, correct specialization state, driver-cache validation or a causal repair. Newly compiled modules and opaque driver binaries are outside this check. No cache was cleared/changed, no shader was rewritten and no new target was run.

[Machine-readable exact inputs, tool identity and per-module result/hash](evidence/cfx008-offline-spirv.json). Proprietary compiled shader bytes remain local; the repository records only keys/hashes/results. The next leading discriminator remains the actual fault interval versus a complete typed resource binding history, then focused source/index/descriptor/lifetime analysis. The repaired address collector still needs a fresh approved safe gate before that one target.
