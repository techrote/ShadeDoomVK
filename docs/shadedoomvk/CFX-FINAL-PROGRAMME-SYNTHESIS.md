# CFX-000 final programme synthesis

Parent: #75  
Synthesis base: `master@844462c3a4ed5f7037ade1b49d1a28f578077213`  
Accepted primary repair: PR #104 / `d0789c88f88049116022e7b904026cddeaba8ac4`  
Accepted cross-case qualification: PR #106 / `2399d9455772c570e597a5960c626f3bf771baeb`

## Disposition

The accumulated CFX-001 through CFX-010 evidence satisfies the six completion criteria in #75 without requiring a single common cause for every historical incident.

The demonstrated primary result is narrower and stronger than the programme's earlier generic "driver crash" framing:

- DBP37 MAP01 repeatedly produced application-observed `VK_ERROR_DEVICE_LOST` on the GTX 1650 SUPER, with the recurring read-fault interval overlapping the retired startup lightmap allocation.
- A matched lifetime discriminator succeeded with replacement-atlas retention enabled and restored the failure with retention disabled.
- The retained production repair does **not** retain old atlases. It republishes persistent initialized correctly typed neutral light/probe views into previously published reserved slots that are removed by atlas shrink, before submission and ordinary fence-controlled destruction of the old atlas owner.
- Safe capture, separate core validation and separate synchronization validation passed for the candidate.
- Three independent exact formerly failing DBP37 MAP01 processes completed normally with diagnostic retention OFF and normal startup-atlas retirement.
- The original DBP50 MAP08 route, separately hashed DBP50 v1.2 MAP08 route, and reconstructed Sunlust MAP24 + Champions movement/filter/reload route each subsequently completed three independent qualifying processes on the accepted repaired renderer. CFX-010 used 17 processes total (five controls and twelve targets) with zero new device-loss/TDR events.

This establishes a bounded renderer compatibility repair and strong practical coverage. It does **not** establish the unique executing shader/SASS instruction, an illegal dynamic descriptor access, identical submitted GPU bytes between historical and repaired runs, a unique NVIDIA defect, isolated PR #104 attribution for every later success, or one shared cause for all historical incidents.

No new physical GPU run was performed for this synthesis. All historical STOP files, loss ceilings, saturation guards and raw classifications remain evidence.

## Final incident matrix

The machine-readable form is [evidence/cfx-final-incident-matrix.json](evidence/cfx-final-incident-matrix.json).

