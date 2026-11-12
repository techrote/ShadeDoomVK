"""Bounded local material-art interpretations; no engine/gameplay changes."""

from __future__ import annotations
import json
import material_generator as base

np = base.np
Image = base.Image


def _smooth(a, lo, hi):
    x = np.clip((a - lo) / (hi - lo), 0, 1)
    return x * x * (3 - 2 * x)


def _mask(values, size):
    return (
        np.asarray(
            Image.fromarray(np.uint8(np.clip(values, 0, 1) * 255), "L").resize(
                size, Image.Resampling.BILINEAR
            ),
            dtype=np.float32,
        )
        / 255
    )


def _family(name, kind, original):
    if kind == "flat":
        if name in ("FLAT1_3", "FLAT1", "FLOOR0_5", "FLOOR0_7", "FLAT3"):
            return "metal"
        if name in ("FLAT20", "FLAT9", "FLAT18"):
            return "stone / concrete"
        return original
    if (
        name.startswith(("BIGDOOR5", "BIGDOOR6", "BIGDOOR7", "WOODMET"))
        or name == "DOOR1"
    ):
        return "wood"
    if name in ("EXITDOOR", "ZELDOOR", "PLAT1", "MIDBRN1", "MIDBRONZ", "ZZWOLF11"):
        return "metal"
    if name.startswith("CRAT"):
        return "painted panels"
    if name in ("BRWINDOW", "ZZWOLF10"):
        return "brick / mortar"
    if name in (
        "GRAY1",
        "GRAY2",
        "GRAY4",
        "GRAY5",
        "GRAY7",
        "GRAYBIG",
        "GRAYTALL",
        "ZZWOLF1",
        "ZZWOLF2",
        "ZZWOLF9",
    ):
        return "stone / concrete"
    if name in ("ZZZFACE3", "ZZZFACE4", "ZZZFACE5"):
        return "organic"
    if name in ("ZZZFACE6", "ZZZFACE7", "ZZZFACE8", "ZZZFACE9") or name.startswith(
        ("TEKBRON", "TEKWALL", "SPACEW2")
    ):
        return "painted technology"
    if name in ("SW1METAL", "SW2METAL"):
        return "metal"
    return original


