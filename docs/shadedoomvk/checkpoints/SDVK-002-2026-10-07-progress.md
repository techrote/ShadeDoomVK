# SDVK-002 progress checkpoint — 7 October 2026

**Disposition:** implementation checkpoint preserved; **SDVK-002 / #2 remains OPEN and unaccepted**. This is not the final release or native qualification receipt. No renderer feature expansion or additional implementation is authorized by this checkpoint alone.

## Repository identity

- Repository: `techrote/ShadeDoomVK`
- Issue and canonical contract: [#2](https://github.com/techrote/ShadeDoomVK/issues/2), [SDVK-002.md](../issues/SDVK-002.md)
- Accepted source baseline: `master@a2d2d293d680895bb8daae86466596b05aaef483` (SDVK-001 acceptance integration).
- Implementation branch: `sdvk-002-renderer-observatory`.
- **Preserved implementation commit:** [`146f6f4a8718e709238c3bb48a510a02fcacde91`](https://github.com/techrote/ShadeDoomVK/commit/146f6f4a8718e709238c3bb48a510a02fcacde91), parent `a2d2d293d680895bb8daae86466596b05aaef483`.
- The compare endpoint reported one implementation commit ahead of the assessed baseline and 40 changed files. The file inventory, not this progress note, is authoritative for the actual code snapshot.
- The existing [observability contract](../SDVK-002-OBSERVABILITY.md), [renderer-oracle README](../../../tools/renderer_oracle/README.md), [RAG observability reference](../rag/11-RENDERER-OBSERVABILITY.md) and [execution ledger](../10-EXECUTION-LEDGER.md) describe the committed design and its limits.

## Preserved implementation scope

The implementation commit contains:

1. Default-off, bounded native renderer observation across frame/view/context, ordered immediate-draw material/sampler, light-query, probe/sun, shadow, resource/generation, pipeline-key and CPU/timestamp channels.
2. An explicit `sdvk-renderer-observation/v1` schema and cross-record validation with rejection tests for missing, reordered, malformed or misattributed observations.
3. Ten deterministic corpus recipes over the eight declared scene classes; seven newly authored scene generators, retained PF recipes and nineteen referenced executable CPU contracts. No original PF oracle or negative fixture is replaced.
4. Fresh-process fixed-camera preparation/capture receipts, bounded RGB8 exact/tolerant comparison, reproducible source/input provenance checks and separate state versus timing runs.
5. Raw-sample percentile/evidence aggregation, three-process repetition checks, native software-Vulkan qualification driver, CI configuration and issue/RAG/validation-contract documentation.

See the pinned commit for the executable files; this document is a handoff, not a reconstructed implementation.

## Evidence observed or reported at checkpoint

- The pre-existing SDVK-001 dependency gate was verified accepted on `master`; its evidence is in [SDVK-001 foundation](../SDVK-001-FOUNDATION.md).
- During the implementation session, the initial full CPU check reported nine errors due to missing CMake. After installing CMake in that environment, the session **reported** 665 unittest passes, CFX checks, four compiled contracts and two identical source-oracle outputs. New comparison/corpus negative controls were reported passing. These session reports are not a replacement for retained exact-source logs or PR CI; repeat the current-head command for acceptance.
- The committed implementation/ledger reports an independent negative-case review (record ordering, parent ancestry, frame coverage, material/sampler/resource identity and workload authenticity). The remote commit includes tests; native hardware success is not inferred from their presence.
- A local software Vulkan probe reported Mesa llvmpipe capabilities suitable for attempted native qualification. In that execution container, Unix socket creation failed with `EPERM`, preventing Xvfb startup. **No successful display-based renderer capture is claimed there.**
- A Linux native compile was reported started. Its finished build result and authenticated logs were not available for this checkpoint, and must not be described as passing.
- At checkpoint inspection, the GitHub branch had no pull request and no branch Actions runs. The committed software Vulkan CI lane has therefore **not** been accepted as passing.
- There are **no accepted native two-run state/image comparisons, no sealed three-process raw CPU/GPU timing baseline and no physical-GPU qualification** in this checkpoint.

## Remaining gates / safe handoff

1. Recover or inspect any original local task workspace and logs **before** cleanup. The preservation environment had no mounted checkout from the implementation session; this Git checkpoint cannot certify whether that environment held additional uncommitted modifications.
2. Run exact-source local checks/build and resolve real compiler/test errors, retaining their logs. Treat any previous completion report as historical until it is tied to identifiable artifacts.
3. Submit a PR from `sdvk-002-renderer-observatory` to `master`; run all required PR jobs. Investigate hosted llvmpipe/native-capture failures without weakening state or image policy.
4. Obtain **two independent clean native state/image captures per required workload** and compare them, plus three raw timing/counter runs under the documented workload. Preserve failed and partial attempts alongside successful ones; do not claim average-FPS-only or cross-hardware parity.
5. Make a final receipt pinning exact source/build/driver/IWAD identities, native and CPU evidence, failures, image policy, sample distributions, required CI jobs and limitations. Update the ledger and RAG if source changes.
6. Merge only after acceptance criteria and all required CI gates pass; verify the resulting `master` commit, then close #2 and mark downstream SDVK-004/006/009/014 dependency gates only when justified.

**Stop boundary:** This checkpoint records progress, not full issue completion. Do not re-run expensive physical GPU campaigns or broaden renderer feature scope merely to publish this note.
