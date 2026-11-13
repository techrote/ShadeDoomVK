"""No-launch diagnostic packet construction using the frozen oracle recipes."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import shutil

from .common import exclusive, normalized, pin, require, utc, validate_packet, environment_policy, read_registry_policy, REGISTRY_KEYS, read_registry_enumeration_policy, DISPLAY_CLASS, CONTROL_VIDEO, linklike, INTEGRITY_POLICY


def checked_directory(path):
    """Reject reparse aliases before canonicalization can erase their identity."""
    original=Path(path)
    for part in [original,*original.parents]:
        require(not linklike(part),"Preparation root/ancestor is a link/junction")
    require(original.is_dir(),"Preparation root is not a directory")
    require(not any(linklike(child) for child in original.rglob("*")),"Preparation root contains a link/junction")
    return original.resolve(strict=True)


def frozen_oracle(root):
    for name in list(sys.modules):
        if name in ("tools.renderer_oracle","tools.pf_oracle") or name.startswith(("tools.renderer_oracle.","tools.pf_oracle.")):
            del sys.modules[name]
    import tools
    tools.__path__ = [str(Path(root) / "tools")]
    run=importlib.import_module("tools.renderer_oracle.run")
    require(normalized(run.__file__)==normalized(Path(root)/"tools/renderer_oracle/run.py"),"Wrong frozen oracle import origin")
    return run


def observer_argv(run, native, out, capture):
    """Mirror the pinned capture adapter's observer/lifecycle flag order."""
    argv = ["-savedir", str(out / "save"), "-sdvkobserve", run._console_path(out / "native"),
            "-sdvkobserveframes", str(capture["frames"]), "-sdvkobservewarmup", str(capture["warmup"]),
            "-sdvkobservemode", capture["mode"], "-sdvkobservecache", run._console_path(out / "cache"), "-sdvkobservequit"]
    if capture["gpu"]:
        argv.append("-sdvkobservegpu")
    for field, flag in (("probe_owner_trace", "-sdvkprobeownertrace"),
                        ("sampler_reset_schedule", "-sdvk153samplerresetdriver"),
                        ("lightmap_transition_schedule", "-sdvk158lightmapdriver"),
                        ("special_surface_schedule", "-sdvk161surfacedriver")):
        if native.get(field):
            require(capture["mode"] == "state", "Lifecycle driver is state-only")
            argv.append(flag)
    if native.get("generator") == "gameplay_smoke":
        require(capture["mode"] == "state" and not capture["gpu"] and
                capture["frames"] == 128 and capture["warmup"] == 32,
                "Gameplay input driver needs its exact correctness-only frame budget")
        argv.append("-sdvkgameplaysmoke")
    if capture.get("collision_snapshot", False):
        require(capture["mode"] == "state" and not capture["gpu"], "CPU collision snapshot is state-only")
        argv += ["-sdvkcollisionsnapshot", run._console_path(out / "collision")]
    return argv


