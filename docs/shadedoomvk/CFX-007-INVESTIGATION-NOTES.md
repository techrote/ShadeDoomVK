# CFX-007 / #97 investigation notebook

**Live disposition: crash unresolved.** This is the detailed work record for PR98. The demonstrated LevelMesh input-dependency repair is not a sufficient DBP37 repair. Parent75/PF020 remain blocked. See [attempt ledger](evidence/cfx007-attempts.json) for exact run IDs, manifests, hashes, plans, results and local paths.

## Objective and accepted starting state

Find the smallest source correctness defect explaining DBP37 MAP01 loss, repair it, and stop physical validation after three independent former-reproducer successes plus safe controls/focused regressions/required CI. This is not a repeated characterization campaign. All old physical STOP files and binaries remain preserved; none of the old binaries were launched. PR96 was reviewed, passed8/8 CI, merged as `a6880fdb22e2f3d9ee85f3a86384b48ad7af9373`, and verified on master before the new issue97 lane.

Owner authorizes unattended GTX1650 SUPER work with cumulative16 launches including controls /6 loss episodes. App loss and correlated OS TDR count once. Automated recovery replaces routine visual confirmation; observed corruption, failed driver/GPU/session/storage recovery or new hardware/BSOD evidence still stops. No driver/TDR/clock/power/BIOS change, broad sweep, global idle or quality reduction is part of the repair.

## Live environment / identity

- Single GTX1650 SUPER, Code0, PCI07:00.0/device2187, NVML616.92 / Windows32.0.16.1692. P400 removed. Boot2026-10-01T22:33:23.5Z, OS26200.
- Loader1.4.341; device API1.4.351. NV checkpointsrev2, EXT faultrev2, KHR faultrev1 exposed. Build uses EXT only; faults/vendor binary retrieved after explicit loss. No locally installed Aftermath Monitor/SDK/decoder path was established.
- OBS_HOOK, NV_optimus and NV_present loaded; unchanged. Their presence does not establish cause.
- Copy-only Khronos layer1.4.357.0 at `C:/ShadeDoomVK/pf-local-evidence/cfx002-tools/vulkan-sdk-1.4.357.0/Bin`, child-only layer/settings environment, independent GPUAV/sync settings and activation proofs.
- Base rebuilt EXE SHA256 `ad7fbf62ae28a34a6cdd37b6ac1283a34956fce6f2fad8a16c297a7739c0ec11`; candidatec24ecede EXE `70fe4134a08ff3bdc1bc9eafde26ae5bb0154bb6808f5dac3b0aeb9f9b5d66b6`. Matching PDBs and all resource hashes are in lane openings/manifests. PK3 sources did not change.
- Preserved IWAD-slot SHA8ac958e2… is not asserted stock DoomII; DBP37 PWADd356de75…, initial configfa45c627…, pipeline snapshot0eca9dc6…, shader snapshot84a1cf4d…. Original input/load order/uncapped/VSyncfalse/MSAA4 retained on targets. Each executor restores the current global cache in finally, with hash proof.
- Requested1904x1001 becomes actual1902x993 with current Windows workarea. This is a disclosed historical viewport limitation; controls/current targets share actual size.

## Phase reconciliation (guards preserved, counters never reset)

1. `cfx007-gtx1650super-20261001`: preflight stopped for recent KernelPower41(record6066)/6008(record6055). Owner explains deliberate restart/shutdown/P400 removal/current boot, no observed hang. Raw Windows record still says unclean shutdown; no claim it was clean or the earlier HD7770 event. Fresh post-context baseline excludes it by actual UTC creation time.
2. `…20261001-reconciled`: control001 exited0, healthy. Capture inventory incorrectly recorded manifest's own size before final rewrite. Other files intact. STOP retained; fix excludes self-size and hashes final manifest externally. Next phase carries1 launch/0 loss.
3. `…20261001-capturefix`: controls002–006 and target001. GPUAV control007 hit60s; initial conservative stop said hard/no-return hang. Matching dump shows CmdBindPipeline, and **post-dump** timeline advances to frame67, submissions131/132 and successful fence/reset. Hard-hang classification is disproven, not waived. STOP retained and next phase pins it, carrying8/1.
4. `…20261002-validation`: shorter GPUAV control008, target002, sync control009. Closed/pinned when moving to source candidate, carrying11/2.
5. `…20261002-mesh-input-repair`: candidate safe control010, targets003–006. Final count16/6. Physical budget exhausted; STOP and final state retained. Recovery gates pass; the stop is the declared ceiling, not a new recovery/hardware failure.

## Experiment log

