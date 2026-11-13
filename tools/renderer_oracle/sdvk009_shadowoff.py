"""Bounded shadow-off scaling collection; never SDVK-009 acceptance.

The registered native supervisor owns every creation. This module only derives
the twenty-stage schedule and validates existing observer/state/image evidence.
No subprocess, renderer launch, new counter or GPU instrumentation lives here.
"""
from __future__ import annotations

import copy
from pathlib import Path

from .common import require
from . import benchmark, sdvk009_physical as physical

PURPOSE = "sdvk009-shadowoff-scaling"
SCENES = ("lights-one-shadow-off", "lights-many-shadow-off",
          "lights-dense-dispersed", "lights-dense-overlap")
COUNTS = dict(zip(SCENES, (1, 64, 256, 256)))
TIMING_ORDERS = (SCENES, tuple(reversed(SCENES)),
                 (SCENES[1], SCENES[0], SCENES[3], SCENES[2]))
EXTENT = [1904, 1001]
WARMUP, FRAMES, DEADLINE = 120, 120, 180


def shadowoff_variant(original):
    """Only the explicit shadow switch/assertions and descriptive identity vary.

    Lighting geometry, light eligibility/counts, materials, sampling, camera,
    ordinary clock and all other settings remain the original one/64 workload.
    Every map/material/image member is byte-identical; MAPINFO's display title
    carries the new scene identity, so the archive has a distinct pinned hash.
    """
    require(original["id"] in ("lights-one", "lights-many"), "Unknown sparse shadow-off source")
    result = copy.deepcopy(original)
    result["id"] += "-shadow-off"
    result["title"] += " (explicit shadow-off scaling control)"
    result["classes"] = [value for value in result["classes"] if value != "shadows"]
    result["required_state_channels"] = [value for value in result["required_state_channels"] if value != "shadow"]
    result["source_refs"] += ["tools/renderer_oracle/sdvk009_shadowoff.py",
                              "tools/renderer_oracle/sdvk009_physical.py",
                              "docs/shadedoomvk/SDVK-009-SHADOWOFF-SCALING.md"]
    native = result["native"]
    for key in ("capture_script", "config", "pk3"):
        native[key] = native[key].replace("scenes/" + original["id"] + "/", "scenes/" + result["id"] + "/")
    native["settings"]["gl_light_shadows"] = 0
    for key in ("shadow_candidates", "shadow_selected", "shadow_dropped"):
        native["frame_assertions"][key] = {"minimum": 0, "maximum": 0}
    native.pop("shadow_capacity_control", None)
    native["pending_coverage"].append("Prospective shadow-off scaling only; shadow correctness and SDVK-009 acceptance remain held.")
    return result


def capture_specs(recipe_hashes):
    """Eight paired correctness processes, then three timing processes/scene."""
    require(set(recipe_hashes) == set(SCENES), "Shadow-off schedule requires its exact four workloads")
    captures = []

    def add(scene, name, mode, compare=None):
        captures.append(dict(name=name, scene=scene, recipe_sha256=recipe_hashes[scene], mode=mode,
            frames=1 if mode == "state" else FRAMES, warmup=WARMUP, extent=list(EXTENT),
            deadline_seconds=DEADLINE, compare_with=compare))

    for scene in SCENES:
        first = scene + "-state-1"
        add(scene, first, "state")
        add(scene, scene + "-state-2", "state", first)
    for repetition, order in enumerate(TIMING_ORDERS, 1):
        for scene in order:
            add(scene, scene + "-timing-" + str(repetition), "timing")
    return captures


def validate_recipes(packet, run):
    catalog = {s["id"]: s for s in run.preparation_module().load_catalog()["scenes"]}
    for scene in SCENES:
        _, _, recipe = run.prepared_scene(packet["prepared"], scene)
        native = recipe["native"]
        authored = copy.deepcopy(recipe)
        authored.pop("prepared_assets", None)  # verified derived hashes/member inventory, not authored policy
        require(authored == catalog[scene], "Shadow-off prepared recipe differs from current source")
        if scene.endswith("-shadow-off"):
            require(authored == shadowoff_variant(catalog[scene.removesuffix("-shadow-off")]),
                    "Sparse shadow-off variant changed more than its declared shadow policy")
        require(native["generator"] == "lighting" and native["authored_light_count"] == COUNTS[scene],
                "Shadow-off workload changed its authored light count")
        require(native["settings"]["gl_light_shadows"] == 0 and native["settings"]["vk_rayquery"] is False
                and native["settings"]["gl_levelmesh"] is False,
                "Shadow-off scaling requires disabled shadows/rayquery and the immediate scene path")
        require(native["clock"]["timing"] == "ordinary_engine_clock" and
                native["settings"]["cl_capfps"] is False and native["settings"]["vid_maxfps"] == 0
                and native["settings"]["vid_vsync"] is False, "Shadow-off ordinary clock policy changed")


