# SDVK-009 no-launch input correction candidate

Physical STOP remains ACTIVE. SDVK-009-PHYSICAL remains HELD / NOT ACCEPTED.
Issue #9 remains OPEN and historical NVIDIA fault cause remains UNDETERMINED.
This is a local software correction candidate, not a new accepted supervisor pin,
host attestation, diagnostic result or execution authorization.

## Command and native-input boundaries

The previously accepted validator checked the command executable and capture
metadata but did not reconstruct the entire command. A retained CPU-only copy
changed observer warmup from 120 to 119 in `expected_argv` while capture metadata
remained 120 and was accepted. The correction reconstructs all three prospective
commands using the pinned oracle's verified prepared scene and observer recipe,
then requires exact array equality. Workload, deadlines and zero retries remain
unchanged.

`native_device` now requires exactly `vendor_id`, `device_id`, `device_type` and
`driver_version_raw`: uint32 integers, with physical type 1 or 2. Nulls, strings,
booleans, extra metadata and nonphysical types fail before registry/file checks.
The approval helper independently applies this same native-input guard before
touching a release gate. Inventory provenance/status belongs outside the native
property map, whose entries are later compared with actual renderer readback.
Successful structural validation never authenticates a human decision or makes
invented numeric values genuine host properties.

Missing native properties remain unavailable under the no-Vulkan constraint.
PCI identifiers, NVML driver strings and historical readbacks do not substitute
for fresh native properties. Any future instance-based attestation requires its
own explicit authorization; no logical device or renderer is needed merely to
query physical-device properties, and neither is authorized here.

## Static Windows discovery and custody

Absence of `SOFTWARE\Khronos\Vulkan\Drivers` does not establish absence of driver
registration. The Windows loader also discovers manifests through adapter and
associated software-component device keys. The private survey must correlate
the active adapter, distinguish legacy/native64/WoW registrations, and retain
manifest and library bytes as static candidates until actual selection is
observed. The helper checks the native64 legacy and display-class/ControlVideo
rows already covered by this supervisor's registry policy; it does not claim a
complete DXGI/PnP/AppX loader enumeration.

For legacy driver/layer entries DWORD 0 means enabled for discovery; nonzero
means disabled. The OBS registration cannot be called disabled solely because
its DWORD is zero. Manifest-specific enable/disable environment names must be
captured even if absent, and the sealed child environment must match the review.
See the Khronos [Windows driver discovery](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md#driver-discovery-on-windows)
and [Windows layer discovery](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderLayerInterface.md#windows-layer-discovery) contracts.

The validator requires discovered native64 manifests and referenced libraries
to match packet SHA-256/size pins. Libraries also need explicit module-policy
entries. It parses JSON and hashes data without loading a DLL, creating Vulkan
objects, changing registrations or changing environment settings. Bare DLL
search names without resolved provenance fail closed. These checks close the
recorded manifest/OBS pin gap without asserting which modules actually load.

Source reconciliation must associate each file with its own source role,
commit/tree and Git blob identity. The public precursor has 15 supervisor files
(including the contract document) and five renderer oracle files. A single
renderer identity must not label all 20 mixed-source rows. Preserve original
mislabelled evidence and issue an explicit superseding correction.

## CPU controls and retained limits

The suite adds native-placeholder rejection before IO/release; legacy DWORD
semantics; device registration despite absent legacy keys; manifest/library,
module and environment omissions; changed bytes; and unresolved library names.
The real recipe control prepares both scenes, accepts a dummy positive packet
through the public no-launch CLI and rejects edits to every non-executable
argument in every stage, plus insertion, deletion and ordering mutations.
Executable/build/device identities and registry/source authority in that unit
fixture are explicitly synthetic. Private controls can separately use the clean
frozen renderer oracle with the same dummy executable. Neither is host or
physical evidence.

The previously reviewed PR #166 failure-receipt instrumentation is carried into
the native benign-CPU test without changing its deadline or production behavior.
Its later success cannot rewrite the retained earlier failed CI attempt or
attribute that failure's exact cause.

Before reconsideration, complete normal source review/checks and select a new
accepted supervisor pin; finish truthful host attestation under separately
authorized scope; refresh host/event evidence; prepare a fresh packet with new
paths/identity/expiry; and review its exact inventories and negative controls.
The current incomplete packet, original failed evidence and protected STOP
markers are not changed or reused. No public upload, approval, release, renderer,
Vulkan, diagnostic or campaign execution is part of this correction work.
