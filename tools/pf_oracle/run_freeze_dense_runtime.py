#!/usr/bin/env python3
"""One fresh, bounded PF020 ordinary Dense CPU benchmark run.

Preparation performs only filesystem and read-only Git attestation. Launch is
explicit, single-use and starts one renderer child. Historical stopped campaigns
are never dispatched. The four retained bench values are CPU snapshots (the
inherited All timer includes Finish/wait); they are not GPU timestamps, a frame
distribution, a speedup decision or permission to reopen PF017/CFX.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "pf020-ordinary-dense-run/v1"
EXTENT = (1904, 1001)
WATCHDOG_SECONDS = 90
PACKAGES = {"vkdoom.pk3", "game_support.pk3", "lights.pk3", "brightmaps.pk3", "game_widescreen_gfx.pk3"}
QUALIFIED = {
    "baseline": ("build/pf020-acceptance/indexed-candidate-5/candidate.json",
                 "097c5457367ad1624f4be6fc205ce8be8e2252c85a4060aa8dfc416c90de268c",
                 "pf110-native-candidate/v1"),
    "candidate": ("build/pf020-acceptance/pbr-probe-candidate-2/candidate.json",
                  "7870042972d4a612fc6b1ecfeead3c655f4a40b834142bc6787ce1c66d30d352",
                  "pf113-native-candidate/v1"),
}
FIXTURE = Path("C:/ShadeDoomVK/pf-local-evidence/pf016/PF016_DenseLights_Interior.wad")
FIXTURE_SHA = "21da7231bc1f81c32d15cda2150c840c6b670299a038a994f498fe680fd1d85e"
IWAD = ROOT / "build/pf020-acceptance/pf110-inputs/doom2.wad"
IWAD_SHA = "31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab"
SEED = Path("C:/ShadeDoomVK/pf-local-evidence/pf016/configs/pf016-01.ini")
SEED_SHA = "b4e4f84eff7f212bf4584e7c417d4e749a628499add91e63ade2c817d0fdbaeb"
STOP_FILE = ROOT / "docs/shadedoomvk/evidence/pf017-final-acceptance/stop-guards.json"
STOP_SHA = "379e529d1a76e5a313ee71f36a88833cd603c8a3a7cbecbdd32717266da6c16a"
GLOBAL = {"vid_rendermode": "4", "gl_multithread": "true", "gl_spritelight": "2", "gl_lights": "true",
          "gl_texture_filter": "6", "gl_texture_filter_anisotropic": "0", "gl_texture_hqresizemode": "0",
          "vid_scalefactor": "1", "vid_scalemode": "0", "cl_capfps": "false", "vid_maxfps": "0",
          "vid_vsync": "false", "vid_fullscreen": "false", "vk_debug": "false", "vk_device": "0",
          "use_mouse": "false", "m_use_mouse": "0", "vid_activeinbackground": "true",
          "vid_lowerinbackground": "false"}
GAME = {"lm_dynlights": "false", "gl_lightmode": "1"}
QUERIES = {**GLOBAL, **GAME, "gl_levelmesh": "false"}
COUNTS = {"walls": 5, "splits": 0, "tSplits": 0, "wallVertices": 20, "flats": 2,
          "flatPrimitives": 2, "flatVertices": 24, "sprites": 832, "decals": 0, "portals": 0,
          "commandBuffers": 5, "wallLightsProcessed": 257, "wallLightsRendered": 253,
          "flatLightsProcessed": 432, "flatLightsRendered": 432}
LIMITS = ["Ordinary BSP/levelmesh-off static Dense scene only; no PBR/indexed diagnostic draw.",
          "CPU snapshots, not GPU timestamps or whole-renderer budget; All includes Finish/wait.",
          "No performance acceptance threshold, historical percentage, PF017 no-go reversal or CFX reopening.",
          "Camera/draw/light counts and decoded presented pixels; no ordered packed-light state oracle.",
          "Isolated stock IWAD differs from the historical augmented PWAD; compare these fresh matching runs only."]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def absolute(path):
    return Path(os.path.abspath(path))


def identity(path):
    # GetFinalPathNameByHandle (Path.resolve on Windows) can require access not
    # available for read-only sealed evidence. Hash the opened regular file;
    # use a normalized absolute name without requesting broader handle rights.
    path = absolute(path)
    require(path.is_file() and not path.is_symlink(), "Expected regular file: " + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": stat.st_size}


def checked(path, digest, size=None):
    result = identity(path)
    require(result["sha256"] == digest and (size is None or result["bytes"] == size),
            "Immutable input differs: " + str(path))
    return result


def read_json(path, maximum=8 * 1024 * 1024):
    require(Path(path).stat().st_size <= maximum, "JSON exceeds bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def save(path, data):
    temporary = Path(str(path) + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def source_name(name):
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_./+@ -]+", name)
            and not name.startswith("/") and ".." not in name.split("/"), "Unsafe source name")
    return name


def attest_sources(closure, commit, runner=subprocess.run):
    """Compare each compile-time raw/LF pin with the recorded commit's blob.

    Git's blob is LF on this checkout. Both pins must agree with the blob or its
    CRLF checkout projection; no current-file substitution for the old baseline.
    """
    require(re.fullmatch(r"[0-9a-f]{40}", commit or "") and 100 <= len(closure) <= 10000,
            "Candidate source commit/closure invalid")
    names = sorted(source_name(name) for name in closure)
    query = "".join(commit + ":" + name + "\n" for name in names).encode("ascii")
    result = runner(["git", "--no-optional-locks", "cat-file", "--batch"], input=query,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=60, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 512 * 1024 * 1024,
            "Read-only committed-source attestation failed")
    data, offset, crlf = result.stdout, 0, 0
    for name in names:
        end = data.find(b"\n", offset)
        require(end >= offset, "Truncated Git blob header")
        header = data[offset:end].split()
        require(len(header) == 3 and header[1] == b"blob" and header[2].isdigit(), "Missing/non-blob source: " + name)
        size = int(header[2]); start = end + 1; offset = start + size + 1
        require(size <= 32 * 1024 * 1024 and offset <= len(data) and data[offset - 1] == 10,
                "Truncated/oversized source blob")
        blob = data[start:start + size]; lf = blob.replace(b"\r\n", b"\n")
        pin = closure[name]
        require(sha(lf) == pin.get("normalized_lf_sha256"), "Committed LF differs: " + name)
        raw = pin.get("raw_sha256")
        require(raw in (sha(blob), sha(lf.replace(b"\n", b"\r\n"))), "Committed raw projection differs: " + name)
        crlf += raw != sha(blob)
    require(offset == len(data), "Unconsumed Git attestation bytes")
    return {"method": "read-only git cat-file --batch", "commit": commit, "files": len(names),
            "crlfProjections": crlf, "status": "PASS"}


def build_identity(variant, receipt_path, executable):
    fixed, digest, schema = QUALIFIED[variant]
    require(absolute(receipt_path) == absolute(ROOT / fixed), "Wrong qualified build receipt path")
    receipt = checked(receipt_path, digest)
    data = read_json(receipt_path)
    require(data.get("schema") == schema and data.get("source_closure_unchanged_during_engine_compile") is True
            and data.get("native_build", {}).get("exit") == 0, "No unchanged-source successful native build")
    require(data["native_build"]["command"][-4:] == ["--config", "RelWithDebInfo", "--parallel", "3"],
            "Unexpected native build configuration")
    artifacts = data.get("artifacts", [])
    require(len(artifacts) == 8, "Expected exact eight staged native artifacts")
    stage = absolute(executable).parent
    found = {}
    for row in artifacts:
        path = absolute(row["path"])
        require(path.parent == stage and path.suffix.lower() in (".exe", ".dll", ".pk3", ".pdb")
                and path.name not in found, "Staged artifact outside exact inventory")
        found[path.name] = {**checked(path, row["sha256"], row["bytes"]),
                            "buildCounterpart": checked(row["source"], row["sha256"], row["bytes"])}
    require({p.name for p in stage.iterdir() if p.suffix.lower() in (".exe", ".dll", ".pk3", ".pdb")} == set(found)
            and {name for name in found if name.endswith(".pk3")} == PACKAGES
            and str(absolute(executable)) == found["vkdoom.exe"]["path"],
            "Actual staged inventory/executable differs")
    build_logs = {}
    for name in ("log", "configure_log"):
        build_logs[name] = checked(ROOT / data["native_build"][name], data["native_build"][name + "_sha256"])
    attestation = attest_sources(data["source_files"], data["source_head"])
    return {"receipt": receipt, "artifacts": found, "logs": build_logs, "sourceAttestation": attestation,
            "nativeBuild": data["native_build"]}, data["source_files"]


def wad_members(path, expected_magic=None):
    data = Path(path).read_bytes()
    require(12 <= len(data) <= 32 * 1024 * 1024, "WAD size invalid")
    magic, count, directory = struct.unpack_from("<4sii", data)
    require(magic in (b"IWAD", b"PWAD") and (expected_magic is None or magic == expected_magic)
            and 0 < count <= 10000 and 12 <= directory <= len(data)
            and directory + count * 16 == len(data), "WAD directory invalid")
    result = []
    for i in range(count):
        start, size, raw = struct.unpack_from("<ii8s", data, directory + i * 16)
        require(0 <= size and 12 <= start <= directory and start + size <= directory, "WAD lump exceeds payload")
        name = raw.rstrip(b"\0").decode("ascii")
        # Stock Doom sprite rotation names legitimately contain '[' and '\\'.
        require(1 <= len(name) <= 8 and all(32 <= ord(c) <= 126 for c in name), "Invalid WAD lump name")
        result.append((name, data[start:start + size]))
    return result


def fixture_evidence(path):
    checked(path, FIXTURE_SHA)
    members = wad_members(path, b"PWAD")
    require([n for n, _ in members] == ["ZSCRIPT", "MAPINFO", "GLDEFS", "PF16TST", "TEXTMAP", "ENDMAP"],
            "Dense fixture includes additional material/shader/probe authoring")
    text = dict(members)["TEXTMAP"].decode("utf-8")
    things = re.findall(r"(?ms)^thing\n\{.*?^\}", text)
    types = [int(re.search(r"\btype\s*=\s*(\d+)\s*;", item)[1]) for item in things]
    require(len(types) == 1049 and types.count(15010) == 832 and types.count(1) == 1
            and sum(types.count(i) for i in range(15000, 15005)) == 216,
            "Dense population differs")
    scripts = dict(members)["ZSCRIPT"].decode("utf-8")
    require("POSS A -1" in scripts and "TNT1 A -1" in scripts and not re.search(
        r"(?i)probe|roughness|metallic|pbr|translation|indexed|shader|material", scripts + text
        + dict(members)["GLDEFS"].decode("utf-8")), "Dense fixture is not the pinned ordinary static route")
    return {"map": "PF16TST", "stationaryTargets": 832, "lights": 216, "playerStarts": 1,
            "memberNames": [n for n, _ in members], "memberHashes": {n: sha(v) for n, v in members},
            "authoredPbrIndexedProbeShaderOverrides": False,
            "route": "Stock textures/static POSS sprites, ordinary BSP with gl_levelmesh=false and lm_dynlights=false"}


def ini_sections(text):
    """Preserve legal repeated Path keys; critical values are checked separately."""
    sections, current = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((";", "#")):
            continue
        match = re.fullmatch(r"\[([^\]\r\n]+)\]", line)
        if match:
            current = match[1]
            require(current not in sections, "Duplicate INI section: " + current)
            sections[current] = []
        else:
            require(current is not None and "=" in line, "Invalid INI entry")
            key, value = line.split("=", 1)
            sections[current].append((key.strip(), value.strip()))
    return sections


def section_values(sections, section, wanted):
    rows = sections.get(section, [])
    result = {}
    for key in wanted:
        values = [v for k, v in rows if k.lower() == key.lower()]
        require(len(values) == 1, "Missing/duplicate critical INI value: " + section + "/" + key)
        result[key] = values[0].lower()
    return result


def configuration(seed):
    sections = ini_sections(seed)
    seed_globals = {k: v for k, v in GLOBAL.items() if k not in (
        "use_mouse", "m_use_mouse", "vid_activeinbackground", "vid_lowerinbackground")}
    actual = section_values(sections, "GlobalSettings", seed_globals)
    require(actual == seed_globals and section_values(sections, "Doom.ConsoleVariables", GAME) == GAME,
            "Seed quality settings differ from preserved Dense controls")
    for section in sections:
        if section.endswith((".Bindings", ".DoubleBindings", ".AutomapBindings", ".ConsoleAliases", ".AutoExec", ".Autoload")):
            sections[section] = []
    for section, wanted in (("GlobalSettings", GLOBAL), ("Doom.ConsoleVariables", GAME)):
        sections[section] = [(k, v) for k, v in sections[section] if k.lower() not in wanted]
        sections[section].extend(wanted.items())
    # Clear remembered untrusted filesystem searches and unneeded previous run.
    for section in ("IWADSearch.Directories", "FileSearch.Directories", "LastRun"):
        if section in sections:
            sections[section] = []
    return "\n\n".join("[" + section + "]\n" + "\n".join(k + "=" + v for k, v in rows)
                         for section, rows in sections.items()) + "\n"


def console_path(path):
    value = str(path)
    require(not any(c in value for c in '\";\r\n\0'), "Unsafe native console path")
    value = str(Path(os.path.abspath(value))).replace("\\", "/")
    return '"' + value + '"'


def execution_script(out):
    commands = ["use_mouse false", "m_use_mouse 0", "unbindall", "vid_activeinbackground true",
                "vid_lowerinbackground false", "gl_levelmesh false", "lm_dynlights false",
                "vid_setsize 1904 1001", "wait 35", "vid_fps true", "stat rendertimes", "bench",
                "wait 350", "pause", "wait 60"]
    for _ in range(4):
        commands += ["bench", "wait 190"]
    commands += ["stat rendertimes", "vid_fps false", *QUERIES, "wait 35",
                 "screenshot " + console_path(Path(out) / "scene.png"), "wait 35",
                 "echo PF020_DENSE_COMPLETE", "quit"]
    return "; ".join(commands) + "\n"


def execution_command(executable, iwad, fixture, out):
    out = Path(out).resolve()
    return [str(absolute(executable)), "-stdout", "-noautoload", "-noautoexec", "-nosound", "-nojoy", "-rngseed", "12345",
            "-width", str(EXTENT[0]), "-height", str(EXTENT[1]), "-config", str(out / "fixture-live.ini"),
            "-savedir", str(out / "save"), "-iwad", str(absolute(iwad)), "-file", str(absolute(fixture)),
            "+map", "PF16TST", "+exec", str(out / "execute.cfg")]


def clean_environment(environment):
    removed = sorted(k for k in environment if re.match(r"(?i)^(PF\d+_|CFX_|VK_|VULKAN_|ZVK_)", k))
    env = {k: v for k, v in environment.items() if k not in removed}
    return env, removed


def package_evidence(text, expected):
    require(text.count("W_Init: Init WADfiles.") == 1, "Expected one startup W_Init block")
    rows = re.findall(r"(?m)^adding (.+), (\d+) lumps\s*$", text)
    require(len(rows) == 7 and len(expected) == 7, "Expected exactly seven loaded packages")
    result, seen = [], set()
    for name, count in rows:
        path = str(absolute(name))
        require(path in expected and path not in seen, "Unknown/duplicate loaded package: " + name)
        seen.add(path)
        pin = expected[path]
        actual = checked(path, pin["sha256"], pin["bytes"])
        require(int(count) == pin["lumps"], "Loaded package lump count differs: " + name)
        result.append({**actual, "lumps": int(count)})
    require(seen == set(expected), "Missing pinned loaded package")
    return result


def native_device(text):
    device = re.findall(r"(?m)^Vulkan device: (.+)$", text)
    types = re.findall(r"(?m)^Vulkan device type: (.+)$", text)
    versions = re.findall(r"(?m)^Vulkan version: (.+) \(api\) (.+) \(driver\)$", text)
    require(device == ["NVIDIA GeForce GTX 1650 SUPER"] and types == ["discrete gpu"] and len(versions) == 1,
            "Actual native NVIDIA device/one initialization missing")
    return {"name": device[0], "type": types[0], "apiVersion": versions[0][0], "encodedDriver": versions[0][1]}


def query_evidence(text):
    result = {}
    for key, expected in QUERIES.items():
        values = re.findall(r'(?m)^"' + re.escape(key) + r'" is "([^"]*)" \(default: "[^"]*"\)\s*$', text)
        require(len(values) == 1 and values[0].lower() == expected, "Actual runtime setting differs/missing: " + key)
        result[key] = values[0]
    return result


def parse_benchmarks(text):
    blocks = re.split(r'(?m)(?=^Map )', text)
    require(not blocks[0].strip(), "Unexpected benchmark preamble")
    blocks = blocks[1:]
    require(len(blocks) == 5, "Expected one excluded warm snapshot and four retained snapshots")
    result = []
    patterns = [
        (r"Walls: (\d+) \((\d+) splits, (\d+) t-splits, (\d+) vertices\)", ("walls", "splits", "tSplits", "wallVertices")),
        (r"Flats: (\d+) \((\d+) primitives, (\d+) vertices\)", ("flats", "flatPrimitives", "flatVertices")),
        (r"Sprites: (\d+), Decals=(\d+), Portals: (\d+), Command buffers: (\d+)", ("sprites", "decals", "portals", "commandBuffers")),
        (r"DLight - Walls: (\d+) processed, (\d+) rendered - Flats: (\d+) processed, (\d+) rendered", ("wallLightsProcessed", "wallLightsRendered", "flatLightsProcessed", "flatLightsRendered")),
    ]
    for index, block in enumerate(blocks):
        require(re.search(r'^Map PF16TST: "PF-016 Dense Dynamic-Light Stress",\s*$', block, re.M), "Benchmark map differs")
        camera = re.findall(r"x = ([^,]+), y = ([^,]+), z = ([^,]+), angle = ([^,]+), pitch = ([^\n]+)", block)
        require(len(camera) == 1 and [float(v) for v in camera[0]] == [-1850., 0., 41., 0., 0.],
                "Actual benchmark camera differs or moved")
        counts = {}
        for pattern, keys in patterns:
            rows = re.findall(pattern, block)
            require(len(rows) == 1, "Benchmark counts missing/duplicated")
            counts.update(zip(keys, map(int, rows[0])))
        require(counts == COUNTS, "Actual sprite/draw/light counters differ")
        timings = re.findall(r"(?m)^All=([^,]+), Render=([^,]+), Setup=([^,]+), Portal=([^,]+), Drawcalls=([^,]+), Postprocess=([^,]+), Finish=([^\n]+)$", block)
        sprite = re.findall(r"(?m)^S: Render=([^,]+), Setup=([^\n]+)$", block)
        fps = re.findall(r"(?m)^(\d+) fps$", block)
        require(len(timings) == len(sprite) == len(fps) == 1, "CPU timing snapshot incomplete/duplicated")
        values = list(map(float, timings[0] + sprite[0]))
        require(all(math.isfinite(v) and v >= 0 for v in values) and int(fps[0]) > 0, "Nonfinite/negative CPU timing")
        result.append({"index": index, "excludedWarmSnapshot": index == 0,
                       "camera": [-1850, 0, 41, 0, 0], "counts": counts, "fpsContext": int(fps[0]),
                       "cpuMilliseconds": dict(zip(("allIncludingFinish", "render", "setup", "portal", "drawcalls", "postprocess", "finish", "spriteRender", "spriteSetup"), values))})
    return {"snapshots": result, "retainedIndices": [1, 2, 3, 4], "gpuTimestampClaimed": False,
            "units": "Inherited CPU glcycle_t TimeMS snapshots; All includes Finish/wait, not per-frame GPU duration"}


def decode_png(path, extent=EXTENT):
    """Bounded actual engine RGB8 PNG decoding, including CRC and all filters."""
    require(0 < extent[0] <= 1920 and 0 < extent[1] <= 1080, "PNG extent bound invalid")
    path = Path(path)
    require(33 <= path.stat().st_size <= 16 * 1024 * 1024, "PNG file size invalid")
    data = path.read_bytes(); require(data[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature invalid")
    pos, payload, chunks, ended_idat, finished = 8, bytearray(), [], False, False
    for _ in range(2048):
        require(pos + 12 <= len(data), "PNG chunk truncated")
        size, kind = struct.unpack_from(">I4s", data, pos); end = pos + size + 12
        require(re.fullmatch(b"[A-Za-z]{4}", kind) and not kind[2] & 32 and end <= len(data), "PNG chunk invalid")
        body = data[pos + 8:pos + 8 + size]
        require(zlib.crc32(kind + body) & 0xffffffff == struct.unpack_from(">I", data, pos + 8 + size)[0], "PNG CRC mismatch")
        require(chunks or kind == b"IHDR", "PNG IHDR must be first")
        if kind == b"IHDR":
            require(not chunks and size == 13, "PNG duplicated/invalid IHDR")
            width, height, depth, colour, compress, filtering, interlace = struct.unpack(">IIBBBBB", body)
            require((width, height) == extent and (depth, colour, compress, filtering, interlace) == (8, 2, 0, 0, 0),
                    "PNG actual extent/RGB8 format differs")
        elif kind == b"IDAT":
            require(not ended_idat, "PNG noncontiguous IDAT")
            payload.extend(body)
        elif kind == b"IEND":
            require(size == 0 and b"IDAT" in chunks and end == len(data), "PNG IEND/trailing bytes invalid")
            finished = True
        else:
            require(kind[0] & 32 or kind == b"PLTE", "Unsupported PNG critical chunk")
            if kind == b"PLTE":
                require(b"IDAT" not in chunks and 0 < size <= 768 and size % 3 == 0 and kind not in chunks, "PNG palette invalid")
            if b"IDAT" in chunks:
                ended_idat = True
        chunks.append(kind); pos = end
        if finished:
            break
    require(finished and payload, "PNG image/IEND missing")
    stride = extent[0] * 3; expected = extent[1] * (stride + 1)
    inflater = zlib.decompressobj()
    try:
        filtered = inflater.decompress(bytes(payload), expected + 1)
    except zlib.error as error:
        raise ValueError("PNG compression invalid") from error
    require(len(filtered) == expected and inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail,
            "PNG decompression boundary/count invalid")
    pixels, previous, modes = bytearray(), bytearray(stride), set()
    for y in range(extent[1]):
        start = y * (stride + 1); mode = filtered[start]; require(mode <= 4, "PNG filter invalid")
        row = bytearray(filtered[start + 1:start + 1 + stride]); modes.add(mode)
        for x in range(stride):
            left, up, corner = (row[x - 3] if x >= 3 else 0), previous[x], (previous[x - 3] if x >= 3 else 0)
            predictors = (0, left, up, (left + up) // 2)
            if mode == 4:
                p = left + up - corner; distances = (abs(p - left), abs(p - up), abs(p - corner))
                prediction = (left, up, corner)[distances.index(min(distances))]
            else:
                prediction = predictors[mode]
            row[x] = (row[x] + prediction) & 255
        pixels.extend(row); previous = row
    return bytes(pixels), {"extent": list(extent), "format": "RGB8/noninterlaced", "decodedBytes": len(pixels),
                           "decodedRgbSha256": sha(pixels), "rowFiltersObserved": sorted(modes),
                           "chunks": [k.decode("ascii") for k in chunks]}


def image_evidence(path):
    pixels, result = decode_png(path, EXTENT)
    samples = {pixels[(y * EXTENT[0] + x) * 3:(y * EXTENT[0] + x) * 3 + 3]
               for y in range(0, EXTENT[1], 16) for x in range(0, EXTENT[0], 16)}
    require(len(samples) >= 8 and max(pixels) - min(pixels) >= 32, "Screenshot blank/insufficient scene diversity")
    return {**identity(path), **result, "gridDistinctRgbCount": len(samples), "status": "PASS",
            "scope": "Actual extent, valid decoded nonblank image and pixel hash; pair parity adjudicated separately"}


def strip_colours(text):
    return re.sub(r"\x1c(?:\[[^\]]*\]|.)", "", text)


def health(since):
    """Read-only host metadata outside timing; no Vulkaninfo/second renderer."""
    require(os.name == "nt", "Native Dense launch requires the approved Windows host")
    fields = "name,pci.device_id,driver_version,temperature.gpu,pstate,memory.total"
    gpu_args = ["nvidia-smi", "--query-gpu=" + fields, "--format=csv,noheader,nounits"]
    gpu = subprocess.run(gpu_args, capture_output=True, text=True, timeout=15, check=False)
    require(gpu.returncode == 0, "NVIDIA metadata query failed")
    rows = list(csv.reader(gpu.stdout.splitlines()))
    require(len(rows) == 1 and len(rows[0]) == 6, "NVIDIA metadata row invalid")
    row = [v.strip() for v in rows[0]]
    require(row[:3] == ["NVIDIA GeForce GTX 1650 SUPER", "0x218710DE", "616.92"]
            and 0 <= float(row[3]) < 80 and row[4] in {"P" + str(i) for i in range(16)}
            and float(row[5]) == 4096, "NVIDIA identity/driver/health differs")
    script = """$ErrorActionPreference='Stop'
