"""SDVK-001: authenticated dependency extraction and loader filenames."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import fetch_build_deps


class BuildDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "dependency prefix with spaces"
        self.output.mkdir()

    def package(self, platform, extension):
        name = "fixture.tar.xz"
        archive = self.output / name
        with tarfile.open(archive, "w:xz") as package:
            for library in ("libzmusic", "libzmusiclite"):
                content = (platform + " " + library).encode()
                entry = tarfile.TarInfo(f"zmusic/lib/{library}{extension}")
                entry.size = len(content)
                package.addfile(entry, io.BytesIO(content))
        return name, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_linux_package_supplies_elf_loader_names(self):
        package = self.package("linux", ".so")
        with patch.dict(fetch_build_deps.PACKAGES, linux=package):
            prefix = fetch_build_deps.fetch_package("linux", self.output)
            for library in ("libzmusic", "libzmusiclite"):
                self.assertEqual((prefix / "lib" / (library + ".so.1")).read_bytes(),
                                 ("linux " + library).encode())
            # Re-extraction must repair an old/mismatched loader alias as well.
            (prefix / "lib/libzmusic.so.1").write_bytes(b"stale dependency")
            fetch_build_deps.fetch_package("linux", self.output)
            self.assertEqual((prefix / "lib/libzmusic.so.1").read_bytes(), b"linux libzmusic")

    def test_macos_package_supplies_macho_loader_names(self):
        package = self.package("macos", ".dylib")
        with patch.dict(fetch_build_deps.PACKAGES, macos=package):
            prefix = fetch_build_deps.fetch_package("macos", self.output)
        for library in ("libzmusic", "libzmusiclite"):
            self.assertEqual((prefix / "lib" / (library + ".1.dylib")).read_bytes(),
                             ("macos " + library).encode())

    def test_tampered_cached_archive_is_never_extracted_or_downloaded(self):
        name, digest = self.package("linux", ".so")
        (self.output / name).write_bytes(b"untrusted archive")
        with patch.dict(fetch_build_deps.PACKAGES, linux=(name, digest)), \
                patch.object(fetch_build_deps.urllib.request, "urlopen") as download, \
                patch.object(fetch_build_deps.subprocess, "run") as extract:
            with self.assertRaisesRegex(SystemExit, "SHA-256 mismatch"):
                fetch_build_deps.fetch_package("linux", self.output)
            download.assert_not_called()
            extract.assert_not_called()
        self.assertFalse((self.output / "zmusic").exists())
