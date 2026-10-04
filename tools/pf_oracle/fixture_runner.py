#!/usr/bin/env python3
"""Compile and run CPU-only PF fixtures with the native C++ toolchain.

Compiler absence, warnings, compilation errors and fixture failures are errors,
never reasons to skip a required fixture. All compiler outputs stay outside the
source tree. This helper does not launch the renderer or any GPU workload.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]


def select_compiler(*, environment: Mapping[str, str] | None = None,
                    windows: bool | None = None) -> str:
    """Select an executable, not a shell command or a string of flags."""
    environment = os.environ if environment is None else environment
    windows = os.name == "nt" if windows is None else windows
    requested = environment.get("PF_CXX") or ("cl" if windows else "c++")
    compiler = shutil.which(requested)
    if not compiler:
        raise RuntimeError(
            f"PF CPU fixture compiler unavailable: {requested!r}. "
            "Use a VS developer shell on Windows or install a C++17 compiler; "
            "PF_CXX may name an explicit compiler executable."
        )
    return compiler


def is_msvc(compiler: str) -> bool:
    # Also recognize Windows paths when command-construction tests run on Unix.
    return Path(compiler.replace("\\", "/")).name.lower() in ("cl", "cl.exe")


def compilation_command(compiler: str, source: Path, includes: Iterable[Path],
                        executable: Path) -> list[str]:
    """Build an argv vector with assertions and warnings-as-errors enabled."""
    if is_msvc(compiler):
        return [
            compiler, "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/UNDEBUG",
            str(source), *["/I" + str(path) for path in includes],
            "/Fe:" + str(executable), "/Fo:" + str(executable.with_suffix(".obj")),
            "/Fd:" + str(executable.with_suffix(".pdb")),
        ]
    return [
        compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-UNDEBUG",
        str(source), *["-I" + str(path) for path in includes], "-o", str(executable),
    ]


def _root_path(path: str | Path, root: Path) -> Path:
    path = Path(path)
    return (path if path.is_absolute() else root / path).resolve()


def compile_fixture(source: str | Path, *, output_dir: str | Path,
                    includes: Iterable[str | Path] = (), root: str | Path = ROOT,
                    name: str | None = None, compiler: str | None = None) -> Path:
    """Compile one fixture; the caller owns its output directory's lifetime."""
    root = Path(root).resolve()
    source = _root_path(source, root)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise FileNotFoundError(f"PF CPU fixture source missing: {source}")
    name = source.stem if name is None else name
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("Fixture name must be a single filename component")
    compiler = select_compiler() if compiler is None else compiler
    executable = output_dir / (name + (".exe" if os.name == "nt" or is_msvc(compiler) else ""))
    command = compilation_command(
        compiler, source, [_root_path(path, root) for path in includes], executable
    )
    # MSVC may emit ancillary files; compile in the output directory as well as
    # naming object/PDB outputs explicitly so none can enter a source checkout.
    subprocess.run(command, cwd=output_dir, check=True, timeout=120)
    if not executable.is_file():
        raise RuntimeError(f"PF CPU compiler succeeded without an executable: {executable}")
    return executable


def run_fixture(source: str | Path, *, includes: Iterable[str | Path] = (),
                root: str | Path = ROOT, args: Sequence[str] = (),
                name: str | None = None, timeout: float = 30,
                compiler: str | None = None,
                capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Compile into a temporary directory, then execute with the inherited cwd."""
    with tempfile.TemporaryDirectory(prefix="pf-cpu-fixture-") as directory:
        executable = compile_fixture(
            source, output_dir=directory, includes=includes, root=root,
            name=name, compiler=compiler
        )
        return subprocess.run(
            [str(executable), *args], cwd=Path(root).resolve(), check=True,
            timeout=timeout, capture_output=capture_output, text=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Root-relative or absolute CPU fixture source")
    parser.add_argument("--include", action="append", default=[], help="Repeat for each include directory")
    parser.add_argument("--root", type=Path, default=ROOT, help="Source root and fixture execution cwd")
    parser.add_argument("--name", help="Optional executable filename stem")
    parser.add_argument("--compiler", help="Explicit compiler executable; otherwise PF_CXX/native default")
    parser.add_argument("--timeout", type=float, default=30, help="Fixture execution timeout in seconds")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Fixture arguments after --")
    options = parser.parse_args(argv)
    args = options.args[1:] if options.args[:1] == ["--"] else options.args
    run_fixture(options.source, includes=options.include, root=options.root,
                name=options.name, timeout=options.timeout, compiler=options.compiler,
                args=args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
