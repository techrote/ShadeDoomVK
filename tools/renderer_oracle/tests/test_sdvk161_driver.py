"""Execute the real fixed input driver without any renderer/device services."""
from pathlib import Path
import re
import json
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block
from tools.renderer_oracle.sdvk161_special_surfaces import SCHEDULE


def build_driver(directory):
    source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
    game = (ROOT / "src/g_game.cpp").read_text()
    level = (ROOT / "src/g_level.cpp").read_text()
    net = (ROOT / "src/d_net.cpp").read_text()
    wait = net[net.index("void TryRunTics (void)"):]
    wait = wait[wait.index("bool doWait ="):wait.index("// get real tics")]
    (directory / "map_transition_wait.inc").write_text(wait)
    phases = source.split("constexpr LightmapTransitionPhase SpecialSurfacePhases[] =", 1)[1].split("};", 1)[0]
    ticker = block(game, "while (gameaction != ga_nothing)")
    actions = sorted(set(re.findall(r"\bga_[a-zA-Z0-9_]+", ticker)))
    (directory / "map_transition_actions.inc").write_text("enum Action {" + ",".join(actions) + "};\nAction gameaction=ga_nothing;\n")
    (directory / "map_transition_ticker.inc").write_text(ticker)
    (directory / "map_transition_defer.inc").write_text(block(level, "void G_DeferedInitNew (const char *mapname, int newskill)"))
    (directory / "map_transition_newgame.inc").write_text(block(level, "void G_DoNewGame (void)"))
    (directory / "map_transition_input.inc").write_text(
        block(source, "struct LightmapTransitionPhase") + ";\n" +
        "constexpr LightmapTransitionPhase SpecialSurfacePhases[] =" + phases + "};\n" +
        block(source, "struct SpecialSurfaceMapInput") + ";\n" +
        block(source, "SpecialSurfaceMapInput& PendingSpecialSurfaceMapInput()") + "\n" +
        block(source, "bool SpecialSurfaceMapClockValid()") + "\n" +
        block(source, "void DriveSpecialSurfaceInput("))
    for name, signature in (("pending", "bool SpecialSurfaceMapTransitionPending()"),
                            ("complete", "void SpecialSurfaceMapTransitionCompleted()")):
        (directory / f"map_transition_{name}.inc").write_text(block(source, signature))
    return compile_fixture(Path(__file__).with_name("sdvk161_map_transition_fixture.cpp"),
                           output_dir=directory, includes=[directory])


class SpecialSurfaceDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sdvk161-driver-")
        cls.binary = build_driver(Path(cls.temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_fixture(self, mode):
        return subprocess.run([str(self.binary), mode], check=True, capture_output=True,
                              text=True, timeout=10).stdout.splitlines()

    def test_actual_driver_is_disabled_by_default_and_emits_exact_registered_inputs(self):
        rows = self.run_fixture("schedule")
        self.assertEqual(SCHEDULE[0], {"after_main_views": 32, "phase": "invalidate-a-retained-start",
                                       "command": "invalidatelightmap"})
        self.assertEqual([row["after_main_views"] for row in SCHEDULE], list(range(32, 121, 8)))
        expected = ["ENABLED"]
        for row in SCHEDULE:
            expected += ["COMMAND " + row["command"],
                         f'SDVK161_INPUT phase={row["phase"]} after_main_views={row["after_main_views"]}']
        self.assertEqual([row for row in rows if not row.startswith("SDVK161_INPUT_COMPLETE ")], expected)
        self.assertEqual([row for row in rows if row.startswith("SDVK161_INPUT_COMPLETE ")], [
            "SDVK161_INPUT_COMPLETE phase=reload-a after_main_views=56 map=SDV161A previous_mesh_owner=3 mesh_owner=4 next_retained_frame=25",
            "SDVK161_INPUT_COMPLETE phase=map-b after_main_views=80 map=SDV161B previous_mesh_owner=4 mesh_owner=5 next_retained_frame=49",
            "SDVK161_INPUT_COMPLETE phase=reload-b after_main_views=104 map=SDV161B previous_mesh_owner=5 mesh_owner=6 next_retained_frame=73"])

    def test_actual_action_loop_also_completes_multiple_tics_before_display(self):
        rows = self.run_fixture("multi-tic")
        self.assertEqual(sum(row.startswith("SDVK161_INPUT_COMPLETE ") for row in rows), 1)

    def test_pending_or_wrong_completion_fails_closed_in_bounded_input_driver(self):
        self.assertIn("PASS cancellation/other-action/missing-callback/bounded-wait/missing-owner/same-owner/wrong-map/duplicate",
                      self.run_fixture("failures"))

    def test_other_modes_remain_inert_and_loop_guard_precedes_any_observed_display(self):
        self.assertEqual(self.run_fixture("inert"), ["PASS ordinary/disabled behavior unchanged"])
        catalog = json.loads((ROOT / "tools/renderer_oracle/corpus.json").read_text())
        scene = next(s for s in catalog["scenes"] if s["id"] == "special-surface-lifecycle")
        settings = scene["native"]["settings"]
        self.assertEqual([settings[k] for k in ("cl_capfps", "vid_maxfps", "vid_vsync")], [True, 0, False])
        source = (ROOT / "src/d_main.cpp").read_text()
        loop = block(source, "void D_DoomLoop ()\n{")
        self.assertLess(loop.index("TryRunTics ();"), loop.index("SpecialSurfaceMapTransitionPending()"))
        self.assertLess(loop.index("SpecialSurfaceMapTransitionPending()"), loop.index("D_Display ();"))
        guard = loop[loop.index("// The exact SDVK-161 driver"):loop.index("// Update display")]
        self.assertIn("continue;", guard)
        self.assertNotIn("D_SingleTick()", guard)
        self.assertNotIn("G_DoNewGame", guard)
        level = (ROOT / "src/g_level.cpp").read_text()
        complete = block(level, "void G_DoNewGame (void)")
        self.assertLess(complete.index("G_InitNew ("), complete.index("SpecialSurfaceMapTransitionCompleted()"))
        self.assertLess(complete.index("gameaction = ga_nothing;"), complete.index("SpecialSurfaceMapTransitionCompleted()"))
        loader = block((ROOT / "src/maploader/maploader.cpp").read_text(), "void MapLoader::InitLevelMesh(")
        self.assertIn("Level->levelMesh = new DoomLevelMesh(*Level)", loader)

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