def oracle_stage(packet, run, spec, base, *, recipe=None):
    """Derive one exact capture from a verified recipe; accept no caller argv."""
    name, scene = spec["name"], spec["scene"]
    if recipe is None:
        _, _, recipe = run.prepared_scene(packet["prepared"], scene)
    if "recipe_sha256" in spec:
        require(run.sha256(run.canonical(recipe)) == spec["recipe_sha256"], "Registered recipe differs")
    native = recipe["native"]
    gameplay_outputs = []
    if native.get("generator") == "gameplay_smoke":
        from .registered import KIND, definition
        from tools.renderer_oracle.gameplay_smoke import validate_recipe, checkpoint_names
        validate_recipe(recipe)
        require(packet.get("kind") == KIND, "Gameplay smoke requires the registered profile")
        registration = definition(packet)
        require(registration["purpose"] == "sdvk011-viewmodel" and len(registration["captures"]) == 1
                and spec["mode"] == "state" and spec["frames"] == 128 and spec["warmup"] == 32
                and spec["extent"] == [640, 480] and spec.get("compare_with") is None,
                "Gameplay smoke requires one exact registered viewmodel capture without dynamic comparison")
        gameplay_outputs = sorted(checkpoint_names())
    out = base / name
    substitutions = {"exe": packet["renderer"], "iwad": str(out / "input" / Path(packet["iwad"]).name),
                     "pk3": str(out / "input/scene.pk3"), "config": str(out / "fixture.ini"),
                     "capture_script": str(out / "capture.cfg")}
    argv = run.apply_extent([part.format(**substitutions) for part in native["argv"]], spec["extent"])
    run.validate_bootstrap_argv(native, argv)
    copies = [(packet["iwad"], out / "input" / Path(packet["iwad"]).name),
              (Path(packet["prepared"]) / native["pk3"], out / "input/scene.pk3"),
              (Path(packet["prepared"]) / native["config"], out / "fixture.ini"),
              (Path(packet["prepared"]) / native["config"], out / "input/fixture.ini"),
              (Path(packet["prepared"]) / native["capture_script"], out / "capture.cfg")]
    generated = [{**pin(source), "path": str(target)} for source, target in copies]
    if spec["extent"] != native["extent"]:
        script_source, script_target = copies[-1]
        script = script_source.read_bytes()
        require(run.sha256(script) == generated[-1]["sha256"] and len(script) == generated[-1]["size"],
                "Prepared capture script changed during stage derivation")
        effective = run.capture_script_at_extent(script, native["extent"], spec["extent"])
        generated[-1] = {"path": str(script_target), "sha256": run.sha256(effective), "size": len(effective)}
    capture = {"exe": packet["renderer"], "iwad": packet["iwad"], "prepared": packet["prepared"],
               "out": str(out), "scene": scene, "mode": spec["mode"], "frames": spec["frames"],
               "warmup": spec["warmup"], "timeout": spec["deadline_seconds"], "gpu": spec["mode"] == "timing",
               "include_stress": True, "image_policy": "exact", "extent": "x".join(map(str, spec["extent"])),
               "expected_commit": packet["source"]["commit"], "require_clean": True}
    if "iwad_support" in packet:
        capture["iwad_support"] = packet["iwad_support"]
    if "collision_snapshot" in spec:
        capture["collision_snapshot"] = spec["collision_snapshot"]
    argv += observer_argv(run, native, out, capture)
    stage = {"name": name, "mode": "oracle", "deadline_seconds": spec["deadline_seconds"],
             "expected_argv": argv, "generated_pins": generated, "capture": capture,
             "mutable_runtime_config": next(row for row in generated if Path(row["path"]) == out / "fixture.ini"),
             "required_outputs": ["run.json", "request.json", "native.renderer.json"] +
                 (["native.png"] if spec["mode"] == "state" else []) + ["stdout.log", "stderr.log"]}
    if spec.get("compare_with"):
        stage["compare_with"] = str(base / spec["compare_with"])
    if capture.get("collision_snapshot", False):
        stage["required_outputs"].append("collision-1.bin")
    stage["required_outputs"] += gameplay_outputs
    return stage


def diagnostic_packet(seed):
    return _packet(seed)


def registered_packet(seed, registration):
    """Prepare a sealed typed schedule, never execute a renderer."""
    return _packet(seed, registration)


