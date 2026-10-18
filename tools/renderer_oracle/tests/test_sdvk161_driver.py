"""Execute the real fixed input driver without any renderer/device services."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block
from tools.renderer_oracle.sdvk161_special_surfaces import SCHEDULE


class SpecialSurfaceDriverTests(unittest.TestCase):
    def test_actual_driver_is_disabled_by_default_and_emits_exact_registered_inputs(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        phase_type = block(source, "struct LightmapTransitionPhase") + ";"
        phases = source.split("constexpr LightmapTransitionPhase SpecialSurfacePhases[] =", 1)[1].split("};", 1)[0]
        driver = block(source, "void DriveSpecialSurfaceInput(")
        # Minimal input-only service boundary: the actual function has no
        # renderer state, device, success counter or outcome callback to read.
        observed = set(re.findall(r"observer\.([A-Za-z0-9_]+)", driver))
        self.assertEqual(observed, {"SpecialSurfaceInput", "Seen"})
        adapter = r'''
#include <cstdio>
#include <iostream>
struct Observer { bool SpecialSurfaceInput = false; unsigned Seen = 0; };
constexpr int PRINT_HIGH = 1, PRINT_NONOTIFY = 2;
void AddCommandString(const char* value) { std::cout << "COMMAND " << value << '\n'; }
template<class... Args> void Printf(int, const char* format, Args... args) { std::printf(format, args...); }
@TYPE@
constexpr LightmapTransitionPhase SpecialSurfacePhases[] = @PHASES@};
@DRIVER@
int main() {
    Observer observer;
    for (observer.Seen = 0; observer.Seen <= 128; ++observer.Seen) DriveSpecialSurfaceInput(observer);
    std::cout << "ENABLED\n";
    observer.SpecialSurfaceInput = true;
    for (observer.Seen = 0; observer.Seen <= 128; ++observer.Seen) DriveSpecialSurfaceInput(observer);
}
'''.replace("@TYPE@", phase_type).replace("@PHASES@", phases).replace("@DRIVER@", driver)
        with tempfile.TemporaryDirectory(prefix="sdvk161-driver-") as directory:
            path = Path(directory) / "driver.cpp"
            path.write_text(adapter)
            binary = compile_fixture(path, output_dir=directory)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(SCHEDULE[0], {"after_main_views": 32, "phase": "invalidate-a-retained-start",
                                       "command": "invalidatelightmap"})
        self.assertEqual([row["after_main_views"] for row in SCHEDULE], list(range(32, 121, 8)))
        expected = ["ENABLED"]
        for row in SCHEDULE:
            expected += ["COMMAND " + row["command"],
                         f'SDVK161_INPUT phase={row["phase"]} after_main_views={row["after_main_views"]}']
        self.assertEqual(result.stdout.splitlines(), expected)

    def test_checkpoint_precedes_next_input_and_is_state_only(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        presentation = block(source, "void FramePresented()")
        self.assertLess(presentation.index("M_ScreenShot("), presentation.index("DriveSpecialSurfaceInput(observer)"))
        self.assertIn("observer.Seen > observer.WitnessPresented", presentation)
        self.assertIn("observer.WitnessPresented = observer.Seen", presentation)
        self.assertIn('Require(bool(screenshot_quiet)', presentation)
        self.assertIn('"SDVK-161 checkpoint image must be fresh"', presentation)
        self.assertIn("observer.StateMode && !observer.GpuRequested", source)
        self.assertLess(source.index('observer.GpuRequested = Args->CheckParm'),
                        source.index('Require(!observer.SpecialSurfaceInput'))


if __name__ == "__main__":
    unittest.main()
