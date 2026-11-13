"""Build a private, standalone Doom II material gallery. No engine changes."""

from pathlib import Path
import hashlib
import html
import json
import math
import struct
import zipfile
from PIL import Image, ImageDraw, ImageFont
from navigation import nav_members


def png(im):
    import io

    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def wad(name, text):
    lumps = [(name, b""), ("TEXTMAP", text.encode()), ("ENDMAP", b"")]
    data = bytearray(b"PWAD" + struct.pack("<II", len(lumps), 0))
    directory = []
    for n, b in lumps:
        directory.append((len(data), len(b), n))
        data.extend(b)
    offset = len(data)
    for p, s, n in directory:
        data.extend(struct.pack("<II8s", p, s, n.encode().ljust(8, b"\0")))
    struct.pack_into("<I", data, 8, offset)
    return bytes(data)


class Map:
    def __init__(self):
        self.rows = {k: [] for k in ("vertex", "sector", "sidedef", "linedef", "thing")}
        self.vertices = {}

    def add(self, k, **d):
        i = len(self.rows[k])
        self.rows[k].append(d)
        return i

    def sector(self, floor=0, ft="LABFLOOR", light=176):
        return self.add(
            "sector",
            heightfloor=floor,
            heightceiling=256,
            texturefloor=ft,
            textureceiling="LABCEIL",
            lightlevel=light,
        )

    def line(
        self, a, b, front, back=None, texture="LABWALL", mid="-", special=0, scale=1
    ):
        for p in (a, b):
            if p not in self.vertices:
                self.vertices[p] = self.add("vertex", x=p[0], y=p[1])
        va = self.vertices[a]
        vb = self.vertices[b]
        s = self.add(
            "sidedef",
            sector=front,
            texturemiddle=texture if back is None else mid,
            texturebottom=texture,
            texturetop=texture,
            scalex_bottom=scale,
            scaley_bottom=scale,
            scalex_mid=2,
            scaley_mid=2,
        )
        if mid != "-":
            self.rows["sidedef"][s].update(light_mid=255, lightabsolute_mid=True)
        d = dict(v1=va, v2=vb, sidefront=s, blocking=back is None)
        if back is not None:
            d.update(
                sideback=self.add(
                    "sidedef",
                    sector=back,
                    texturemiddle="-",
                    texturebottom=texture,
                    texturetop=texture,
                ),
                twosided=True,
            )
        if special:
            d.update(special=special, playeruse=True, repeatspecial=True)
        self.add("linedef", **d)

    def rect(self, x0, y0, x1, y1, outer, inner, texture="LABWALL", scale=1):
        # Counterclockwise solid island: room faces are front/right.
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            self.line(a, b, outer, inner, texture, scale=scale)

    def thing(self, t, x, y, z=0, angle=0, **kw):
        self.add(
            "thing",
            type=t,
            x=x,
            y=y,
            height=z,
            angle=angle,
            skill1=True,
            skill2=True,
            skill3=True,
            skill4=True,
            skill5=True,
            single=True,
            **kw,
        )

    def text(self):
        def val(v):
            return str(v).lower() if isinstance(v, bool) else json.dumps(v)

        return 'namespace="ZDoom";\n' + "".join(
            k + " { " + " ".join(f"{a}={val(b)};" for a, b in d.items()) + " }\n"
            for k, rows in self.rows.items()
            for d in rows
        )


def font(size):
    return ImageFont.load_default(size=size)


def label(lines, width=2304):
    im = Image.new("RGBA", (width, 512))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, width, 126), fill=(14, 20, 28, 255))
    d.text((20, 6), lines[0], font=font(34), fill="#ffe4a1")
    for x, t in zip(
        (80, 848, 1616), ("ORIGINAL DIFFUSE", "NORMAL + SPECULAR", "PBR MATERIAL")
    ):
        d.text((x, 66), t, font=font(25), fill="#e6f3ff")
    return png(im)


