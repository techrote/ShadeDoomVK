#!/usr/bin/env python3
"""Diagnostic-only SDVK-009 hosted software timeout discriminator.

This harness preserves the frozen PR #146 uninstrumented shadow-control workload.
It cannot grant qualification acceptance. If the native process is still alive
at the fixed 600-second deadline, failure is durably recorded first; only then
are bounded host-side /proc and optional gdb diagnostics collected before the
process is terminated. No renderer retry is performed.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

try:
    from . import native_ci, prepare, run, sdvk009_publication as publication
    from .common import EvidenceError, pin, read_json, require, write_json
except ImportError:
    import native_ci
    import prepare
    import run
    import sdvk009_publication as publication
    from common import EvidenceError, pin, read_json, require, write_json

SCHEMA = "sdvk009-timeout-discriminator/v1"
REQUEST_SCHEMA = "sdvk009-timeout-discriminator-request/v1"
RENDERER_COMMIT = "14c2ecefad41374d39a8fb9d369d510251b9dd6e"
DEADLINE_SECONDS = 600
WARMUP_FRAMES = 120
RETAINED_FRAMES = 1
EXTENT = [640, 480]
SAMPLE_SECONDS = 5.0
MAX_THREADS = 256
MAX_CHILDREN = 64
MAX_FDS = 1024
MAX_PROC_BYTES = 256 * 1024
GDB_TIMEOUT_SECONDS = 30
TERMINATE_GRACE_SECONDS = 5
CFX_PREFIX = "CFX_"


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def durable_json(path, value):
    """Write a small control-plane receipt durably before post-deadline attach."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _bounded_text(path, maximum=MAX_PROC_BYTES):
    path = Path(path)
    try:
        raw = path.read_bytes()
        if len(raw) > maximum:
            return {"status": "TRUNCATED", "bytes": len(raw),
                    "text": raw[:maximum].decode("utf-8", errors="replace")}
        return {"status": "OK", "bytes": len(raw), "text": raw.decode("utf-8", errors="replace")}
    except OSError as error:
        return {"status": "UNAVAILABLE", "error": str(error)}


def _status_fields(text):
    if not isinstance(text, str):
        return {}
    result = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in {"Name", "State", "Tgid", "Pid", "PPid", "TracerPid", "Threads", "VmRSS", "VmSize",
                   "voluntary_ctxt_switches", "nonvoluntary_ctxt_switches", "Cpus_allowed_list"}:
            result[key] = value.strip()
    return result


def _stat_summary(text):
    """Parse only stable fields needed for external CPU/state sampling."""
    if not isinstance(text, str):
        return {}
    close = text.rfind(")")
    if close < 0:
        return {}
    tail = text[close + 2:].split()
    if len(tail) < 13:
        return {}
    try:
        ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        return {"state": tail[0], "ppid": int(tail[1]),
                "utime_ticks": int(tail[11]), "stime_ticks": int(tail[12]),
                "cpu_seconds": (int(tail[11]) + int(tail[12])) / float(ticks)}
    except (ValueError, OSError, KeyError):
        return {}


