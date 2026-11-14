#!/usr/bin/env python3
"""Preregistered, independent hosted SDVK-009 workers and fail-closed assembly.

This is an explicit alternative to sdvk009_publication.qualify's serial fail-stop
launch policy. It changes no capture, witness validator, state or image oracle.
The compatibility probe has a separate plan and cannot award qualification.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import uuid

from . import native_ci, prepare, run, sdvk009_publication as publication
from .common import ROOT, EvidenceError, canonical, checked, pin, read_json, require, sha256, write_json

PLAN_SCHEMA = "sdvk009-distributed-plan/v1"
WORKER_SCHEMA = "sdvk009-distributed-worker/v1"
INVENTORY_SCHEMA = "sdvk009-distributed-inventory/v1"
WORKERS = ("publication", "controls", "witness-1", "witness-2")
PROBE_WORKERS = ("controls", "witness-1", "witness-2")
PROBE_KIND = "cross-runner-compatibility-probe"
STARTUP_PROBE_KIND = "shadow-startup-compatibility-probe"
FULL_KIND = "publication-qualification"
HOSTED_KEYS = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_NAME", "RUNNER_ENVIRONMENT")


def file_identity(path):
    return {key: value for key, value in pin(path).items() if key != "path"}


def validate_host_identity(value):
    require(isinstance(value, dict) and set(value) == {"boot_id"}
            and isinstance(value["boot_id"], str)
            and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["boot_id"]),
            "Missing or malformed Linux boot identity")
    return value


def host_identity():
    # RUNNER_NAME is retained descriptively but is not globally unique. A kernel
    # boot UUID identifies a separate hosted VM without depending on that name.
    return validate_host_identity({"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()})


def source_identity(expected):
    require(re.fullmatch(r"[0-9a-f]{40}", expected or ""), "Expected exact source commit is required")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    require(git("rev-parse", "HEAD") == expected, "Checkout differs from the registered source commit")
    require(not git("status", "--porcelain", "--untracked-files=no"), "Distributed qualification requires clean source")
    return {"commit": expected, "tree": git("rev-parse", "HEAD^{tree}")}


def workers_for_kind(kind):
    require(kind in (FULL_KIND, PROBE_KIND, STARTUP_PROBE_KIND), "Unknown distributed campaign kind")
    return WORKERS if kind == FULL_KIND else PROBE_WORKERS


def workload(probe=False, *, shadow_startup_probe=False):
    require(not (probe and shadow_startup_probe), "Select only one compatibility probe")
    if shadow_startup_probe:
        # This diagnostic does not enable publication instrumentation: the
        # unchanged full witness validator requires all 121 observed frames.
        rows = [("startup-control-cold", "shadow-boundary", False, "controls"),
                ("startup-compositing-primer", "compositing", False, "controls"),
                ("startup-control-warm", "shadow-boundary", False, "controls"),
                ("startup-witness-1", "shadow-boundary", False, "witness-1"),
                ("startup-witness-2", "shadow-boundary", False, "witness-2")]
    elif probe:
        rows = [("compatibility-" + worker, "compositing", False, worker) for worker in PROBE_WORKERS]
    else:
        rows = [(name, scene, witness, WORKERS[ordinal])
                for ordinal, (name, scene, witness) in enumerate(publication.PLAN)]
    return [{"ordinal": ordinal, "name": name, "scene": scene, "publication_witness": witness,
             "worker": worker, "extent": [640, 480],
             "warmup_frames": 5 if shadow_startup_probe and scene == "shadow-boundary" else 120,
             "frames": 1, "timeout_seconds": 180 if probe or shadow_startup_probe else 3600, "mode": "state",
             "gpu_timestamps": False, "image_policy": {"metric": "exact-rgb8"}}
            for ordinal, (name, scene, witness, worker) in enumerate(rows)]


def runtime_identity(args):
    executable = Path(args.exe).resolve(strict=True)
    packages = {name: file_identity(executable.parent / name) for name in run.PACKAGES
                if (executable.parent / name).is_file()}
    require("vkdoom.pk3" in packages, "Shared runtime has no vkdoom.pk3")
    return {"archive": file_identity(args.runtime_archive), "executable": file_identity(executable),
            "engine_packages": packages}


def matching_content(iwad, prepared):
    value = publication.verify_historical_content(iwad, prepared)
    for key in ("iwad", "historical_manifest"):
        value[key].pop("path", None)
    return value


def inventory(root, *, exclude=()):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "Nonregular distributed evidence: " + str(path))
        name = path.relative_to(root).as_posix()
        if stat.S_ISREG(mode) and name not in exclude:
            result[name] = file_identity(path)
    return result


def _write_seal(path, value):
    write_json(path, value)
    with Path(str(path) + ".sha256").open("x", encoding="ascii") as stream:
        stream.write(sha256(Path(path).read_bytes()) + "  " + Path(path).name + "\n")


def _read_seal(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Missing distributed registration")
    sidecar = Path(str(path) + ".sha256")
    require(sidecar.is_file() and not sidecar.is_symlink(), "Missing distributed registration SHA-256")
    require(sidecar.read_text(encoding="ascii") == sha256(path.read_bytes()) + "  " + path.name + "\n",
            "Distributed registration SHA-256 changed")
    return read_json(path)


def register(args):
    out = run.fresh_directory(args.out)
    source = source_identity(args.expected_commit)
    prepared = out / "prepared"
    prepare.prepare(prepared, ["compositing", "shadow-boundary"])
    probe = bool(getattr(args, "compatibility_probe", False))
    startup_probe = bool(getattr(args, "shadow_startup_probe", False))
    captures = workload(probe, shadow_startup_probe=startup_probe)
    kind = STARTUP_PROBE_KIND if startup_probe else PROBE_KIND if probe else FULL_KIND
    result = {"schema": PLAN_SCHEMA, "status": "REGISTERED", "started_utc": run.utc(),
              "campaign_id": uuid.uuid4().hex, "kind": kind,
              "source": source, "runtime": runtime_identity(args),
              "matching_content": matching_content(args.iwad, prepared),
              "iwad_license": file_identity(args.iwad_license),
              "prepared_manifest": pin(prepared / "prepared.json", relative_to=out),
              "captures": [{**row, "authorization_id": uuid.uuid4().hex} for row in captures],
              "workers": list(workers_for_kind(kind)), "automatic_retries": 0,
              "hosted_run": {key: os.environ.get(key) for key in HOSTED_KEYS if key != "RUNNER_NAME"},
              "launch_policy": "independently authorized workers; fail-stop within each worker; all registered workers required at assembly",
              "physical_gpu_qualified": False, "performance_accepted": False,
              "qualification_awarded": False}
    _write_seal(out / "preregistration.json", result)
    return result


def load_plan(path, expected_commit):
    path = Path(path).resolve(strict=True)
    plan = _read_seal(path)
    require(set(plan) == {"schema", "status", "started_utc", "campaign_id", "kind", "source", "runtime",
                         "matching_content", "iwad_license", "prepared_manifest", "captures", "workers",
                         "automatic_retries", "hosted_run", "launch_policy", "physical_gpu_qualified",
                         "performance_accepted", "qualification_awarded"}, "Unknown distributed plan fields")
    require(plan["schema"] == PLAN_SCHEMA and plan["status"] == "REGISTERED"
            and plan["kind"] in (PROBE_KIND, STARTUP_PROBE_KIND, FULL_KIND), "Unknown distributed plan/schema")
    require(plan["source"] == source_identity(expected_commit), "Plan source identity differs")
    require(plan["workers"] == list(workers_for_kind(plan["kind"])) and plan["automatic_retries"] == 0,
            "Worker allocation or retry policy changed")
    require(all(plan[key] is False for key in ("physical_gpu_qualified", "performance_accepted", "qualification_awarded")),
            "Registration cannot grant qualification")
    require(re.fullmatch(r"[0-9a-f]{32}", plan["campaign_id"]), "Invalid campaign identity")
    captures = plan["captures"]
    require(isinstance(captures, list) and all(isinstance(row, dict) for row in captures), "Malformed capture plan")
    require([{k: v for k, v in row.items() if k != "authorization_id"} for row in captures]
            == workload(plan["kind"] == PROBE_KIND, shadow_startup_probe=plan["kind"] == STARTUP_PROBE_KIND),
            "Capture plan order, ownership or fixed workload changed")
    tokens = [row.get("authorization_id") for row in captures]
    require(all(isinstance(token, str) and re.fullmatch(r"[0-9a-f]{32}", token) for token in tokens)
            and len(set(tokens)) == len(tokens), "Missing or duplicate capture authorization")
    require(plan["matching_content"]["iwad"] == {"sha256": publication.IWAD_SHA256, "bytes": publication.IWAD_BYTES},
            "Plan has a different historical IWAD")
    checked(path.parent, plan["prepared_manifest"])
    require(plan["prepared_manifest"]["path"] == "prepared/prepared.json", "Prepared manifest path changed")
    prepare.verify_prepared(path.parent / "prepared")
    require(plan["matching_content"]["historical_manifest"] == file_identity(publication.HISTORICAL_MANIFEST),
            "Historical input authority changed")
    require(set(plan["matching_content"]["inputs"]) == {scene + "/" + leaf for scene in
            ("compositing", "shadow-boundary") for leaf in ("scene.pk3", "fixture.ini", "capture.cfg")},
            "Historical authored input inventory is incomplete")
    historical = read_json(publication.HISTORICAL_MANIFEST)["files"]
    for name, identity in plan["matching_content"]["inputs"].items():
        scene, leaf = name.split("/", 1)
        require(identity == pin(path.parent / "prepared/scenes" / scene / leaf, relative_to=path.parent / "prepared"),
                "Registered authored input changed: " + name)
        historical_leaf = leaf if leaf == "capture.cfg" else "input/" + leaf
        require({key: identity[key] for key in ("sha256", "bytes")} ==
                historical[f"campaign-01/reference-state/{scene}/1/{historical_leaf}"],
                "Registered authored input differs from the sealed history: " + name)
    return plan


def _plan_pin(path):
    return file_identity(path)


def _capture_args(args, row, prepared, out):
    return argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared, out=out,
        scene=row["scene"], mode="state", frames=row["frames"], warmup=row["warmup_frames"],
        timeout=row["timeout_seconds"], gpu=False, include_stress=True, image_policy="exact",
        collision_snapshot=row["publication_witness"], publication_witness=row["publication_witness"],
        expected_commit=args.expected_commit, require_clean=True)


def admit_capture(root, row, plan, prepared_identity):
    root, data, _, _ = run.validate_run(root)
    request = read_json(root / "request.json")
    require(Path(request["cwd"]).name == row["name"] and Path(request["cwd"]).parent.name == "captures"
            and Path(request["cwd"]).parent.parent.name == "renderer-sdvk009-worker-" + row["worker"],
            "Native request belongs to another capture/worker")
    profile = request["reproduction"]
    for key in ("scene", "extent", "warmup_frames", "frames", "image_policy"):
        require(profile[key] == row[key], "Native workload differs from the authorized capture: " + key)
    require(request["mode"] == "state" and profile["gpu_timestamps_requested"] is False
            and request["timeout_seconds"] == row["timeout_seconds"] and request["automatic_retries"] == 0,
            "Native mode, timeout or retry policy differs")
    require(("diagnostics" in request) is row["publication_witness"]
            and ("collision_snapshot" in profile) is row["publication_witness"], "Capture instrumentation role changed")
    require(data["build"]["commit"] == plan["source"]["commit"] and data["build"]["working_tree"] == "clean",
            "Capture source/build differs")
    require({k: data["executable"][k] for k in ("sha256", "bytes")} == plan["runtime"]["executable"],
            "Capture executable differs from the shared runtime")
    actual = {Path(value["path"]).name: {k: value[k] for k in ("sha256", "bytes")}
              for value in data["loaded_packages"] if Path(value["path"]).name in run.PACKAGES}
    require(actual == plan["runtime"]["engine_packages"], "Capture engine packages differ from the shared runtime")
    require(file_identity(root / "prepared.json") == prepared_identity, "Capture used another prepared manifest")
    require(profile["iwad_sha256"] == publication.IWAD_SHA256, "Capture historical IWAD changed")
    return {"cwd": request["cwd"], "request": file_identity(root / "request.json"),
            "run": file_identity(root / "run.json"), "build": run.comparable_build(data["build"]),
            "diagnostic_run_id": request.get("diagnostics", {}).get("run_id"),
            "elapsed_seconds": data["elapsed_seconds"]}


def worker(args):
    out = run.fresh_directory(args.out)
    require(out.name == "renderer-sdvk009-worker-" + args.worker, "Worker output must use its unique assigned directory")
    result = {"schema": WORKER_SCHEMA, "status": "FAIL", "worker": args.worker,
              "worker_execution_id": uuid.uuid4().hex, "started_utc": run.utc(), "steps": [], "captures": [],
              "hosted_run": {key: os.environ.get(key) for key in HOSTED_KEYS},
              "automatic_retries": 0, "qualification_awarded": False, "physical_gpu_qualified": False,
              "performance_accepted": False}
    try:
        result["host_identity"] = validate_host_identity(host_identity())
        # This durable failure-default receipt precedes even device enumeration.
        write_json(out / "worker-start.json", copy.deepcopy(result))
        plan = load_plan(args.plan, args.expected_commit)
        require(args.worker in plan["workers"], "Worker is not authorized by this campaign")
        result.update(plan=_plan_pin(args.plan), campaign_id=plan["campaign_id"], kind=plan["kind"], source=plan["source"])
        result["software_execution_guard"] = publication.hosted_software_guard()
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()),
                "Distributed worker forbids inherited diagnostic environment")
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_ENVIRONMENT"):
            require(os.environ.get(key) == plan["hosted_run"].get(key), "Worker belongs to another hosted run: " + key)
        require(result["hosted_run"]["RUNNER_NAME"], "Missing independent hosted runner identity")
        require(runtime_identity(args) == plan["runtime"], "Shared runtime/archive identity differs")
        require(file_identity(args.iwad_license) == plan["iwad_license"], "Historical license changed")
        prepared = Path(args.plan).resolve().parent / "prepared"
        require(matching_content(args.iwad, prepared) == plan["matching_content"], "Historical content differs")
        result["runtime"] = plan["runtime"]
        write_json(out / "worker-registration.json", copy.deepcopy(result))
        step = native_ci.attempt(out, "preflight", lambda: native_ci.preflight(args, out))
        result["steps"].append(step)
        require(step["status"] == "PASS", "Software-only preflight failed; no capture authorized")
        for row in plan["captures"]:
            if row["worker"] != args.worker:
                continue
            capture_root = out / "captures" / row["name"]
            launch = {"schema": "sdvk009-distributed-launch/v1", "status": "AUTHORIZED",
                      "campaign_id": plan["campaign_id"], "plan": result["plan"], "capture": row,
                      "worker_execution_id": result["worker_execution_id"], "started_utc": run.utc(),
                      "cwd": str(capture_root), "automatic_retries": 0}
            launch_path = out / "launches" / (row["name"] + ".json")
            write_json(launch_path, launch)
            step = native_ci.attempt(out, row["name"],
                lambda r=row, p=capture_root: run.capture(_capture_args(args, r, prepared, p)), ("COLLECTED",))
            result["steps"].append(step)
            require(step["status"] == "PASS", "Capture failed; remaining captures in this worker suppressed")
            admission = admit_capture(capture_root, row, plan, file_identity(prepared / "prepared.json"))
            result["captures"].append({"name": row["name"], "authorization_id": row["authorization_id"],
                                       "launch": pin(launch_path, relative_to=out), "admission": admission})
        result["status"] = "PASS"
    except (OSError, ValueError, KeyError, TypeError) as error:
        result["error"] = str(error)
    except KeyboardInterrupt:
        result.update(status="CANCELLED", error="Capture worker interrupted; incomplete evidence cannot qualify")
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "worker.json", result)
        _write_seal(out / "manifest.json", {"schema": INVENTORY_SCHEMA, "worker": args.worker,
                    "status": result["status"], "files": inventory(out, exclude=("manifest.json", "manifest.json.sha256"))})
    return result


def verify_worker(root, worker_name, plan, plan_identity, prepared_identity):
    root = Path(root)
    manifest = _read_seal(root / "manifest.json")
    require(set(manifest) == {"schema", "worker", "status", "files"} and manifest["schema"] == INVENTORY_SCHEMA
            and manifest["worker"] == worker_name and manifest["status"] == "PASS", "Worker inventory failed/incomplete")
    require(manifest["files"] == inventory(root, exclude=("manifest.json", "manifest.json.sha256")),
            "Worker raw evidence missing, added or altered")
    result = read_json(root / "worker.json")
    require(result["schema"] == WORKER_SCHEMA and result["status"] == "PASS" and result["worker"] == worker_name,
            "Worker failed, cancelled, cross-wired or incomplete")
    require(result["plan"] == plan_identity and result["campaign_id"] == plan["campaign_id"]
            and result["source"] == plan["source"] and result["runtime"] == plan["runtime"]
            and result["kind"] == plan["kind"], "Worker source/runtime/registration differs")
    require(result["automatic_retries"] == 0 and all(result[key] is False for key in
            ("qualification_awarded", "physical_gpu_qualified", "performance_accepted")), "Worker claims unauthorized acceptance")
    require(re.fullmatch(r"[0-9a-f]{32}", result["worker_execution_id"]), "Worker execution identity malformed")
    validate_host_identity(result["host_identity"])
    start = read_json(root / "worker-start.json")
    registration = read_json(root / "worker-registration.json")
    for value in (start, registration):
        require(value["status"] == "FAIL" and value["worker"] == worker_name
                and value["worker_execution_id"] == result["worker_execution_id"]
                and value["hosted_run"] == result["hosted_run"]
                and value["host_identity"] == result["host_identity"], "Worker launch provenance changed")
    require(registration["plan"] == plan_identity and registration["runtime"] == plan["runtime"],
            "Worker prospective runtime registration differs")
    require(result["hosted_run"]["RUNNER_NAME"] and result["hosted_run"]["RUNNER_ENVIRONMENT"] == "github-hosted",
            "Missing independently hosted worker identity")
    require({key: result["hosted_run"][key] for key in plan["hosted_run"]} == plan["hosted_run"],
            "Worker came from a different workflow run/attempt")
    rows = [row for row in plan["captures"] if row["worker"] == worker_name]
    require([entry["name"] for entry in result["captures"]] == [row["name"] for row in rows],
            "Missing, duplicated, reordered or unexpected worker captures")
    require([step["name"] for step in result["steps"]] == ["preflight", *[row["name"] for row in rows]]
            and all(step["status"] == "PASS" for step in result["steps"]), "Worker process receipts incomplete/reordered")
    require(sorted(path.name for path in (root / "captures").iterdir()) == sorted(row["name"] for row in rows),
            "Unexpected capture directory or silent duplicate")
    for step in result["steps"]:
        receipt = checked(root, step["receipt"])
        data = read_json(receipt)
        require(data["name"] == step["name"] and data["status"] == "PASS", "Native process receipt failed or cross-wired")
        require(data["result"]["status"] == ("PASS" if step["name"] == "preflight" else "COLLECTED"),
                "Native process result did not succeed")
        if step["name"] == "preflight":
            checked(root, data["result"]["provenance"])
        else:
            require(data["result"] == read_json(root / "captures" / step["name"] / "run.json"),
                    "Process receipt does not describe the retained native capture")
    for row, entry in zip(rows, result["captures"]):
        launch = read_json(checked(root, entry["launch"]))
        require(launch["schema"] == "sdvk009-distributed-launch/v1" and launch["status"] == "AUTHORIZED"
                and launch["capture"] == row and entry["authorization_id"] == row["authorization_id"]
                and launch["campaign_id"] == plan["campaign_id"] and launch["plan"] == plan_identity
                and launch["worker_execution_id"] == result["worker_execution_id"] and launch["automatic_retries"] == 0,
                "Capture launch authorization mismatched or reused")
        admission = admit_capture(root / "captures" / row["name"], row, plan, prepared_identity)
        require(admission == entry["admission"] and launch["cwd"] == admission["cwd"],
                "Capture request/receipt changed after collection")
    return result


def _save_relocations(path, relocations):
    # This is an incrementally updated transport journal, never a capture or
    # acceptance receipt. Atomic replacement retains progress on interruption.
    temporary = Path(str(path) + ".tmp")
    temporary.write_bytes(canonical({"schema": "sdvk009-publication-relocation/v1", "files": relocations}))
    temporary.replace(path)


def _relocate_tree(source, destination, workers_root, relocations, journal):
    require(not destination.exists(), "Evidence relocation would overwrite a path")
    before = inventory(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    for name, identity in before.items():
        relocations[(source / name).relative_to(workers_root).as_posix()] = {
            "destination": (destination / name).relative_to(workers_root).as_posix(), **identity}
    # Journal the rename before the potentially long rehash, so cancellation
    # during that verification still leaves a complete path accounting record.
    _save_relocations(journal, relocations)
    require(inventory(destination) == before, "Evidence changed while being relocated")


def assemble(args):
    out = run.fresh_directory(args.out)
    workers_root = Path(args.workers).resolve(strict=True)
    relocations = {}
    journal = out / "relocation.json"
    _save_relocations(journal, relocations)
    result = {"schema": publication.SCHEMA, "status": "FAIL", "started_utc": run.utc(), "steps": [],
              "automatic_retries": 0, "physical_stop_active": True, "physical_gpu_qualified": False,
              "performance_accepted": False, "qualification_awarded": False,
              "root_cause": "UNDETERMINED", "orchestration": "independently-authorized-distributed-captures"}
    try:
        plan_path = Path(args.plan).resolve(strict=True)
        plan = load_plan(plan_path, args.expected_commit)
        result.update(kind=plan["kind"], expected_commit=args.expected_commit, campaign_id=plan["campaign_id"],
                      plan=plan["captures"], matching_content=plan["matching_content"])
        plan_identity = _plan_pin(plan_path)
        prepared_identity = file_identity(plan_path.parent / "prepared/prepared.json")
        worker_names = workers_for_kind(plan["kind"])
        found = sorted(path.name.removeprefix("renderer-sdvk009-worker-")
                       for path in workers_root.glob("renderer-sdvk009-worker-*"))
        require(found == sorted(worker_names), "Missing, duplicate or unregistered distributed worker")
        workers = [verify_worker(workers_root / ("renderer-sdvk009-worker-" + name), name,
                                 plan, plan_identity, prepared_identity) for name in worker_names]
        require(len({row["worker_execution_id"] for row in workers}) == len(worker_names), "Worker execution reused")
        require(len({row["host_identity"]["boot_id"] for row in workers}) == len(worker_names),
                "Distributed workers did not execute on independent hosted runners")
        captures = [item for value in workers for item in value["captures"]]
        require(len({row["admission"]["cwd"] for row in captures}) == len(captures)
                and len({row["admission"]["request"]["sha256"] for row in captures}) == len(captures),
                "The same native process/request was supplied more than once")
        witness_ids = [row["admission"]["diagnostic_run_id"] for row in captures if row["admission"]["diagnostic_run_id"]]
        require(len(witness_ids) == len(set(witness_ids)), "Publication diagnostic process identity reused")
        reference = captures[0]["admission"]["build"]
        require(all(row["admission"]["build"] == reference for row in captures),
                "Cross-runner source, backend, renderer, device or Vulkan identity differs")
        result["workers"] = [{key: value[key] for key in ("worker", "worker_execution_id", "hosted_run", "host_identity", "started_utc", "finished_utc")}
                             for value in workers]
        # Authenticate every complete worker before moving any raw byte. Moving,
        # rather than copying, preserves the old consumer layout without doubles.
        for row in plan["captures"]:
            source = workers_root / ("renderer-sdvk009-worker-" + row["worker"]) / "captures" / row["name"]
            _relocate_tree(source, out / "captures" / row["name"], workers_root, relocations, journal)
        provenance_worker = "controls"
        for name in worker_names:
            worker_root = workers_root / ("renderer-sdvk009-worker-" + name)
            if name == provenance_worker:
                _relocate_tree(worker_root / "provenance", out / "provenance", workers_root, relocations, journal)
            _relocate_tree(worker_root, out / "distributed-workers" / name, workers_root, relocations, journal)
        # Plan files/inputs move with the packet; all original bytes are retained.
        for child in sorted(plan_path.parent.iterdir()):
            if child.is_dir():
                _relocate_tree(child, out / child.name, workers_root, relocations, journal)
            else:
                before = file_identity(child)
                destination = out / child.name
                require(not destination.exists(), "Plan relocation would overwrite evidence")
                shutil.move(str(child), str(destination))
                require(file_identity(destination) == before, "Plan bytes changed in relocation")
                relocations[child.relative_to(workers_root).as_posix()] = {
                    "destination": destination.relative_to(workers_root).as_posix(), **before}
                _save_relocations(journal, relocations)
        plan_path.parent.rmdir()
        write_json(out / "matching-content.json", plan["matching_content"])
        # Preserve original step receipt filenames; these small aliases are exact
        # copies, not duplicated native captures. The originals remain in workers.
        workers_by_name = {value["worker"]: value for value in workers}
        aliases = [(provenance_worker, workers_by_name[provenance_worker]["steps"][0])]
        for row in plan["captures"]:
            step = next(step for step in workers_by_name[row["worker"]]["steps"] if step["name"] == row["name"])
            aliases.append((row["worker"], step))
        # Legacy order describes the immutable plan, not concurrent timestamps.
        for worker_name, step in aliases:
            source = out / "distributed-workers" / worker_name / step["receipt"]["path"]
            destination = out / "steps" / (step["name"] + ".json")
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, destination)
            require(file_identity(source) == file_identity(destination), "Step alias differs")
            result["steps"].append({**step, "receipt": pin(destination, relative_to=out)})
        if plan["kind"] == STARTUP_PROBE_KIND:
            cold = out / "captures/startup-control-cold"
            warm = out / "captures/startup-control-warm"
            history = run.compare_runs(cold, warm)
            write_json(out / "startup-history-comparison.json", history)
            result["startup_history"] = {
                "comparison": history,
                "scope": "Descriptive first-use versus post-compositing state/RGB; its result cannot award qualification"}
            result["comparisons"] = []
            pairs = [("cold-control-witness-1", cold, out / "captures/startup-witness-1"),
                     ("cold-control-witness-2", cold, out / "captures/startup-witness-2"),
                     ("witness-repeat", out / "captures/startup-witness-1", out / "captures/startup-witness-2")]
            for name, left, right in pairs:
                comparison = run.compare_runs(left, right)
                write_json(out / ("startup-" + name + "-comparison.json"), comparison)
                result["comparisons"].append(comparison)
                require(comparison["status"] == "PASS", "First-use shadow startup probe failed original exact comparison")
            result.update(status="PROBE_PASS", qualification_awarded=False,
                          evidence_scope="Short uninstrumented first-use shadow startup diagnosis; not full publication qualification")
        elif plan["kind"] == PROBE_KIND:
            reference = out / "captures" / plan["captures"][0]["name"]
            result["comparisons"] = []
            for row in plan["captures"][1:]:
                comparison = run.compare_runs(reference, out / "captures" / row["name"])
                write_json(out / (row["name"] + "-comparison.json"), comparison)
                result["comparisons"].append(comparison)
                require(comparison["status"] == "PASS", "Cross-runner compatibility probe failed exact comparison")
            result.update(status="PROBE_PASS", qualification_awarded=False,
                          evidence_scope="Cheap compositing-only cross-runner compatibility; not publication qualification")
        else:
            for name in ("shadow-witness-1", "shadow-witness-2"):
                capture = out / "captures" / name
                proof = publication.validate_witness(capture)
                write_json(out / (name + "-publication.json"), proof)
                controls = publication.negative_controls(capture)
                require(len(controls["controls"]) == 9 and controls["status"] == "PASS",
                        "All nine original publication negative controls are required")
                write_json(out / (name + "-negative-controls.json"), controls)
                comparison = publication.compare_control(out / "captures/shadow-control", capture)
                write_json(out / (name + "-control-comparison.json"), comparison)
                require(comparison["status"] == "PASS", "Instrumented witness changed protected state or exact RGB")
            comparison = run.compare_runs(out / "captures/shadow-witness-1", out / "captures/shadow-witness-2")
            write_json(out / "witness-repeat-comparison.json", comparison)
            require(comparison["status"] == "PASS", "Independent publication witnesses are not repeatable")
            result.update(status="PASS", qualification_awarded=True,
                          evidence_scope="Matching historical authored inputs and software publication; no physical/performance acceptance")
    except (OSError, ValueError, KeyError, TypeError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        _save_relocations(journal, relocations)
        write_json(out / "qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    registration = sub.add_parser("register")
    probes = registration.add_mutually_exclusive_group()
    probes.add_argument("--compatibility-probe", action="store_true")
    probes.add_argument("--shadow-startup-probe", action="store_true")
    execution = sub.add_parser("worker")
    execution.add_argument("--worker", choices=WORKERS, required=True)
    execution.add_argument("--plan", type=Path, required=True)
    assembly = sub.add_parser("assemble")
    assembly.add_argument("--plan", type=Path, required=True)
    assembly.add_argument("--workers", type=Path, required=True)
    for command in (registration, execution):
        for name in ("exe", "iwad", "iwad-license", "runtime-archive"):
            command.add_argument("--" + name, type=Path, required=True)
    for command in (registration, execution, assembly):
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "worker":
            def cancelled(signum, frame):
                raise KeyboardInterrupt("worker cancelled")
            signal.signal(signal.SIGTERM, cancelled)
        result = {"register": register, "worker": worker, "assemble": assemble}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(result["status"] + (": " + result["error"] if "error" in result else ""), flush=True)
    return 0 if result["status"] in ("REGISTERED", "PASS", "PROBE_PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
