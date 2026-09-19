#!/usr/bin/env python3
"""PF-009 sprite render-surface/orientation extraction coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class SpriteSurfaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface_h = source("src/rendering/hwrenderer/scene/hw_sprite_surface.h")
        cls.drawstructs_h = source("src/rendering/hwrenderer/scene/hw_drawstructs.h")
        cls.sprites_cpp = source("src/rendering/hwrenderer/scene/hw_sprites.cpp")

    def test_surface_state_carries_compatibility_sensitive_identity(self) -> None:
        for token in [
            "HWSpriteRenderSurfaceState RenderSurface",
            "HWSpriteSurfaceSource source",
            "HWSpritePresentation presentation",
            "bool xyBillboard",
            "bool facesCamera",
            "bool frameMirrored",
            "bool uvMirrorX",
            "bool uvMirrorY",
            "bool portalMirrored",
            "int throughPortalMode",
            "uint32_t spriteType",
            "int actorSprite",
            "int actorFrame",
            "int sourcePortalGroup",
            "int renderPortalGroup",
            "FGameTexture* texture",
            "FTranslationID translation",
            "FRenderStyle renderStyle",
            "DRotator renderAngles",
        ]:
            self.assertIn(token, self.drawstructs_h)

        for token in [
            "float x, y, z",
            "float x1, y1, z1",
            "float x2, y2, z2",
            "float ul, ur, vt, vb",
            "double viewX, viewY, viewZ",
            "double viewYaw, viewPitch, viewRoll",
        ]:
            self.assertIn(token, self.drawstructs_h)

    def test_process_records_selected_frame_mirroring_and_portal_context(self) -> None:
        for token in [
            "RenderSurface.frameMirrored = mirror",
            "RenderSurface.uvMirrorX = mirror ^ !!(thing->renderflags & RF_XFLIP)",
            "RenderSurface.uvMirrorY = !!(thing->renderflags & RF_YFLIP)",
            "RenderSurface.throughPortalMode = thruportal",
            "UpdateRenderSurfaceState(di)",
            "di->drawctx->portalState.isMirrored()",
            "thing->Sector->PortalGroup",
            "sector->PortalGroup",
        ]:
            self.assertIn(token, self.sprites_cpp)

    def test_vertex_path_consumes_canonical_orientation_policy(self) -> None:
        start = self.sprites_cpp.index("bool HWSprite::CalculateVertices")
        end = self.sprites_cpp.index("inline void HWSprite::PutSprite", start)
        body = self.sprites_cpp[start:end]

        self.assertIn("const bool drawWithXYBillboard = RenderSurface.xyBillboard", body)
        self.assertIn("const bool drawBillboardFacingCamera = RenderSurface.facesCamera", body)
        self.assertIn("uint32_t spritetype = RenderSurface.spriteType", body)
        self.assertNotIn("gl_billboard_mode == 1", body)
        self.assertNotIn("RF2_BILLBOARDFACECAMERA", body)
        self.assertNotIn("SPF_FACECAMERA", body)

    def test_actor_particle_and_visual_thinker_paths_publish_state(self) -> None:
        actor_start = self.sprites_cpp.index("void HWSprite::Process(HWDrawInfo")
        particle_start = self.sprites_cpp.index("void HWSprite::ProcessParticle", actor_start)
        visual_start = self.sprites_cpp.index("void HWSprite::AdjustVisualThinker", particle_start)
        actor_body = self.sprites_cpp[actor_start:particle_start]
        particle_body = self.sprites_cpp[particle_start:visual_start]

        self.assertIn("RenderSurface.source = HWSpriteSurfaceSource::Actor", actor_body)
        self.assertIn("UpdateRenderSurfaceState(di)", actor_body)
        self.assertIn("HWSpriteSurfaceSource::VisualThinker", particle_body)
        self.assertIn("HWSpriteSurfaceSource::Particle", particle_body)
        self.assertIn("UpdateRenderSurfaceState(di)", particle_body)

    def test_state_refresh_is_diagnostic_and_geometry_equivalent(self) -> None:
        # The extraction must observe, not rewrite, the inherited quad/UV data.
        update_start = self.sprites_cpp.index("void HWSprite::UpdateRenderSurfaceState")
        update_end = self.sprites_cpp.index("void HandleSpriteOffsets", update_start)
        body = self.sprites_cpp[update_start:update_end]
        for assignment in [
            "RenderSurface.x = x",
            "RenderSurface.x1 = x1",
            "RenderSurface.x2 = x2",
            "RenderSurface.ul = ul",
            "RenderSurface.ur = ur",
            "RenderSurface.vt = vt",
            "RenderSurface.vb = vb",
            "RenderSurface.texture = texture",
            "RenderSurface.translation = translation",
            "RenderSurface.renderStyle = RenderStyle",
            "RenderSurface.alpha = trans",
            "RenderSurface.renderAngles = Angles",
        ]:
            self.assertIn(assignment, body)
        self.assertNotIn("state.Draw", body)
        self.assertNotIn("SetMaterial", body)

    def test_no_new_tbn_pom_or_shadow_algorithm(self) -> None:
        self.assertNotIn("tangent", self.surface_h.lower())
        self.assertNotIn("parallax", self.surface_h.lower())
        self.assertNotIn("pom", self.surface_h.lower())
        self.assertNotIn("shadow", self.surface_h.lower())

    def test_compiled_orientation_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "sprite-surface-policy-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/rendering/hwrenderer/scene",
                    "tools/pf_oracle/tests/sprite_surface_policy_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
