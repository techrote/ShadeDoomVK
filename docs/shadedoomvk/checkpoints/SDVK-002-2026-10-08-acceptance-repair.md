# SDVK-002 acceptance-repair checkpoint — 8 October 2026

**Disposition:** SDVK-002 substantive implementation is merged and post-merge qualified, but issue #2 remains open because the documentation-only acceptance PR exposed one additional same-scene nondeterminism. This checkpoint preserves the exact proposed repair and its current evidence. It is **not** a completed acceptance record and must not be merged merely because it is checkpointed.

## 1. Verified implementation already on master

- Repository: `techrote/ShadeDoomVK`.
- Accepted dependency baseline before SDVK-002: `master@a2d2d293d680895bb8daae86466596b05aaef483`.
- SDVK-002 implementation publication head: `59cfcaeccbdbd0617e4e032fa153fd91604aa970`.
- PR #121 merged to `master` as `1ecc3cf73aa2266a1e741f09078b7d089ba8bf89` on 8 October 2026.
- Merge tree: `d12e07da15cccddc7f699c140911a5a6f852c4aa`.
- Final implementation-head CI run `37766168263`: **9/9 PASS**, including software Vulkan native qualification.
  - Native artifact `renderer-software-vulkan`: ID `11546975098`, 221,162,106 bytes. PR #121 records uploaded ZIP SHA-256 `75a028ecbc83725eb752d5dd9dbf4b6511609c9789ea13470a3a934f058e66f9`.
  - CPU artifact: ID `11544523182`, 67,598 bytes.
- Exact implementation source-evidence run `37766168248`: PASS.
  - Artifact ID `11544378381`, 147,504,773 bytes. PR #121 records complete source-bundle SHA-256 `ac6b2de8454abad6368141814cc26ee9e90297f9f7a09281dfb0315832760eed`.
- Exact post-merge CI run `37767780123`: **9/9 PASS**, including software Vulkan native qualification.
  - Post-merge native artifact ID `11546439515`, 221,161,272 bytes.
  - Post-merge CPU artifact ID `11546685561`, 67,598 bytes.
- Post-merge exact source-evidence run `37767780437`: PASS; artifact ID `11545956639`, 147,504,860 bytes.

Thus the substantive PR #121 implementation is not being reopened as an unqualified renderer implementation. The remaining problem was exposed while proving the later acceptance-document integration itself.

## 2. Acceptance PR state and newly retained failure

PR #123, `SDVK-002: record verified renderer-observability acceptance`, is open on branch `sdvk-002-acceptance`.

At this checkpoint:

- acceptance branch head: `4edc7efb61dfff234232360b4374fd6ceeb4ff11`;
- PR merge ref exercised by Actions: `c130a5ff19067e89e7d1e8332fa8cd9744ce20fe`;
- branch is seven commits ahead of `master` and changes only seven canonical documentation/receipt files;
- source evidence run `37778174543`: PASS, artifact ID `11551006715`, 147,522,166 bytes;
- CI run `37778174743`: eight jobs PASS; only `Linux software Vulkan | RelWithDebInfo` FAIL.
- CPU artifact ID `11551001680`, 67,597 bytes.
- Failed native artifact: ID `11551965034`, 221,162,581 bytes; uploaded ZIP SHA-256 `def2aa26cf873cc1dd9fe67cf6f6a9403b77c8dd1da3ab8058a3ad188476c3b2`.

The failed lane still passes dependency install, configure, full build, executable identity, llvmpipe preflight, preparation, all state captures, all timing captures and the timing baseline. All native comparisons pass **except** `shadow-boundary-compare`.

The shadow captures themselves both PASS and their decoded RGB output is exact:

- extent: `640 x 480`;
- changed pixels: `0`;
- both RGB SHA-256: `90103e7b5daad044e50b03b63bb04bc124319fd9eff301e57f872a561823ef76`.

The retained comparison first reports only differing selected shadow-map row numbers, for example `573 -> 571`, `404 -> 403`, `388 -> 386`. These are allocator-local row identities; the semantic selected/rejected light decisions are otherwise retained.

## 3. Evidence-driven repair

The local repair is based on `master@1ecc3cf73aa2266a1e741f09078b7d089ba8bf89` and changes exactly six files:

- `tools/renderer_oracle/README.md`
- `tools/renderer_oracle/prepare.py`
- `tools/renderer_oracle/run.py`
- `tools/renderer_oracle/tests/test_corpus.py`
- `tools/renderer_oracle/tests/test_validation.py`
- `tools/renderer_oracle/validate.py`

