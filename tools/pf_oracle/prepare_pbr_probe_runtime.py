#!/usr/bin/env python3
"""Prepare deterministic, unexecuted #113 PBR/probe inputs; never launch an engine.

The mod contains authored geometry and channel images only. It contains no
prebaked lightmap/probe data and no copied IWAD asset. Native observation must
prove the initial missing-probe draw and later publication; geometry is not
substitute evidence for either event.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "pf113-pbr-probe-runtime-inputs/v1"
IWAD_SHA256 = "31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab"
EXTENT = [640, 480]
SETTINGS = {"rendererMode": 4, "globalFilter": 0, "lightProbes": True,
            "levelMesh": False, "uberShaders": False, "lightShadows": 0}
PROBES = [[-112, -112, 64], [64, 0, 64]]
SOURCE_FILES = (
    "AGENTS.md", "docs/shadedoomvk/PF-113-MISSING-IBL-DECISION.md",
    "tools/pf_oracle/prepare_pbr_probe_runtime.py", "tools/pf_oracle/run_pbr_probe_runtime.py",
    "tools/pf_oracle/run_indexed_material_runtime.py", "tools/cfx_capture.py",
    "src/common/rendering/vulkan/textures/vk_pbrprobediagnostics.cpp",
    "src/common/rendering/vulkan/textures/vk_pbrprobediagnostics.h",
    "src/common/rendering/vulkan/vk_renderstate.h",
    "src/common/rendering/hwrenderer/data/hw_surfaceuniforms.h", "src/common/textures/textures.h",
    "src/common/rendering/vulkan/vk_renderstate.cpp", "src/common/rendering/vulkan/vk_lightprober.cpp",
    "src/common/rendering/vulkan/vk_renderdevice.cpp", "src/common/rendering/vulkan/vk_capabilities.h",
    "src/common/rendering/vulkan/textures/vk_texture.cpp",
    "src/common/rendering/vulkan/textures/vk_imagetransition.cpp",
    "src/common/rendering/vulkan/textures/vk_imagetransition.h",
    "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp",
    "src/common/rendering/vulkan/samplers/vk_samplers.cpp",
    "src/common/rendering/vulkan/pipelines/vk_renderpass.cpp",
    "src/common/rendering/vulkan/shaders/vk_shader.cpp",
    "src/common/textures/hw_material.cpp", "src/r_data/gldefs.cpp",
    "src/maploader/udmf.cpp", "src/g_levellocals.h",
    "src/rendering/hwrenderer/hw_entrypoint.cpp", "src/common/rendering/hwrenderer/data/hw_lightprobe.cpp",
    "src/rendering/hwrenderer/scene/hw_drawinfo.cpp", "src/rendering/hwrenderer/scene/hw_bsp.cpp",
    "src/common/rendering/hwrenderer/data/hw_cvars.cpp",
    "src/common/console/c_dispatch.cpp", "src/common/engine/i_net.h", "src/d_net.cpp",
    "src/m_misc.cpp", "src/g_game.cpp", "src/common/utility/vectors.h",
    "src/d_main.cpp", "src/common/rendering/v_video.cpp", "src/common/platform/win32/base_sysfb.cpp",
    "wadsrc/static/shaders/scene/lightmodel_pbr.glsl", "wadsrc/static/shaders/scene/material_default.glsl",
    "wadsrc/static/shaders/scene/material_normalmap.glsl", "wadsrc/static/shaders/scene/material.glsl",
    "wadsrc/static/shaders/scene/frag_main.glsl", "wadsrc/static/shaders/scene/lightmodel_shared.glsl",
    "wadsrc/static/shaders/scene/layout_shared.glsl",
    "libraries/ZVulkan/src/vulkanbuilders.cpp", "libraries/ZVulkan/src/vulkandevice.cpp",
    "libraries/ZVulkan/include/zvulkan/vulkanbuilders.h",
    "libraries/ZVulkan/include/zvulkan/vulkanobjects.h",
)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Required file missing: {path}")
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def safe_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if any(c in value for c in '\r\n"\0;'):
        raise ValueError("Console path contains a quote/control/semicolon")
    return value


def png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    if not (1 <= width <= 256 and 1 <= height <= 256) or len(pixels) != width * height * 4:
        raise ValueError("Synthetic RGBA extent/payload invalid")
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    rows = b"".join(b"\0" + pixels[y*width*4:(y+1)*width*4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def wad(lumps: list[tuple[str, bytes]]) -> bytes:
    result = bytearray(b"PWAD" + struct.pack("<II", len(lumps), 0))
    entries = []
    for name, payload in lumps:
        if not name or len(name.encode("ascii")) > 8:
            raise ValueError("Invalid synthetic WAD lump name")
        entries.append((len(result), len(payload), name.encode("ascii").ljust(8, b"\0")))
        result.extend(payload)
    struct.pack_into("<I", result, 8, len(result))
    for entry in entries:
        result.extend(struct.pack("<II8s", *entry))
    return bytes(result)


def textmap() -> str:
    # Clockwise linedefs keep this room on each front/right side. Actual target
    # selection is independently observed from the engine's recalculation.
    lines = ['namespace = "ZDoom";']
    for x, y in ((-128, -128), (-128, 128), (128, 128), (128, -128)):
        lines.append(f"vertex {{ x = {x}; y = {y}; }}")
    lines.append('sector { heightfloor = 0; heightceiling = 128; texturefloor = "PF113FL"; '
                 'textureceiling = "PF113FL"; lightlevel = 160; }')
    for i in range(4):
        lines.append('sidedef { sector = 0; texturemiddle = "PF113W"; }')
        lines.append(f"linedef {{ v1 = {i}; v2 = {(i+1)%4}; sidefront = {i}; blocking = true; }}")
    lines.append("thing { x = -64; y = 0; height = 0; angle = 0; type = 1; skill1 = true; "
                 "skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }")
    for x, y, z in PROBES:
        lines.append(f"thing {{ x = {x}; y = {y}; height = {z}; type = 9892; }}")
    return "\n".join(lines) + "\n"


def gldefs() -> str:
    # ParseMaterial's ordinary channel keywords use FindGameTexture(TryAny).
    # Full channel names refer to our own generated PNGs, never IWAD material.
    return "".join(f'''material {kind} {name}
{{
    normal "PF113N"
    metallic "PF113M"
    roughness "PF113R"
    ao "PF113A"
}}
''' for kind, name in (("texture", "PF113W"), ("flat", "PF113FL")))


def members() -> dict[str, bytes]:
    colours = ((196, 52, 30, 255), (28, 168, 214, 255), (214, 184, 48, 255), (48, 54, 172, 255))
    albedo = bytes(channel for y in range(64) for x in range(64)
                   for channel in colours[(x//8 + 2*(y//8)) % 4])
    def constant(rgba):
        return png_rgba(64, 64, bytes(rgba) * (64*64))
    return {
        "MAPINFO": b'map PF113 "Missing IBL laboratory" { nointermission }\n',
        "GLDEFS": gldefs().encode(),
        "textures/PF113W.png": png_rgba(64, 64, albedo),
        "flats/PF113FL.png": png_rgba(64, 64, albedo),
        "textures/PF113N.png": constant((128, 128, 255, 255)),
        "textures/PF113M.png": constant((64, 64, 64, 255)),
        "textures/PF113R.png": constant((128, 128, 128, 255)),
        "textures/PF113A.png": constant((192, 192, 192, 255)),
        "maps/PF113.wad": wad([("PF113", b""), ("TEXTMAP", textmap().encode()), ("ENDMAP", b"")]),
    }


def archive_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 0, 0
            archive.writestr(info, files[name])
    return output.getvalue()


def configuration() -> str:
    return """[GlobalSettings]
