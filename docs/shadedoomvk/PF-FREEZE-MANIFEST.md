# PF-020 freeze checkpoint — release blocked

Date: 2026-10-04. **PF-020: NOT ACCEPTED. SDVK-001: BLOCKED.** This is a durable synthesis checkpoint, not a passing freeze or permission to begin the feature programme.

## Source and ownership

The authenticated starting master is `4df7dea1338f063c6417e024f967bfa4aa23edd4`, with eight successful required jobs in push run [37115776563](https://github.com/techrote/ShadeDoomVK/actions/runs/37115776563). All PF-001–019 accepted disposition merges and the accepted CFX merges are ancestors. The [evidence matrix](PF-FREEZE-EVIDENCE-MATRIX.md) maps their requirements, implementation, tests, artifacts, receipts and limitations. The [PF-020 issue](https://github.com/techrote/ShadeDoomVK/issues/37) remains open.

The sole mutable source repository is ShadeDoomVK, focused checkout `C:/ShadeDoomVK/campaign-worktrees/pf020-native-freeze`, branch `codex/pf020-native-freeze`. Original source and historical worktrees remain preserved. Sibling source repositories are read-only. One coordinator owns integration and native execution; independent agents reviewed evidence/source and prepared disjoint fixtures/documents. The initial `f4959818` checkpoint had no physical GPU launch. Subsequent unaccepted native attempts are recorded below.

No PF-020 merge commit exists. Final-head CI, a genuinely passing freeze, merge-to-master verification and issue closure are outstanding. A checkpoint commit or successful CPU suite does not satisfy those gates.

## Confirmed release blockers

1. **GLDEFS custom-layer sampling isolation — repaired and tested locally, unaccepted:** shared material/map/class and legacy HardwareShader allocation defaults indexed the initial `texIndex=0` before assigning the free authoring slot `i`. A second declaration reset the first layer's explicit filter and left its own omitted filter at enum zero instead of `Default=-1`. The four-line repair selects the actual slot before default initialization. The source-extracted current producer passes 1,119 checks and 31 expected error cases; the exact original producer still demonstrates both counterexamples in 15 checks. Independent review confirms the original bodies are byte-exact to starting master. These are compiled parser-property checks, not a full GLDEFS loader or GPU/image claim.
2. **Indexed 2D material provisioning:** public `DTA_Indexed` reaches a one-layer `FMaterial`; Vulkan assumes three layers, while `material_paletted.glsl` consumes a missing palette binding. [Blocker #110](https://github.com/techrote/ShadeDoomVK/issues/110) owns the independent semantic repair. This is a supported source-chain finding, not a claimed physical crash. Reducing the descriptor count or supplying a guessed neutral palette would not establish correct palette/translation behavior.
3. Final source/build/CPU/runtime evidence must be revalidated after any accepted repair, followed by required exact-head checks and verified merge. The initial native receipts below are limited to the named current-master build and portable test changes.
4. **Mapped software framebuffer layout — source-established independent blocker:** `AllocateBuffer()` leaves its sampled host-written image in `GENERAL`; `CreateTexture(nullptr, ...)` and existing-image lookup preserve it, while the bindless writer declares `SHADER_READ_ONLY_OPTIMAL`. [Blocker #112](https://github.com/techrote/ShadeDoomVK/issues/112) owns this separate protected-route repair. No incoherent software launch or GPU failure is induced or claimed. Its diagnostic must not conceal the mismatch by transitioning or copying the sampled-only image.
5. **PBR missing-probe sentinel/view type:** [blocker #113](https://github.com/techrote/ShadeDoomVK/issues/113) records a reachable initial two-probe bake where a missing pair returns0 and PBR treats the fixed 2D null/BRDF views as cubes. The fallback's contribution/blending decision remains unresolved; no affected PBR GPU route was launched. See the [source blocker notebook](PF-020-PBR-PROBE-BLOCKER.md).

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
- Post-parser-repair discovery:272 tests PASS /zero errors /zero skips,30.333s. The focused two-test parser run also passes,1.710s; the retained pre-repair run failed the current-producer case as required. The native engine rebuild after the source repair returns0. The [compact checkpoint receipt](PF-020-NATIVE-CHECKPOINT.json) pins this source state, candidate EXE/PDB and every named local evidence hash. Source pins explicitly distinguish measured native raw bytes from LF-normalized/committed blob bytes, with byte equality verified against checkpoint `f495981841945b8779b0d73b70f603cfe968a749`. Subsequent indexed-material work needs a new receipt; this one remains historical.
- Four additional inherited standalone generation, bindless allocator, LevelMesh and probe fixtures compile/run PASS using the [documented native commands](../../tools/pf_oracle/README.md). LevelMesh includes10,000 fragmentation operations; assertions remain enabled.
- CFX capture classifier:8/8 PASS,0.060s. No physical CFX runner was invoked.
- Deterministic oracle runs both succeed and byte hashes match: `2f8d95cfe4184dba7b432e701146e1275ef8ff5edc25910a086bd02539028f88`.

The subsequent, unaccepted #110 candidate now has a real unchanged base-palette row, canonical-remap-specific R8 images, scoped synchronous indexed production, discrete sampling and explicit final sampled layout after non-mip copies. Its strict production-extracted current/original fixture passes24/24 tests in3.374s; the accepted-master negative retains the missing-layer and non-mip layout defects. Full native PF discovery passes302/302 tests in33.850s with zero errors/skips, four strict standalone fixtures pass, CFX classifier8/8 passes0.044s and both final-source oracle hashes still equal the value above. The new diagnostic builds successfully with the native engine. The corrected seven synthetic runtime-input tests pass0.013s. These are CPU/build/preparation receipts; scoped native GPU output and validation remain pending. The rejected neutral-index/translated-row proposal is retained as history in the blocker notebook.

Disposable native artifacts are retained in `build/pf020-native/` and `build/pf020-acceptance/`, including the failing baseline log, passing portable log, standalone fixture logs, both oracle JSON files, build log, baseline package/resource hashes and environment receipt. They are evidence staging, not instruction authority. The source-controlled compact receipt will identify retained hashes; unrestricted native logs and game content are not published.

## Subsequent native attempts — incomplete acceptance

The narrow #112 layout repair now passes11/11 strict production-extracted software tests, preserving both accepted-master R8/BGRA mismatches as negative controls. The updated indexed extraction passes25/25 and the then-current runner passes20/20:56 tests in6.002s, zero errors/skips (`layout-indexed-runner-tests.log`). Material publication passes the selected image's tracked `GENERAL` or `SHADER_READ_ONLY_OPTIMAL` layout; the writer rejects other layouts. Allocation, host pixels, sampling, cache topology and fences are unchanged. Real software-scene acceptance remains pending.

Three isolated hardware processes have run. Their attempt directories and receipts are immutable; none is a complete accepted packet:

| Attempt under `build/pf020-native/pf110-runs/` | Actual outcome |
|---|---|
| `core-nearest-01` | Fixture ZScript header rejected an unexpected semicolon before the native diagnostic; the owned90s watchdog terminated this child. An unpinned adjacent `extras.wad` loaded. No indexed output result. |
| `core-nearest-02` | Exit0, core layer proved active;19 cases/318 assertions retained before a diagnostic assertion failed. It incorrectly compared optional CFX IDs, which are zero when resource tracing is off. Subsequent read-only analysis finds zero actual core errors/warnings; saved mode4/filter0. The original runner also misclassified an informational log-path line and rejected legal repeated INI search paths. Its failed receipt remains unchanged. |
| `core-nearest-03` | Candidate EXE SHA256 `9c6a1828c1edacc0557d869334508503d873ef345a5e957cde34cfe39ba0efa0`; actual production diagnostic PASS348 assertions/23 cases, including resident R8/palette and shader output, translations/inverse/cache/retirement and ordinary palette/alpha controls. Exit0, proved core activation, zero errors/warnings, immutable inputs unchanged. Overall runner FAIL: no presentation PNG. |

Attempt03 queries actual native linear-image subresource geometry using the production software allocation:640×480 R8 has offset0/row pitch640 bytes and BGRA has offset0/row pitch2560 bytes, matching the respective producer pitches. Both map successfully. This is an allocation observation, with no host pixel write, software draw or copy from the sampled-only image. Its reported image layout is the renderer's tracked layout, not a driver query of current layout.

The missing screenshot exposed another preparation defect: exec-file lines dispatch separately, so standalone `wait` lines do not defer later lines. Prior warm-up/frame-timing and fixed-scene presentation were therefore not established. The repaired runner emits a bounded single semicolon chain with source-linked negative tests, ensuring each wait has a continuation and queued screenshot work can execute before quit. It needs a fresh run. Prior raw diagnostic draws remain real GPU evidence; neither they nor allocation observations establish software presentation, synchronization validation, a clean final candidate build, required final-head CI or acceptance. No GPU timing or additional hardware qualification is claimed.

## Latest material build and rejected presentation gate

Strict native MSVC discovery passes345/345 tests in32.814s with zero errors/skips; four strict standalone fixtures, CFX classifier8/8 and both deterministic oracle hashes pass. The protected runtime-input/runner subset passes37/37 in1.089s. A fresh configure/build under `build/pf110-clean` returns0; logs are `configure-pf110-clean.log` and `build-pf110-clean.log` in `build/pf020-native`. The staged EXE SHA256 is `8f2baf070ac0a475eaf7589ec3e91ead265aa3ea8ec4036e665a9611269e341d`; candidate3 records2528 exact source files and build/staged counterpart hashes.

Hardware `core-nearest-04` completes400 assertions/26 native cases, actual mode4/filter0, core validation active with0 errors/warnings, exit0 and a640×480 screenshot. However, its original runner PASS is rejected as presentation acceptance: the PNG contains the striped room/log and no authored overlay, and its gate verified only the header/extent. The original receipt and artifacts are immutable. [Retained attempts](PF-110-RETAINED-ATTEMPTS.json) records this separate FAIL disposition without replacing the valid raw GPU observations.

Source tracing establishes that `G_Ticker` can process a17-tick catch-up batch before `D_Display`; the old post-diagnostic5/post-enable5 waits can complete and request a screenshot of the previous presented frame within that batch. Registration, saved overlay=true and HUD=false are insufficient. A revised input/runner needs display-boundary waits, an actual enabled overlay acknowledgement and decoded source-declared ROI comparisons. All mode/filter/core/sync acceptance runs must be regenerated; no software/synchronization acceptance follows from attempt04.

## Aggregate performance and quality boundary

The [matrix](PF-FREEZE-EVIDENCE-MATRIX.md) reviews aggregate implications and exclusions rather than adding incompatible subsystem percentages. Retained PF-016 evidence measures representative CPU setup benefit; PF-018 measures bounded AABB CPU/resource benefit with mixed whole-path timing; PF-005 and PF-019 prove bounded allocation/work reductions. None establishes a matched founding-baseline→current-master GPU/frame-budget percentage.

PF-017's final five integrated pairs regress CPU setup10.79% and whole-frame2.42%. The complete candidate was restored; material hashes remain measured no-go. Earlier prototype savings are not retained benefits, and incomplete candidate packed-state/byte diagnostics remain unmeasured. No accepted optimization may reduce eligible lights, alter filtering/mips/color space/precision/resolution, suppress active effects or change gameplay/portal/probe/shadow policy.

## Limits and next action

CFX's accepted removed-page typed-neutral descriptor publication and ordinary fence-controlled atlas retirement remain authoritative. DBP37 repaired GTX coverage is3/3; the selected originalDBP50/v1.2/Sunlust routes each qualify3/3 in accepted historical evidence. Unique historical shader/access/driver causation is not proved; repaired P400 behavior is untested. Preserve every historical STOP/saturation guard. This checkpoint does not reopen a crash campaign.

Complete #110/#112's fresh protected native matrix after the presentation gate repair, retaining exact source/build/input identities and failures. Resolve #113's contribution decision and prove its negative off GPU before any affected PBR launch. Refresh final source/RAG/receipts and required CI/review/merge evidence. Publish only reviewable, accurately blocked checkpoint/repair work until the entire PF-020 contract passes. No human action is currently required.


## Candidate4 source/CPU checkpoint; native gates pending

[Compact candidate checkpoint](PF-110-CANDIDATE-CHECKPOINT.json) records the
clean engine build,391/391 strict PF CPU gate and2,528 unchanged engine source
pins. The real restart seam and corrected linear-control presentation gate
have independent source review. No candidate4 GPU launch has yet occurred.
All12 normal mode/filter/validation cases and separate core/sync genuine
restart runs remain required. #113 and the overall freeze remain blocked;
the independent GLDEFS repair PR115 cannot be treated as freeze acceptance.
