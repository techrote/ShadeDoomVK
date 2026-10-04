#!/usr/bin/env python3
"""Preregister and validate bounded PF020 VIEW evidence; execution is explicit.

Default preparation and --validate-state never launch an engine. A collected
state packet is not image acceptance or a passing freeze. Only --launch runs
the preregistered serial children; it must be invoked by the root operator.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import time
import zipfile


def repository():
    for path in Path(__file__).resolve().parents:
        if (path / "tools/pf_oracle/prepare_freeze_view_fixture.py").is_file() and (path / "AGENTS.md").is_file():
            return path
    raise ValueError("Cannot locate the sole source repository")


ROOT = repository()


def load(name):
    spec = importlib.util.spec_from_file_location("pf020_view_" + name, ROOT / "tools/pf_oracle" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load("run_indexed_material_runtime")
dense = load("run_freeze_dense_runtime")
fixture = load("prepare_freeze_view_fixture")
derive = load("derive_freeze_view_baseline")
require, identity, read_json, save = base.require, base.identity, base.read_json, base.save
SCHEMA = "pf020-bounded-view-acceptance/v1"
ORDER = (("current", "cold"), ("original-seams", "cold"), ("original-seams", "warm"), ("current", "warm"))
CACHE_FILES = ("shadercache.zdsc", "pipelinecache.zdpc")
ARTIFACT_NAMES = {"vkdoom.exe", "vkdoom.pdb", "ZMusic.dll", *dense.PACKAGES}
SHADER_FIELDS = set("Simple2D TextureMode ClampY Brightmap Detailmap Glowmap UseShadowmap UseRaytrace ShadowmapFilter FogBeforeLights FogAfterLights FogRadial SWLightRadial SWLightBanded LightMode LightBlendMode LightAttenuationMode PaletteMode FogBalls NoFragmentShader DepthFadeThreshold AlphaTestOnly LightNoNormals UseSpriteCenter SpecialEffect EffectState VertexFormat layout".split())
LAYOUT_FIELDS = set("AlphaTest Simple Simple3D GBufferPass UseLevelMesh ShadeVertex UseRaytracePrecise".split())
PIPELINE_FIELDS = set("DrawType CullMode ColorMask DepthWrite DepthTest DepthClamp DepthBias DepthFunc StencilTest StencilPassOp DrawLine IsGeneralized shader style".split())
PASS_FIELDS = {"DepthStencil", "Samples", "DrawBuffers", "DrawBufferFormat"}
WATCHDOG_SECONDS = 120
WARMUP_WAIT_UNITS, COLLECTION_WAIT_UNITS = 350, 140
UI_SETTINGS = {"show_messages": "false", "con_notifytime": "0", "use_mouse": "false", "m_use_mouse": "0",
               "vid_activeinbackground": "true", "vid_lowerinbackground": "false"}
# These existing built-ins have flags 0. ReadCVars sets their values without
# adding ARCHIVE; normal exit omits them. Runtime queries remain mandatory.
UNARCHIVED_SETTINGS = {
    "gl_portals": "src/common/rendering/hwrenderer/data/hw_cvars.cpp",
    "gl_mirrors": "src/common/rendering/hwrenderer/data/hw_cvars.cpp",
    "gl_lightprobe": "src/rendering/hwrenderer/hw_entrypoint.cpp",
    "gl_levelmesh": "src/rendering/hwrenderer/scene/hw_drawinfo.cpp",
    "gl_ubershaders": "src/common/rendering/vulkan/pipelines/vk_renderpass.cpp",
    "gl_customshader": "src/common/textures/hw_material.cpp",
}
EXTRA_PINS = ("docs/shadedoomvk/PF-020-VIEW-EVIDENCE-PROTOCOL.md", "tools/pf_oracle/run_indexed_material_runtime.py",
              "tools/pf_oracle/run_freeze_dense_runtime.py", "tools/pf_oracle/derive_freeze_view_baseline.py",
              "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp",
              "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.h",
              "src/common/rendering/vulkan/textures/vk_pfviewdiagnostics.cpp",
              "src/common/rendering/vulkan/textures/vk_pfviewdiagnostics.h")
LIMITS = ["Correctness only; no performance measurement or full PF020 acceptance.",
          "Source-derived original seams retain later accepted fixes; not a historical binary.",
          "Cold concerns exactly two application cache files; driver-global cache remains untouched.",
          "Specialized immediate BSP only; generalized/Uber/library/LevelMesh/stereo/plane mirrors/SavePicture unexecuted.",
          "User material association is inferred from unique pinned fixture source plus actual ready user key in the scene."]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_projection(value):
    # Match the generator's durable JSON representation (tuples become arrays),
    # while preserving every authored value and rejecting nonfinite numbers.
    return json.loads(json.dumps(value, allow_nan=False))


def safe_build(path, *, fresh=False):
    path = Path(path)
    path = path if path.is_absolute() else ROOT / path
    require(".." not in path.parts, "Parent traversal in evidence path")
    build = ROOT / "build"
    require(path.is_relative_to(build) and path != build, "Evidence must be a child of the sole repository build directory")
    cursor = path
    while cursor != ROOT:
        require(not cursor.is_symlink() and not getattr(cursor, "is_junction", lambda: False)(), "Evidence link/junction rejected")
        cursor = cursor.parent
    require(path.resolve() == path, "Evidence path resolves to an alias")
    base.safe_console_path(path)
    require(not fresh or not path.exists(), "Fresh output already exists; retained attempts cannot be overwritten")
    return path


def source_name(name):
    require(isinstance(name, str) and "\\" not in name and ":" not in name, "Invalid source path")
    path = PurePosixPath(name)
    require(str(path) == name and not path.is_absolute() and path.parts and all(p not in (".", "..") for p in path.parts), "Unsafe source member")
    return name


def fixture_identity(path):
    data = read_json(path, 8 * 1024 * 1024)
    require(data.get("schema") == fixture.SCHEMA and data.get("status") == "prepared-unaccepted"
            and data.get("gpuExecuted") is False, "Expected unexecuted final VIEW fixture")
    require(data.get("settings") == fixture.SETTINGS and data.get("requestedClientExtent") == fixture.EXTENT
            and data.get("scene") == json_projection(fixture.fixture())
            and data.get("observationContract") == json_projection(fixture.observation_contract(fixture.fixture())),
            "Authored settings/scene/observation contract differs")
    wanted = fixture.members()
    mod = base.checked(data["mod"], "VIEW mod")
    with zipfile.ZipFile(mod["path"]) as archive:
        require(archive.namelist() == sorted(wanted) and len(archive.namelist()) == len(wanted), "Exact authored member closure/order differs")
        for name, raw in wanted.items():
            require(archive.getinfo(name).file_size == len(raw) and archive.read(name) == raw
                    and data["mod"]["members"].get(name) == {"sha256": sha(raw), "bytes": len(raw)}, "Authored member changed: " + name)
    require(Path(mod["path"]).read_bytes() == fixture.archive_bytes(wanted), "Deterministic fixture ZIP bytes differ")
    iwad = base.checked(data["iwad"], "isolated IWAD")
    require(iwad["sha256"] == fixture.IWAD_SHA256 and data["iwad"].get("copiedIntoPackage") is False,
            "Pinned IWAD/publication policy changed")
    require(not any(p != Path(iwad["path"]) for p in Path(iwad["path"]).parent.iterdir() if p.suffix.lower() == ".wad"),
            "Unpinned adjacent WAD")
    require(fixture.stock_assets(Path(iwad["path"]).read_bytes()) == data["stockAssets"], "Actual stock input directory changed")
    config = base.checked(data["config"], "authored config")
    require(Path(config["path"]).read_text() == fixture.configuration(), "Fixture config changed")
    require(data["fixtureInterfaceSources"] == fixture.source_identity(), "Final fixture source pins changed")
    return data, {"manifest": identity(path), "iwad": iwad, "mod": mod, "config": config,
                  "fixtureSources": data["fixtureInterfaceSources"]}


def runtime_member(name):
    return name.startswith(("src/", "libraries/", "wadsrc/", "cmake/")) or name.endswith("CMakeLists.txt")


def build_identity(candidate_path, variant, derivation_path):
    candidate_path, derivation_path = safe_build(candidate_path), safe_build(derivation_path)
    report = read_json(derivation_path, 32 * 1024 * 1024)
    require(report.get("schema") == derive.SCHEMA and report.get("status") == "PASS"
            and report.get("export_byte_verified") is True and report.get("changed_path_allowlist_verified") is True
            and report.get("native_acceptance") is False and report.get("native_executed") is False,
            "Unqualified exact source derivation")
    changes, authentic = derive.derive_plan(ROOT, report.get("commit", ""))
    for key in ("commit", "git_tree", "historical", "changed_paths", "compile_definitions", "preserved"):
        require(report.get(key) == authentic.get(key), "Source derivation authentication differs: " + key)
    expected = report["closure"][variant]
    rows = expected["files"]
    committed = {name: (mode, oid) for name, mode, oid in derive.tree_entries(ROOT, report["commit"])}
    if variant == "original-seams":
        for name, body in changes.items():
            if body is None: del committed[name]
            else: committed[name] = (committed[name][0], derive.git_blob_id(body))
    require(100 <= len(rows) <= 20000 and len({r["path"].casefold() for r in rows}) == len(rows)
            and expected["file_count"] == len(rows) and derive.closure_digest(rows) == expected["sha256"]
            and {r["path"]: (r["mode"], r["git_blob"]) for r in rows} == committed,
            "Export source closure does not match the complete committed tree/exact original seams")
    source = safe_build(derivation_path.parent / variant)
    pins, live = {}, {}
    for row in rows:
        name = source_name(row["path"])
        path = source / name
        require(path.is_file() and not path.is_symlink(), "Export source unavailable: " + name)
        raw = path.read_bytes()
        require(len(raw) == row["bytes"] and sha(raw) == row["sha256"] and derive.git_blob_id(raw) == row["git_blob"],
                "Export source changed: " + name)
        pins[name] = {"bytes": len(raw), "raw_sha256": sha(raw), "git_blob": row["git_blob"]}
        if runtime_member(name):
            # Original-seam deltas are checked against current export, never against fabricated original production metadata.
            current = (derivation_path.parent / "current" / name).read_bytes()
            actual = (ROOT / name).read_bytes()
            require(actual.replace(b"\r\n", b"\n") == current.replace(b"\r\n", b"\n"), "Live engine differs from frozen derivation: " + name)
            live[name] = sha(actual)
    data = read_json(candidate_path, 32 * 1024 * 1024)
    require(data.get("schema") == "pf020-source-derived-view-build/v1" and data.get("status") == "BUILD_PASS_STAGED"
            and data.get("variant") == variant and data.get("source_head") == report["commit"]
            and data.get("source_directory") == str(source) and data.get("derivation_sha256") == identity(derivation_path)["sha256"]
            and data.get("source_files") == pins and data.get("source_unchanged") is True
            and data.get("diagnostic_only") is True and data.get("freeze_accepted") is False
            and data.get("renderer_started") is False and data.get("gpu_executed") is False, "Native staged build attestation differs")
    for step in ("configure", "build"):
        row = data["steps"][step]
        require(row.get("exit") == 0, "Native build step failed")
        pin = identity(safe_build(ROOT / row["log"]))
        require(pin["sha256"] == row["sha256"], "Native compiler log changed")
    configure = data["commands"]["configure"]
    require(configure[configure.index("-S") + 1] == str(source) and "-G" in configure
            and configure[configure.index("-G") + 1] == "Visual Studio 17 2022" and "-A" in configure
            and configure[configure.index("-A") + 1] == "x64" and "-DHAVE_VULKAN=ON" in configure
            and "-DPF020_ORIGINAL_SEAMS=" + ("ON" if variant == "original-seams" else "OFF") in configure,
            "Native source/macro/compiler configuration differs")
    build = data["commands"]["build"]
    require(build[build.index("--config") + 1] == "RelWithDebInfo", "Native build configuration differs")
    linked = safe_build(Path(data["native_build_receipt"]))
    require(identity(linked)["sha256"] == data["native_build_receipt_sha256"], "Build receipt identity changed")
    original = read_json(linked, 32 * 1024 * 1024)
    require(all(original.get(k) == v for k, v in data.items() if k not in ("native_build_receipt", "native_build_receipt_sha256", "limitations")),
            "Staged candidate differs from actual native build receipt")
    artifacts = data.get("artifacts", [])
    require(len(artifacts) == 8 and {Path(r["path"]).name for r in artifacts} == ARTIFACT_NAMES, "Complete eight native artifacts required")
    inventory = {}
    for row in artifacts:
        require(Path(row["path"]).parent == candidate_path.parent, "Staged artifact outside candidate directory")
        pin = base.checked(row, "staged native artifact")
        counterpart = base.checked({**row, "path": str(safe_build(row["source"]))}, "build counterpart")
        inventory[Path(row["path"]).name] = pin
        require(pin["sha256"] == counterpart["sha256"] and pin["bytes"] == counterpart["bytes"], "Stage/build counterpart differs")
    require(base.build_inventory(candidate_path.parent / "vkdoom.exe") == inventory, "Unlisted staged runtime file or missing build artifact")
    return {"candidate": identity(candidate_path), "derivation": identity(derivation_path), "sourceHead": report["commit"],
            "sourceFiles": len(pins), "sourceClosureSha256": expected["sha256"], "liveEngineSources": live,
            "build": inventory, "nativeReceipt": identity(linked), "sourceDirectory": str(source)}


def tool_source_identity():
    head = derive.git(ROOT, "rev-parse", "HEAD").decode("ascii").strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head), "Current tool source head unavailable")
    require(not derive.git(ROOT, "status", "--porcelain").strip(), "Current launcher/tool source must be clean and committed")
    return {"commit": head, "clean": True}


def snapshot(fixture_path, derivation_path, candidate_paths, layer_dir, expected_device_path):
    tool_source = tool_source_identity()
    _, inputs = fixture_identity(fixture_path)
    builds = {variant: build_identity(candidate_paths[variant], variant, derivation_path) for variant in ("current", "original-seams")}
    require(builds["current"]["sourceHead"] == builds["original-seams"]["sourceHead"], "Variants do not derive from the same head")
    require(expected_device_path is not None, "Exact target device preregistration is required")
    device_path = safe_build(expected_device_path)
    device = read_json(device_path)
    require(set(device) == {"name", "type", "apiVersion", "encodedDriver"} and device["name"] == "NVIDIA GeForce GTX 1650 SUPER"
            and device["type"] == "discrete gpu" and all(isinstance(v, str) and 0 < len(v) <= 128 for v in device.values()),
            "Preregistered native target device fields differ")
    return {"inputs": inputs, "variants": builds, "layer": base.layer_identity(layer_dir), "toolSource": tool_source,
            "expectedDevice": {"file": identity(device_path), "fields": device},
            "tools": {name: identity(ROOT / name) for name in EXTRA_PINS},
            "runner": identity(Path(__file__)), "stops": dense.stop_identity()}


def cache_inventory(path, *, cold=False):
    path = safe_build(path)
    result = {}
    if path.exists():
        for child in path.iterdir():
            require(child.name in CACHE_FILES and child.is_file() and not child.is_symlink(), "Only the two isolated cache files are permitted")
            require(0 < child.stat().st_size <= 64 * 1024 * 1024, "Isolated cache size invalid")
            result[child.name] = {**identity(child), "sha1": hashlib.sha1(child.read_bytes()).hexdigest()}
    require(not result if cold else set(result) == set(CACHE_FILES), "Cold cache must be absent; warm cache must contain both prior saved files")
    return result


def script(out):
    commands = [*(f"{k} {v}" for k, v in UI_SETTINGS.items()), "unbindall"]
    commands += [f"{k} {str(v).lower()}" for k, v in fixture.SETTINGS.items()]
    commands += [f"wait {WARMUP_WAIT_UNITS}", "vid_setsize 640 480", "wait 35",
                 "pf020view_begin warmup", f"wait {COLLECTION_WAIT_UNITS}", *fixture.SETTINGS, *UI_SETTINGS,
                 'screenshot "' + base.safe_console_path(out / "scene.png") + '"', "wait 35",
                 'pf020vk_dump "' + base.safe_console_path(out / "native") + '"', "pf020view_dump", "wait 35", "quit"]
    # FExecList dispatches physical lines independently; wait only delays its semicolon remainder.
    return "; ".join(commands) + "\n"


def command(exe, inputs, out, cache):
    return [str(exe), "-stdout", "-noautoload", "-noautoexec", "-nosound", "-nojoy", "-rngseed", "12345",
            "-iwad", inputs["iwad"]["path"], "-file", inputs["mod"]["path"],
            "-config", str(out / "fixture-live.ini"), "-width", "640", "-height", "480", "-window",
            # The dump command compares the explicit prefix literally. Use one
            # console-safe representation for argv and the command script.
            "-pf020viewobserve", base.safe_console_path(out / "native"), "-pf020viewfraction", "0.5",
            "-pf020viewcache", base.safe_console_path(cache),
            # D_DoomInit consumes +map as an autostart request before ordinary
            # startup commands; a map command inside +exec cannot replace it.
            "+map", fixture.MAP, "+logfile", base.safe_console_path(out / "startup.log"),
            "+exec", str(out / "execute.cfg")]


def _prepare(fixture_path, derivation_path, candidate_paths, layer_dir, out, mode, expected_device_path=None):
    require(mode in ("core", "sync"), "Only independent core/sync modes are preregistered; GPU-AV excluded")
    out = safe_build(out, fresh=True)
    before = snapshot(fixture_path, derivation_path, candidate_paths, layer_dir, expected_device_path)
    out.mkdir(parents=True, exist_ok=False)
    packets = []
    save(out / "receipt.json", {"schema": SCHEMA, "status": "PREPARING", "output": str(out), "mode": mode,
                                "before": before, "children": packets, "rendererStarted": False, "gpuExecuted": False, "freezeAccepted": False})
    for index, (variant, thermal) in enumerate(ORDER):
        child = out / f"{index + 1:02d}-{variant}-{thermal}"
        child.mkdir()
        config = child / "fixture-live.ini"
        config.write_bytes(Path(before["inputs"]["config"]["path"]).read_bytes())
        (child / "fixture-input.ini").write_bytes(config.read_bytes())
        (child / "execute.cfg").write_text(script(child), encoding="utf-8", newline="\n")
        settings = child / "vk_layer_settings.txt"
        settings.write_text("\n".join("khronos_validation." + item for item in base.settings_recipe(mode))
                            + "\nkhronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG\n"
                            + "khronos_validation.report_flags = error;warn;info\n"
                            + "khronos_validation.log_filename = " + base.safe_console_path(child / "validation.log") + "\n", encoding="utf-8", newline="\n")
        cache = out / (variant + "-cache")
        cache_inventory(cache, cold=True)
        exe = Path(before["variants"][variant]["build"]["vkdoom.exe"]["path"])
        packets.append({"ordinal": index, "variant": variant, "cacheState": thermal, "directory": str(child), "cache": str(cache),
                        "argv": command(exe, before["inputs"], child, cache), "status": "PREPARED", "rendererStarted": False,
                        "generated": {name: identity(child / name) for name in ("fixture-input.ini", "fixture-live.ini", "execute.cfg", "vk_layer_settings.txt")}})
        save(out / "receipt.json", {"schema": SCHEMA, "status": "PREPARING", "output": str(out), "mode": mode,
                                    "before": before, "children": packets, "rendererStarted": False, "gpuExecuted": False, "freezeAccepted": False})
    receipt = {"schema": SCHEMA, "status": "PREPARED", "mode": mode, "cwd": str(ROOT), "output": str(out),
               "before": before, "paths": {"fixture": str(Path(fixture_path).resolve()), "derivation": str(Path(derivation_path).resolve()),
                    "candidates": {k: str(Path(v).resolve()) for k, v in candidate_paths.items()}, "layer": str(Path(layer_dir).resolve()),
                    "expectedDevice": None if expected_device_path is None else str(Path(expected_device_path).resolve())},
               "children": packets, "watchdogSeconds": WATCHDOG_SECONDS, "warmupWaitUnits": WARMUP_WAIT_UNITS, "collectionWaitUnits": COLLECTION_WAIT_UNITS,
               "waitUnitBasis": "FWaitingCommand delayed-command Tick advances; simulation/render time is independently observed, never inferred",
               "imageTolerance": {"decodedComponents": 0, "decodedMainRgb": 0}, "rendererStarted": False, "gpuExecuted": False,
               "gpuExecutionStatus": "NOT_STARTED",
               "freezeAccepted": False, "generalizedExecuted": False, "createdUtc": base.utc(), "limits": LIMITS}
    save(out / "receipt.json", receipt)
    return receipt


def prepare(fixture_path, derivation_path, candidate_paths, layer_dir, out, mode, expected_device_path=None):
    out = safe_build(out, fresh=True)
    try:
        return _prepare(fixture_path, derivation_path, candidate_paths, layer_dir, out, mode, expected_device_path)
    except BaseException as error:
        if out.is_dir():
            partial = read_json(out / "receipt.json", 64 * 1024 * 1024) if (out / "receipt.json").is_file() else {"schema": SCHEMA, "output": str(out)}
            partial.update(status="FAIL", preparationError=f"{type(error).__name__}: {error}", rendererStarted=False,
                           gpuExecuted=False, freezeAccepted=False, finishedUtc=base.utc())
            save(out / "receipt.json", partial)
        raise


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite observation number")
    elif isinstance(value, dict):
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)


def vector(value, count):
    require(isinstance(value, list) and len(value) == count and all(type(x) in (int, float) and math.isfinite(x) for x in value), "Finite vector dimensions invalid")
    return value


def scene_evidence(data, variant):
    require(data.get("schema") == "pf020-native-scene-observation/v1" and data.get("status") == "COLLECTED_STATE_ONLY"
            and data.get("error") == "" and data.get("freezeAccepted") is False and data.get("imagesCapturedByThisObserver") is False
            and data.get("fixedActorFractionRequested") is True, "Frontend collection failed or asserts unsupported acceptance")
    finite(data)
    rows = data.get("records", [])
    require(0 < len(rows) <= 2048 and all(r.get("phase") in ("startup", "warmup") for r in rows), "Scene phase/record bounds invalid")
    scenes = [r for r in rows if r.get("event") == "scene"]
    sprites = [r for r in rows if r.get("event") == "sprite-vertices"]
    require(data.get("sceneCalls", 0) >= len(scenes) > 0 and data.get("spriteVertexCalls", 0) >= len(sprites) > 0, "Observed call counts missing")
    require(len({(r["phase"], r["event"], r["semanticKey"], r.get("tid")) for r in rows}) == len(rows), "Duplicate deduplicated scene record")
    require(any(r["phase"] == "startup" for r in scenes) and any(r["phase"] == "warmup" and r["rootType"] == "main" for r in scenes), "Startup/warm actual roots missing")
    for row in scenes:
        require(row.get("rootType") in ("main", "camera-texture", "light-probe") and 0 <= row.get("depth", -1) < 32
                and row.get("diagnosticIdentity", 0) > row.get("diagnosticParent", -1) >= 0 and row.get("eye") == 0
                and row.get("face") in (range(6) if row["rootType"] == "light-probe" else (-1,))
                and type(row.get("tic")) is int and row["tic"] >= 0, "Scene ancestry/root/face/time invalid")
        for field, n in (("position", 3), ("hardwareAngles", 3), ("viewMatrix", 16), ("projectionMatrix", 16), ("cameraPositionUniform", 4)):
            vector(row.get(field), n)
        require(row.get("fraction") == (1 if row["rootType"] == "light-probe" else .5), "Actual root interpolation fraction differs")
        require(row.get("productionContextAvailable") is (variant == "current"), "Legacy unavailable context was manufactured or current context omitted")
        if variant == "current":
            context = row.get("productionContext", {})
            require(context.get("identity", 0) > 0 and context.get("depth") == row["depth"]
                    and context.get("epoch", 0) > 0 and context.get("rootType") == row["rootType"]
                    and context.get("type") == ("portal" if row["depth"] else row["rootType"])
                    and context.get("face") == row["face"] and context.get("eye") == row["eye"]
                    and (context.get("parentIdentity", 0) > 0) is (row["depth"] > 0)
                    and context.get("lineMirror") is bool(row["lineMirrorFlag"]) and context.get("planeMirror") is bool(row["planeMirrorFlag"])
                    and context.get("mirrored") == row["mirrored"]
                    and context.get("postprocessEligible") is (row["rootType"] == "main" and row["depth"] == 0)
                    and context.get("historyEligible") is (row["rootType"] == "main" and row["depth"] == 0),
                    "Current production context depth/parity/PP/history disagrees with actual scene")
        else:
            require("productionContext" not in row, "Legacy context values invented")
    if variant == "current":
        contexts = [(r["productionContext"]["epoch"], r["productionContext"]["identity"]) for r in scenes]
        require(len(set(contexts)) == len(contexts), "Distinct actual scenes reused a production context epoch/identity token")
        roots, retained = {}, {(r["diagnosticRoot"], r["diagnosticIdentity"]): r for r in scenes}
        for row in scenes:
            context = row["productionContext"]
            root = row["diagnosticRoot"]
            require(roots.setdefault(root, context["epoch"]) == context["epoch"], "Actual same-invocation scenes disagree on production epoch")
            parent = retained.get((root, row["diagnosticParent"]))
            if parent is not None:
                require(context["parentIdentity"] == parent["productionContext"]["identity"]
                        and context["epoch"] == parent["productionContext"]["epoch"],
                        "Actual retained parent context identity/epoch disagrees with child")
    require({r["face"] for r in scenes if r["phase"] == "startup" and r["rootType"] == "light-probe" and r["depth"] == 0} == set(range(6)), "Six natural startup probe roots missing")
    require(any(r["rootType"] == "camera-texture" and r["depth"] == 0 for r in scenes), "Actual camera root missing")
    linked = [r for r in scenes if r["rootType"] == "main" and r.get("linePortalAvailable") and r["depth"] == 1]
    portals = [p for r in linked for p in r.get("linePortalSpan", [])]
    require(any(p.get("linked") is True and p.get("destinationLinksBack") is True
                and p.get("originLineIndex") == 4 and p.get("destinationLineIndex") == 9
                and p.get("sourceGroup") != p.get("destinationGroup") and p.get("displacementXY") == [1024, 0]
                and p.get("angleDifference") == 0 for p in portals), "Actual linked reciprocal portal/displacement missing or downgraded")
    require(any(r["rootType"] == "main" and r["depth"] >= 2 and r.get("mirrored") is True and "mirror" in r["semanticKey"].lower()
                for r in scenes), "Actual linked-to-mirror depth2 traversal missing")
    restored = [r for r in rows if r.get("event") == "restored"]
    require(data.get("restorationCalls", 0) >= len(restored) > 0 and any(not r.get("mirrored") and r.get("lineMirrorFlag") == 0 for r in restored), "Actual parent restoration absent")
    pp = [r for r in rows if r.get("event") == "postprocess-completed"]
    require(data.get("postprocessSceneCalls", 0) >= len(pp) > 0 and all(r.get("rootType") == "main" and r.get("face") == -1 for r in pp), "Postprocess not exclusively completed main view")
    main = {r["tid"]: r for r in sprites if r["phase"] == "warmup" and r["semanticKey"].startswith("main:-1:0:root")}
    required = set(range(4201, 4209)) | {4301, 4302, 4303, 4304, 4400}
    require(required.issubset(main), "Main rotating/wall/flat/explicit-flip/interpolated sprite witness missing")
    for row in sprites:
        require(len(row.get("verticesXYZUV", [])) == 4, "Actual emitted sprite must have four vertices")
        for vertex in row["verticesXYZUV"]: vector(vertex, 5)
        xyz = {tuple(v[:3]) for v in row["verticesXYZUV"]}
        uv = {tuple(v[3:]) for v in row["verticesXYZUV"]}
        require(len(xyz) == 4 and len(uv) == 4 and all(0 <= x <= 1 for v in row["verticesXYZUV"] for x in v[3:]), "Degenerate or out-of-range actual quad/UV")
        require(row.get("productionSurfaceAvailable") is (variant == "current"), "Actual/legacy surface availability differs")
        require(variant == "current" or "productionSurface" not in row, "Legacy named sprite surface invented")
        for field in ("previousAngles", "actorAngles", "interpolatedAngles", "effectiveSpriteAngles", "previousPosition", "actorPosition", "interpolatedPosition"):
            vector(row.get(field), 3)
    for tid, texture in zip(range(4201, 4209), fixture.ROTATIONS):
        require(main[tid]["texture"] == texture, "Actual selected stock eight-rotation texture differs")
    if variant == "current":
        for tid in range(4201, 4209):
            require(main[tid]["productionSurface"].get("frameMirrored") is (tid >= 4206), "Actual paired stock frame Flip differs")
        require(main[4301]["productionSurface"].get("presentation") == 3 and main[4302]["productionSurface"].get("presentation") == 4,
                "Actual wall/flat presentation missing")
        require(main[4303]["productionSurface"].get("uvMirrorX") is True and main[4304]["productionSurface"].get("uvMirrorY") is True,
                "Actual explicit X/Y UV flips missing")
    interpolated = main[4400]
    for field, expected in (("previousPosition", [-32, -48, 8]), ("actorPosition", [-24, -40, 8]), ("interpolatedPosition", [-28, -44, 8]),
                            ("previousAngles", [0, 0, 0]), ("actorAngles", [22.5, 0, 0]), ("interpolatedAngles", [11.25, 0, 0])):
        require(interpolated.get(field) == expected, "Positive interpolation endpoints/angles differ: " + field)
    require(interpolated["fraction"] == .5 and interpolated["effectiveSpriteAngles"][0] == 11.25, "Effective emitted interpolation yaw not positive")
    return {"validated": True, "stateOnly": True, "records": rows, "startupSixFaces": True, "mainSpriteTids": sorted(main),
            "legacyMetadataUnavailable": variant == "original-seams", "generalizedAccepted": False}


def key_evidence(data, variant):
    require(data.get("schema") == "shadedoomvk-pf020-vulkan-observation/v1" and data.get("status") == "COLLECTED_PENDING_VALIDATION"
            and data.get("error") == "" and data.get("freezeAccepted") is False and data.get("performanceMeasured") is False
            and data.get("productionNamedKeysAvailable") is (variant == "current")
            and data.get("sourceBranch") == ("current-named-seams" if variant == "current" else "source-derived-original-seams"), "Vulkan collection/source branch failed")
    finite(data)
    worker = data.get("workerState", {})
    numeric_workers = ("queued", "active", "pendingMainPublications", "failed", "scheduledPrecache", "scheduledPriority", "completedWorkers", "completedMainPublications")
    require(set(worker) == set(numeric_workers) | {"allObservedTasksCompleted"}
            and all(type(worker.get(k)) is int and worker[k] >= 0 for k in numeric_workers), "Actual worker field closure/types invalid")
    require(worker.get("allObservedTasksCompleted") is True and all(worker.get(k) == 0 for k in ("queued", "active", "pendingMainPublications", "failed")), "Actual compilation/publication workers not ready")
    require(worker.get("completedWorkers") == worker.get("scheduledPrecache", -1) + worker.get("scheduledPriority", -1), "Worker accounting incomplete")
    classification = data.get("shaderClassification", {})
    cutoff = classification.get("firstUserShader")
    require(type(cutoff) is int and cutoff > 0 and cutoff == classification.get("builtinShaderCount"), "Actual engine user cutoff missing")
    rows = data.get("keyLookups", [])
    require(0 < len(rows) <= 8192 and all(type(r.get("count")) is int and r["count"] > 0 for r in rows), "Actual key observations/counts invalid")
    user = []
    def shader_fields(shader):
        require(isinstance(shader, dict) and set(shader) == SHADER_FIELDS and isinstance(shader.get("layout"), dict)
                and set(shader["layout"]) == LAYOUT_FIELDS, "Actual meaningful shader/layout field closure missing")
        # EFF_NONE is -1 in hw_renderstate.h; other scalar fields stay nonnegative.
        require(all(type(v) is int and v >= (-1 if k == "SpecialEffect" else 0) for k, v in shader.items() if k != "layout")
                and all(type(v) is int and v >= 0 for v in shader["layout"].values()), "Shader/layout field types invalid")
    for row in rows:
        observation = row["observation"]
        require(type(observation.get("workerThread")) is bool, "Worker marker absent")
        scene = observation.get("scene")
        require(not observation["workerThread"] or scene is None, "Worker accessed an unsynchronized frontend scene")
        if scene is not None:
            require(set(scene) == {"phase", "semanticKey", "rootType", "face", "eye", "path", "sectorGroup"}, "Key must contain stable semantic scene, no invocation IDs")
        if observation.get("kind") == "shader":
            shader_fields(observation.get("shader"))
            require(type(observation.get("generalized")) is bool and type(observation.get("hit")) is bool
                    and (type(observation.get("actualGeneralizedKey")) is int if observation["generalized"] else observation.get("actualGeneralizedKey") is None), "Actual shader map partition missing")
        elif observation.get("kind") == "pipeline":
            pipeline = observation.get("pipeline", {})
            require(set(pipeline) == PIPELINE_FIELDS and set(pipeline.get("style", {})) == {"BlendOp", "SrcAlpha", "DestAlpha", "Flags"}
                    and set(observation.get("pass", {})) == PASS_FIELDS
                    and type(observation.get("ready")) is bool and type(observation.get("hit")) is bool, "Actual meaningful pipeline/style/pass field closure missing")
            shader_fields(pipeline.get("shader"))
        elif observation.get("kind") == "shader-binary-cache":
            # CalcSha1(ShaderType, sources) includes decimal type and final source
            # length. Preserve the whole production key, not only its SHA1 part.
            checksum = observation.get("actualSourceChecksum")
            require(isinstance(checksum, str) and re.fullmatch(r"[0-5]-[0-9a-f]{40}-(?:0|[1-9][0-9]*)", checksum) and type(observation.get("hit")) is bool,
                    "Actual shader binary source checksum/cache result missing")
        else: require(False, "Unknown actual key observation kind")
        if observation.get("kind") == "pipeline" and observation.get("ready") is True and observation.get("route") == "specialized-main-lookup" and not observation["workerThread"] and scene and scene["rootType"] == "main" and scene["phase"] == "warmup":
            if observation["pipeline"]["shader"]["EffectState"] >= cutoff: user.append(observation)
    require(user, "Actual ready main user-material pipeline lookup missing")
    program_matches = [r["observation"] for r in rows if r["observation"].get("kind") == "shader"
                       and not r["observation"]["workerThread"] and r["observation"].get("scene")
                       and r["observation"].get("generalized") is False
                       and (r["observation"].get("route") == "publish-existing-or-insert" or r["observation"].get("hit") is True)
                       and any(r["observation"]["shader"] == p["pipeline"]["shader"] for p in user)]
    require(program_matches, "Actual matching user ShaderProgram lookup/publication missing")
    return {"validated": True, "keys": rows, "workerState": worker, "userCutoff": cutoff, "readyUserKeys": len(user),
            "association": "Unique pinned authored identity source + actual ready main warmup pipeline; matching ShaderProgram lookup/publish can occur on its actual startup root. No emitted material-name association.",
            "shaderLookupHookBasis": "GetProgram only during pipeline creation; publication hook reports existing entry before insertion. Ready matching pipeline establishes completion.",
            "generalizedExecuted": any(r["observation"].get("generalized") is True for r in rows), "generalizedAccepted": False}


def artifact(path, expected, maximum):
    path = Path(path)
    require(path == expected and path.resolve() == expected and path.is_file() and not path.is_symlink(), "Observer artifact path not exact private output")
    require(0 < path.stat().st_size <= maximum, "Observer artifact exceeds bound")
    return path.read_bytes(), identity(path)


def completed_view_evidence(scene, variant, root, face):
    require(variant in ("current", "original-seams"), "Unknown completed producer source variant")
    scene_fields = {"phase", "semanticKey", "diagnosticRoot", "diagnosticIdentity", "diagnosticParent", "rootType", "face", "eye", "path", "sectorGroup", "completedView"}
    require(isinstance(scene, dict) and set(scene) == scene_fields, "Completed producer scene/snapshot field closure missing or changed")
    require(scene.get("phase") in ("startup", "warmup") and scene.get("rootType") == root
            and type(scene.get("face")) is int and scene["face"] == face and scene.get("eye") == 0
            and scene.get("path") == ":root" and type(scene.get("sectorGroup")) is int and scene["sectorGroup"] >= 0,
            "Completed producer root/face/eye/path/group semantics differ")
    require(all(type(scene.get(k)) is int and scene[k] > 0 for k in ("diagnosticRoot", "diagnosticIdentity"))
            and type(scene.get("diagnosticParent")) is int and scene["diagnosticParent"] == 0,
            "Completed producer invocation/root ancestry differs")
    require(scene["semanticKey"] == f"{root}:{face}:0:root:group{scene['sectorGroup']}", "Completed producer semantic key disagrees with actual view")
    view = scene.get("completedView")
    view_fields = {"depth", "tic", "fraction", "position", "hardwareAngles", "viewpointIndex", "sectorGroup", "lineMirrorFlag", "planeMirrorFlag", "mirrored", "viewMatrix", "projectionMatrix", "cameraPositionUniform", "productionContextAvailable"}
    require(isinstance(view, dict) and set(view) == view_fields | ({"productionContext"} if variant == "current" else set()),
            "Completed producer view snapshot field closure missing or changed")
    finite(view)
    require(type(view.get("depth")) is int and view["depth"] == 0 and type(view.get("tic")) is int and view["tic"] >= 0
            and type(view.get("viewpointIndex")) is int and view["viewpointIndex"] >= 0
            and type(view.get("sectorGroup")) is int and view["sectorGroup"] == scene["sectorGroup"],
            "Completed producer depth/tic/viewpoint/group differs")
    require(type(view.get("fraction")) in (int, float) and view["fraction"] == (1 if root == "light-probe" else .5),
            "Completed producer actual fraction differs")
    require(all(type(view.get(k)) is int and view[k] == 0 for k in ("lineMirrorFlag", "planeMirrorFlag")) and view.get("mirrored") is False,
            "Completed producer root mirror semantics differ")
    for field, count in (("position", 3), ("hardwareAngles", 3), ("viewMatrix", 16), ("projectionMatrix", 16), ("cameraPositionUniform", 4)):
        vector(view.get(field), count)
    require(view.get("productionContextAvailable") is (variant == "current"), "Completed producer current/legacy context availability differs")
    if variant == "current":
        context = view["productionContext"]
        context_fields = {"type", "rootType", "epoch", "identity", "parentIdentity", "depth", "face", "eye", "lineMirror", "planeMirror", "mirrored", "postprocessEligible", "historyEligible"}
        require(isinstance(context, dict) and set(context) == context_fields
                and context.get("type") == context.get("rootType") == root
                and all(type(context.get(k)) is int and context[k] > 0 for k in ("epoch", "identity"))
                and all(type(context.get(k)) is int and context[k] == 0 for k in ("parentIdentity", "depth", "eye"))
                and type(context.get("face")) is int and context["face"] == face
                and all(context.get(k) is False for k in ("lineMirror", "planeMirror", "mirrored"))
                and all(context.get(k) is (root == "main") for k in ("postprocessEligible", "historyEligible")),
                "Completed producer current context root/face/ancestry/ownership differs")
    # These are all actual stable fields. Only structural invocation tokens and
    # current-only representation are removed; tic/fraction/state stay exact.
    return {k: ({f: v for f, v in view.items() if f not in ("productionContextAvailable", "productionContext")} if k == "completedView" else v)
            for k, v in scene.items() if k not in ("diagnosticRoot", "diagnosticIdentity", "diagnosticParent")}


def image_evidence(data, out, variant="current"):
    require(data.get("productionNamedKeysAvailable") is (variant == "current"), "Image packet source/context availability differs")
    rows = data.get("images", [])
    required = {f"probe-face-{i}" for i in range(6)} | {"camera-PFVCAM-demanded"}
    require(len(rows) in (7, 8) and {r.get("semantic") for r in rows} in (required, required | {"camera-PFVCAM-startup"}), "Actual startup six-face/demanded-camera image closure missing")
    result = {}
    probe_rgb_first, probe_rgb_varies = None, False
    scene_tokens, context_tokens = set(), set()
    for row in rows:
        semantic = row["semantic"]
        require(semantic not in result, "Duplicate actual sampled image")
        probe = semantic.startswith("probe-face-")
        layer = int(semantic[-1]) if probe else 0
        extent, format_id = (row.get("width"), row.get("height")), row.get("format")
        require(all(type(x) is int and 0 < x <= 1024 for x in extent) and format_id == (97 if probe else 37), "Actual producer extent/format differs")
        require(probe or extent == (128, 128), "Actual camera extent differs from authored demand")
        require(row.get("sourceImage", 0) > 0 and row.get("producerView", 0) > 0 and row.get("sampledViewType") == 1
                and row.get("sourceViewType") == (3 if probe else 1) and row.get("sampledBaseLayer") == layer
                and row.get("sampledLayerCount") == 1 and row.get("mip") == 0 and row.get("producerMipCount", 0) >= 1
                and row.get("producerLayerCount") == (6 if probe else 1) and row.get("producerViewBaseLayer") == 0
                and row.get("producerViewLayers") == (6 if probe else 1) and row.get("channels") == 4
                and row.get("sourceLayoutBefore") == row.get("sourceLayoutAfter") == 5,
                "Actual exact source/layer/mip/layout representation differs")
        for field, value in (("producerRerendered", False), ("sourceCopied", False), ("sameFormatTexelFetch", True),
                             ("normalFenceWaited", True), ("allocationInvalidated", True)):
            require(row.get(field) is value, "Illegal/incomplete producer readback: " + field)
        require(row.get("sampler") == {"minFilter": 0, "magFilter": 0, "maxLod": 0, "anisotropyEnable": False}, "Private exact texel sampler differs")
        scene = row.get("scene", {})
        completed = completed_view_evidence(scene, variant, "light-probe" if probe else "camera-texture", layer if probe else -1)
        require(not probe or scene["phase"] == "startup", "Capture lacks actual completed producer startup identity")
        token = (scene["diagnosticRoot"], scene["diagnosticIdentity"])
        require(token not in scene_tokens, "Different producer images reused an actual completed scene token")
        scene_tokens.add(token)
        if variant == "current":
            context = scene["completedView"]["productionContext"]
            token = (context["epoch"], context["identity"])
            require(token not in context_tokens, "Different producer images reused a current context epoch/identity token")
            context_tokens.add(token)
        producer = row.get("producerState", {})
        if probe:
            require(producer.get("actualRenderAttachmentLayer") == layer and producer.get("actualRenderAttachmentFormat") == 97
                    and producer.get("actualRenderAttachmentView", 0) > 0, "Probe attachment does not prove actual rendered face")
        elif semantic.endswith("demanded"):
            require(producer.get("firstUpdate") is False and producer.get("requestedUpdate") is True, "Camera capture is only initialization, no later material demand")
        else:
            require(producer.get("firstUpdate") is True, "Startup camera metadata inconsistent")
        stem = out / ("native-" + semantic)
        suffix, component_bytes = (".rgba16f", 2) if probe else (".rgba8", 1)
        byte_count = extent[0] * extent[1] * 4 * component_bytes
        require(row.get("bytes") == byte_count and row.get("rowBytes") == extent[0] * 4 * component_bytes, "Tight same-format row size differs")
        raw, pin = artifact(row.get("file", ""), Path(str(stem) + suffix), 8 * 1024 * 1024)
        require(len(raw) == byte_count, "Actual raw image byte count differs")
        if probe:
            values = [v[0] for v in struct.iter_unpack("<e", raw)]
            require(all(math.isfinite(v) for v in values), "Actual half-float producer contains nonfinite components")
        else:
            values = raw
        # Alpha is not radiance evidence. A constant individual probe face is
        # legal, but the authored six-face bundle must have spatial RGB diversity.
        rgb_first, rgb_varies, rgb_max = tuple(values[:3]), False, -math.inf
        for offset in range(0, len(values), 4):
            rgb = tuple(values[offset:offset + 3])
            rgb_max = max(rgb_max, *rgb)
            rgb_varies |= rgb != rgb_first
            if probe:
                if probe_rgb_first is None: probe_rgb_first = rgb
                probe_rgb_varies |= rgb != probe_rgb_first
        require(rgb_max > 0, "Actual sampled producer image has no positive RGB content")
        require(probe or rgb_varies, "Actual demanded/startup camera image has no spatial RGB diversity")
        artifacts = {}
        for field, suffix_part in (("vertexGLSL", ".vert.glsl"), ("fragmentGLSL", ".frag.glsl"), ("vertexSPIRV", ".vert.spv"), ("fragmentSPIRV", ".frag.spv")):
            payload, a_pin = artifact(row.get(field, ""), Path(str(stem) + suffix_part), 2 * 1024 * 1024)
            if suffix_part.endswith("spv"):
                require(len(payload) % 4 == 0 and len(payload) >= 20 and struct.unpack_from("<I", payload)[0] == 0x07230203, "Retained compiled SPIR-V invalid")
            elif field == "fragmentGLSL":
                require(payload == b"#version 460\nlayout(set=0,binding=0) uniform sampler2D Source;layout(location=0) out vec4 Result;void main(){Result=texelFetch(Source,ivec2(gl_FragCoord.xy),0);}\n", "Private capture GLSL changed texel/format semantics")
            artifacts[field] = a_pin
        result[semantic] = {"metadata": row, "artifact": pin, "componentSha256": sha(raw), "shaderArtifacts": artifacts,
                            "rgbContent": {"positive": True, "spatialVariation": rgb_varies}, "completedViewState": completed}
    require(probe_rgb_varies, "Actual six-face probe bundle has no spatial RGB diversity")
    return result


def main_presentation_evidence(data, out, variant):
    row = data.get("mainPresentation")
    fields = {"semantic", "scene", "width", "height", "bytes", "rowBytes", "channels", "format", "file", "basis"}
    require(isinstance(row, dict) and set(row) == fields, "Actual main presentation snapshot/raw field closure missing or changed")
    require(row.get("semantic") == "main-presented" and row.get("basis") == "production-GetScreenshotBuffer-RGB"
            and (row.get("width"), row.get("height")) == (640, 480) and row.get("format") == "RGB8"
            and row.get("channels") == 3 and row.get("rowBytes") == 640*3 and row.get("bytes") == 640*480*3,
            "Actual main presented RGB representation/basis differs")
    completed = completed_view_evidence(row.get("scene"), variant, "main", -1)
    require(row["scene"]["phase"] == "warmup", "Actual main screenshot belongs to an unrequested collection phase")
    raw, pin = artifact(row.get("file", ""), out/"native-main-presented.rgb8", 640*480*3)
    require(len(raw) == row["bytes"], "Actual main presented RGB byte count differs")
    pixels, image = dense.decode_png(out/"scene.png", (640, 480))
    require(raw == pixels, "Decoded main PNG differs from actual captured presented RGB bytes")
    require(len(set(pixels)) >= 16 and max(pixels)-min(pixels) >= 32, "Actual main screenshot blank")
    return {**image, "file": identity(out/"scene.png"), "artifact": pin, "metadata": row, "completedViewState": completed,
            "scope": "Exact native presented RGB/PNG association and completed main snapshot; paired equivalence adjudicated separately"}


def cache_evidence(data, child, cache_before):
    out, cache = Path(child["directory"]), Path(child["cache"])
    path = out / "native.cache-events.jsonl"
    # The launch prefix uses forward slashes; compare the exact private Path,
    # not Windows separator spelling. Preserve the same artifact/link/bound gate.
    raw, event_pin = artifact(data.get("cacheShutdownEvents", ""), path, 2 * 1024 * 1024)
    rows = [json.loads(line, object_pairs_hook=base.no_duplicates) for line in raw.decode("utf-8").splitlines()]
    require(0 < len(rows) <= 64 and [r.get("sequence") for r in rows] == list(range(1, len(rows) + 1)), "Cache event order incomplete")
    require(rows[:len(data.get("cacheEventsAtDump", []))] == data.get("cacheEventsAtDump"), "Dump/normal-exit cache observations differ")
    after = cache_inventory(cache)
    for kind, leaf, loaded in (("shader", CACHE_FILES[0], "after-load-return"), ("pipeline", CACHE_FILES[1], "after-create")):
        events = [r for r in rows if r.get("cache") == kind]
        require([r.get("stage") for r in events] == ["before-load", loaded, "after-save-close"]
                and all(r.get("path") == str(cache / leaf) for r in events), "Actual isolated cache load/save lifecycle differs")
        initial = events[0]["file"]
        expected = cache_before.get(leaf)
        require(initial == ({"exists": False, "bytes": 0, "sha1": None} if expected is None else
                            {"exists": True, "bytes": expected["bytes"], "sha1": expected["sha1"]}), "Actual cache initial file differs from independent pre-child inventory")
        require(events[1].get("operationCompleted") is True and events[2].get("operationCompleted") is True, "Cache load/create/save operation incomplete")
        require(events[2]["file"] == {"exists": True, "bytes": after[leaf]["bytes"], "sha1": after[leaf]["sha1"]}, "Independent cache post-exit hash differs")
        if child["cacheState"] == "warm":
            require(events[1].get("count", 0) > 0, "Warm cache lacked actual loaded entries/initial data")
    if child["cacheState"] == "warm":
        require(any(r["observation"].get("kind") == "shader-binary-cache" and r["observation"].get("hit") is True for r in data.get("keyLookups", [])), "Warm real shader cache did not supply a binary hit")
    return {"before": cache_before, "after": after, "eventArtifact": event_pin, "events": rows, "actualWarmLoad": child["cacheState"] == "warm"}


def unarchived_settings():
    for name, path in UNARCHIVED_SETTINGS.items():
        source = (ROOT / path).read_text()
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        require(len(re.findall(r"\bCVAR\s*\(\s*Bool\s*,\s*" + re.escape(name)
                               + r"\s*,\s*(?:true|false)\s*,\s*0\s*\)", source)) == 1,
                "Unarchived built-in source declaration changed: " + name)
    return set(UNARCHIVED_SETTINGS)


def settings_evidence(out):
    text = base.log_text(out / "stdout.log")
    expected = {k: str(v).lower() for k, v in fixture.SETTINGS.items()} | UI_SETTINGS
    for name, value in expected.items():
        matches = re.findall(r'(?m)^"' + re.escape(name) + r'" is "([^"]*)" \(default: "[^"]*"\)\s*$', text)
        require(matches == [value], "Actual runtime CVar missing/duplicated/changed: " + name)
    sections = dense.ini_sections((out / "fixture-live.ini").read_text())
    absent = unarchived_settings()
    for name, value in expected.items():
        matches = [v.lower() for entries in sections.values() for key, v in entries if key == name]
        require(matches == ([] if name in absent else [value]), "Saved normal-exit CVar differs: " + name)
    return expected


def validate_state(out, variant):
    out = safe_build(out)
    scene = scene_evidence(read_json(out / "native.scene.json", 32 * 1024 * 1024), variant)
    vulkan = read_json(out / "native.vulkan.json", 32 * 1024 * 1024)
    return {"status": "STATE_VALIDATED_IMAGES_PENDING", "stateOnly": True, "freezeAccepted": False,
            "scene": scene, "keys": key_evidence(vulkan, variant), "rawImages": image_evidence(vulkan, out, variant),
            "mainPresentation": main_presentation_evidence(vulkan, out, variant)}


def projection(rows, key_fields, ignored):
    result = {}
    for row in rows:
        key = tuple(row.get(k) for k in key_fields)
        require(key not in result, "Ambiguous semantic record during pair comparison")
        result[key] = {k: v for k, v in row.items() if k not in ignored}
    return result


def binary_key_identity(packet):
    # Cache lookup runs before the hit-return branch. Null-scene and worker
    # records are real production identities and must not disappear here.
    result = frozenset(row["observation"]["actualSourceChecksum"] for row in packet["keys"]
                       if row["observation"].get("kind") == "shader-binary-cache")
    require(result, "Actual production shader binary key set missing")
    return result


def paired_compare(left, right):
    # Correspondence uses the actual stable root/path/group/phase, not pointer IDs or invocation counters.
    a, b = left["state"], right["state"]
    ignore = {"diagnosticRoot", "diagnosticIdentity", "diagnosticParent", "productionContextAvailable", "productionContext", "productionSurfaceAvailable", "productionSurface"}
    scene_a = projection(a["scene"]["records"], ("phase", "event", "semanticKey", "tid"), ignore)
    scene_b = projection(b["scene"]["records"], ("phase", "event", "semanticKey", "tid"), ignore)
    require(scene_a == scene_b, "Paired actual scene/sprite/matrix/UV/portal/postprocess state differs")
    binary_a, binary_b = binary_key_identity(a["keys"]), binary_key_identity(b["keys"])
    require(binary_a == binary_b, "Paired complete production shader binary key sets differ")
    def keys(packet):
        result = set()
        for row in packet["keys"]["keys"]:
            observation = row["observation"]
            if observation.get("scene") is None: continue
            fields = {k: v for k, v in observation.items() if k not in ("hit", "ready", "workerThread", "actualSourceChecksum")}
            result.add(json.dumps(fields, sort_keys=True, separators=(",", ":")))
        return result
    require(keys(a) == keys(b), "Paired meaningful actual key partitions differ")
    require(set(a["rawImages"]) == set(b["rawImages"]), "Paired sampled image closure differs")
    for name in a["rawImages"]:
        x, y = a["rawImages"][name], b["rawImages"][name]
        root, face = ("light-probe", int(name[-1])) if name.startswith("probe-face-") else ("camera-texture", -1)
        completed_a = completed_view_evidence(x["metadata"]["scene"], "original-seams" if a["scene"]["legacyMetadataUnavailable"] else "current", root, face)
        completed_b = completed_view_evidence(y["metadata"]["scene"], "original-seams" if b["scene"]["legacyMetadataUnavailable"] else "current", root, face)
        require(completed_a == completed_b, "Paired actual completed producer tic/fraction/view state differs: " + name)
        for field in ("format", "width", "height", "bytes", "rowBytes", "sampledBaseLayer", "sampledLayerCount", "producerLayerCount", "producerMipCount", "mip"):
            require(x["metadata"][field] == y["metadata"][field], "Paired image representation differs")
        require(Path(x["artifact"]["path"]).read_bytes() == Path(y["artifact"]["path"]).read_bytes(), "Exact actual sampled image components differ: " + name)
    main_a, main_b = a.get("mainPresentation"), b.get("mainPresentation")
    require(isinstance(main_a, dict) and isinstance(main_b, dict), "Paired actual main presentation snapshot missing")
    completed_a = completed_view_evidence(main_a["metadata"]["scene"], "original-seams" if a["scene"]["legacyMetadataUnavailable"] else "current", "main", -1)
    completed_b = completed_view_evidence(main_b["metadata"]["scene"], "original-seams" if b["scene"]["legacyMetadataUnavailable"] else "current", "main", -1)
    require(completed_a == completed_b, "Paired actual main presented tic/fraction/view state differs")
    require(Path(main_a["artifact"]["path"]).read_bytes() == Path(main_b["artifact"]["path"]).read_bytes(), "Paired actual main presented RGB bytes differ")
    require(left["presentation"]["decodedRgbSha256"] == right["presentation"]["decodedRgbSha256"], "Exact paired decoded main RGB differs")
    require(left["nativeDevice"] == right["nativeDevice"] and left["settings"] == right["settings"], "Paired device/settings differ")
    return {"status": "PAIRED_EXACT_MATCH", "decodedComponentTolerance": 0, "decodedMainRgbTolerance": 0,
            "images": sorted(a["rawImages"]), "stateSemanticRecords": len(scene_a),
            "shaderBinaryKeys": len(binary_a), "shaderBinaryKeySetSha256": hashlib.sha256("\n".join(sorted(binary_a)).encode("ascii")).hexdigest(),
            "generalizedAccepted": False, "freezeAccepted": False}


def collect(child, before, mode):
    out = Path(child["directory"])
    text = base.log_text(out / "stdout.log")
    require(text.count("PF020_VIEW_BEGIN warmup") == 1 and text.count("PF020_VIEW_STATE_WRITTEN") == 1
            and not re.search(r"PF020.*(?:REJECTED|FAILED|failed)|Script error|Execution could not continue|Fatal error", text, re.I), "Runtime command/fixture/observer failed")
    require(re.findall(r"(?m)^D_DoomInit: Static RNGseed (\d+) set\.$", text) == ["12345"], "Actual fixed RNG seed startup acknowledgement missing/changed")
    child["nativeDevice"] = dense.native_device(text)
    require(child["nativeDevice"] == before["expectedDevice"]["fields"], "Actual native device/API/driver differs from preregistration")
    startup = identity(out / "startup.log")
    require(0 < startup["bytes"] <= 32 * 1024 * 1024, "Actual startup capability log missing or unbounded")
    child["startupLog"] = startup
    validation = base.validation_evidence(out, mode)
    require(validation["requestedModeVerified"] and validation["errorCount"] == validation["warningCount"] == 0, "Actual requested loader/core/sync proof absent or validation findings")
    child["validation"] = validation
    packages = base.loaded_package_evidence(out, {"build": before["variants"][child["variant"]]["build"], "inputs": before["inputs"]})
    require(packages["verified"] and packages["packageCount"] == 7, "Actual loaded package closure is not exactly seven pinned files")
    child["packages"] = packages
    child["settings"] = settings_evidence(out)
    child["state"] = validate_state(out, child["variant"])
    child["cacheEvidence"] = cache_evidence(read_json(out / "native.vulkan.json", 32 * 1024 * 1024), child, child["cacheBefore"])
    retained = out / "cache-saved"
    retained.mkdir(exist_ok=False)
    copies = {}
    for leaf, pin in child["cacheEvidence"]["after"].items():
        actual = Path(pin["path"])
        require(identity(actual) == {k: v for k, v in pin.items() if k != "sha1"}, "Cache changed before evidence retention")
        target = retained / leaf
        with target.open("xb") as stream: stream.write(actual.read_bytes())
        copy = identity(target)
        require(copy["sha256"] == pin["sha256"] and copy["bytes"] == pin["bytes"] and hashlib.sha1(target.read_bytes()).hexdigest() == pin["sha1"],
                "Retained cache evidence bytes differ")
        copies[leaf] = copy
    child["cacheEvidence"]["retainedCopies"] = copies
    child["presentation"] = child["state"]["mainPresentation"]


def retained_inventory(out, receipt):
    rows, errors = [], []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in ("receipt.json", "receipt.json.tmp"):
            try: rows.append(identity(path))
            except Exception as error: errors.append({"path": str(path), "error": repr(error)})
    receipt["outputs"] = rows
    if errors: receipt.update(status="FAIL", outputIdentityErrors=errors)


def windows_token_info(pid=None):
    """Query-only token proof; no privilege adjustment, elevation or ignored-tool dependency."""
    require(os.name == "nt", "Windows token proof requires the approved Windows host")
    require(pid is None or (type(pid) is int and pid > 0), "Own child token query PID invalid")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]; advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]; advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]; advapi.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]; advapi.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    def checked(ok):
        if not ok: raise ctypes.WinError(ctypes.get_last_error())
    process = kernel.OpenProcess(0x1000, False, pid) if pid is not None else kernel.GetCurrentProcess()
    checked(process)
    token = wintypes.HANDLE()
    try:
        checked(advapi.OpenProcessToken(process, 8, ctypes.byref(token)))
        needed, elevated = wintypes.DWORD(), wintypes.DWORD()
        checked(advapi.GetTokenInformation(token, 20, ctypes.byref(elevated), ctypes.sizeof(elevated), ctypes.byref(needed)))
        advapi.GetTokenInformation(token, 25, None, 0, ctypes.byref(needed))
        require(0 < needed.value <= 4096, "Token integrity query exceeds bounded size")
        buffer = ctypes.create_string_buffer(needed.value)
        checked(advapi.GetTokenInformation(token, 25, buffer, needed, ctypes.byref(needed)))
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        require(bool(sid), "Token integrity SID missing")
        count_pointer = advapi.GetSidSubAuthorityCount(sid)
        require(bool(count_pointer) and 0 < count_pointer[0] < 16, "Token integrity SID invalid")
        integrity_pointer = advapi.GetSidSubAuthority(sid, count_pointer[0]-1)
        require(bool(integrity_pointer), "Token integrity RID missing")
        return {"pid": os.getpid() if pid is None else pid, "elevated": bool(elevated.value),
                "integrityRid": integrity_pointer[0], "queryOnly": True}
    finally:
        if token: kernel.CloseHandle(token)
        if pid is not None and process: kernel.CloseHandle(process)


def require_medium_token(token, label, pid=None):
    require(isinstance(token, dict) and set(token) == {"pid", "elevated", "integrityRid", "queryOnly"}
            and type(token.get("pid")) is int and token["pid"] > 0 and (pid is None or token["pid"] == pid)
            and type(token.get("integrityRid")) is int and token["integrityRid"] == 8192
            and token.get("elevated") is False and token.get("queryOnly") is True,
            label + " requires actual medium RID8192 and TokenElevation false query-only proof")


def launch(receipt, *, popen=subprocess.Popen, clock=time.monotonic, token_query=None):
    require(receipt.get("schema") == SCHEMA and receipt.get("status") == "PREPARED"
            and receipt.get("rendererStarted") is False and receipt.get("cwd") == str(ROOT), "Only a pristine preregistered packet may launch")
    out = safe_build(receipt["output"])
    paths = receipt["paths"]
    require(receipt.get("mode") in ("core", "sync") and receipt.get("watchdogSeconds") == WATCHDOG_SECONDS
            and receipt.get("warmupWaitUnits") == WARMUP_WAIT_UNITS and receipt.get("collectionWaitUnits") == COLLECTION_WAIT_UNITS
            and receipt.get("imageTolerance") == {"decodedComponents": 0, "decodedMainRgb": 0}
            and [(c.get("variant"), c.get("cacheState")) for c in receipt.get("children", [])] == list(ORDER),
            "Preregistered mode/order/timing/tolerance changed")
    for index, child in enumerate(receipt["children"]):
        expected_out = out / f"{index + 1:02d}-{child['variant']}-{child['cacheState']}"
        expected_cache = out / (child["variant"] + "-cache")
        exe = Path(receipt["before"]["variants"][child["variant"]]["build"]["vkdoom.exe"]["path"])
        require(child.get("ordinal") == index and child.get("status") == "PREPARED" and child.get("rendererStarted") is False
                and child.get("directory") == str(expected_out) and child.get("cache") == str(expected_cache)
                and child.get("argv") == command(exe, receipt["before"]["inputs"], expected_out, expected_cache)
                and (expected_out / "execute.cfg").read_text() == script(expected_out)
                and (expected_out / "fixture-live.ini").read_text() == fixture.configuration(),
                "Preregistered child paths/argv/script/config changed")
    def current_snapshot():
        return snapshot(Path(paths["fixture"]), Path(paths["derivation"]), {k: Path(v) for k, v in paths["candidates"].items()}, Path(paths["layer"]),
                        None if paths.get("expectedDevice") is None else Path(paths["expectedDevice"]))
    require(current_snapshot() == receipt["before"], "Prelaunch source/build/fixture/layer/STOP changed")
    receipt.update(status="RUNNING", startedUtc=base.utc())
    process = None
    try:
        save(out / "receipt.json", receipt)
        query = windows_token_info if token_query is None else token_query
        try: receipt["coordinatorToken"] = query()
        except BaseException as error:
            receipt["coordinatorTokenQueryError"] = {"error": repr(error), "winerror": getattr(error, "winerror", None)}
            raise
        require_medium_token(receipt["coordinatorToken"], "Coordinator")
        for child in receipt["children"]:
            child_out = Path(child["directory"])
            for name, pin in child["generated"].items(): require(identity(child_out / name) == pin, "Prepared child input changed")
            child["cacheBefore"] = cache_inventory(Path(child["cache"]), cold=child["cacheState"] == "cold")
            if child["cacheState"] == "warm":
                cold = next(c for c in receipt["children"] if c["variant"] == child["variant"] and c["cacheState"] == "cold")
                require(cold.get("status") == "CHILD_VALIDATED" and cold["cacheEvidence"]["after"] == child["cacheBefore"], "Warm cache is not the exact completed own cold cache")
            child["status"] = "RUNNING"
            save(out / "receipt.json", receipt)
            environment, child["environment"] = base.environment(child_out, Path(paths["layer"]))
            with (child_out / "stdout.log").open("xb") as stdout, (child_out / "stderr.log").open("xb") as stderr:
                process = popen(child["argv"], cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
                # Every operation after Popen stays inside the own-child cleanup region.
                try:
                    child.update(rendererStarted=True, pid=process.pid)
                    receipt["rendererStarted"] = True
                    receipt["gpuExecutionStatus"] = "STARTED_WORK_NOT_YET_QUALIFIED"
                    try: child["nativeToken"] = query(process.pid)
                    except BaseException as error:
                        child["nativeTokenQueryError"] = {"error": repr(error), "winerror": getattr(error, "winerror", None)}
                        raise
                    require_medium_token(child["nativeToken"], "Own native child", process.pid)
                    save(out / "receipt.json", receipt)
                    started = clock()
                    while process.poll() is None:
                        require(clock() - started < WATCHDOG_SECONDS, "Own native child watchdog expired")
                        for name in ("stdout.log", "stderr.log", "startup.log"):
                            log = child_out / name
                            require(not log.exists() or log.stat().st_size <= 32 * 1024 * 1024, "Native log cap exceeded")
                        try: process.wait(timeout=.25)
                        except subprocess.TimeoutExpired: pass
                    child["exitCode"] = process.wait(timeout=10)
                    require(child["exitCode"] == 0, "Native child did not exit normally")
                finally:
                    if process.poll() is None:
                        process.kill(); child["exitCode"] = process.wait(timeout=10)
                        child["cleanupAction"] = "Killed and waited for only the own Popen child"
            process = None
            collect(child, receipt["before"], receipt["mode"])
            child["gpuExecuted"] = True
            receipt.update(gpuExecuted=True, gpuExecutionStatus="ACTUAL_COMPLETED_PRODUCER_READBACK_VERIFIED")
            require(current_snapshot() == receipt["before"], "Immutable source/build/input/layer/STOP changed during child")
            for name in ("fixture-input.ini", "execute.cfg", "vk_layer_settings.txt"):
                require(identity(child_out / name) == child["generated"][name], "Immutable generated child input changed")
            child["status"] = "CHILD_VALIDATED"
            save(out / "receipt.json", receipt)
        receipt["comparisons"] = []
        for thermal in ("cold", "warm"):
            pair = [c for c in receipt["children"] if c["cacheState"] == thermal]
            receipt["comparisons"].append({"cacheState": thermal, **paired_compare(*pair)})
        receipt.update(status="PASS_BOUNDED_SPECIALIZED_EQUIVALENCE", gpuExecuted=True)
    except BaseException as error:
        receipt.update(status="FAIL", error=f"{type(error).__name__}: {error}", winerror=getattr(error, "winerror", None))
    finally:
        try:
            if process is not None and process.poll() is None:
                process.kill(); process.wait(timeout=10)
        except BaseException as error:
            receipt.update(status="FAIL", childCleanupError=f"{type(error).__name__}: {error}",
                           cleanupScope="Only the retained own Popen child; no global process termination")
        receipt["finishedUtc"] = base.utc()
        try:
            receipt["after"] = current_snapshot()
            require(receipt["after"] == receipt["before"], "Final immutable identity differs")
        except Exception as error: receipt.update(status="FAIL", identityError=repr(error))
        try: retained_inventory(out, receipt)
        except Exception as error: receipt.update(status="FAIL", outputIdentityError=repr(error))
        save(out / "receipt.json", receipt)
    return 0 if receipt["status"] == "PASS_BOUNDED_SPECIALIZED_EQUIVALENCE" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--derivation", type=Path)
    parser.add_argument("--current-candidate", type=Path)
    parser.add_argument("--original-candidate", type=Path)
    parser.add_argument("--layer-dir", type=Path)
    parser.add_argument("--expected-device", type=Path)
    parser.add_argument("--mode", choices=("core", "sync"), default="core")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=("current", "original-seams"))
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--launch", action="store_true")
    actions.add_argument("--validate-state", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.validate_state:
            require(args.variant is not None, "State validation needs exact source variant")
            result = validate_state(args.out, args.variant)
            print(json.dumps({k: v for k, v in result.items() if k not in ("scene", "keys", "rawImages")}))
            return 0
        if args.launch:
            receipt = read_json(safe_build(args.out) / "receipt.json", 64 * 1024 * 1024)
            return launch(receipt)
        require(all((args.fixture, args.derivation, args.current_candidate, args.original_candidate, args.layer_dir, args.expected_device)),
                "Preparation needs all fixture/derivation/build/layer/target device inputs")
        receipt = prepare(args.fixture, args.derivation, {"current": args.current_candidate, "original-seams": args.original_candidate},
                          args.layer_dir, args.out, args.mode, args.expected_device)
        print(json.dumps({"status": receipt["status"], "rendererStarted": False, "freezeAccepted": False, "receipt": str(args.out / "receipt.json")}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        if args.launch and "receipt" in locals():
            receipt.update(status="FAIL", prelaunchError=f"{type(error).__name__}: {error}", freezeAccepted=False)
            try: save(safe_build(args.out) / "receipt.json", receipt)
            except OSError as save_error: print("Failure receipt unavailable: " + str(save_error), file=sys.stderr)
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
