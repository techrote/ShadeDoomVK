"""Strict, bounded evidence I/O shared by the SDVK renderer harness.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MAX_JSON_BYTES = 64 * 1024 * 1024


class EvidenceError(ValueError):
    """An input cannot support the requested evidence claim."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise EvidenceError(f"Nonfinite JSON value: {value}")


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite evidence number")
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def read_json(path, maximum=MAX_JSON_BYTES):
    path = Path(path)
    require(path.is_file(), f"Missing JSON file: {path}")
    require(0 < path.stat().st_size <= maximum, f"JSON size out of bounds: {path}")
    try:
        result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object,
                            parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise EvidenceError(f"Invalid JSON in {path}: {error}") from error
    finite(result)
    return result


def canonical(value):
    finite(value)
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value):
    """Write a fresh artifact; never silently replace an earlier attempt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path, *, relative_to=None):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), f"Expected a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    name = str(path) if relative_to is None else path.relative_to(Path(relative_to).resolve()).as_posix()
    return {"path": name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def artifact_path(root, name):
    require(isinstance(name, str) and name and "\\" not in name and "\0" not in name,
            "Artifact must have a nonempty POSIX relative path")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/"))
            and ":" not in name, "Artifact path escapes or aliases the run directory")
    root = Path(root).resolve(strict=True)
    path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink(), "Evidence artifact may not be a symlink")
    require(path.resolve().is_relative_to(root), "Evidence artifact escapes the run directory")
    return path


def checked(root, expected, *, maximum=None):
    require(isinstance(expected, dict) and set(expected) == {"path", "bytes", "sha256"},
            "Artifact identity must contain path, bytes and sha256")
    require(type(expected["bytes"]) is int and expected["bytes"] >= 0, "Invalid artifact size")
    require(isinstance(expected["sha256"], str) and len(expected["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in expected["sha256"]), "Invalid SHA-256")
    path = artifact_path(root, expected["path"])
    require(path.is_file(), f"Missing artifact: {expected['path']}")
    if maximum is not None:
        require(expected["bytes"] <= maximum, "Artifact exceeds declared resource bound")
    require(pin(path, relative_to=root) == expected, f"Artifact identity changed: {expected['path']}")
    return path


def number(value, label, *, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum,
            f"Invalid {label}; expected a finite number >= {minimum}")
    return value


def integer(value, label, *, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and (maximum is None or value <= maximum),
            f"Invalid {label}; expected an integer in the declared bounds")
    return value
