#!/usr/bin/env python3
"""SDVK-006 renderer visual-time and opt-in interpolation contracts."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class VisualTimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.clock_h = source("src/rendering/r_visualtime.h")
        cls.context_h = source("src/rendering/hwrenderer/scene/hw_visualtime.h")
        cls.entrypoint = source("src/rendering/hwrenderer/hw_entrypoint.cpp")
        cls.actor_h = source("src/playsim/actor.h")
        cls.actor_inline = source("src/playsim/actorinlines.h")
        cls.sprites = source("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        cls.flags = source("src/scripting/thingdef_data.cpp")
        cls.level = source("src/g_level.cpp")
        cls.wipe = source("src/common/2d/wipe.cpp")
        cls.diagnostics = source("src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp")
        cls.base_zs = source("wadsrc/static/zscript/engine/base.zs")

    def test_clock_is_main_root_owned_and_sampled_once_before_stereo(self) -> None:
        start = self.entrypoint.index("sector_t* RenderViewpoint")
        end = self.entrypoint.index("void DoWriteSavePic", start)
        body = self.entrypoint[start:end]
        self.assertEqual(body.count("AdvanceMain("), 1)
        self.assertIn("contextType == HWRenderContextType::MainView", body)
        self.assertLess(body.index("AdvanceMain("), body.index("for (int eye_ix = 0;"))
        self.assertIn("mainvp.DiscontinuousView", body)
        self.assertIn("MonotonicTimestampSeconds()", body)
        self.assertNotIn("I_nsTime() *", body)

    def test_non_main_routes_remain_non_owners(self) -> None:
        self.assertIn("context.rootType != HWRenderContextType::MainView", self.context_h)
        self.assertIn("NonMainFallback", self.context_h)
        self.assertIn("RenderViewpoint(texvp, camera, &bounds, fov, ratio, ratio, false, false)", self.entrypoint)
        self.assertIn("RenderViewpoint(probevp, lightprobe, &bounds, 90.0, 1.0f, 1.0f, false, false, side)", self.entrypoint)
        self.assertIn("MakeHWPortalRenderContext", source("src/rendering/hwrenderer/scene/hw_portal.h"))

    def test_reset_hooks_are_explicit_and_bounded(self) -> None:
        for token in ["MaxDeltaSeconds", "ClockRollback", "InvalidTimestamp", "RepeatedTimestamp",
                      "LongFrameClamped", "Pause", "Resume", "LevelLoad", "Wipe", "CameraCut",
                      "InterpolationEnabled", "InterpolationDisabled"]:
            self.assertIn(token, self.clock_h)
        self.assertIn("RenderVisualTime::Reason::LevelLoad", self.level)
        self.assertIn("RenderVisualTime::Reason::Wipe", self.wipe)

    def test_alpha_scale_interpolation_is_opt_in_and_presentation_only(self) -> None:
        for token in ["RF2_INTERPOLATESCALE", "RF2_INTERPOLATEALPHA", "PrevScale", "PrevAlpha",
                      "InterpolatedScale", "InterpolatedAlpha"]:
            self.assertIn(token, self.actor_h)
        self.assertIn("PrevScale = Scale", self.actor_inline)
        self.assertIn("PrevAlpha = Alpha", self.actor_inline)
        self.assertIn("DEFINE_FLAG(RF2, INTERPOLATESCALE", self.flags)
        self.assertIn("DEFINE_FLAG(RF2, INTERPOLATEALPHA", self.flags)
        self.assertIn("HWVisualInterpolationFraction", self.sprites)
        self.assertIn("InterpolatedScale(visualFraction)", self.sprites)
        self.assertIn("InterpolatedAlpha(visualFraction)", self.sprites)
        self.assertNotIn("RenderVisualTime", source("src/p_tick.cpp"))
        self.assertNotIn("AdvanceMain", source("src/p_tick.cpp"))

    def test_ui_script_access_is_explicitly_render_only(self) -> None:
        self.assertIn("native static ui double GetRenderDeltaTime()", self.base_zs)
        self.assertIn("native static ui double GetRenderVisualTime()", self.base_zs)

    def test_sdvk_diagnostics_expose_time_scope_and_discontinuity(self) -> None:
        for token in ["visual_time", "scope", "advances_main_clock", "delta_seconds",
                      "accumulated_seconds", "generation", "interpolation_valid", "discontinuity"]:
            self.assertIn(token, self.diagnostics)

    def test_compiled_clock_and_context_fixture(self) -> None:
        run_fixture(
            "tools/pf_oracle/tests/visual_time_fixture.cpp",
            includes=("src/rendering", "src/rendering/hwrenderer/scene"),
            root=ROOT,
        )


if __name__ == "__main__":
    unittest.main()