$since=[DateTime]::Parse('__SINCE__').ToUniversalTime()
$adapters=@(Get-CimInstance Win32_VideoController | Select-Object Name,ConfigManagerErrorCode,DriverVersion)
$games=@(Get-Process vkdoom,zdoom -ErrorAction SilentlyContinue | Select-Object Id,Name)
$events=@(Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$since.ToLocalTime()} -ErrorAction SilentlyContinue | Where-Object {$_.ProviderName -match 'WHEA|BugCheck|Display|nvlddmkm' -or $_.Id -eq 6008 -or ($_.ProviderName -match 'Kernel-Power' -and $_.Id -eq 41)} | Select-Object Id,RecordId,ProviderName)
[PSCustomObject]@{adapters=$adapters;games=$games;events=$events} | ConvertTo-Json -Depth 5
""".replace("__SINCE__", since)
    args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    env = {k: v for k, v in os.environ.items() if k.lower() != "psmodulepath"}
    query = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env, check=False)
    require(query.returncode == 0, "Windows host state query failed")
    state = json.loads(query.stdout.lstrip("\ufeff"))
    require(len(state["adapters"]) == 1 and state["adapters"][0] == {
        "Name": "NVIDIA GeForce GTX 1650 SUPER", "ConfigManagerErrorCode": 0, "DriverVersion": "32.0.16.1692"}
        and not state["games"] and not state["events"], "Concurrent renderer or host/device failure event")
    return {"atUtc": utc(), "nvidiaQuery": {"argv": gpu_args, "stdout": gpu.stdout, "stderr": gpu.stderr},
            "windows": state, "scope": "Pre/post-run metadata outside the CPU snapshot intervals"}


def stop_identity():
    checked(STOP_FILE, STOP_SHA)
    guards = read_json(STOP_FILE)
    require(len(guards) == 22, "Historical STOP inventory differs")
    return {name: checked(name, digest) for name, digest in guards.items()}


def snapshot(args, out, initial=False):
    build, closure = build_identity(args.variant, args.candidate_receipt, args.executable)
    # Union with final candidate closure pins current renderer files, independent
    # of historical build's checkout projections. Docs may be reconciled elsewhere.
    final = read_json(ROOT / QUALIFIED["candidate"][0])
    require(identity(ROOT / QUALIFIED["candidate"][0])["sha256"] == QUALIFIED["candidate"][1],
            "Final source closure receipt changed")
    for name, pin in final["source_files"].items():
        require(sha((ROOT / source_name(name)).read_bytes().replace(b"\r\n", b"\n")) == pin["normalized_lf_sha256"],
                "Current engine source differs from qualified final binary: " + name)
    names = set(closure) | set(final["source_files"])
    names.update(("tools/pf_oracle/run_freeze_dense_runtime.py", "tools/pf_oracle/tests/test_freeze_dense_runtime.py"))
    sources = {name: identity(ROOT / source_name(name)) for name in sorted(names)}
    inputs = {"iwad": checked(args.iwad, IWAD_SHA), "fixture": checked(args.fixture, FIXTURE_SHA),
              "seed": checked(args.config_seed, SEED_SHA), "execute": identity(out / "execute.cfg"),
              "configurationInput": identity(out / "configuration-input.ini")}
    require((out / "execute.cfg").read_text() == execution_script(out)
            and (out / "configuration-input.ini").read_text() == configuration(Path(args.config_seed).read_text()),
            "Generated immutable config/physical execution chain changed")
    if initial:
        require((out / "fixture-live.ini").read_bytes() == (out / "configuration-input.ini").read_bytes(),
                "Prelaunch live config differs")
    return {"build": build, "currentSourceFiles": sources, "inputs": inputs, "stops": stop_identity()}


def expected_packages(snap):
    result = {}
    counts = {"vkdoom.pk3": 718, "game_support.pk3": 3308, "lights.pk3": 7,
              "brightmaps.pk3": 499, "game_widescreen_gfx.pk3": 214}
    for name in PACKAGES:
        row = snap["build"]["artifacts"][name]
        result[row["path"]] = {k: row[k] for k in ("sha256", "bytes")}
        result[row["path"]]["lumps"] = counts[name]
    for key, count in (("iwad", 2928), ("fixture", 6)):
        row = snap["inputs"][key]
        result[row["path"]] = {"sha256": row["sha256"], "bytes": row["bytes"], "lumps": count}
    return result


def run_child(argv, out, env, receipt, popen=subprocess.Popen, clock=time.monotonic):
    """Only this child's handle can be killed. No global taskkill, retry or shell."""
    with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
        child = popen(argv, cwd=out / "work", env=env, stdout=stdout, stderr=stderr, shell=False)
        try:
            receipt.update(status="RUNNING", pid=child.pid, childCount=1, rendererStarted=True, startedUtc=utc())
            save(out / "receipt.json", receipt)
            start = clock()
            while child.poll() is None:
                if clock() - start >= WATCHDOG_SECONDS:
                    receipt["watchdog"] = {"expired": True, "seconds": WATCHDOG_SECONDS, "killedOwnPid": child.pid}
                    child.kill(); child.wait(timeout=10)
                    raise ValueError("90-second owned renderer watchdog expired")
                if stdout.tell() + stderr.tell() > 16 * 1024 * 1024:
                    raise ValueError("Renderer log output exceeds bound")
                time.sleep(.10)
            receipt["exit"] = child.returncode
            receipt["durationSeconds"] = clock() - start
        finally:
            if child.poll() is None:
                child.kill(); child.wait(timeout=10)
                receipt["abortedOwnPid"] = child.pid


