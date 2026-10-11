#!/usr/bin/env python3
"""Prepare, capture, validate, compare and summarize the SDVK renderer corpus.

Every capture uses a fresh process/config/application cache/output directory.
No command retries a failed attempt or changes a comparison tolerance after it.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

try:
    from . import adapters, benchmark, images, validate
    from .common import ROOT, EvidenceError, artifact_path, canonical, checked, integer, pin, read_json, require, sha256, write_json
except ImportError:
    import adapters
    import benchmark
    import images
    import validate
    from common import ROOT, EvidenceError, artifact_path, canonical, checked, integer, pin, read_json, require, sha256, write_json

PACKAGES = ("vkdoom.pk3", "game_support.pk3", "lights.pk3", "brightmaps.pk3", "game_widescreen_gfx.pk3")
CHANNEL_KIND = {"view": "context", "materials": "material", "lighting": "light-query", "probes": "probe",
                "resources": "resource", "pipelines": "pipeline", "shadows": "shadow"}


def preparation_module():
    try:
        from . import prepare
    except ImportError:
        import prepare
    return prepare


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def host_profile():
    cpu = platform.processor()
    info = Path("/proc/cpuinfo")
    if info.is_file():
        names = re.findall(r"(?m)^model name\s*:\s*(.+)$", info.read_text(encoding="utf-8", errors="replace"))
        if names:
            cpu = names[0]
    return {"platform": platform.platform(), "machine": platform.machine(),
            "cpu_model": cpu or "unavailable", "logical_processors": os.cpu_count(),
            "allowed_processors": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "power_and_scheduling": "external host policy; not controlled by the harness"}


def fresh_directory(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def image_policy(scene, selected):
    require(selected in ("exact", "tolerant"), "Unknown image policy selection")
    if selected == "exact":
        return {"metric": "exact-rgb8"}
    tolerance = scene["comparison"]["image"]["tolerant_rgb"]
    result = {"metric": "rgb8-absolute", "max_channel_error": tolerance["max_absolute_error"],
              "mean_channel_error": tolerance["mean_absolute_error"],
              "changed_pixel_fraction": tolerance["maximum_changed_pixel_fraction"]}
    images.validate_policy(result)
    return result


def prepared_scene(directory, identity):
    directory = Path(directory).resolve(strict=True)
    module = preparation_module()
    # Authenticate actual recipe/source/member bytes, not just a rewritten hash
    # inventory. The chosen runtime copies are independently pinned below.
    prepared = module.verify_prepared(directory)
    catalog = module.load_catalog()
    scenes = [scene for scene in catalog["scenes"] if scene["id"] == identity]
    require(len(scenes) == 1, "Unknown/duplicate corpus scene")
    scene = scenes[0]
    require(any(item["id"] == identity for item in prepared["scenes"]), "Scene was not selected in this preparation")
    native = scene["native"]
    for key in ("pk3", "config", "capture_script"):
        path = artifact_path(directory, native[key])
        require(path.is_file(), f"Prepared scene file is missing: {native[key]}")
    return directory, prepared, scene


def loaded_packages(text, expected, *, verify_files=True):
    require(text.count("W_Init: Init WADfiles.") == 1, "Expected exactly one actual loaded-package inventory")
    found = re.findall(r"(?m)^adding (.+), (\d+) lumps\s*$", text)
    require(found, "Engine did not report loaded packages")
    rows, seen = [], set()
    for name, count in found:
        path = str(Path(name).resolve())
        require(path in expected and path not in seen, f"Unknown/duplicate loaded package: {name}")
        seen.add(path)
        actual = pin(path) if verify_files else expected[path]
        require(actual == expected[path], f"Loaded package changed during capture: {name}")
        rows.append({**actual, "lumps": int(count)})
    require(seen == set(expected), "One or more preregistered packages were not loaded")
    return rows


def console_settings(text, expected):
    """Require actual engine readbacks, including CVars outside frame settings."""
    result = {}
    for key, value in expected.items():
        values = re.findall(r'(?m)^"' + re.escape(key) + r'" is "([^"\r\n]*)" \(default: "[^"\r\n]*"\)\s*$', text)
        require(len(values) == 1, "Missing or repeated actual setting readback: " + key)
        if type(value) is bool:
            require(values[0] in ("true", "false"), "Invalid boolean setting readback: " + key)
            actual = values[0] == "true"
        elif isinstance(value, str):
            actual = values[0]
        else:
            try:
                actual = float(values[0])
            except ValueError as error:
                raise EvidenceError("Invalid numeric setting readback: " + key) from error
        require(actual == value, "Actual console setting differs: " + key)
        result[key] = actual
    return result


def completion_log(text):
    require(text.count("SDVK_OBSERVATION_COLLECTED:") == 1 and not re.search(
        r"SDVK_OBSERVATION_(?:FAILED|REJECTED|WRITE_FAILED)|Script error|Execution could not continue|Fatal error|Unknown command", text),
        "Native observation completion marker missing or startup/observer failed")


def package_identity(run):
    return [(Path(row["path"]).name, row["sha256"], row["bytes"], row["lumps"])
            for row in run["loaded_packages"]]


def _console_path(path):
    value = Path(path).resolve().as_posix()
    require(not any(c in value for c in '\";\r\n\t\0'), "Path cannot be represented by an engine console argument")
    return value


def validated_extent(profile, native, argv):
    extent = profile.get("extent")
    reference = profile.get("reference_extent", extent)
    require(reference == native["extent"], "Preregistered reference extent differs from the retained recipe")
    require(isinstance(extent, list) and len(extent) == 2 and all(type(value) is int and value > 0 for value in extent),
            "Preregistered capture extent is malformed")
    require(extent[0] <= 1920 and extent[1] <= 1080, "Preregistered capture extent exceeds bounded evidence dimensions")
    require(extent == reference or "reference_extent" in profile,
            "Legacy capture receipt cannot silently override its retained recipe extent")
    for flag, value in (("-width", extent[0]), ("-height", extent[1])):
        require(argv.count(flag) == 1 and argv.index(flag) + 1 < len(argv), "Native request has no unique " + flag)
        require(argv[argv.index(flag) + 1] == str(value), "Native request extent disagrees with preregistration")
    return extent


def capture_extent(args, native, mode):
    reference = list(native["extent"])
    requested = getattr(args, "extent", None)
    if not requested:
        return reference
    match = re.fullmatch(r"([1-9][0-9]{0,4})x([1-9][0-9]{0,4})", requested)
    require(match is not None, "Extent override must be WIDTHxHEIGHT")
    extent = [int(match.group(1)), int(match.group(2))]
    require(extent[0] <= 1920 and extent[1] <= 1080, "Extent override exceeds bounded evidence dimensions")
    return extent


def apply_extent(argv, extent):
    result = list(argv)
    for flag, value in (("-width", extent[0]), ("-height", extent[1])):
        require(result.count(flag) == 1, "Prepared native argv has no unique " + flag)
        index = result.index(flag)
        require(index + 1 < len(result), "Prepared native extent flag has no value")
        result[index + 1] = str(value)
    return result


def version_identity(stdout):
    """Read native LF or Windows CRT CRLF output without changing retained bytes."""
    text = stdout.decode("utf-8", errors="strict")
    lines = text.splitlines()
    commits = [line.removeprefix("Commit: ") for line in lines if line.startswith("Commit: ")]
    states = [line.removeprefix("Working tree: ") for line in lines if line.startswith("Working tree: ")]
    require(lines and lines[0].startswith("ShadeDoomVK ") and len(commits) == len(states) == 1
            and re.fullmatch(r"[0-9a-f]{40}", commits[0]) and states[0] in ("clean", "modified"),
            "Executable has no valid SDVK build identity")
    return commits[0], states[0]


def capture(args):
    prepared_dir, prepared, scene = prepared_scene(args.prepared, args.scene)
    native = scene["native"]
    require(native.get("generic_capture_supported", True), "This PF recipe requires its retained dedicated state driver")
    require(not native.get("manual_opt_in") or args.include_stress,
            "This bounded stress/probe recipe requires the explicit --include-stress selection")
    mode = args.mode
    extent = capture_extent(args, native, mode)
    frames = args.frames if args.frames is not None else (1 if mode == "state" else 120)
    warmup = args.warmup if args.warmup is not None else native.get("recommended_warmup_frames", 120)
    integer(frames, "requested frames", minimum=1, maximum=4096)
    integer(warmup, "warmup frames", maximum=100000)
    integer(args.timeout, "timeout seconds", minimum=1, maximum=3600)
    exe, iwad = Path(args.exe).resolve(strict=True), Path(args.iwad).resolve(strict=True)
    require(exe.is_file() and iwad.is_file(), "Executable and IWAD must be files")
    for path in (exe, iwad, prepared_dir, args.out):
        _console_path(path)
    iwad_pin = pin(iwad)
    expected_iwad = native.get("iwad", {}).get("sha256")
    if expected_iwad:
        require(iwad_pin["sha256"] == expected_iwad, "IWAD differs from this retained PF recipe's exact content identity")
    out = fresh_directory(args.out)
    started = utc()
    status, error = "FAIL", ""
    result = {"schema": "sdvk-renderer-run/v1", "status": "FAIL", "mode": mode,
              "scene": scene["id"], "started_utc": started, "error": "capture did not finish",
              "native_acceptance_awarded": False}
    try:
        (out / "input").mkdir()
        (out / "cache").mkdir()
        (out / "save").mkdir()
        # An isolated IWAD avoids sibling WAD autoload and leaves original bytes intact.
        shutil.copyfile(iwad, out / "input" / iwad.name)
        shutil.copyfile(artifact_path(prepared_dir, native["pk3"]), out / "input" / "scene.pk3")
        shutil.copyfile(artifact_path(prepared_dir, native["config"]), out / "fixture.ini")
        shutil.copyfile(out / "fixture.ini", out / "input" / "fixture.ini")
        shutil.copyfile(artifact_path(prepared_dir, native["capture_script"]), out / "capture.cfg")
        write_json(out / "recipe.json", scene)
        write_json(out / "prepared.json", prepared)
        for key, relative in (("pk3", "input/scene.pk3"), ("config", "input/fixture.ini"), ("capture_script", "capture.cfg")):
            original = prepared["files"][native[key]]
            require(pin(out / relative)["sha256"] == original["sha256"] and (out / relative).stat().st_size == original["bytes"],
                    "Prepared input changed while being copied: " + key)
        require(pin(out / "input" / iwad.name)["sha256"] == iwad_pin["sha256"], "IWAD changed while being copied")
        executable = pin(exe)
        expected = {str((exe.parent / name).resolve()): pin(exe.parent / name) for name in PACKAGES
                    if (exe.parent / name).is_file()}
        require((exe.parent / "vkdoom.pk3").is_file(), "Executable runtime has no vkdoom.pk3")
        for path in (out / "input" / iwad.name, out / "input" / "scene.pk3"):
            expected[str(path)] = pin(path)
        version = subprocess.run([str(exe), "--version"], cwd=out, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30, check=False)
        (out / "version.txt").write_bytes(version.stdout)
        (out / "version-stderr.txt").write_bytes(version.stderr)
        require(version.returncode == 0, "Executable --version failed")
        source_commit, working_tree = version_identity(version.stdout)
        profile = {"scene": scene["id"], "recipe_sha256": sha256(canonical(scene)),
                   "iwad_sha256": iwad_pin["sha256"], "scene_sha256": pin(out / "input" / "scene.pk3")["sha256"],
                   "config_sha256": pin(out / "input" / "fixture.ini")["sha256"],
                   "script_sha256": pin(out / "capture.cfg")["sha256"],
                   "seed": native["seed"], "extent": extent, "reference_extent": native["extent"], "camera": native["camera"],
                   "settings": native["settings"], "clock": native["clock"][mode],
                   "warmup_frames": warmup, "frames": frames,
                   "application_cache": "fresh-empty-directory-per-process",
                   "driver_cache": "external-driver-cache-uncontrolled",
                   "gpu_timestamps_requested": args.gpu,
                   "image_policy": image_policy(scene, args.image_policy)}
        prefix = _console_path(out / "native")
        substitutions = {"exe": str(exe), "iwad": str(out / "input" / iwad.name),
                         "pk3": str(out / "input" / "scene.pk3"), "config": str(out / "fixture.ini"),
                         "capture_script": str(out / "capture.cfg")}
        argv = apply_extent([part.format(**substitutions) for part in native["argv"]], extent)
        argv += ["-savedir", str(out / "save"), "-sdvkobserve", prefix,
                 "-sdvkobserveframes", str(frames), "-sdvkobservewarmup", str(warmup),
                 "-sdvkobservemode", mode, "-sdvkobservecache", _console_path(out / "cache"), "-sdvkobservequit"]
        if args.gpu:
            argv.append("-sdvkobservegpu")
        env_keys = ("VK_ICD_FILENAMES", "VK_DRIVER_FILES", "VK_INSTANCE_LAYERS", "VK_LAYER_PATH", "DISPLAY",
                    "WAYLAND_DISPLAY", "SDL_VIDEODRIVER", "LP_NUM_THREADS", "OMP_NUM_THREADS",
                    "MESA_SHADER_CACHE_DISABLE", "MESA_SHADER_CACHE_DIR", "MESA_LOADER_DRIVER_OVERRIDE",
                    "VK_LOADER_DRIVERS_SELECT", "VK_LOADER_DRIVERS_DISABLE", "VK_LOADER_LAYERS_ENABLE",
                    "VK_LOADER_LAYERS_DISABLE", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")
        preregister = {"schema": "sdvk-renderer-request/v1", "argv": argv, "cwd": str(out), "mode": mode,
                       "reproduction": profile, "executable": executable, "source_commit": source_commit, "working_tree": working_tree,
                       "packages": expected, "timeout_seconds": args.timeout,
                       "prepared_manifest": pin(out / "prepared.json", relative_to=out),
                       "iwad_artifact": "input/" + iwad.name,
                       "environment": {key: os.environ[key] for key in env_keys if key in os.environ},
                       "host": host_profile(), "automatic_retries": 0}
        write_json(out / "request.json", preregister)
        start = time.monotonic()
        with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
            process = subprocess.run(argv, cwd=out, stdout=stdout, stderr=stderr, timeout=args.timeout, check=False)
        elapsed = time.monotonic() - start
        require(process.returncode == 0, f"Native process exited {process.returncode}")
        text = (out / "stdout.log").read_text(encoding="utf-8", errors="replace")
        completion_log(text)
        packages = loaded_packages(text, expected)
        readbacks = console_settings(text, native["settings"])
        require(pin(exe) == executable, "Executable changed while capture was running")
        raw = read_json(out / "native.renderer.json")
        required = [CHANNEL_KIND.get(name, name) for name in scene["required_state_channels"] if name != "sprites"] if mode == "state" else []
        structural = validate.observation(raw, required_kinds=required, expected_map=native["map"],
                                          expected_frames=frames, expected_extent=extent)
        require(raw["build"]["commit"] == source_commit and raw["build"]["working_tree"] == working_tree,
                "Runtime and startup build identities disagree")
        require(raw["build"]["backend"] == "vulkan", "Requested Vulkan backend did not initialize")
        require(raw["warmup_frames"] == warmup and raw["gpu_timing_requested"] is args.gpu,
                "Actual observer warmup/GPU timing mode differs from preregistration")
        _scene_assertions(raw, scene)
        if mode == "state":
            extent, pixels = images.decode(out / "native.png")
            require(list(extent) == profile["extent"] and raw["screenshot"]["available"] is True,
                    "Screenshot or actual client extent is missing")
        result.update(status="COLLECTED", error="", reproduction=profile, build=raw["build"],
                      executable=executable, loaded_packages=packages, validation=structural,
                      console_settings=readbacks,
                      elapsed_seconds=elapsed, returncode=process.returncode,
                      collection_scope="fresh native collection; owning issue acceptance remains separate")
    except (OSError, ValueError, subprocess.SubprocessError) as caught:
        error = str(caught)
        result["error"] = error
    finally:
        result["finished_utc"] = utc()
        # Inputs may be copyrighted; only identity manifests, not IWAD bytes,
        # should be included in a public issue evidence packet.
        result["artifacts"] = {path.relative_to(out).as_posix(): pin(path, relative_to=out)
                               for path in sorted(out.rglob("*")) if path.is_file() and not path.is_symlink()
                               and not path.relative_to(out).as_posix().startswith(("cache/", "save/"))}
        write_json(out / "run.json", result)
    require(result["status"] == "COLLECTED", f"Capture failed; retained at {out / 'run.json'}: {result['error']}")
    return result


def _numeric_vector_matches(actual, expected, *, tolerance=1e-9):
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    for left, right in zip(actual, expected):
        if isinstance(left, bool) or isinstance(right, bool) or not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return False
        if not math.isfinite(float(left)) or not math.isfinite(float(right)) or not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance):
            return False
    return True


_DEFAULT_PLACEHOLDER_SEMANTICS = ("brightmap-emissive", "detail", "glow")


def _material_semantics_match(value, expected, *, allow_custom=False, allow_height=False):
    layers = value.get("layers")
    if not isinstance(layers, list) or len(layers) < len(expected):
        return False
    authored = layers[:len(expected)]
    if ([layer.get("semantic") for layer in authored] != expected
            or any(layer.get("role") != "authored-layer" for layer in authored)):
        return False
    extras = layers[len(expected):]
    placeholders = []
    customs = []
    heights = []
    for layer in extras:
        semantic = layer.get("semantic")
        if semantic in _DEFAULT_PLACEHOLDER_SEMANTICS:
            if customs:
                return False  # PF-008 customs append after fixed fallback slots.
            placeholders.append(layer)
        elif semantic == "custom" and allow_custom:
            if heights:
                return False
            customs.append(layer)
        elif semantic == "height" and allow_height:
            if heights:
                return False
            heights.append(layer)
        else:
            return False
    semantics = [layer.get("semantic") for layer in placeholders]
    ordered = [name for name in _DEFAULT_PLACEHOLDER_SEMANTICS if name in semantics]
    if semantics != ordered or len(set(semantics)) != len(semantics):
        return False
    for layer in placeholders:
        source = layer.get("source")
        if (layer.get("role") != "fallback-placeholder"
                or not isinstance(source, dict) or source.get("lump") != 0
                or source.get("width") != 1 or source.get("height") != 1):
            return False
    for layer in customs + heights:
        source = layer.get("source")
        if (layer.get("role") != "authored-layer"
                or not isinstance(source, dict)
                or not isinstance(source.get("width"), int) or source["width"] <= 0
                or not isinstance(source.get("height"), int) or source["height"] <= 0):
            return False
    return True


def _material_layer_sampling_match(value, expected):
    layers = value.get("layers")
    if not isinstance(layers, list):
        return False
    for requirement in expected:
        matches = [layer for layer in layers
                   if layer.get("semantic") == requirement["semantic"]
                   and layer.get("binding") == requirement["binding"]
                   and layer.get("requested_sampling") == requirement["requested_sampling"]]
        if len(matches) != 1 or matches[0].get("role") != "authored-layer":
            return False
        sampler = matches[0].get("sampler", {})
        for key in ("min_filter", "mag_filter", "mipmap_mode"):
            if key in requirement and sampler.get(key) != requirement[key]:
                return False
    return True


def _material_height_layer_match(value, expected):
    layers = value.get("layers")
    if not isinstance(layers, list):
        return False
    actual = [
        {"binding": layer.get("binding"), "requested_sampling": layer.get("requested_sampling")}
        for layer in layers
        if layer.get("semantic") == "height" and layer.get("role") == "authored-layer"
    ]
    return len(actual) == 1 and actual[0] == expected and value.get("height_texture_index") == expected["binding"]


def _material_custom_layers_match(value, expected):
    layers = value.get("layers")
    if not isinstance(layers, list):
        return False
    actual = [
        {"binding": layer.get("binding"),
         "custom_index": layer.get("custom_index"),
         "requested_sampling": layer.get("requested_sampling")}
        for layer in layers
        if layer.get("semantic") == "custom" and layer.get("role") == "authored-layer"
    ]
    return actual == expected


def _scene_assertions(raw, scene):
    frames = [r["data"] for r in raw["records"] if r["kind"] == "frame"]
    camera = scene["native"]["camera"]
    for frame in frames:
        require(_numeric_vector_matches(frame.get("camera", {}).get("position"), camera["position"]), "Actual camera position differs from the fixture")
        require(_numeric_vector_matches(frame["camera"].get("angles"), [camera["yaw"], camera["pitch"], camera["roll"]]), "Actual camera angles differ from the fixture")
        for key, expected in scene["native"]["settings"].items():
            if key in frame["settings"]:
                require(frame["settings"][key] == expected, "Actual frame setting differs: " + key)
        require(_numeric_vector_matches([frame["camera"].get("fov")], [90]), "Actual camera FOV differs from the fixture")
        for counter, bounds in scene["native"].get("frame_assertions", {}).items():
            actual = integer(frame.get(counter), "Required frame counter " + counter)
            require(actual >= bounds.get("minimum", 0) and actual <= bounds.get("maximum", actual),
                    "Required frame counter was not exercised: " + counter)
    if scene["id"] == "lights-zero":
        require(all(frame["shadow_candidates"] == frame["shadow_selected"] == 0 for frame in frames),
                "Zero-light scene unexpectedly selected shadow lights")
    if scene["id"] == "shadow-boundary":
        require(all(frame["shadow_candidates"] > 1024 and frame["shadow_selected"] == 1024
                    and frame["shadow_dropped"] == frame["shadow_candidates"] - 1024 for frame in frames),
                "Shadow capacity boundary was not exercised")
    if raw["mode"] == "state":
        assertions = scene["native"].get("state_assertions", {})
        for frame in range(1, raw["observed_frames"] + 1):
            records = [record for record in raw["records"] if record["frame"] == frame]
            roots = {record["data"]["context"]["root_type"] for record in records if record["kind"] == "context"}
            materials = {record["data"].get("name") for record in records if record["kind"] == "material"}
            require(set(assertions.get("root_types", [])).issubset(roots), "Required view producer was not observed")
            require(set(assertions.get("materials", [])).issubset(materials), "Required material was not drawn")
            if assertions.get("line_mirror"):
                require(any(record["kind"] == "context" and record["data"]["context"]["line_mirror"]
                            for record in records), "Required line-mirror context was not observed")
            for name, expected in assertions.get("material_semantics", {}).items():
                drawn = [record["data"] for record in records
                         if record["kind"] == "material" and record["data"].get("name") == name]
                require(drawn and all(_material_semantics_match(
                            value, expected, allow_custom=name in assertions.get("material_custom_layers", {}),
                            allow_height=name in assertions.get("material_height_layers", {}))
                            for value in drawn),
                        "Required material semantic bindings differ: " + name)
            for name, expected in assertions.get("material_layer_sampling", {}).items():
                drawn = [record["data"] for record in records
                         if record["kind"] == "material" and record["data"].get("name") == name]
                require(drawn and all(_material_layer_sampling_match(value, expected) for value in drawn),
                        "Required material sampler bindings differ: " + name)
            for name, expected in assertions.get("material_custom_layers", {}).items():
                drawn = [record["data"] for record in records
                         if record["kind"] == "material" and record["data"].get("name") == name]
                require(drawn and all(_material_custom_layers_match(value, expected) for value in drawn),
                        "Required custom material bindings differ: " + name)
            for name, expected in assertions.get("material_height_layers", {}).items():
                drawn = [record["data"] for record in records
                         if record["kind"] == "material" and record["data"].get("name") == name]
                require(drawn and all(_material_height_layer_match(value, expected) for value in drawn),
                        "Required height material binding differs: " + name)
            sprite = assertions.get("sprite_basis")
            if sprite:
                draws = [record["data"] for record in records if record["kind"] == "sprite-basis"]
                require(len(draws) >= sprite["minimum_draws"], "Too few actual emitted sprite-basis draws")
                explicit = [row for row in draws if row["explicit"]]
                require(explicit and all(row["surface"]["basis_valid"] for row in explicit),
                        "No qualified explicit sprite normal basis used by emitted Vulkan draws")
                require(set(sprite["presentations"]) <= {row["surface"]["presentation"] for row in explicit},
                        "Not all claimed sprite presentations used an explicit draw basis")
                require(set(sprite["material_examples"]) <= {row["material"] for row in explicit},
                        "Normal/specular, PBR or legacy sprite control not actually emitted")
                require(all(frame["settings"].get("effective_sprite_light_mode") == 2
                            and frame.get("active_lights", 0) >= 1 for frame in frames),
                        "Sprite directional lighting fixture lacked active per-pixel lights")
                for name in sprite["light_material_examples"]:
                    require(any(row["material"] == name and row["explicit"] and
                                row["light_index"] >= 0 and row["shader"] in (3, 4) for row in explicit),
                            "Normal/specular or PBR sprite lacked an active drawn light range: " + name)
                for assertion, key in (("requires_frame_mirror", "frame_mirrored"),
                                       ("requires_uv_mirror_x", "uv_mirror_x"),
                                       ("requires_uv_mirror_y", "uv_mirror_y"),
                                       ("requires_portal_mirror", "portal_mirrored")):
                    if sprite[assertion]:
                        require(any(row["surface"][key] for row in explicit),
                                "Required actual sprite TBN mirror/flip state absent: " + key)
                require(all(row["height_texture_index"] == (6 if row["material"] == "SDVRA1" else -1)
                            for row in draws if row["material"] in {"SDVRA1", "SDVPA0", "SDVLA0"}),
                        "Height-bearing sprite unexpectedly changed height binding semantics")
            relief = assertions.get("sprite_relief")
            if relief:
                draws = [r["data"] for r in records if r["kind"] == "sprite-relief"]
                require(draws, "Native emitted sprite-relief draws absent")
                require(all(row["measurement"] == "shader-sample-upper-bound-not-actual-fragment-work"
                            for row in draws), "GPU cost incorrectly inferred from shader upper bound")
                candidates = [row for row in draws if row["candidate"]]
                require(len(candidates) >= relief["minimum_candidates"], "No configured relief candidate reached draw path")
                require(all(row["quality"] == relief["quality"] and
                            abs(row["depth"] - relief["depth"]) < 1e-5 for row in candidates),
                        "Observed sprite relief quality/depth disagrees with fixed fixture settings")
                require(set(relief["eligible_materials"]) <=
                        {row["material"] for row in draws if row["eligible_draw"]},
                        "Height-bearing sprite POM was not eligible at actual Vulkan draw")
                require(all(row["height_reads_max"] == ({1:10,2:15,3:23}[relief["quality"]])
                            for row in draws if row["eligible_draw"]), "Incorrect upper sample work bound")
                for name in relief["height_absent_materials"]:
                    require(any(row["material"] == name and not row["eligible_draw"] and
                                row["height_texture_index"] == -1 for row in draws),
                            "Height-absent sprite unexpectedly eligible for POM: " + name)
                if relief["requires_mirrored_view"]:
                    require(any(row["eligible_draw"] and row["context"]["mirrored"] for row in draws),
                            "No mirrored-context height-bearing sprite relief emitted draw")
            actor_probe = assertions.get("actor_probe")
            if actor_probe:
                selections = [record["data"] for record in records if record["kind"] == "probe"
                              and record["data"].get("actor_selection", {}).get("available") is True]
                require(len(selections) >= actor_probe["minimum_draws"],
                        "Too few actual emitted actor probe draw decisions")
                require(set(actor_probe["required_indices"]) <=
                        {row["actor_selection"]["authored_index"] for row in selections},
                        "Required separate actor probe ordinals were not drawn")
                require(set(actor_probe["material_examples"]) <=
                        {row["material"] for row in selections},
                        "Required PBR actor probe material not drawn")
                if actor_probe["require_live"]:
                    for ordinal in actor_probe["required_indices"]:
                        require(any(row["actor_selection"]["authored_index"] == ordinal and
                                    row["actor_selection"]["policy"] == "spatial-nearest" and
                                    row["runtime_irradiance_index"] > 0 and
                                    row["resource"]["available"] for row in selections),
                                "Authored actor probe has no actually published descriptor pair")
                    for material in actor_probe["material_examples"]:
                        require(any(row["material"] == material and not row["fallback"] and
                                    row["actor_selection"]["selected"] for row in selections),
                                "PBR actor material did not consume a live probe pair")
                else:
                    require(any(row["actor_selection"]["policy"] == "no-probes" and
                                row["authored_index"] == -1 and row["fallback"] for row in selections),
                            "No-probe actor sprite failed to expose explicit zero IBL fallback")
            minimum_probes = assertions.get("published_probes_minimum")
            if minimum_probes is not None:
                owners = [record["data"] for record in records if record["kind"] == "resource"]
                require(owners and all(value.get("irradiance_maps", 0) >= minimum_probes
                                       and value.get("prefilter_maps", 0) >= minimum_probes for value in owners),
                        "Required published probe resources were not observed")
                require(any(record["kind"] == "probe" and record["data"].get("fallback") is False
                            and record["data"].get("resource", {}).get("available") is True for record in records),
                        "Published probes were not bound to an observed draw")
            if "sun_intensity" in assertions:
                owners = [record["data"] for record in records if record["kind"] == "resource"]
                require(owners and all(value.get("sun", {}).get("intensity") == assertions["sun_intensity"] for value in owners),
                        "Actual authored sun intensity differs")


def validate_run(path):
    try:
        return _validate_run(path)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise EvidenceError("Malformed run receipt field: " + str(error)) from error


def _validate_run(path):
    path = Path(path)
    if path.is_dir():
        path = path / "run.json"
    data = read_json(path)
    root = path.resolve().parent
    require(data.get("schema") == "sdvk-renderer-run/v1" and data.get("status") == "COLLECTED" and data.get("error") == "",
            "Run is failed, incomplete or an unknown schema")
    require(data.get("native_acceptance_awarded") is False and data.get("returncode") == 0, "Invalid run completion claims")
    artifacts = data.get("artifacts", {})
    require(isinstance(artifacts, dict) and all(isinstance(value, dict) and key == value.get("path") for key, value in artifacts.items()),
            "Artifact map names differ from their identities")
    for expected in artifacts.values():
        checked(root, expected)
    for name in ("native.renderer.json", "request.json", "recipe.json", "prepared.json", "stdout.log", "stderr.log",
                 "version.txt", "version-stderr.txt", "input/scene.pk3", "input/fixture.ini", "capture.cfg"):
        require(name in artifacts, f"Run artifact missing: {name}")
    raw = read_json(root / "native.renderer.json")
    request = read_json(root / "request.json")
    scene = read_json(root / "recipe.json")
    require(request.get("schema") == "sdvk-renderer-request/v1" and request.get("automatic_retries") == 0,
            "Unknown or retried capture request")
    require(request.get("reproduction") == data.get("reproduction"), "Run profile differs from its preregistration")
    profile = data["reproduction"]
    require(profile["recipe_sha256"] == sha256(canonical(scene)), "Recipe identity differs from preregistration")
    require(data["scene"] == profile["scene"] == scene["id"], "Scene identities disagree")
    for key in ("seed", "camera", "settings"):
        require(profile[key] == scene["native"][key], "Preregistered recipe value differs: " + key)
    extent = validated_extent(profile, scene["native"], request["argv"])
    require(profile["clock"] == scene["native"]["clock"][data["mode"]], "Clock policy differs from the fixture")
    images.validate_policy(profile["image_policy"])
    require(profile["image_policy"] in (image_policy(scene, "exact"), image_policy(scene, "tolerant")),
            "Comparison tolerance differs from the documented recipe")
    require(profile["application_cache"] == "fresh-empty-directory-per-process"
            and profile["driver_cache"] == "external-driver-cache-uncontrolled", "Unknown cache isolation claim")
    for key, name in (("scene_sha256", "input/scene.pk3"), ("config_sha256", "input/fixture.ini"),
                      ("script_sha256", "capture.cfg"), ("iwad_sha256", request["iwad_artifact"])):
        require(name in artifacts and artifacts[name]["sha256"] == profile[key], "Input identity differs: " + key)
    require(request["prepared_manifest"] == artifacts["prepared.json"], "Prepared receipt identity differs")
    prepared = read_json(root / "prepared.json")
    recipes = [item for item in prepared.get("scenes", []) if item.get("id") == scene["id"]]
    require(len(recipes) == 1 and {key: value for key, value in recipes[0].items() if key != "prepared_assets"} == scene,
            "Run recipe differs from the retained preparation")
    require(data["executable"] == request["executable"], "Executable identity differs from preregistration")
    require(data["build"] == raw["build"] and data["mode"] == raw["mode"] == request["mode"], "Run/native mode or build mismatch")
    require(raw["build"]["commit"] == request["source_commit"] and raw["build"]["working_tree"] == request["working_tree"],
            "Runtime and preregistered source identities disagree")
    require(version_identity((root / "version.txt").read_bytes()) == (request["source_commit"], request["working_tree"]),
            "Retained executable version differs from the native build")
    require(raw["warmup_frames"] == profile["warmup_frames"]
            and raw["gpu_timing_requested"] is profile["gpu_timestamps_requested"],
            "Actual observer warmup/GPU mode differs from preregistration")
    require(raw["build"]["backend"] == "vulkan", "Run did not initialize the Vulkan backend")
    application_cache = raw["build"].get("application_cache", {})
    require(application_cache.get("available") is True
            and Path(application_cache.get("path", "")) == Path(request["cwd"]) / "cache",
            "Native application cache did not use the isolated run directory")
    stdout = (root / "stdout.log").read_text(encoding="utf-8", errors="replace")
    completion_log(stdout)
    require(console_settings(stdout, scene["native"]["settings"]) == data["console_settings"], "Actual setting receipts differ")
    require(loaded_packages(stdout, request["packages"], verify_files=False) == data["loaded_packages"],
            "Retained loaded-package inventory differs from actual startup output")
    required = [CHANNEL_KIND.get(name, name) for name in scene["required_state_channels"] if name != "sprites"] if raw["mode"] == "state" else []
    structural = validate.observation(raw, required_kinds=required, expected_map=scene["native"]["map"],
                                      expected_frames=request["reproduction"]["frames"], expected_extent=extent)
    _scene_assertions(raw, scene)
    if data["mode"] == "state":
        require("native.png" in artifacts, "State capture has no image")
        require(raw["screenshot"]["available"] is True, "Native state capture did not produce its image")
        image_extent, _ = images.decode(root / "native.png")
        require(list(image_extent) == extent, "Image extent differs from the preregistered capture")
    return root, data, raw, structural


def differences(left, right, path="", result=None, maximum=20):
    result = [] if result is None else result
    if left == right or len(result) >= maximum:
        return result
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                result.append({"path": path + "/" + key, "reason": "missing key"})
            else:
                differences(left[key], right[key], path + "/" + key, result, maximum)
            if len(result) >= maximum:
                break
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            result.append({"path": path, "reason": "length differs", "left": len(left), "right": len(right)})
        for i, (a, b) in enumerate(zip(left, right)):
            differences(a, b, path + "/" + str(i), result, maximum)
            if len(result) >= maximum:
                break
    else:
        result.append({"path": path, "left": left, "right": right})
    return result


def compare_runs(left, right, *, allow_build_change=False):
    left_root, a, left_raw, _ = validate_run(left)
    right_root, b, right_raw, _ = validate_run(right)
    require(left_root != right_root, "State comparison requires two independent capture directories")
    left_request = read_json(left_root / "request.json")
    right_request = read_json(right_root / "request.json")
    require(left_request["cwd"] != right_request["cwd"],
            "The same process capture was copied and supplied twice")
    require(a["mode"] == b["mode"] == "state", "Image/state comparison requires two correctness captures")
    require(a["reproduction"] == b["reproduction"], "Reproduction profiles differ; not a controlled comparison")
    for field in ("backend", "device", "renderer", "vulkan"):
        require(a["build"].get(field) == b["build"].get(field), f"Actual {field} differs; same-device comparison is not valid")
    if not allow_build_change:
        require(comparable_build(a["build"]) == comparable_build(b["build"]) and a["executable"]["sha256"] == b["executable"]["sha256"],
                "Builds differ; use --allow-build-change for an explicit candidate comparison")
        require(package_identity(a) == package_identity(b), "Loaded engine/content package identities differ")
    require(a["build"]["working_tree"] == b["build"]["working_tree"] == "clean", "Controlled comparisons require clean identified native builds")
    static = a["reproduction"]["clock"] == "static_after_initialization"
    x, y = validate.state_projection(left_raw, static_scene=static), validate.state_projection(right_raw, static_scene=static)
    image = images.compare(left_root / "native.png", right_root / "native.png", a["reproduction"]["image_policy"])
    equal = x == y
    return {"schema": "sdvk-renderer-comparison/v1", "status": "PASS" if equal and image["passed"] else "FAIL",
            "left": pin(left_root / "run.json"), "right": pin(right_root / "run.json"),
            "explicit_build_change": allow_build_change, "state_equal": equal,
            "state_sha256": {"left": sha256(canonical(x)), "right": sha256(canonical(y))},
            "first_state_differences": differences(x, y), "image": image,
            "normalization": "Validated explicit context producer/tokens; 1e-9 view-number canonicalization; static-scene tic/fraction labels; renderer-local live slots and selected shadow rows normalized bijectively; cumulative allocation/upload-volume telemetry excluded; order/aliasing/generation/epoch/resets/cancellations/waits/failures retained",
            "performance_accepted": False}


def comparable_build(build):
    result = copy.deepcopy(build)
    cache = result.get("application_cache", {})
    if cache.get("available"):
        cache.pop("path", None)  # fresh directories intentionally have different paths
    return result


def summarize_runs(paths, minimum_samples=30):
    inputs = [validate_run(path) for path in paths]
    require(inputs, "No timing runs supplied")
    profile = inputs[0][1]["reproduction"]
    identity = comparable_build(inputs[0][1]["build"])
    require(all(data["reproduction"] == profile and comparable_build(data["build"]) == identity for _, data, _, _ in inputs),
            "Timing runs have different build/workload/device/settings profiles")
    require(identity["working_tree"] == "clean", "Timing baselines require clean identified native builds")
    require(profile["clock"] == "ordinary_engine_clock", "Timing baselines require ordinary engine time")
    first = inputs[0][1]
    require(all(data["executable"]["sha256"] == first["executable"]["sha256"]
                and package_identity(data) == package_identity(first) for _, data, _, _ in inputs),
            "Timing runs have different executable or loaded-package bytes")
    require(len({str(root) for root, _, _, _ in inputs}) == len(inputs), "A run was supplied twice")
    requests = [read_json(root / "request.json") for root, _, _, _ in inputs]
    require(len({request["cwd"] for request in requests}) == len(inputs), "The same process capture was copied and supplied twice")
    require(all(request["environment"] == requests[0]["environment"] and request["host"] == requests[0]["host"] for request in requests),
            "Timing runs have different recorded host/loader/layer/thread environments")
    summaries = [benchmark.summarize(raw, minimum_samples=minimum_samples) for _, _, raw, _ in inputs]
    return {"schema": "sdvk-renderer-baseline/v1", "status": "DESCRIPTIVE",
            "independent_processes": len(inputs), "reproduction": profile, "build": identity,
            "runs": [{"manifest": pin(root / "run.json"), "summary": summary}
                     for (root, _, _, _), summary in zip(inputs, summaries)],
            "between_run_cpu_medians": benchmark.distribution([s["cpu_render_view"]["p50"] for s in summaries], minimum_samples=1),
            "repeatability_evidence": len(inputs) >= 3,
            "limits": "Separate processes; raw per-frame values retained. No outlier deletion, pooling of nested GPU groups, significance or automatic performance acceptance."}


def ci(out, with_contracts=False):
    out = fresh_directory(out)
    module = preparation_module()
    catalog = module.load_catalog()
    module.validate_catalog(catalog)
    a = module.prepare(out / "prepare-a")
    b = module.prepare(out / "prepare-b")
    require(a == b, "Clean corpus preparations are not deterministic")
    runs = []
    if with_contracts:
        for name, spec in sorted(catalog["cpu_contracts"].items()):
            argv = [part.replace("{python}", sys.executable) for part in spec["command"]]
            log = out / (name + ".log")
            with log.open("xb") as stream:
                result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
            runs.append({"id": name, "argv": argv, "returncode": result.returncode, "log": pin(log, relative_to=out)})
            require(result.returncode == 0, f"CPU corpus contract failed: {name}; see {log}")
    result = {"schema": "sdvk-renderer-ci/v1", "status": "PASS", "preparations_equal": True,
              "scenes": [scene["id"] for scene in catalog["scenes"]], "classes": catalog["classes"],
              "catalog": pin(ROOT / "tools/renderer_oracle/corpus.json"), "cpu_contracts": runs,
              "native_execution": False, "image_or_gpu_acceptance": False,
              "scope": "Deterministic preparation and selected CPU contracts; renderer runtime coverage remains separately qualified"}
    write_json(out / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture", help="one fresh native process; never retries")
    for name in ("exe", "iwad", "prepared", "out"):
        capture_parser.add_argument("--" + name, type=Path, required=True)
    capture_parser.add_argument("--scene", required=True)
    capture_parser.add_argument("--mode", choices=("state", "timing"), default="state")
    capture_parser.add_argument("--frames", type=int)
    capture_parser.add_argument("--warmup", type=int)
    capture_parser.add_argument("--timeout", type=int, default=180)
    capture_parser.add_argument("--gpu", action="store_true", help="request numeric named GPU timestamp groups")
    capture_parser.add_argument("--include-stress", action="store_true")
    capture_parser.add_argument("--image-policy", choices=("exact", "tolerant"), default="exact")
    capture_parser.add_argument("--extent", help="bounded WIDTHxHEIGHT capture override; recorded in the reproduction profile")
    valid = sub.add_parser("validate")
    valid.add_argument("run", type=Path)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("left", type=Path)
    compare_parser.add_argument("right", type=Path)
    compare_parser.add_argument("--allow-build-change", action="store_true")
    compare_parser.add_argument("--out", type=Path, required=True)
    bench = sub.add_parser("benchmark")
    bench.add_argument("runs", nargs="+", type=Path)
    bench.add_argument("--minimum-samples", type=int, default=30)
    bench.add_argument("--out", type=Path, required=True)
    imported = sub.add_parser("import-pf")
    imported.add_argument("source", type=Path)
    imported.add_argument("--out", type=Path, required=True)
    cpu = sub.add_parser("ci")
    cpu.add_argument("--out", type=Path, required=True)
    cpu.add_argument("--with-contracts", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture(args)
        elif args.command == "validate":
            result = validate_run(args.run)[3]
        elif args.command == "compare":
            result = compare_runs(args.left, args.right, allow_build_change=args.allow_build_change)
            write_json(args.out, result)
        elif args.command == "benchmark":
            result = summarize_runs(args.runs, args.minimum_samples)
            write_json(args.out, result)
        elif args.command == "import-pf":
            result = adapters.adapt(args.source)
            write_json(args.out, result)
        else:
            result = ci(args.out, args.with_contracts)
        print(json.dumps({key: value for key, value in result.items() if key in ("schema", "status", "state_equal", "frames", "records", "scope")}, sort_keys=True))
        return 1 if result.get("status") == "FAIL" else 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
