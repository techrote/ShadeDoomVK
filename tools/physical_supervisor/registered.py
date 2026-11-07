"""Typed, sealed capture schedules. Collection never implies milestone acceptance.

This profile reuses the diagnostic's native supervisor and oracle adapter. It
admits recipe-derived captures, never caller-supplied commands or callbacks.
The historical fixed diagnostic and unqualified full campaign are unchanged.
"""
import argparse
import importlib
import re
from pathlib import Path

from .common import normalized, pin, read_json, require, verify_pin

KIND = "registered-workload"
PROFILE = "REGISTERED_WORKLOAD"
SCHEMA = "physical-supervisor/registered-workload-v1"
PURPOSES = {"sdvk008-partial-reference", "sdvk008-partial-reference-and-cost",
            "sdvk011-viewmodel", "sdvk014-lifecycle", "sdvk009-fault-discriminator", "sdvk009-shadowoff-scaling"}


def definition(packet):
    row = packet["workload_registration"]
    require(row in packet["files"], "Workload registration is not in packet custody")
    verify_pin(row)
    document = read_json(row["path"])
    pom = document.get("purpose", "").startswith("sdvk008-")
    require(set(document) == {"schema", "profile", "purpose", "scope", "renderer_source", "oracle_source",
                              "build_receipt", "renderer", "iwad", "prepared_manifest", "output_root", "captures"}
            | ({"pom_plan"} if pom else set()), "Unexpected/missing registered workload fields")
    require(document["schema"] == SCHEMA and document["profile"] == PROFILE and
            document["purpose"] in PURPOSES and document["scope"] == "PARTIAL_COLLECTION_ONLY",
            "Unsupported registered workload or acceptance claim")
    require(document["renderer_source"] == packet["source"] and
            document["oracle_source"] == packet.get("oracle_source", packet["source"]),
            "Registered renderer/oracle source differs")
    require(document["build_receipt"] == packet["build_receipt"], "Registered build receipt differs")
    for key, path in (("renderer", packet["renderer"]), ("iwad", packet["iwad"]),
                      ("prepared_manifest", Path(packet["prepared"]) / "prepared.json")):
        require(document[key] == pin(path), "Registered input changed: " + key)
    require(Path(document["output_root"]).is_absolute(), "Registered output root must be absolute")
    rows = document["captures"]
    require(isinstance(rows, list) and rows, "Registered workload has no captures")
    if document["purpose"] == "sdvk009-fault-discriminator":
        require(len(rows) == 1, "A fault discriminator permits exactly one correctness-only creation")
    names = []
    for spec in rows:
        require(set(spec) == {"name", "scene", "recipe_sha256", "mode", "frames", "warmup", "extent",
                              "deadline_seconds", "compare_with"} | ({"collision_snapshot"} if "collision_snapshot" in spec else set()),
                "Unexpected/missing capture controls")
        if "collision_snapshot" in spec:
            require(type(spec["collision_snapshot"]) is bool and document["purpose"] == "sdvk009-fault-discriminator",
                    "CPU collision snapshot is restricted to the one-stage fault discriminator")
        require(isinstance(spec["name"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", spec["name"]) and
                spec["name"] not in names, "Invalid/duplicate registered stage")
        require(isinstance(spec["scene"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", spec["scene"]) and
                re.fullmatch(r"[0-9a-f]{64}", spec["recipe_sha256"]), "Missing scene/recipe identity")
        require(spec["mode"] in ("state", "timing") and type(spec["frames"]) is int and
                1 <= spec["frames"] <= 4096 and type(spec["warmup"]) is int and
                0 <= spec["warmup"] <= 100000, "Invalid registered observer frame budget")
        require(type(spec["deadline_seconds"]) is int and 1 <= spec["deadline_seconds"] <= 600,
                "Registered deadline is not bounded")
        extent = spec["extent"]
        require(isinstance(extent, list) and len(extent) == 2 and all(type(v) is int for v in extent) and
                0 < extent[0] <= 1920 and 0 < extent[1] <= 1080, "Invalid registered extent")
        require(spec["compare_with"] is None or (spec["mode"] == "state" and spec["compare_with"] in names),
                "Comparison must name an earlier state capture")
        if spec["compare_with"] is not None:
            previous = rows[names.index(spec["compare_with"])]
            require(all(spec[key] == previous[key] for key in ("scene", "mode", "frames", "warmup", "extent")),
                    "Repeat comparison must retain the same recipe workload")
        if not pom and document["purpose"] != "sdvk009-shadowoff-scaling":
            require(spec["mode"] == "state", "Viewmodel/lifecycle registration is correctness-only")
        names.append(spec["name"])
    if document["purpose"] == "sdvk009-shadowoff-scaling":
        driver = importlib.import_module("tools.renderer_oracle.sdvk009_shadowoff")
        hashes = {row["scene"]: row["recipe_sha256"] for row in rows}
        require(rows == driver.capture_specs(hashes), "Shadow-off scaling requires its exact twenty-stage schedule")
    return document


def derive_stages(packet, document, run):
    from .prepare import oracle_stage
    stages = []
    recipes = {}
    for spec in document["captures"]:
        if spec["scene"] not in recipes:
            _, _, recipes[spec["scene"]] = run.prepared_scene(packet["prepared"], spec["scene"])
        stages.append(oracle_stage(packet, run, spec, Path(document["output_root"]), recipe=recipes[spec["scene"]]))
    return stages


def validate(packet, *, check_files):
    document = definition(packet)
    require([s["name"] for s in packet["stages"]] == [s["name"] for s in document["captures"]],
            "Registered stage order/count differs")
    # Controls are checked even when expensive source/file verification is
    # explicitly disabled by a CPU fixture. Full validation derives all argv,
    # generated pins, output requirements and comparison paths from the oracle.
    for stage, spec in zip(packet["stages"], document["captures"]):
        capture = stage["capture"]
        require(stage["deadline_seconds"] == spec["deadline_seconds"] and
                all(capture[key] == spec[key] for key in ("scene", "mode", "frames", "warmup")) and
                capture["timeout"] == spec["deadline_seconds"] and
                capture["extent"] == "x".join(map(str, spec["extent"])), "Registered capture controls differ")
    if check_files:
        from .prepare import frozen_oracle
        run = frozen_oracle(packet["oracle_source_root"])
        require(packet["stages"] == derive_stages(packet, document, run), "Registered stage differs from derived recipe")
        if document["purpose"].startswith("sdvk008-"):
            validate_pom(packet, document, run)
        elif document["purpose"] == "sdvk009-shadowoff-scaling":
            importlib.import_module("tools.renderer_oracle.sdvk009_shadowoff").validate_recipes(packet, run)
    return document


def validate_pom(packet, document, run):
    """Reuse the current-source partial plan; never relax frozen full gates."""
    driver = importlib.import_module("tools.renderer_oracle.sdvk008_physical")
    require(hasattr(driver, "current_source_plan"), "Frozen oracle lacks prospective partial POM authority")
    plan_pin = document["pom_plan"]
    require(plan_pin in packet["files"], "POM plan is not in packet custody")
    verify_pin(plan_pin)
    plan = read_json(plan_pin["path"])
    args = argparse.Namespace(current_source_plan=plan_pin["path"], current_source_plan_sha256=plan_pin["sha256"],
        exe=Path(packet["renderer"]), iwad=Path(packet["iwad"]), vulkan_summary=Path(plan["vulkan_summary"]["path"]),
        device_name=packet["telemetry"]["name"], timeout=document["captures"][0]["deadline_seconds"],
        correctness_only=document["purpose"] == "sdvk008-partial-reference", software_fixture_control=False)
    checked, _ = driver.current_source_plan(args)
    require(checked["renderer_source"] == packet["source"] and checked["oracle_source"] == document["oracle_source"] and
            normalized(checked["renderer_source_root"]) == normalized(packet.get("renderer_source_root", packet["oracle_source_root"])),
            "POM plan source differs from native packet")
    for key in ("owner_authorization", "generation", "iwad_license", "vulkan_summary"):
        p = checked[key]
        require(any(normalized(r["path"]) == normalized(p["path"]) and r["sha256"] == p["sha256"] and
                    r["size"] == p["bytes"] for r in packet["files"]), "POM authority/preflight input is not in custody")
    preflight = driver.vulkan_preflight(args.vulkan_summary, args.device_name)
    driver.runtime_vulkan_identity({"vulkan": packet["native_device"]}, preflight)
    contract, catalog = driver.fixture_contract(), run.preparation_module().load_catalog()
    driver.validate_fixtures(contract, catalog, correctness_only=True)
    pairs = [p for p in contract.CORRECTNESS_PAIRS if p["id"] in driver.PARTIAL_PAIRS]
    driver.prepared_pair_continuity(read_json(Path(packet["prepared"]) / "prepared.json"), pairs)
    ids = sorted({p[k] for p in pairs for k in ("off", "on", "background") if k in p})
    expected = []
    for scene in ids:
        for attempt in (1, 2):
            expected.append((scene, "state", 1, 120, [640, 480], attempt == 2))
    if not args.correctness_only:
        for variant in driver.PARTIAL_VARIANTS:
            for attempt in (1, 2):
                expected.append((contract.TIMING_VARIANTS[variant], "state", 1, 120, [1904, 1001], attempt == 2))
        for order in checked["protocol"]["timing_orders"]:
            for variant in order:
                expected.append((contract.TIMING_VARIANTS[variant], "timing", 120, 120, [1904, 1001], False))
    rows = document["captures"]
    require(len(rows) == len(expected) and len(rows) in (16, 26), "POM partial process count differs")
    for index, (spec, expected_row) in enumerate(zip(rows, expected)):
        scene, mode, frames, warmup, extent, repeat = expected_row
        require([spec[k] for k in ("scene", "mode", "frames", "warmup", "extent")] ==
                [scene, mode, frames, warmup, extent] and spec["deadline_seconds"] == args.timeout and
                spec["compare_with"] == (rows[index - 1]["name"] if repeat else None),
                "POM partial schedule/order/repeat policy differs")
    return driver, pairs


def after_capture(packet, stage, run):
    """Retain typed per-process controls beyond generic capture integrity."""
    if packet.get("kind") != KIND:
        return None
    verify_pin(packet["workload_registration"])
    document = read_json(packet["workload_registration"]["path"])
    if document["purpose"] == "sdvk009-shadowoff-scaling":
        return importlib.import_module("tools.renderer_oracle.sdvk009_shadowoff").validate_capture(packet, stage, run)
    if not document["purpose"].startswith("sdvk008-"):
        return None
    driver = importlib.import_module("tools.renderer_oracle.sdvk008_physical")
    plan = read_json(document["pom_plan"]["path"])
    preflight = driver.vulkan_preflight(Path(plan["vulkan_summary"]["path"]), packet["telemetry"]["name"])
    out = Path(stage["capture"]["out"])
    result = read_json(out / "run.json")
    driver.physical_build(result["build"], commit=packet["source"]["commit"], device_name=packet["telemetry"]["name"])
    driver.runtime_vulkan_identity(result["build"], preflight)
    reference_out = Path(packet["stages"][0]["capture"]["out"])
    if out != reference_out:
        driver.continuity(read_json(reference_out / "run.json"), result)
        request, reference = read_json(out / "request.json"), read_json(reference_out / "request.json")
        require(all(request[key] == reference[key] for key in ("host", "environment")),
                "POM host/loader/layer environment changed")
    witness = driver.relief_draw_witness(out) if stage["capture"]["mode"] == "state" else driver.timing_integrity(out)
    receipt = {"schema": "physical-supervisor/pom-partial-capture-v1", "status": "PASS",
               "scope": "PARTIAL_COLLECTION_ONLY_FULL_ACCEPTANCE_HELD", "witness": witness}
    if document["purpose"] == "sdvk008-partial-reference" and stage["name"] == packet["stages"][-1]["name"]:
        receipt["reference_gate"] = reference_gate(packet, run, require_pass=False)
    return receipt


def before_capture(packet, stage, run):
    """First timing creation is conditional on its typed correctness/image gates.

    Called in the owned collector before capture/target registration. Its same
    30-second preparation bound and parent heartbeat/fault observers still apply.
    No renderer or other child is launched by this pure validation step.
    """
    if packet.get("kind") != KIND or stage["capture"]["mode"] != "timing":
        return None
    document = definition(packet)
    if document["purpose"] == "sdvk009-shadowoff-scaling":
        timing = [s for s in packet["stages"] if s["capture"]["mode"] == "timing"]
        if stage["name"] == timing[0]["name"]:
            return importlib.import_module("tools.renderer_oracle.sdvk009_shadowoff").reference_gate(packet, run)
        return None  # existing ledger requires every prior timing stage/fence
    require(document["purpose"] == "sdvk008-partial-reference-and-cost", "Unregistered timing scope")
    timing = [s for s in packet["stages"] if s["capture"]["mode"] == "timing"]
    if stage["name"] != timing[0]["name"]:
        return None  # ledger admits these only after the first timing is fenced
    return reference_gate(packet, run, require_pass=True)


def reference_gate(packet, run, *, require_pass):
    """Original partial-reference rule: reject FAIL; timing additionally needs PASS."""
    driver = importlib.import_module("tools.renderer_oracle.sdvk008_physical")
    contract = driver.fixture_contract()
    pairs = [p for p in contract.CORRECTNESS_PAIRS if p["id"] in driver.PARTIAL_PAIRS]
    paths = {}
    reference = None
    for previous in packet["stages"]:
        capture = previous["capture"]
        if capture["mode"] == "timing":
            break
        out = Path(capture["out"])
        run.validate_run(out)
        result = read_json(out / "run.json")
        if reference is None:
            reference = result
        else:
            driver.continuity(reference, result)
        paths.setdefault((capture["extent"], capture["scene"]), []).append(out)
    for repeats in paths.values():
        require(len(repeats) == 2 and run.compare_runs(*repeats)["status"] == "PASS", "POM reference repeat failed")
    witnesses = {}
    for pair in pairs:
        witnesses[pair["id"]] = []
        for attempt in (0, 1):
            off, on = (paths["640x480", pair[key]][attempt] for key in ("off", "on"))
            raw_pair = driver.controlled_pair(off, on)
            background = paths["640x480", pair["background"]][attempt] if "background" in pair else None
            witness = driver.image_pair(off, on, pair["oracle"], background=background)
            if pair["id"].startswith("single-") and hasattr(contract, "source_projected_marker_direction"):
                direction = driver.source_projected_direction_witness(off, on, raw_pair=raw_pair)
                witness["source_projected_directional_marker"] = direction
                if direction["status"] == "FAIL":
                    witness["status"] = "FAIL"
                elif direction["status"] != "PASS" and witness["status"] != "FAIL":
                    witness["status"] = "INCONCLUSIVE"
            require(witness["status"] != "FAIL" and (not require_pass or witness["status"] == "PASS"),
                    "POM OFF/ON reference gate did not pass: " + pair["id"])
            witnesses[pair["id"]].append(witness)
    status = "PASS" if all(w["status"] == "PASS" for rows in witnesses.values() for w in rows) else "INCONCLUSIVE"
    return {"schema": "physical-supervisor/pom-partial-reference-gate-v1", "status": status,
            "scope": "PARTIAL_REFERENCE_ONLY_FULL_ACCEPTANCE_HELD", "image_pairs": witnesses,
            "missing_full_gates": list(contract.MISSING_GATES)}