vid_preferbackend=1
vid_rendermode=4
vid_fullscreen=false
win_w=640
win_h=480
win_maximized=false
vid_vsync=false
vid_maxfps=60
gl_texture_filter=0
gl_texture_filter_anisotropic=1
gl_multisample=0
gl_tonemap=0
gl_light_shadows=0
vid_brightness=0
vid_contrast=1
vid_gamma=1

[Doom.ConsoleVariables]
screenblocks=12
crosshair=0
"""


def capture_script(prefix: Path, shot: Path) -> str:
    # FExecList gives each physical line a separate AddCommandString call;
    # only a semicolon remainder waits.35 ticks exceeds selected backlog17.
    commands = ["wait 105", "vid_setsize 640 480", "wait 35",
                f'pf113_probe_diag "{safe_path(prefix)}"', "wait 35",
                f'screenshot "{safe_path(shot)}"', "wait 5", "quit"]
    line = "; ".join(commands)
    if len(line.encode()) + 1 > 4094:
        raise ValueError("Exec line exceeds actual parser bound")
    return line + "\n"


def command(exe: Path | None, iwad: Path, mod: Path, config: Path, script: Path, early: Path) -> list[str]:
    for path in (iwad, mod, config, script, early):
        safe_path(path)
    return [str(exe.resolve()) if exe else "<verified-native-executable>", "-stdout", "-noautoload", "-noautoexec",
            "-nosound", "-nojoy", "-iwad", str(iwad.resolve()), "-file", str(mod.resolve()),
            "-config", str(config.resolve()), "-width", "640", "-height", "480",
            "-pf113observe", str(early.resolve()), "+gl_lightprobe", "true", "+gl_levelmesh", "false",
            "+gl_ubershaders", "false", "+gl_light_shadows", "0", "+map", "PF113", "+exec", str(script.resolve())]


def source_identity(root: Path = ROOT) -> dict:
    return {name: sha((root/name).read_bytes()) for name in SOURCE_FILES}


def prepare(out: Path, iwad: Path, exe: Path | None = None) -> dict:
    iwad = iwad.resolve(strict=True)
    iwad_pin = identity(iwad)
    if iwad_pin["sha256"] != IWAD_SHA256:
        raise ValueError("IWAD differs from the accepted isolated material-test input")
    # No sibling WAD is allowed; actual loaded-package evidence remains required.
    if any(p != iwad for p in iwad.parent.iterdir() if p.suffix.lower() == ".wad"):
        raise ValueError("IWAD directory contains an adjacent WAD")
    before = source_identity()
    executable = identity(exe) if exe else None
    out = out.resolve()
    if out.exists():
        raise ValueError("Preparation directory must be fresh; evidence is immutable")
    safe_path(out)
    out.mkdir(parents=True)
    files = members()
    mod = out / "pf113-pbr-probes.pk3"
    mod.write_bytes(archive_bytes(files))
    cfg, script, early, native, shot = [out/name for name in ("fixture.ini", "capture.cfg", "early", "native", "presentation.png")]
    cfg.write_text(configuration(), encoding="utf-8", newline="\n")
    script.write_text(capture_script(native, shot), encoding="utf-8", newline="\n")
    case = {"id": "hardware-truecolour-nearest", **SETTINGS, "extent": EXTENT,
            "config": str(cfg), "configSha256": sha(cfg.read_bytes()),
            "captureScript": str(script), "captureScriptSha256": sha(script.read_bytes()),
            "earlyPrefix": str(early), "nativePrefix": str(native), "presentationCapture": str(shot),
            "command": command(exe, iwad, mod, cfg, script, early), "executed": False}
    if before != source_identity():
        raise ValueError("Fixture/source identity changed during preparation")
    manifest = {"schema": SCHEMA, "status": "prepared-unaccepted", "gpuExecuted": False,
                "iwad": {**iwad_pin, "copiedIntoMod": False}, "executable": executable,
                "mod": {**identity(mod), "members": {name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in files.items()}},
                "fixtureInterfaceSources": before, "scenarios": [case],
                "scene": {"map": "PF113", "probes": PROBES, "probeThingType": 9892,
                          "sectorTarget": {"sector": 0, "origin": [0, 0, 64], "expectedOrdinal": 1},
                          "sideTarget": {"side": 2, "origin": [128, 0, 64], "expectedOrdinal": 1},
                          "player": [-64, 0, 0, 0], "extent": EXTENT,
                          "materialNames": ["PF113W", "PF113FL"], "channelNames": ["PF113N", "PF113M", "PF113R", "PF113A"],
                          "prebakedProbeOrLightmapLumps": False, "generatedAssets": True},
                "preparationNotes": [
                    "Synthetic geometry/channel PNGs are authored inputs, not native PBR or probe execution evidence.",
                    "Actual first missing probe1 PBR draw, real publication and later live probe1 draw must be observed.",
                    "gl_levelmesh=false and gl_ubershaders=false select observable immediate specialized rendering; no LevelMesh parity claim.",
                    "Zero IBL/readback controls do not alter ambient/direct light or renormalize remaining gather coefficients.",
                    "One physical semicolon exec chain preserves wait continuations; startup extent alone is insufficient.",
                    "Native shader compilation, actual CURRENT core/sync mode and loaded seven-package closure remain pending.",
                    "PNG is fixed-scene presentation context, not original/candidate parity, performance, or human judgement."]}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--iwad", required=True, type=Path)
    parser.add_argument("--exe", type=Path, help="Exact staged native executable; never executed by this tool")
    args = parser.parse_args()
    try:
        result = prepare(args.out, args.iwad, args.exe)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"status": result["status"], "manifest": str(args.out.resolve()/"manifest.json"), "gpuExecuted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
