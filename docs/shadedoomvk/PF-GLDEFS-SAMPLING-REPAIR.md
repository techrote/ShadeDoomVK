# GLDEFS custom texture sampling repair

References [independent repair/#114](https://github.com/techrote/ShadeDoomVK/issues/114) and [PF-020/#37](https://github.com/techrote/ShadeDoomVK/issues/37).
This independent parser repair does not accept the renderer freeze or unblock
SDVK-001. The indexed-material, software-layout and PBR probe blockers remain
separate work; none of their implementation or freeze synthesis is included.

## Defect and resulting invariant

At accepted master `4df7dea1338f063c6417e024f967bfa4aa23edd4`, both the shared
material/map/class texture property and legacy HardwareShader property assigned
the omitted-filter default through the initial `texIndex=0` before selecting
the free authoring slot. Adding a second texture therefore overwrote the first
texture's explicit filter and left its own default at enum zero.

The four-line repair selects `texIndex=i` before default initialization.
Explicit filter properties, shader layer order, sparse authoring slots, errors,
limits and Vulkan sampler selection remain under the existing contract.
This is a local repair of inherited code, with no external donor transplant.

## Verification and limits

The compiled fixture extracts the actual property branches and MaterialLayers
types from production source. Scanner, lookup and container services are bounded
stubs. Its original branch is whitespace-hash pinned to the exact accepted
master and retains both counterexamples (15 assertions). The current branch
passes 1,119 assertions and 31 deliberate error cases, covering defaults,
explicit filters, insertion order, sparse slots, missing/duplicate textures and
capacity limits. This is not a full GLDEFS loader, GPU or visual fixture.

The CPU helper selects installed MSVC on Windows or C++17 on other hosts; it
does not skip compiler failures. All twelve inherited compiled-test callers
use it. Assertions, strict warnings and out-of-tree compiler outputs are
required. No renderer, GPU, performance or human acceptance is inferred.

Initial identical-production-source checkpoint `f4959818` passed272/272 native
Windows/MSVC PF discovery, four strict standalone fixtures, CFX8/8, deterministic
oracle equality and an engine rebuild. Retained local receipt hashes accompany
this note. The focused tree receives its own full CPU gate and all eight
exact-head hosted jobs before merge. Merge/master and post-merge verification
are required; PF-020 remains blocked independently.


## Focused-tree local gate

The isolated master-based source tree passes272/272 PF tests in28.894 seconds
with zero skips/errors under MSVC19.44 `/W4 /WX /UNDEBUG`, four additional strict
standalone fixtures, CFX8/8 and two byte-identical source-oracle runs. Commands
match the repository CI gate; compact log hashes are in the verification JSON.
All18 executable/test/helper paths are byte-identical after CRLF-to-LF
normalization to the retained checkpoint. Git archive applies native text
line endings; raw and normalized source hashes are recorded separately.
Shared material/map/class cases supply route inputs to the same
extracted property body; they do not prove the full loader's outer dispatch.
Legacy coverage preserves its actual omitted-filter grammar. Hosted exact-head
builds and post-merge verification remain separate required gates.
