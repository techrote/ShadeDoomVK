# SDVK-009 bound publication witness

## Scope and starting authority

This is the bounded continuation of [issue #9 checkpoint
6120820868](https://github.com/techrote/ShadeDoomVK/issues/9#issuecomment-6120820868).
PR #145 is merged as `0c0332c47584f2f9d1a49290829b40e43b0d7c7a`, tree
`f2a6b87612032e070e4694b01010852ccfe1de51`; its source workflow and all nine
post-merge CI jobs passed. No open PR was present at reconciliation.

**Physical STOP remains active. Root cause remains UNDETERMINED.** This
continuation neither retries a physical experiment nor changes the sealed
original source, executable, content, incident or private diagnostic packets.
#8/#9/#10 remain open, and physical scaling, architecture, performance and POM
acceptance remain ungranted.

The engineering question is whether a newly identified hosted software run
can join production CPU collision snapshots, staging/copy records, buffer
allocation identities, descriptor publications, actual recorded command state,
bound pipeline stage bytes and defined-field destination readback. The scope
is the software collision Node/Vertex/Index buffers used at scene Fixed set 0,
bindings 2/3/4. It does not qualify every sampled image, surface/portal record,
hardware acceleration structure or arbitrary Vulkan consumer.

The ordinary renderer and existing CFX resource caps remain the control.
There is no light-selection, traversal, quality, shader-math or workload change.
This document records the prospective qualification before its first hosted
execution; actual run identities and disposition belong in the PR/issue receipt.

## Evidence meaning

| Evidence | What it establishes | Remaining limit |
|---|---|---|
| CPU collision snapshot | Production construction/update state with original slots, occupied indices and defined geometry fields | A reconstructed software run is not either failed physical graph. |
| Staging and copy records | Prepared byte fingerprints, source/destination allocation IDs and recorded offset/size ranges | A fingerprint is not a GPU instruction or a cryptographic content identity. |
| Descriptor publication and typed command state | Which allocation generation was published and recorded for a command, including updates and command recording generations | The application record is not a driver trace of every executed load. |
| Pipeline stages and SPIR-V files | Exact stage bytes passed to successful creation, entry points, specialization and library ancestry for the recorded bound pipeline | Driver-generated machine code and historical NVIDIA instruction attribution remain absent. |
| Post-use readback | Defined destination fields after the preceding submitted work and an existing successful fence | Later visibility cannot prove the values seen by each earlier shader load. |
| Uninstrumented control and independent repeat | Same-build/content/settings state and RGB equivalence in the bounded software experiment | Instrumentation can alter scheduling even when the retained output is identical. |

These distinctions are part of the acceptance contract. In particular, an
after-draw barrier can make bytes visible to a later copy without proving an
earlier shader's publication dependency was correct. A passing packet therefore
narrows the new software run's publication/identity uncertainty; it does not
resolve the historical timeout or authorize a physical launch.

## Identity and coverage contract

The witness is opt-in through `CFX_WITNESS_DIR` together with the existing CFX
trace/resource activation. It uses exclusive new files and a separate bounded
`publication-witness.tsv`, preserving the historical trace's 8,192-resource-row
and upload fingerprint limits. The witness stream has a prospective maximum of
262,144 rows and 128 MiB. Missing initialization, write failure, omission,
unknown identity, budget exhaustion and incomplete completion are failures.
Neither tail rotation nor sampling may be called complete coverage.

Each shader/specialization export is limited to 16 MiB, with 128 MiB of such
exports per process. Complete upload hashing has a separate 128 MiB process
budget. The final observer hook runs after the ordinary screenshot and existing
waits, checks that no submitted or unsubmitted readback remains, and closes the
stream. A completion marker is published exclusively only after successful
stream and marker close. A summary line alone cannot establish completion.

Existing process-monotonic resource IDs identify allocation incarnations. Raw
Vulkan handles alone do not distinguish retirement and reuse. The join must
retain descriptor publication generations, command recording generations and
actual submission/fence associations, so stale or unsubmitted bindings cannot
pass as consumption evidence. Graphics library inputs and the stages inherited
through them remain attributable. Exact SPIR-V files are bounded and exclusively
created; retained artifact SHA-256 checks supplement the runtime byte fingerprints.

The witness covers the 120 warmup frames as well as the retained state frame.
Restricting the identity records to the retained frame would omit the phase in
which both historical shadow-boundary failures occurred. Startup commands
without a qualified collision snapshot have a separate explicit scope; they
cannot silently satisfy a later collision-consumption requirement.

## Post-use readback and lifetime

The copy command is appended after the existing transfer, draw and thread
command buffers in the same normal submission. It is not inserted before the
shadow draw, and does not add a new fence, host wait or queue-idle operation.
Existing upload-only submissions retain their ordinary behavior.

Readback uses a compact set of defined fields: the root word; collision node
center, extents and link/element words excluding padding; occupied index words,
including holes; and XYZ words of referenced vertices. Unused backing tails,
unreferenced positions, other vertex attributes and native padding remain
UNKNOWN/UNREAD. Original field offsets and resource allocation identities are
recorded rather than renumbered as semantic identities.

The normal shader/vertex/index and transfer accesses precede the buffer-scoped
copy dependency. Transfer writes to the staging allocation are made available
to host reads. Staging and source lifetime cover the existing submission fence;
mapping/cache invalidation and serialization occur only after its successful
ordinary recycle/frame wait, before the relevant retirement lists are released.
The snapshot object/event used for comparison must have completed its original
exclusive file write. No new snapshot schema replaces or rewrites earlier files.

Each compact plan is bounded to 4 MiB and 16,384 regions; at most 4,096 plans and
256 MiB of readback bytes are allowed per process. The existing eight submission
slots plus one plan being recorded bound staging allocation ownership. A logging
failure disables further evidence creation but must not release or abandon an
already submitted readback: its command and staging allocation still retire only
after the ordinary successful fence. Such a packet remains failed.

The host visibility sequence follows the Vulkan
[mapped-memory invalidation contract](https://docs.vulkan.org/refpages/latest/refpages/source/vkInvalidateMappedMemoryRanges.html):
device write, host-read memory dependency, fence signal/wait, then invalidation
before reading. A fence alone is insufficient. VMA's
[allocation invalidation API](https://gpuopen-librariesandsdks.github.io/VulkanMemoryAllocator/html/group__group__alloc.html)
handles allocation-relative non-coherent atom alignment; map/unmap alone does
not perform cache invalidation.

The extra after-draw copies, CPU serialization and witness-only transfer-source
usage on vertex/index buffers are declared perturbations. They are not timing
samples. Their effect on scheduling remains a limit even after a control match.

## Prospectively pinned hosted qualification

Execution belongs only in the identified hosted Linux software-Vulkan job.
Its process environment isolates the Mesa lavapipe ICD; every native receipt
must identify a CPU llvmpipe device. No renderer, vktool, version query that can
initialize rendering, or Vulkan-device creation is permitted in the ordinary
coding environment.

The legal historical content is official Freedoom 0.13.0 `freedoom2.wad`,
28,787,748 bytes, SHA-256
`a8772e088847032510d97ba2312406a6998f21cbab44d4ff10696faa9c0ecd4b`.
The archive, license and extracted member identities must be retained. The
shadow scene's PK3, generated scene configuration and base INI must independently
match the historical content pins before launch. A version label alone does
not establish byte equality.

| Serial process | Content | Extra witness instrumentation |
|---|---|---|
| 1 | Compositing control | Off |
| 2 | Shadow-boundary control | Off |
| 3 | Shadow-boundary witness 1 | On; CPU snapshot and complete publication/readback evidence |
| 4 | Shadow-boundary witness 2 | On; independent fresh process and evidence directory |

Every process uses 640x480, 120 warmup frames, one retained state/RGB frame and
the unchanged authored settings. There are no timing samples or automatic
retries. The GitHub-hosted software-only process execution ceiling is 3600 seconds.
The workload remains exactly 120 warmup frames plus one retained state/RGB frame,
with no automatic retries. The ceiling is a runner-throughput accommodation, not
a correctness or performance acceptance threshold, and it does not replace or
qualify the held physical diagnostic's 180-second limit. The former 600-second
Avrea-oriented ceiling and the first GitHub-hosted 1200-second ceiling are both
retained as failed host-duration evidence. On the last accepted 16-vCPU run the
three shadow publication captures completed in about 270-279 seconds each; on the
standard four-vCPU GitHub host, shadow-control exceeded 1200 seconds without a
renderer/device fault. That retained evidence authorizes the 1800-second ceiling
while preserving the exact workload, oracle and zero-retry policy. A failed stage
stops dependent stages and preserves the incomplete receipt. Workload, coverage,
state/image thresholds and retry policy must not be relaxed after failure to
obtain a pass; any future execution-ceiling change requires another explicit
runner-policy decision and retained failure evidence.

Both witnesses must match the shadow control through the existing exact RGB
and normalized semantic-state oracle, preserving its decisions and capacities.
Only explicitly named diagnostic request metadata may differ. Each packet must
independently join all required snapshot, publication, command, stage, fence
and readback evidence, including warmup. Cross-process raw handles and allocation
numbers are not compared as durable semantic identities.

## Negative controls and integration gates

CPU production/helper tests and copied receipt mutations exercise missing or
wrong field offsets, copy coverage, stale allocation/publication/recording
generations, missing bind/consume/submit links, absent or wrong stage bytes,
premature or missing fence completion, unknown fields and truncated evidence.
The unchanged original packets are retained. No deliberately stale Vulkan
descriptor or invalid buffer is submitted to any GPU as a negative control.

All attributable check failures must be repaired without weakening assertions.
An independent review of identity, byte layout, lifetime, normal submission
ordering and completeness precedes merge. Source evidence, the full required
CI matrix and the separate matching-content software qualification must pass
for the reviewed tree. After merge, the resulting master/tree and its required
post-merge checks are verified and the exact disposition is appended to #9.

Software qualification is the boundary of this change. Finite expensive ray
work, the two historical physical failures and physical architecture/scaling
acceptance remain separate questions. No physical candidate or authorization
is created by this protocol.