def build_channels(pixels, name, kind, original_family, context=None):
    """Return five PIL auxiliary maps and honest profile/mask metadata.

    Optional native-resolution switch_mask is the composited device-patch alpha;
    paired_pixels is the matching SW1/SW2 state. Reviewed device patches may
    supply switch_alloy='bronze'. Neither changes source albedo.
    """
    context = context or {}
    name = name.upper()
    family = _family(name, kind, original_family)
    maps, interpretation, properties = base.maps_for(pixels, family)
    size = maps["normal"].size
    rgba = (
        np.asarray(
            Image.fromarray(pixels).resize(size, Image.Resampling.BICUBIC),
            dtype=np.float32,
        )
        / 255
    )
    rgb = rgba[:, :, :3]
    lum = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    maximum, minimum = rgb.max(2), rgb.min(2)
    chroma = (maximum - minimum) / np.maximum(maximum, 0.04)
    visible = rgba[:, :, 3] > 0.5
    neutral = (1 - _smooth(chroma, 0.16, 0.42)) * _smooth(maximum, 0.025, 0.11)
    # This hue mask is consumed only by reviewed bronze profiles. Normalizing
    # the hue differences keeps shaded copper/bronze from turning dielectric;
    # the small near-black gate still excludes actual black holes/background.
    copper = (
        _smooth((rgb[:, :, 0] - rgb[:, :, 2]) / np.maximum(maximum, 0.01), 0.10, 0.35)
        * _smooth((rgb[:, :, 1] - rgb[:, :, 2]) / np.maximum(maximum, 0.01), 0.04, 0.18)
        * _smooth(maximum, 0.01, 0.05)
    )
    colored_paint = _smooth(chroma, 0.35, 0.65)
    metal = np.asarray(maps["metallic"], dtype=np.float32) / 255
    rough = np.asarray(maps["roughness"], dtype=np.float32) / 255
    hardware = np.zeros_like(lum)
    actuator = np.zeros_like(lum)
    profile = family
    correction = "Base family-guided interpretation retained"
    switch = kind == "wall" and name.startswith(("SW1", "SW2"))
    if switch:
        native_mask = context.get("switch_mask")
        partner = context.get("paired_pixels")
        if native_mask is not None:
            hardware = _mask(native_mask, size)
        elif partner is not None and partner.shape == pixels.shape:
            changed = np.any(pixels != partner, axis=2)
            yy, xx = np.where(changed)
            if len(xx):
                margin = max(3, round(min(pixels.shape[:2]) * 0.07))
                native_mask = np.zeros(pixels.shape[:2], dtype=np.float32)
                native_mask[
                    max(0, yy.min() - margin) : yy.max() + margin + 1,
                    max(0, xx.min() - margin) : xx.max() + margin + 1,
                ] = 1
                hardware = _mask(native_mask, size)
        if partner is not None and partner.shape == pixels.shape:
            actuator = _mask(np.any(pixels != partner, axis=2).astype(np.float32), size)
        bronze_relief = context.get("switch_alloy") == "bronze" or any(
            token in name[3:] for token in ("GARG", "LION", "SATYR")
        )
        # Copper-colored bronze is not paint when source-device ownership has
        # qualified that alloy. Paired changed actuator pixels always override
        # this exception, so colored eyes/buttons cannot become metal by tint.
        qualified_copper = copper if bronze_relief else np.zeros_like(copper)
        actuator = np.maximum(
            actuator, colored_paint * hardware * (1 - qualified_copper)
        )
        if any(token in name[3:] for token in ("SKIN", "SKULL")):
            metal[:] = 0
            profile = "organic / bone switch; nonmetal"
            correction = (
                "Flesh/bone switch art stays dielectric; no blanket metal overlay"
            )
        else:
            substrate = np.maximum(neutral, copper if bronze_relief else 0)
            if family != "metal":
                metal[:] = 0
            else:
                metal = 0.96 * neutral
            plate = hardware * substrate * (1 - actuator)
            metal = np.maximum(metal * (1 - actuator), 0.94 * plate)
            polish = 0.24 + 0.16 * (1 - lum) + 0.13 * (1 - substrate)
            rough = rough * (1 - plate) + polish * plate
            rough = rough * (1 - actuator) + (0.38 + 0.12 * (1 - lum)) * actuator
            profile = "source-masked switch housing + dielectric actuator"
            correction = "Actual switch patch/paired state localizes metal housing; shaded steel remains metal and colored/changed actuator pixels remain dielectric"
            if native_mask is None:
                correction += (
                    "; no switch localization available, conservatively retain backing"
                )
    elif kind == "wall" and (
        name.startswith(("BIGDOOR5", "BIGDOOR6", "BIGDOOR7", "WOODMET"))
        or name == "DOOR1"
    ):
        # Gray iron straps/rims contrast with warm brown wood in these reviewed
        # source textures. No name-only whole-leaf metal fill is introduced.
        hardware = neutral
        metal = 0.93 * hardware
        rough = rough * (1 - hardware) + (0.28 + 0.22 * (1 - lum)) * hardware
        profile = "wood leaf with neutral iron hardware"
        correction = "Warm wood stays dielectric; existing gray straps/rims get rough metal response"
    elif name == "BRWINDOW" and kind == "wall":
        y = np.linspace(0, 1, size[1])[:, None]
        hardware = neutral * _smooth(y, 0.42, 0.60)
        metal = 0.90 * hardware
        rough = rough * (1 - hardware) + (0.27 + 0.22 * (1 - lum)) * hardware
        profile = "brick backing / lower neutral window grille"
        correction = (
            "Brick remains dielectric; only lower neutral grille colors receive metal"
        )
    elif family == "metal":
        bronze = name.startswith(("BRONZE", "MIDBRONZ", "TEKBRON")) or name == "FLAT1_3"
        body = np.maximum(neutral, copper if bronze else 0)
        # Bare dark steel remains metal; highly colored stripes/labels are paint.
        # Oxide/dirt may remain nonmetal. Copper tint is explicitly profile-gated.
        metal = 0.96 * body
        rough = 0.23 + 0.23 * (1 - lum) + 0.17 * (1 - body)
        hardware = body
        profile = "bare metal body / dielectric paint and oxidation"
        correction = "Metal body is independent of high brightness; low-chroma steel and explicit bronze receive spatially varying polish"
    elif kind == "wall" and (
        name.startswith(("TEKBRON", "TEKWALL", "SPACEW2"))
        or name in ("ZZZFACE6", "ZZZFACE7", "ZZZFACE8", "ZZZFACE9")
    ):
        body = np.maximum(neutral, copper if name.startswith("TEKBRON") else 0)
        hardware = body
        metal = 0.91 * body
        rough = 0.29 + 0.23 * (1 - lum) + 0.19 * (1 - body)
        profile = "machinery / dielectric screens and colored insulation"
        correction = "Neutral machinery and explicit bronze are metal; colored screen/insulation art stays dielectric"
    elif kind == "wall" and name.startswith("CRAT"):
        edge = np.abs(lum - base.blur(lum, max(1, min(size) / 80)))
        hardware = neutral * _smooth(edge, 0.018, 0.075)
        metal = 0.88 * hardware
        rough = rough * (1 - hardware) + (0.31 + 0.19 * (1 - lum)) * hardware
        profile = "painted industrial crate / exposed neutral frame detail"
        correction = "Crate panels are painted dielectrics, not wood; neutral frame/edge details may expose metal"
    elif family in (
        "stone / concrete",
        "carved stone",
        "brick / mortar",
        "wood",
        "organic",
        "fabric",
        "vegetation",
        "lava crust",
        "sky / static artwork",
        "liquid / static sample",
    ):
        metal[:] = 0
    metal = np.clip(metal, 0, 0.97)
    rough = np.clip(rough, 0.20, 0.96)
    metal[~visible] = 0
    rough[~visible] = 1
    normal = np.asarray(maps["normal"]).copy()
    normal[~visible] = (128, 128, 255)
    ao = np.asarray(maps["ao"]).copy()
    ao[~visible] = 255
    maps["normal"] = Image.fromarray(normal, "RGB")
    maps["ao"] = Image.fromarray(ao, "L")
    maps["metallic"] = Image.fromarray(np.uint8(metal * 255), "L")
    maps["roughness"] = Image.fromarray(np.uint8(rough * 255), "L")
    spec = np.clip(0.12 + 0.50 * metal + 0.12 * (1 - rough), 0.08, 0.80)
    spec[~visible] = 0.08
    maps["specular"] = Image.fromarray(np.uint8(spec * 255), "L")
    selected = metal[visible]
    stats = dict(
        mean_metallic=round(float(selected.mean()), 4) if selected.size else 0,
        mean_roughness=round(float(rough[visible].mean()), 4) if selected.size else 1,
        metallic_fraction=(
            round(float((selected > 0.5).mean()), 4) if selected.size else 0
        ),
        hardware_fraction=(
            round(float((hardware[visible] > 0.5).mean()), 4) if selected.size else 0
        ),
        actuator_fraction=(
            round(float((actuator[visible] > 0.5).mean()), 4) if selected.size else 0
        ),
        mask_source=(
            "composited source patch alpha"
            if context.get("switch_mask") is not None
            else (
                "paired SW1/SW2 bounds"
                if context.get("paired_pixels") is not None
                else "reviewed profile/color features"
            )
        ),
    )
    if switch:
        stats["switch_alloy"] = (
            "bronze" if bronze_relief else "neutral steel / unspecified"
        )
    return maps, dict(
        family=family,
        profile=profile,
        mask_stats=stats,
        mean_metallic=stats["mean_metallic"],
        mean_roughness=stats["mean_roughness"],
        normal_extent=list(size),
        interpretation=interpretation + "; " + correction,
        limitation="Procedural semantic/feature interpretation, not recovered artist segmentation",
    )