def _packet(seed, registration=None):
    """Return a complete packet; never create stage directories or run EXEs.

    Seed supplies actual host/readback/expiry/source paths and runtime roots.
    Every root is a closed recursive file inventory, not a wildcard allow-list.
    """
    packet = dict(seed)
    for path in [*(row["path"] for row in seed.get("runtime_roots",[])),seed["oracle_source_root"],
                 seed["prepared"],Path(seed["iwad"]).parent]:
        checked_directory(path)
    packet.update(schema="physical-supervisor/packet-v1", kind="registered-workload" if registration else "diagnostic", automatic_retries=0,
                  integrity_policy=dict(INTEGRITY_POLICY),
                  monitor={"gpu_seconds": 1, "event_seconds": 5, "reader_timeout_seconds": 10,
                           "completion_grace_seconds": 15}, temperature_limit_c=seed.get("temperature_limit_c", 80))
    packet.setdefault("created_utc", utc())
    # setdefault evaluates its default eagerly, even for a supplied policy.
    # Synthetic CPU controls supply their authority explicitly; native reads
    # remain mandatory in validate_packet, never incidental default evaluation.
    if "environment_policy" not in packet:
        packet["environment_policy"] = environment_policy(packet.get("environment_extra_keys", ()))
    if "registry_policy" not in packet:
        packet["registry_policy"] = read_registry_policy([{"hive":hive,"key":key} for hive in ("HKLM","HKCU") for key in REGISTRY_KEYS])
    if "registry_enumeration_policy" not in packet:
        packet["registry_enumeration_policy"] = read_registry_enumeration_policy([{"hive":"HKLM","key":key} for key in (DISPLAY_CLASS,CONTROL_VIDEO)])
    packet.setdefault("git", shutil.which("git"))
    require(packet["git"], "Read-only source verification requires a pinned Git executable")
    commit = packet["source"]["commit"]
    packet["declared_version_utf8"] = f"ShadeDoomVK declared expected build\nCommit: {commit}\nWorking tree: clean\n"
    run = frozen_oracle(packet["oracle_source_root"])
    base = Path(packet.pop("stage_output_root")).resolve()
    require(not base.exists(), "Stage output root must be fresh")
    if registration:
        packet["workload_registration"] = pin(registration)
        packet["files"] = [*packet.get("files", []), packet["workload_registration"]]
        from .registered import definition, derive_stages
        document = definition(packet)
        require(Path(document["output_root"]) == base, "Registered output root differs from seed")
        packet["stages"] = derive_stages(packet, document, run)
    else:
        packet["stages"] = [oracle_stage(packet, run, {"name": name, "scene": scene, "mode": "state", "frames": 1,
            "warmup": 120, "extent": [640, 480], "deadline_seconds": 180,
            "compare_with": "shadow-boundary-1" if name == "shadow-boundary-2" else None}, base)
            for name, scene in (("compositing", "compositing"), ("shadow-boundary-1", "shadow-boundary"),
                                ("shadow-boundary-2", "shadow-boundary"))]
    roots = [Path(row["path"]) for row in packet.get("runtime_roots", [])]
    roots += [Path(__file__).resolve().parent, Path(packet["oracle_source_root"]) / "tools/renderer_oracle",
              Path(packet["oracle_source_root"]) / "tools/pf_oracle",
              Path(packet["oracle_source_root"]) / "specs", Path(packet["prepared"]), Path(packet["iwad"]).parent]
    unique = {str(checked_directory(path)): path for path in roots}
    packet["runtime_roots"] = [{"path": str(path.resolve()), "files": [str(p.resolve()) for p in sorted(path.rglob("*")) if p.is_file()]}
                               for path in unique.values()]
    paths = {normalized(row["path"]): Path(row["path"]) for row in packet.get("files", [])}
    for root in packet["runtime_roots"]:
        for name in root["files"]:
            paths[normalized(name)] = Path(name)
    from .common import read_json
    build = read_json(packet["build_receipt"]["path"])
    for name in (packet["python"], packet["renderer"], packet["nvidia_smi"], packet["git"],
                 packet["build_receipt"]["path"], build["source_snapshot"]["path"], build["executable"]["path"]):
        paths[normalized(name)] = Path(name)
    packet["files"] = [pin(path) for _, path in sorted(paths.items())]
    packet["renderer_sha256"] = pin(packet["renderer"])["sha256"]
    validate_packet(packet)
    return packet