def output_inventory(out):
    found = {}
    for path in sorted(out.rglob("*")):
        require(not path.is_symlink(), "Output symlink forbidden")
        if path.is_file() and path.name not in ("receipt.json", "receipt.json.tmp"):
            require(len(found) < 128 and path.stat().st_size <= 32 * 1024 * 1024, "Output closure exceeds bound")
            found[str(path.relative_to(out))] = identity(path)
    return found


def adjudicate(out, receipt):
    text = strip_colours((out / "stdout.log").read_text(errors="replace"))
    errors = (out / "stderr.log").read_text(errors="replace")
    require(receipt.get("exit") == 0, "Renderer did not exit normally")
    require(text.count("Benchmark info saved") == 5 and len(re.findall(r"(?m)^PF020_DENSE_COMPLETE\s*$", text)) == 1,
            "Actual benchmark/terminal completion markers missing/duplicated")
    require(not re.search(r"(?i)VUID-|VK_LAYER_KHRONOS_validation|Validation Error|Validation Warning|Script error|compile failed|fatal error", text + errors),
            "Validation activation/error or startup/runtime error in timing process")
    receipt["nativeDevice"] = native_device(text)
    receipt["loadedPackages"] = package_evidence(text, expected_packages(receipt["before"]))
    receipt["actualRuntimeSettings"] = query_evidence(text)
    sections = ini_sections((out / "fixture-live.ini").read_text(errors="strict"))
    require(section_values(sections, "GlobalSettings", GLOBAL) == GLOBAL
            and section_values(sections, "Doom.ConsoleVariables", GAME) == GAME, "Saved settings differ at normal exit")
    receipt["savedSettingsScope"] = "Observed at normal exit, paired with actual pre-capture CVar queries"
    receipt["cpuBenchmarks"] = parse_benchmarks((out / "work/benchmarks.txt").read_text())
    receipt["presentation"] = image_evidence(out / "scene.png")