| Incident / route | Historical evidence | Relationship to accepted repair | Repaired-build coverage | Final disposition | Residual uncertainty / PF-020 impact |
|---|---|---|---|---|---|
| CFX-DBP37-MAP01-20260924 | GTX 1650 SUPER; historical 153/141 evidence. Later CFX-003/005/007/009 captures repeatedly returned device loss near frame 7; complete CFX-009 address capture joined the read interval to the startup 8 MiB lightmap retired at frame 6. | Matched retention ON succeeded; matched OFF restored the failure. PR #104 removes the stale removed-slot target state while preserving ordinary retirement. | **3/3 exact former-reproducer successes**, retention OFF; capture/core/sync safe controls pass. | **demonstrated repaired primary reproducer** | Executing shader/SASS, actual illegal dynamic access and exact submitted GPU bytes remain unproven. This limitation does not leave the demonstrated stale reserved-target state in current source. |
| CFX-DBP50-20260920-MAP08 | Original DBP50 route; application device-loss secondary record, NVIDIA 153 and WER 141; exact initiating command unknown. | Repaired renderer exhibits neutral removed-slot publication before normal atlas retirement, but historical shared causation is not proved. | Original DBP50 route **3/3 qualified** in CFX-010. | **repaired-build qualified historical route; historical cause unresolved** | Historical skill/seed/cache/layer details are incomplete. No current CFX blocker to PF freeze from this reconstructed route. |
| CFX-DBP50-20260923-1824 | Same original WAD family; NVIDIA 153 + WER 141; surviving 0x141 WATCHDOG dump strongly correlated with `vkdoom.exe`, initiating command unknown. | Same bounded relationship as the original DBP50 route; do not equate the historical dump with DBP37 causality. | Covered by the selected original DBP50 MAP08 reconstruction, **3/3 qualified**. | **repaired-build qualified historical route; historical cause unresolved** | Strong historical incident identity, incomplete initiating GPU identity. |
| CFX-DBP50-20260923-2259 | Same original WAD family; watchdog + NVIDIA 153 + WER 141, no retained application device-loss text. | Same bounded route-level qualification; no unique historical mechanism assigned. | Covered by original DBP50 MAP08 reconstruction, **3/3 qualified**. | **repaired-build qualified historical route; historical cause unresolved** | Historical application-side failure identity is weaker than the 18:24 case. |
| CFX-DBP50-V12-20260924-1309 | Separate hashed v1.2 MAP08 content; watchdog, NVIDIA 153 and WER 141; no retained application device-loss string. | Removed-slot neutral publication is present on repaired runs; common cause with original DBP50 or DBP37 is not proved. | Separate v1.2 route **3/3 qualified** from four target attempts; one pre-frame host abort excluded. | **repaired-build qualified historical route; historical cause unresolved** | Historical skill/seed and some runtime-state identity are unavailable. |
| CFX-SUNLUST-MAP24-20260924 | Freedoom2 + Sunlust + Champions, UV skill 3, seed 12345; phase-1 image plus partial phase-2 CPU trace, NVIDIA 153; no retained application device-loss text or matching dump. | Repaired runs show neutral publication and ordinary retirement, but historical unique activation and shared causation are unproved. | Full movement/turn/filter/reload route **3/3 qualified**; two host/capture-confounded observations excluded. | **repaired-build qualified historical route; historical cause unresolved** | Historical executable/diagnostic patch and cache/layer state differ from current accepted renderer. |
| CFX-MAP04-CAPDIAG-20260924 | Test-only MAP04 diagnostic watchdog with no new driver event; later paired run clean. | No evidence ties this timeout control to descriptor retirement or a GPU reset. | No repair replay required for the parent disposition. | **non-driver timeout/control; distinct/non-equivalent incident** | Retained as negative control; no PF-020 crash blocker. |
| CFX-DBP37-P400-CFX005 | Quadro P400 / 582.78: two cross-adapter and one verified native-output DBP37 target returned device loss; first two reported invalid-write/execute signatures materially different from GTX invalid-read signature, native run lacked fault payload. | Historical P400 failures predate PR #104 qualification and cannot be assigned to the accepted mechanism. | **No repaired-build P400 physical qualification was performed.** The P400 lane exhausted its three-loss cap and is stopped. | **distinct/non-equivalent incident; historical cause unresolved; documented residual limitation** | Repaired P400 behavior is unknown. This is not evidence of a current known failing repaired path and does not justify reopening saturated physical testing for #75. PF-020 must preserve the limitation rather than claim cross-GPU proof. |

The CFX-010 exclusions remain exclusions, not failures or successes: the missing deferred Sunlust screenshot, the focus/pause/watchdog race with an unreadable empty dump, and the pre-frame DBP50 v1.2 host foreground abort.

## Primary DBP37 evidence boundary

The accepted CFX-009 result demonstrates a compatibility repair around removed reserved atlas descriptor targets.

What is established:

- the original and matched retirement-OFF cases fail after the startup lightmap interval is retired;
- the matched retention-ON discriminator succeeds through the former failure window;
- source review shows removed reserved slots could continue naming views whose owners are subsequently destroyed;
- PR #104 republishes persistent initialized typed neutral targets into those removed slots before submission;
- the old atlas is still destroyed normally after its fence-controlled lifetime;
- the repaired candidate passes safe output/state controls, separately activated core and synchronization validation, focused CPU/ASan regressions and three exact former reproducer trials.

What remains deliberately unclaimed:

- which shader/SASS instruction executed at the fault;
- that a particular shader dynamically accessed an invalid descriptor;
- that CPU-visible or uploaded state was byte-identical across historical and repaired executions;
- that Vulkan `PARTIALLY_BOUND` was violated merely because an unused descriptor target became undefined;
- that NVIDIA's driver was uniquely defective.

The repair therefore stands on demonstrated compatibility behavior and source lifetime hygiene, not on a stronger unsupported claim.

## Cross-case and P400 interpretation

CFX-010 gives strong current practical coverage for the three selected reconstructed historical routes. Those successful routes contain the accepted neutral publication before ordinary old-atlas retirement, but multiple historical variables differ from the original failures. A later success cannot recover missing historical cache/layer state or prove that PR #104 alone caused every outcome.

P400 is intentionally different. CFX-005 established that a compatible second GPU/driver also lost the device on the DBP37 workload, including a verified native-output replay, but its reported signatures differed and causal attribution remained inconclusive. The old P400 lane then exhausted its permitted three loss episodes. CFX-010 did not qualify the repaired build on P400.

