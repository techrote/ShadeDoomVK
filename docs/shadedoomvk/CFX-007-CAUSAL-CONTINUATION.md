# CFX-007 / #97 operator protocol

Status: physical phase prepared; initiating defect unresolved. #96 merged and verified on master a6880fdb. See issues/CFX-007.md for authorization, repair objective, limits and three-success saturation.

## Live-state reconciliation
Windows boot22:33:23.5Z reports Kernel-Power41/6008 from the preceding shutdown. Owner explicitly explains restart, deliberate shutdown to remove P400, then current boot; no observed hang. Original stopped preflight root and all six historical guards remain immutable. A separate reconciled root contains a fresh post-context automated PASS baseline; events are filtered by actual UTC creation time, independently of Get-WinEvent's local-time StartTime handling. No event is relabeled as a clean shutdown or proven HD7770 cause.

## One launch at a time
`python tools/cfx007_execute.py --plan ABSOLUTE_ATTEMPT_PLAN.json` runs preflight only; add `--launch` for exactly one preregistered attempt. No automatic reproduction loop. Plans pin runner SHA, merged-renderer EXE/PDB/runtime/content/config/cache/script hashes, discriminator and predictions. `cfx_capture.py --approved-cfx007 --cfx007-lane-plan ...` is a separate #97 gate, not an old #78/#92 opening. It rejects missing/changed plans, binaries/PDBs/guards, out-of-scope run roots and spent/stopped budgets. Use only new merged renderer. Archive historical old EXE/PDB for old dumps.

`state.json` durably reserves each launch before start and tracks correlated loss/TDR episodes, pending attempt and analysis. At most16 launches total including controls and6 loss episodes. A risky launch requires accepted safe controls and no unreviewed prior target result. The executor backs up exact current global cache, installs the preregistered per-GPU snapshot, captures post-run cache then restores and hashes originals in finally. Application process dump precedes watchdog kill. Every attempt retains an artifact hash index.

## Automated recovery
`cfx007_health.py` performs read-only GPU/driver/PCI/Code0, NVML temperature/clocks/power/VRAM, Vulkan enumeration, prior process, Explorer and WM_NULL desktop responsiveness, unexpected WHEA/Bugcheck/Kernel-Power41/6008/BlueScreen, boot identity and storage checks. >20GiB free; GPU<80C and reported clocks/power inside declared normal bounds are protocol stop thresholds, not changes to hardware policy. No automatic reboot or policy change. Physical pixel integrity is unobserved while owner absent; routine human checkpoint expressly waived. Observed artifacting or any failed gate stops the lane and permits offline analysis.

Raw root: C:/ShadeDoomVK/pf-local-evidence/cfx007-gtx1650super-20261001-reconciled/. Per attempt: plan.json, execution-start/result, health-before/after, cache-backup/after, runs/RUN_ID/manifest.json, timeline.tsv, stdout/stderr, loader/layer/OS logs, conditional fault.bin and process.dmp, images/OBJ for controls and artifact-index.json. Match new dump with new PDB. Timeline joins as CFX-006 report describes; fingerprints are CPU prepared bytes only.

## Offline gate verification
12 CPU-only tests cover valid scope, spent/stopped/negative budget, changed EXE/PDB or guards, old issue/out-of-root, recovery events, live process/unresponsive desktop/disabled GPU, BlueScreen vs recovered TDR, PowerShell module-path isolation and UTC cursor excludes old anomalies but retains new WHEA. Existing8 classifier tests pass. Fresh merged-master Windows build succeeds; no resource source changes versus preserved runtime bundle. No physical result is claimed until attempt records exist.

First safe control exited0 with healthy automatic recovery and complete image/OBJ. The strict inventory gate exposed a pre-existing self-size error: manifest6278 recorded before final9704-byte write. Every other listed artifact size matched. Fixed by excluding the changing manifest from its internal inventory and hashing the final file in the external attempt index; a CPU regression pins that contract. Original evidence/STOP remain immutable. A separately recorded corrected-capture phase carries **one consumed launch /zero losses**, not a reset budget.
