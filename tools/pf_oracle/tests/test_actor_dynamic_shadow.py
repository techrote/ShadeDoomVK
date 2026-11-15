"""Actual source-alpha actor shadows: per-emitter ray and source/ABI contracts.

The mathematical reference is an independently authored oracle, not a GPU PASS.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[3]
MASK_WIDTH, MASK_HEIGHT = 64, 128


def solid_mask():
    return (0xFFFFFFFF,) * (MASK_WIDTH * MASK_HEIGHT // 32)


def caster_for(light, mask=None, *, mirror_x=False, mirror_y=False):
    """A source-alpha frame looking from the actual light position."""
    dx, dz = -light[0], -light[2]
    size = math.hypot(dx, dz)
    if size == 0:
        raise ValueError("Coincident light and actor")
    return (0., 0., 0., 12., 0., 60.,
            dx / size, dz / size, -16., 16.,
            float(mirror_x), float(mirror_y),
            solid_mask() if mask is None else mask)


def visibility(light, receiver, caster):
    (x, y, z, radius, bottom, top, nx, nz,
     left, right, mirror_x, mirror_y, mask) = caster
    if radius <= 0 or bottom >= top or right <= left:
        return 1.
    delta = tuple(receiver[i] - light[i] for i in range(3))
    denominator = delta[0] * nx + delta[2] * nz
    if abs(denominator) < 1e-5:
        return 1.
    t = ((x - light[0]) * nx + (z - light[2]) * nz) / denominator
    bias = min(.01, .05 / max(math.sqrt(sum(d*d for d in delta)), .0001))
    if not bias < t < 1. - bias:
        return 1.
    hit = tuple(light[i] + delta[i] * t for i in range(3))
    horizontal = (hit[0] - x) * (-nz) + (hit[2] - z) * nx
    u = (right - horizontal) / (right - left)
    v = (hit[1] - bottom) / (top - bottom)
    if not (0. <= u < 1. and 0. <= v < 1.):
        return 1.
    if mirror_x: u = 1. - u
    if mirror_y: v = 1. - v
    px = min(MASK_WIDTH - 1, max(0, int(math.floor(u * MASK_WIDTH))))
    py = min(MASK_HEIGHT - 1, max(0, int(math.floor((1. - v) * MASK_HEIGHT))))
    bit = py * MASK_WIDTH + px
    return float((mask[bit // 32] & (1 << (bit % 32))) == 0)


class ActorShadowContracts(unittest.TestCase):
    def test_source_alpha_occludes_actual_floor_and_wall(self):
        light = (-90., 60., 0.)
        caster = caster_for(light)
        self.assertEqual(visibility(light, (90., 0., 0.), caster), 0.)
        self.assertEqual(visibility(light, (90., 40., 0.), caster), 0.)
        self.assertEqual(visibility(light, (90., 0., 60.), caster), 1.)

    def test_transparent_holes_do_not_cast(self):
        light = (-90., 60., 0.)
        full = list(solid_mask())
        # Row 64, column 32 corresponds to the center of the silhouette.
        bit = 64 * MASK_WIDTH + 32
        full[bit // 32] &= ~(1 << (bit % 32))
        self.assertEqual(visibility(light, (90., 0., 0.), caster_for(light, tuple(full))), 1.)
        self.assertEqual(visibility(light, (90., 40., 0.), caster_for(light, tuple(full))), 0.)

    def test_light_source_changes_shadow_but_not_ambient_or_other_lights(self):
        first = (-90., 60., 0.)
        second = (90., 60., 90.)
        receiver = (90., 0., 0.)
        blocked = visibility(first, receiver, caster_for(first))
        clear = visibility(second, receiver, caster_for(second))
        self.assertEqual((blocked, clear), (0., 1.))
        self.assertAlmostEqual(.15 + .7 * blocked + .4 * clear, .55)

    def test_ray_between_endpoints_and_receiver_height(self):
        light = (-90., 60., 0.)
        caster = caster_for(light)
        self.assertEqual(visibility(light, (-40., 0., 0.), caster), 1.)
        self.assertEqual(visibility(light, (0., 30., 0.), caster), 1.)
        self.assertEqual(visibility(light, (90., 0., 50.), caster), 1.)
        self.assertEqual(visibility(light, (90., 0., 5.), caster), 0.)
        self.assertEqual(visibility((-90., 200., 0.), (90., 180., 0.),
                                    caster_for((-90., 200., 0.))), 1.)

    def test_asymmetric_source_flips_once_in_the_authored_direction(self):
        light = (-90., 60., 0.)
        # Source U<.5 is clear, U>=.5 opaque; signed source U decreases
        # along the sprite tangent, just as the actual HWSprite quad.
        words = [0] * len(solid_mask())
        for y in range(MASK_HEIGHT):
            for x in range(MASK_WIDTH // 2, MASK_WIDTH):
                bit = y * MASK_WIDTH + x
                words[bit // 32] |= 1 << (bit % 32)
        caster = caster_for(light, tuple(words))
        self.assertEqual(visibility(light, (90., 0., 16.), caster), 1.)
        self.assertEqual(visibility(light, (90., 0., -16.), caster), 0.)
        flipped = caster_for(light, tuple(words), mirror_x=True)
        self.assertEqual(visibility(light, (90., 0., 16.), flipped), 0.)
        self.assertEqual(visibility(light, (90., 0., -16.), flipped), 1.)

    def test_far_receiver_does_not_expand_the_endpoint_bias(self):
        light = (-10000., 60., 0.)
        # A receiver only one world unit behind a caster remains occluded,
        # even when the source-to-receiver segment is very long.
        self.assertEqual(visibility(light, (1., 30., 0.), caster_for(light)), 0.)

    def test_runtime_structural_abi_and_source_alpha(self):
        cpu = (ROOT / "src/common/rendering/hwrenderer/data/hw_dynlightdata.h").read_text()
        gpu = (ROOT / "wadsrc/static/shaders/binding_struct_definitions.glsl").read_text()
        tiled = (ROOT / "wadsrc/static/shaders/scene/comp_lighttiles.glsl").read_text()
        source = (ROOT / "src/rendering/hwrenderer/hw_dynlightdata.cpp").read_text()
        self.assertIn("sizeof(FActorShadowCaster) == 1072", cpu)
        self.assertIn("sizeof(FDynLightInfo) == 80", cpu)
        self.assertIn("ActorShadowMaskWidth = 64", cpu)
        self.assertIn("ActorShadowMaskHeight = 128", cpu)
        self.assertIn("MaxActorShadowCastersPerLight = 4", cpu)
        self.assertIn("uint alphaWords[256]", gpu)
        self.assertNotIn("alphaWords", tiled)
        for layout in (cpu, gpu, tiled):
            self.assertIn("actorShadowIndex", layout)
            self.assertIn("actorShadowCount", layout)
            self.assertIn("actorShadowMask", layout)
        self.assertIn("GetThinkerIterator<AActor>()", source)
        self.assertIn("GetSpriteFrame(", source)
        self.assertIn("GetSpriteAngle(", source)
        self.assertIn("CreateTexBuffer(0)", source)
        self.assertIn("SourceAlphaMask(", source)
        self.assertIn("FindModelFrame(", source)
        self.assertIn("actor->picnum.isValid()", source)
        self.assertIn("RF_INVISIBLE", source)
        self.assertIn("actor->Floorclip", source)
        self.assertIn("GetSpriteOffset(", source)
        self.assertIn("candidate == light->target", source)
        self.assertIn("candidate->Sector->PortalGroup != group", source)
        self.assertIn("gl_actor_light_shadows, false", source)
        self.assertNotIn("STYLE_Stencil", source)

    def test_flashlight_player_exclusion_keeps_no_shadowmap_actor_casters(self):
        # A PR #190 flashlight is a separate beam actor, NOT the player pawn.
        # Source-level integration guard; native visual acceptance is separate.
        zscript = (ROOT / "tools/doom2_showcase/flashlight/ZSCRIPT").read_text()
        lights = (ROOT / "src/playsim/a_dynlight.h").read_text()
        renderer = (ROOT / "src/rendering/hwrenderer/hw_dynlightdata.cpp").read_text()
        self.assertIn("class SDVKLocalFlashlightBeam : SpotLight", zscript)
        self.assertIn("+DYNAMICLIGHT.NOSHADOWMAP", zscript)
        self.assertIn("DontShadowmap() const", lights)
        self.assertIn("candidate == light->target || candidate->player", renderer)
        # NOSHADOWMAP is an ordinary world-shadowmap opt-out, not permission
        # to remove actor silhouettes from lights (our native room uses it).
        self.assertNotIn("light->DontShadowmap()", renderer)
        self.assertIn("light_noshadowmap=True", (ROOT / "tools/dynamic_shadows/native_scene.py").read_text())

    def test_per_local_light_shading_not_global_composite(self):
        root = ROOT / "wadsrc/static/shaders/scene"
        for filename in ("lightmodel_normal.glsl", "lightmodel_specular.glsl",
                         "lightmodel_pbr.glsl"):
            shader = (root / filename).read_text()
            self.assertIn("attenuation *= ActorLightShadowVisibility(light);", shader)
        pbr = (root / "lightmodel_pbr.glsl").read_text()
        self.assertLess(pbr.index("attenuation *= ActorLightShadowVisibility(light);"),
                        pbr.index("vec3 radiance = light.color.rgb * attenuation"))
        self.assertIn("SampleProbePrefiltered", pbr)
        normal = (root / "lightmodel_normal.glsl").read_text()
        self.assertIn("float spotCosine = dot(lightdir, light.spotDir.xyz)", normal)
        shadow = (root / "light_shadow.glsl").read_text()
        self.assertIn("actorShadowCasters[casterIndex].alphaWords[bit / 32]", shadow)
        self.assertIn("actorShadowCasters[casterIndex].planeNx", shadow)
        self.assertIn("actorShadowCasters[casterIndex].mirrorX", shadow)
        self.assertIn("actorShadowCasters.length()", shadow)
        self.assertNotIn("STYLE_Stencil", shadow)
        self.assertNotIn("discriminant", shadow)


if __name__ == "__main__":
    unittest.main()
