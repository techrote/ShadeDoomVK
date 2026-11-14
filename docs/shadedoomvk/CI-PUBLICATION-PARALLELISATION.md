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
| `publication` | SDVK-010, 150, 153, 158, 161 and 014 in their original sequences, then the original inexpensive compositing control | Authenticated build and shared authored input/plan |
| `controls` | One bounded routing probe, then only its allocated original shadow roles | Authenticated build, immutable plan and complete three-probe barrier |
| `witness-1` | One bounded routing probe, then only its allocated original shadow roles | Same build, plan and barrier |
| `witness-2` | One bounded routing probe, then only its allocated original shadow roles | Same build, plan and barrier |

The six short modules share one worker because their 8–11 minutes are below the
corpus and shadow paths. The inexpensive compositing control now shares that
short-module worker. The three shadow hosts first collect explicitly nonqualifying
five-warmup/one-frame/180-second probes from the original historical shadow scene.
All three packets must arrive and validate. Original exact comparisons select
compatible hosts, and an immutable placement rule assigns the three original
full shadow roles exactly once across them. Three compatible hosts give one
capture each, two give two plus one, and a singleton gives three sequential
captures. No fourth expensive shadow worker, consumer recompilation, replacement
host or post-failure reassignment is added. The barrier and its limits are
described below.
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

The initial, explicitly labelled compatibility preflight exercised separate
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
full shadow campaign remains decisive. The preflight's complete
[source-qualified receipt](evidence/CI-PUBLICATION-PREFLIGHT-20261114.json)
records timings, identities, artifacts and the deliberate `PRECHECK_ONLY` failure.

## Full-campaign failure and startup-history investigation