def build(manifest, outroot, hero_names, feature_groups):
    entries = manifest["entries"]
    byname = {e["name"]: e for e in entries}
    preferred = hero_names or [
        "BRICK7",
        "METAL2",
        "WOOD1",
        "STONE2",
        "TEKWALL4",
        "FLAT5_4",
    ]
    heroes = [byname[n] for n in preferred if n in byname]
    if len(heroes) < 6:
        heroes += [e for e in entries if e not in heroes][: 6 - len(heroes)]
    pages = [
        (
            "SGSHOW",
            (
                "START HERE - switches, doors and mixed surfaces"
                if hero_names
                else "START HERE - six familiar materials"
            ),
            heroes,
        )
    ]
    for mapname, title, names in feature_groups or []:
        pages.append((mapname, title, [byname[n] for n in names]))
    families = sorted({e["family"] for e in entries})
    for fam in families:
        group = [e for e in entries if e["family"] == fam]
        for start in range(0, len(group), 8):
            batch = group[start : start + 8]
            name = f"SG{len(pages):04d}"
            pages.append(
                (name, f'{fam}: {batch[0]["name"]} - {batch[-1]["name"]}', batch)
            )
    members = nav_members([p[0] for p in pages], [p[1] for p in pages])
    defs = []
    for name, color in [
        ("LABFLOOR", (66, 71, 78)),
        ("LABCEIL", (42, 48, 55)),
        ("LABWALL", (62, 69, 78)),
    ]:
        members["textures/" + name + ".png"] = png(Image.new("RGB", (64, 64), color))
    for e in entries:
        for mode, alias in e["aliases"].items():
            members["textures/" + alias + ".png"] = (
                outroot / e["files"]["albedo"]
            ).read_bytes()
        for channel, path in e["files"].items():
            if channel != "albedo":
                members[path] = (outroot / path).read_bytes()
        f = e["files"]
        n = e["aliases"]["normal"]
        p = e["aliases"]["pbr"]
        defs.append(
            f'material texture {n} {{ normal "{f["normal"]}" {{ filter linear }} specular "{f["specular"]}" {{ filter linear }} }}'
        )
        defs.append(
            f'material texture {p} {{ normal "{f["normal"]}" {{ filter linear }} metallic "{f["metallic"]}" {{ filter linear }} roughness "{f["roughness"]}" {{ filter linear }} ao "{f["ao"]}" {{ filter linear }} }}'
        )
    members["GLDEFS"] = "\n".join(defs).encode()
    coverage = []
    for page_index, (mapname, title, batch) in enumerate(pages):
        m = Map()
        room = m.sector()
        last_y = (len(batch) - 1) * 480 + 320
        pts = [(-704, -720), (-704, last_y), (704, last_y), (704, -720)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            m.line(a, b, room)
        m.thing(1, 0, -620, angle=90)
        # An entrance directory, with use-able next/previous signs behind player.
        entrance = Image.new("RGBA", (2304, 512))
        d = ImageDraw.Draw(entrance)
        d.rectangle((0, 0, 2304, 512), fill=(17, 26, 35, 255))
        instructions = [
            title,
            "F1: choose any page | Walk around each triplet",
            "Same artwork + equal lights. All panels stay in hardware mode.",
            "LEFT original diffuse | CENTRE normal/spec | RIGHT PBR",
            "Normal/PBR maps are procedural interpretations, not recovered originals.",
            "No displacement, ray tracing, baked GI or backend switching.",
            "USE: PREVIOUS PAGE                     USE: NEXT PAGE",
        ]
        for j, t in enumerate(instructions):
            d.text(
                (20, 20 + j * 64),
                t,
                font=font(25 if j else 31),
                fill="#e5ebef" if j else "#ffda83",
            )
        sign = f"H{page_index:06d}"
        members["textures/" + sign + ".png"] = png(entrance)
        # South wall faces north; its middle uses scale2, sign spans768world.
        m.line((576, -719), (-576, -719), room, room, mid=sign)
        m.line((576, -718), (0, -718), room, room, mid="-", special=243)
        m.line((0, -718), (-576, -718), room, room, mid="-", special=244)
        for row, e in enumerate(batch):
            y = row * 480
            caption = f'{e["name"]} / {e["kind"].upper()} / {e["family"].upper()} | {e["width"]}x{e["height"]}'
            sign = f"T{page_index:03d}{row:03d}"
            members["textures/" + sign + ".png"] = label([caption])
            m.line((-576, y - 10), (576, y - 10), room, room, mid=sign)
            for x, mode in zip((-384, 0, 384), ("legacy", "normal", "pbr")):
                alias = e["aliases"][mode]
                panel = m.sector(192, alias)
                m.rect(
                    x - 96,
                    y,
                    x + 96,
                    y + 24,
                    room,
                    panel,
                    alias,
                    scale=max(e["width"], e["height"]) / 192,
                )
                tile = m.sector(0, alias)
                m.rect(x - 96, y - 224, x + 96, y - 40, room, tile, alias)
                # Duplicate local light arrangement for each material treatment.
                m.thing(
                    9800, x - 64, y - 100, 132, arg0=220, arg1=200, arg2=176, arg3=108
                )
                m.thing(9800, x + 70, y - 92, 48, arg0=56, arg1=96, arg2=168, arg3=80)
            coverage.append(
                dict(
                    map=mapname,
                    row=row + 1,
                    name=e["name"],
                    kind=e["kind"],
                    family=e["family"],
                    aliases=e["aliases"],
                )
            )
        members["maps/" + mapname + ".wad"] = wad(mapname, m.text())
    members["SHOWCASE.txt"] = (
        b"Local Doom II artwork; private owner use. F1 opens page menu. No engine changes. Procedural material interpretations. Full coverage in external manifest/index."
    )
    output = outroot / "DoomII-Material-Gallery.pk3"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, 6) as z:
        for name, data in sorted(members.items()):
            z.writestr(name, data)
    report = dict(
        source={"iwad": manifest["iwad"], "sha256": manifest["iwad_sha256"]},
        materials=len(entries),
        pages=len(pages),
        source_coverage=coverage,
        pk3_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        interpretation="procedural material art; local derived IWAD artwork; side-by-side material treatments, not historical renderer modes",
    )
    (outroot / "gallery-manifest.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    rows = []
    for e in entries:
        loc = next(
            c
            for c in coverage
            if c["name"] == e["name"]
            and c["kind"] == e["kind"]
            and c["map"] != "SGSHOW"
        )
        import os

        preview_path = Path(
            os.path.relpath(outroot / e["files"]["albedo"], outroot)
        ).as_posix()
        rows.append(
            '<tr><td><img src="'
            + html.escape(preview_path)
            + '"></td><td>'
            + html.escape(e["name"])
            + "</td><td>"
            + html.escape(e["kind"])
            + "</td><td>"
            + html.escape(e["family"])
            + "</td><td><code>map "
            + loc["map"]
            + "</code> / bay "
            + str(loc["row"])
            + "</td></tr>"
        )
    index = (
        '<!doctype html><meta charset="utf-8"><title>Doom II Material Gallery Index</title><style>body{background:#161c23;color:#e5edf5;font:16px system-ui;margin:32px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #3a4652}img{width:96px;height:80px;object-fit:contain;image-rendering:pixelated}code{color:#ffda83}input{padding:12px;font:inherit}</style><h1>Doom II Material Gallery</h1><p>All '
        + str(len(entries))
        + ' wall/flat entries. Original artwork with procedural material interpretations. F1 in game opens the page selector. This index shows original albedo; inspect material response in the game.</p><input id="q" placeholder="Filter texture or family" oninput="document.querySelectorAll(\'tbody tr\').forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(this.value.toLowerCase()))"><table><thead><tr><th>Artwork</th><th>Name</th><th>Kind</th><th>Material family</th><th>In-game location</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )
    (outroot / "INDEX.html").write_text(index, encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "source_coverage"}, indent=2
        )
    )
