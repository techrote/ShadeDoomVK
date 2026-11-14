# Hosted publication qualification parallelisation

Status: **Draft / HOLD — Owner review required before merge.** This is the
explicitly requested distributed software-qualification experiment stacked on
[PR #196](https://github.com/techrote/ShadeDoomVK/pull/196). It does not authorize
physical GPU execution, renderer changes or automatic native retries. The PR
conversation records the exact final source, Actions links and measured outcome.

## Starting authority and baseline

The foundation is #196 at `da017d82d74d4681164c0aac8b031bdeea0543a7`, based on
accepted `master@2cc70f33295881f73c7460364c6fa8e4e546efb3`. Its authenticated shared
runtime, native corpus, six companion modules and legacy evidence consumer are
retained. This PR must remain stacked until #196 is accepted; it must not replace
or merge the foundation independently.

The Owner superseded earlier macOS requirements: mandatory CI now contains the
two Visual Studio 2022 configurations and all three original Linux compiler
configurations. macOS Release/Debug, their dependency branch and their startup
diagnostic are removed. Historical macOS evidence remains historical evidence.
At reconnaissance `master` had no branch protection requirements and the
repository had no rulesets, so there were no externally configured macOS check
contexts to remove.

| Historical CI | Six short modules | Three shadow captures | Complete SDVK-009 | Whole workflow |
| --- | ---: | ---: | ---: | ---: |
| [#608](https://github.com/techrote/ShadeDoomVK/actions/runs/43431359571) | about 8.4 min | 71m47s | about 75.6 min | 139m51s, including initial queue |
| [#613](https://github.com/techrote/ShadeDoomVK/actions/runs/43448945635) | about 11.1 min | 124m31s | about 129.8 min | 159m03s |
| [#620](https://github.com/techrote/ShadeDoomVK/actions/runs/43506661855) | 8m41s | 72m40s | 76m36s | 106m49s |

These are different source revisions and hosts, not a repeated controlled A/B.
In #620, the run head was `da017d82` but checkout built synthetic PR merge
`7980f0cc9f1e7aa3b759c47f3b6db66e0992387a`. This workflow instead checks out the
actual PR head in every job, verifies the compiled clean commit, and binds all
workers to the same immutable runtime digest. The separate source-bundle
workflow now exports that same PR head, retaining its complete Git history and
the existing source-evidence check identity.

#620's build took 7m34s, native corpus 35m56s, publication worker 86m37s and final
aggregation 12m27s. The two macOS jobs used 4m06s and 5m13s: removing them saves
**9m19s of runner consumption on that sample**, independently of critical-path
speedup. The final archive was 47,282,436 bytes, inside a 47,823,064-byte Actions
artifact. All stored artifacts together occupied 1,527,585,889 bytes, including
large temporary corpus/publication transport archives and the runtime.

## Execution graph and scheduling

One Ubuntu 24.04 software-Vulkan build feeds five independent hosted workers:

| Worker | Exact workload | Dependency |
| --- | --- | --- |
| `corpus` | Original SDVK-008 preflight/control, complete native state/timing corpus and collision replay | Authenticated build |
| `publication` | SDVK-010, 150, 153, 158, 161 and 014, preserving their internal sequences | Authenticated build and shared authored input |
| `controls` | Original compositing control, then original shadow control | Authenticated build and immutable four-capture plan |
| `witness-1` | Original first instrumented shadow witness | Same build and plan |
| `witness-2` | Original second instrumented shadow witness | Same build and plan |

The six short modules share one worker because their 8–11 minutes are below the
corpus and shadow paths. The inexpensive compositing control shares the controls
worker. No fourth expensive shadow worker or consumer recompilation is added.
Matrix `fail-fast` remains false: a failed worker must not erase siblings' useful
evidence. The final `Linux software Vulkan | RelWithDebInfo` check keeps its
original name and requires the CPU oracle, complete Windows/Linux matrix, shared
build, every native worker, successful authenticated assembly and final archive.

Three-way shadow execution avoids putting a complete 24–42 minute control in
front of both witnesses. Applying #620's measured process durations gives about
24.5 minutes for the capture part of full concurrency versus about 48.4 minutes
for a control followed by two concurrent witnesses, excluding preparation,
validation, transfer and queueing. With concurrency the 35m56s corpus can become
the limiting worker. These are dependency-graph estimates, not new native
measurements or performance acceptance.

The initial, explicitly labelled compatibility preflight exercises separate
parallel and control-gated three-runner probe plans against one source-matched
runtime. Each plan has its own campaign and capture authorization IDs. Tiny
compositing captures establish comparable metadata and exact state/RGB plus
observed scheduling/setup overhead; they do not establish full shadow coverage.
Temporary gated probe jobs are removed before the full campaign. The required
qualification check deliberately reports `PRECHECK_ONLY` during preflight,
even when all probe comparisons pass. Only full-mode exact-head CI can qualify.

The hosted [preflight #621](https://github.com/techrote/ShadeDoomVK/actions/runs/43530238730)
at exact head `4b8e0984da7941cdeba809874a9fee68ab29d802` passed both plans, all four
cross-runner exact state/RGB comparisons, and all Windows/Linux/CPU gates. Each
packet's 135 files were independently checked against its manifest, archive
sidecar and GitHub artifact digest. Both packets report `PROBE_PASS`, with
qualification explicitly false. The six captures have distinct VM boot and
worker execution identities and use two independent campaign plans. The gated
plan includes EPYC 7763 and EPYC 9V45 hosts; the parallel plan uses EPYC 9V74.
No comparator relaxation was required.

Build readiness through completion of all three workers was **87 seconds for
parallel** and **181 seconds for control-gated**. Their aggregation jobs took
59 and 53 seconds respectively. The parallel aggregator additionally waited
155 seconds for its Windows prerequisite, which the experimental gated
aggregator did not require; final packet completion times are therefore not a
matched topology comparison. The tiny native captures took approximately
10–31 seconds, so this experiment mostly measures setup and scheduling. The
full shadow campaign remains decisive. Its complete
[source-qualified receipt](evidence/CI-PUBLICATION-PREFLIGHT-20261114.json)
records timings, identities, artifacts and the deliberate `PRECHECK_ONLY` failure.

## Explicit change to serial fail-stop semantics

`sdvk009_publication.qualify` and its original fail-stop tests remain unchanged.
It still suppresses later dependent launches after an earlier failure. The new
`sdvk009_distributed` entry points have a distinct, reviewable contract:

1. The build creates and SHA-256 seals the complete ordered plan before any
   worker launches a capture. The plan contains source/tree, executable,
   runtime archive, engine packages, historical input, prepared input, workload,
   worker allocation and unique single-use capture authorization identities.
2. Each independently authorized worker authenticates those identities and the
   explicit hosted lavapipe guard before its native preflight. It writes a
   failure-default prospective receipt and exclusive capture launch records.
3. Controls retain local fail-stop order: compositing must pass before shadow
   control starts. Witness workers may already be running when another worker
   fails. This is the deliberately changed temporal property requiring Owner
   approval; it is never described as preserving global serial fail-stop.
4. Every worker must finish exactly its registered captures. Each capture keeps
   the original fresh process directory/application cache, mode, diagnostics,
   640×480 extent, **120 warmup frames, one retained frame, 3600-second deadline,
   exact RGB policy and zero retries**.
5. The CPU aggregator authenticates every complete worker before moving any
   capture. It then runs the original independent witness validation, both
   control/witness comparisons, witness-repeat comparison and all nine original
   negative controls for each witness. Any failure or missing evidence fails
   qualification. A sibling success cannot repair another worker's failure.

SIGTERM/interruption leaves a failed or cancelled worker receipt and partial
inventory when the process has an opportunity to finish. Actions uses `always()`
for packing/upload and retains original per-worker artifacts even if aggregation
fails. A hard runner loss may prevent an upload; absence is rejected, never
treated as a pass or replaced by an automatic retry.

## Cross-runner identity and independence

The existing comparisons are called without relaxed policy or additional
normalization. `run.comparable_build` already excludes only the fresh cache path;
it preserves backend, renderer, Vulkan device/capabilities and other build
identity. Runtime executable/package hashes and reproduction settings remain
exact. CPU model is recorded for latency interpretation, not silently added to
or removed from the renderer oracle.

#620 already used different CPU models (EPYC 7763 for corpus, EPYC 9V74 for
publication) with the same llvmpipe LLVM 20.1.2 device and Mesa 25.2.8 package.
That observation motivates the preflight; it does not substitute for the actual
cross-runner exact comparisons.

Distinct Linux VM boot identities, worker execution UUIDs, request hashes,
original process working directories and publication diagnostic run IDs are
required. Runner display names remain descriptive, not a uniqueness assumption.
The aggregator verifies capture names/order, exactly one authorized request,
receipt/run equality and worker provenance. Renaming a copied packet cannot
supply an independent repetition. Mismatched source, runtime, device or plan
fails before qualification.

## Evidence transport and consumer compatibility

The shared runtime is built once. Runtime and authored-input archive SHA-256
values and the plan SHA-256 are passed directly from build job outputs and
checked by consumers, in addition to retained sidecars. Historical Freedoom
0.13.0 content is fetched and authenticated once; controls retain that shared
input and plan in the final evidence.

Each worker transports a bounded namespace, source/runtime/plan/workflow
identity, explicit job status, raw process receipts/captures/diagnostics, and
complete SHA-256 file manifest. Download namespaces remain separate until
verification. Unknown, duplicated, cross-wired, incomplete or corrupt artifacts
cannot be silently overwritten by download merging.

Assembly moves authenticated capture files to the original
`renderer-sdvk009-publication/captures/<name>` paths. It retains worker launch
and native receipts under `distributed-workers`, restores original step aliases
and prepared/provenance paths, and journals the original-to-final path mapping
with byte counts and SHA-256 values. Raw captures are not duplicated. Final
sealing verifies that every transported file survived unchanged at its original
or explicitly mapped location, then inventories added comparison reports.

The consumer remains `renderer-software-vulkan` containing
`renderer-software-vulkan.tar.xz`, its SHA-256 sidecar and complete manifest,
with 30-day retention. Standard tar/XZ consumers read the original capture
layout. Failed comparisons still receive a lossless final archive when input
restoration succeeds; an invalid transport remains in its original worker
artifact and cannot acquire a successful final manifest.

Final verification streams external `xz -dc` into the existing tar-member
size/type/path/SHA-256 checks and also checks the decompressor CRC exit status
and trailing tar bytes. This avoids Python's costly compressed-stream buffering
without reducing integrity checks. A read-only replay of the original #620
archive verified all **2,923 files in 12.455 seconds** in the coding environment.
Compression, extraction, verification, transfer, archive size and host identity
are recorded separately; no combined step duration is mislabeled as pure
compression. The [bounded retained-byte experiment](evidence/CI-PUBLICATION-COMPRESSION-20261113.json)
reproduced the original single-block archive exactly in 1090.267 seconds. The
tested `xz -6 -T3 --block-size=512MiB --lzma2=dict=64MiB` produced identical
decoded tar bytes in 419.641 seconds, at 87,495,836 compressed bytes. That is a
one-off local packaging comparison with overlapping CPU work, not a repeatable
hosted speedup claim. The size trade is +40,213,400 bytes (+85.05%), well below the
893 MB regression, while preserving strong lossless compression.

The helper selects this measured three-thread recipe only with at least 12 GiB
effective memory and three effective processors, and enforces a 7 GiB XZ memory
cap with `--no-adjust`. It records physical/cgroup memory and CPU limits. Smaller
or unknown-memory hosts retain the original single-thread 64 MiB dictionary,
with a 1 GiB cap. There is no retry or automatic dictionary reduction. The full
hosted campaign, not the local benchmark, supplies the final workflow timing.

## Qualification and merge decision

CPU tests cover the immutable plan, original workload, authorized exactly-once
execution, source/runtime mismatch, distinct requests/runners, corrupted and
reordered evidence, cancellation, partial retention, all original comparison
calls and negative controls, path relocation and standard archive consumption.
Workflow tests expand the bounded matrix, preserve Windows/Linux checks and
enforce final dependencies. The original serial tests continue to apply to the
serial API.

The initial hosted compatibility result must pass before the complete expensive
campaign is enabled. Full exact-head CI then runs all Windows/Linux, CPU and
native gates without a repeated benchmark campaign. Native failures must be
retained, diagnosed and repaired; changed source must be requalified. Final
measurements must distinguish source changes, host variation, actual overlap,
queueing, packaging and macOS runner consumption.

Even a successful exact-head campaign leaves this PR **Draft/HOLD**. Owner
review must explicitly accept the independent-sibling launch semantics and the
stacked dependency on #196 before any merge. No physical GPU correctness,
physical performance, historical fault resolution or repeatable speedup is
awarded by this work.
