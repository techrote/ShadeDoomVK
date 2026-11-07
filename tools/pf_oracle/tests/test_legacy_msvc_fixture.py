"""Legacy-header portability never disables errors in actual fixture code."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.tests.legacy_msvc_fixture import compile_legacy_fixture


class LegacyHeaderWarningBoundaryTests(unittest.TestCase):
    def test_deprecation_outside_legacy_headers_still_fails_compilation(self):
        with tempfile.TemporaryDirectory(prefix='legacy-warning-boundary-') as directory:
            root = Path(directory)
            fixture = root / 'outside_scope.cpp'
            fixture.write_text(
                '[[deprecated("fixture warning must remain fatal")]] int old_api() { return 0; }\n'
                'int main() { return old_api(); }\n', encoding='utf-8', newline='\n')
            with self.assertRaises(subprocess.CalledProcessError):
                compile_legacy_fixture(fixture, output_dir=root, includes=[])


if __name__ == '__main__':
    unittest.main()