For #75, this is a bounded residual limitation rather than a reason to reopen physical testing: the parent contract permits an incident to remain unresolved with a precise evidence-backed blocker, and the primary/current supported-path repair is independently demonstrated on the acceptance GTX 1650 SUPER. PF-020 must not turn that into a claim of repaired P400 coverage.

## Failed, negative and superseded hypotheses

| Hypothesis / path | Final status | Evidence-backed interpretation |
|---|---|---|
| Present-semaphore reuse | **separate correctness defect** | Found by validation and repaired independently. No evidence established it as the DBP37 cause. |
| Mipmap transfer synchronization | **separate correctness defect** | Found and repaired independently; not sufficient to remove DBP37 failure. |
| Swapchain-clear dependency | **separate correctness defect** | Correctness finding retained independently from the crash mechanism. |
| Hardware-buffer transfer dependency | **separate correctness defect** | Correct publication scope was repaired; not established as the historical crash cause. |
| LevelMesh upload INDEX_READ dependency | **separate correctness defect; crash causation refuted as sufficient** | CFX-007 safe validation localized and fixed it; DBP37 still failed. Direct-LevelMesh-off and generalized/specialized pipeline tests also prevented a universal LevelMesh-required explanation. |
| LevelMesh/index/tree corruption | **unsupported as primary cause** | Six matching-PDB post-error CPU snapshots pass logical bounds/tree/finite checks; pending traversal stack peaks at 18/64. Post-error CPU state still cannot prove submitted GPU bytes. |
| Zero-index unused-capacity interpretation | **disproven for active CPU geometry** | The zero-index tail is unused capacity and all active indices remain below it; this does not prove GPU-visible bytes. |
| Malformed cached SPIR-V structure | **unsupported** | All 138 logged historical cache-hit modules pass `spirv-val` for the source target. Structural validity does not prove dynamic descriptor correctness or executed instruction identity. |
| Ordinary lightmap guard hoisting/removal | **weakened / unsupported** | Cached fragment modules retain recognized lightmap access under the immediate index guard; executed shader/SASS remains unidentified. |
| Diagnostic retained-atlas lifetime | **superseded diagnostic hypothesis** | Retention ON was a useful discriminator, not the production repair. Accepted source restores ordinary retirement and republishes removed descriptors to neutral live targets. |
| CFX-008 synchronous address logger | **contributory diagnostic defect** | Safe activation dropped 237 callback records and correctly stopped before the target. PR #100 replaced it with the bounded queued collector; this was measurement infrastructure, not a renderer repair. |
| Healthy-frame NV checkpoint retrieval | **contributory diagnostic defect** | CFX-006 removed a query path that was invalid outside device loss. Historical DBP37 predates it and later crash reproduction persisted. |
| Fault-address/resource overlap alone | **insufficient causal proof** | CFX-009 maps the read precision interval to the retired startup lightmap allocation, but address aliases/reuse and lack of executed-shader identity prevent stronger inference. |
| Valid-but-excessive workload/TDR | **unsupported as universal explanation** | Historical DBP50 failures occurred under low-resolution/capped conditions; the accepted repair succeeds on exact uncapped DBP37 and reconstructed routes without introducing a cap. |
| Unique NVIDIA driver defect | **not established** | NVIDIA event/dump buckets and cross-GPU device loss are observations. Application-side lifetime state was repaired, P400 signatures differ, and no minimized vendor-grade driver defect is demonstrated. |

Negative evidence remains part of the accepted record; the final repair does not rewrite earlier dead ends as if they had pointed inevitably to the result.

## Parent #75 acceptance audit