def cpu_controls():
    pixels = np.full((32, 32, 4), (32, 32, 32, 255), dtype=np.uint8)
    pixels[:, 16:] = (80, 6, 6, 255)
    context = {"switch_mask": np.ones((32, 32), dtype=np.float32)}
    maps, _ = build_channels(pixels, "SW1METAL", "wall", "mixed switch panel", context)
    m = np.asarray(maps["metallic"])
    assert m[:, : m.shape[1] // 2 - 4].mean() > 180
    assert m[:, m.shape[1] // 2 + 4 :].max() < 5
    for family, name in (
        ("wood", "WOOD1"),
        ("stone / concrete", "STONE2"),
        ("organic", "SKIN2"),
    ):
        maps, _ = build_channels(pixels, name, "wall", family)
        assert np.asarray(maps["metallic"]).max() == 0, name
    wood = np.full((32, 32, 4), (110, 65, 30, 255), dtype=np.uint8)
    wood[:, 8:12] = (80, 80, 80, 255)
    maps, _ = build_channels(wood, "WOODMET1", "wall", "wood")
    m = np.asarray(maps["metallic"])
    assert m[:, :20].max() < 5 and m[:, 36:44].mean() > 180
    transparent = pixels.copy()
    transparent[:16, :, 3] = 0
    maps, _ = build_channels(transparent, "DOOR3", "wall", "metal")
    assert np.asarray(maps["metallic"])[:50].max() == 0
    bronze = np.full((32, 32, 4), (120, 75, 30, 255), dtype=np.uint8)
    bronze[:, 20:] = (160, 12, 12, 255)
    pair = bronze.copy()
    pair[:, 20:] = (12, 160, 12, 255)
    ctx = {"switch_mask": np.ones((32, 32), dtype=np.float32), "paired_pixels": pair}
    maps, _ = build_channels(bronze, "SW1WOOD", "wall", "wood", ctx)
    assert np.asarray(maps["metallic"])[:, :60].max() == 0
    ctx["switch_alloy"] = "bronze"
    maps, _ = build_channels(bronze, "SW1WOOD", "wall", "wood", ctx)
    m = np.asarray(maps["metallic"])
    assert m[:, :60].mean() > 200
    assert m[:, 90:].max() == 0
    dark_bronze = np.full((32, 32, 4), (24, 15, 5, 255), dtype=np.uint8)
    maps, _ = build_channels(
        dark_bronze,
        "SW1WOOD",
        "wall",
        "wood",
        {"switch_mask": np.ones((32, 32)), "switch_alloy": "bronze"},
    )
    assert np.asarray(maps["metallic"]).mean() > 225
    maps, _ = build_channels(dark_bronze, "WOOD1", "wall", "wood")
    assert np.asarray(maps["metallic"]).max() == 0
    for image in maps.values():
        image.load()
    n = np.asarray(maps["normal"]).astype(float)
    length = np.linalg.norm((n - 128) / 127, axis=2)
    assert np.all((length > 0.98) & (length < 1.02))
    return {
        "status": "PASS",
        "controls": [
            "dark gray switch housing metal",
            "dark red button dielectric",
            "wood/stone/flesh nonmetal",
            "wood leaf versus iron band",
            "transparent exterior conservative",
            "bronze requires reviewed alloy context",
            "paired red/green actuator remains dielectric on bronze housing",
            "dark bronze stays metal under qualified alloy",
            "same dark brown hue stays nonmetal wood without alloy context",
            "normal finite/unit within quantization",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(cpu_controls(), indent=2))
