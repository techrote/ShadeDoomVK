#!/usr/bin/env python3
"""Fetch the hash-pinned ZMusic packages used by hosted CI. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import urllib.request

PACKAGES = {
    "linux": ("zmusic-1.1.14-linux.tar.xz",
              "b25b03f78893d6de018c6e620ab6aaddc8618363012bf7388388815a5ddb1f78"),
    "macos": ("zmusic-1.1.14-macos-arm.tar.xz",
              "395419c9d6f53e941e77148ec9b5bd4f88ccb66f86f33ad820a65f3a4e25795b"),
}
RELEASE = "https://github.com/ZDoom/gzdoom/releases/download/ci_deps/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=PACKAGES, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/deps"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    name, digest = PACKAGES[args.platform]
    archive = args.output / name
    if archive.exists():
        data = archive.read_bytes()
    else:
        with urllib.request.urlopen(RELEASE + name, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(f"SHA-256 mismatch: {name}; dependency was not extracted")
    if not archive.exists():
        archive.write_bytes(data)
    # Extraction is permitted only after the exact known archive is authenticated.
    subprocess.run(["tar", "-xf", str(archive.resolve()), "-C", str(args.output.resolve())], check=True)
    print(f"Verified {name}: {digest}\nZMusic prefix: {(args.output / 'zmusic').resolve()}")


if __name__ == "__main__":
    main()
