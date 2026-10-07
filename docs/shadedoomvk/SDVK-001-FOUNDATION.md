# SDVK-001 foundation, identity and build contract

Date: 2026-10-07. Owner: [SDVK-001 / #1](https://github.com/techrote/ShadeDoomVK/issues/1).
Acceptance requires the implementation PR's eight passing jobs, verified merge
on `master` and recorded release evidence. SDVK-002/003 remain gated on that
verified acceptance.

## Checkout and freeze authority

SDVK-001 starts from remote `master@f21fe672cb54c8db3dca8977822d7697493c71ff`,
which contains PF-020 merge `e185e60b04fe37ec84a18c5a85eec6722b541b71` and the
accepted [release receipt](PF-020-RELEASE-ACCEPTANCE.json). Founding VKDoom commit
`09634479ab5bf9adf691074fffe85a006a398cd0` is ancestral to both.

On the current Windows development host, the main checkout `C:/ShadeDoomVK/source`
was fast-forwarded from `844462c3a` to that verified master before creating
`sdvk-001-foundation`. It is the active SDVK development checkout. The PF-020
qualification checkout at `C:/ShadeDoomVK/campaign-worktrees/pf020-native-freeze`,
historical `worktrees/`, `pf-local-evidence/` and their builds retain their
original identities. This supersedes the freeze campaign's instruction that its
checkout was the only mutable source for that campaign. Its receipts remain historical evidence.
Other developers can use any checkout path; [build instructions](../BUILDING.md)
and helpers do not depend on this host's directory spelling.

## Project identity and compatibility boundary

`src/version.h` defines the separate `SDVK_PROJECT_NAME` (`ShadeDoomVK`),
`SDVK_VERSIONSTR` (`0.1.0-dev`), `SDVK_FOUNDING_COMMIT` and
`SDVK_PF_FREEZE_COMMIT`. `CMakeLists.txt` names the build project `ShadeDoomVK`;
the Windows solution and resource product name use that identity.

`GetBuildIdentity()` in `src/common/utility/gitinfo.cpp` supplies the project
version, full build commit, working-tree state, Git description, exact lineage
and PF freeze. Ordinary startup logs print it. `gamemain.cpp` / `toolmain.cpp`
handle a standalone `--version` before platform/game initialization and print
the same text. The existing MSVC CPU prerequisite check still precedes game
entry. `--version` requires neither game content nor rendering.

The inherited identifiers below retain their frozen values:

| Surface | Retained identity / reason |
|---|---|
| Executables and CMake target names | `vkdoom`, `vktool`, `zdoom`, `ztool`, `zengine`; scripts and packaging use them |
| Content resources | `BASEWAD=vkdoom.pk3`, `OPTIONALWAD=game_support.pk3`, existing PK3/font/bank names |
| Config/save/cache/crash paths | `GAMENAME=VKDoom`, `GAMENAMELOWERCASE=vkdoom`, `WGAMENAME`, `GAME_DIR`, existing platform paths |
| Content/scripting engine versions | `VERSIONSTR`, `VER_*`, `ENG_*`, `ZSCRIPT_VER_*`; mod queries keep inherited semantics |
| Save/network/demo/lightmap protocols | `GAMESIG=VKDOOM`, save versions, `NETGAMEVERSION=235`, demo versions, `LIGHTMAPVER=4` |
| OS/platform integration | existing bundle IDs, internal filenames, Discord identity and inherited window captions |

The project version is intentionally separate from inherited engine/content
versions. Renaming config/resource/protocol identifiers would require individual
migration evidence. The compatibility fixture pins the frozen values.

## Build metadata contract

`tools/updaterevision/UpdateRevision.cmake` resolves its own source root, supports
linked worktree `.git` files and tagless/shallow checkouts, and refreshes metadata
at the same commit when state or tags change. Git tags are escaped as C++ string
data. A source archive cannot borrow a containing repository's identity.

`src/CMakeLists.txt` generates the header inside each build directory at
configure time and refreshes it through `revision_check`. Compiler/resource
includes select that generated header ahead of any historical source header.
No generated metadata is written into tracked source. `clean` means Git found
no staged/unstaged or nonignored untracked files; `modified` records those
changes without pretending the commit alone identifies all compiled bytes.
Archives or unavailable Git report commit `0` / state `unknown`.

The existing checked-in Windows dependencies are staged for the default bundled
x64 build. The existing Linux/macOS ZMusic 1.1.14 packages are verified by SHA-256
before extraction. [Build documentation](../BUILDING.md) specifies compiler,
dependency and runtime paths. Reproducibility here covers declared inputs and
commands; it is not a universal binary-reproducibility claim.

The executable checks exposed two inherited startup gaps that compilation alone
did not catch. The authenticated ZMusic packages omit their versioned loader
filenames; extraction now supplies byte-identical runtime aliases. The ordinary
POSIX `FStringData` allocator requested four-byte aligned storage, which a strict
aligned allocator rejects. It now uses `malloc` with a compile-time fundamental
alignment check, retaining the string layout, requested capacity, overflow checks
and matching `free`. Windows retains its existing allocation/free pair. The
production-method fixture retains the pre-fix failure and checks small storage,
growth, overflow and allocation failure; native macOS CI checks the real startup.
The [pre-fix native debugger job](https://github.com/techrote/ShadeDoomVK/actions/runs/37635432959/job/112841654502)
traces the exception to `FStringData::Alloc` while a console-command initializer
runs before `main`. This is a startup portability repair, with no donor source
transplant or renderer algorithm change.

## Verification and acceptance

- Clean Windows configure/build using the documented Visual Studio commands.
- Complete `tools/check.py`: PF/SDVK unittests, CFX classification, four compiled
  contracts and two identical oracle outputs; logs retained under `build/`.
- Real Git/CMake metadata controls: tagless source, dirty/clean transitions at
  one commit, untracked source, unchanged header timestamp, linked worktree,
  nested non-Git archive, unavailable Git and punctuated tag compiled into diagnostics.
- Compiled production entry points with platform witnesses: standalone
  `--version` returns before platform initialization; ordinary/unknown/mixed
  arguments reach the inherited startup path.
- Both built executables' provenance smoke checks from an empty working directory.
- Eight hosted jobs preserve the inherited Windows/macOS/Linux matrix and add
  actual executable identity checks. Linux builds qualify the documented path.

This issue changes build/startup/provenance surfaces. It adds no renderer feature,
donor engine source, gameplay/protocol change or PF optimization. GPL and inherited
third-party notices remain in place; `licenses.zip` accompanies staged bundled
Windows dependencies. SDVK-003 owns subsequent upstream differential/import work.
