"""Portable compiler argv and failure propagation; no compiler or GPU invoked."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle import fixture_runner as runner


class FixtureRunnerTests(unittest.TestCase):
    def test_msvc_preserves_assertions_and_strict_warnings_with_space_paths(self):
        executable = Path("temporary output/fixture.exe")
        command = runner.compilation_command(
            r"C:\Program Files\VS\cl.exe", Path("source folder/fixture.cpp"),
            [Path("include folder")], executable
        )
        self.assertEqual(command[0], r"C:\Program Files\VS\cl.exe")
        for flag in ("/std:c++17", "/EHsc", "/W4", "/WX", "/UNDEBUG"):
            self.assertIn(flag, command)
        self.assertIn(str(Path("source folder/fixture.cpp")), command)
        self.assertIn("/Iinclude folder", command)
        for suffix, flag in ((".exe", "/Fe:"), (".obj", "/Fo:"), (".pdb", "/Fd:")):
            self.assertIn(flag + str(executable.with_suffix(suffix)), command)
        self.assertFalse(any('"' in arg for arg in command))

    def test_gnu_and_clang_preserve_assertions_and_strict_warnings(self):
        for compiler in ("c++", "g++", "clang++"):
            with self.subTest(compiler=compiler):
                command = runner.compilation_command(
                    compiler, Path("fixture.cpp"), [Path("include dir")], Path("fixture")
                )
                for flag in ("-std=c++17", "-Wall", "-Wextra", "-Werror", "-UNDEBUG"):
                    self.assertIn(flag, command)
                self.assertIn("-Iinclude dir", command)
                self.assertEqual(command[-2:], ["-o", "fixture"])

    def test_native_compiler_selection_and_explicit_override(self):
        for windows, environment, requested in (
            (True, {}, "cl"), (False, {}, "c++"),
            (True, {"PF_CXX": "compiler directory/clang++"}, "compiler directory/clang++"),
        ):
            with self.subTest(windows=windows, environment=environment):
                with patch.object(runner.shutil, "which", return_value="resolved compiler") as which:
                    self.assertEqual(runner.select_compiler(environment=environment, windows=windows),
                                     "resolved compiler")
                    which.assert_called_once_with(requested)

    def test_missing_compiler_fails_without_skipping(self):
        with patch.object(runner.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "PF CPU fixture compiler unavailable"):
                runner.select_compiler(environment={}, windows=True)

    def test_compilation_uses_absolute_inputs_and_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source root"
            root.mkdir()
            source = root / "fixture.cpp"
            source.write_text("int main() {}", encoding="utf-8")
            output = Path(directory) / "temporary output"
            def compiler_success(command, **kwargs):
                executable = Path(command[command.index("-o") + 1])
                executable.touch()
                return subprocess.CompletedProcess(command, 0)
            with patch.object(runner.subprocess, "run", side_effect=compiler_success) as run:
                executable = runner.compile_fixture(
                    "fixture.cpp", includes=("include dir",), output_dir=output,
                    root=root, compiler="g++"
                )
            command, = run.call_args.args
            self.assertIn(str(source.resolve()), command)
            self.assertIn("-I" + str((root / "include dir").resolve()), command)
            self.assertEqual(executable.parent, output.resolve())
            self.assertEqual(run.call_args.kwargs, {"cwd": output.resolve(), "check": True, "timeout": 120})
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_compile_failure_is_propagated_and_prevents_execution(self):
        failure = subprocess.CalledProcessError(2, ["synthetic compiler"])
        with patch.object(runner, "compile_fixture", side_effect=failure), \
             patch.object(runner.subprocess, "run") as run:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                runner.run_fixture("fixture.cpp")
            self.assertIs(caught.exception, failure)
            run.assert_not_called()

    def test_success_without_executable_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixture.cpp"
            source.write_text("int main() {}", encoding="utf-8")
            with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                with self.assertRaisesRegex(RuntimeError, "without an executable"):
                    runner.compile_fixture(source, output_dir=directory, compiler="g++")

    def test_missing_source_and_escaping_name_fail_before_compile(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(runner.subprocess, "run") as run:
            with self.assertRaises(FileNotFoundError):
                runner.compile_fixture("missing.cpp", output_dir=directory)
            source = Path(directory) / "fixture.cpp"
            source.touch()
            with self.assertRaises(ValueError):
                runner.compile_fixture(source, name="../escape", output_dir=directory)
            run.assert_not_called()

    def test_execution_preserves_cwd_arguments_and_failure(self):
        failure = subprocess.CalledProcessError(3, ["synthetic fixture"])
        with patch.object(runner, "compile_fixture", return_value=Path("fixture executable")), \
             patch.object(runner.subprocess, "run", side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                runner.run_fixture("fixture.cpp", args=("--scenario", "one"),
                                   timeout=7, capture_output=True)
            self.assertIs(caught.exception, failure)
            self.assertEqual(run.call_args.args[0], ["fixture executable", "--scenario", "one"])
            self.assertEqual(run.call_args.kwargs, {
                "cwd": ROOT, "check": True, "timeout": 7,
                "capture_output": True, "text": True,
            })

    def test_cli_passes_repeat_includes_and_fixture_arguments(self):
        with patch.object(runner, "run_fixture") as run:
            self.assertEqual(runner.main([
                "--source", "fixture.cpp", "--include", "first", "--include", "second",
                "--compiler", "compiler with spaces", "--timeout", "9", "--", "--scenario", "one",
            ]), 0)
            run.assert_called_once_with(
                "fixture.cpp", includes=["first", "second"], root=ROOT,
                name=None, timeout=9, compiler="compiler with spaces", args=["--scenario", "one"],
            )


if __name__ == "__main__":
    unittest.main()
