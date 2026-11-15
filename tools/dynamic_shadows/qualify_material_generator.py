"""Compare the frozen local generator with the unchanged PR190 algorithms.

Only purpose-built, copyright-free IWADs are used. No owner's game bytes are
required or included in the qualification output or Windows artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]


def synthetic_iwad(path: Path, map_name: str):
    """A small valid classic texture/flat/sprite source, not a playable game."""
    width, height = 16, 32
    columns = []
    for x in range(width):
        pixels = bytes(1 + (x + y) % 2 for y in range(height))
        columns.append(bytes((0, height, 0)) + pixels + bytes((0, 255)))
    base = 8 + width * 4
    patch = struct.pack("<hhhh", width, height, 8, height)
    patch += b"".join(struct.pack("<I", base + sum(map(len, columns[:x]))) for x in range(width))
    patch += b"".join(columns)
    texture = struct.pack("<8sIhhIh", b"STONE001", 0, width, height, 0, 1)
    texture += struct.pack("<hhhhh", 0, 0, 0, 0, 0)
    palette = bytearray(768)
    palette[3:9] = bytes((96, 96, 96, 170, 70, 35))
    lumps = [("PLAYPAL", bytes(palette)), ("PNAMES", struct.pack("<I8s", 1, b"WALLPTCH")),
             ("TEXTURE1", struct.pack("<II", 1, 8) + texture), ("WALLPTCH", patch),
             ("F_START", b""), ("FLAT0001", bytes(1 + (x // 8 + y // 8) % 2 for y in range(64) for x in range(64))),
             ("F_END", b""), ("S_START", b""), ("POSSA1", patch), ("S_END", b""),
             (map_name, b"")]
    body = bytearray()
    directory = bytearray()
    for name, payload in lumps:
        directory += struct.pack("<ii8s", 12 + len(body), len(payload), name.encode("ascii"))
        body += payload
    path.write_bytes(struct.pack("<4sii", b"IWAD", len(lumps), 12 + len(body)) + body + directory)


def contents(path: Path):
    """Archive timestamps are packaging metadata; compare every actual member."""
    with ZipFile(path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("Invalid generated archive: " + str(path))
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in sorted(archive.namelist())}


def qualify(generator: Path, out: Path):
    if out.exists():
        raise ValueError("Qualification output must be new")
    out.mkdir(parents=True)
    cases = []
    for name in ("MAP01", "E1M1"):
        case = out / name
        case.mkdir()
        iwad = case / "synthetic.wad"
        synthetic_iwad(iwad, name)
        commands = {
            "python": [sys.executable, str(ROOT / "tools/dynamic_shadows/build_pr190_materials.py")],
            "frozen": [str(generator)],
        }
        for kind, command in commands.items():
            result = subprocess.run(command + ["--doom2", str(iwad), "--out", str(case / kind)],
                                    capture_output=True, text=True, timeout=120)
            (case / (kind + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
            (case / (kind + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
            if result.returncode:
                raise ValueError(f"{kind} material generator failed for synthetic {name}: {result.stderr}")
        packs = {}
        for filename in ("DoomII-NormalPBR.pk3", "DoomII-SpritePBR.pk3", "Local-Flashlight.pk3"):
            source = contents(case / "python" / filename)
            frozen = contents(case / "frozen" / filename)
            if not source or source != frozen:
                raise ValueError(f"Frozen generator differs from original algorithm output: {name}/{filename}")
            packs[filename] = {"members": len(source), "member_sha256": source}
        report = json.loads((case / "frozen/material-build.json").read_text())
        if report["DoomII"]["world_bindings"] != 2 or report["DoomII"]["sprite_bindings"] < 1:
            raise ValueError("Synthetic output lacks world or actor PBR bindings")
        cases.append({"map_family": name, "iwad_sha256": hashlib.sha256(iwad.read_bytes()).hexdigest(),
                      "packs": packs, "material_build": report})
    receipt = {"status": "PASS", "scope": "frozen versus original PR190 synthetic local material generation",
               "private_game_bytes": False, "generator_sha256": hashlib.sha256(generator.read_bytes()).hexdigest(),
               "cases": cases}
    (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("PR190_GENERATOR_QUALIFICATION_PASS synthetic MAP01/E1M1, every archive member identical")
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generator", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    qualify(a.generator.resolve(), a.out.resolve())


if __name__ == "__main__":
    main()
