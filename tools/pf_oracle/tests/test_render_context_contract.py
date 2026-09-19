#!/usr/bin/env python3
"""PF-010 render-view/pass context extraction coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class RenderContextContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context_h = source("src/rendering/hwrenderer/scene/hw_rendercontext.h")
        cls.entrypoint_cpp = source("src/rendering/hwrenderer/hw_entrypoint.cpp")
        cls.portal_h = source("src/rendering/hwrenderer/scene/hw_portal.h")

    def test_context_names_all_required_root_and_recursive_classes(self) -> None:
        for token in [
            "MainView",
            "CameraTexture",
            "LightProbe",
            "SavePicture",
            "Portal",
            "rootType",
            "epoch",
            "identity",
            "parentIdentity",
            "recursionDepth",
            "probeFace",
            "eyeIndex",
            "lineMirror",
            "planeMirror",
            "mirrored",
            "postprocessEligible",
            "historyEligible",
        ]:
            self.assertIn(token, self.context_h)

    def test_top_level_viewpoint_gets_epoch_and_per_pass_identity(self) -> None:
        start = self.entrypoint_cpp.index("sector_t* RenderViewpoint")
        end = self.entrypoint_cpp.index("void DoWriteSavePic", start)
        body = self.entrypoint_cpp[start:end]
        self.assertIn("contextSequence.BeginEpoch()", body)
        self.assertIn("ClassifyHWRenderContext(mainview, toscreen, side)", body)
        self.assertIn("contextSequence.AllocateIdentity()", body)
        self.assertIn("mainthread_drawctx.portalState.RenderContext", body)
        self.assertIn("side, eye_ix", body)
        self.assertIn("di->IsEnvironmentMapRendering = side != -1", body)

    def test_existing_main_camera_probe_and_save_routes_remain_authoritative(self) -> None:
        # PF-010 describes these routes; it does not replace their rendering
        # booleans, transform setup, environment-face signal or postprocess gate.
        for token in [
            "RenderViewpoint(texvp, camera, &bounds, fov, ratio, ratio, false, false)",
            "RenderViewpoint(probevp, lightprobe, &bounds, 90.0, 1.0f, 1.0f, false, false, side)",
            "RenderViewpoint(r_viewpoint, player->camera, NULL, r_viewpoint.FieldOfView.Degrees(), ratio, fovratio, true, true)",
            "RenderViewpoint(savevp, players[consoleplayer].camera, &bounds, r_viewpoint.FieldOfView.Degrees(), 1.6f, 1.6f, true, false)",
            "R_SetupFrame(mainvp, r_viewwindow, camera, side)",
            "di->SetupView(RenderState, vp.Pos.X, vp.Pos.Y, vp.Pos.Z, false, false)",
            "if (mainview)",
            "if (toscreen) di->EndDrawScene",
            "screen->PostProcessScene",
        ]:
            self.assertIn(token, self.entrypoint_cpp)

    def test_recursive_portal_context_samples_live_inherited_mirror_state(self) -> None:
        start = self.portal_h.index("virtual void DrawContents(HWDrawInfo *di, FRenderState &state)")
        end = self.portal_h.index("virtual bool Setup(HWDrawInfo *di", start)
        body = self.portal_h[start:end]
        setup = body.index("if (Setup(")
        context = body.index("MakeHWPortalRenderContext")
        draw = body.index("di->DrawScene(DM_PORTAL, state)")
        shutdown = body.index("Shutdown(di, state)")
        restore = body.index("mState->RenderContext = parentContext", context)
        self.assertLess(setup, context)
        self.assertLess(context, draw)
        self.assertLess(draw, shutdown)
        self.assertLess(shutdown, restore)
        self.assertIn("mState->MirrorFlag", body)
        self.assertIn("mState->PlaneMirrorFlag", body)
        self.assertIn("HWRenderContextRuntimeSequence().AllocateIdentity()", body)

    def test_extraction_adds_no_temporal_feature_or_transform_policy(self) -> None:
        lowered = self.context_h.lower()
        for forbidden in ["motionvector", "motion_vector", "taa", "historyimage", "historybuffer"]:
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("VSMatrix", self.context_h)
        self.assertNotIn("SetViewMatrix", self.context_h)
        self.assertNotIn("SetupView", self.context_h)

    def test_compiled_adversarial_context_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "render-context-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/rendering/hwrenderer/scene",
                    "tools/pf_oracle/tests/render_context_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
