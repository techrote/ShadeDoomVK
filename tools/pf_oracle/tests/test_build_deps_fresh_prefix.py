"""Regression: authenticated archive extraction must not inherit old prefix state."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import fetch_build_deps


class FreshBuildDependencyPrefixTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.output = root / "deps with spaces"
        self.output.mkdir()
        self.outside = root / "outside"
        self.outside.mkdir()
        archive = self.output / "fixture.tar.xz"
        with tarfile.open(archive, "w:xz") as package:
            for library in ("libzmusic", "libzmusiclite"):
                content = library.encode("ascii")
                member = tarfile.TarInfo("zmusic/lib/" + library + ".so")
                member.size = len(content)
                package.addfile(member, io.BytesIO(content))
        self.package = (archive.name, hashlib.sha256(archive.read_bytes()).hexdigest())

    def fetch(self):
        with patch.dict(fetch_build_deps.PACKAGES, linux=self.package):
            return fetch_build_deps.fetch_package("linux", self.output)

    def test_reextraction_discards_unlisted_stale_files(self):
        prefix = self.fetch()
        (prefix / "unexpected-old-file").write_bytes(b"old")
        (prefix / "lib" / "stale.so").write_bytes(b"old")
        prefix = self.fetch()
        self.assertFalse((prefix / "unexpected-old-file").exists())
        self.assertFalse((prefix / "lib" / "stale.so").exists())
        self.assertEqual((prefix / "lib/libzmusic.so.1").read_bytes(), b"libzmusic")

    def test_existing_prefix_symlink_cannot_redirect_extraction(self):
        outside_file = self.outside / "sentinel"
        outside_file.write_bytes(b"must stay intact")
        link = self.output / "zmusic"
        try:
            link.symlink_to(self.outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable to test user: {exc}")
        prefix = self.fetch()
        self.assertFalse(prefix.is_symlink())
        self.assertNotEqual(prefix.resolve(), self.outside.resolve())
        self.assertEqual(outside_file.read_bytes(), b"must stay intact")
        self.assertEqual((prefix / "lib/libzmusiclite.so.1").read_bytes(), b"libzmusiclite")


if __name__ == "__main__":
    unittest.main()