[Full CI #622](https://github.com/techrote/ShadeDoomVK/actions/runs/43532176029)
at `c99a20f36733d3b198f2bbebf8e61130fd2511bf` passed all twelve upstream jobs,
including the complete original corpus, six companion modules and four original
captures. Authenticated restoration passed, but the unchanged control/witness
state comparison failed closed. Both witnesses had two `SDVFL` material resource
generations and renderer-owner `texture_epoch` equal to 3, against 4 in the
control. These three protected fields are not normalized or exempted.

All three shadow RGB comparisons were exact, with zero changed pixels. The two
witnesses also matched each other's exact state. Control and witness 2 shared
EPYC 7763 CPUs; witness 1 used EPYC 9V74. CPU model mismatch alone therefore does
not explain the rejection. All three original #620 shadows match #622's
control state exactly. The original corpus's 56 native processes and ordered
83-step sequence also matched #620, although its new Xeon 6975P-C host was much
faster than #620's EPYC 7763. That speed difference is not credited to scheduling.

The failed packet retains every raw byte: 2,956 transported files, 1,069
relocations, 2,969 final files, an 88,029,068-byte XZ and 89,141,135-byte Actions
ZIP. Its archive SHA-256 is
`a6c502bdfd0628a8899ad40a38985534a48804f075f0a0adb1fe22a28ea9feed`.
Independent ZIP, XZ, file-hash, relocation and ordinary tar checks passed;
qualification remains FAIL. The main workflow took 61m09s to retain that failed
result, not to achieve qualification. Compression took 330.277s and full archive
verification 10.339s on the hosted runner. See the complete
[failure investigation receipt](evidence/CI-PUBLICATION-FAILURE-20261114.json).

The initial topology gave shadow-control a preceding compositing process, while
both independent witnesses were their hosts' first renderer captures. Their
fresh application caches are proven; the unchanged reproduction policy records
external driver cache as uncontrolled. This is evidence of a startup-history
asymmetry, not proof of a particular Mesa cache mechanism. The first repair candidate
moved compositing to the existing short-module worker so all three shadows are
first-use processes on fresh hosts, without extra full captures or changed
acceptance. The historical four-capture plan order is still immutable even
though execution times overlap.

Before another full campaign, `--shadow-startup-probe` registered a distinct
nonqualifying plan. Three independent workers first collect uninstrumented
shadow captures with five warmup frames, one retained frame and a 180-second
ceiling. The controls probe then performs a 120-warmup compositing primer and
another five-warmup shadow. Original exact comparisons test the three first-use
shadows; a separate original comparison records the cold/warm history effect.
All probe names, workload identities and authorizations are explicitly labelled.
Only `PROBE_PASS` is possible, with `qualification_awarded=false`, and the legacy
required check still rejects it as `PRECHECK_ONLY`.

The short probe does not weaken or parameterize publication witness validation.
The original instrumented validator requires all 121 observer frames and remains
unchanged; a new full exact-head campaign must supply those complete witnesses,
all eighteen negative-control outcomes, and both exact control comparisons.
The probe diagnoses startup state and cannot substitute for full qualification.
Any failed-assembly timing report is now retained after successful transport
restoration, with incomplete/failed status preserved.

During #622, accepted master advanced to
`0ecba708e283e33c381fae329ace7a2cedc6a3f3` by merging independent PR #199.
The stacked #196 foundation stayed unchanged. This candidate does not import
that tolerance change; SDVK-161 passed its original checks in #622. The PR
conversation records the latest source relationship and eventual qualification.

## Protected cross-host mismatch and bounded placement

The [startup diagnostic #624](https://github.com/techrote/ShadeDoomVK/actions/runs/43540127826)
at `d90410b5f014832e4592fd1d2ac4208784dad439` failed the original exact comparison.
All three cold shadows had material generations and texture epoch equal to 3.
On the Intel controls host, cold shadow followed by compositing and another
shadow changed only those three fields to 4. This reproduces startup-history
asymmetry without proving a specific driver-cache mechanism.

The Intel control and Intel witness 2 agreed with each other. The AMD witness
had a separate protected mismatch: `light_wall_rendered` was 672 versus 731,
normal/used light records were 3279 versus 3338, and uploaded bytes were 262464
versus 267184. All exact RGB comparisons passed. These counters describe actual
selected and uploaded lights; they reset each frame and cannot be discarded as
cumulative timing telemetry. The complete 175-file failure packet was retained
and independently authenticated. The run also had a separate Windows CPU-test
failure and the expected `PRECHECK_ONLY` failure. It was not a passing probe. The [complete investigation receipt](evidence/CI-PUBLICATION-COHORT-INVESTIGATION-20261114.json)
binds its source bundle, runtime, raw packet, exact comparisons, historical
observations and job/artifact accounting.

Historical corpus captures show the same AMD/Intel counter split at one warmup
frame, with the same authored scene/config/script hashes. The corpus uses a
different IWAD, so these are supporting diagnostics, not interchangeable
qualification. AMD publication evidence retains the lower counts at 120 warmup
frames on EPYC 7763, 9V74 and 9V45. Bounded inspection found no completed Intel
120-frame publication packet. The five-frame reduction alone does not explain
this repeated per-frame split.

Disassembly of the authenticated #624 executable confirms `rsqrtss` followed by
Newton refinement in `HWWall::SetupLights`, corresponding to its existing
fast-math wall-normal calculation. Strict radius and side tests consume that
normal before accepting light records. [GCC documents this transformation](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/x86-Options.html#index-mrecip).
The actual fixture contains lights on an exact radius boundary, where a
one-ULP normal difference can change a strict comparison. This is a concrete
plausible mechanism, not proof of the complete 59-record causal chain. Compiler
flags, renderer arithmetic, fixtures, counters and comparison projections are
unchanged.

The selected fallback retains the same five fixed jobs and inserts a bounded
three-party compatibility barrier. Before any full shadow capture, all three
candidate hosts collect one separately authorized uninstrumented shadow probe
with five warmup frames, one retained frame and a 180-second deadline. Every
packet must pass the original native validator and global source/runtime/input
checks. A wrong source, failed process, missing file or cancelled worker is a
campaign failure, not a host that can be silently excluded.

The fixed algorithm computes all three original exact pairwise comparisons,
enumerates the seven nonempty host subsets and selects the largest subset whose
every pair passes. A fixed lexical tie-break resolves equal-sized candidates;
the ordered three full shadow roles are assigned round-robin. This does not
assume comparator transitivity or select hosts by CPU vendor. All workers bind
the same complete artifact identities and canonical allocation hash before full
execution. There is no new group, replacement host, takeover or retry after a
failure.

This rule preserves three-way overlap when possible and a two-plus-one schedule
when only two hosts compare exactly. A singleton remains safe but has no shadow
parallel speedup and adds probe overhead. The short probe includes startup costs
and does not reliably predict full 120-frame witness time, so the placement rule
does not rank hosts using speculative extrapolation. A faster singleton could
in principle beat a slower pair. Actual assignment, probe overhead and full
critical-path measurements must remain visible; this is not a claim of globally
optimal or repeatable performance.

Artifact names bind the current run, attempt and three fixed workers. The
barrier requires immutable artifact IDs, API SHA-256 digests, bounded safe ZIP
extraction and complete original raw evidence. It has a finite 600-second wait;
missing peers never produce a successful smaller campaign. [GitHub artifact v4](https://github.blog/changelog/2024-02-12-github-actions-artifacts-v4-is-now-generally-available/)
makes completed uploads downloadable before their jobs end, permitting this
rendezvous inside the existing matrix. The workflow uses read-only Actions
access and does not create or reschedule jobs. Its native-job ceiling accounts
for the singleton case: three original 3600-second process deadlines plus
bounded setup, barrier and evidence handling.

A separate nonqualifying `--cohort-probe` mode exercises the whole barrier and
placement rule, then collects distinctly named, uninstrumented post-probe checks
with five shadow warmup frames. This tests the previously unobserved
cold-shadow-to-shadow sequence before another expensive campaign. The full
mode retains every original 120-warmup capture and complete witness. Probe
plans can yield only `PROBE_PASS` with qualification false; the final required
check still rejects them as `PRECHECK_ONLY`. A probe cohort predicts where to
run the full captures. Only their unchanged exact comparisons can qualify them.

The independent Windows failure in #624 was an existing CPU-only positive test
that injected a 2.05-second delay into every integrity audit, including launch
proofs with an unchanged 0.5-second freshness limit. Retained receipts show
continuing heartbeats and an expired proof, so containment correctly failed
closed. A test-only repair confines the delay to one background audit after
real authenticated target resume and uses a bounded benign handshake to observe
heartbeats. Production deadlines and stale-proof negative controls remain
unchanged. Hidden partial coordination files are also retained by that bounded
failure upload. See the [fixture investigation](evidence/CI-WINDOWS-CPU-FIXTURE-20261114.json).

## Explicit change to serial fail-stop semantics

`sdvk009_publication.qualify` and its original serial fail-stop tests remain
unchanged. The distributed entry points implement a separate contract requiring
Owner review before merge:

1. The shared build seals the complete ordered four-capture workload, exact
   source/tree/runtime/packages/historical inputs, single-use authorizations,
   three separate routing probes and fixed placement algorithm before execution.
2. Every worker authenticates those identities and the explicit hosted llvmpipe
   guard before native preflight. It creates failure-default prospective receipts
   and exclusive launch records.
3. All three probes must complete and validate. Every worker recomputes the
   original exact pairwise comparisons and the same canonical allocation. An
   excluded host still retains its valid probe and explicit empty full workload;
   it cannot disappear from the expected worker set.
4. Compositing remains on the six-module worker. Shadow workers execute only
   their allocated original roles, in original plan order, stopping locally on
   a native capture or individual admission failure. Cross-capture comparisons
   and negative controls remain deferred to assembly even when several roles
   share one host; their failure cannot qualify that completed collection.
   Already-authorized siblings on another host may continue. The
   original plan and legacy receipt alias order remain intact; global temporal
   launch suppression is deliberately changed and is not claimed.
5. Every full capture retains a fresh process directory and application cache,
   the original mode and diagnostic role, 640×480 extent, **120 warmup frames,
   one retained frame, 3600-second deadline, exact RGB and zero retries**.
6. The assembler authenticates every original probe and worker, independently
   recomputes the allocation, and requires agreement and exactly-once ownership
   before moving evidence. It runs the unchanged witness validators, both
   control comparisons, witness-repeat comparison and all nine original negative
   controls for each witness. Every applicable corpus/module/platform/CPU gate
   remains mandatory. Neither a passing probe nor a sibling success can repair a
   failed or missing qualification.

SIGTERM/interruption leaves a failed or cancelled receipt and partial inventory
when execution can finish its failure handler. Actions uses `always()` for
packing/upload and retains original worker/probe artifacts when aggregation
fails. A hard runner loss may prevent upload; that absence fails closed. There
is no automatic native retry or reassignment.

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

Distinct Linux VM boot identities for all four full-mode capture workers,
worker execution UUIDs, request hashes, original process working directories
and publication diagnostic run IDs are required. Several independently authorized
full processes may share a selected worker, but their requests, directories and
diagnostic IDs remain distinct. Each shadow worker must attest the same boot
identity for its routing probe and later full captures. Runner display names
remain descriptive, not a uniqueness assumption.
The aggregator verifies capture names/order, exactly one authorized request,
receipt/run equality and worker provenance. Renaming a copied packet cannot
supply an independent repetition. Mismatched source, runtime, device or plan
fails before qualification.

## Evidence transport and consumer compatibility

The shared runtime is built once. The publication packet now contains its
compositing worker's manifest and raw capture as well as the six original
module packets; all seven roots and successful native receipts are required.
Runtime and authored-input archive SHA-256
values and the plan SHA-256 are passed directly from build job outputs and
checked by consumers, in addition to retained sidecars. Historical Freedoom
0.13.0 content is fetched and authenticated once; controls retain that shared
input and plan in the final evidence.

Each worker transports a bounded namespace, source/runtime/plan/workflow
identity, explicit job status, raw process receipts/captures/diagnostics, and
complete SHA-256 file manifest. Download namespaces remain separate until
verification. Unknown, duplicated, cross-wired, incomplete or corrupt artifacts
cannot be silently overwritten by download merging. Each original routing probe
is retained once in final evidence, including probes from excluded hosts. Peer
downloads stay outside retained worker roots; separate immutable probe Actions
artifacts remain available, and all allocation receipts bind the same three
artifact identities.

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
serial API. Cohort controls additionally cover all seven subsets, deterministic
ties, non-transitive comparison outcomes, strict three-party authentication,
unsafe/corrupt ZIPs, missing/cancelled probes, allocation disagreement, excluded
workers and exact full role ownership. A successful subset cannot hide an
invalid or absent probe packet.

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