Diff size: **62 insertions, 7 deletions**.

Exact patch file SHA-256:

`ef0cc4253788861ba266d65366b865a12e1931a7af873d4c8abea252f3f0012b`

The repair has two independent parts.

### 3.1 Normalize renderer-local selected shadow rows without weakening semantics

`state_projection()` now treats a selected non-negative shadow row as a frame-local allocator identity, normalizing rows bijectively by first observation. It deliberately preserves:

- the `-1` capacity-rejection sentinel exactly;
- selected versus rejected decision state;
- row aliasing relationships (two semantic lights unexpectedly sharing one row still fails);
- light identity/order and all other shadow/material/pipeline state.

The regression test `test_shadow_rows_normalize_but_aliasing_and_rejection_remain` proves that changing row numbers alone compares equal, while accidental row aliasing or converting a rejected light into a selected one still compares unequal.

### 3.2 Remove a real fixture ambiguity revealed after row normalization

Re-comparing the retained failed packets using the row normalization does **not** make the old packet pass. Instead it exposes a second state difference:

- one run draws `PLAYA1`;
- the other draws `PLAYA5`;
- corresponding albedo source lump/width differ;
- images remain exact-identical.

The authored fixed camera and the live player start were at the same XY position. That makes the view-relative player-sprite rotation undefined at zero horizontal displacement, allowing otherwise identical runs to choose different player rotations.

`prepare.py` now places the player start 48 map units **behind** the fixed camera according to the authored yaw while leaving the fixed camera itself unchanged. The generated-scene tests require exactly one player start, require it not to coincide with the camera, verify that it lies behind the view direction, and pin the generated metadata.

This is a deterministic test-fixture correction, not a renderer behavior change or an instruction to ignore sprite orientation.

## 4. Verification performed on the repair

- `git diff --check`: PASS.
- Focused renderer-oracle suite: **66/66 PASS** in 2.881 s.
- Focused test log SHA-256: `9b92de32e72aeaabc7fd36b91b78d47ebee176558ca9e57e749e6fcb2e14dd67`.
- Retained acceptance packet re-comparison after **only** the projection-side repair remains FAIL, as expected, because immutable old packets still contain the coincident-player fixture. Re-comparison receipt SHA-256: `c52e310854c748df8e293f3fe04d15cdfc3752c3df4d2e2757e59f433b4d82e4`.
  - This failure is useful evidence: it demonstrates that shadow-row normalization did not simply erase every remaining mismatch; it surfaced the `PLAYA1`/`PLAYA5` fixture problem that requires fresh generated inputs and native captures.
- A full local `python3 tools/check.py` run was attempted but exceeded the available local command window before returning a usable result. The redirected buffered log contained no completed evidence and is not claimed as passing. Full CPU/PF/CFX qualification of this exact six-file repair is therefore **pending**.

The existing PR #123 PF renderer contract job does pass, but it tests the unmodified acceptance branch, not this unpublished six-file repair, so it is not substituted for repair qualification.

## 5. What remains before acceptance

1. Preserve this exact repair independently of the current PR #123 documentation branch.
2. Run the complete CPU/PF/CFX/oracle suite on the repair source and retain its logs.
3. Run the full software-Vulkan native corpus on the repaired generated scenes. In particular, require two new `shadow-boundary` state captures and a passing comparison; do not reuse or relabel the old failed packets.
4. Confirm the shadow boundary still witnesses the intended smallest true overflow: 1,025 candidates, 1,024 selected, one dropped.
5. If those checks pass, integrate the repair through normal PR discipline, then refresh the acceptance receipt to pin the resulting source/CI identities rather than pretending `1ecc3cf7` is still the final source.
6. Re-run exact post-integration checks, verify `master`, merge the acceptance records, and only then close issue #2 and advance dependency gates.

## 6. Stopping conditions

- Do not weaken comparison by deleting player-sprite material identity or shadow selected/rejected semantics.
- Do not treat exact-identical images alone as sufficient state equivalence.
- Do not merge PR #123 while its required CI is red.
- Do not describe the local repair as accepted until full CPU/native CI has exercised the exact repaired source.
- Preserve the failed acceptance artifact and prior successful PR #121/post-merge artifacts as distinct historical evidence.

This checkpoint exists to make the repair recoverable without overstating its verification state.