| #75 criterion | Result | Evidence |
|---|---|---|
| 1. Every known incident family has an explicit disposition | **PASS** | The matrix above covers all seven CFX-001 incident IDs plus the material CFX-005 P400 comparison. Unresolved historical cause is explicit where proof is unavailable. |
| 2. At least one primary incident has root-cause proof or the strongest practical evidence boundary | **PASS** | DBP37 has repeated exact failures, complete address localization, matched retention ON/OFF discrimination, a source-level removed-target repair, safe validation, and 3/3 exact repaired successes. Claims beyond that boundary remain excluded. |
| 3. Any retained repair has a pre-fix regression/invariant and successful-path coverage | **PASS** | The lightmap publication fixture/source-contract tests exercise one-to-zero retirement, typed fallback publication, reservation bounds and publication-before-submit/fence-before-release. Safe controls and 3/3 exact targets cover successful behavior. |
| 4. Original physical failure is rechecked when safe/necessary, or blocked confirmation is stated | **PASS** | The primary DBP37 former reproducer is rechecked 3/3 on the accepted candidate. CFX-010 supplies 3/3 repaired-build coverage for each selected DBP50/Sunlust route. Repaired P400 coverage is explicitly absent and its old three-loss lane is saturated; no new physical evidence is authorized by this synthesis. |
| 5. Failed/negative approaches are preserved | **PASS** | CFX-001 through CFX-010 reports and machine evidence retain validation defects, LevelMesh negatives, SPIR-V checks, address-capture failure, excluded host/capture observations, stopped campaigns and STOP identities. |
| 6. PF-020 impact is explicit | **PASS** | The handoff below and the reconciled PF-020 contract state exactly what is fixed, what remains uncertain and what does or does not block the PF freeze. |

The synthesis therefore supports closure of #75 after this documentation/evidence change passes its own required non-GPU CI, independent review, merge and master verification.

## PF-020 handoff

PF-020 should consume the CFX result as follows:

- **Accepted production correctness state:** previously published reserved light/probe atlas slots removed by shrink are republished to persistent initialized correctly typed neutral views before submission; normal fence-controlled atlas retirement remains active.
- **Primary physical proof:** exact formerly failing DBP37 MAP01 completes 3/3 on GTX 1650 SUPER with retention OFF; safe capture/core/sync controls and focused regressions pass.
- **Historical route coverage:** original DBP50 MAP08, separate v1.2 MAP08 and the reconstructed Sunlust/Champions full route each qualify 3/3 on the repaired renderer.
- **Remaining uncertainty:** common historical causation, unique executing shader/SASS, illegal dynamic descriptor access, exact historical GPU bytes and repaired P400 behavior are not established.
- **PF correctness implication:** the demonstrated stale removed-slot target state is repaired in current source. No accepted CFX evidence currently demonstrates a reproducible crash/corrupt identity remaining on the repaired GTX supported path. CFX therefore does not remain an independent blocker to beginning PF-020 once PF-019 and every other PF dependency are genuinely complete.
- **PF-020 obligation:** independently exercise the final merged source and the applicable descriptor/lightmap/probe lifetime regressions as part of the freeze. CFX evidence does not waive PF-020's own fail-closed resource/identity criteria.
- **Retained infrastructure:** CFX capture/classifier/address tooling, immutable STOP/saturation guards, reports and evidence remain historical/operational diagnostics. They are not permission to restart saturated physical campaigns.
- **P400/vendor limitation:** lack of repaired-build P400 qualification and absence of a proven NVIDIA defect are maintenance/evidence limitations, not a currently demonstrated PF correctness failure. Record them in the freeze manifest; do not silently promote them to proof.

PF-020 remains open and is not accepted by this synthesis. PF-019 remains separate.

## NVIDIA / #103 disposition

The accepted record does not establish a defensible unique NVIDIA-driver defect. NVIDIA 153/141 records, driver-bucket dumps and EXT fault reports document where failures surfaced; they do not by themselves assign responsibility. The accepted application-side descriptor-target compatibility repair further narrows what can responsibly be claimed.

Accordingly, #103 remains downstream of its own entry gate and owner decision. This synthesis does not prepare or submit a vendor package and does not decide submission on the owner's behalf. If future independent evidence establishes a vendor-grade defect, #103 can be reassessed without reopening or rewriting the completed CFX evidence.

## Verification and evidence integrity

This synthesis introduces no renderer behavior and performs no physical GPU work. Applicable verification is non-physical:

- complete Python/PF oracle discovery through required CI;
- CFX failure-classifier, capture, address, CFX-009 publication and CFX-010 gate regressions;
- final matrix/schema and source/document consistency tests;
- deterministic PF oracle jobs and compiled fixtures exercised by the repository workflow;
- cross-platform required build jobs;
- review of accepted issue/PR/CI receipts and checked-in machine-readable evidence.

Historical physical facts come only from already accepted CFX evidence. CI does not create a physical-behavior claim.

The CFX physical record is saturated and immutable for this programme disposition. Further hardware testing requires a separately justified future task and must not delete, weaken, reset or reinterpret historical STOP files or loss budgets.
