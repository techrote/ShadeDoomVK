#!/usr/bin/env python3
"""One bounded two-process hosted-software sunlight actor acceptance.

Real native work is run once per capture with no retries, on an explicitly
isolated GitHub-hosted Linux llvmpipe runner. This is a focused software gate,
not physical-GPU acceptance.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

try:
    from . import native_ci, run
    from .common import pin, read_json, require, write_json
except ImportError:
    import native_ci, run
    from common import pin, read_json, require, write_json


def _software_host_contract():
    require(sys.platform == "linux" and os.environ.get("GITHUB_ACTIONS") == "true",
            "Focused native acceptance must run on hosted Linux Actions")
    require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Focused native acceptance requires a GitHub-hosted Linux runner")
    allowed_cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    require(type(allowed_cpus) is int and allowed_cpus > 0,
            "Focused native acceptance could not determine an allowed CPU set")
    names = ("VK_DRIVER_FILES", "VK_ICD_FILENAMES")
    selected = []
    for name in names:
        requested = os.environ.get(name, "")
        require(requested and len(requested.split(os.pathsep)) == 1,
                "Exactly one software ICD must be selected by " + name)
        selected.append(Path(requested).resolve(strict=True))
    require(selected[0] == selected[1] and
            re.fullmatch(r"lvp_icd(?:\.[A-Za-z0-9_-]+)?\.json", selected[0].name) is not None,
            "GPU Vulkan ICD is forbidden for sun qualification")
    manifest = read_json(selected[0], maximum=65536)
    library = manifest.get("ICD", {}).get("library_path")
    require(isinstance(library, str) and re.fullmatch(r"libvulkan_lvp\.so(?:\.[0-9]+)*", Path(library).name),
            "ICD must link to lavapipe, not a physical driver")
    overrides = {k: v for k, v in os.environ.items() if v and
                 ((k.startswith("VK_") and k not in names) or k in
                  ("MESA_LOADER_DRIVER_OVERRIDE", "MESA_VK_DEVICE_SELECT",
                   "MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE", "DRI_PRIME"))}
    require(not overrides, "Unexpected Vulkan device/layer/driver override")
    return {"schema":"sdvk010-sun-host/v1","runner":os.environ.get("RUNNER_NAME"),
            "allowed_cpus":allowed_cpus,"icd":pin(selected[0]),
            "device":"one software llvmpipe CPU","physical_gpu":False,
            "request":"diagnostic-only; no physical performance claim"}


def software_host_guard(out):
    """Qualify one isolated software device and retain every discovery outcome."""
    evidence = run.fresh_directory(Path(out) / "software-host")
    stdout = evidence / "vulkaninfo-summary.txt"
    stderr = evidence / "vulkaninfo-summary.stderr.txt"
    command = {"argv": ["vulkaninfo", "--summary"], "attempted": False,
               "returncode": None, "timeout_seconds": 30, "outcome": "not-attempted"}
    discovery = {"schema": "sdvk010-software-host-discovery/v1", "status": "FAIL",
                 "started_utc": run.utc(), "command": command, "automatic_retries": 0,
                 "presentation_surface": False}
    try:
        # Direct file streams preserve partial output if the one attempt times
        # out or fails. A rejected host contract leaves empty, unattempted logs.
        with stdout.open("xb") as output, stderr.open("xb") as errors:
            host = _software_host_contract()
            discovery["host"] = host
            environment = native_ci.device_feature_probe_environment()
            discovery["environment"] = {
                key: environment[key] for key in native_ci.ENVIRONMENT if key in environment}
            command.update(attempted=True, started_utc=run.utc())
            try:
                vk = subprocess.run(command["argv"], stdout=output, stderr=errors,
                                    env=environment, check=False, timeout=30)
                command.update(returncode=vk.returncode, outcome="completed")
            except subprocess.TimeoutExpired:
                command["outcome"] = "timed-out"
                raise
            except (OSError, subprocess.SubprocessError):
                command["outcome"] = "launch-error"
                raise
            finally:
                command["finished_utc"] = run.utc()
        require(vk.returncode == 0,
                "Vulkan device discovery exited with return code " + str(vk.returncode) +
                "; inspect software-host/vulkaninfo-summary.stderr.txt")
        summary = stdout.read_text(encoding="utf-8")
        discovery["identity"] = {
            "device_names": native_ci.fields(summary, "deviceName"),
            "device_types": native_ci.fields(summary, "deviceType"),
        }
        require(len(re.findall(r"deviceName\s*=\s*llvmpipe", summary)) == 1 and
                len(re.findall(r"deviceType\s*=\s*PHYSICAL_DEVICE_TYPE_CPU", summary)) == 1 and
                len(re.findall(r"deviceName\s*=", summary)) == 1,
                "Vulkan device discovery did not report exactly one CPU llvmpipe device; "
                "inspect software-host/vulkaninfo-summary.txt")
        discovery["status"] = "PASS"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        discovery.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        discovery.update(finished_utc=run.utc(), stdout=pin(stdout, relative_to=evidence),
                         stderr=pin(stderr, relative_to=evidence))
        write_json(evidence / "discovery.json", discovery)
    return {**host, "discovery": pin(evidence / "discovery.json", relative_to=out)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--iwad",type=Path,required=True)
    parser.add_argument("--prepared",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--expected-commit",required=True)
    args=parser.parse_args(argv)
    root=run.fresh_directory(args.out)
    result={"schema":"sdvk010-sun-native-qualification/v1","status":"FAIL",
            "started_utc":run.utc(),"expected_commit":args.expected_commit,
            "native_runs_attempted":0,"automatic_retries":0,
            "physical_stop_active":True,"physical_gpu_qualified":False,
            "full_integrated_sdvk010_accepted":False,"portal_acceptance_pending":True}
    try:
        require(re.fullmatch(r"[a-f0-9]{40}", args.expected_commit) is not None,
                "Expected exact built commit is malformed")
        result["host"]=software_host_guard(root)
        captures=[]
        for index in (1,2):
            capture_args=argparse.Namespace(
                exe=args.exe,iwad=args.iwad,prepared=args.prepared,
                out=root / ("sun-capture-%d" % index),
                scene="sun-actor-occlusion",mode="state",frames=1,warmup=240,
                timeout=600,gpu=False,include_stress=True,image_policy="exact",
                extent=None,collision_snapshot=False,publication_witness=False,
                expected_commit=args.expected_commit,require_clean=True)
            result["native_runs_attempted"]=index
            capture=run.capture(capture_args)
            captures.append(capture_args.out)
            require(capture.get("sun_actor_image", {}).get("status") == "PASS",
                    "Actor world occlusion did not pass actual screenshot discrimination")
        comparison=run.compare_runs(*captures)
        write_json(root / "comparison.json",comparison)
        require(comparison["status"] == "PASS" and comparison["state_equal"] is True
                and comparison["image"]["changed_pixels"] == 0,
                "Independent clean-state actor-sun images/state were not repeatable")
        result.update(status="PASS",comparison=pin(root / "comparison.json",relative_to=root),
                      native_captures=[pin(path/"run.json",relative_to=root) for path in captures],
                      qualification_scope="software world-occluded versus sunlit PBR actor; no portal/physical acceptance")
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        result["error"]=str(error)
    finally:
        result["finished_utc"]=run.utc()
        write_json(root / "qualification.json",result)
    print(json.dumps({k:result.get(k) for k in ("status","native_runs_attempted","error")},sort_keys=True))
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
