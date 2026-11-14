#!/usr/bin/env python3
"""Preregistered, independent hosted SDVK-009 workers and fail-closed assembly.

This is an explicit alternative to sdvk009_publication.qualify's serial fail-stop
launch policy. It changes no original capture, witness validator, state or image oracle.
The compatibility probe has a separate plan and cannot award qualification.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal
import itertools
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
COHORT_RECEIPT_SCHEMA = "sdvk009-distributed-cohort-probe/v1"
INVENTORY_SCHEMA = "sdvk009-distributed-inventory/v1"
WORKERS = ("publication", "controls", "witness-1", "witness-2")
PROBE_WORKERS = ("controls", "witness-1", "witness-2")
PROBE_KIND = "cross-runner-compatibility-probe"
STARTUP_PROBE_KIND = "shadow-startup-compatibility-probe"
FULL_KIND = "publication-qualification"
COHORT_KIND = "cohort-publication-qualification"
COHORT_PROBE_KIND = "cohort-post-probe-compatibility"
COHORT_KINDS = (COHORT_KIND, COHORT_PROBE_KIND)
ARTIFACT_SET_SCHEMA = "sdvk009-cohort-artifacts/v1"
ALLOCATION_SCHEMA = "sdvk009-cohort-allocation/v1"
ALLOCATION_POLICY = {"probe_workers": list(PROBE_WORKERS), "barrier": "all-three-authenticated-probes",
    "comparison": "original-exact-state-and-rgb", "selection": "compatible-subsets-within-relative-minimum-score",
    "weight": "ceil-milliseconds-of-authenticated-native-probe-elapsed-seconds",
    "score": "maximum-assigned-shadow-count-times-probe-weight",
    "near_minimum": {"numerator": 110, "denominator": 100},
    "tie_break": "largest-cohort-then-lowest-score-then-lexicographic-worker-ids",
    "assignment": "round-robin-original-shadow-order",
    "assignment_order": "two-host-fastest-first-otherwise-lexicographic-worker-ids",
    "weight_scope": "uncertain-relative-placement-estimate; no performance acceptance",
    "automatic_retries": 0, "reassignment": False}
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
    require(kind in (FULL_KIND, PROBE_KIND, STARTUP_PROBE_KIND, *COHORT_KINDS), "Unknown distributed campaign kind")
    return WORKERS if kind == FULL_KIND or kind in COHORT_KINDS else PROBE_WORKERS


def workload(probe=False, *, shadow_startup_probe=False, cohort=False, cohort_probe=False):
    require(sum(map(bool, (probe, shadow_startup_probe, cohort, cohort_probe))) <= 1, "Select only one campaign kind")
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
        rows = [(("cohort-proof-" + name) if cohort_probe else name, scene, witness and not cohort_probe,
                 "cohort" if ordinal and (cohort or cohort_probe) else WORKERS[ordinal])
                for ordinal, (name, scene, witness) in enumerate(publication.PLAN)]
    return [{"ordinal": ordinal, "name": name, "scene": scene, "publication_witness": witness,
             "worker": worker, "extent": [640, 480],
             "warmup_frames": 5 if (shadow_startup_probe or cohort_probe) and scene == "shadow-boundary" else 120,
             "frames": 1, "timeout_seconds": 180 if probe or shadow_startup_probe or cohort_probe else 3600, "mode": "state",
             "gpu_timestamps": False, "image_policy": {"metric": "exact-rgb8"}}
            for ordinal, (name, scene, witness, worker) in enumerate(rows)]


def cohort_probes():
    return [{"ordinal": ordinal, "name": "cohort-probe-" + worker, "scene": "shadow-boundary",
             "publication_witness": False, "worker": worker, "extent": [640, 480], "warmup_frames": 5,
             "frames": 1, "timeout_seconds": 180, "mode": "state", "gpu_timestamps": False,
             "image_policy": {"metric": "exact-rgb8"}} for ordinal, worker in enumerate(PROBE_WORKERS)]


def _workload_for_kind(kind):
    return workload(kind == PROBE_KIND, shadow_startup_probe=kind == STARTUP_PROBE_KIND,
                    cohort=kind == COHORT_KIND, cohort_probe=kind == COHORT_PROBE_KIND)


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
    cohort = bool(getattr(args, "cohort", False))
    cohort_probe = bool(getattr(args, "cohort_probe", False))
    captures = workload(probe, shadow_startup_probe=startup_probe, cohort=cohort, cohort_probe=cohort_probe)
    kind = (COHORT_KIND if cohort else COHORT_PROBE_KIND if cohort_probe else
            STARTUP_PROBE_KIND if startup_probe else PROBE_KIND if probe else FULL_KIND)
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
    if kind in COHORT_KINDS:
        result.update(probes=[{**row, "authorization_id": uuid.uuid4().hex} for row in cohort_probes()],
                      allocation_policy=copy.deepcopy(ALLOCATION_POLICY))
    _write_seal(out / "preregistration.json", result)
    return result


def load_plan(path, expected_commit):
    path = Path(path).resolve(strict=True)
    plan = _read_seal(path)
    expected_fields = {"schema", "status", "started_utc", "campaign_id", "kind", "source", "runtime",
                         "matching_content", "iwad_license", "prepared_manifest", "captures", "workers",
                         "automatic_retries", "hosted_run", "launch_policy", "physical_gpu_qualified",
                         "performance_accepted", "qualification_awarded"}
    if plan.get("kind") in COHORT_KINDS:
        expected_fields.update(("probes", "allocation_policy"))
    require(set(plan) == expected_fields, "Unknown distributed plan fields")
    require(plan["schema"] == PLAN_SCHEMA and plan["status"] == "REGISTERED"
            and plan["kind"] in (PROBE_KIND, STARTUP_PROBE_KIND, FULL_KIND, *COHORT_KINDS), "Unknown distributed plan/schema")
    require(plan["source"] == source_identity(expected_commit), "Plan source identity differs")
    require(plan["workers"] == list(workers_for_kind(plan["kind"])) and plan["automatic_retries"] == 0,
            "Worker allocation or retry policy changed")
    require(all(plan[key] is False for key in ("physical_gpu_qualified", "performance_accepted", "qualification_awarded")),
            "Registration cannot grant qualification")
    require(re.fullmatch(r"[0-9a-f]{32}", plan["campaign_id"]), "Invalid campaign identity")
    captures = plan["captures"]
    require(isinstance(captures, list) and all(isinstance(row, dict) for row in captures), "Malformed capture plan")
    require([{k: v for k, v in row.items() if k != "authorization_id"} for row in captures]
            == _workload_for_kind(plan["kind"]),
            "Capture plan order, ownership or fixed workload changed")
    if plan["kind"] in COHORT_KINDS:
        require(plan["allocation_policy"] == ALLOCATION_POLICY, "Preregistered cohort placement policy changed")
        require([{k: v for k, v in row.items() if k != "authorization_id"} for row in plan["probes"]]
                == cohort_probes(), "Cohort probe order, ownership or workload changed")
        captures = [*captures, *plan["probes"]]
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


def admit_capture(root, row, plan, prepared_identity, *, probe=False):
    root, data, _, _ = run.validate_run(root)
    request = read_json(root / "request.json")
    require(Path(request["cwd"]).name == row["name"] and Path(request["cwd"]).parent.name == "captures"
            and Path(request["cwd"]).parent.parent.name ==
                ("renderer-sdvk009-probe-" if probe else "renderer-sdvk009-worker-") + row["worker"],
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


def validate_artifact_set(value, plan, plan_identity, roots):
    require(set(value) == {"schema", "github_run_id", "github_run_attempt", "source_commit", "plan_sha256", "artifacts"}
            and value["schema"] == ARTIFACT_SET_SCHEMA, "Unknown cohort artifact-set schema")
    require(value["github_run_id"] == plan["hosted_run"]["GITHUB_RUN_ID"]
            and value["github_run_attempt"] == plan["hosted_run"]["GITHUB_RUN_ATTEMPT"]
            and value["source_commit"] == plan["source"]["commit"]
            and value["plan_sha256"] == plan_identity["sha256"], "Cohort artifacts belong to another source/run/attempt/plan")
    artifacts = value["artifacts"]
    require(isinstance(artifacts, list) and [item["worker"] for item in artifacts] == list(PROBE_WORKERS),
            "All three ordered cohort artifacts are required")
    for item in artifacts:
        require(set(item) == {"worker", "artifact_id", "name", "archive_sha256", "archive_bytes", "manifest_sha256"},
                "Unknown cohort artifact identity fields")
        expected_name = "sdvk-cohort-probe-{}-{}-{}".format(value["github_run_id"], value["github_run_attempt"], item["worker"])
        require(item["name"] == expected_name and type(item["artifact_id"]) is int and item["artifact_id"] > 0
                and type(item["archive_bytes"]) is int and 0 < item["archive_bytes"] <= 512 * 1024 * 1024,
                "Cohort artifact name, ID or size is invalid")
        require(all(isinstance(item[key], str) and re.fullmatch(r"[0-9a-f]{64}", item[key])
                    for key in ("archive_sha256", "manifest_sha256")), "Cohort artifact digest malformed")
        require(item["manifest_sha256"] == file_identity(roots[item["worker"]] / "manifest.json")["sha256"],
                "Cohort artifact manifest differs from its authenticated archive")
    require(len({item["artifact_id"] for item in artifacts}) == 3
            and len({item["archive_sha256"] for item in artifacts}) == 3, "Cohort artifacts duplicated or cross-wired")
    return value


def compatible_placement(comparisons, elapsed_seconds):
    """Score seven fixed subsets; probe time is a routing estimate, not acceptance."""
    pairs = list(itertools.combinations(PROBE_WORKERS, 2))
    require([(row["left"], row["right"]) for row in comparisons] == pairs
            and all(row["status"] in ("PASS", "FAIL") for row in comparisons), "Incomplete cohort comparison matrix")
    require(isinstance(elapsed_seconds, dict) and set(elapsed_seconds) == set(PROBE_WORKERS),
            "All three authenticated native probe elapsed values are required")
    weights = []
    for worker in PROBE_WORKERS:
        value = elapsed_seconds[worker]
        require(type(value) in (int, float), "Native probe elapsed seconds must be positive and finite")
        decimal = Decimal(str(value))
        require(decimal.is_finite() and decimal > 0, "Native probe elapsed seconds must be positive and finite")
        # Preserve the retained native value and ceil its decimal representation
        # exactly. Integer arithmetic avoids float threshold/rounding ties. The
        # native timeout remains authoritative: subprocess creation/wait costs
        # mean elapsed time need not be bounded by precisely 180.000 seconds.
        numerator, denominator = decimal.as_integer_ratio()
        weights.append({"worker": worker, "native_elapsed_seconds": value,
                        "ceil_milliseconds": (numerator * 1000 + denominator - 1) // denominator})
    milliseconds = {row["worker"]: row["ceil_milliseconds"] for row in weights}
    passed = {frozenset((row["left"], row["right"])) for row in comparisons if row["status"] == "PASS"}
    candidates = []
    for size in range(1, 4):
        for members in itertools.combinations(sorted(PROBE_WORKERS), size):
            group = list(members)
            order = sorted(group, key=lambda name: (milliseconds[name], name)) if size == 2 else group
            counts = {name: sum(order[index % size] == name for index in range(3)) for name in group}
            candidates.append({"cohort": group, "compatible": all(frozenset(pair) in passed
                for pair in itertools.combinations(group, 2)), "assignment_order": order, "role_counts": counts,
                "score_milliseconds": max(counts[name] * milliseconds[name] for name in group)})
    minimum = min(row["score_milliseconds"] for row in candidates if row["compatible"])
    band = ALLOCATION_POLICY["near_minimum"]
    for row in candidates:
        row["within_near_minimum"] = row["compatible"] and (
            row["score_milliseconds"] * band["denominator"] <= minimum * band["numerator"])
    chosen = min((row for row in candidates if row["within_near_minimum"]),
                 key=lambda row: (-len(row["cohort"]), row["score_milliseconds"], row["cohort"]))
    return {"cohort": chosen["cohort"], "assignment_order": chosen["assignment_order"],
            "placement": {"policy": copy.deepcopy(ALLOCATION_POLICY), "weights": weights, "candidates": candidates,
                          "minimum_score_milliseconds": minimum,
                          "selected_score_milliseconds": chosen["score_milliseconds"]}}


def derive_allocation(plan, plan_identity, prepared_identity, roots, artifact_set, *, evidence_out=None):
    require(plan["kind"] in COHORT_KINDS and set(roots) == set(PROBE_WORKERS), "Cohort needs all three probe workers")
    require(plan["allocation_policy"] == ALLOCATION_POLICY, "Preregistered cohort placement policy changed")
    validate_artifact_set(artifact_set, plan, plan_identity, roots)
    probes = [verify_worker(roots[name], name, plan, plan_identity, prepared_identity, probe=True) for name in PROBE_WORKERS]
    require(len({value["host_identity"]["boot_id"] for value in probes}) == 3
            and len({value["worker_execution_id"] for value in probes}) == 3, "Cohort probes need three independent hosted runners")
    admissions = [value["captures"][0]["admission"] for value in probes]
    require(len({value["cwd"] for value in admissions}) == 3
            and len({value["request"]["sha256"] for value in admissions}) == 3, "Cohort probe request/process reused")
    require(all(value["build"] == admissions[0]["build"] for value in admissions),
            "Cohort probe source, backend, renderer, device or Vulkan identity differs")
    comparisons = []
    for left, right in itertools.combinations(PROBE_WORKERS, 2):
        comparison = run.compare_runs(roots[left] / "captures" / ("cohort-probe-" + left),
                                      roots[right] / "captures" / ("cohort-probe-" + right))
        if evidence_out is not None:
            write_json(Path(evidence_out) / "cohort-comparisons" / (left + "-vs-" + right + ".json"), comparison)
        comparisons.append({"left": left, "right": right, "status": comparison["status"]})
    placement = compatible_placement(comparisons, {value["worker"]: value["captures"][0]["admission"]["elapsed_seconds"]
                                                  for value in probes})
    order = placement["assignment_order"]
    captures = copy.deepcopy(plan["captures"])
    shadows = [row for row in captures if row["worker"] == "cohort"]
    require(len(shadows) == 3, "Cohort must allocate exactly the three registered shadows")
    for ordinal, row in enumerate(shadows):
        row["worker"] = order[ordinal % len(order)]
    return {"schema": ALLOCATION_SCHEMA, "kind": plan["kind"], "campaign_id": plan["campaign_id"],
            "plan": plan_identity, "artifact_set_sha256": sha256(canonical(artifact_set)),
            "probes": [{"worker": value["worker"], "worker_execution_id": value["worker_execution_id"],
                        "host_identity": value["host_identity"], "manifest": file_identity(roots[value["worker"]] / "manifest.json"),
                        "started_utc": value["started_utc"], "finished_utc": value["finished_utc"],
                        "build": value["captures"][0]["admission"]["build"],
                        "elapsed_seconds": value["captures"][0]["admission"]["elapsed_seconds"],
                        "request": value["captures"][0]["admission"]["request"],
                        "run": value["captures"][0]["admission"]["run"]} for value in probes],
            "comparisons": comparisons, **placement, "captures": captures,
            "automatic_retries": 0, "qualification_awarded": False}


def _execute(args, *, probe=False):
    out = run.fresh_directory(args.out)
    phase = "probe" if probe else "worker"
    require(out.name == "renderer-sdvk009-" + phase + "-" + args.worker, "Worker output must use its unique assigned directory")
    result = {"schema": COHORT_RECEIPT_SCHEMA if probe else WORKER_SCHEMA, "status": "FAIL", "worker": args.worker,
              "worker_execution_id": uuid.uuid4().hex, "started_utc": run.utc(), "steps": [], "captures": [],
              "hosted_run": {key: os.environ.get(key) for key in HOSTED_KEYS},
              "automatic_retries": 0, "qualification_awarded": False, "physical_gpu_qualified": False,
              "performance_accepted": False}
    try:
        result["host_identity"] = validate_host_identity(host_identity())
        # This durable failure-default receipt precedes even device enumeration.
        write_json(out / (phase + "-start.json"), copy.deepcopy(result))
        plan = load_plan(args.plan, args.expected_commit)
        require(args.worker in (PROBE_WORKERS if probe else plan["workers"]), "Worker is not authorized by this campaign")
        require(not probe or plan["kind"] in COHORT_KINDS, "Separate cohort probe requires its preregistered campaign")
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
        rows = plan["probes"] if probe else plan["captures"]
        if not probe and plan["kind"] in COHORT_KINDS:
            peers = Path(args.peers).resolve(strict=True)
            require(sorted(path.name for path in peers.iterdir()) == sorted(PROBE_WORKERS), "Missing or unexpected cohort peer directory")
            artifact_set = read_json(args.artifact_set)
            allocation = derive_allocation(plan, result["plan"], file_identity(prepared / "prepared.json"),
                {name: peers / name for name in PROBE_WORKERS}, artifact_set, evidence_out=out)
            if args.worker in PROBE_WORKERS:
                own = next(value for value in allocation["probes"] if value["worker"] == args.worker)
                require(own["host_identity"] == result["host_identity"], "Full worker did not execute its own prior cohort probe")
                require(result["started_utc"] >= own["finished_utc"], "Full worker began before its cohort probe finished")
            shutil.copyfile(args.artifact_set, out / "cohort-artifacts.json")
            write_json(out / "allocation.json", allocation)
            result["allocation_sha256"] = sha256(canonical(allocation))
            result["cohort_artifacts"] = pin(out / "cohort-artifacts.json", relative_to=out)
            rows = allocation["captures"]
        write_json(out / (phase + "-registration.json"), copy.deepcopy(result))
        step = native_ci.attempt(out, "preflight", lambda: native_ci.preflight(args, out))
        result["steps"].append(step)
        require(step["status"] == "PASS", "Software-only preflight failed; no capture authorized")
        # Even a worker assigned no full capture retains its explicit empty set.
        (out / "captures").mkdir(exist_ok=False)
        for row in rows:
            if row["worker"] != args.worker:
                continue
            capture_root = out / "captures" / row["name"]
            launch = {"schema": "sdvk009-distributed-launch/v1", "status": "AUTHORIZED",
                      "campaign_id": plan["campaign_id"], "plan": result["plan"], "capture": row,
                      "worker_execution_id": result["worker_execution_id"], "started_utc": run.utc(),
                      "cwd": str(capture_root), "automatic_retries": 0}
            if "allocation_sha256" in result:
                launch["allocation_sha256"] = result["allocation_sha256"]
            launch_path = out / "launches" / (row["name"] + ".json")
            write_json(launch_path, launch)
            step = native_ci.attempt(out, row["name"],
                lambda r=row, p=capture_root: run.capture(_capture_args(args, r, prepared, p)), ("COLLECTED",))
            result["steps"].append(step)
            require(step["status"] == "PASS", "Capture failed; remaining captures in this worker suppressed")
            admission = admit_capture(capture_root, row, plan, file_identity(prepared / "prepared.json"), probe=probe)
            if not probe and plan["kind"] in COHORT_KINDS:
                require(admission["build"] == allocation["probes"][0]["build"],
                        "Full capture source/device identity changed after the cohort probes")
            result["captures"].append({"name": row["name"], "authorization_id": row["authorization_id"],
                                       "launch": pin(launch_path, relative_to=out), "admission": admission})
        result["status"] = "PASS"
    except (OSError, ValueError, KeyError, TypeError) as error:
        result["error"] = str(error)
    except KeyboardInterrupt:
        result.update(status="CANCELLED", error="Capture worker interrupted; incomplete evidence cannot qualify")
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / (phase + ".json"), result)
        _write_seal(out / "manifest.json", {"schema": INVENTORY_SCHEMA, "worker": args.worker,
                    "status": result["status"], "files": inventory(out, exclude=("manifest.json", "manifest.json.sha256"))})
    return result


def worker(args):
    return _execute(args)


def probe(args):
    return _execute(args, probe=True)


def verify_worker(root, worker_name, plan, plan_identity, prepared_identity, *, probe=False, allocation=None):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Worker evidence must be an unaliased directory")
    phase = "probe" if probe else "worker"
    manifest = _read_seal(root / "manifest.json")
    require(set(manifest) == {"schema", "worker", "status", "files"} and manifest["schema"] == INVENTORY_SCHEMA
            and manifest["worker"] == worker_name and manifest["status"] == "PASS", "Worker inventory failed/incomplete")
    require(manifest["files"] == inventory(root, exclude=("manifest.json", "manifest.json.sha256")),
            "Worker raw evidence missing, added or altered")
    result = read_json(root / (phase + ".json"))
    require(result["schema"] == (COHORT_RECEIPT_SCHEMA if probe else WORKER_SCHEMA)
            and result["status"] == "PASS" and result["worker"] == worker_name,
            "Worker failed, cancelled, cross-wired or incomplete")
    require(result["plan"] == plan_identity and result["campaign_id"] == plan["campaign_id"]
            and result["source"] == plan["source"] and result["runtime"] == plan["runtime"]
            and result["kind"] == plan["kind"], "Worker source/runtime/registration differs")
    require(result["automatic_retries"] == 0 and all(result[key] is False for key in
            ("qualification_awarded", "physical_gpu_qualified", "performance_accepted")), "Worker claims unauthorized acceptance")
    require(re.fullmatch(r"[0-9a-f]{32}", result["worker_execution_id"]), "Worker execution identity malformed")
    validate_host_identity(result["host_identity"])
    start = read_json(root / (phase + "-start.json"))
    registration = read_json(root / (phase + "-registration.json"))
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
    rows = plan["probes"] if probe else plan["captures"]
    if not probe and plan["kind"] in COHORT_KINDS:
        require(allocation is not None and read_json(root / "allocation.json") == allocation
                and result["allocation_sha256"] == registration["allocation_sha256"] == sha256(canonical(allocation)),
                "Worker cohort allocation missing or disagrees with authenticated probes")
        artifacts = read_json(checked(root, result["cohort_artifacts"]))
        require(result["cohort_artifacts"]["path"] == "cohort-artifacts.json"
                and registration["cohort_artifacts"] == result["cohort_artifacts"]
                and sha256(canonical(artifacts)) == allocation["artifact_set_sha256"], "Worker cohort artifact set changed")
        if worker_name in PROBE_WORKERS:
            own = next(value for value in allocation["probes"] if value["worker"] == worker_name)
            require(own["host_identity"] == result["host_identity"], "Full worker did not execute its own prior cohort probe")
            require(result["started_utc"] >= own["finished_utc"], "Full worker began before its cohort probe finished")
        rows = allocation["captures"]
    rows = [row for row in rows if row["worker"] == worker_name]
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
        if not probe and plan["kind"] in COHORT_KINDS:
            require(launch["allocation_sha256"] == result["allocation_sha256"], "Capture launch used another cohort allocation")
        admission = admit_capture(root / "captures" / row["name"], row, plan, prepared_identity, probe=probe)
        if not probe and plan["kind"] in COHORT_KINDS:
            require(admission["build"] == allocation["probes"][0]["build"],
                    "Full capture source/device identity changed after the cohort probes")
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
        allocation = None
        capture_rows = plan["captures"]
        if plan["kind"] in COHORT_KINDS:
            found_probes = sorted(path.name.removeprefix("renderer-sdvk009-probe-")
                                  for path in workers_root.glob("renderer-sdvk009-probe-*"))
            require(found_probes == sorted(PROBE_WORKERS), "All three original cohort probe artifacts are required")
            artifact_set = read_json(workers_root / "renderer-sdvk009-worker-publication/cohort-artifacts.json")
            allocation = derive_allocation(plan, plan_identity, prepared_identity,
                {name: workers_root / ("renderer-sdvk009-probe-" + name) for name in PROBE_WORKERS},
                artifact_set, evidence_out=out)
            write_json(out / "cohort-allocation.json", allocation)
            result.update(cohort_allocation=allocation, cohort_allocation_sha256=sha256(canonical(allocation)),
                          orchestration="preregistered-compatibility-cohort-captures")
            capture_rows = allocation["captures"]
        workers = [verify_worker(workers_root / ("renderer-sdvk009-worker-" + name), name,
                                 plan, plan_identity, prepared_identity, allocation=allocation) for name in worker_names]
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
        for row in capture_rows:
            source = workers_root / ("renderer-sdvk009-worker-" + row["worker"]) / "captures" / row["name"]
            _relocate_tree(source, out / "captures" / row["name"], workers_root, relocations, journal)
        provenance_worker = "controls"
        for name in worker_names:
            worker_root = workers_root / ("renderer-sdvk009-worker-" + name)
            if name == provenance_worker:
                _relocate_tree(worker_root / "provenance", out / "provenance", workers_root, relocations, journal)
            _relocate_tree(worker_root, out / "distributed-workers" / name, workers_root, relocations, journal)
        if allocation is not None:
            for name in PROBE_WORKERS:
                _relocate_tree(workers_root / ("renderer-sdvk009-probe-" + name), out / "distributed-probes" / name,
                               workers_root, relocations, journal)
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
        for row in capture_rows:
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
        if plan["kind"] == COHORT_PROBE_KIND:
            control = out / "captures/cohort-proof-shadow-control"
            witness1 = out / "captures/cohort-proof-shadow-witness-1"
            witness2 = out / "captures/cohort-proof-shadow-witness-2"
            result["comparisons"] = []
            for name, left, right in (("control-witness-1", control, witness1),
                                      ("control-witness-2", control, witness2),
                                      ("witness-repeat", witness1, witness2)):
                comparison = run.compare_runs(left, right)
                write_json(out / ("cohort-proof-" + name + "-comparison.json"), comparison)
                result["comparisons"].append(comparison)
                require(comparison["status"] == "PASS", "Post-probe cohort shadows failed original exact comparison")
            result["startup_history"] = []
            for row in capture_rows[1:]:
                history = run.compare_runs(out / "distributed-probes" / row["worker"] / "captures" / ("cohort-probe-" + row["worker"]),
                                           out / "captures" / row["name"])
                write_json(out / (row["name"] + "-startup-history.json"), history)
                result["startup_history"].append({"name": row["name"], "worker": row["worker"], "comparison": history})
            result.update(status="PROBE_PASS", qualification_awarded=False,
                evidence_scope="Short uninstrumented post-probe cohort comparison; startup history descriptive; not full publication qualification")
        elif plan["kind"] == STARTUP_PROBE_KIND:
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
            require(plan["kind"] in (FULL_KIND, COHORT_KIND), "Only original full captures can award publication qualification")
            for name in ("shadow-witness-1", "shadow-witness-2"):
                capture = out / "captures" / name
                proof = publication.validate_witness(capture)
                write_json(out / (name + "-publication.json"), proof)
                controls = publication.negative_controls(capture)
                write_json(out / (name + "-negative-controls.json"), controls)
                require(len(controls["controls"]) == 9 and controls["status"] == "PASS",
                        "All nine original publication negative controls are required")
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
    probes.add_argument("--cohort", action="store_true")
    probes.add_argument("--cohort-probe", action="store_true")
    execution = sub.add_parser("worker")
    execution.add_argument("--worker", choices=WORKERS, required=True)
    execution.add_argument("--plan", type=Path, required=True)
    execution.add_argument("--peers", type=Path)
    execution.add_argument("--artifact-set", type=Path)
    probing = sub.add_parser("probe")
    probing.add_argument("--worker", choices=PROBE_WORKERS, required=True)
    probing.add_argument("--plan", type=Path, required=True)
    assembly = sub.add_parser("assemble")
    assembly.add_argument("--plan", type=Path, required=True)
    assembly.add_argument("--workers", type=Path, required=True)
    for command in (registration, execution, probing):
        for name in ("exe", "iwad", "iwad-license", "runtime-archive"):
            command.add_argument("--" + name, type=Path, required=True)
    for command in (registration, execution, probing, assembly):
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("worker", "probe"):
            def cancelled(signum, frame):
                raise KeyboardInterrupt("worker cancelled")
            signal.signal(signal.SIGTERM, cancelled)
        result = {"register": register, "worker": worker, "probe": probe, "assemble": assemble}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(result["status"] + (": " + result["error"] if "error" in result else ""), flush=True)
    return 0 if result["status"] in ("REGISTERED", "PASS", "PROBE_PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
