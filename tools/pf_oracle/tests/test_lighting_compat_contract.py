#!/usr/bin/env python3
"""PF-011 lighting compatibility source, numerical and boundary contract."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class LightingCompatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compat_h = source("src/common/rendering/hwrenderer/data/hw_lightcompat.h")
        cls.dynlight_cpp = source("src/rendering/hwrenderer/hw_dynlightdata.cpp")
        cls.actor_light_cpp = source("src/rendering/hwrenderer/scene/hw_spritelight.cpp")
        cls.play_light_cpp = source("src/playsim/a_dynlight.cpp")
        cls.shared = source("wadsrc/static/shaders/scene/lightmodel_shared.glsl")
        cls.pbr = source("wadsrc/static/shaders/scene/lightmodel_pbr.glsl")
        cls.specular = source("wadsrc/static/shaders/scene/lightmodel_specular.glsl")

    def test_cpu_packing_uses_named_compatibility_bridge(self) -> None:
        for token in [
            "HWLightCompat::AdditiveGpuColorScale",
            "HWLightCompat::NormalizeColorChannel",
            "HWLightCompat::ClampLinearity",
            "HWLightCompat::SunProxyDistance",
            "HWLightCompat::SunProxyRadius",
            "HWLightCompat::SunProxyStrength",
        ]:
            self.assertIn(token, self.dynlight_cpp)
        self.assertNotIn("cs = 0.2f", self.dynlight_cpp)
        self.assertNotIn("info.radius = 100000000.0f", self.dynlight_cpp)

    def test_shader_bridge_names_inherited_calibration(self) -> None:
        for token in [
            "LIGHT_COMPAT_SUN_ATTENUATION_RADIUS = 1000000.0",
            "LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE = 2.5",
            "LIGHT_COMPAT_PBR_AMBIENT_SCALE = 2.25",
            "LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE = 0.40",
        ]:
            self.assertIn(token, self.shared)
        self.assertNotIn("PBRBrightnessScale", self.pbr)
        self.assertIn("LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE", self.pbr)
        self.assertIn("LIGHT_COMPAT_PBR_AMBIENT_SCALE", self.pbr)
        self.assertIn("LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE", self.pbr)
        self.assertIn("LIGHT_COMPAT_SUN_ATTENUATION_RADIUS", self.pbr)
        self.assertIn("LIGHT_COMPAT_SUN_ATTENUATION_RADIUS", self.specular)

    def test_distance_equation_remains_inherited_exact_shape(self) -> None:
        # Keep operation ordering stable: this is a compatibility refactor, not
        # an attenuation redesign.
        for token in [
            "float a = dist / radius;",
            "float b = clamp(1.0 - a * a * a * a, 0.0, 1.0);",
            "(b * b) / (dist * dist + 1.0) * strength",
            "clamp((radius - dist) / radius, 0.0, 1.0)",
        ]:
            self.assertIn(token, self.shared)

    def test_intentionally_distinct_cpu_sprite_path_is_not_silently_unified(self) -> None:
        # The aggregate sprite path has inherited input conditioning that the
        # GPU fragment path does not: a minimum inverse-square distance and raw
        # (not upload-clamped) linearity. PF-011 documents and preserves it.
        self.assertIn("std::max(dist, sqrt(radius) * 2)", self.actor_light_cpp)
        self.assertIn("light->GetLinearity()", self.actor_light_cpp)
        self.assertNotIn("AdditiveGpuColorScale", self.actor_light_cpp)

    def test_authoring_strength_calibration_is_unchanged(self) -> None:
        self.assertIn("radius *= 2", self.play_light_cpp)
        self.assertIn("std::min(1500.0f, (radius * radius) / 10)", self.play_light_cpp)

    def test_compiled_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "lighting-compat-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/lighting_compat_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
