"""SDVK-156 exact current-source and pinned historical atlas fixture inputs."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
RETAINED = Path(__file__).parent / 'fixtures/sdvk156-pre-fix'


def retained_files() -> dict:
    manifest = json.loads((RETAINED / 'manifest.json').read_text())
    for name, pin in manifest['files'].items():
        data = (RETAINED / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != pin['sha256'] or hashlib.sha1(
                b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != pin['git_blob']:
            raise AssertionError('Changed retained SDVK-156 input: ' + name)
    return manifest['files']


def retain_atlas_headers(directory: Path) -> None:
    retained_files()
    for name in ('hw_rectpacker.h', 'hw_lightmaptile.h'):
        (directory / name).write_bytes((RETAINED / name).read_bytes())