def prepare(args, out, receipt):
    require(out.is_relative_to((ROOT / "build").resolve()) and not out.exists(), "Output must be a fresh directory below this checkout's build")
    require(not out.is_relative_to(absolute(args.executable).parent)
            and not out.is_relative_to(absolute(args.iwad).parent), "Output collides with pinned stage/input directory")
    out.mkdir(parents=True); (out / "work").mkdir(); (out / "save").mkdir()
    receipt.update(status="PREPARING", createdUtc=utc()); save(out / "receipt.json", receipt)
    checked(args.config_seed, SEED_SHA); checked(args.iwad, IWAD_SHA)
    require(len(wad_members(args.iwad, b"IWAD")) == 2928, "Wrong isolated stock IWAD")
    receipt["fixtureContract"] = fixture_evidence(args.fixture)
    config = configuration(Path(args.config_seed).read_text())
    (out / "configuration-input.ini").write_text(config, encoding="utf-8", newline="\n")
    (out / "fixture-live.ini").write_text(config, encoding="utf-8", newline="\n")
    (out / "execute.cfg").write_text(execution_script(out), encoding="utf-8", newline="\n")
    receipt["argv"] = execution_command(args.executable, args.iwad, args.fixture, out)
    receipt["cwd"] = str(out / "work")
    receipt["before"] = snapshot(args, out, initial=True)
    receipt["status"] = "PREPARED"; save(out / "receipt.json", receipt)


