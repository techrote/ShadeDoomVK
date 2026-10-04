#!/usr/bin/env python3
"""Prepare a synthetic #110 mod and capture inputs; never launch a renderer.

Generated artifacts are disposable acceptance inputs, not authoritative repo
instructions. Native compilation/validation/readback remains a separate gate.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WIDTH, HEIGHT = 16, 4
INDEX_ROW = (5, 5, 250, 250, 10, 10, 20, 20, 96, 96, 160, 160, 200, 200, 32, 32)
REMAP_A = {5: 10, 250: 20, 96: 160, 160: 96, 10: 32, 20: 200}
REMAP_B = {5: 96, 250: 160, 96: 20, 160: 10, 10: 200, 20: 32, 32: 250, 200: 5}
# FRenderStyle = bytes {Add=1, Src=2, InvSrc=3, Alpha1|InvertSource=18}.
# DTA_RenderStyle parses AsDWORD; STYLE_InverseMultiply has different semantics.
INVERSE_STYLE = 0x12030201
NORMAL_STYLE = 0x02030201
FRAME_EXTENT = (640, 480)
PANELS_X = (120, 284, 448)
PANEL_EXTENT = (128, 20)
ROWS_Y = (54, 104, 154, 204, 254, 304, 354)
SOURCE_FILES = (
    "tools/pf_oracle/prepare_indexed_material_runtime.py",
    "src/d_main.cpp", "src/d_main.h",
    "wadsrc/static/zscript/events.zs", "wadsrc/static/zscript/engine/base.zs",
    "wadsrc/static/zscript/doombase.zs",
    "src/common/rendering/v_video.cpp", "src/common/platform/win32/base_sysfb.cpp",
    "src/common/console/c_dispatch.cpp",
    "src/common/console/c_cvars.cpp", "src/common/scripting/interface/vmnatives.cpp",
    "src/common/engine/i_net.h", "src/d_net.cpp", "src/g_game.cpp",
    "src/events.cpp", "src/g_statusbar/shared_sbar.cpp",
    "src/gamedata/gi.cpp", "src/maploader/udmf.cpp",
    "src/common/2d/v_draw.cpp", "src/common/2d/v_2ddrawer.cpp",
    "src/common/engine/renderstyle.h", "src/common/engine/renderstyle.cpp",
    "src/common/engine/palettecontainer.cpp", "src/r_data/r_translate.cpp",
    "src/common/textures/formats/patchtexture.cpp", "src/common/textures/formats/flattexture.cpp",
    "src/common/textures/imagehelpers.h", "src/common/textures/texture.cpp",
    "src/common/textures/hw_material.cpp",
    "src/common/rendering/hwrenderer/hw_draw2d.cpp",
    "src/common/rendering/vulkan/textures/vk_hwtexture.cpp",
    "src/common/rendering/vulkan/textures/vk_hwtexture.h",
    "src/common/rendering/vulkan/samplers/vk_samplers.cpp",
    "wadsrc/static/shaders/scene/material_paletted.glsl",
    "wadsrc/static/shaders/scene/material_gettexel.glsl",
    "wadsrc/static/shaders/scene/vert_main.glsl",
    "wadsrc/static/shaders/scene/frag_main.glsl",
    "wadsrc/static/shaders/scene/lightmode.glsl",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def doom_patch(rows: list[list[int]]) -> bytes:
    """One opaque, bounded Doom column post per column (height below 255)."""
    if not rows or not rows[0] or len(rows) >= 255:
        raise ValueError("patch requires nonempty height <255")
    width, height = len(rows[0]), len(rows)
    if any(len(row) != width or any(not 0 <= n <= 255 for n in row) for row in rows):
        raise ValueError("nonrectangular/out-of-range patch pixels")
    columns = [bytes((0, height, 0)) + bytes(row[x] for row in rows) + bytes((0, 255))
               for x in range(width)]
    offset = 8 + width * 4
    offsets = []
    for column in columns:
        offsets.append(offset)
        offset += len(column)
    return struct.pack("<HHhh", width, height, 0, 0) + struct.pack("<" + "I" * width, *offsets) + b"".join(columns)


def wad(lumps: list[tuple[str, bytes]]) -> bytes:
    data, directory = bytearray(), bytearray()
    for name, payload in lumps:
        encoded = name.encode("ascii")
        if not 1 <= len(encoded) <= 8:
            raise ValueError("WAD lump names require 1..8 ASCII characters")
        directory += struct.pack("<II8s", 12 + len(data), len(payload), encoded)
        data += payload
    return struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory


def translation_lump() -> str:
    def line(name, mapping):
        return name + " = " + ", ".join(f'"{n}:{n}={dest}:{dest}"' for n, dest in mapping.items())
    return line("PF110_A", REMAP_A) + "\n" + line("PF110_B", REMAP_B) + "\n"


def textmap() -> str:
    # Clockwise boundary: each one-sided line's right side contains sector 0.
    parts = ['namespace = "ZDoom";']
    for x, y in ((-128, -128), (-128, 128), (128, 128), (128, -128)):
        parts.append(f"vertex {{ x = {x}.0; y = {y}.0; }}")
    parts.append('sector { heightfloor = 0; heightceiling = 128; texturefloor = "PF110FL"; textureceiling = "PF110FL"; lightlevel = 255; }')
    for i in range(4):
        parts.append('sidedef { sector = 0; texturemiddle = "PF110W"; }')
        parts.append(f"linedef {{ v1 = {i}; v2 = {(i+1)%4}; sidefront = {i}; blocking = true; }}")
    parts.append("thing { x = 0.0; y = 0.0; angle = 0; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; coop = true; dm = true; }")
    return "\n".join(parts) + "\n"


def zscript() -> str:
    # No play-state writes from RenderOverlay; all lookups are bounded fixture
    # inputs. Registration comes from the actual TRNSLATE parser, not a fake ID.
    return '''version "4.5"
class PF110Overlay : EventHandler
{
    ui void Label(double y, String text)
    {
        Screen.DrawText(SmallFont, Font.CR_WHITE, 8, y, text);
    }
    ui void Panel(String name, double x, double y, bool indexed, TranslationID trans,
                  int style = 0x02030201, int tint = 0xffffffff, double width = 128)
    {
        TextureID tex = TexMan.CheckForTexture(name, TexMan.Type_Any, TexMan.TryAny);
        Screen.DrawTexture(tex, false, x, y,
            DTA_DestWidthF, width, DTA_DestHeight, 20,
            DTA_TopOffset, 0, DTA_LeftOffset, 0, DTA_NoOffset, true,
            DTA_Indexed, indexed, DTA_TranslationIndex, trans,
            DTA_RenderStyle, style, DTA_Color, tint, DTA_Masked, false);
    }
    override void RenderOverlay(RenderEvent e)
    {
        // The raw diagnostic runs before preview so it owns first-use order.
        if (!CVar.GetCVar('pf110_overlay').GetBool()) return;
        // Actual 3D/SWCanvas output remains visible below y=404.
        Screen.Clear(0, 0, 640, 404, 0xff101010);
        if (Screen.GetWidth() != 640 || Screen.GetHeight() != 480)
        {
            Label(8, "PF110 BLOCKER: expected native 640x480 extent");
            return;
        }
        TranslationID a = Translation.GetID('PF110_A');
        TranslationID b = Translation.GetID('PF110_B');
        if (a == -1 || b == -1)
        {
            Label(8, "PF110 BLOCKER: named TRNSLATE registration missing");
            return;
        }
        // A tick wait is not a rendered-frame count. This bounded, config-only
        // mod cvar attests actual enabled UI dispatch without playsim writes.
        CVar frameCounter = CVar.GetCVar('pf110_overlay_frames');
        int enabledFrames = frameCounter.GetInt();
        if (enabledFrames < 2)
        {
            enabledFrames++;
            frameCounter.SetInt(enabledFrames);
            if (enabledFrames == 2)
                Console.Printf("PF110_OVERLAY_READY mode=%d filter=%d extent=640x480 frames=2",
                    CVar.GetCVar('vid_rendermode').GetInt(), CVar.GetCVar('gl_texture_filter').GetInt());
        }
        Label(8, "PF110 synthetic indexed material compatibility fixture");
        Label(23, String.Format("mode=%d filter=%d; presentation only; raw oracle separate",
            CVar.GetCVar('vid_rendermode').GetInt(), CVar.GetCVar('gl_texture_filter').GetInt()));
        Label(40, "neutral: indexed / ordinary / flat source");
        Panel("PF110SRC", 120, 54, true, 0);
        Panel("PF110SRC", 284, 54, false, 0);
        Panel("PF110FL", 448, 54, true, 0);
        Label(90, "first use source A: A / B / A (same texture)");
        Panel("PF110SA", 120, 104, true, a);
        Panel("PF110SA", 284, 104, true, b);
        Panel("PF110SA", 448, 104, true, a);
        Label(140, "first use source B: B / A / B (same texture)");
        Panel("PF110SB", 120, 154, true, b);
        Panel("PF110SB", 284, 154, true, a);
        Panel("PF110SB", 448, 154, true, b);
        Label(190, "inverse A / old-order reference / REJECTED row-order model");
        Panel("PF110SA", 120, 204, true, a, 0x12030201);
        // Literal 255-remap[n] indices use the same discrete indexed sampler;
        // ordinary controls elsewhere retain the configured global filter.
        Panel("PF110IA", 284, 204, true, 0);
        Panel("PF110WR", 448, 204, false, 0);
        Label(240, "DTA_Color control: indexed A / literal indexed ref / RedIsAlpha");
        Panel("PF110SA", 120, 254, true, a, 0x02030201, 0xff80c0ff);
        // Same indexed route/style/tag, independent pretranslated source bytes.
        // Indexed AddTexture converts DTA_Color-derived vertex RGB to mLightLevel;
        // this is not a direct uObjectColor/getTexel tint oracle.
        Panel("PF110RA", 284, 254, true, 0, 0x02030201, 0xff80c0ff);
        TextureID src = TexMan.CheckForTexture("PF110SRC", TexMan.Type_Any, TexMan.TryAny);
        Screen.DrawTexture(src, false, 448, 254, DTA_DestWidth, 128, DTA_DestHeight, 20,
            DTA_FillColor, 0xff40d080, DTA_LegacyRenderStyle, STYLE_Shaded,
            DTA_TranslationIndex, 0, DTA_Indexed, false);
        Label(290, "off-grid boundaries: indexed A / reference / raw flat");
        Panel("PF110SA", 120.25, 304, true, a, 0x02030201, 0xffffffff, 127.5);
        Panel("PF110RA", 284.25, 304, false, 0, 0x02030201, 0xffffffff, 127.5);
        Panel("PF110FL", 448.25, 304, true, 0, 0x02030201, 0xffffffff, 127.5);
        Label(340, "ordinary translation A / missing input (must stay background) / indexed alpha");
        Panel("PF110SRC", 120, 354, false, a);
        TextureID missing = TexMan.CheckForTexture("PF110_MISSING_INPUT", TexMan.Type_Any, TexMan.TryAny | TexMan.DontCreate);
        Screen.DrawTexture(missing, false, 284, 354, DTA_Indexed, true, DTA_TranslationIndex, a,
            DTA_DestWidth, 128, DTA_DestHeight, 20);
        Screen.DrawTexture(src, false, 448, 354, DTA_Indexed, true, DTA_TranslationIndex, a,
            DTA_DestWidth, 128, DTA_DestHeight, 20, DTA_Alpha, 0.5,
            DTA_LegacyRenderStyle, STYLE_Translucent);
        Label(385, "Bottom strip: actual empty-room renderer output; mode2 palette / mode0 SWCanvas.");
    }
}
'''


def members() -> dict[str, bytes]:
    def patch(row):
        return doom_patch([list(row) for _ in range(HEIGHT)])
    a = [REMAP_A.get(n, n) for n in INDEX_ROW]
    inverse = [255 - n for n in a]
    rejected = [REMAP_A.get(255 - n, 255 - n) for n in INDEX_ROW]
    flat = bytes(INDEX_ROW * 4) * 64  # 64x64, row-major; no copied IWAD content.
    return {
        "ZSCRIPT": zscript().encode(),
        "MAPINFO": b'gameinfo { AddEventHandlers = "PF110Overlay" }\nmap PF110 "Indexed material laboratory" { nointermission }\n',
        "CVARINFO": b'nosave bool pf110_overlay = false;\nnosave int pf110_overlay_frames = 0;\n',
        "TRNSLATE": translation_lump().encode(),
        "TEXTURES": b'Texture PF110W, 16, 4 { Patch PF110SRC, 0, 0 }\n',
        "patches/PF110SRC.lmp": patch(INDEX_ROW),
        "patches/PF110SA.lmp": patch(INDEX_ROW),
        "patches/PF110SB.lmp": patch(INDEX_ROW),
        "patches/PF110RA.lmp": patch(a),
        "patches/PF110IA.lmp": patch(inverse),
        "patches/PF110WR.lmp": patch(rejected),
        "flats/PF110FL.lmp": flat,
        "maps/PF110.wad": wad([("PF110", b""), ("TEXTMAP", textmap().encode()), ("ENDMAP", b"")]),
    }


def archive_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, files[name])
    return output.getvalue()


def iwad_identity(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 12:
        raise ValueError("IWAD header missing")
    magic, count, offset = struct.unpack_from("<4sII", raw)
    if magic != b"IWAD" or count > 1000000 or offset + count * 16 > len(raw):
        raise ValueError("invalid IWAD directory")
    palette = None
    for i in range(count):
        start, size, name = struct.unpack_from("<II8s", raw, offset + i * 16)
        if start + size > len(raw):
            raise ValueError("IWAD lump bounds invalid")
        if name.rstrip(b"\0") == b"PLAYPAL" and size >= 768:
            palette = raw[start:start + 768]
    if palette is None:
        raise ValueError("first base palette missing")
    if palette[245*3:246*3] == palette[20*3:21*3]:
        raise ValueError("selected IWAD cannot distinguish inverse order witness colours245/20")
    return {"path": str(path.resolve()), "sha256": digest(raw), "bytes": len(raw),
            "playpalFirst768Sha256": digest(palette), "copiedIntoMod": False,
            "inverseOrderWitness": {"sourceIndex": 5, "oldIndex": 245, "rejectedIndex": 20,
                "oldRGB": list(palette[245*3:246*3]), "rejectedRGB": list(palette[20*3:21*3]),
                "requiresActualPaletteRemapState": True}}


def roi_metadata() -> list[dict]:
    names = (
        ("neutral-indexed", "neutral-ordinary", "neutral-flat"),
        ("a-first-A", "a-first-B", "a-repeat-A"),
        ("b-first-B", "b-first-A", "b-repeat-B"),
        ("inverse-A", "inverse-reference", "rejected-row-order-model"),
        ("tinted-indexed-A", "tinted-reference", "ordinary-red-is-alpha"),
        ("boundary-indexed-A", "boundary-reference", "boundary-flat"),
        ("ordinary-translation-A", "missing-input", "indexed-translucent-A"),
    )
    return [{"name": name, "rect": [x, y, *PANEL_EXTENT],
             "interiorSamples": [[x+4+column*8, y+10] for column in range(WIDTH)],
             "exposure": "presentation settings in run configuration",
             "units": "presented RGB bytes, not raw palette/index/shader values"}
            for row, y in zip(names, ROWS_Y) for name, x in zip(row, PANELS_X)]


def configuration(mode: int, filtering: int) -> str:
    return f'''[GlobalSettings]
vid_preferbackend=1
vid_rendermode={mode}
vid_fullscreen=false
win_w=640
win_h=480
win_maximized=false
vid_vsync=false
vid_maxfps=60
gl_texture_filter={filtering}
gl_texture_filter_anisotropic=1
hw_2dmip=false
gl_multisample=0
gl_tonemap=0
vid_brightness=0
vid_contrast=1
vid_gamma=1

[Doom.ConsoleVariables]
screenblocks=12
crosshair=0
'''


def capture_script(shot: Path) -> str:
    # FExecList dispatches each physical line independently. Only a semicolon
    # remainder inside the same AddCommandString call is deferred by wait.
    # The selected ticdup=1 input backlog is bounded at17 by BACKUPTICS/2-1.
    # Wait35 after enabling crosses display boundaries; the UI marker and
    # decoded PNG/ROI acceptance are still required to prove presentation.
    commands = ["wait 105", "vid_setsize 640 480", "wait 5", "pf110_overlay true",
                "wait 35", f'screenshot "{shot.as_posix()}"', "wait 5", "quit"]
    return "; ".join(commands) + "\n"


def prepare(out: Path, iwad: Path, exe: Path | None = None) -> dict:
    identity = iwad_identity(iwad)
    source = {name: digest((ROOT/name).read_bytes()) for name in SOURCE_FILES}
    executable = None if exe is None else {"path": str(exe.resolve()), "sha256": digest(exe.read_bytes()), "bytes": exe.stat().st_size}
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    files = members()
    archive = archive_bytes(files)
    mod = out / "pf110-indexed-material.pk3"
    mod.write_bytes(archive)
    scenarios = []
    for name, mode in (("hardware-truecolour", 4), ("hardware-palette", 2), ("software-palette-swcanvas", 0)):
        for filter_name, filtering in (("nearest", 0), ("linear", 2)):
            case = f"{name}-{filter_name}"
            run = out / case
            run.mkdir(exist_ok=True)
            cfg, script = run / "fixture.ini", run / "capture.cfg"
            cfg.write_text(configuration(mode, filtering), encoding="utf-8", newline="\n")
            shot = run / "presentation.png"
            script.write_text(capture_script(shot), encoding="utf-8", newline="\n")
            command = [str(exe.resolve()) if exe else "<verified-native-executable>", "-stdout", "-noautoload", "-nosound", "-nojoy",
                       "-iwad", str(iwad.resolve()), "-file", str(mod), "-config", str(cfg), "-width", "640", "-height", "480",
                       "+map", "PF110", "+exec", str(script)]
            scenarios.append({"id": case, "rendererMode": mode, "globalFilter": filtering,
                              "extent": list(FRAME_EXTENT), "config": str(cfg), "configSha256": digest(cfg.read_bytes()),
                              "captureScript": str(script), "captureScriptSha256": digest(script.read_bytes()),
                              "presentationCapture": str(shot), "command": command, "executed": False,
                              "protectedRoute": "hardware palette state" if mode == 2 else "real SWSceneDrawer SWCanvas" if mode == 0 else "ordinary hardware truecolour"})
    source_after = {name: digest((ROOT/name).read_bytes()) for name in SOURCE_FILES}
    if source_after != source:
        raise ValueError("fixture interface sources changed during preparation; regenerate after source freeze")
    report = {"schema": "pf110-indexed-runtime-inputs-v1", "status": "prepared-unaccepted", "gpuExecuted": False,
              "preparationNotes": ["ZScript version directive is 4.5 without a semicolon; native compilation remains required.",
                  "CVar.GetCVar is declared by the actual static doombase.zs extension; the engine-only base.zs declaration is not the whole public ABI.",
                  "Windows win_w/win_h describe outer-window dimensions; vid_setsize 640 480 requests client dimensions after initialization via SetWindowSize/AdjustWindowRectEx.",
                  "A startup Resolution line before vid_setsize is not proof of the acceptance extent; retain actual client/render extent before diagnostic/preview.",
                  "Capture exec input is one physical semicolon chain: actual wait commands defer their remaining commands; separate wait lines do not defer subsequent exec lines.",
                  "The post-enabled wait is35 ticks, exceeding the selected ticdup1 catch-up batch bound17; actual RenderOverlay-only bounded counter must emit the matching frames2 marker and decoded PNG/ROIs must pass.",
                  "PF110IA is an independent literal 255-remap[n] R8 reference drawn indexed with translation0 and normal style; ordinary neutral, translation, boundary and RedIsAlpha controls retain global filtering and need not match discrete palette bytes under linear filtering.",
                  "Preparation tests are CPU input/source checks, not ZScript compilation or indexed Vulkan execution.",
                  "Use an isolated hashed IWAD copy and retain the complete actually loaded archive list; -noautoload alone does not prove absence of sibling extras.wad."],
              "zscriptCompilation": "not-run", "mod": {"path": str(mod), "sha256": digest(archive),
                  "members": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in sorted(files.items())}},
              "iwad": identity, "executable": executable, "fixtureInterfaceSources": source,
              "fixtureInterfaceSourcesUnchangedDuringPreparation": True,
              "syntheticInput": {"width": WIDTH, "height": HEIGHT, "rowMajorIndices": list(INDEX_ROW)*HEIGHT,
                  "ordinaryTexture": "PF110SRC", "firstUseOwners": ["PF110SA", "PF110SB"], "flat": "PF110FL",
                  "translations": {"PF110_A": REMAP_A, "PF110_B": REMAP_B},
                  "indexProducer": "actual Doom patch/flat loader -> Get8BitPixels(false) -> CreateTexBuffer",
                  "sourceRemapPolicy": "R_ParseTrnslate AddIndexRange uses actual GPalette.Remap; native state must attest it",
                  "inverseStyleAsDWORD": INVERSE_STYLE, "normalStyleAsDWORD": NORMAL_STYLE,
                  "referenceScope": "literal old-order index inputs; native source/shader/readback verification remains required",
                  "inverseReference": {"input": "PF110IA literal 255-remap[n] indices", "indexed": True,
                      "translation": 0, "styleAsDWORD": NORMAL_STYLE, "sampler": "discrete indexed nearest",
                      "ordinaryControls": "neutral, translation, boundary and RedIsAlpha controls retain the configured global sampler"},
                  "colorTagControl": {"tag": "DTA_Color", "value": "0xff80c0ff", "referenceIndexed": True,
                      "referenceTranslation": 0, "referenceInput": "PF110RA literal translated indices",
                      "sourcePolicy": "SetStyle vertex colour -> indexed AddTexture mLightLevel=luminance and white vertex colour -> Draw2D SetSoftLightLevel",
                      "claim": "same indexed tag/style route control; not a direct getTexel object-colour tint oracle"}},
              "scene": {"map": "PF110", "sectors": 1, "lines": 4, "playerStarts": 1, "monsters": 0,
                        "scriptedGameplay": False, "roomStrip": [0,404,640,76]},
              "preview": {"cvar": "pf110_overlay", "default": False, "firstUsePolicy": "run raw diagnostic before enabling preview",
                  "readyCounterCvar": "pf110_overlay_frames", "readyCounterDefault": 0, "readyCounterMaximum": 2,
                  "readyMarker": "PF110_OVERLAY_READY mode=%d filter=%d extent=640x480 frames=2",
                  "readyMarkerMeaning": "two enabled RenderOverlay callbacks after native extent and translation guards; not a GPU submission or screenshot parity claim",
                  "captureWaitTicksAfterEnabled": 35},
              "rois": roi_metadata(), "scenarios": scenarios,
              "requiredNativeProof": ["ZScript/TRNSLATE/map compilation and actual extent", "registered named translation identities",
                  "actual two-callback enabled RenderOverlay marker and decoded presentation/ROI acceptance",
                  "actual translated R8/palette/shader target byte readbacks", "PF descriptor identity/reset observations",
                  "actual nearest sampler and real palette/SWCanvas route state", "proved validation-layer activation and process exit"],
              "limitations": ["Preparation does not prove native grammar compilation, shader execution, image parity or Vulkan validation.",
                  "Presentation captures do not isolate the raw material shader and do not replace pf_indexedmaterial_validate.",
                  "Numeric translation-ID replacement and pending upload/reset require the separate production-linked native/CPU diagnostic.",
                  "DTA_Color is converted to indexed command light level and white vertex colour; no uObjectColor tint or visible tint-effect claim follows from this public tag control.",
                  "Ordinary STYLE_Shaded overlay is a public RedIsAlpha style control; PF013 palette-mode R8 interpretation must be attested separately.",
                  "No CFX or PF017 campaign, optimization, performance, quality/default or full-frame acceptance claim."]}
    (out/"manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    (out/"ACCEPTANCE.md").write_text("# Prepared #110 runtime inputs\n\nThese synthetic inputs have not been executed or accepted. The manifest records exact files, source identity, commands and ROIs.\n\nThe six commands start only the empty PF110 lab map, request a 640x480 client extent with `vid_setsize 640 480`, enable the preview and exit after a presentation screenshot. Windows `win_w`/`win_h` configure outer-window dimensions; the startup Resolution line can precede the client-size command. Verify actual client/render extent after the short wait before the raw diagnostic or preview. Preview starts disabled (`pf110_overlay false`) so the separately prepared raw diagnostic can control first-use order; run it before enabling preview. Run these commands only after the native production-linked CPU gate. Add `pf_indexedmaterial_validate` and process-scoped validation before claiming GPU correctness. Keep runtime/compiler/validation logs, raw image/state JSON and process exit evidence. The version header has no semicolon; preparation tests do not prove native ZScript compilation.\n\nPresentation controls: A/B/A and B/A/B repeats; inverse A versus inverse-reference (rejected-row-order-model must differ); indexed DTA_Color versus a literal pretranslated source through the same indexed route/style/tag. Indexed AddTexture converts the tag-derived vertex colour to command light level and white vertex colour; this control does not prove getTexel uObjectColor/additive ordering or a visible tint effect. Those shader operations have a separate source-extracted CPU ordering oracle. Ordinary and boundary references may follow the configured global filter while actual indexed lookups remain discrete; do not demand boundary parity under linear filtering. The bottom room strip accompanies real hardware palette or software SWCanvas routing, but state evidence must prove the actual route.\n\nThe original IWAD is referenced and hashed; no original game content is included in the generated mod. Use an isolated IWAD copy and retain the full actually loaded archive list: `-noautoload` does not prove that a sibling `extras.wad` was absent.\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iwad", type=Path, required=True)
    parser.add_argument("--exe", type=Path, help="verified native executable identity; never executed here")
    args = parser.parse_args()
    try:
        result = prepare(args.out, args.iwad, args.exe)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"status": result["status"], "manifest": str(args.out.resolve()/"manifest.json"),
                      "mod": result["mod"]["path"], "modSha256": result["mod"]["sha256"], "gpuExecuted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
