# SDVK-009 instance-only probe candidate

This is a separate prospective attestation program, not a renderer diagnostic,
performance measurement or physical qualification. Historical STOP records and
failed packets remain immutable. The renderer's source pin is not advanced.

## Scope and mechanics

`instance_probe.cpp` dynamically loads the absolute native system Vulkan loader
only after its explicit instance-only argument and controller identity pass.
It requests Vulkan 1.1, creates one instance, enumerates at most 16 physical
devices and 1,024 extensions per device, queries properties/UUID and advertised
PCI bus properties, inventories actual loaded modules, destroys the instance,
and emits one JSON result. An incomplete enumeration fails without retry.
No device, queue, command-buffer, surface, swapchain or renderer API exists in
its backend interface. It is not linked to a Vulkan import library.

The worker retains its native parent handle and authenticates the parent's
creation time. A native watchdog terminates only its own process if that parent
exits or the 30-second worker lifetime expires. The external controller creates
the worker suspended, authenticates its executable/parent/time identity, assigns
its private containment job, and rechecks plan/registry/environment/boot/expiry
before resume. It monitors telemetry and System events, observes actual modules,
retains bounded output and a 15-second completion event fence, and uses owned
handles for failure containment. Receipt failure must not bypass termination.

The reviewed exact plan pins the executable/PDB, source/header bytes, manifests,
loader, candidate driver/layer libraries, telemetry executable and closed runtime
roots. It includes fresh native boot and System event identity. No registration,
driver, clock, power limit or persistent setting is changed. The probe inherits
the reviewed layer environment, including registered implicit layers.

## Review and CPU qualification

The CMake project under `tools/physical_supervisor/probe` builds only this worker
and a fake-backend control executable. `SDVK_PROBE_CPU_TEST` excludes the native
loader backend entirely. The C++ controls check one positive case and thirteen
negative lifecycle/count/cleanup/output cases. Native Python tests additionally
exercise a benign Python worker through the controller, its deadline despite a
STOP-receipt failure, and native parent-death containment using the worker's
explicit CPU-only lifetime mode. None of these tests load Vulkan.

Review findings addressed in this candidate include missing parent-death
containment; missed module evidence from fast exit; cleanup after partial loader
construction; cleanup exactly once on errors; bounded enumeration; fresh expiry
checks at create/resume; case-insensitive path identity; and authenticated
termination even when failure receipts cannot be written.

The review record must accurately distinguish a self-review from independent
review. It binds the exact plan digest, genuine user instruction, CPU receipts,
expiry and disposition. A HOLD decision or blocking finding cannot execute.
The plan-specific one-use claim prohibits replay at a different output path.
There is no CLI that launches a renderer and no automatic retry loop.

## Renderer allowance is a separate protocol

A finite renderer budget does not itself define an executable workload. New
prospective limits must count retries in the total and retain every attempted
process and failed result. An allowed retry requires a fresh reviewed packet and
claim after its preceding failure is assessed; historical packets/STOP records
are never erased or relabelled. The three fixed diagnostic stages and their
workload/deadline/compare contracts remain the available renderer experiment.
No 24-process campaign or physical acceptance is created by this probe.

The current supervisor's exact-packet approval schema and zero-automatic-retry
contract remain in force. A conditional grant made before a packet exists must
not be disguised as a later human exact-packet decision. A prospective adapter
for delegated conditional grants/retry budgets requires its own source review;
native readback from this probe alone does not resolve that authorization-format
gap or qualify a physical renderer run.
