# Renderer integration backlog — 7 November 2026

This reconciliation keeps demonstrated build and evidence-admission corrections
in PR #172, preserving their original commits as merge parents. It is
tooling integration, not a renderer milestone or a performance acceptance.
The integrated base includes #171 at master
`9cf86b92dac3ae784eea0554d24ca18a43a3120c`.

## Verified guarded integration

| PR | Qualified head | Verified master merge | Qualification |
|---|---|---|---|
| #172 | `e6ac0cad0e197ad626b1bd2d49ab6ce6f6663474` | `ea2e172640f7c05a7f6c8c70bba89975ab5783a0` | [Nine normal jobs](https://github.com/techrote/ShadeDoomVK/actions/runs/42357628391) and [source evidence](https://github.com/techrote/ShadeDoomVK/actions/runs/42357628420) PASS; tree `774c0ccab472b0c7d94d2f44b4eea157f2b43f6d` equals the reviewed head. |
| #162 | `8a0114825f7043576bb5a31b15cbd5e83f1b624d` | `d40475519170606e83dec20dc822ceb5a54312ee` | [Nine normal jobs](https://github.com/techrote/ShadeDoomVK/actions/runs/42356746720) and [source evidence](https://github.com/techrote/ShadeDoomVK/actions/runs/42356746707) PASS; tree `9f70041506a66f1bb29e6fcee2d7d63f83d34c85` equals the reviewed head. |

Both expected-head merges and post-merge trees were verified on 7 November 2026.
#162's [bounded special-surface software scope](SDVK-161-SPECIAL-SURFACE-LIFECYCLE.md)
was qualified at merge, then reopened after the post-merge repeatability failure;
its current software requalification and parent #14's physical criteria are held. PR #186's
weapon/gameplay continuation remains a separately unaccepted integration candidate.

PR #187 is a later optional CI packaging candidate and remains Draft: it conflicts
with current master, must preserve #162's SDVK-161 call/evidence directory, and
must correct the uploaded checksum pathname. Its proposed packaging improvement
has no accepted source-matched performance result. Fourteen obsolete remote heads
were removed with explicit expected-SHA leases after verifying their ancestry;
the non-ancestor original #184 head and frozen physical sources were retained.

## Original backlog decisions

| PR | Original reviewed head | Disposition and reason |
|---|---|---|
| #162 | `ff300c6413b8aeb68ae3130c3824a6b970da4f57` | Reconciled and merged above; substantive SDVK-014 renderer ownership and special surfaces. |
| #167 | `497ca90ae0e6e1cad86dbcb2d9da91c1dd3d61e2` | Close as deferred optimisation; it does not repair the baseline. Its extracted archive allowlist needs reconciliation for #162's new evidence directory. |
| #171 | `0abfa61d08cd00d1ea48cf4e8422ddd0c0e33556` | Independently reviewed and merged; prospective IWAD-bound support custody and separate renderer/oracle identities. |
| #172 | `72c1b3e664782067b5be8ca1f2dd9a9ff2a20951` | Finished and merged above; requires freshly produced CPU fixture executables. |
| #173 | `9670d3f0326fcee72d6d0d786fb34b7683c93d30` | Absorb; distinguish POSIX signal exits from unsigned Windows exception statuses. |
| #174 | `ff27d7b9d6f05ad4806d9def644611f76b811f43` | Absorb and repair its test dependency; matching failed captures cannot pass safe-run comparison. |
| #175 | `5002388de365a45be6b0f1c32cc0a0425df3b139` | Absorb; hash-authenticated extraction must start with a clean ZMusic prefix. |
| #176 | `b6cb6961ffdc91a713fba1840ef6684c574c76a5` | Absorb; verify all six ordered executable identity fields against current source. |
| #177 | `103b9c6d0317f69114a37c2f9ef8b4ad096de113` | Absorb; reject failed, dropped or incomplete native timing intervals before summary. |
| #178 | `ff3a59f37284a36057b4d1e202b0f87f2b2a9a69` | Absorb; source assertions require canonical files within the repository. |
| #179 | `59eeb6b53c7081b0503378478e12d9690beed8b7` | Absorb; RGB comparison extents must be positive bounded integer dimensions. |
| #180 | `6d496f5d4c3f8371374a316b7ee0142890bdfcee` | Absorb; encode valid JSON before reserving an immutable receipt filename. |
| #181 | `b0613b2322a7f61ead1d79f5a28a87ea15417189` | Absorb; malformed producer collections cannot establish imported channel presence. |
| #182 | `4dbafe164a635816d0aaccae87f85335f188a9b0` | Absorb; software-Vulkan summary/full driver and API reports must agree. |
| #183 | `4ec73a285d336291b21861c1b571db8fe7445303` | Absorb; emitted probe selection and packed sunlight must name the same actor. |
| #184 | `179235f1d6466cd6d1ad13413c2a6b8d875585c3` | Absorbed by merged #162; monotonic lightmap resource epochs protect that lifecycle. |

## Preserved failures and boundaries

#174's original PF job in run `42018890623` failed while importing Pillow,
before its new regression methods could execute. The consolidated test loads
the original comparison implementation with an isolated fixed-RGB image reader;
the actual manifest, mesh, pixel metrics and exit-admission paths execute. It
does not install a global stub, skip the regression, add a CI dependency or alter
production image decoding. Actual use of the historical comparison tool still
requires Pillow.

#184's original PF run `42233815131` rejects an old repeatability-test epoch
mutation at the new earlier admission boundary. This failure is retained for its
separate owner; no epoch policy is changed by this integration.

#171 review found no blocking implementation finding. It was a direct child of
the then-current `master@1efde17998305531b1d583a6b53e6f29de857ac4`, with all nine
normal CI jobs and exact-source evidence passing. Independent tests on its clean
exact head passed eight supervisor source/support tests and eleven renderer
support tests (one expected symlink privilege skip). These mocked CPU controls
created no renderer or Vulkan device. The review checked exact IWAD/resource
hashes, package-set equality, separate renderer/oracle heads, legacy packet
compatibility and retained request validation. The merge was subsequently
verified at the base above.

All original feature fixtures, source/CI matrices, image tolerances and native
workloads remain. No physical result, hardware stability, scaling, or renderer
milestone acceptance follows from these CPU/tooling corrections. The normal
exact-head CI and independent integration review were satisfied before #172's
guarded merge above.