def launch(args, out, receipt):
    require(receipt.get("schema") == SCHEMA and receipt.get("status") == "PREPARED"
            and receipt.get("rendererStarted") is False and receipt.get("variant") == args.variant,
            "Only unchanged, unused PREPARED receipt can launch; no retry")
    require(receipt["argv"] == execution_command(args.executable, args.iwad, args.fixture, out)
            and receipt["cwd"] == str(out / "work"), "Prepared exact command/cwd changed")
    require({str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} == {
        "receipt.json", "execute.cfg", "fixture-live.ini", "configuration-input.ini"}, "Prepared output contains unexpected files")
    require(snapshot(args, out, initial=True) == receipt["before"], "Source/build/input/STOP changed after preparation")
    env, removed = clean_environment(os.environ)
    receipt["removedEnvironmentKeys"] = removed
    receipt["diagnosticsAndValidation"] = "Off: sanitized PF/CFX/VK environment, vk_debug=false; no diagnostic commands"
    receipt["hostBefore"] = health(utc())
    run_child(receipt["argv"], out, env, receipt)
    receipt["hostAfter"] = health(receipt["startedUtc"])
    receipt["after"] = snapshot(args, out)
    receipt["immutableUnchanged"] = receipt["before"] == receipt["after"]
    require(receipt["immutableUnchanged"], "Source/build/input/STOP changed during renderer run")
    adjudicate(out, receipt)
    receipt["outputs"] = output_inventory(out)
    # This second inventory prevents validation-side mutation of already hashed
    # output artifacts from being silently accepted.
    require(receipt["outputs"] == output_inventory(out), "Output evidence changed during closure")
    receipt.update(status="PASS", completedUtc=utc(), performanceAccepted=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true"); mode.add_argument("--launch", action="store_true")
    parser.add_argument("--variant", choices=tuple(QUALIFIED), required=True)
    parser.add_argument("--candidate-receipt", type=Path)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--iwad", type=Path, default=IWAD)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--config-seed", type=Path, default=SEED)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.candidate_receipt = args.candidate_receipt or ROOT / QUALIFIED[args.variant][0]
    args.executable = args.executable or args.candidate_receipt.parent / "vkdoom.exe"
    out = args.out.resolve()
    receipt = {"schema": SCHEMA, "status": "FAIL", "variant": args.variant, "rendererStarted": False,
               "childCount": 0, "performanceAccepted": False, "gpuTimestampClaimed": False,
               "limits": LIMITS, "extent": list(EXTENT), "rngSeed": 12345}
    try:
        if args.prepare:
            prepare(args, out, receipt)
        else:
            receipt = read_json(out / "receipt.json", maximum=16 * 1024 * 1024)
            launch(args, out, receipt)
        save(out / "receipt.json", receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(out / "receipt.json"), "performanceAccepted": False}))
        return 0
    except Exception as error:
        # A rejected launch does not erase an earlier completed run's receipt.
        if receipt.get("status") not in ("PASS", "FAIL") or not (out / "receipt.json").exists():
            receipt.update(status="FAIL", error=type(error).__name__ + ": " + str(error), completedUtc=utc())
            if out.is_dir():
                try:
                    receipt["retainedOutputs"] = output_inventory(out)
                    save(out / "receipt.json", receipt)
                except Exception as closure_error:
                    receipt["closureError"] = str(closure_error)
                    save(out / "receipt.json", receipt)
        print(json.dumps({"status": "FAIL", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
