#!/usr/bin/env python3
"""CFX-002 bounded run manifest and capture launcher. Prepare is the default."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
KNOWN_CRASH = ("dbp37", "sunlust", "dbp50")
MODES = ("off", "capture", "core", "sync", "gpu-assisted")
VALIDATION_SETTINGS = {
    "core": ("validate_core = true", "validate_sync = false", "gpuav_enable = false"),
    "sync": ("validate_core = false", "validate_sync = true", "gpuav_enable = false",
             "syncval_submit_time_validation = true"),
    "gpu-assisted": ("validate_core = false", "validate_sync = false", "gpuav_enable = true",
                     "gpuav_shader_instrumentation = true",
                     "gpuav_debug_print_instrumentation_info = true"),
}


def digest(path):
    if not path or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path):
    return {"path": str(path.resolve()), "sha256": digest(path), "size": path.stat().st_size if path.is_file() else None}


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return p.stdout.strip().decode("utf-8", "replace") if p.returncode == 0 else None


def scan_failure(trace, stdout, stderr, timed_out, returncode):
    data = ""
    for p in (trace, stdout, stderr):
        if p.is_file():
            data += p.read_text(errors="replace")[-2_000_000:]
    if "VK_ERROR_DEVICE_LOST" in data or re.search(r"vk-return[^\n]*\t-4(?:\n|$)", data):
        return "VK_ERROR_DEVICE_LOST"
    if "vk-error" in data:
        return "other Vulkan error"
    if timed_out:
        return "timeout; no Vulkan return proven"
    if returncode and (returncode & 0xC0000000) == 0xC0000000:
        return "application CPU exception status; inspect Windows Application event"
    if returncode and returncode != 0:
        return "nonzero application exit; inspect stdout/stderr"
    return None


def capture_dump(pid, target):
    if platform.system() != "Windows":
        return {"status": "unavailable", "reason": "Windows comsvcs only"}
    cmd = ["rundll32.exe", "C:\\Windows\\System32\\comsvcs.dll,", "MiniDump",
           str(pid), str(target), "full"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        readable = False
        if target.is_file() and target.stat().st_size:
            # comsvcs writes a restrictive ACL on this machine. The file owner
            # can grant their own token read access without changing system policy.
            user = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"],
                                           text=True)
            sid = next(csv.reader([user.strip()]))[1]
            acl = subprocess.run(["icacls", str(target), "/grant", "*" + sid + ":(R)"],
                                 capture_output=True, text=True)
            readable = acl.returncode == 0
        return {"status": "captured" if readable and result.returncode == 0 else
                "partial" if readable else "failed",
                "command": cmd, "exit_code": result.returncode,
                "readable": readable, "stderr": result.stderr[-1000:], "path": str(target)}
    except subprocess.TimeoutExpired:
        return {"status": "dump timeout", "command": cmd, "path": str(target)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=pathlib.Path, required=True)
    ap.add_argument("--run-root", type=pathlib.Path, required=True)
    ap.add_argument("--iwad", type=pathlib.Path, required=True)
    ap.add_argument("--pwad", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--addon", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--config", type=pathlib.Path)
    ap.add_argument("--pipeline-cache", type=pathlib.Path)
    ap.add_argument("--shader-cache", type=pathlib.Path)
    ap.add_argument("--map", required=True)
    ap.add_argument("--skill")
    ap.add_argument("--seed")
    ap.add_argument("--camera")
    ap.add_argument("--resolution")
    ap.add_argument("--cap-vsync-msaa")
    ap.add_argument("--mode", choices=MODES, default="capture")
    ap.add_argument("--validation-layer-dir", type=pathlib.Path,
                    help="directory containing local Khronos validation JSON and DLL; process-scoped")
    ap.add_argument("--isolate-workdir", action="store_true",
                    help="run from a per-run work directory for screenshot/state fixtures")
    ap.add_argument("--pre-arg", action="append", default=[])
    ap.add_argument("--arg", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--skip-dump-on-timeout", action="store_true",
                    help="safe smoke only; never use for CFX-003")
    ap.add_argument("--launch", action="store_true", help="otherwise only prepare the manifest")
    ap.add_argument("--approved-cfx003", action="store_true",
                    help="reserved for a separately reviewed CFX-003 primary run")
    ap.add_argument("--approved-cfx005", action="store_true",
                    help="deliberate CFX-005 replay under a separate lane plan")
    ap.add_argument("--cfx005-lane-plan", type=pathlib.Path,
                    help="immutable CFX-005 per-GPU lane-opening JSON")
    args = ap.parse_args()
    if args.approved_cfx003 and args.approved_cfx005:
        ap.error("choose one crash campaign approval scope")
    if args.cfx005_lane_plan and not args.approved_cfx005:
        ap.error("--cfx005-lane-plan requires --approved-cfx005")
    if args.approved_cfx005:
        if not args.cfx005_lane_plan or not args.cfx005_lane_plan.is_file():
            ap.error("CFX-005 requires an existing lane-opening JSON")
        try:
            lane_plan = json.loads(args.cfx005_lane_plan.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            ap.error(f"invalid CFX-005 lane-opening JSON: {exc}")
        if (not isinstance(lane_plan, dict) or
                lane_plan.get("schema") != "cfx-005-lane-v1" or
                lane_plan.get("issue") != 92 or lane_plan.get("status") != "OPEN"):
            ap.error("CFX-005 lane-opening JSON must name open issue #92")
        if not args.run_root.resolve().is_relative_to(args.cfx005_lane_plan.parent.resolve()):
            ap.error("CFX-005 run root must be inside its lane directory")
    files = [args.exe, args.iwad, *args.pwad, *args.addon]
    if args.cfx005_lane_plan:
        files.append(args.cfx005_lane_plan)
    if args.config:
        files.append(args.config)
    for path in files:
        if not path.is_file():
            ap.error(f"missing input: {path}")
    if any((parent / "STOP-LAUNCHES.txt").exists() for p in files for parent in (p.parent, *p.parents)):
        ap.error("STOP-LAUNCHES.txt guard applies to an input")
    risky = args.map.upper() in ("MAP01", "MAP24", "MAP08") and any(
        key in p.name.lower() for p in args.pwad + args.addon for key in KNOWN_CRASH)
    crash_approved = args.approved_cfx003 or args.approved_cfx005
    campaign = "CFX-005" if args.approved_cfx005 else "CFX-003"
    if args.launch and risky and not crash_approved:
        ap.error("known crash route requires a separately approved CFX-003 or CFX-005 campaign")
    if crash_approved and args.skip_dump_on_timeout:
        ap.error(f"{campaign} requires a pre-kill process dump")
    if crash_approved and (not args.pipeline_cache or not args.shader_cache):
        ap.error(f"{campaign} requires explicit pipeline and shader cache paths")
    if crash_approved and (args.mode != "capture" or not args.config or args.timeout > 60):
        ap.error(f"{campaign} requires capture mode, an exact config, and a watchdog of at most 60 seconds")
    probe_env = os.environ.copy()
    layer_dir = args.validation_layer_dir.resolve() if args.validation_layer_dir else None
    if layer_dir:
        manifest_file = layer_dir / "VkLayer_khronos_validation.json"
        library_file = layer_dir / "VkLayer_khronos_validation.dll"
        if not manifest_file.is_file() or not library_file.is_file():
            ap.error("validation layer directory must contain Khronos JSON and DLL")
        probe_env["VK_ADD_LAYER_PATH"] = str(layer_dir)
    if args.launch and args.mode in VALIDATION_SETTINGS:
        probe = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True,
                               env=probe_env)
        if "VK_LAYER_KHRONOS_validation" not in probe.stdout:
            ap.error("VK_LAYER_KHRONOS_validation unavailable in this process layer path")

    run_id = "cfx-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    run_dir = args.run_root.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    work_dir = run_dir / "work" if args.isolate_workdir else args.exe.parent.resolve()
    if args.isolate_workdir:
        work_dir.mkdir()
    for source, name in ((args.config, "config-before.ini"),
                         (args.pipeline_cache, "pipelinecache-before.zdpc"),
                         (args.shader_cache, "shadercache-before.zdsc")):
        if source and source.is_file():
            shutil.copy2(source, run_dir / name)
    trace = run_dir / "timeline.tsv"
    out = run_dir / "stdout.log"
    err = run_dir / "stderr.log"
    fault = run_dir / "device-fault.bin"
    dump = run_dir / "process.dmp"
    runtime = []
    for p in sorted(args.exe.parent.iterdir()):
        if p.is_file() and p.suffix.lower() in (".pk3", ".dll", ".pdb"):
            runtime.append(identity(p))
    source_sha = git("rev-parse", "HEAD")
    patch = subprocess.run(["git", "diff", "HEAD", "--binary"], cwd=ROOT, capture_output=True).stdout
    untracked = []
    for relative in (git("ls-files", "--others", "--exclude-standard") or "").splitlines():
        if relative.startswith(("build-relwithdebinfo/", "tools/__pycache__/")):
            continue
        path = ROOT / relative
        if path.is_file():
            untracked.append({"path": relative, "sha256": digest(path)})
    patch_identity = patch + json.dumps(untracked, sort_keys=True).encode()
    patch_sha = hashlib.sha256(patch_identity).hexdigest() if patch_identity else None
    status = git("status", "--porcelain")
    command = [str(args.exe.resolve()), *args.pre_arg, "-iwad", str(args.iwad.resolve())]
    if args.pwad or args.addon:
        command += ["-file", *(str(p.resolve()) for p in args.pwad + args.addon)]
    if args.config:
        command += ["-config", str(args.config.resolve())]
    if args.seed:
        command += ["-rngseed", args.seed]
    if args.skill:
        command += ["+skill", args.skill]
    command += ["+map", args.map, *args.arg]
    local = dt.datetime.now().astimezone().isoformat()
    manifest = {
        "schema": "cfx-002-run-v1", "incident_id": None, "run_id": run_id,
        "status": "PREPARED", "observed_at_local": local,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {"git_sha": source_sha, "dirty_status": status,
                   "local_patch_sha256": patch_sha, "untracked_files": untracked,
                   "exe": identity(args.exe),
                   "pdb": identity(args.exe.with_suffix(".pdb")),
                   "runtime_bundle": runtime},
        "content": ([{"role": "IWAD", **identity(args.iwad)}] +
                    [{"role": "PWAD", **identity(p)} for p in args.pwad] +
                    [{"role": "addon", **identity(p)} for p in args.addon]),
        "run": {"map": args.map, "skill_actual": args.skill, "seed": args.seed,
                "camera_or_warp": args.camera, "arguments": command,
                "config_sha256": digest(args.config), "resolution": args.resolution,
                "fps_vsync_msaa": args.cap_vsync_msaa,
                "pipeline_cache_identity": identity(args.pipeline_cache) if args.pipeline_cache else None,
                "shader_cache_identity": identity(args.shader_cache) if args.shader_cache else None,
                "working_directory": str(work_dir),
                "crash_campaign_approval": campaign if crash_approved else None,
                "cfx005_lane_plan": identity(args.cfx005_lane_plan) if args.cfx005_lane_plan else None},
        "environment": {"os": platform.platform(), "gpu": None, "driver": None,
                        "vulkan_runtime": None, "active_vulkan_layers": None,
                        "validation_or_capture_mode": args.mode,
                        "validation_layer_dir": str(layer_dir) if layer_dir else None,
                        "validation_layer_json": identity(layer_dir / "VkLayer_khronos_validation.json") if layer_dir else None,
                        "validation_layer_dll": identity(layer_dir / "VkLayer_khronos_validation.dll") if layer_dir else None,
                        "capability_state": None},
        "failure": {"application_observation": None, "watchdog_action": None,
                    "last_known_cpu_stage": None, "last_known_gpu_stage": None},
        "exit_status": None, "artifacts": ["manifest.json", "timeline.tsv",
                                         "stdout.log", "stderr.log", "loader-layers.log",
                                         "vulkaninfo-summary.txt", "system-events.xml",
                                         "application-events.xml", "config-before.ini",
                                         "pipelinecache-before.zdpc", "shadercache-before.zdsc",
                                         "device-fault.bin", "process.dmp"],
        "unknowns": ["actual loaded layers and enabled device features require launch evidence"]
    }
    probe = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True,
                           env=probe_env)
    (run_dir / "vulkaninfo-summary.txt").write_text(probe.stdout + probe.stderr)
    manifest["environment"]["vulkan_runtime"] = next((l.strip() for l in probe.stdout.splitlines()
                                                      if "Vulkan Instance Version" in l), None)
    manifest["environment"]["gpu"] = next((l.strip() for l in probe.stdout.splitlines()
                                           if "deviceName" in l), None)
    manifest["environment"]["driver"] = next((l.strip() for l in probe.stdout.splitlines()
                                              if "driverInfo" in l), None)
    if args.mode in VALIDATION_SETTINGS:
        settings = run_dir / "vk_layer_settings.txt"
        settings.write_text("\n".join("khronos_validation." + item for item in
                                      VALIDATION_SETTINGS[args.mode]) +
                            "\nkhronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG\n" +
                            "khronos_validation.report_flags = error;warn;info\n" +
                            "khronos_validation.log_filename = " +
                            str(run_dir / "validation.log").replace("\\", "/") + "\n")
        manifest["artifacts"].extend((settings.name, "validation.log"))
    manifest_path = run_dir / "manifest.json"
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    save()  # durable before any application launch
    print(run_dir)
    if not args.launch:
        return 0
    env = probe_env.copy()
    if args.mode != "off":
        env.update(CFX_RUN_ID=run_id, CFX_TRACE_FILE=str(trace), CFX_FAULT_BIN=str(fault),
                   VK_LOADER_DEBUG="layer")
    if args.mode in VALIDATION_SETTINGS:
        env["VK_INSTANCE_LAYERS"] = "VK_LAYER_KHRONOS_validation"
    if args.mode in VALIDATION_SETTINGS:
        env["VK_LAYER_SETTINGS_PATH"] = str(run_dir / "vk_layer_settings.txt")
    timed_out = False
    with out.open("wb") as stdout, err.open("wb") as stderr:
        proc = subprocess.Popen(command, cwd=work_dir, env=env, stdout=stdout, stderr=stderr)
        manifest["status"] = "RUNNING"
        manifest["pid"] = proc.pid
        save()
        try:
            code = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            manifest["failure"]["watchdog_action"] = (
                {"status": "skipped for safe smoke"} if args.skip_dump_on_timeout
                else capture_dump(proc.pid, dump))
            proc.kill()
            code = proc.wait(timeout=15)
    loader = err.read_text(errors="replace") if err.is_file() else ""
    console = out.read_text(errors="replace") if out.is_file() else ""
    (run_dir / "loader-layers.log").write_text("\n".join(
        line for line in loader.splitlines() if "layer" in line.lower()) + "\n")
    manifest["environment"]["active_vulkan_layers"] = [
        name for name in ("VK_LAYER_KHRONOS_validation", "VK_LAYER_OBS_HOOK",
                          "VK_LAYER_NV_optimus", "VK_LAYER_NV_present")
        if name in loader and re.search(r"(Insert|Loading|using).*" + name, loader, re.I)]
    manifest["environment"]["layer_activation_evidence"] = "loader-layers.log"
    layer_loaded = "VK_LAYER_KHRONOS_validation" in manifest["environment"]["active_vulkan_layers"]
    validation_log = (run_dir / "validation.log").read_text(errors="replace") if (run_dir / "validation.log").is_file() else ""
    enabled_modes = {
        "core": "  - Core Checks" in validation_log,
        "sync": "  - Synchronization" in validation_log,
        "gpu-assisted": "  - GPU-AV" in validation_log,
    }
    instrumented = bool(re.search(r"instrumentation count: [1-9]|instrumentation performed: true",
                                  console, re.I))
    manifest["environment"]["validation_enabled_report"] = [
        line.strip() for line in validation_log.splitlines()
        if line.startswith("  - ")]
    manifest["environment"]["gpuav_shader_instrumentation_observed"] = instrumented
    manifest["environment"]["validation_mode_verified"] = (
        True if args.mode in ("off", "capture") else
        bool(layer_loaded and enabled_modes[args.mode] and
             (args.mode != "gpu-assisted" or instrumented)))
    manifest["environment"]["validation_mode_activation_evidence"] = (
        "loader insertion plus CURRENT-VALIDATION-ENABLED report" if
        args.mode in VALIDATION_SETTINGS and layer_loaded and enabled_modes[args.mode]
        else None)
    if platform.system() == "Windows":
        for log_name, filename in (("System", "system-events.xml"),
                                   ("Application", "application-events.xml")):
            try:
                events = subprocess.run(["wevtutil", "qe", log_name, "/rd:true", "/c:100", "/f:xml"],
                                        capture_output=True, text=True, timeout=15)
                (run_dir / filename).write_text(events.stdout + events.stderr)
            except (subprocess.TimeoutExpired, OSError) as exc:
                (run_dir / filename).write_text(f"event export unavailable: {exc}\n")
    manifest["exit_status"] = code
    actual = re.search(r"^Resolution:\s*(.+)$", console, re.M)
    manifest["run"]["actual_resolution"] = actual.group(1).strip() if actual else None
    ray = re.search(r"ray-query-enabled=(yes|no)", console)
    manifest["environment"]["ray_query_enabled"] = ray.group(1) if ray else None
    manifest["failure"]["application_observation"] = (
        "controlled safe stop" if timed_out and args.skip_dump_on_timeout
        else scan_failure(trace, out, err, timed_out, code))
    manifest["failure"]["first_observed_failure"] = (
        None if timed_out and args.skip_dump_on_timeout
        else manifest["failure"]["application_observation"])
    manifest["status"] = ("SAFE_STOP" if timed_out and args.skip_dump_on_timeout
                          else "TIMEOUT" if timed_out else
                          "EXITED" if code == 0 else "FAILED")
    if trace.is_file():
        rows = [l.split("\t") for l in trace.read_text(errors="replace").splitlines()[2:]]
        manifest["environment"]["capability_state"] = [
            r[7] for r in rows if len(r) > 7 and r[6] == "capability"]
        stages = [r[5] for r in rows if len(r) > 6 and r[6] == "stage-complete"]
        manifest["failure"]["last_known_cpu_stage"] = stages[-1] if stages else None
        confirmed = [r[7] for r in rows if len(r) > 7 and r[6] == "gpu-checkpoint-confirmed"]
        manifest["failure"]["last_known_gpu_stage"] = confirmed[-1] if confirmed else None
    manifest["run"]["pipeline_cache_after"] = (
        identity(args.pipeline_cache) if args.pipeline_cache else None)
    manifest["run"]["shader_cache_after"] = (
        identity(args.shader_cache) if args.shader_cache else None)
    if args.isolate_workdir:
        manifest["artifacts"].extend(("work/levelmesh.obj", "work/levelmesh.mtl"))
    manifest["artifact_files"] = [
        {"path": str(run_dir / name), "size": (run_dir / name).stat().st_size}
        for name in manifest["artifacts"] if (run_dir / name).is_file()]
    save()
    return 0 if timed_out and args.skip_dump_on_timeout else code if code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