| Attempt | Question / changed factor | Observed result / consequence |
|---|---|---|
| Controls001–003 | New capture substrate vs off, uncapped safe fixture | All healthy exits. Strict three-way state equivalence failed because uncapped off controls themselves differed; retain failed fixture choice, do not claim equivalence. |
| Controls004/005/006 | Paused/capped/fixed-seed **safe fixture only**, off/off/capture | Identical pixels; mesh headers/objects/faces/vertex+UV counts equal. Full positions/UV bytes vary within off/off baseline. Resource logging, submits and checkpoints activated. |
| Target001 | First required merged-CFX006 original DBP37 startup | Loss frame7/tic18/submission11; fence -4 after2335ms. Submission10/11 success, present success. GPU bottom marker world maps to drawcmd186/actual submission10, not recording CPU column9. |
| Control007 | Full safe GPUAV160tic fixture | GPUAV/instrumentation active, zero errors,12 feature/compile-cost warnings. Deadline; later progress proves no hard hang/loss. Cloned screenshot path accidentally pointed at006; never reached, verified006 hash unchanged. Corrected008 path. |
| Control008 | Shorter20tic GPUAV safe scene | Image+OBJ, exit0, activation verified, zero errors. Timing/features/compilation perturbed; not an output equivalence claim. |
| Target002 | Original DBP37 + GPUAV only | Loss same frame7/tic18/fence11,2465ms. Zero recovered access errors **does not clear accesses** after GPU reset. No automatic repeat. |
| Control009 | Safe LevelMesh=true + sync only | One READ_AFTER_WRITE: uploaded IndexBuffer -> vkCmdDrawIndexed INDEX_READ missing visibility. Concrete source defect localized to VkLevelMesh::BeginFrame, separate from #87 VkHardwareBuffer path. |
| Control010 | Candidate input publication + sync, prior paused safe fixture | Exit0, zero errors/warnings, identical pixels/protected mesh state; full OBJ bytes not asserted. Correctness hazard removed. |
| Target003 | Candidate barrier only, original capture-mode DBP37 inputs | Still explicit loss same frame7/tic18/fence11 and invalid read0x1da00000. Candidate is a real fix for safe hazard, **not sufficient crash repair**. Analyze target-specific sync next. |
| Target004 | Candidate + sync on original DBP37 | Same loss/read0x1da00000 with activation verified and zero sync errors/warnings. No map-specific synchronization signature recovered; no repeat. |
| Target005 | Only startup gl_ubershaders=false, original capture mode | 22full pipeline creations,0library-link,0uber1 prove selector. Still loss frame8/tic18/fence12/read0x1da00000. Generalized/library/fallback path not necessary. Missing LevelMesh push shaderKey remains separate concern, not sufficient explanation. |
| Target006 | Only startup gl_levelmesh=false + readback, original backend/capture | Readback false; still loss frame7/tic18/submission13/read0x1da00000. Both NV entries confirm a startup marker in drawcmd188/submission11, **different bracket** from prior world marker. Direct LevelMesh drawing not necessary. Preparation/query/shadow mesh resources can remain active. Final16/6 STOP. |

## Fault, resource and dump analysis

Target001 EXT count/data queries both success: invalid-read0x1da00000(4096-byte precision), instruction0x200117690(16), two addresses/zero vendors,550536-byte binary. Target002 instruction0x200302ca0/read0x242400000,424860-byte binary. Target003 instruction0x20010af90/read0x1da00000,442792-byte binary. Target004 instruction0x200107290; target005 instruction0x2000ba090; target006 instruction0x20014f090/read0x1da00000,717988-byte binary. Address differences under validation cannot identify changed shader/resource by themselves. Standard vendor header identifies NVIDIA/device2187; opaque payload is retained, not decoded.

Target001 has560 CPU-prepared upload fingerprints,561 recorded copies,245 buffer descriptor targets. All copy/descriptor extents fit allocations; no trace/resource truncation. Pre-loss logged retirements follow successful fences; no demonstrated premature buffer/set destruction. These facts do not prove uploaded semantic ranges, GPU bytes/visibility, shader indices, or image descriptor generations. Pipeline **creation** inputs are recorded but are not a per-draw executed-pipeline or instruction mapping. NV checkpoints delimit stages, not offending draw.

Matching private-PDB target001 process dump catches the main thread in ErrorWindow::ExecModal / Win32DisplayWindow::RunLoop after explicit device loss. It does not provide the pre-error blocked stack. Other target pre-kill full dumps survive for offline analysis. NV and EXT retrieval happen only after loss and finish without collector deadlock. Base target reproduces without removed invalid healthy NV query; that misuse is not necessary for this current loss.

## Implemented candidate and verification limits

`VkLevelMesh::BeginFrame` existing transfer-write publication now includes VERTEX_ATTRIBUTE_READ and INDEX_READ at VERTEX_INPUT alongside shader visibility, both software traversal and AS branches. No idle, resource/lifetime/quality/default change. The test `test_levelmesh_upload_sync.py` fails the two a688 pre-fix publications and passes both candidate branches. Safe hardware sync is the independent runtime oracle. Ray-query hardware branch is not physically exercised on this GPU.

Local MSVC RelWithDebInfo build passes. Focused source and13 gate regressions pass. Broad initial local suite has12 compiler-availability errors (`c++` absent / no VS developer shell), not a green full-suite claim; subsequently11 CFX fixtures pass in the proper MSVC ASan shell. Linux CI oracle executes compiled fixtures. Required CI run36998084119 is8/8 green at97ff8a7da; final documentation head requires its own green checks. Causal crash-repair saturation has **zero successes**; issue97/75 cannot close on this candidate.

## Next discriminating action

No further physical launch under this16/6 protocol. The narrowest demonstrated blocker is a GPU invalid read during early graphics submissions, still reproduced with direct LevelMesh drawing disabled and with generalized/library pipelines disabled separately. The original runs reached the world checkpoint; target006 has a different startup-only checkpoint bracket. Copy/descriptor allocated extents and logged retirement are valid; no initiating executed shader/resource is mapped. Sync found and repaired one real independent hazard but did not clear the loss; GPUAV yielded no recoverable access violation.

Read-only post-campaign `vulkaninfo` **actually exposes** VK_EXT_device_address_binding_report rev1 / reportAddressBinding=true, and VK_NV_device_diagnostics_config rev2. These are capabilities, not enabled capture claims. Next source discriminator: opt-in bounded DEVICE_ADDRESS_BINDING debug-utils callback + supported device feature/extension, join fault read0x1da00000's4096-byte precision interval to buffer/image bind/unbind address ranges and resource identities. Add bounded executed-pipeline/draw attribution around the world stage if needed; creation-only keys are insufficient. Offline build/synthetic callback tests can proceed now. A new physical validation protocol/budget is required before any later target. Do not decode NVIDIA opaque payload without an actual supported decoder or pretend raw fault address is a Vulkan handle.
