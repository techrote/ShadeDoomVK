"""Review/contain one instance-only worker. No device/renderer launch interface.

This is a separate prospective experiment, never a release of historical STOP.
Callers must retain the actual user's instruction and the reviewed exact plan.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import time

from .common import (Journal, Stop, canonical, exclusive, future, normalized,
                     pin, read_json, require, sealed_environment, verify_pin,
                     verify_registry, verify_roots)
from .readers import bounded_host_identity, check_host_identity, continuity, telemetry
from .supervisor import ModuleWatch, Watch
from .vulkan_inventory import verify_manifest_closure
from .windows import FileLock, Job, Process, RootGuard, platform_check


LIMITS = {"instance_create_calls": 1, "logical_devices_created": 0, "queue_submissions": 0,
          "deadline_seconds": 30, "completion_grace_seconds": 15, "automatic_retries": 0}


def plan_digest(plan):
    return hashlib.sha256(canonical(plan)).hexdigest()


def validate_plan(plan):
    require(plan["schema"] == "sdvk009-instance-attestation-plan/v1", "Unsupported attestation plan")
    require(plan["limits"] == LIMITS, "Instance attestation limits changed")
    require(plan["argv"] == [plan["probe"], "--instance-attestation-only"], "Probe command changed")
    require(plan["physical_gate"] == "HELD / NOT ACCEPTED", "Attestation must not qualify physical gate")
    require(Path(plan["claim_root"]).is_absolute(), "Attestation claim root must be absolute")
    future(plan["expires_utc"])
    require(plan["files"] and plan["runtime_roots"], "Missing closed attestation inputs")
    paths = [normalized(row["path"]) for row in plan["files"]]
    require(len(paths) == len(set(paths)), "Duplicate attestation input")
    require(normalized(plan["probe"]) in paths, "Attestation executable is not pinned")
    require(normalized(plan["nvidia_smi"]) in paths, "Telemetry executable is not pinned")
    for row in plan["files"]:
        verify_pin(row)
    verify_roots(plan)
    verify_registry(plan)
    sealed_environment(plan)
    verify_manifest_closure(plan)
    return plan_digest(plan)


def validate_review(plan, review):
    require(review["schema"] == "sdvk009-instance-attestation-review/v1", "Wrong attestation review schema")
    require(review["plan_sha256"] == plan_digest(plan), "Review belongs to a different plan")
    require(review["decision"] == "REVIEWED_ONE_INSTANCE_ONLY_ATTEMPT", "Attestation review is held")
    require(review["blocking_findings"] == [], "Open blocking attestation findings")
    require(review["user_authorization_verbatim"].strip(), "Actual user authorization is missing")
    require(review["reviewer_provenance"].strip(), "Review provenance missing")
    future(review["expires_utc"])
    require(review["cpu_evidence"], "CPU qualification receipts missing")
    for row in review["cpu_evidence"]:
        verify_pin(row)


def device_readback(plan, result):
    """Select exactly the preregistered PCI device; never substitute PCI for VK fields."""
    require(result["schema"] == "sdvk009-instance-readback/v1" and
            result["status"] == "NATIVE_READBACK_ONLY_NOT_PHYSICAL_QUALIFICATION", "Worker did not produce native readback")
    require(type(result["instance_create_calls"]) is int and result["instance_create_calls"] == 1 and
            type(result["logical_devices_created"]) is int and result["logical_devices_created"] == 0 and
            type(result["queue_submissions"]) is int and result["queue_submissions"] == 0 and
            result["instance_destroyed"] is True, "Worker exceeded instance-only scope or did not clean up")
    require(isinstance(result["devices"], list) and 0 < len(result["devices"]) <= 16, "Unbounded device inventory")
    expected = plan["expected_device"]
    for row in result["devices"]:
        if row.get("pci_bus_info_available") is True:
            pci = row.get("pci")
            require(isinstance(pci, dict) and set(pci) == {"domain", "bus", "device", "function"} and
                    all(type(value) is int and 0 <= value <= 0xffffffff for value in pci.values()),
                    "Malformed native PCI properties")
    selected = [row for row in result["devices"] if row.get("vendor_id") == expected["vendor_id"] and
                row.get("device_id") == expected["device_id"] and row.get("pci_bus_info_available") is True and
                row.get("pci") == expected["pci"]]
    require(len(selected) == 1, "Native device cannot be uniquely correlated to reviewed PCI identity")
    device = selected[0]
    native = {key: device[key] for key in ("vendor_id", "device_id", "device_type", "driver_version_raw")}
    from .common import verify_native_device
    verify_native_device(native)
    require(device["device_type"] == expected["device_type"], "Native device type differs")
    modules = result["modules_during_instance"]
    require(isinstance(modules, list) and 0 < len(modules) <= 1024 and all(isinstance(p, str) for p in modules),
            "Missing worker module observations")
    names = [normalized(path) for path in modules]
    require(len(names) == len(set(names)), "Duplicate worker module observations")
    require(all(normalized(path) in names for path in plan["module_policy"]["required_paths"]),
            "Required loader was not observed during instance")
    return {"native_device": native, "selected_device": device, "module_paths": names,
            "scope": "INSTANCE_PROPERTIES_ONLY_NOT_RENDERER_DIAGNOSTIC_OR_STABILITY_PROOF"}


def execute_probe(plan, review, output, *, readers=None):
    """One owned attempt. No retries; permanent failure evidence stays latched."""
    platform_check()
    digest = validate_plan(plan)
    validate_review(plan, review)
    output = Path(output).resolve()
    require(not output.exists(), "Attestation output must be fresh")
    # The plan-specific guard root prevents a second attempt at another output.
    claim_root = Path(plan["claim_root"])
    claim_root.mkdir(exist_ok=False)
    exclusive(claim_root / "claim.json", {"plan_sha256": digest, "review": review, "scope": "ONE_INSTANCE_ONLY"})
    exclusive(claim_root / "HELD.json", {"status": "HELD", "physical_qualification": False})
    output.mkdir()
    journal = Journal(output / "journal")
    exclusive(output / "plan.json", plan)
    exclusive(output / "review.json", review)
    packet = {**plan, "packet_sha256": digest, "stop_root": str(claim_root), "temperature_limit_c": 80}
    child = identity = watch = roots = job = modules = None
    locks = ExitStack()
    result = {"status": "FAILED_STOP", "physical_gate": "HELD / NOT ACCEPTED", "renderer_runs": 0}
    try:
        for row in plan["files"]:
            lock = FileLock(row)
            locks.callback(lock.close)
        roots = RootGuard(plan)
        check_host_identity(plan["host_identity"], bounded_host_identity())
        watch = Watch(packet, plan["event_baseline"], journal, readers)
        raw = watch.readers.call("telemetry")
        journal.append("preflight-telemetry", {"raw_utf8": raw.decode(errors="replace"),
            "readback": telemetry(raw, plan["telemetry"], 80)})
        snapshot = watch.readers.call("event", plan["event_baseline"])
        watch.baseline = continuity(plan["event_baseline"], snapshot)
        journal.append("preflight-events", snapshot)
        watch.start()
        job = Job()
        with (output / "stdout.txt").open("xb") as stdout, (output / "stderr.txt").open("xb") as stderr:
            owner = Process.open(os.getpid())
            try: owner_identity = owner.identity()
            finally: owner.close()
            argv = [*plan["argv"], str(owner_identity["pid"]), str(owner_identity["creation_ticks"])]
            def boundary():
                future(plan["expires_utc"]); future(review["expires_utc"])
                watch.check(); roots.check(); verify_registry(plan); sealed_environment(plan)
                check_host_identity(plan["host_identity"], bounded_host_identity())
                require(not list(claim_root.glob("STOP*")), "Attestation STOP is latched")
            boundary()
            child = Process.spawn(argv, output, stdout, stderr, env=sealed_environment(plan), job=job,
                                  before_create=boundary)
            identity = child.identity()
            journal.append("suspended-probe-identity", identity)
            require(not getattr(child, "assignment_error", None), "Probe containment job assignment failed")
            require(job.pids() == {identity["pid"]}, "Unexpected process in probe job")
            watch.check(); roots.check()
            check_host_identity(plan["host_identity"], bounded_host_identity())
            started = time.monotonic()
            child.resume(identity, before_resume=boundary)
            deadline = started + LIMITS["deadline_seconds"]
            modules = ModuleWatch(packet, child, identity, journal, watch, target_deadline=deadline)
            modules.start()
            while child.poll() is None:
                watch.check(); roots.check()
                require(time.monotonic() < deadline, "Instance probe deadline exceeded")
                require(job.pids() <= {identity["pid"]}, "Unexpected child of instance probe")
                for path in [output / "stdout.txt", output / "stderr.txt"]:
                    require(path.stat().st_size <= 1024 * 1024, "Probe output exceeds retained evidence budget")
                time.sleep(.02)
            journal.append("probe-exit", {"identity": identity, "returncode": child.poll()})
        # The worker's pinned code records modules while the instance is live;
        # an exited fast worker need not satisfy a later periodic sample.
        modules.finish(require_complete=False)
        require(child.poll() == 0, "Instance probe failed")
        stderr = (output / "stderr.txt").read_bytes()
        require(not stderr, "Instance probe emitted unexpected stderr")
        readback = device_readback(plan, read_json(output / "stdout.txt"))
        # Validate/hashes the exact modules observed by the worker even if it
        # exited too quickly for a periodic sample to include the loaded ICD.
        expected = {normalized(row["path"]): row for row in plan["files"]}
        system = Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve()
        observed = []
        for path in readback["module_paths"]:
            actual = pin(path)
            if path in expected:
                require(all(actual[key] == expected[path][key] for key in ("sha256", "size")),
                        "Worker observed changed preregistered module")
            else:
                require(Path(path).is_relative_to(system) and not Path(path).name.casefold().startswith(("nv", "vulkan", "graphics-hook")),
                        "Worker observed unreviewed driver/layer/external module")
            observed.append(actual)
        until = time.monotonic() + LIMITS["completion_grace_seconds"]
        while time.monotonic() < until:
            watch.check(); roots.check(); time.sleep(.02)
        final = watch.readers.call("event", watch.baseline)
        watch.baseline = continuity(watch.baseline, final)
        journal.append("completion-event-fence", final)
        require(job.pids() == set(), "Probe job still contains children")
        exclusive(output / "native-attestation.json", {**readback, "observed_modules": observed,
            "plan_sha256": digest, "physical_gate": "HELD / NOT ACCEPTED"})
        result["status"] = "NATIVE_ATTESTATION_RETAINED_PENDING_REVIEW"
    except BaseException as error:
        result["error"] = str(error)
        result["partial_evidence"] = getattr(error, "evidence", None)
        # Receipt failures must never skip containment of an authenticated child.
        try:
            if child is not None and identity is not None and child.poll() is None:
                child.kill(identity)
        finally:
            for label, action in [("stop", lambda: exclusive(claim_root / "STOP.json", result)),
                                  ("journal", lambda: journal.append("failure", result))]:
                try: action()
                except BaseException as receipt_error: result[label + "_receipt_error"] = str(receipt_error)
    finally:
        if modules is not None:
            try: modules.finish(require_complete=False)
            except BaseException as error: result.update(status="FAILED_STOP", final_module_error=str(error))
        if watch is not None:
            try: watch.finish()
            except BaseException as error: result.update(status="FAILED_STOP", final_observer_error=str(error))
        if result["status"] == "FAILED_STOP" and not (claim_root / "STOP.json").exists():
            try: exclusive(claim_root / "STOP.json", result)
            except BaseException as error: result["final_stop_receipt_error"] = str(error)
        if child is not None: child.close()
        if job is not None: job.close()
        if roots is not None: roots.close()
        locks.close()
        exclusive(output / "result.json", result)
    return result
