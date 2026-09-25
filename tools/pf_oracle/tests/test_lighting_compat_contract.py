#!/usr/bin/env python3
"""PF-011 lighting compatibility source, numerical and boundary contract."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def numeric_constant(text: str, name: str) -> float:
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*([0-9]+(?:\.[0-9]+)?)f?\s*;", text
    )
    if not match:
        raise AssertionError(f"missing numeric constant {name}")
    return float(match.group(1))


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

    def test_shader_bridge_reference_vectors(self) -> None:
        brightness = numeric_constant(self.shared, "LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE")
        ambient_scale = numeric_constant(self.shared, "LIGHT_COMPAT_PBR_AMBIENT_SCALE")
        metal_scale = numeric_constant(self.shared, "LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE")

        self.assertAlmostEqual(brightness, 2.5)
        self.assertAlmostEqual(ambient_scale, 2.25)
        self.assertAlmostEqual(metal_scale, 0.40)

        # Representative classic-to-PBR direct-light bridge vector.
        light_rgb = (0.4, 0.2, 0.1)
        attenuation = 0.5
        direct = tuple(channel * attenuation * brightness for channel in light_rgb)
        for actual, expected in zip(direct, (0.5, 0.25, 0.125)):
            self.assertAlmostEqual(actual, expected)

        # Sunlight uses the same direct-light bridge while sector ambient has
        # its own historical approximation and metallic specular calibration.
        sun_rgb = (0.8, 0.6, 0.4)
        sun_intensity = 0.75
        sun_attenuation = 0.5
        sun = tuple(
            channel * sun_intensity * brightness * sun_attenuation
            for channel in sun_rgb
        )
        for actual, expected in zip(sun, (0.75, 0.5625, 0.375)):
            self.assertAlmostEqual(actual, expected)

        ambient = tuple(channel * ambient_scale for channel in (0.2, 0.1, 0.05))
        for actual, expected in zip(ambient, (0.45, 0.225, 0.1125)):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(0.5 * 0.8 * metal_scale, 0.16)

    def test_sun_proxy_boundary_is_explicit_and_consistent(self) -> None:
        distance = numeric_constant(self.compat_h, "SunProxyDistance")
        radius = numeric_constant(self.compat_h, "SunProxyRadius")
        strength = numeric_constant(self.compat_h, "SunProxyStrength")
        bypass_radius = numeric_constant(
            self.shared, "LIGHT_COMPAT_SUN_ATTENUATION_RADIUS"
        )

        self.assertEqual(distance, 100000.0)
        self.assertEqual(radius, 100000000.0)
        self.assertEqual(strength, 1500.0)
        self.assertGreaterEqual(radius, bypass_radius)
        self.assertIn("info.x = x + sundir.X * dist;", self.dynlight_cpp)
        self.assertIn("info.z = y + sundir.Y * dist;", self.dynlight_cpp)
        self.assertIn("info.y = z + sundir.Z * dist;", self.dynlight_cpp)
        self.assertIn("LIGHTINFO_ATTENUATED", self.dynlight_cpp)
        self.assertIn("LIGHTINFO_TRACE | LIGHTINFO_SUN", self.dynlight_cpp)

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

    def test_color_class_and_gldefs_semantics_remain_distinct(self) -> None:
        # GPU additive color is pre-scaled, subtractive color is packed as a
        # positive complement, and GLDEFS intensity remains multiplicative.
        self.assertIn("lightClass = LIGHTARRAY_ADDITIVE;", self.dynlight_cpp)
        self.assertIn("lightClass = LIGHTARRAY_SUBTRACTIVE;", self.dynlight_cpp)
        self.assertIn("cs *= (float)light->GetLightDefIntensity();", self.dynlight_cpp)
        self.assertIn("info.r = length - info.r;", self.dynlight_cpp)
        self.assertIn("info.g = length - info.g;", self.dynlight_cpp)
        self.assertIn("info.b = length - info.b;", self.dynlight_cpp)

        # CPU aggregate lighting performs its historical signed subtractive
        # conversion and deliberately does not inherit the GPU additive scale.
        self.assertIn("lr *= light->GetLightDefIntensity();", self.actor_light_cpp)
        self.assertIn("lr = (bright - lr) * -1;", self.actor_light_cpp)
        self.assertIn("lg = (bright - lg) * -1;", self.actor_light_cpp)
        self.assertIn("lb = (bright - lb) * -1;", self.actor_light_cpp)
        self.assertNotIn("AdditiveGpuColorScale", self.actor_light_cpp)

    def test_intentionally_distinct_cpu_sprite_path_is_not_silently_unified(self) -> None:
        # The aggregate sprite path has inherited input conditioning that the
        # GPU fragment path does not: a minimum inverse-square distance and raw
        # (not upload-clamped) linearity. PF-011 documents and preserves it.
        self.assertIn("std::max(dist, sqrt(radius) * 2)", self.actor_light_cpp)
        self.assertIn("light->GetLinearity()", self.actor_light_cpp)
        self.assertNotIn("HWLightCompat::ClampLinearity", self.actor_light_cpp)

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
