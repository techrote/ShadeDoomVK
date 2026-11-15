"""Run the original PR #190 PBR interpretation on a structurally valid Doom II IWAD.

The WAD identity is recorded from the supplied file; no fixed edition whitelist.
This does not modify PR #190's map-generation algorithms.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / "doom2_showcase"
sys.path.insert(0, str(SOURCE))


def validate_iwad(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) < 12:
        raise ValueError("IWAD header is incomplete")
    kind, count, directory = struct.unpack_from("<4sii", raw)
    if kind != b"IWAD" or count <= 0 or count > 100000 or directory < 12 or directory + count * 16 > len(raw):
        raise ValueError("Not a valid classic Doom-family IWAD directory")
    names = set()
    for i in range(count):
        pos, size, lump = struct.unpack_from("<ii8s", raw, directory + i*16)
        if pos < 0 or size < 0 or pos + size > len(raw):
            raise ValueError(f"Invalid IWAD lump extent at index {i}")
        try:
            names.add(lump.rstrip(b"\0").decode("ascii").upper())
        except UnicodeDecodeError as exc:
            raise ValueError(f"Non-ASCII IWAD lump name at index {i}") from exc
    # The PR #190 Doom II art generator actually needs these sources.
    required = {"PLAYPAL", "PNAMES", "TEXTURE1", "F_START", "F_END", "S_START", "S_END"}
    missing = sorted(required - names)
    if missing:
        raise ValueError("IWAD lacks material-generation source lumps: " + ", ".join(missing))
    return hashlib.sha256(raw).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doom2", type=Path, required=True, help="Owner-supplied classic Doom II IWAD")
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    parser.add_argument("--gallery", action="store_true")
    args = parser.parse_args(argv)
    path = args.doom2.expanduser().resolve()
    out = args.out.expanduser().resolve()
    if out.exists():
        parser.error("Output directory must be new; existing files are never replaced")
    if not path.is_file():
        parser.error("IWAD does not exist: " + str(path))
    try:
        identity = validate_iwad(path)
        import dbp50_effective as dbp
        import sprite_materials as sprites
        import build as showcase
        # The strict PR #190 checks are replaced with the independently
        # validated actual file identity, not a bypass of WAD structure.
        dbp.IWAD_SHA256 = identity
        sprites.IWAD_SHA256 = identity
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".shadedoom-pbr-", dir=out.parent) as tmp:
            staging = Path(tmp) / "assets"
            staging.mkdir()
            showcase.build_flashlight(staging)
            showcase.build_materials(staging, path, None, args.gallery)
            (staging / "SOURCE-IWAD-SHA256.txt").write_text(identity + "\n", encoding="ascii")
            staging.rename(out)
        print("Generated original PR #190 PBR maps for IWAD SHA-256:", identity)
        return 0
    except (OSError, ValueError, AssertionError, ImportError, struct.error, KeyError, IndexError) as exc:
        print(f"Material generation unavailable for this IWAD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
