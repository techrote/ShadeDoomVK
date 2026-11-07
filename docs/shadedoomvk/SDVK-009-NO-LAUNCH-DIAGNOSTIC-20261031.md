# SDVK-009 — GTX 1650 SUPER no-launch diagnostic source precursor (31 October 2026)

**Disposition: `PACKET_INCOMPLETE_HOST_INPUTS` and `PHYSICAL_HELD_NOT_ACCEPTED`. Physical STOP is ACTIVE. Historical NVIDIA fault cause is UNDETERMINED. Issue #9 stays OPEN.**

This is a source-verified, **not executable and not approved**, handoff following [PR #164](https://github.com/techrote/ShadeDoomVK/pull/164). It has not launched ShadeDoomVK, its `--version` interface, the diagnostic, Vulkan, or the 41-process campaign. No operator release/claim/approval has been created.

Machine-readable authority: [`evidence/SDVK-009-NO-LAUNCH-PRECURSOR-20261031.json`](evidence/SDVK-009-NO-LAUNCH-PRECURSOR-20261031.json). Its prospective stage command arrays contain unresolved placeholders by design; **do not copy/paste them as native launch commands**.

## Five identity planes; no implicit advancement

| Plane | Independently pinned authority | What remains unobserved |
| --- | --- | --- |
| Supervisor source | **Accepted `master@2f7681e749f6e6a8560bb7b831857d356b99193d`**, Git tree `790300c3f0cd995d1af85fd13414dd7b59b78a78` (reviewed PR #164 head tree is equal). SHA-256 and exact size of all 14 files in `tools/physical_supervisor/` plus Windows supervisor document are inventoried in JSON. | A host-local independent checkout and immutable input/ancestor binding. |
| Renderer source | **Separate accepted `130d09ac4267d02359c7c2603ceced723ceac746`**, Git tree `50c749a848c35f04780140e4d06e9f4fdeb57ff6`, not the newest master. Five relevant frozen oracle/recipe/PF source files are individually SHA-256 pinned; the whole Git tree pins all other source bytes. | Exact clean, independently built local renderer checkout and complete local file-level build provenance. |
| Renderer build | No build selected, no executable/PDB measured. Historical executable/driver hashes must **not** be promoted to this new build. | Compiler/toolchain, flags, `RelWithDebInfo` configuration, generated binary and PDB hashes/sizes, complete build/source snapshot receipts and original/isolated copy equality. |
| Runtime/inputs | Frozen authored recipe selectors `compositing` and `shadow-boundary` and source hash inventory. | Actual isolated Python, oracle/PF package closure, shader sources, game PK3/DLLs, selected loader and layers, official Doom2-compatible IWAD, generated fixtures/config/script hashes, all absolute stage paths. |
| Physical host | Prospective **Ryzen 5 2600X / GTX 1650 SUPER class**, **not** a current authenticated device identity. | Native OS build/boot identity, fresh CIM comparison, GPU PCI ID/UUID and driver/NVML policy, Vulkan loader/ICD/layers and registry snapshots, independent System event epoch/bookmark/anchor and current NTFS-root evidence. |

These are *separate* identities: the supervisor merge does not upgrade renderer source. Public repository SHA-256 rows are computed from actual GitHub-tracked UTF-8 bytes, cross-checked against the corresponding Git blob IDs and byte lengths; they do **not** authenticate a local Windows working tree or machine.

## Frozen three-stage diagnostic (not executed)

| Order | Authored scene/map | Extent | Warmup | Retention | Renderer deadline | Retries |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `compositing` / `SDVCMP` | 640×480 | 120 frames | 1 state/RGB frame | 180 s | 0 |
| 2 | `shadow-boundary` / `SDVSHDW` | 640×480 | 120 frames | 1 state/RGB frame | 180 s | 0 |
| 3 | Independent `shadow-boundary` / `SDVSHDW` | 640×480 | 120 frames | 1 state/RGB frame | 180 s | 0 |

Strictly serial. Stage 3 requires exact state and RGB equality against stage 2. Authored shadow control expects 1,025 candidates / 1,024 selected / one dropped. The JSON records the original `corpus.json` recipe-derived argv with `{RENDERER_EXE}`, `{STAGE_OUT}` and `{IWAD_NAME}` unresolved; it also records the unchanged supervisor observer flags. These are **prospective metadata, not host-validated commands**. The actual reviewed `prepare.py` must derive absolute `expected_argv` from independently pinned runtime inputs.

The separate 41-process architecture campaign (20+6+15) is **not part of this packet** and remains held. Existing [physical qualification protocol](SDVK-009-GPU-QUALIFICATION-PROTOCOL.md) is not an execution permit; do not use the legacy physical driver's `--execute` interface.

## Private Windows completion: strictly no launch

Conduct the following **only when back at the actual Windows PC**. Store the worktrees, receipt outputs and any machine-identifying details privately; use fresh directories and never alter the retained failed-incident archive.

1. **Freeze/check both source identities without executing the renderer.** Independently checkout the exact supervisor commit and the exact renderer commit stated above. Use read-only `git rev-parse HEAD HEAD^{tree}`, `git status --porcelain --untracked-files=all` and `git cat-file -e <commit>^{commit}`. Reject either dirty worktree, changed tree or missing commit. Independently hash and size all source files used by tooling, oracles, shaders and dependencies. Source commits/tree are not SHA-256 file hashes.
2. **Build-only, then pin actual bytes.** Use the repository's qualified Windows build tooling and record exact MSVC/compiler versions, generator, flags, configuration, source snapshot, complete staged runtime, EXE/PDB and original/copied executable SHA-256 and sizes. Do **not** invoke the executable, even with `--version`; preserve `DECLARED_NOT_EXECUTED` provenance. Supply the official isolated Doom2-compatible IWAD and hash it; generate/validate authored scene assets without a renderer launch.
3. **Survey the actual host read-only.** On the Windows supervisor checkout, from a trusted isolated Python:
   ```powershell
   python -B -m tools.physical_supervisor host-identity --out <FRESH_PRIVATE_HOST_JSON>
   python -B -m tools.physical_supervisor event-baseline --out <FRESH_PRIVATE_EVENT_JSON>
   ```
   Independently compare native boot FILETIME with current CIM LastBootUpTime at CIM precision. Record read-only current GPU PCI/UUID/driver and NVML policy, loader/ICD/manifest/layer file hashes, HKLM/HKCU Vulkan and display-class registry values, System event bookmark/epoch/RecordId continuity, environmental overrides, fixed local NTFS roots and reparse/ancestor checks. Do not change driver, GPU settings or registry. Reject any ambiguity.
4. **Prepare and validate without authorising anything.** Construct a private seed matching [the reviewed supervisor README](../../tools/physical_supervisor/README.md), pointing at a never-used output root and the exact source/build/runtime/host inventories. Then invoke only:
   ```powershell
   python -B -m tools.physical_supervisor prepare --seed <COMPLETE_PRIVATE_SEED_JSON> --packet <FRESH_PRIVATE_PACKET_JSON>
   python -B -m tools.physical_supervisor validate --packet <FRESH_PRIVATE_PACKET_JSON>
   ```
   Record stdout/stderr/exit statuses, canonical packet digest, independent SHA-256 of the complete byte inventories and all exact generated `expected_argv`. Neither successful command releases STOP or asserts runtime validation. **No approval file, release, claim or execution command is part of this procedure.**
5. **Exercise the rejection path on isolated copies.** First run `python -B -m unittest discover -s tools/physical_supervisor -t . -v` using only benign CPU children/synthetic readers. Then, on **fresh copied private seeds/packets only**, attempt read-only `validate` with one change at a time: source/EXE hash, dirty checkout, fixture/shader/dep, native boot, GPU/driver/loader/registry registration, event epoch/anchor, expiry/commands, unsupported junction/reparse root, missing files or changed policy. Require every invalid variant to fail. Historical STOP/approval/replay/owned-child races belong to the native synthetic test suite; do not probe them by creating an approval or initiating `run`. Preserve each failed validation output and its source/input identities.

If any host readback, inventory, preflight or negative control fails, record `PACKET_INCOMPLETE_HOST_INPUTS` or `FAILED_STOP` as appropriate, retain all evidence and stop. Once every real private input is sealed and actual `prepare` and `validate` succeed, **a separately frozen packet may be marked `PACKET_PREPARED_NOT_AUTHORIZED`**, but it still cannot run. Human review and any future authorisation are separate, out-of-scope actions.

## Evidence, negative controls and remaining limits

PR #164's exact-head [nine-job CI](https://github.com/techrote/ShadeDoomVK/actions/runs/39107722480) and [source evidence](https://github.com/techrote/ShadeDoomVK/actions/runs/39107722465) passed. Its hosted native Windows benign-CPU job executes 129 tests (one expected privilege skip), covering watcher/STOP policy, suspended child ownership, native locks and junctions, one-use audit generations, parent liveness, source/version adapters, 50 ms controlled exit observations, atomic receipts and failed/incomplete evidence. Their results qualify the **software supervisor**, not the actual GTX 1650 SUPER.

The source-only precursor additionally rejected **23/23 deliberately modified metadata copies** under a fixed invariant checker. These include changed source hashes and tree, fabricated runtime/host baselines, changed stage/deadline/warmup, prohibited `--execute`/`--version`, STOP tampering, fake validation and forged approval. These controls do **not** claim that a real Windows packet's hardware/registry/event tampering was tested here. Native host-specific negative testing is still outstanding.

Original failed heartbeat and historical NVIDIA/CFX incidents remain immutable negative evidence; they cannot be reinterpreted as repaired physical runs. All private telemetry, identity paths, owner records, crash dumps, proprietary assets and sealed original archives remain **outside public GitHub**.

**Current safe stopping point:** source pinned, supervisor software merge verified, precursor published, physical execution prohibited; remaining launch gates and the actual initial three-process diagnostic are deliberately outstanding. Issue #9 remains open; `SDVK-009-PHYSICAL` is **HELD / NOT ACCEPTED**.
