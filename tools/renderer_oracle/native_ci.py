#!/usr/bin/env python3
"""Qualify authored renderer scenes on isolated software Vulkan under caller Xvfb.

Each planned process runs once. Keep the complete output, including failed runs,
copied inputs and IWAD copyright. Results make no physical GPU performance claim.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

try:
    from . import prepare, run
    from .common import pin, read_json, require, write_json
except ImportError:
    import prepare
    import run
    from common import pin, read_json, require, write_json

SCENES = ("compositing", "lights-zero", "lights-one", "lights-many",
          "lights-dense-overlap", "lights-dense-dispersed",
          "shadow-boundary", "material-stress", "sun-probes", "sprite-mirror")
SDVK009_SCALE_TIMING_SCENES = ("lights-zero", "lights-many", "lights-dense-overlap", "lights-dense-dispersed")
FEATURES = ("shaderSampledImageArrayNonUniformIndexing",
            "descriptorBindingSampledImageUpdateAfterBind", "descriptorBindingPartiallyBound",
            "descriptorBindingVariableDescriptorCount", "runtimeDescriptorArray")
ENVIRONMENT = ("DISPLAY", "WAYLAND_DISPLAY", "SDL_VIDEODRIVER", "LD_LIBRARY_PATH",
               "VK_DRIVER_FILES", "VK_ICD_FILENAMES", "VK_ADD_DRIVER_FILES",
               "VK_INSTANCE_LAYERS", "VK_LAYER_PATH", "VK_LOADER_DRIVERS_SELECT",
               "VK_LOADER_DRIVERS_DISABLE", "VK_LOADER_LAYERS_ENABLE", "VK_LOADER_LAYERS_DISABLE",
               "MESA_SHADER_CACHE_DISABLE", "MESA_SHADER_CACHE_DIR", "MESA_LOADER_DRIVER_OVERRIDE",
               "LP_NUM_THREADS", "OMP_NUM_THREADS", "XDG_RUNTIME_DIR")


def fields(text, name):
    return [value.strip() for value in re.findall(
        r"(?m)^[ \t]*" + re.escape(name) + r"[ \t]*=[ \t]*([^\r\n]+)$", text)]


def device_evidence(summary, full):
    """Require one actual CPU llvmpipe device and every required feature bit."""
    for text in (summary, full):
        require(re.findall(r"(?m)^GPU(\d+):\s*$", text) == ["0"],
                "Software qualification requires exactly one enumerated Vulkan device")
        require(fields(text, "deviceType") == ["PHYSICAL_DEVICE_TYPE_CPU"], "Vulkan device is not CPU")
        require(fields(text, "driverName") == ["llvmpipe"], "Vulkan driver is not llvmpipe")
        require(fields(text, "driverID") == ["DRIVER_ID_MESA_LLVMPIPE"], "Unexpected Vulkan driver ID")
    identity = {}
    for name in ("deviceName", "driverName", "driverInfo", "driverID", "apiVersion", "driverVersion"):
        values = fields(summary, name)
        require(len(values) == 1, "Missing/ambiguous Vulkan property: " + name)
        identity[name] = values[0]
    require(identity["deviceName"].startswith("llvmpipe (") and
            fields(full, "deviceName") == [identity["deviceName"]], "llvmpipe device identities differ")
    for name in FEATURES:
        values = fields(full, name)
        require(values and all(value == "true" for value in values), "Required Vulkan feature unavailable: " + name)
    return {"device": identity, "required_features": dict.fromkeys(FEATURES, True)}


def command(out, name, argv):
    result = {"argv": argv, "returncode": None, "started_utc": run.utc()}
    stdout, stderr = out / (name + ".txt"), out / (name + ".stderr.txt")
    with stdout.open("xb") as output, stderr.open("xb") as errors:
        try:
            result["returncode"] = subprocess.run(argv, stdout=output, stderr=errors,
                                                  timeout=60, check=False).returncode
        except (OSError, subprocess.SubprocessError) as error:
            result["error"] = str(error)
    result.update(stdout=pin(stdout, relative_to=out), stderr=pin(stderr, relative_to=out))
    return result


def preflight(args, out):
    provenance = out / "provenance"
    provenance.mkdir()
    data = {"host": run.host_profile(), "environment": {k: os.environ[k] for k in ENVIRONMENT if k in os.environ},
            "started_utc": run.utc(), "software_vulkan_only": True}
    try:
        data["executable"], data["iwad"] = pin(args.exe), pin(args.iwad)
        license_path = args.iwad_license
        if license_path is None:
            installed = [Path("/usr/share/games/doom") / name for name in ("freedoom1.wad", "freedoom2.wad")]
            require(any(path.is_file() and pin(path)["sha256"] == data["iwad"]["sha256"] for path in installed),
                    "Supply --iwad-license when IWAD bytes differ from the installed Freedoom package")
            license_path = Path("/usr/share/doc/freedoom/copyright")
        data["iwad_license_source"] = pin(license_path)
        shutil.copyfile(license_path, provenance / "iwad-copyright.txt")
        data["iwad_license"] = pin(provenance / "iwad-copyright.txt", relative_to=out)
        if Path("/etc/os-release").is_file():
            shutil.copyfile("/etc/os-release", provenance / "os-release.txt")
        data["commands"] = {
            "packages": command(provenance, "packages", ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"]),
            "vulkan_summary": command(provenance, "vulkaninfo-summary", ["vulkaninfo", "--summary"]),
            "vulkan_full": command(provenance, "vulkaninfo-full", ["vulkaninfo"])}
        manifests = []
        for key in ("VK_DRIVER_FILES", "VK_ICD_FILENAMES"):
            if os.environ.get(key):
                paths = os.environ[key].split(os.pathsep)
                require(len(paths) == 1 and paths[0], "Isolate exactly one llvmpipe ICD manifest with " + key)
                manifests.append(Path(paths[0]).resolve(strict=True))
        require(manifests and len(set(manifests)) == 1, "Set VK_DRIVER_FILES/VK_ICD_FILENAMES to one identical isolated ICD")
        require(not os.environ.get("VK_ADD_DRIVER_FILES"), "Additional Vulkan driver manifests are not isolated")
        data["icd"] = pin(manifests[0])
        shutil.copyfile(manifests[0], provenance / "icd.json")
        require("lvp" in str(read_json(manifests[0]).get("ICD", {}).get("library_path", "")), "ICD is not lavapipe")
        require(all(value["returncode"] == 0 for value in data["commands"].values()),
                "Package/Vulkan provenance command failed; inspect retained stdout and stderr")
        data.update(device_evidence((provenance / "vulkaninfo-summary.txt").read_text(),
                                    (provenance / "vulkaninfo-full.txt").read_text()))
        require(os.environ.get("DISPLAY"), "Caller must provide an active Xvfb DISPLAY")
    finally:
        write_json(provenance / "host.json", data)
    return {"status": "PASS", "provenance": pin(provenance / "host.json", relative_to=out)}


def attempt(out, name, operation, accepted=("PASS",)):
    print(name + ": starting", flush=True)
    result = {"name": name, "status": "FAIL", "started_utc": run.utc()}
    try:
        result["result"] = operation()
        require(result["result"].get("status") in accepted, "Operation did not meet its required status")
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = str(error)
        trace = out / "steps" / (name + ".traceback.txt")
        trace.parent.mkdir(exist_ok=True)
        with trace.open("x", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        result["traceback"] = pin(trace, relative_to=out)
    result["finished_utc"] = run.utc()
    receipt = out / "steps" / (name + ".json")
    write_json(receipt, result)
    print(name + ": " + result["status"] + ("; " + result["error"] if "error" in result else ""), flush=True)
    return {"name": name, "status": result["status"], "receipt": pin(receipt, relative_to=out)}


def timing_summary(out, paths, *, filename, minimum_samples, requirement):
    summary = run.summarize_runs(paths, minimum_samples=minimum_samples)
    write_json(out / filename, summary)
    gpu = [bool(item["summary"]["gpu_groups"]) for item in summary["runs"]]
    return {"status": "PASS" if all(gpu) and summary["repeatability_evidence"] else "FAIL",
            "summary": pin(out / filename, relative_to=out), "numeric_gpu_groups_per_process": gpu,
            "requirement": requirement}


def baseline(out, paths):
    result = timing_summary(out, paths, filename="baseline.json", minimum_samples=120,
                            requirement="Three independent 120-frame CPU distributions with actual resolved GPU groups")
    result["baseline"] = result.pop("summary")
    return result


def dense_baseline(out, scene, paths):
    return timing_summary(out, paths, filename=scene + "-timing.json", minimum_samples=30,
                          requirement=("Three independent 30-frame software-Vulkan descriptive distributions for "
                                       + scene + "; not physical-GPU performance acceptance"))


def qualify(args):
    scenes = list(SCENES) if args.full else args.scene or ["compositing", "lights-one"]
    require(len(set(scenes)) == len(scenes) and all(scene in SCENES for scene in scenes), "Select unique authored scene IDs")
    out = run.fresh_directory(args.out)
    steps = []
    result = {"schema": "sdvk-renderer-native-ci/v1", "status": "FAIL", "started_utc": run.utc(),
              "scenes": scenes, "state_processes_per_scene": 2, "timing_scene": "lights-one",
              "timing_processes": 3, "timing_frames_per_process": 120,
              "sdvk009_dense_timing_scenes": [scene for scene in SDVK009_DENSE_SCENES if scene in scenes],
              "sdvk009_dense_timing_processes_per_scene": 3, "sdvk009_dense_timing_frames_per_process": 30,
              "automatic_retries": 0,
              "image_policy": "exact-rgb8", "steps": steps, "physical_gpu_qualified": False,
              "performance_accepted": False, "scope": "Same-build software Vulkan state/images and descriptive timing only"}
    try:
        steps.append(attempt(out, "preflight", lambda: preflight(args, out)))
        if steps[-1]["status"] == "PASS":
            prepared = out / "prepared"
            selected = list(dict.fromkeys(scenes + ["lights-one"]))
            steps.append(attempt(out, "prepare", lambda: prepare.prepare(prepared, selected), ("prepared_only",)))
            if steps[-1]["status"] == "PASS":
                def capture(scene, mode, destination, *, frames=None, warmup=None):
                    if frames is None:
                        frames = 1 if mode == "state" else 120
                    return run.capture(argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared,
                        out=destination, scene=scene, mode=mode, frames=frames, warmup=warmup,
                        timeout=600, gpu=mode == "timing", include_stress=True, image_policy="exact"))
                for scene in scenes:
                    paths = [out / "state" / scene / str(i) for i in (1, 2)]
                    for i, path in enumerate(paths, 1):
                        steps.append(attempt(out, scene + "-state-" + str(i),
                                             lambda p=path, s=scene: capture(s, "state", p), ("COLLECTED",)))
                    steps.append(attempt(out, scene + "-compare", lambda p=paths: run.compare_runs(*p)))
                paths = [out / "timing" / ("lights-one-" + str(i)) for i in (1, 2, 3)]
                for i, path in enumerate(paths, 1):
                    steps.append(attempt(out, "lights-one-timing-" + str(i),
                                         lambda p=path: capture("lights-one", "timing", p), ("COLLECTED",)))
                steps.append(attempt(out, "baseline", lambda: baseline(out, paths)))
                for scene in SDVK009_DENSE_SCENES:
                    if scene not in scenes:
                        continue
                    dense_paths = [out / "timing" / (scene + "-" + str(i)) for i in (1, 2, 3)]
                    for i, path in enumerate(dense_paths, 1):
                        steps.append(attempt(out, scene + "-timing-" + str(i),
                                             lambda p=path, s=scene: capture(s, "timing", p, frames=30, warmup=20),
                                             ("COLLECTED",)))
                    steps.append(attempt(out, scene + "-timing-summary",
                                         lambda p=dense_paths, s=scene: dense_baseline(out, s, p)))
        result["status"] = "PASS" if steps and all(step["status"] == "PASS" for step in steps) else "FAIL"
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "native-ci.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("exe", "iwad", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--iwad-license", type=Path, help="Copyright/license to retain; defaults to matching installed Freedoom copyright")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--scene", action="append", choices=SCENES, help="Repeat for authored scenes; default: compositing and lights-one")
    selection.add_argument("--full", action="store_true", help="All ten authored scenes, including SDVK-009 dense-light stress; excludes retained PF recipes")
    args = parser.parse_args(argv)
    try:
        result = qualify(args)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(result["status"] + ": " + str(args.out / "native-ci.json"), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
