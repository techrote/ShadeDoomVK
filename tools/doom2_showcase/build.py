"""Build the optional flashlight and local Doom II/DBP50 material add-ons."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FLASHLIGHT_FILES = ("ZSCRIPT", "CVARINFO", "MAPINFO", "KEYCONF", "MENUDEF")
HEROES = [
    "DOOR3",
    "SW1METAL",
    "BIGDOOR6",
    "WOODMET2",
    "TEKBRON1",
    "BRWINDOW",
    "SW1WOOD",
    "BRICK7",
]
FEATURE_PAGES = [
    (
        "SGSWITCH",
        "SWITCHES - metal housing, dielectric actuator",
        ["SW1METAL", "SW2METAL", "SW1WOOD", "SW1MARB", "SW1COMP", "SW1SKULL"],
    ),
    (
        "SGDOORS",
        "DOORS - steel versus wood and iron hardware",
        ["DOOR3", "EXITDOOR", "ZELDOOR", "BIGDOOR6", "DOOR1", "WOODMET2"],
    ),
    (
        "SGMIXED",
        "MIXED SURFACES - brick, wood and paint",
        ["WOODMET2", "BRWINDOW", "CRATE1", "TEKBRON1", "GRAY1", "BRICK7"],
    ),
]
CHANNELS = ("normal", "metallic", "roughness", "ao")


def build_flashlight(out):
    source = Path(__file__).resolve().parent / "flashlight"
    with ZipFile(out / "Local-Flashlight.pk3", "w") as package:
        for name in FLASHLIGHT_FILES:
            member = ZipInfo(name)
            member.compress_type = ZIP_DEFLATED
            package.writestr(
                member, (source / name).read_text(encoding="utf-8").encode("utf-8")
            )


def dbp50_material_inputs(effective_rows, original, replacement):
    """Yield changed art and switch context using the effective definition and patches."""
    import dbp50_effective as dbp
    import wall_materials as walls

    rows = {(row["kind"], row["name"]): row for row in effective_rows}
    decoder = dbp._IndexedOverlay(original | replacement)
    tables = dbp.texture_overrides(original, replacement)
    definitions = walls.definitions(original)
    if tables:
        definitions.update(walls.definitions(tables))
    for row in effective_rows:
        if row["rgba_changed"] and not row["placeholder"]:
            yield row, walls.context(row, rows, definitions, decoder)


def build_materials(out, iwad, pwad, include_gallery):
    from PIL import Image

    import dbp50_effective as dbp
    import material_generator as base
    import sprite_materials as sprites
    import wall_materials as walls
    from material_profiles_v2 import build_channels

    stock_sprites, palette = sprites.read_wad(iwad, dbp.IWAD_SHA256, b"IWAD")
    mod_sprites, mod_palette = ({}, None)
    if pwad:
        mod_sprites, mod_palette = sprites.read_wad(pwad, dbp.PWAD_SHA256, b"PWAD")

    def wall_maps(row, original_family, context):
        maps, info = build_channels(
            row["pixels"], row["name"], row["kind"], original_family, context
        )
        walls.validate_maps(maps, row["pixels"])
        return maps, info

    def write_wall_pack(game, entries, shared, overrides):
        definitions = []
        restriction = "iwad " if game == "DoomII" else ""
        with ZipFile(out / f"{game}-NormalPBR.pk3", "w", ZIP_DEFLATED) as package:
            for entry in entries:
                if entry["placeholder"]:
                    continue
                key = entry["kind"], entry["name"]
                target = "texture" if key[0] == "wall" else "flat"
                paths = {
                    channel: f"sdvkwallpbr/{entry['id']:04}/{channel}.png"
                    for channel in CHANNELS
                }
                for channel, path in paths.items():
                    data = overrides[key] if key in overrides else shared[key]
                    package.writestr(path, data[channel])
                layers = " ".join(
                    f'{c} "{paths[c]}" {{ filter linear }}' for c in CHANNELS
                )
                definitions.append(
                    f"material {target} {key[1]} {{ {restriction}{layers} }}"
                )
            package.writestr("GLDEFS", "\n".join(definitions) + "\n")
        return len(definitions)

    wad = base.Wad(iwad)
    rows = sorted(
        wad.textures() + wad.flats(), key=lambda row: (row["kind"], row["name"])
    )
    lookup = {name: wad.lump(name) for name in wad.by_name}
    definitions = walls.definitions(lookup)
    by_key = {(row["kind"], row["name"]): row for row in rows}
    shared = {}
    entries = []
    gallery_entries = []
    for ordinal, row in enumerate(rows, 1):
        kind, name = row["kind"], row["name"]
        key = kind, name
        family = base.family_of(name, kind)
        entry = {k: row[k] for k in ("kind", "name", "source_index", "placeholder")}
        entry.update(id=ordinal, family=family)
        entries.append(entry)
        if not entry["placeholder"] or include_gallery:
            maps, info = wall_maps(
                row, family, walls.context(row, by_key, definitions, wad)
            )
            shared[key] = {
                channel: sprites.png(base.np.asarray(maps[channel]))
                for channel in CHANNELS
            }
        if include_gallery:
            folder = out / "gallery-art" / f"{ordinal:04}"
            folder.mkdir(parents=True)
            images = {"albedo": Image.fromarray(row["pixels"]), **maps}
            paths = {}
            for channel, image in images.items():
                path = folder / f"{channel}.png"
                image.save(path)
                paths[channel] = path.relative_to(out).as_posix()
            height, width = row["pixels"].shape[:2]
            gallery_entries.append(
                dict(
                    entry,
                    family=info["family"],
                    width=width,
                    height=height,
                    files=paths,
                    aliases={
                        "legacy": f"L{ordinal:07d}",
                        "normal": f"N{ordinal:07d}",
                        "pbr": f"P{ordinal:07d}",
                    },
                )
            )

    report = {}
    count = write_wall_pack("DoomII", entries, shared, {})
    manifest = sprites.build(out, "DoomII", stock_sprites, palette, set())
    report["DoomII"] = {
        "world_bindings": count,
        "sprite_bindings": len(manifest["bindings"]),
    }

    if pwad:
        effective_rows = dbp.effective_rows(iwad, pwad, entries)
        mod_lookup = dbp._lumps(pwad, dbp.PWAD_SHA256, b"PWAD")
        overrides = {}
        for row, context in dbp50_material_inputs(effective_rows, lookup, mod_lookup):
            maps, _ = wall_maps(row, row["family"], context)
            overrides[row["kind"], row["name"]] = {
                channel: sprites.png(base.np.asarray(maps[channel]))
                for channel in CHANNELS
            }
        count = write_wall_pack("DBP50", entries, shared, overrides)
        manifest = sprites.build(
            out,
            "DBP50",
            stock_sprites | mod_sprites,
            mod_palette or palette,
            set(mod_sprites),
        )
        report["DBP50"] = {
            "world_bindings": count,
            "sprite_bindings": len(manifest["bindings"]),
            "adapted_world_bindings": len(overrides),
        }

    if include_gallery:
        import gallery

        gallery.build(
            {
                "entries": gallery_entries,
                "iwad": iwad.name,
                "iwad_sha256": dbp.IWAD_SHA256,
            },
            out,
            HEROES,
            FEATURE_PAGES,
        )
    (out / "material-build.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--doom2", type=Path, help="owner-supplied Doom II IWAD")
    parser.add_argument("--dbp50", type=Path, help="owner-supplied DBP50 PWAD")
    parser.add_argument(
        "--gallery",
        action="store_true",
        help="also build the wall and flat comparison gallery",
    )
    args = parser.parse_args()
    if (args.dbp50 or args.gallery) and not args.doom2:
        parser.error("--dbp50 and --gallery require --doom2")
    out = args.out.resolve()
    if out.exists():
        parser.error("--out must name a new directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with TemporaryDirectory(prefix=".doom2-showcase-", dir=out.parent) as staging:
            prepared = Path(staging) / "build"
            prepared.mkdir()
            build_flashlight(prepared)
            if args.doom2:
                build_materials(prepared, args.doom2, args.dbp50, args.gallery)
            prepared.rename(out)
    except (OSError, ValueError, ImportError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Built add-ons in {out}")


if __name__ == "__main__":
    main()
