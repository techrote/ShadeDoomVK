"""Bounded native source-plane/facing witness for standard FF_BOTHPLANES.

Two compact maps reuse the accepted96/32 invalidate/filter/reload driver. The
first camera is above both model planes, the second below both. A real line
mirror requires the immediate path as well as the main LevelMesh path. Authored
inputs and CPU checks alone never award native or physical acceptance.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
from tools.renderer_oracle import sdvk161_special_surfaces as legacy
from tools.renderer_oracle.common import EvidenceError, pin, require, write_json

SCENE = "controlled-plane-lifecycle"
GENERATOR = "controlled_plane_lifecycle"
FRAMES, WARMUP, DEADLINE = legacy.FRAMES, legacy.WARMUP, legacy.DEADLINE
MAP_A, MAP_B = legacy.MAP_A, legacy.MAP_B
MAP_CAMERAS = legacy.MAP_CAMERAS
SCHEDULE, WITNESS_FRAMES = legacy.SCHEDULE, legacy.WITNESS_FRAMES
MAP_HEIGHTS = {MAP_A: (32, 48), MAP_B: (96, 112)}
CONTROL = 1
# TileCensus serializes the engine's unsigned no-plane sentinel as -1.
NO_CONTROL_PLANE = -1
NAMES = {0: "S161PN", 1: "S161PH"}
EXCLUDED = ["FF_FIX/Vavoom", "copied/sloped control planes", "overlapping controls",
            "in-place animated control-height changes", "hardware cost/scaling/stability",
            "retained v5 RGB for FF_BOTHPLANES (runtime-bake-only quarantine)"]


def validate_recipe(scene):
    native = scene.get("native", {})
    require(scene.get("id") == SCENE and native.get("generator") == GENERATOR
            and native.get("controlled_plane_matrix") == {
                "definition": [161, 5, 0, 255], "control_sector": CONTROL,
                "heights": {key: list(value) for key, value in MAP_HEIGHTS.items()},
                "source_planes": [0, 1], "facings": [4, 5],
                "immediate_facing": {MAP_A: 5, MAP_B: 4}, "retained_v5": "RuntimeBakeOnly"},
            "Unknown controlled-plane lifecycle matrix")
    # Same accepted schedule/clock/budget, distinct recipe and authored geometry.
    checked = {**scene, "id": legacy.SCENE,
               "native": {**native, "generator": "special_surface_lifecycle"}}
    legacy.validate_recipe(checked)
    require(native["settings"].get("gl_lights") is False
            and native["settings"].get("gl_light_shadows") == 0
            and native["settings"].get("vk_rayquery") is False,
            "Controlled planes require the small no-dynamic-light shadow-off scope")


def settings_for_frame(native, frame):
    return legacy.settings_for_frame(native, frame)


def authored_members(scene, author):
    from tools.renderer_oracle.sdvk161_fixtures import _ring, _sector
    validate_recipe(scene)
    members = author._base_members()
    author._material_layers(members)
    for index, name in enumerate((NAMES[0], NAMES[1], "S161NO")):
        members[f"textures/{name}.png"] = author._texture(64, 64,
            (50 + 55 * index, 70, 210 - 45 * index, 255),
            (220 - 50 * index, 180, 35 + 65 * index, 255))
    def pbr(name, height=False):
        text = author._pbr(name).replace(' normal "SDVN"', ' normal "SDVN" { filter linear }')
        return text[:-2] + (' height "SDVH" { filter linear }\n' if height else '') + '}\n'
    members["GLDEFS"] = (pbr(NAMES[0]) + pbr(NAMES[1], True)).encode()
    metadata = []
    for map_name, (bottom, top) in MAP_HEIGHTS.items():
        model = author._Map(floor=0, ceiling=160)
        model.records["sector"][0]["id"] = 161
        cx, cy = (0, 0) if map_name == MAP_A else (1060, -64)
        model.boundary([(cx-256, cy-192), (cx-256, cy+192),
                        (cx+256, cy+192), (cx+256, cy-192)], ["SDVW"]*4)
        mirror = 2 if map_name == MAP_A else 1
        model.records["linedef"][mirror].update(id=14182, special=182)
        model.records["sector"].append(_sector(author, floor=bottom, ceiling=top,
            floor_texture=NAMES[0], ceiling_texture=NAMES[1]))
        definitions, _ = _ring(model, [(1600, -32), (1600, 32), (1664, 32), (1664, -32)], CONTROL, "S161NO")
        model.records["linedef"][definitions[0]].update(special=160, arg0=161, arg1=5, arg2=0, arg3=255)
        camera = MAP_CAMERAS[map_name]
        player = [-240, 0] if map_name == MAP_A else [1060, -224]
        model.thing(1, *player, tid=2001)
        model.thing(32200, *camera["position"], camera["yaw"], tid=2002)
        model.thing(9890, cx-96, cy, angle=0, pitch=0, lm_suncolor=16777215,
                    lm_sunintensity=0, lm_sampledist=32)
        members[f"maps/{map_name}.wad"] = author.pf_indexed.wad([
            (map_name, b""), ("TEXTMAP", model.text().encode()), ("ENDMAP", b"")])
        metadata.append({"map": map_name, "camera": copy.deepcopy(camera), "player_start_world": player,
                         "counts": {kind: len(rows) for kind, rows in model.records.items()},
                         "boundary_signed_areas": model.polygon_areas, "mirror_side": mirror,
                         "controlled_heights": [bottom, top], "controlled_definition": [161, 5, 0, 255]})
    members["MAPINFO"] = (''.join(f'map {name} "SDVK controlled planes {index}" {{ nointermission }}\n'
        for index, name in enumerate(MAP_HEIGHTS)) + 'DoomEdNums { 32200 = SDVKFixedCamera\n }\n').encode()
    return members, {"geometry": "two compact original authored UDMF maps", "textures": "generated_rgba_only",
        "native_executed": False, "camera_actor_tid": 2002, "camera_position_world": [-192, 0, 64],
        "player_start_world": [-240, 0], "monsters": 0, "animated_or_random_actors": 0,
        "baked_lightmap_members": 0, "initial_retained_work": {"retained_frames": [1, 8], **SCHEDULE[0]},
        "maps": metadata, "excluded": EXCLUDED,
        "ownership": "model-source axis independent of emitted facing; four live allocations per target subsector"}


def _controlled_census(tiles):
    groups = {}
    for tile in tiles.values():
        binding = tile["binding"]
        axis = binding.get("control_plane")
        if binding["control_sector"] != -1 and binding["type"] in (4, 5):
            require(binding["control_sector"] == CONTROL and type(axis) is int and axis in (0, 1),
                    "Controlled tile lost its exact model-source axis")
            pairs = groups.setdefault(binding["type_index"], set())
            pair = (axis, binding["type"])
            require(pair not in pairs, "Controlled source/facing key is duplicated")
            pairs.add(pair)
        else:
            require(axis == NO_CONTROL_PLANE, "Ordinary tile invented a controlled source axis")
    require(groups and all(pairs == {(0, 4), (0, 5), (1, 4), (1, 5)} for pairs in groups.values()),
            "Controlled census lacks four independent source/facing bindings")
    return groups


def _surface_tile(value, resource, tiles, axis):
    lm = value["lightmap"]
    require(lm["epoch"] == resource["lightmap_epoch"], "Controlled surface has stale atlas epoch")
    if not lm["eligible"]:
        require(axis is None, "Controlled face was silently disabled from lightmapping")
        return None
    require(lm["tile"] in tiles, "Submitted face has no live tile")
    tile = tiles[lm["tile"]]; owner = value["owner"]
    require(lm["valid"] is True and lm["page"] == tile["page"] and lm["receipt"] == tile["receipt"],
            "Submitted face samples a retired allocation/page")
    require(tile["binding"] == {"type": owner["type"], "type_index": owner["type_index"],
                "control_sector": owner["control_sector"], "control_plane": NO_CONTROL_PLANE if axis is None else axis},
            "Submitted face uses another model-source/facing tile")
    return (lm["tile"], lm["page"], *legacy._receipt(lm["receipt"]))


def _submitted(raw, resources, native):
    selected = {frame: [] for frame in WITNESS_FRAMES}; parents = {}
    material_bindings = {frame: [] for frame in WITNESS_FRAMES}
    censuses = {frame: legacy._tile_census(row) for frame, row in resources.items()}
    atlas_owners = {}
    for frame, tiles in censuses.items():
        _controlled_census(tiles)
        owner = next(iter(tiles.values()))["receipt"]["owner"]
        require(atlas_owners.setdefault((frame-1)//24, owner) == owner,
                "Sampler reset replaced the controlled atlas allocation owner")
    require(len(set(atlas_owners.values())) == 4, "Reload reused a controlled atlas allocation owner")
    for row in raw["records"]:
        frame, value = row.get("frame"), row.get("data", {})
        if row.get("kind") == "pipeline" and value.get("producer") == "levelmesh-indexed-range":
            parents.setdefault(frame, []).append(value)
        if row.get("kind") != "surface": continue
        require(frame in selected and type(row.get("count")) is int and row["count"] > 0,
                "Controlled face emitted outside fixed native witness frames")
        legacy.validate_surface_record(value)
        resource = resources[frame]; owner = value["owner"]; context = value["context"]
        map_name = MAP_A if frame <= 48 else MAP_B
        require(value["mesh_owner"] == resource["levelmesh"]["owner"] and value["mesh_epoch"] == resource["levelmesh"]["epoch"],
                "Submitted controlled geometry belongs to a retired mesh")
        require(context.get("map") == map_name and context.get("portal_group") == owner["portal_group"] == 0,
                "Controlled surface escaped its authored map/portal owner")
        if value["producer"] == "levelmesh-surface-range":
            require(any(parent.get("first_index") == value["batch_first_index"] and parent.get("draw_count") == value["batch_index_count"]
                        and parent.get("key") == value["key"] and parent.get("context") == context for parent in parents.get(frame, [])),
                    "Controlled geometry has no actual same-frame indexed parent draw")
        controlled = value["class"] in ("three-d-floor-floor", "three-d-floor-ceiling")
        axis = None
        if controlled:
            name = value.get("material", {}).get("name")
            require(name in NAMES.values(), "Unexpected controlled plane material")
            axis = next(axis for axis, expected in NAMES.items() if name == expected)
            kind = 4 if value["class"] == "three-d-floor-ceiling" else 5
            require(owner["type"] == kind and owner["side"] == -1 and owner["sector"] == 0
                    and owner["control_sector"] == CONTROL, "Controlled submitted receiver owner/facing differs")
            legacy._plane(value, z=MAP_HEIGHTS[map_name][axis], normal=-1 if kind == 4 else 1)
        token = _surface_tile(value, resource, censuses[frame], axis)
        if value["class"] != "mirror":
            material = value["material"]
            material_token = legacy._material(material, value["key"]["shader"], value["texture_index"],
                                              int(17 <= frame <= 32 or 65 <= frame <= 80))
            for earlier_name, earlier in material_bindings[frame]:
                overlaps = material_token[0] < earlier[0]+earlier[3] and earlier[0] < material_token[0]+material_token[3]
                require(not overlaps or (material["name"] == earlier_name and material_token == earlier),
                        "Controlled materials alias one current descriptor block")
            material_bindings[frame].append((material["name"], material_token))
            probe = value["probe"]
            require(type(probe.get("authored_index")) is int and probe["authored_index"] >= -1
                    and probe.get("runtime_irradiance_index") == 0 and probe.get("fallback") is True
                    and probe.get("probe_epoch") == resource["probe_epoch"],
                    "Controlled no-probe path retained another map's probe owner")
            expected_scope = "not stored in mesh; no authored target claim" if value["producer"] == "levelmesh-surface-range" else "current immediate authored uniform selector"
            require(probe.get("authored_scope") == expected_scope
                    and (value["producer"] != "levelmesh-surface-range" or probe["authored_index"] == -1),
                    "Controlled submitted probe selector scope differs")
        if controlled:
            require(token is not None and value["geometry"]["current_uv_valid"] is True,
                    "Controlled face does not sample its current allocation UVs")
            selected[frame].append((value, axis, token))
    result = {}
    for frame, values in selected.items():
        # Native actual draws, not only a census of four allocated CPU tiles.
        main = {(axis, v["owner"]["type"]) for v, axis, _ in values if v["producer"] == "levelmesh-surface-range"
                and v["context"].get("type") == "main" and v["context"].get("producer") == "root" and v["context"].get("depth") == 0}
        require(main == {(0, 4), (0, 5), (1, 4), (1, 5)}, f"Frame{frame} lacks actual four-face main submission")
        facing = 5 if frame <= 48 else 4
        immediate = {(axis, v["owner"]["type"]) for v, axis, _ in values if v["producer"] == "immediate-special-surface"
                     and v["context"].get("type") == "portal" and v["context"].get("producer") == "Mirror"
                     and v["context"].get("line_mirror") is True and v["context"].get("depth") == 1}
        require(immediate == {(0, facing), (1, facing)}, f"Frame{frame} lacks actual mirrored source/facing UV submissions")
        tokens = {}
        for value, axis, token in values:
            key = (value["owner"]["type_index"], axis, value["owner"]["type"])
            require(key not in tokens or tokens[key] == token, "Main/immediate paths disagree on the same current face allocation")
            tokens[key] = token
        require(len(set(tokens.values())) == len(tokens), "Distinct source/facing receivers share an atlas allocation")
        result[str(frame)] = {"main_faces": sorted(main), "immediate_faces": sorted(immediate), "allocation_keys": len(tokens)}
    return result


def validate_transition_records(raw, stdout, native):
    validate_recipe({"id": SCENE, "native": native})
    require(raw.get("observed_frames") == FRAMES, "Controlled lifecycle retained frame budget differs")
    expected = [f"SDVK161_INPUT phase={p['phase']} after_main_views={p['after_main_views']}" for p in SCHEDULE]
    require([line for line in stdout.splitlines() if line.startswith("SDVK161_INPUT ")] == expected, "Controlled driver phase order/count differs")
    frames, resources = (legacy._one_per_frame(raw, kind) for kind in ("frame", "resource"))
    owners = {}
    for frame in range(1, FRAMES+1):
        map_name = MAP_A if frame <= 48 else MAP_B; incarnation = (frame-1)//24
        require(frames[frame].get("map") == map_name, "Controlled lifecycle frame has another map owner")
        legacy._resource_state(resources[frame], map_name)
        camera = MAP_CAMERAS[map_name]
        legacy._camera_vector(frames[frame]["camera"]["position"], camera["position"], "controlled fixed camera")
        legacy._camera_vector(frames[frame]["camera"]["angles"], [camera["yaw"], 0, 0], "controlled fixed angles")
        legacy._retained_fov(frames[frame]["camera"].get("fov"))
        for key in ("gl_levelmesh", "lm_dynlights", "gl_lightprobe", "gl_texture_filter", "gl_texture_filter_anisotropic"):
            require(frames[frame]["settings"].get(key) == settings_for_frame(native, frame)[key], "Controlled lifecycle actual setting differs")
        r = resources[frame]; owner = (r["lightmap_epoch"], r["probe_epoch"], r["levelmesh"]["owner"], r["levelmesh"]["epoch"])
        require(owners.setdefault(incarnation, owner) == owner, "Controlled sampler reset replaced live resource owners")
    for incarnation in (1, 2, 3):
        before, after = owners[incarnation-1], owners[incarnation]
        require(after[2] > before[2] and after[0] > before[0] and after[1] > before[1], "Controlled reload did not retire mesh/atlas/probe owners")
    completions = legacy._map_completions(stdout, owners)
    cycles = {name: legacy._completed_cycle(resources, first, last, name) for name, first, last in (
        ("initial-a", 1, 8), ("invalidate-a1", 9, 24), ("reload-a", 25, 40), ("invalidate-a2", 41, 48),
        ("invalidate-b1", 57, 72), ("reload-b", 73, 88), ("invalidate-b2", 89, 96))}
    require(all(resources[f]["lightmap_state"]["all_clean"] is True for f in WITNESS_FRAMES), "Controlled witness captured unconverged bake work")
    return {"status": "PASS", "frames": FRAMES, "cycles": cycles, "resource_owners": owners, "map_completions": completions,
            "source_facing_submissions": _submitted(raw, resources, native), "physical_gpu_qualified": False,
            "scope": "Actual main/immediate source-plane/facing, live UV/allocation/descriptor and rebuild witnesses; no executed-shader/physical cost claim"}


# Same map labels and exact96-frame schedule: existing checkpoint ownership,
# equivalent-state RGB comparisons and all original image pins remain mandatory.
validate_checkpoint_artifacts = legacy.validate_checkpoint_artifacts
validate_checkpoint_images = legacy.validate_checkpoint_images
compare_checkpoint_images = legacy.compare_checkpoint_images


def captured_negatives(raw, stdout, native):
    """Four faults derived from this independently admitted actual capture."""
    validate_transition_records(raw, stdout, native)
    def first(data, immediate=False):
        return next(r["data"] for r in data["records"] if r["kind"] == "surface" and r["frame"] == 8
                    and r["data"].get("class") == "three-d-floor-floor"
                    and r["data"].get("material", {}).get("name") == NAMES[0]
                    and (not immediate or r["data"].get("producer") == "immediate-special-surface"))
    def missing_mirror(data):
        data["records"] = [r for r in data["records"] if not (r["kind"] == "surface" and r["frame"] == 8
            and r["data"].get("class", "").startswith("three-d-floor-")
            and r["data"].get("producer") == "immediate-special-surface")]
    controls = (
        ("wrong-source-plane", lambda d: first(d)["geometry"].update(plane=[0, 0, 1, 48]), "selected/flipped"),
        ("overwritten-immediate-uv", lambda d: first(d, True)["geometry"].update(current_uv_valid=False), "UV"),
        ("retired-atlas-incarnation", lambda d: first(d)["lightmap"]["receipt"].update(incarnation=0), "receipt|incarnation"),
        ("missing-mirrored-face", missing_mirror, "mirrored source/facing"),
    )
    results = []
    for name, mutate, expected in controls:
        damaged = copy.deepcopy(raw); mutate(damaged)
        try:
            validate_transition_records(damaged, stdout, native)
        except EvidenceError as error:
            require(re.search(expected, str(error)) is not None, "Captured controlled-plane negative failed for an unrelated reason: " + name)
            results.append({"name": name, "rejected": True, "error": str(error)})
        else:
            require(False, "Captured controlled-plane fault was accepted: " + name)
    return {"status": "PASS", "controls": results, "scope": "Mutated in-memory copies; original native evidence unchanged"}


def qualify(args):
    """Hosted software Vulkan only; hardware uses the separate guarded executor."""
    from tools.renderer_oracle import native_ci, prepare, run, sdvk010_sun_native
    out = run.fresh_directory(args.out)
    result = {"schema": "sdvk014-controlled-plane-qualification/v1", "status": "FAIL", "steps": [],
              "physical_gpu_qualified": False, "performance_accepted": False, "automatic_retries": 0,
              "physical_cost_scaling_stability": "HELD / NOT ACCEPTED", "unsupported": EXCLUDED}
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None, "Expected exact clean build commit required")
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()), "No CFX experiments in controlled-plane gate")
        result["software_host"] = sdvk010_sun_native.software_host_guard()
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out/"prepared"; manifest = prepare.prepare(prepared, [SCENE]); captures = []
        for name in ("lifecycle-1", "lifecycle-2"):
            target = out/name
            options = argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared, out=target, scene=SCENE,
                mode="state", frames=FRAMES, warmup=WARMUP, timeout=DEADLINE, gpu=False, include_stress=True,
                image_policy="exact", extent=None, collision_snapshot=False, publication_witness=False,
                expected_commit=args.expected_commit, require_clean=True)
            def capture_and_admit():
                receipt = run.capture(options)
                require(receipt.get("status") == "COLLECTED", "Controlled native capture failed")
                root, _, raw, _ = run.validate_run(target); stdout = (root/"stdout.log").read_text()
                validation = validate_transition_records(raw, stdout, manifest["scenes"][0]["native"])
                validation["checkpoint_images"] = validate_checkpoint_images(root, raw)
                controls = captured_negatives(raw, stdout, manifest["scenes"][0]["native"])
                controls["source"] = pin(root/"native.renderer.json", relative_to=root)
                write_json(target/"negative-controls.json", controls); write_json(target/"controlled-plane-lifecycle.json", validation)
                return receipt
            step = native_ci.attempt(out, name, capture_and_admit, ("COLLECTED",)); result["steps"].append(step)
            require(step["status"] == "PASS", "Controlled native attempt failed; no retry/dependent run")
            captures.append(target)
        comparison = run.compare_runs(*captures); write_json(out/"repeatability.json", comparison)
        require(comparison.get("status") == "PASS" and comparison.get("state_equal") is True
                and comparison.get("image", {}).get("passed") is True and comparison["image"].get("changed_pixels") == 0,
                "Controlled exact semantic state/final RGB repeatability failed")
        checkpoints = compare_checkpoint_images(*captures); write_json(out/"checkpoint-repeatability.json", checkpoints)
        require(checkpoints["status"] == "PASS", "Controlled checkpoint RGB repeatability failed")
        result.update(status="PASS", captures=[pin(p/"run.json", relative_to=out) for p in captures],
                      comparison=pin(out/"repeatability.json", relative_to=out), checkpoint_comparison=pin(out/"checkpoint-repeatability.json", relative_to=out))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        write_json(out/"qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("exe", "iwad", "iwad-license", "out"): parser.add_argument("--"+key, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    result = qualify(parser.parse_args(argv)); print(json.dumps({key: result.get(key) for key in ("schema", "status", "error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
