"""No-launch diagnostic packet construction using the frozen oracle recipes."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import shutil

from .common import exclusive, normalized, pin, require, utc, validate_packet, environment_policy, read_registry_policy, REGISTRY_KEYS, read_registry_enumeration_policy, DISPLAY_CLASS, CONTROL_VIDEO, linklike


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
        if name == "tools.renderer_oracle" or name.startswith("tools.renderer_oracle."):
            del sys.modules[name]
    import tools
    tools.__path__ = [str(Path(root) / "tools")]
    return importlib.import_module("tools.renderer_oracle.run")


def diagnostic_packet(seed):
    """Return a complete packet; never create stage directories or run EXEs.

    Seed supplies actual host/readback/expiry/source paths and runtime roots.
    Every root is a closed recursive file inventory, not a wildcard allow-list.
    """
    packet = dict(seed)
    for path in [*(row["path"] for row in seed.get("runtime_roots",[])),seed["oracle_source_root"],
                 seed["prepared"],Path(seed["iwad"]).parent]:
        checked_directory(path)
    packet.update(schema="physical-supervisor/packet-v1", kind="diagnostic", automatic_retries=0,
                  monitor={"gpu_seconds": 1, "event_seconds": 5, "reader_timeout_seconds": 10,
                           "completion_grace_seconds": 15}, temperature_limit_c=seed.get("temperature_limit_c", 80))
    packet.setdefault("created_utc", utc())
    packet.setdefault("environment_policy", environment_policy(packet.get("environment_extra_keys", ())))
    packet.setdefault("registry_policy", read_registry_policy([{"hive":hive,"key":key} for hive in ("HKLM","HKCU") for key in REGISTRY_KEYS]))
    packet.setdefault("registry_enumeration_policy", read_registry_enumeration_policy([{"hive":"HKLM","key":key} for key in (DISPLAY_CLASS,CONTROL_VIDEO)]))
    packet.setdefault("git", shutil.which("git"))
    require(packet["git"], "Read-only source verification requires a pinned Git executable")
    commit = packet["source"]["commit"]
    packet["declared_version_utf8"] = f"ShadeDoomVK declared expected build\nCommit: {commit}\nWorking tree: clean\n"
    run = frozen_oracle(packet["oracle_source_root"])
    base = Path(packet.pop("stage_output_root")).resolve()
    require(not base.exists(), "Stage output root must be fresh")
    stages = []
    for name, scene in (("compositing", "compositing"), ("shadow-boundary-1", "shadow-boundary"), ("shadow-boundary-2", "shadow-boundary")):
        _, prepared, recipe = run.prepared_scene(packet["prepared"], scene)
        native = recipe["native"]
        out = base / name
        config = str(out / "fixture.ini")
        script = str(out / "capture.cfg")
        substitutions = {"exe": packet["renderer"], "iwad": str(out / "input" / Path(packet["iwad"]).name),
                         "pk3": str(out / "input/scene.pk3"), "config": config, "capture_script": script}
        argv = run.apply_extent([part.format(**substitutions) for part in native["argv"]], [640, 480])
        run.validate_bootstrap_argv(native, argv)
        argv += ["-savedir", str(out / "save"), "-sdvkobserve", run._console_path(out / "native"),
                 "-sdvkobserveframes", "1", "-sdvkobservewarmup", "120", "-sdvkobservemode", "state",
                 "-sdvkobservecache", run._console_path(out / "cache"), "-sdvkobservequit"]
        copies = [(packet["iwad"], out / "input" / Path(packet["iwad"]).name),
                  (Path(packet["prepared"]) / native["pk3"], out / "input/scene.pk3"),
                  (Path(packet["prepared"]) / native["config"], out / "fixture.ini"),
                  (Path(packet["prepared"]) / native["config"], out / "input/fixture.ini"),
                  (Path(packet["prepared"]) / native["capture_script"], out / "capture.cfg")]
        generated = [{**pin(source), "path": str(target)} for source, target in copies]
        capture = {"exe": packet["renderer"], "iwad": packet["iwad"], "prepared": packet["prepared"],
                   "out": str(out), "scene": scene, "mode": "state", "frames": 1, "warmup": 120,
                   "timeout": 180, "gpu": False, "include_stress": True, "image_policy": "exact", "extent": "640x480",
                   "expected_commit": commit, "require_clean": True}
        stage = {"name": name, "mode": "oracle", "deadline_seconds": 180, "expected_argv": argv,
                 "generated_pins": generated, "capture": capture,
                 "mutable_runtime_config": next(row for row in generated if Path(row["path"]) == out / "fixture.ini"),
                 "required_outputs": ["run.json", "request.json", "native.renderer.json", "native.png", "stdout.log", "stderr.log"]}
        if name == "shadow-boundary-2":
            stage["compare_with"] = str(base / "shadow-boundary-1")
        stages.append(stage)
    packet["stages"] = stages
    roots = [Path(row["path"]) for row in packet.get("runtime_roots", [])]
    roots += [Path(__file__).resolve().parent, Path(packet["oracle_source_root"]) / "tools/renderer_oracle",
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
