"""Actual constant-FOV interpolation through narrow view-number admission.

CPU source extraction only. No renderer/device, timing changes or packet edits.
"""
import copy
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.renderer_oracle import sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests.test_sdvk161_special_surfaces import full_raw, native_recipe, stdout

ROOT = Path(__file__).resolve().parents[3]


def actor_fov_method():
    source = (ROOT / "src/playsim/p_mobj.cpp").read_text()
    first = source.index("double AActor::GetFOV(double ticFrac)")
    opening = source.index("{", first)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[first:end]


class FovRepresentationTests(unittest.TestCase):
    def test_actual_equal_endpoint_camera_interpolation_produces_old_gate_counterexample(self):
        compiler = shutil.which("c++") or shutil.which("g++")
        self.assertIsNotNone(compiler, "CPU source replay compiler required")
        source = r'''
#include <iomanip>
#include <iostream>
constexpr int CF_NOFOVINTERP=1;
struct Angle { double value; double Degrees() const { return value; } };
struct Player { int cheats=0; double FOV=90; };
struct AActor {
  Player* player=nullptr; Angle PrevFOV{90}; double CameraFOV=90;
  double GetFOV(double ticFrac);
};
''' + actor_fov_method() + r'''
int main() {
  AActor camera; Player player;
  for (int path=0; path<2; ++path) {
    camera.player=path?&player:nullptr;
    for (int i=0;i<=10000;++i)
      std::cout << std::setprecision(17) << camera.GetFOV(double(i)/10000) << '\n';
  }
}
'''
        with tempfile.TemporaryDirectory(prefix="sdvk161-fov-cpu-") as directory:
            directory = Path(directory)
            code, executable = directory / "fov.cpp", directory / "fov"
            code.write_text(source)
            compiled = subprocess.run([compiler, "-std=c++17", "-O0", str(code), "-o", str(executable)],
                                      capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            values = [float(line) for line in executed.stdout.splitlines()]
        self.assertEqual(len(values), 20002)
        self.assertTrue(any(value != 90 for value in values), "Original literal90 gate must fail")
        self.assertLessEqual(max(abs(value - 90) for value in values), math.ulp(90))
        for value in values:
            gate._retained_fov(value)
        # This is the already declared renderer view-number representation,
        # not a new generic camera or image tolerance.
        self.assertIn("rounded = round(float(value), 9)",
                      (ROOT / "tools/renderer_oracle/validate.py").read_text())

    def test_raw_one_ulp_values_are_preserved_and_real_fov_changes_reject(self):
        raw = full_raw()
        frames = [record for record in raw["records"] if record["kind"] == "frame"]
        for index, record in enumerate(frames):
            record["data"]["camera"]["fov"] = math.nextafter(90, math.inf if index % 2 else -math.inf)
        original = copy.deepcopy(raw)
        self.assertEqual(gate.validate_transition_records(raw, stdout(), native_recipe())["status"], "PASS")
        self.assertEqual(raw, original)
        for value in (90 + 1e-8, 90 - 1e-8, 89, 91, float("inf"), float("nan"), True, "90", None):
            with self.subTest(value=value), self.assertRaisesRegex(EvidenceError, "retained frame camera FOV differs"):
                gate._retained_fov(value)


if __name__ == "__main__":
    unittest.main()
