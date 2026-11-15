#!/usr/bin/env python3
"""Qualify SHADOW-002 against actual software-Vulkan state and screenshots.

Run from the repository root with an existing exact-source engine build. Each
case is a fresh bounded process. The original synthetic cutout and its expected
receiver points are fixed before launch; screenshots are never synthesized.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.dynamic_shadows import native_scene as fixture
from tools.renderer_oracle import images, native_ci, prepare, run, validate
from tools.renderer_oracle.common import pin, read_json, require, write_json


CASES = (
    ("normal", "base", False), ("normal", "base", True),
    ("normal", "solid", True),
    ("specular", "base", False), ("specular", "base", True),
    ("pbr", "base", False), ("pbr", "base", True),
    ("normal", "flip", False), ("normal", "flip", True),
    ("normal", "orbit", False), ("normal", "orbit", True),
    ("normal", "animated", False), ("normal", "animated", True),
    ("normal", "invisible", False), ("normal", "invisible", True),
)
MIN_RED_LOSS = 8.0
MAX_UNAFFECTED_ERROR = 2


def case_name(material, variant, enabled):
    return f"{material}-{variant}-{'on' if enabled else 'off'}"


def source_pins():
    names = ("tools/dynamic_shadows/native_capture.py", "tools/dynamic_shadows/native_scene.py",
        "src/rendering/hwrenderer/hw_dynlightdata.cpp",
        "src/common/rendering/hwrenderer/data/hw_dynlightdata.h",
        "src/common/rendering/hwrenderer/data/hw_actor_shadowmask.h",
        "wadsrc/static/shaders/scene/light_shadow.glsl",
        "wadsrc/static/shaders/scene/lightmodel_normal.glsl",
        "wadsrc/static/shaders/scene/lightmodel_specular.glsl",
        "wadsrc/static/shaders/scene/lightmodel_pbr.glsl",
        "wadsrc/static/shaders/binding_struct_definitions.glsl")
    return {name: pin(ROOT / name) for name in names}


def validate_native(raw, spec, source_commit, allow_modified=False):
    validate.observation(raw, required_kinds=("frame", "context", "resource", "pipeline", "material"),
        expected_map=fixture.MAP, expected_frames=1, expected_extent=fixture.EXTENT)
    require(raw["build"]["commit"] == source_commit and raw["build"]["backend"] == "vulkan",
            "Native source/backend differs from requested build")
    require(allow_modified or raw["build"]["working_tree"] == "clean",
            "Qualification requires a clean identified build")
    require(raw["warmup_frames"] == spec["warmup_frames"] and not raw["gpu_timing_requested"],
            "Native observation frame/timing contract differs")
    require(raw.get("screenshot", {}).get("available") is True, "Actual native screenshot is missing")
    frames = [r["data"] for r in raw["records"] if r["kind"] == "frame"]
    require(len(frames) == 1, "One exact retained native frame is required")
    frame = frames[0]
    require(all(abs(actual - expected) < 0.001 for actual, expected in
                zip(frame["camera"]["position"], spec["camera_position"])),
            "Native camera position differs from authored projection")
    require(abs(frame["camera"]["angles"][0] - spec["camera_yaw"]) < 0.001
            and abs(frame["camera"]["angles"][1]) < 0.001
            and abs(frame["camera"]["fov"] - 90.0) < 0.001,
            "Native camera angles/FOV differ from authored projection")
    require(frame.get("authored_lights") == 2 and frame.get("active_lights") == 2,
            "Native fixture did not retain both authored emitters")
    states = [r["data"].get("actor_shadows") for r in raw["records"]
              if r["kind"] == "resource" and "actor_shadows" in r["data"]]
    require(states, "Native actor-shadow resource diagnostics are absent")
    for state in states:
        require(state.get("enabled") is spec["enabled"], "Actor-shadow resource switch differs")
        require(state.get("mask_width") == 64 and state.get("mask_height") == 128,
                "Native source-alpha mask extent differs")
        count, capacity = state.get("uploaded_casters"), state.get("capacity")
        require(type(count) is int and capacity == 4096 and 0 <= count <= capacity,
                "Invalid native caster upload count")
        require(state.get("record_stride_bytes") == 1072
                and state.get("buffer_bytes") == capacity * state["record_stride_bytes"]
                and type(state.get("frame_epoch")) is int and state["frame_epoch"] > 0,
                "Native caster SSBO allocation/stride/frame ownership differs")
        require(state.get("overflow_casters") == 0, "Compact fixture unexpectedly dropped caster data")
        if not spec["enabled"] or spec["variant"] == "invisible":
            require(count == 0, "Disabled/invisible actor produced shadow casters")
    if spec["enabled"] and spec["variant"] != "invisible":
        require(any(state["uploaded_casters"] > 0 for state in states),
                "No native caster upload reached the shadow test")
    material_rows = [r["data"] for r in raw["records"] if r["kind"] == "material"]
    require({r.get("name") for r in material_rows} >= {"SDVW", "SDVFL"},
            "Both actual wall and floor materials must be emitted")
    if spec["variant"] == "animated":
        actor_names = {row.get("name") for row in material_rows if row.get("name", "").startswith("SH02")}
        require(actor_names == {"SH02B0"}, "Animation did not retain the actual second source frame")
    expected_shader = {"normal": 0, "specular": 3, "pbr": 4}[spec["material"]]
    for name in ("SDVW", "SDVFL"):
        require({row.get("shader") for row in material_rows if row.get("name") == name} == {expected_shader},
                "Actual receiver material did not select the requested shader: " + name)
        bound = [r["data"] for r in raw["records"] if r["kind"] == "pipeline"
                 and r["data"].get("material") == name]
        require(bound and all(row.get("key", {}).get("shader", {}).get("EffectState") == expected_shader
                              for row in bound),
                "Native receiver pipeline differs from its declared material: " + name)
    return {"camera": frame["camera"], "actor_shadow_resources": states,
        "material_shader_ids": {name: sorted({row.get("shader") for row in material_rows if row.get("name") == name})
            for name in ("SDVW", "SDVFL", "SH02A0")},
        "scope": "actual native CPU upload/resource observations; shader visibility is tested in captured RGB"}


def capture(args, root, iwad, case):
    material, variant, enabled = case
    name = case_name(*case)
    out = root / name
    out.mkdir()
    (out / "cache").mkdir()
    (out / "save").mkdir()
    spec = fixture.recipe(material, variant, enabled)
    package = out / "scene.pk3"
    package.write_bytes(fixture.archive(material=material, variant=variant))
    native = {"settings": spec["settings"],
        "console_commands": ["unbindall", "fov 90", "vid_setsize 640 480"],
        "console_queries": sorted(spec["settings"])}
    (out / "fixture.ini").write_bytes(prepare.configuration({"native": native}))
    (out / "capture.cfg").write_bytes(prepare.capture_script({"native": native}))
    write_json(out / "recipe.json", spec)
    exe = args.exe.resolve(strict=True)
    argv = [str(exe), "-stdout", "-noautoload", "-noautoexec", "-nostartup", "-nosound", "-nojoy",
        "-rngseed", "215", "-iwad", str(iwad), "-file", str(package),
        "-config", str(out / "fixture.ini"), "-width", "640", "-height", "480", "-window",
        "-savedir", str(out / "save"), "-sdvkobserve", str(out / "native"),
        "-sdvkobserveframes", "1", "-sdvkobservewarmup", str(spec["warmup_frames"]),
        "-sdvkobservemode", "state", "-sdvkobservecache", str(out / "cache"), "-sdvkobservequit",
        "+map", fixture.MAP, "+exec", str(out / "capture.cfg")]
    expected = {str(path.resolve()): pin(path) for path in
                [exe.parent / name for name in run.PACKAGES if (exe.parent / name).is_file()] + [iwad, package]}
    request = {"schema": "shadow002-native-request/v1", "argv": argv,
        "expected_commit": args.expected_commit, "executable": pin(exe), "packages": expected,
        "source_files": source_pins(), "timeout_seconds": args.timeout,
        "recipe": pin(out / "recipe.json"), "config": pin(out / "fixture.ini"),
        "script": pin(out / "capture.cfg"), "automatic_retries": 0,
        "image_policy": {"minimum_opaque_red_loss": MIN_RED_LOSS,
            "maximum_unchanged_channel_error": MAX_UNAFFECTED_ERROR}}
    write_json(out / "request.json", request)
    result = {"schema": "shadow002-native-run/v1", "status": "FAIL", "name": name,
              "started_utc": run.utc(), "native_rendered": False}
    print(name + ": starting", flush=True)
    try:
        with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
            process = subprocess.run(argv, cwd=out, stdout=stdout, stderr=stderr,
                timeout=args.timeout, check=False)
        result["returncode"] = process.returncode
        require(process.returncode == 0, "Native renderer process failed")
        stdout = (out / "stdout.log").read_text(errors="replace")
        stderr = (out / "stderr.log").read_text(errors="replace")
        run.completion_log(stdout, stderr)
        result["loaded_packages"] = run.loaded_packages(stdout, expected)
        result["settings"] = run.console_settings(stdout, spec["settings"])
        raw = read_json(out / "native.renderer.json")
        result["native_state"] = validate_native(raw, spec, args.expected_commit, args.allow_modified_dev)
        extent, rgb = images.decode(out / "native.png")
        require(extent == fixture.EXTENT, "Native screenshot extent differs")
        require(request["source_files"] == source_pins(), "Fixture/renderer source changed during capture")
        require(pin(exe) == request["executable"], "Native executable changed during capture")
        result.update(status="COLLECTED", native_rendered=True, image=pin(out / "native.png"),
                      observation=pin(out / "native.renderer.json"))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "run.json", result)
    print(name + ": " + result["status"], flush=True)
    require(result["status"] == "COLLECTED", f"{name}: {result.get('error')}")
    return result


def patch_pixels(rgb, sample, extent=fixture.EXTENT):
    cx, cy = (int(round(value)) for value in sample["pixel"])
    half = sample["half_extent"]
    require(0 <= cx - half <= cx + half < extent[0]
            and 0 <= cy - half <= cy + half < extent[1], "Projected witness lies outside native image")
    return [tuple(rgb[(y * extent[0] + x) * 3:(y * extent[0] + x) * 3 + 3])
            for y in range(cy - half, cy + half + 1) for x in range(cx - half, cx + half + 1)]


def delta(off, on, sample):
    a, b = patch_pixels(off, sample), patch_pixels(on, sample)
    return {"red_loss": sum(x[0] - y[0] for x, y in zip(a, b)) / len(a),
        "green_max_error": max(abs(x[1] - y[1]) for x, y in zip(a, b)),
        "blue_max_error": max(abs(x[2] - y[2]) for x, y in zip(a, b)),
        "red_max_error": max(abs(x[0] - y[0]) for x, y in zip(a, b)),
        "off_mean_rgb": [sum(x[c] for x in a) / len(a) for c in range(3)],
        "on_mean_rgb": [sum(x[c] for x in b) / len(b) for c in range(3)]}


def assess_pair(off, on, *, variant="base", solid=False):
    values = {label: delta(off, on, sample) for label, sample in fixture.witnesses(variant).items()}
    for label, value in values.items():
        require(value["off_mean_rgb"][1] >= 4 and value["off_mean_rgb"][2] >= 4,
                "Ambient/independent blue control is absent at " + label)
        require(value["green_max_error"] <= MAX_UNAFFECTED_ERROR
                and value["blue_max_error"] <= MAX_UNAFFECTED_ERROR,
                "Actor shadow attenuated ambient/independent blue light at " + label)
        blocked = label.endswith("opaque") or (solid and label.endswith(("hole", "notch")))
        if variant in ("flip", "animated"):
            blocked = blocked or label.endswith("notch")
        if label.startswith("sprite_"):
            blocked = False
        if blocked:
            require(value["red_loss"] >= MIN_RED_LOSS,
                    "Actual red-light shadow missing from " + label)
        else:
            require(value["red_max_error"] <= MAX_UNAFFECTED_ERROR,
                    "Source-alpha hole or visible sprite incorrectly self-darkened at " + label)
    return values


def assess(root):
    def pixels(material, variant, enabled):
        extent, rgb = images.decode(root / case_name(material, variant, enabled) / "native.png")
        require(extent == fixture.EXTENT, "Comparison extent mismatch")
        return rgb
    results, errors = {}, {}
    for material, variant in (("normal", "base"), ("specular", "base"), ("pbr", "base"),
                              ("normal", "solid"), ("normal", "flip"),
                              ("normal", "orbit"), ("normal", "animated")):
        name = material + "-" + variant
        control_variant = "base" if variant == "solid" else variant
        off, on = pixels(material, control_variant, False), pixels(material, variant, True)
        # Keep every planned capture and each pair's measured RGB even when an
        # earlier pair fails. This changes diagnostic coverage, never the gate.
        values = {label: delta(off, on, sample)
                  for label, sample in fixture.witnesses(variant).items()}
        report = {"status": "FAIL", "witnesses": values}
        try:
            assess_pair(off, on, variant=variant, solid=variant == "solid")
            report["status"] = "PASS"
        except ValueError as error:
            errors[name] = report["error"] = str(error)
        results[name] = values
        write_json(root / case_name(material, variant, True) / "image-acceptance.json", report)
    invisible_off, invisible_on = pixels("normal", "invisible", False), pixels("normal", "invisible", True)
    identical = invisible_off == invisible_on
    if not identical:
        errors["normal-invisible"] = "Invisible actor fallback changed actual native image"
    results["invisible_off_on_identical"] = identical
    return {"status": "FAIL" if errors else "PASS", "errors": errors, "witnesses": results,
        "scope": ["normal/specular/PBR source-specific dynamic-light attenuation", "real floor and wall fragments",
            "transparent source holes and asymmetric flip", "stationary light/actor under changed camera",
            "actual changed animation frame and invalidation of source-alpha selection",
            "independent blue light and green ambient preserved", "visible sprite self-shadow negative",
            "invisible actor fallback", "actual Vulkan screenshots and bounded source upload state"],
        "not_qualified": ["physical GPU performance", "all maps", "portal recursion", "soft penumbra", "owner visual acceptance"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--iwad-license", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--allow-modified-dev", action="store_true", help="Local diagnosis only; never awards clean-build qualification")
    args = parser.parse_args(argv)
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None, "An exact source SHA is required")
    require(1 <= args.timeout <= 600, "Per-process timeout is out of bounds")
    root = run.fresh_directory(args.out)
    result = {"schema": "shadow002-native-qualification/v1", "status": "FAIL",
        "expected_commit": args.expected_commit, "started_utc": run.utc(),
        "native_runs_attempted": 0, "automatic_retries": 0, "captures": [],
        "physical_gpu_qualified": False, "owner_visual_acceptance": False}
    try:
        result["host"] = native_ci.preflight(args, root)
        version = subprocess.run([str(args.exe.resolve(strict=True)), "--version"],
            capture_output=True, timeout=30, check=False)
        (root / "version.txt").write_bytes(version.stdout)
        require(version.returncode == 0, "Native --version failed")
        commit, tree = run.version_identity(version.stdout)
        require(commit == args.expected_commit and (args.allow_modified_dev or tree == "clean"),
                "Executable is not the requested clean source")
        (root / "content").mkdir()
        iwad = root / "content" / args.iwad.name
        shutil.copyfile(args.iwad, iwad)
        for case in CASES:
            result["native_runs_attempted"] += 1
            row = capture(args, root, iwad, case)
            result["captures"].append({"name": row["name"], "receipt": pin(root / row["name"] / "run.json")})
        result["image_acceptance"] = assess(root)
        require(result["image_acceptance"]["status"] == "PASS",
                "Native image controls failed: " + json.dumps(result["image_acceptance"]["errors"], sort_keys=True))
        result["status"] = "DIAGNOSTIC_PASS" if args.allow_modified_dev else "PASS"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(root / "qualification.json", result)
    print(json.dumps({key: result.get(key) for key in ("status", "native_runs_attempted", "error")}, sort_keys=True))
    return 0 if result["status"] in ("PASS", "DIAGNOSTIC_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
