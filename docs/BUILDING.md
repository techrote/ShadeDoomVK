# Building and running ShadeDoomVK

Run commands from the repository root. The build is C++17 and requires Git,
CMake **3.24 or newer**, a native compiler and Python **3.10 or newer** for the
checks/helpers. [CMake binary distributions](https://cmake.org/download/) are
available when your distribution's CMake is too old. Ubuntu 22.04's stock CMake
is below the project's minimum; check `cmake --version` before configuring.

The commands establish reproducible source/dependency/configuration inputs.
They do not promise byte-identical binaries across toolchain/OS versions.
Record `git rev-parse HEAD`, compiler version, `cmake --version`, build type and
`--version` output when reporting a problem.

## Checkout and build directories

```text
git clone https://github.com/techrote/ShadeDoomVK.git
cd ShadeDoomVK
git status --short
```

For an existing checkout, inspect local changes, fetch `origin`, then fast-forward
`master` with `git merge --ff-only origin/master` before creating an issue branch.
Never reset existing work to make a checkout clean. Use a new directory under
`build/` for a new generator/compiler/configuration. Historical native captures
and qualified binaries keep their original checkout/build identities.

## Windows x64 / Visual Studio 2022

Install Visual Studio 2022 or Build Tools with **Desktop development with C++**,
the MSVC x64 tools and Windows SDK. For CPU tests, use its **x64 Native Tools
Command Prompt** or Developer PowerShell configured for x64; [Microsoft's command
line setup instructions](https://learn.microsoft.com/en-us/cpp/build/building-on-the-command-line?view=msvc-170)
describe both. `cl`, `cmake`, `git` and `python` must be available in that shell.

```text
cmake -S . -B build/windows -G "Visual Studio 17 2022" -A x64 -DPK3_QUIET_ZIPDIR=ON
cmake --build build/windows --config RelWithDebInfo --parallel 3
python tools/check.py --output build/checks-windows
python tools/check_build_identity.py --build-dir build/windows --config RelWithDebInfo
```

The solution is `build/windows/ShadeDoomVK.sln`. The default outputs are
`build/windows/RelWithDebInfo/vkdoom.exe`, `vktool.exe`, generated PK3 resources,
soundfonts and FM banks. The bundled x64 dependency path stages `zmusic.dll`,
`libsndfile-1.dll`, `openal32.dll` and `licenses.zip` beside both executables.
Windows ZMusic and libvpx import libraries/headers are checked into `bin/windows`;
no Vulkan SDK or vcpkg download is required for this default path. The Vulkan
loader and a suitable graphics driver are required for actual rendering.

The inherited MSVC x64 build requires **AVX2**. Use `--config Debug` for a Debug
build and pass the same configuration to the identity check. Custom dependency
prefixes and other architectures need their own matching runtime packaging;
the automatic DLL staging above is scoped to the bundled x64 configuration.

To inspect provenance directly in PowerShell:

```powershell
& .\build\windows\RelWithDebInfo\vkdoom.exe --version | Out-String
& .\build\windows\RelWithDebInfo\vktool.exe --version | Out-String
```

To play, replace the example path with your own IWAD:

```powershell
& .\build\windows\RelWithDebInfo\vkdoom.exe -iwad "C:\Games\Doom\doom2.wad"
```

## Linux x86_64 / Ubuntu 22.04 CI baseline

Install CMake >=3.24 separately if needed, then the native dependencies:

```bash
sudo apt update
sudo apt install build-essential gcc-12 g++-12 git python3 libsdl2-dev libvpx-dev libgtk-3-dev libwebp-dev
python3 tools/fetch_build_deps.py --platform linux --output build/deps
cmake -S . -B build/linux -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=gcc-12 -DCMAKE_CXX_COMPILER=g++-12 \
  -DCMAKE_PREFIX_PATH="$PWD/build/deps/zmusic" -DPK3_QUIET_ZIPDIR=ON
cmake --build build/linux --parallel 3
python3 tools/check.py --output build/checks-linux
LD_LIBRARY_PATH="$PWD/build/deps/zmusic/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  python3 tools/check_build_identity.py --build-dir build/linux
```

The outputs include `build/linux/vkdoom`, `vktool` and generated PK3 resources.
Use the same library path when running with the downloaded ZMusic package:

```bash
LD_LIBRARY_PATH="$PWD/build/deps/zmusic/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  ./build/linux/vkdoom -iwad /path/to/doom2.wad
```

An SDL/display session and a Vulkan loader/driver are needed for play. OpenAL is
loaded dynamically by default. A compile-time OpenAL build uses
`-DDYN_OPENAL=OFF` plus `libopenal-dev`, as in the Clang 11 Debug CI job.
Installed ZMusic may replace the pinned package via `CMAKE_PREFIX_PATH`; record
its version and runtime library resolution when doing so.

## Pinned dependencies and CI

`tools/fetch_build_deps.py` verifies these existing upstream release assets
before extracting them. A mismatched cached/downloaded archive fails closed.

| CI platform | ZMusic archive | SHA-256 |
|---|---|---|
| Linux x86_64 | `zmusic-1.1.14-linux.tar.xz` | `b25b03f78893d6de018c6e620ab6aaddc8618363012bf7388388815a5ddb1f78` |
| macOS ARM64 | `zmusic-1.1.14-macos-arm.tar.xz` | `395419c9d6f53e941e77148ec9b5bd4f88ccb66f86f33ad820a65f3a4e25795b` |

Source: [ZDoom/gzdoom CI dependency release](https://github.com/ZDoom/gzdoom/releases/tag/ci_deps).
These are dependency packages, not an upstream source import. OS packages and
hosted toolchain images remain externally maintained; the workflow records the
actual compiler/configuration output.

`.github/workflows/continuous_integration.yml` retains eight jobs: the CPU oracle,
two Visual Studio configurations, two macOS configurations and three Linux
GCC/Clang configurations. The CPU job uses the same `tools/check.py` command as
developers, preserving the full unittest suite, crash classification, four
standalone C++ contracts and two byte-identical source oracle outputs. Its logs
are uploaded even on failure. Every build job also runs both actual executables'
`--version` from an empty directory without a display or IWAD.

macOS retains the inherited ARM64 hosted builds. Install libvpx with Homebrew,
fetch `--platform macos`, configure with the resulting ZMusic prefix, and use
`DYLD_LIBRARY_PATH` for its `lib` directory when checking a local build. The
single-configuration application is `build/vkdoom.app/Contents/MacOS/vkdoom`; the
tool is `build/vktool`. Xcode places both under `build/<configuration>/`; pass that
configuration to the identity checker, which reads the generator's cache layout.
Packaging/deployment of a standalone macOS app remains outside this foundation.

## Diagnostics and common setup failures

`tools/check.py` writes step logs and oracle JSON under its `--output` directory.
It runs CPU fixtures only. A missing compiler, fixture failure or changed oracle
is an error; none are skipped. `PF_CXX` / `CFX_CXX` can select explicit compiler
executables, but MSVC still requires the developer environment's include/lib
paths. Restricted environments must permit executable/temp/hard-link fixtures.

Build metadata is generated per build at `src/generated/gitinfo.h` within that
build directory. `revision_check` refreshes it during each build, including
tracked or nonignored untracked changes at the same commit. A source archive
without its own `.git` reports commit `0` and state `unknown`, even if stored
inside another repository. Unchanged metadata does not force recompilation.

`tools/check_build_identity.py` checks both executable outputs against checkout
HEAD and the project lineage constants. Add `--expected-state clean` when
verifying a committed clean build. This is a startup/provenance check; renderer
state/image and performance evidence remains governed by the PF/SDVK contracts.
