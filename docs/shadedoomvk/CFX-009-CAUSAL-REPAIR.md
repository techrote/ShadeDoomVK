# CFX-009 causal repair notebook — #102

## 2026-10-02 — scope and preparation

The owner approved **six total launches / two confirmed device-loss or TDR episodes**, including safe controls. One application loss with a correlated OS TDR counts once. Every historical STOP remains immutable; twelve guards are hashed in the new lane opening. CFX-008 remains stopped at one safe launch and zero losses because its old synchronous collector dropped 237 writes.

Accepted PR #100 merge `d7ebce43449e9f347dccf399999832e11ea7c105` supplies the queued collector. A fresh RelWithDebInfo build completed with matching PDB; renderer source remains exactly that accepted merge. The dedicated runner branch changes only CPU orchestration/tests/documentation. **71 focused CFX tests pass under MSVC ASan**. New scope tests reject expired/negative budgets, changed guards, binaries/symbols, wrong scope/root, missing/changed control proof, and missing address/dump arguments. Existing CFX-007/008 behavior and spent ledgers remain unchanged.

PR #101 offline audit is accepted with all eight CI checks passing and verified on master as `c8c8cf6f32bb5b570a8787558655bc4eb2b4589b`. It changes two documentation/evidence files, no renderer source. All 138 logged historical target cache-hit modules passed installed spirv-val under the source Vulkan 1.2 target; this does not establish dynamic access or lifetime correctness.

New local root: `C:\ShadeDoomVK\pf-local-evidence\cfx009-gtx1650super-20261002-repair`. Fresh automated baseline passes since the last CFX-008 recovery, `2026-10-02T12:22:48.820883+00:00`, with unchanged boot `2026-10-01T22:33:23.5000000Z`. It verifies the single healthy GTX 1650 SUPER / expected 616.92 driver, NVML/Vulkan, sane health telemetry, responsive desktop, no live game process, coherent storage and no new hardware/OS anomaly.

Initial phase permits only the preserved IWAD-slot-only safe activation/equivalence control, then one exact original DBP37 MAP01 address-localization target. The target requires a hashed, complete control proof, actual queued flush/cutoff fields, intact run identity, zero omissions and unchanged exact pixels/protected mesh. All six slots are counted durably before child launch, with required pre-kill dump and cache restoration. Subsequent source/repair experiments require written analysis and explicit plans; no automatic retry loop exists.

No CFX-009 application launch has occurred at preparation. Next: safe proof → sole target if accepted → full actual fault/address/submission/process evidence analysis → smallest source defect and correctness repair if supported. A candidate must pass a relevant control and exactly three independent former-reproducer successes, focused regressions and all required CI. No causal repair or issue closure is claimed yet.

[Canonical issue/protocol](issues/CFX-009.md). Runtime binaries, PDBs, content and large dumps stay local; machine-readable public identities and findings will be added as evidence is produced.