def _output_progress(cwd):
    """Sample only bounded externally visible capture outputs; never instrument renderer."""
    root = Path(cwd) if cwd else None
    result = {}
    if root is None:
        return result
    for name in ("stdout.log", "stderr.log", "native.renderer.json", "native.png"):
        path = root / name
        try:
            stat = path.stat()
            result[name] = {"exists": True, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        except OSError as error:
            result[name] = {"exists": False, "error": str(error)}
    return result


def process_sample(pid, started_monotonic, cwd=None):
    root = Path("/proc") / str(pid)
    stat = _bounded_text(root / "stat")
    status = _bounded_text(root / "status")
    io = _bounded_text(root / "io")
    return {"utc": run.utc(), "elapsed_seconds": time.monotonic() - started_monotonic,
            "pid": pid, "alive": root.exists(), "stat": _stat_summary(stat.get("text")),
            "status": _status_fields(status.get("text")), "io": io,
            "output_progress": _output_progress(cwd)}


def _process_table():
    result = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        status = _bounded_text(entry / "status", 65536)
        fields = _status_fields(status.get("text"))
        try:
            pid = int(fields.get("Pid", entry.name))
            ppid = int(fields.get("PPid", "-1"))
        except ValueError:
            continue
        result[pid] = {"pid": pid, "ppid": ppid, "status": fields}
    return result


def descendants(pid):
    table = _process_table()
    pending = [pid]
    found = []
    while pending and len(found) < MAX_CHILDREN:
        parent = pending.pop(0)
        children = sorted(row["pid"] for row in table.values() if row["ppid"] == parent and row["pid"] not in found)
        found.extend(children[:MAX_CHILDREN - len(found)])
        pending.extend(children)
    return found, len(found) >= MAX_CHILDREN


def _write_proc_member(destination, source):
    value = _bounded_text(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if value["status"] in {"OK", "TRUNCATED"}:
        destination.write_text(value["text"], encoding="utf-8")
    else:
        destination.with_suffix(destination.suffix + ".unavailable.json").write_bytes(_json_bytes(value))
    return value["status"]


def collect_proc_snapshot(pid, destination):
    """Collect bounded process/thread/FD/child evidence after deadline only."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    process_root = Path("/proc") / str(pid)
    manifest = {"schema": "sdvk009-host-proc-snapshot/v1", "utc": run.utc(), "pid": pid,
                "thread_limit": MAX_THREADS, "child_limit": MAX_CHILDREN, "fd_limit": MAX_FDS,
                "process_files": {}, "threads": [], "children": [], "fds": [], "limits_reached": {}}
    for name in ("stat", "status", "wchan", "stack", "io", "limits", "sched"):
        manifest["process_files"][name] = _write_proc_member(destination / "process" / (name + ".txt"), process_root / name)

    task_root = process_root / "task"
    try:
        tids = sorted((int(entry.name) for entry in task_root.iterdir() if entry.name.isdigit()))
    except OSError as error:
        tids = []
        manifest["task_error"] = str(error)
    manifest["limits_reached"]["threads"] = len(tids) > MAX_THREADS
    for tid in tids[:MAX_THREADS]:
        item = {"tid": tid, "files": {}}
        source = task_root / str(tid)
        for name in ("stat", "status", "wchan", "stack"):
            item["files"][name] = _write_proc_member(destination / "tasks" / str(tid) / (name + ".txt"), source / name)
        stat = _bounded_text(source / "stat")
        item["cpu"] = _stat_summary(stat.get("text"))
        manifest["threads"].append(item)

    fd_root = process_root / "fd"
    try:
        entries = sorted((entry for entry in fd_root.iterdir() if entry.name.isdigit()), key=lambda p: int(p.name))
    except OSError as error:
        entries = []
        manifest["fd_error"] = str(error)
    manifest["limits_reached"]["fds"] = len(entries) > MAX_FDS
    for entry in entries[:MAX_FDS]:
        try:
            target = os.readlink(entry)
            if len(target) > 4096:
                target = target[:4096] + "<truncated>"
            manifest["fds"].append({"fd": int(entry.name), "target": target})
        except OSError as error:
            manifest["fds"].append({"fd": int(entry.name), "error": str(error)})

    child_ids, child_limit = descendants(pid)
    manifest["limits_reached"]["children"] = child_limit
    for child in child_ids:
        child_root = Path("/proc") / str(child)
        item = {"pid": child, "files": {}}
        for name in ("stat", "status", "wchan", "stack", "io"):
            item["files"][name] = _write_proc_member(destination / "children" / str(child) / (name + ".txt"), child_root / name)
        stat = _bounded_text(child_root / "stat")
        item["cpu"] = _stat_summary(stat.get("text"))
        manifest["children"].append(item)
    write_json(destination / "manifest.json", manifest)
    return manifest


def collect_gdb(pid, destination, original_run):
    destination = Path(destination)
    result = {"schema": "sdvk009-gdb-after-deadline/v1", "utc": run.utc(), "pid": pid,
              "attempted": False, "timeout_seconds": GDB_TIMEOUT_SECONDS}
    gdb = shutil.which("gdb")
    if not gdb:
        result.update(status="UNAVAILABLE", reason="gdb not installed")
        write_json(destination / "gdb.json", result)
        return result
    result["attempted"] = True
    stdout = destination / "gdb-backtrace.txt"
    stderr = destination / "gdb-stderr.txt"
    command = [gdb, "-nx", "-q", "-batch", "-ex", "set pagination off", "-ex", "set confirm off",
               "-ex", "info threads", "-ex", "thread apply all bt full", "-p", str(pid)]
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            completed = original_run(command, stdout=out, stderr=err, timeout=GDB_TIMEOUT_SECONDS, check=False)
        result.update(status="COLLECTED" if completed.returncode == 0 else "FAILED",
                      returncode=completed.returncode, command=command,
                      stdout=pin(stdout, relative_to=destination), stderr=pin(stderr, relative_to=destination))
    except (OSError, subprocess.SubprocessError) as error:
        result.update(status="FAILED", error=str(error), command=command)
        if stdout.exists():
            result["stdout"] = pin(stdout, relative_to=destination)
        if stderr.exists():
            result["stderr"] = pin(stderr, relative_to=destination)
    write_json(destination / "gdb.json", result)
    return result


def validate_renderer_argv(argv, timeout, env):
    require(timeout == DEADLINE_SECONDS, "Diagnostic renderer deadline must remain exactly 600 seconds")
    require(isinstance(argv, list) and argv, "Native renderer argv is missing")
    checks = (("-width", "640"), ("-height", "480"), ("-sdvkobserveframes", "1"),
              ("-sdvkobservewarmup", "120"), ("-sdvkobservemode", "state"), ("+map", "SDVSHDW"))
    for flag, expected in checks:
        require(argv.count(flag) == 1 and argv.index(flag) + 1 < len(argv) and argv[argv.index(flag) + 1] == expected,
                "Diagnostic renderer request changed: " + flag)
    require("-sdvkcollisionsnapshot" not in argv, "Timeout discriminator must remain the uninstrumented control")
    require(not any(str(value).startswith("-sdvk") and "witness" in str(value).lower() for value in argv),
            "Publication witness instrumentation is forbidden in the timeout discriminator")
    inherited = os.environ if env is None else env
    require(not any(key.startswith(CFX_PREFIX) and value for key, value in inherited.items()),
            "Timeout discriminator inherited publication diagnostics")
    return True


def validate_request(path, expected_commit):
    request = read_json(path)
    require(request.get("schema") == "sdvk-renderer-request/v1" and request.get("automatic_retries") == 0,
            "Native capture request is not the no-retry renderer request")
    require(request.get("source_commit") == expected_commit and request.get("working_tree") == "clean",
            "Native renderer source identity changed")
    require(request.get("timeout_seconds") == DEADLINE_SECONDS, "Native timeout changed")
    profile = request.get("reproduction", {})
    require(profile.get("scene") == "shadow-boundary" and profile.get("extent") == EXTENT
            and profile.get("warmup_frames") == WARMUP_FRAMES and profile.get("frames") == RETAINED_FRAMES
            and profile.get("gpu_timestamps_requested") is False and profile.get("image_policy") == {"metric": "exact-rgb8"},
            "Shadow-boundary workload/profile changed")
    require("diagnostics" not in request and "-sdvkcollisionsnapshot" not in request.get("argv", []),
            "Timeout discriminator is not the uninstrumented control")
    require(not any(key.startswith(CFX_PREFIX) for key in request.get("environment", {})),
            "Timeout discriminator request recorded CFX diagnostics")
    validate_renderer_argv(request["argv"], request["timeout_seconds"], request.get("environment", {}))
    return request


class DeadlineRunner:
    def __init__(self, exe, root, original_run):
        self.exe = str(Path(exe).resolve())
        self.root = Path(root)
        self.original_run = original_run
        self.outcome = {"native_process_started": False, "deadline_reached": False,
                        "completed_before_deadline": False, "samples": 0}

    def __call__(self, *popenargs, **kwargs):
        argv = popenargs[0] if popenargs else kwargs.get("args")
        if not (isinstance(argv, (list, tuple)) and argv and str(Path(argv[0]).resolve()) == self.exe
                and "--version" not in argv):
            return self.original_run(*popenargs, **kwargs)
        timeout = kwargs.pop("timeout", None)
        check = kwargs.pop("check", False)
        require(check is False, "Diagnostic native invocation unexpectedly enabled subprocess check")
        validate_renderer_argv(list(argv), timeout, kwargs.get("env"))
        timeline = {"schema": "sdvk009-timeout-timeline/v1", "deadline_seconds": DEADLINE_SECONDS,
                    "failure_irrevocable": False, "process_start_utc": run.utc(), "timeout_utc": None,
                    "diagnostic_start_utc": None, "termination_utc": None, "pid": None}
        process_cwd = kwargs.get("cwd")
        process = subprocess.Popen(*popenargs, **kwargs)
        timeline["pid"] = process.pid
        self.outcome.update(native_process_started=True, pid=process.pid, process_start_utc=timeline["process_start_utc"])
        durable_json(self.root / "timeline.json", timeline)
        started = time.monotonic()
        samples = []
        next_sample = 0.0
        while True:
            elapsed = time.monotonic() - started
            returncode = process.poll()
            if returncode is not None:
                samples.append(process_sample(process.pid, started, process_cwd))
                self._write_samples(samples)
                timeline["termination_utc"] = run.utc()
                timeline["returncode"] = returncode
                timeline["completed_before_deadline"] = elapsed < DEADLINE_SECONDS
                durable_json(self.root / "timeline.json", timeline)
                self.outcome.update(completed_before_deadline=elapsed < DEADLINE_SECONDS,
                                    returncode=returncode, elapsed_seconds=elapsed, samples=len(samples),
                                    termination_utc=timeline["termination_utc"])
                completed = subprocess.CompletedProcess(argv, returncode)
                if check and returncode:
                    raise subprocess.CalledProcessError(returncode, argv)
                return completed
            if elapsed >= DEADLINE_SECONDS:
                break
            if elapsed >= next_sample:
                samples.append(process_sample(process.pid, started, process_cwd))
                next_sample += SAMPLE_SECONDS
            time.sleep(min(0.25, max(0.01, DEADLINE_SECONDS - elapsed)))

        timeline["timeout_utc"] = run.utc()
        timeline["diagnostic_start_utc"] = timeline["timeout_utc"]
        timeline["failure_irrevocable"] = True
        durable_json(self.root / "timeline.json", timeline)
        self._write_samples(samples)
        self.outcome.update(deadline_reached=True, timeout_utc=timeline["timeout_utc"], samples=len(samples))

        before = collect_proc_snapshot(process.pid, self.root / "proc-at-deadline")
        gdb = collect_gdb(process.pid, self.root, self.original_run)
        after = collect_proc_snapshot(process.pid, self.root / "proc-after-gdb") if process.poll() is None else None
        termination = {"signal": "SIGTERM", "grace_seconds": TERMINATE_GRACE_SECONDS, "sigkill_used": False}
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                termination["sigkill_used"] = True
                process.kill()
                process.wait(timeout=TERMINATE_GRACE_SECONDS)
        timeline["termination_utc"] = run.utc()
        timeline["returncode"] = process.returncode
        durable_json(self.root / "timeline.json", timeline)
        termination.update(returncode=process.returncode, termination_utc=timeline["termination_utc"])
        write_json(self.root / "termination.json", termination)
        self.outcome.update(returncode=process.returncode, termination_utc=timeline["termination_utc"],
                            proc_threads=len(before.get("threads", [])), proc_children=len(before.get("children", [])),
                            gdb_status=gdb.get("status"), post_gdb_snapshot=after is not None)
        raise subprocess.TimeoutExpired(argv, DEADLINE_SECONDS)

    def _write_samples(self, samples):
        path = self.root / "process-samples.json"
        write_json(path, {"schema": "sdvk009-process-samples/v1", "sample_interval_seconds": SAMPLE_SECONDS,
                          "samples": samples, "sample_count": len(samples),
                          "scope": "External /proc plus bounded output-file metadata sampling only; no renderer instrumentation"})


def diagnose(args):
    out = run.fresh_directory(args.out)
    result = {"schema": SCHEMA, "status": "FAIL", "started_utc": run.utc(),
              "physical_stop_active": True, "physical_gpu_qualified": False,
              "performance_accepted": False, "qualification_eligible": False,
              "can_change_pr146_status": False, "root_cause": "UNDETERMINED",
              "automatic_retries": 0, "renderer_source_commit": args.expected_commit,
              "diagnostic_harness_commit": os.environ.get("GITHUB_SHA"),
              "workload": {"scene": "shadow-boundary", "extent": EXTENT,
                           "warmup_frames": WARMUP_FRAMES, "frames": RETAINED_FRAMES,
                           "timeout_seconds": DEADLINE_SECONDS, "mode": "state",
                           "gpu_timestamps": False, "publication_witness": False,
                           "collision_snapshot": False},
              "authority": "Diagnostic-only; cannot grant the frozen PR #146 matching-content qualification a pass"}
    preregistration = {"schema": REQUEST_SCHEMA, "created_utc": run.utc(), "automatic_retries": 0,
                       "renderer_source_commit": args.expected_commit, "workload": result["workload"],
                       "deadline_policy": "At 600s the run has failed irrevocably; only then may host diagnostics attach",
                       "post_deadline": {"proc": True, "thread_cpu_state": True, "wchan": True,
                                        "kernel_stack_when_readable": True, "open_fds": True,
                                        "children": True, "gdb_all_thread_bt": True},
                       "qualification_eligible": False, "physical_stop_active": True}
    durable_json(out / "preregistration.json", preregistration)
    original_run = subprocess.run
    runner = DeadlineRunner(args.exe, out / "host-diagnostic", original_run)
    try:
        require(args.expected_commit == RENDERER_COMMIT, "Diagnostic must build/run the frozen PR #146 source identity")
        result["software_execution_guard"] = publication.hosted_software_guard()
        require(not any(key.startswith(CFX_PREFIX) and value for key, value in os.environ.items()),
                "Timeout discriminator forbids inherited CFX diagnostics")
        result["hosted_run"] = {key: os.environ.get(key) for key in
                                ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_NAME", "RUNNER_ENVIRONMENT")}
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out / "prepared"
        prepare.prepare(prepared, ["compositing", "shadow-boundary"])
        result["matching_content"] = publication.verify_historical_content(args.iwad, prepared)
        write_json(out / "matching-content.json", result["matching_content"])
        capture_args = argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared,
            out=out / "capture", scene="shadow-boundary", mode="state", frames=RETAINED_FRAMES,
            warmup=WARMUP_FRAMES, timeout=DEADLINE_SECONDS, gpu=False, include_stress=True,
            image_policy="exact", collision_snapshot=False, publication_witness=False,
            expected_commit=args.expected_commit, require_clean=True)
        capture_error = None
        with patch.object(run.subprocess, "run", new=runner):
            try:
                capture_result = run.capture(capture_args)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                capture_result = None
                capture_error = str(error)
        request = validate_request(out / "capture/request.json", args.expected_commit)
        write_json(out / "request-validation.json", {"schema": "sdvk009-timeout-request-validation/v1",
                   "status": "PASS", "request": pin(out / "capture/request.json", relative_to=out),
                   "argv": request["argv"], "automatic_retries": request["automatic_retries"],
                   "qualification_eligible": False})
        result["native_capture_error"] = capture_error
        result["deadline_outcome"] = runner.outcome
        if runner.outcome.get("deadline_reached"):
            require(capture_result is None, "A post-deadline native capture cannot become a collected qualification")
            result["status"] = "DIAGNOSTIC_COLLECTED_AFTER_TIMEOUT"
            result["classification"] = "600-second failure preserved; post-deadline host evidence collected"
        else:
            require(runner.outcome.get("completed_before_deadline") and capture_result is not None
                    and capture_result.get("status") == "COLLECTED" and runner.outcome.get("returncode") == 0,
                    "Diagnostic native process failed before the 600-second deadline")
            result["status"] = "DIAGNOSTIC_ONLY_COMPLETED_BEFORE_DEADLINE"
            result["classification"] = "Separate diagnostic process completed before 600s; this is not a retry/pass for PR #146"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        result["artifacts"] = {path.relative_to(out).as_posix(): pin(path, relative_to=out)
                               for path in sorted(out.rglob("*")) if path.is_file() and not path.is_symlink()
                               and not path.relative_to(out).as_posix().startswith(("capture/cache/", "capture/save/"))}
        write_json(out / "diagnostic.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--iwad", type=Path, required=True)
    parser.add_argument("--iwad-license", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-commit", default=RENDERER_COMMIT)
    args = parser.parse_args(argv)
    result = diagnose(args)
    print(json.dumps({key: result.get(key) for key in ("schema", "status", "classification", "root_cause")}, sort_keys=True))
    return 0 if str(result.get("status", "")).startswith("DIAGNOSTIC_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
