"""SDVK-001: real Git/CMake metadata, entry-point bypass and compatibility pins."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / "source with spaces"
        script_dir = self.repo / "tools/updaterevision"
        script_dir.mkdir(parents=True)
        for name in ("UpdateRevision.cmake", "gitinfo.h.in"):
            shutil.copyfile(ROOT / "tools/updaterevision" / name, script_dir / name)
        self.script = script_dir / "UpdateRevision.cmake"
        self.header = self.directory / "generated/gitinfo.h"
        self.git("init", "--quiet")
        self.git("config", "core.autocrlf", "false")
        (self.repo / "tracked.txt").write_text("original\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=SDVK fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "fixture")

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.repo), *arguments],
                                       text=True, stderr=subprocess.STDOUT).strip()

    def generate(self, script=None, output=None, environment=None):
        output = output or self.header
        subprocess.run([shutil.which("cmake"), "-P", str(script or self.script), str(output)],
                       cwd=self.directory, env=environment, check=True, capture_output=True, text=True)
        return {name: json.loads(value) for name, value in re.findall(
            r'^#define (GIT_\w+) (".*")$', output.read_text(encoding="utf-8"), re.MULTILINE)}

    def compile(self, source, name):
        wrapper = self.directory / (name + ".cpp")
        wrapper.write_text(source, encoding="utf-8")
        return compile_fixture(wrapper, output_dir=self.directory / name,
                               includes=[self.header.parent, ROOT / "src"], name=name)

    def test_tagless_checkout_from_unrelated_working_directory(self):
        identity = self.generate()
        self.assertEqual(identity["GIT_HASH"], self.git("rev-parse", "HEAD"))
        self.assertEqual(identity["GIT_STATE"], "clean")
        self.assertNotEqual(identity["GIT_DESCRIPTION"], "<unknown version>")

    def test_dirty_and_clean_transitions_at_same_commit(self):
        original = self.generate()
        original_bytes = self.header.read_bytes()
        (self.repo / "tracked.txt").write_text("modified\n", encoding="utf-8")
        modified = self.generate()
        self.assertEqual(modified["GIT_HASH"], original["GIT_HASH"])
        self.assertEqual(modified["GIT_STATE"], "modified")
        self.assertTrue(modified["GIT_DESCRIPTION"].endswith("-m"))
        self.git("checkout", "--", "tracked.txt")
        self.generate()
        self.assertEqual(self.header.read_bytes(), original_bytes)

    def test_unchanged_metadata_does_not_touch_header(self):
        self.generate()
        original_time = self.header.stat().st_mtime_ns
        self.generate()
        self.assertEqual(self.header.stat().st_mtime_ns, original_time)

    def test_nonignored_untracked_source_marks_build_modified(self):
        self.generate()
        (self.repo / "new-source.cpp").write_text("int added;\n", encoding="utf-8")
        self.assertEqual(self.generate()["GIT_STATE"], "modified")

    def test_linked_worktree_uses_its_own_commit(self):
        worktree = self.directory / "linked checkout"
        self.git("worktree", "add", "--quiet", "--detach", str(worktree), "HEAD")
        self.assertTrue((worktree / ".git").is_file())
        identity = self.generate(worktree / "tools/updaterevision/UpdateRevision.cmake")
        self.assertEqual(identity["GIT_HASH"], self.git("rev-parse", "HEAD"))
        self.assertEqual(identity["GIT_STATE"], "clean")

    def test_archive_inside_another_repo_is_explicitly_unknown(self):
        archive = self.repo / "archive/tools/updaterevision"
        archive.mkdir(parents=True)
        shutil.copyfile(self.script, archive / self.script.name)
        shutil.copyfile(self.script.parent / "gitinfo.h.in", archive / "gitinfo.h.in")
        identity = self.generate(archive / self.script.name)
        self.assertEqual(identity["GIT_HASH"], "0")
        self.assertEqual(identity["GIT_STATE"], "unknown")

    def test_unavailable_git_reports_unknown_identity(self):
        environment = dict(os.environ, PATH=str(self.directory / "no-programs"))
        identity = self.generate(environment=environment)
        self.assertEqual(identity["GIT_HASH"], "0")
        self.assertEqual(identity["GIT_STATE"], "unknown")

    def test_punctuated_tag_is_data_in_compiled_diagnostics(self):
        # A quote is valid in Unix refs; Windows loose refs require NTFS names.
        tag = "v;punctuation" if os.name == "nt" else 'v"quoted'
        self.git("tag", tag)
        identity = self.generate()
        self.assertEqual(identity["GIT_DESCRIPTION"], tag)
        implementation = (ROOT / "src/common/utility/gitinfo.cpp").as_posix()
        exe = self.compile(f'#include "{implementation}"\n'
                           'int main() { return PrintVersionIfRequested(L"--version") ? 0 : 1; }\n',
                           "quoted-version")
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
        self.assertIn("Git description: " + tag, result.stdout)
        self.assertIn("ShadeDoomVK 0.1.0-dev", result.stdout)

    def test_real_entry_points_bypass_platform_startup_only_for_version(self):
        identity = self.generate()
        implementation = (ROOT / "src/common/utility/gitinfo.cpp").as_posix()
        for source, backend in (("gamemain.cpp", "I_GameMain"), ("toolmain.cpp", "I_ToolMain")):
            with self.subTest(source=source):
                entry = (ROOT / "src" / source).as_posix()
                exe = self.compile(f'#include "{implementation}"\n#undef WIN32\n'
                                   f'int {backend}(int, char**) {{ std::puts("platform-startup"); return 42; }}\n'
                                   f'#include "{entry}"\n', source.replace(".cpp", ""))
                result = subprocess.run([str(exe), "--version"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertNotIn("platform-startup", result.stdout)
                self.assertIn("Commit: " + identity["GIT_HASH"], result.stdout)
                for args in ([], ["--version-extra"], ["--version", "-iwad", "missing.wad"]):
                    normal = subprocess.run([str(exe), *args], capture_output=True, text=True)
                    self.assertEqual(normal.returncode, 42)
                    self.assertEqual(normal.stdout.strip(), "platform-startup")

    def test_compatibility_identifiers_keep_frozen_values(self):
        header = (ROOT / "src/version.h").read_text(encoding="utf-8")
        defines = dict(re.findall(r'^#define (\w+) (.+)$', header, re.MULTILINE))
        expected = {
            "GAMESIG": '"VKDOOM"', "BASEWAD": '"vkdoom.pk3"',
            "OPTIONALWAD": '"game_support.pk3"', "GAMENAME": '"VKDoom"',
            "WGAMENAME": 'L"VKDoom"', "GAMENAMELOWERCASE": '"vkdoom"',
            "TOOLNAMELOWERCASE": '"vktool"', "VERSIONSTR": '"1.0pre"',
            "NETGAMEVERSION": "235", "LASTRUNVERSION": '"225"',
            "DEMOGAMEVERSION": "0x221", "MINDEMOVERSION": "0x221",
            "SAVEVER": "4560", "MINSAVEVER": "4556", "LIGHTMAPVER": "4",
        }
        for name, value in expected.items():
            self.assertEqual(defines[name], value, name)


if __name__ == "__main__":
    unittest.main()
