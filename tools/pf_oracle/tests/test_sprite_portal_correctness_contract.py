#!/usr/bin/env python3
"""PF-014 sprite clipping and sky/portal identity correctness coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class SpritePortalCorrectnessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sprite_cpp = source("src/rendering/hwrenderer/scene/hw_sprites.cpp")
        cls.portal_h = source("src/rendering/hwrenderer/scene/hw_portal.h")
        cls.sky_cpp = source("src/rendering/hwrenderer/scene/hw_sky.cpp")

    def test_sprite_clip_top_uses_the_same_sentinel_for_init_break_and_fallback(self) -> None:
        begin = self.sprite_cpp.index("void HWSprite::PerformSpriteClipAdjustment")
        end = self.sprite_cpp.index("void HWSprite::Process(", begin)
        body = self.sprite_cpp[begin:end]

        self.assertIn("float btm = NO_VAL", body)
        self.assertIn("float top = -NO_VAL", body)
        self.assertIn("btm != NO_VAL && top != -NO_VAL", body)
        self.assertIn("if (btm == NO_VAL)", body)
        self.assertIn("if (top == -NO_VAL)", body)
        self.assertNotIn("if (top == NO_VAL)", body)
        self.assertIn("thing->Sector->ceilingplane.ZatPoint(thingpos)", body)

    def test_sky_identity_is_explicit_and_padding_independent(self) -> None:
        begin = self.portal_h.index("struct HWSkyInfo")
        end = self.portal_h.index("struct HWHorizonInfo", begin)
        body = self.portal_h[begin:end]

        self.assertNotIn("memcmp", body)
        self.assertIn("bool operator==(const HWSkyInfo & inf) const", body)
        self.assertIn("bool operator!=(const HWSkyInfo & inf) const", body)
        for token in [
            "x_offset[0] == inf.x_offset[0]",
            "x_offset[1] == inf.x_offset[1]",
            "y_offset == inf.y_offset",
            "texture[0] == inf.texture[0]",
            "texture[1] == inf.texture[1]",
            "skytexno1 == inf.skytexno1",
            "mirrored == inf.mirrored",
            "doublesky == inf.doublesky",
            "sky2 == inf.sky2",
            "fadecolor == inf.fadecolor",
            "return !(*this == inf)",
        ]:
            self.assertIn(token, body)

    def test_sky_initialization_and_dedup_inputs_remain_inherited(self) -> None:
        self.assertIn("memset(this, 0, sizeof(*this))", self.sky_cpp)
        for token in [
            "x_offset[0]",
            "x_offset[1]",
            "y_offset",
            "texture[0]",
            "texture[1]",
            "skytexno1",
            "mirrored",
            "doublesky",
            "sky2",
            "fadecolor",
        ]:
            self.assertIn(token, self.sky_cpp)

    def test_pf009_pf010_mirror_and_portal_context_contracts_remain_intact(self) -> None:
        self.assertIn(
            "RenderSurface.portalMirrored = di->drawctx->portalState.isMirrored()",
            self.sprite_cpp,
        )
        self.assertIn("return !!((MirrorFlag ^ PlaneMirrorFlag) & 1)", self.portal_h)

        setup = self.portal_h.index("if (Setup(di, state")
        make_context = self.portal_h.index("MakeHWPortalRenderContext", setup)
        draw_scene = self.portal_h.index("di->DrawScene(DM_PORTAL, state)", make_context)
        shutdown = self.portal_h.index("Shutdown(di, state)", draw_scene)
        restore = self.portal_h.index("mState->RenderContext = parentContext", shutdown)
        self.assertLess(setup, make_context)
        self.assertLess(make_context, draw_scene)
        self.assertLess(draw_scene, shutdown)
        self.assertLess(shutdown, restore)

    def test_compiled_adversarial_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "sprite-portal-correctness-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "tools/pf_oracle/tests/sprite_portal_correctness_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
