# Physical campaign resumption - 7 November 2026

The owner explicitly corrected the earlier execution restriction in this session:

> YOU ARE AUTHORIZED TO USE THE AVAILABLE PHYSICAL GPU.

The correction authorizes a fresh current-source campaign, bounded rendering,
measurement and profiling in the existing owner-configured system state. It
requires exact source/build/content/host identities, preserved fault detection,
and retained attempts. Historical STOPs remain evidence; no old failure is
relabeled PASS. No voltage, BIOS, firmware or driver installation changes follow.

The new private generation pins twelve historical STOP files and the direct
owner instruction. Renderer source starts at master `9cf86b92dac3ae784eea0554d24ca18a43a3120c`,
tree `b8e156f7255596dea527c515720b4d223702d70c`. The clean Windows build identifies
that source. New supervisor source is separately identified and qualified.

An independently reviewed, once-only instance probe completed with no logical
device or queue submission: GTX 1650 SUPER, vendor 4318/device 8583, driver raw
2585198592 (616.92), Vulkan API raw 4211039, and 56 observed module pins.
Its plan SHA-256 is `785d76ab4be21a5debd219a1d3cea7009a9bc98a7d5eb3d1321454f645e910f5`.
This establishes instance/device identity only. It does not establish renderer
stability, speed, architecture acceptance or a passed physical milestone.

Two independently reviewed diagnostics now have retained results. Generation 01
rendered compositing but stopped on an external module reader's error 299 near
process teardown. Its original exit status is unknown; it remains FAILED_STOP.
The bounded reader repair admits only an already exiting, fully attested process
with prior complete module coverage, and passed 174 native CPU controls.

Generation 02 used observer `307fc30517fd0c03a3c193bdb171fffd675ae97c`,
the unchanged renderer/build/content above and a new three-creation, zero-retry
grant. Compositing exited 0 and passed its completion fence. The first 1,025-light
shadow process then triggered nvlddmkm event 153 and a live WATCHDOG dump with
code 0x141 (VIDEO_ENGINE_TIMEOUT_DETECTED). The independent repeat was never
launched. The attempt remains FAILED_STOP; no completed shadow state/image or
timing acceptance exists. Peak observed temperature was 55 C. Type-4 Vulkan
address rows identify unknown instruction pointers and do not establish a root
cause. Full private failure evidence and the 7.8 GB kernel dump are retained;
kernel memory must not be published with ordinary renderer artifacts.

The generation-02 packet SHA-256 is
`bf39ae6e1c6bbdb39f9916822fef40e3de6c373520def2b1acfa317c86145490`;
the failed-attempt manifest SHA-256 is
`2def23ed1cce57afb7cd53ada046b44ad97bd2c5d851814a827f3e1bce0b6fd9`.
The OS did not reboot and the GPU returned to idle. A later readback reports
90 W instead of the failed packet's 100 W limit; no setting was changed by this
session. This unexplained operating-state difference must remain explicit in any
prospective comparison, and prevents a matched performance claim.

The requested unmodified stock VKDoom comparison is a prospective engine
discriminator, not an unchanged failed-workload retry. Stock source is exactly
the founding commit `09634479ab5bf9adf691074fffe85a006a398cd0`; a clean
RelWithDebInfo build is available. Stock has no SDVK observer: console `wait`
counts game tics, so its screenshot/exit/health comparison cannot stand in for
matched frame timings or SDVK native-state acceptance. At this entry no stock
GPU process has run. A new [warmup extent diagnostic](SDVK-009-SHADOW-FAULT-DISCRIMINATOR-20261107.md)
also closes a concrete observation gap without claiming a TDR repair.

Serious GPU or OS faults stop an attempt, retain complete evidence, and require
a bounded repair or discriminator before another identified attempt. The owner
also authorizes a checkpointed system restart if a fault leaves lasting
impairment; no restart has been needed so far. Unchanged faults are not retried
blindly. All measurements remain pending until actual retained runs support them.

SDVK-009 physical acceptance, full SDVK-008 POM cost/quality and SDVK-014 physical
bake/update criteria remain unaccepted. SDVK-012 and later dependencies receive
no exemption from this resumption authorization.