def _continuity(packet, path, result, run):
    physical._physical_build(result["build"])
    require(result["build"].get("commit") == packet["source"]["commit"] and
            result["build"].get("working_tree") == "clean", "Shadow-off native source identity differs")
    for key, expected in packet["native_device"].items():
        require(result["build"]["vulkan"].get(key) == expected, "Shadow-off physical device changed: " + key)
    reference_path = Path(packet["stages"][0]["capture"]["out"])
    reference = run.read_json(reference_path / "run.json")
    physical._same_build(reference["build"], result["build"])
    require(physical._runtime_identity(reference) == physical._runtime_identity(result),
            "Shadow-off executable/engine/IWAD bytes changed")
    request, first_request = run.read_json(path / "request.json"), run.read_json(reference_path / "request.json")
    require(all(request[key] == first_request[key] for key in ("host", "environment")),
            "Shadow-off host/loader/layer environment changed")


def state_workload(raw, scene):
    """Existing state counters are the paired timing workload authority."""
    frames = [r["data"] for r in raw["records"] if r["kind"] == "frame"]
    resources = [r["data"] for r in raw["records"] if r["kind"] == "resource"]
    require(raw["mode"] == "state" and len(frames) == len(resources) == 1,
            "Shadow-off workload authority requires one complete state frame/resource snapshot")
    frame, resource = frames[0], resources[0]
    require(frame["authored_lights"] == frame["active_lights"] == COUNTS[scene],
            "Shadow-off actual authored/active light count differs")
    require(frame["settings"]["gl_light_shadows"] == 0 and frame["settings"]["vk_rayquery"] is False
            and frame["settings"]["gl_levelmesh"] is False,
            "Actual shadow-off state enabled shadows/rayquery/LevelMesh")
    require(all(frame[key] == 0 for key in ("shadow_candidates", "shadow_selected", "shadow_dropped")),
            "Shadow-off state selected shadow work")
    uploads = resource["light_uploads"]
    require(uploads.get("available") is True and uploads["records_used"] > 0 and
            uploads["failed"] == uploads["index_capacity_failures"] == uploads["data_capacity_failures"] == 0,
            "Shadow-off dynamic-light uploads unavailable, empty or failed")
    census = ("authored_lights", "active_lights", "spot_lights", "subtractive_lights", "additive_lights",
              "actor_light_queries", "actor_light_candidates", "actor_light_selected", "actor_light_filtered",
              "actor_light_duplicates", "actor_light_traces", "light_wall_considered", "light_wall_rendered",
              "light_flat_considered", "light_flat_rendered", "walls", "flats", "sprites", "decals", "portals", "vertices")
    return {"frame_census": {key: frame[key] for key in census}, "light_uploads": uploads,
            "descriptor_pressure": {key: resource[key] for key in
                ("descriptor_capacity", "descriptor_current", "descriptor_high_water", "descriptor_failures")}}


def validate_capture(packet, stage, run):
    path = Path(stage["capture"]["out"])
    _, result, raw, _ = run.validate_run(path)
    capture, profile = stage["capture"], result["reproduction"]
    specs = run.read_json(Path(packet["workload_registration"]["path"]))["captures"]
    spec = next(row for row in specs if row["name"] == stage["name"])
    require(result["scene"] == profile["scene"] == capture["scene"] and result["mode"] == capture["mode"]
            and profile["recipe_sha256"] == spec["recipe_sha256"] and profile["extent"] == EXTENT
            and profile["warmup_frames"] == WARMUP and profile["frames"] == capture["frames"]
            and profile["gpu_timestamps_requested"] is (capture["mode"] == "timing"),
            "Shadow-off collected capture differs from its registered workload")
    require(profile["settings"]["gl_light_shadows"] == 0 and profile["settings"]["vk_rayquery"] is False
            and profile["settings"]["gl_levelmesh"] is False and
            profile["clock"] == ("ordinary_engine_clock" if capture["mode"] == "timing" else "static_after_initialization"),
            "Shadow-off collected clock/shadow policy differs")
    _continuity(packet, path, result, run)
    receipt = {"schema": "sdvk009-shadowoff-capture/v1", "status": "PASS",
               "scope": "PARTIAL_SCALING_COLLECTION_ONLY", "physical_gpu_qualified": False, "performance_accepted": False}
    if stage["capture"]["mode"] == "state":
        receipt["workload"] = state_workload(raw, stage["capture"]["scene"])
    else:
        coverage = physical._timing_integrity(path)
        require(coverage["status"] == "COMPLETE_GROUPS_SCOPE_UNQUALIFIED" and
                coverage["groups"].get("scene.immediate") == {"frames": FRAMES, "samples_per_frame": [1]},
                "Shadow-off timing lacks complete single immediate-scene GPU samples")
        benchmark.summarize(raw, minimum_samples=FRAMES)
        receipt["gpu_coverage"] = coverage
        if stage["name"] == packet["stages"][-1]["name"]:
            receipt["summaries"] = {scene: run.summarize_runs([
                Path(s["capture"]["out"]) for s in packet["stages"]
                if s["capture"]["mode"] == "timing" and s["capture"]["scene"] == scene], minimum_samples=FRAMES)
                for scene in SCENES}
    return receipt
