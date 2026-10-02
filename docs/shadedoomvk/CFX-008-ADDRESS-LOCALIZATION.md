# CFX-008 / #99 — GPU address localization notebook

## Accepted starting point, 2026-10-02

PR98 passed all eight checks at `0e07a1429939580e03b4201327161a08880ec54a`. Review accepted its bounded address collector, stopped causal evidence and independent LevelMesh vertex/index publication fix. It did **not** accept a DBP37 crash repair. PR98 merged as `c6a7197ae48b8d163df9f72783c177ca427505f5`, verified on current master. #97/#75/PF-020 remain unresolved.

The owner approved the separately documented **two-launch / one-loss** proposal with “Go ahead!”; #99 records that scope. All eleven historical STOP files remain intact. New evidence root: `C:/ShadeDoomVK/pf-local-evidence/cfx008-gtx1650super-20261002-address/`. CFX-007 remains stopped at 16 launches / 6 losses.

Fresh baseline passed: only GTX1650 SUPER, Code0, driver616.92 /32.0.16.1692; boot2026-10-01T22:33:23.5000000Z; NVML/Vulkan enumeration, responsive session, no running game, coherent storage and no new hardware/OS anomaly since the last CFX-007 recovery. Baseline is evidence, not a substitute for per-attempt checks.

## Fixed sequence and discriminator

1. Exactly one preserved IWAD-slot-only MAP01 paused/capped/seed12345 safe control, capture/resource/address mode, no validation. The IWAD slot is not asserted stock Doom II. Compare decoded pixels and protected OBJ topology/counts with CFX7-CONTROL-006. Full OBJ vertex/UV bytes varied in previous off/off controls and are not asserted identical.
2. Only after a hashed, complete safe proof: exactly one original DBP37 MAP01 target, original uncapped/VSyncfalse/MSAA4/config/cache/script, LevelMesh and generalized pipeline defaults restored. No control-only seed, pause or cap.

The target asks which bind/unbind event ranges overlap the **actual newly returned** EXT fault address precision interval. A resource overlap motivates that resource's upload/index/range/descriptor/lifetime audit; an internal allocation or no overlap establishes a narrower capture limitation. A different fault or no loss is reported honestly. None justifies an identical retry.

## Commands and fail-closed gates

`python tools/cfx008_execute.py --plan <new-root>/control-001/plan.json` performs health and identity preflight; add `--launch` for the one reserved control. The executor automatically accepts `control-proof.json` only on clean exit/recovery, exact run-ID agreement, registered address messenger/enabled feature, real bind and unbind callbacks, intact records, zero omission/contention/malformed/writer gaps at teardown, identical image and protected mesh state. Target preflight verifies that proof and each evidence hash again.

`python tools/cfx008_execute.py --plan <new-root>/target-001/plan.json --launch` is the sole permitted target. There is no launch loop. The wrapper durably reserves every launch, backs up/restores global caches, enforces <=60-second watchdog and matching-PDB full process dump before kill, rechecks health and writes an artifact index. Final count2 or loss1 closes the scope with a STOP file even after normal recovery.

Renderer EXE/PDB comes from the verified PR98 master build. Python runner source is pinned separately in the attempt and manifest. CPU-only scope/guard/budget/argument/control-gap tests precede launch. Existing CFX-007 gates retain their original16/6 behavior.

Address callback events are reported driver virtual bindings, not queried BDA, GPU execution checkpoints or a unique live allocation map. CPU frame/submission annotations are host snapshots. Preserve aliases, pre-creation/internal handles, partial/unmatched unbinds and reused handles. A clean validation log or no overlap does not prove correctness.

## Working status

Fresh merged renderer build succeeded. Nine new CPU-only gate tests and all61 CFX tests in MSVC ASan passed. Physical activation/result is pending. No CFX-008 application launch has occurred at this entry. Record subsequent facts here and in the machine-readable evidence index before any scope disposition.
