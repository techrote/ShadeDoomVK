# PF-020 freeze checkpoint — release blocked

Date: 2026-10-04. **PF-020: NOT ACCEPTED. SDVK-001: BLOCKED.** This is a durable synthesis checkpoint, not a passing freeze or permission to begin the feature programme.

## Source and ownership

The authenticated starting master is `4df7dea1338f063c6417e024f967bfa4aa23edd4`, with eight successful required jobs in push run [37115776563](https://github.com/techrote/ShadeDoomVK/actions/runs/37115776563). All PF-001–019 accepted disposition merges and the accepted CFX merges are ancestors. The [evidence matrix](PF-FREEZE-EVIDENCE-MATRIX.md) maps their requirements, implementation, tests, artifacts, receipts and limitations. The [PF-020 issue](https://github.com/techrote/ShadeDoomVK/issues/37) remains open.

The sole mutable source repository is ShadeDoomVK, focused checkout `C:/ShadeDoomVK/campaign-worktrees/pf020-native-freeze`, branch `codex/pf020-native-freeze`. Original source and historical worktrees remain preserved. Sibling source repositories are read-only. One coordinator owns integration and native execution; independent agents reviewed evidence/source and prepared disjoint fixtures/documents. No physical GPU process has been launched for this checkpoint.

No PF-020 merge commit exists. Final-head CI, a genuinely passing freeze, merge-to-master verification and issue closure are outstanding. A checkpoint commit or successful CPU suite does not satisfy those gates.

## Confirmed release blockers

1. **GLDEFS custom-layer sampling isolation — repaired and tested locally, unaccepted:** shared material/map/class and legacy HardwareShader allocation defaults indexed the initial `texIndex=0` before assigning the free authoring slot `i`. A second declaration reset the first layer's explicit filter and left its own omitted filter at enum zero instead of `Default=-1`. The four-line repair selects the actual slot before default initialization. The source-extracted current producer passes 1,119 checks and 31 expected error cases; the exact original producer still demonstrates both counterexamples in 15 checks. Independent review confirms the original bodies are byte-exact to starting master. These are compiled parser-property checks, not a full GLDEFS loader or GPU/image claim.
2. **Indexed 2D material provisioning:** public `DTA_Indexed` reaches a one-layer `FMaterial`; Vulkan assumes three layers, while `material_paletted.glsl` consumes a missing palette binding. [Blocker #110](https://github.com/techrote/ShadeDoomVK/issues/110) owns the independent semantic repair. This is a supported source-chain finding, not a claimed physical crash. Reducing the descriptor count or supplying a guessed neutral palette would not establish correct palette/translation behavior.
3. Final source/build/CPU/runtime evidence must be revalidated after any accepted repair, followed by required exact-head checks and verified merge. The initial native receipts below are limited to the named current-master build and portable test changes.

## Native verification performed

Host: Windows 11 Pro build26200, `DESKTOP-D7T9A7Q`, 34,265,980,928 bytes reported RAM. Observed adapter: NVIDIA GeForce GTX1650SUPER, PCI vendor10DE/device2187, Windows driver32.0.16.1692. Tools: CMake4.4.3, Python3.14.7, Visual Studio2022 BuildTools / MSVC19.44.35228.0. These are observed environment facts; no GPU performance or additional-device qualification is inferred.

Clean configure/build commands:

```text
cmake -S . -B build/pf020-native -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPK3_QUIET_ZIPDIR=ON
cmake --build build/pf020-native --config RelWithDebInfo --parallel 3
```

Both return0. The baseline renderer source trees are `src=8a432a6dffc59df048b8ac4d413f07da396fd2a7`, `wadsrc=7f8f54fddb6098a12f9d5cdac3dc96d3c39a6bef`, `libraries=c86648a28037fff215185d0861fc652490bb359b`. Packaged baseline EXE SHA256 is `431e66ebacf75d1b57be2cdc5ffd1246504baf0316e27476fa0940594de4c006`; PDB is `7ca3488f561a6431514bb0051656083a6a1932101143383419a96571dd734451`. Resources and the existing ZMusic runtime DLL were hashed separately. Packaging is not a smoke launch.

In a VS x64 developer environment, with a new `build/pf020-cpu-temp` directory, `PYTHONDONTWRITEBYTECODE=1`, `PF_CXX=cl` and `CFX_CXX=cl`:

```text
python -X utf8 -m unittest discover -s tools/pf_oracle/tests -v
python -X utf8 tools/test_cfx_capture.py
python -X utf8 tools/pf_oracle/run.py --baseline tools/pf_oracle/baseline.json --output build/pf020-native/oracle-a.json
python -X utf8 tools/pf_oracle/run.py --baseline tools/pf_oracle/baseline.json --output build/pf020-native/oracle-b.json
```

- Inherited baseline discovery:260 tests /12 errors /zero skips,14.444s. Exactly12 hardcoded POSIX `c++` invocations could not start. That failed result is retained.
- Portable runner discovery:270 tests PASS /zero errors /zero skips,29.533s. All12 migrated compiled fixtures execute under MSVC with C++17, `/W4 /WX /UNDEBUG`; CFX's existing native compiled fixtures also execute. Ten new helper tests protect compiler selection, output placement, assertion/warning flags and failure propagation.
- Post-parser-repair discovery:272 tests PASS /zero errors /zero skips,30.333s. The focused two-test parser run also passes,1.710s; the retained pre-repair run failed the current-producer case as required. The native engine rebuild after the source repair returns0. The [compact checkpoint receipt](PF-020-NATIVE-CHECKPOINT.json) pins this source state, candidate EXE/PDB and every named local evidence hash. Subsequent indexed-material work needs a new receipt; this one remains historical.
- Four additional inherited standalone generation, bindless allocator, LevelMesh and probe fixtures compile/run PASS using the [documented native commands](../../tools/pf_oracle/README.md). LevelMesh includes10,000 fragmentation operations; assertions remain enabled.
- CFX capture classifier:8/8 PASS,0.060s. No physical CFX runner was invoked.
- Deterministic oracle runs both succeed and byte hashes match: `2f8d95cfe4184dba7b432e701146e1275ef8ff5edc25910a086bd02539028f88`.

Disposable native artifacts are retained in `build/pf020-native/` and `build/pf020-acceptance/`, including the failing baseline log, passing portable log, standalone fixture logs, both oracle JSON files, build log, baseline package/resource hashes and environment receipt. They are evidence staging, not instruction authority. The source-controlled compact receipt will identify retained hashes; unrestricted native logs and game content are not published.

## Aggregate performance and quality boundary

The [matrix](PF-FREEZE-EVIDENCE-MATRIX.md) reviews aggregate implications and exclusions rather than adding incompatible subsystem percentages. Retained PF-016 evidence measures representative CPU setup benefit; PF-018 measures bounded AABB CPU/resource benefit with mixed whole-path timing; PF-005 and PF-019 prove bounded allocation/work reductions. None establishes a matched founding-baseline→current-master GPU/frame-budget percentage.

PF-017's final five integrated pairs regress CPU setup10.79% and whole-frame2.42%. The complete candidate was restored; material hashes remain measured no-go. Earlier prototype savings are not retained benefits, and incomplete candidate packed-state/byte diagnostics remain unmeasured. No accepted optimization may reduce eligible lights, alter filtering/mips/color space/precision/resolution, suppress active effects or change gameplay/portal/probe/shadow policy.

## Limits and next action

CFX's accepted removed-page typed-neutral descriptor publication and ordinary fence-controlled atlas retirement remain authoritative. DBP37 repaired GTX coverage is3/3; the selected originalDBP50/v1.2/Sunlust routes each qualify3/3 in accepted historical evidence. Unique historical shader/access/driver causation is not proved; repaired P400 behavior is untested. Preserve every historical STOP/saturation guard. This checkpoint does not reopen a crash campaign.

Resolve #110's actual palette/translation binding semantics before any indexed-path GPU launch. Refresh the final source matrix, native receipts and remaining required runtime coverage. Publish only reviewable, accurately blocked checkpoint/repair work until the entire PF-020 contract passes. No human action is currently required.
