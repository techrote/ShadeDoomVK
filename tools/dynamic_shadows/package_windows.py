"""Package exact-head Windows research executable with normal engine resources.

No game IWAD, generated Doom assets or privately held source art is redistributed.
The original PR #190 generator is copied, unchanged, for local user-owned WADs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"vkdoom.exe", "vkdoom.pk3", "zmusic.dll", "openal32.dll", "libsndfile-1.dll",
            "licenses.zip", "soundfonts/vkdoom.sf2", "fm_banks/GENMIDI.GS.wopl",
            "fm_banks/gs-by-papiezak-and-sneakernets.wopn"}
ENGINE_PK3 = {"vkdoom.pk3", "game_support.pk3", "brightmaps.pk3", "lights.pk3", "game_widescreen_gfx.pk3"}
REQUIRED |= ENGINE_PK3


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def collect(build: Path, name: str):
    # CMake copies the complete native runtime to the selected configuration.
    # Do not recursively collect unrelated Debug binaries or fixture resources.
    for root in (build / "RelWithDebInfo", build):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def package(build: Path, flashlight: Path, out: Path, sha: str, material_generator: Path):
    observed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if observed != sha:
        raise ValueError(f"Source HEAD differs: {observed} != {sha}")
    if out.exists():
        raise ValueError("Research package path already exists")
    if not (material_generator / "Build-PR190-Materials.exe").is_file():
        raise ValueError("Standalone original PR190 material generator is missing")
    inputs = {name: collect(build, name) for name in sorted(REQUIRED)}
    missing = sorted(name for name, path in inputs.items() if path is None)
    if missing:
        raise ValueError("Missing compiled native runtime requirements: " + ", ".join(missing))
    for name in sorted(ENGINE_PK3):
        with ZipFile(inputs[name]) as archive:
            if archive.testzip() is not None:
                raise ValueError("Corrupt engine resource archive: " + name)
    with ZipFile(flashlight) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt original flashlight archive")
    out.mkdir(parents=True)
    runtime = out / "runtime"
    runtime.mkdir()
    for name, found in inputs.items():
        dest = runtime / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(found, dest)

    shutil.copyfile(flashlight, out / "Local-Flashlight.pk3")
    toolbox = out / "tools"
    shutil.copytree(ROOT / "tools" / "doom2_showcase", toolbox / "doom2_showcase",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(material_generator, toolbox / "material-generator")
    (toolbox / "dynamic_shadows").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "tools" / "dynamic_shadows" / "build_pr190_materials.py",
                    toolbox / "dynamic_shadows" / "build_pr190_materials.py")
    shutil.copyfile(ROOT / "tools" / "dynamic_shadows" / "Play-Windows.ps1", out / "Play-Windows.ps1")
    (out / "RUN-WINDOWS.cmd").write_text(
        '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Play-Windows.ps1" %*\r\n'
        'set "sdvk_exit=%errorlevel%"\r\nif not "%sdvk_exit%"=="0" pause\r\nexit /b %sdvk_exit%\r\n',
        encoding="ascii", newline=""
    )
    shutil.copyfile(ROOT / "docs" / "shadedoomvk" / "SHADOW-002-DYNAMIC-LIGHT-VISIBILITY.md",
                    out / "SHADOW-002-READ-FIRST.md")
    (out / "local-materials").mkdir(exist_ok=True)
    files = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "PACKAGE-SHA256.json").write_text(json.dumps({
        "source_commit": sha, "base_renderer": "PR195 in master",
        "shader_status": "light-facing source-alpha sprite masks; owner visual acceptance pending",
        "game_iwad_included": False, "original_pr190_generator": True,
        "standalone_material_generator": True,
        "files": files
    }, indent=2) + "\n", encoding="utf-8")
    print(f"WIN_PACKAGE_OK {sha} files={len(files)} total_bytes={sum(p.stat().st_size for p in out.rglob('*') if p.is_file())}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--flashlight", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--material-generator", type=Path, required=True)
    a = p.parse_args()
    package(a.build.resolve(), a.flashlight.resolve(), a.out.resolve(), a.expected_commit,
            a.material_generator.resolve())


if __name__ == "__main__":
    main()
