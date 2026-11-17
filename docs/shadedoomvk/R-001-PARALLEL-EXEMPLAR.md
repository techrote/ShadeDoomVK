# R-001 parallel CI exemplar — source-matched single build, independent native suites

**Status:** experimental, opt-in reference; *not* a replacement for Pro's [#211](https://github.com/techrote/ShadeDoomVK/pull/211), not an approved new required CI check and not a performance claim.

**Workflow:** [`reference_parallel_r001.yml`](../../.github/workflows/reference_parallel_r001.yml)  
**Related:** [R-001 #203](https://github.com/techrote/ShadeDoomVK/issues/203), [SHADOW-001 #204](https://github.com/techrote/ShadeDoomVK/issues/204), [legacy shared-build #196](https://github.com/techrote/ShadeDoomVK/pull/196) and the old publication-sharding [#201](https://github.com/techrote/ShadeDoomVK/pull/201).  
**Review base:** `impl/r-001-ci-lanes-20261115@9d0b0ebf8a4518974e45d62af43b1f5d1798c84c`.

## 1. Source-grounded audit of Pro's active workflow

The 15 November #211 workflow is a substantial improvement: it retains nine familiar check names, changes the unconditional historical publication into four source-matched native smoke captures, routes relevant Lane B tests, and preserves deep publication separately as an explicit dispatch. Its routing and safety/negative controls are meaningful.

However, the **schedule topology** still has avoidable serial work:

| #211 condition | Latency consequence | Exemplar/production opportunity |
| --- | --- | --- |
| `build: needs: pf_oracle` | All eight platform builds wait for the entire CPU oracle, despite no dependency on its output except route selection. | Split cheap **route** and heavyweight **CPU**. Start compilation alongside CPU after route is known, or concurrently if route-independent. Retain CPU as a mandatory final gate. |
| Native build and all Lane A/B tests share one matrix job | Renderer compilation must finish before native tests; all selected native suites then run one after another on the same worker. | Build native renderer **once** and fan it out to independent hosted suites on separate runners. |
| Every native test series shares one evidence/packaging step | A slow suite holds up completion of unrelated suites and the final archive. | Emit small, per-suite receipts; aggregate only after independent completion. |
| Eight build matrix configurations are mandatory on every PR | Paid runner occupancy even for narrow changes; compilation remains a significant wall-clock component. | Retain stable required status checks until deliberate governance change; measure whether full platform matrix should be release/deep while preserving fast compatibility signals. |
| Exact old publication research available separately | Good preservation, but its complexity should not return through the new routine gate. | Keep nonqualifying deep tests separate and clearly labelled. |

**Measurement boundary:** #211 and #212 CI were still running at the initial audit. No successful speedup, runner cost saving, or total latency estimate is claimed from an incomplete cohort.

## 2. Exemplar DAG

```text
               exact source head / hosted-only
                  ┌────────────────────┐
             ┌────│ CPU + source checks│──────────────┐
             │    └────────────────────┘              │
             │                                        ▼
             │                               Final truthful gate
             │                                        ▲
             │    ┌────────────────────┐              │
             └────│ One native build   │              │
                  │ SHA + tree + pack  │              │
                  └────────┬───────────┘              │
                ┌──────────┼──────────┐               │
                ▼          ▼          ▼               │
             Routine    Actors     Resources ─────────┘
             captures   /sunlight  /lifetime
```

CPU and compilation can overlap. The one authenticated renderer package is reused by three independent native runner jobs. The final **EXAMPLE | Complete parallel result** refuses an overall PASS if CPU, build or any native matrix child fails, is skipped or is cancelled.

The workflow uses **GitHub-hosted Ubuntu** with explicit llvmpipe/ICD identity, no dedicated physical GPU, no repository secrets, no external artifact downloads, and no `pull_request_target`.

## 3. Source and evidence ownership

- The GitHub event SHA is checked against `git rev-parse HEAD` in every producer/consumer.
- Shared runtime is the repository-proven packaging subset from #196: `vkdoom`, `vktool`, CMake cache, ZMusic libraries and relevant runtime resource packs.
- Runtime tar.gz has a SHA-256 sidecar and contains explicit `COMMIT` and `TREE` pins. Consumers verify archive digest, source/tree and original `check_build_identity.py`.
- Each suite runs in a **fresh job**, with its own current-source Git checkout and distinct output. No cross-suite state or synthetic “all PASS” merging.
- The usual native oracle remains responsible for rejecting incorrect input, unsupported Vulkan devices and resource/scene claims.
- Suite receipt artifacts are small JSON files, with an internal SHA-256 inventory. The shared runtime is retained for one day and summary evidence for three days. Failure receipts are not relabelled.
- No full 121-frame shadow publication process, repeated benchmark, or historical physical-fault reproducer is invoked.

### Tradeoffs and measured question

The native fanout requires more concurrent runners and independent apt/runtime setup than the serial lane. It is intended to reduce **critical path latency**, not necessarily total runner-minutes or storage. A source-matched valid-run A/B comparison is required before claiming a win.

The reference has a deliberately static three-way matrix. For adoption in #211, **generate the native matrix from the existing fail-closed `tools/ci/route.py` gate** so only truly relevant suites run. Never let a file-path omission silently drop safety checks. Keep the one runtime build shared across selected suites.

## 4. Invocation and safety

The file includes two triggers:

- `push` limited to the dedicated `ci/reference-parallel-r001-20261115` branch **and changes to this workflow file**. This is a bounded branch-only demonstration, not a mainline CI trigger.
- `workflow_dispatch` for later deliberate invocation. GitHub generally requires the workflow to be present on the default branch before UI dispatch is available. Do not merge merely to expose that button; use a controlled branch push for this proof.

A run of this reference **does not satisfy** any of the nine established normal CI checks. It cannot silently replace the required `Linux software Vulkan | RelWithDebInfo` context. Those names and the current R-001 selection policy remain untouched.

This reference is stacked on Pro's implementation branch so its helpers exist. The Draft PR should target `impl/r-001-ci-lanes-20261115`, **not master**. Copy the workflow stages into Pro's own implementation only after checking results and any changes Pro has made.

The new physically safe llvmpipe workflow is **not** authorisation to use a GTX 1650 SUPER, Quadro P400 or other physical GPU. The existing physical STOP remains active.

## 5. Suggested Pro integration sequence

1. Let the independent #211 and #212 qualifications finish; inspect complete timings and failures.
2. Compare actual job graph times: CPU delay before builds, native build cost, Lane A capture time and targeted 010/150/153/158/161/014 groups.
3. If this exemplar passes, extract the **three structural improvements**: CPU/build overlap, single verified runtime, independent native fanout; keep R-001's routing and safety logic authoritative.
4. Preserve check identity through a final aggregation job. When any required lane is missing/failed, the status must fail, not skip green.
5. Time both topologies on equivalent source and inputs. Record end-to-end wall time **and** total runner-minutes/artifact bytes. No speedup claim from red/incomplete runs.
6. Retain the exemplar Draft PR as a reference; do not merge it as a second production workflow or duplicate the routine CI indefinitely.

## 6. Targeted review questions

- Does R-001's actual route select the actor, material, portal and resource suites on Pro's changed paths, including the new shadow receiver path?
- Can a valid but slow suite run concurrently with others without breaking shared source invariants?
- Do the archive SHA, built executable identity and runtime asset source agree for each independent job?
- Do every missing/failed/cancelled/skipped job and any corrupt artifact cause the *final* required status to fail?
- Are the hosted driver guards and physical STOP preserved?
- Can the production policy avoid triggering full eight-build matrix compilation for a pure docs change without losing platform compatibility confidence?

**Reference success is a demonstrated workflow DAG, not an automatic merge recommendation.**
