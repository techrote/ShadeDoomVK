#!/usr/bin/env python3
"""Strict SDVK-161 submitted special-surface lifecycle qualification.

This is bounded hosted software-Vulkan correctness evidence. It authenticates
submitted draw state and current owners, not executed shaders or per-texel GPU
probe selections. Physical STOP remains active; cost/scaling/stability are held.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess

from tools.renderer_oracle.common import EvidenceError, artifact_path, canonical, pin, require, sha256, write_json

SCENE = "special-surface-lifecycle"
MAP_A = "SDV161A"
MAP_B = "SDV161B"
WARMUP = 32
FRAMES = 96
DEADLINE = 600
SCHEDULE = [
    {"after_main_views": 40, "phase": "invalidate-a-1", "command": "invalidatelightmap"},
    {"after_main_views": 48, "phase": "filter-linear-a", "command": "gl_texture_filter 4"},
    {"after_main_views": 56, "phase": "reload-a", "command": "map SDV161A"},
    {"after_main_views": 64, "phase": "filter-nearest-a", "command": "gl_texture_filter 0"},
    {"after_main_views": 72, "phase": "invalidate-a-2", "command": "invalidatelightmap"},
    {"after_main_views": 80, "phase": "map-b", "command": "map SDV161B"},
    {"after_main_views": 88, "phase": "invalidate-b-1", "command": "invalidatelightmap"},
    {"after_main_views": 96, "phase": "filter-linear-b", "command": "gl_texture_filter 4"},
    {"after_main_views": 104, "phase": "reload-b", "command": "map SDV161B"},
    {"after_main_views": 112, "phase": "filter-nearest-b", "command": "gl_texture_filter 0"},
    {"after_main_views": 120, "phase": "invalidate-b-2", "command": "invalidatelightmap"},
]
WITNESS_FRAMES = tuple(range(8, FRAMES + 1, 8))
CURRENT_UV_TOLERANCE = 2.0 ** -21  # Four IEEE-754 float epsilons; never an RGB tolerance.
LIFECYCLE_RGB_GROUPS = (
    ("a-nearest", MAP_A, 0, (8, 16, 40, 48)),
    ("a-linear", MAP_A, 4, (24, 32)),
    ("b-nearest", MAP_B, 0, (56, 64, 88, 96)),
    ("b-linear", MAP_B, 4, (72, 80)),
)


# Independent expected authored semantics, not generated from the asset author.
MATERIAL_SPECS = {
    "S161PH": {"shader": 4, "height": 8,
               "semantics": ["albedo", "normal", "metallic", "roughness", "ambient-occlusion", "height"]},
    "S161PN": {"shader": 4, "height": -1,
               "semantics": ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"]},
    "S161WP": {"shader": 2, "height": 4, "semantics": ["albedo", "height"]},
    "S161HO": {"shader": 0, "height": 4, "semantics": ["albedo", "height"]},
    "S161NO": {"shader": 0, "height": -1, "semantics": ["albedo"]},
}


def validate_recipe(scene: dict) -> None:
    native = scene["native"]
    require(scene["id"] == SCENE and native.get("generator") == "special_surface_lifecycle"
            and native.get("map") == MAP_A, "Unknown SDVK-161 special-surface recipe")
    require(native.get("special_surface_schedule") == SCHEDULE,
            "SDVK-161 special-surface schedule differs from preregistration")
    require(native.get("recommended_warmup_frames") == WARMUP,
            "SDVK-161 special-surface warmup differs")
    require(native.get("map_sequence") == [MAP_A, MAP_A, MAP_B, MAP_B]
            and native.get("surface_witness_frames") == list(WITNESS_FRAMES),
            "SDVK-161 map incarnation sequence or sampled witness policy differs")
    commands = native.get("console_commands", [])
    budgets = [command for command in commands if re.match(r"lm_(?:max|background)_updates(?:\s|$)", command)]
    require(budgets == ["lm_max_updates 128", "lm_background_updates 32"],
            "SDVK-161 prospective lightmap work budget differs")
    quiet = [part.strip() for command in commands for part in re.split(r"[;\r\n]", command)
             if re.match(r"screenshot_quiet(?:\s|$)", part.strip(), re.IGNORECASE)]
    require(quiet == ["screenshot_quiet true"],
            "SDVK-161 checkpoint screenshots require exactly one quiet-output command")
    settings = native["settings"]
    require(settings.get("gl_levelmesh") is True and settings.get("lm_dynlights") is False,
            "SDVK-161 requires static lightmapping with the LevelMesh path")
    require(settings.get("gl_lightprobe") is True,
            "SDVK-161 empty authored probe-owner resets must remain enabled")
    require(settings.get("gl_texture_filter") == 0
            and settings.get("gl_texture_filter_anisotropic") == 1,
            "SDVK-161 material sampler baseline differs")


def settings_for_frame(native: dict, frame: int) -> dict:
    result = dict(native["settings"])
    if 17 <= frame <= 32 or 65 <= frame <= 80:
        result["gl_texture_filter"] = 4
    return result



def _integer(value, label: str, minimum=0) -> int:
    require(type(value) is int and value >= minimum, "SDVK-161 invalid " + label)
    return value


def _one_per_frame(raw: dict, kind: str) -> dict[int, dict]:
    rows = {}
    for record in raw["records"]:
        if record.get("kind") != kind:
            continue
        frame = _integer(record.get("frame"), kind + " frame", 1)
        require(frame <= FRAMES and frame not in rows
                and type(record.get("count")) is int and record["count"] == 1,
                "SDVK-161 missing/duplicate " + kind + " frame state")
        rows[frame] = record["data"]
    require(set(rows) == set(range(1, FRAMES + 1)),
            "SDVK-161 requires one " + kind + " snapshot for every retained frame")
    return rows


def _resource_state(row: dict, map_name: str) -> dict:
    state = row.get("lightmap_state", {})
    require(state.get("available") is True and state.get("map") == map_name,
            "SDVK-161 lightmap lifecycle owner unavailable or stale")
    require(type(state.get("authored_probe_count")) is int and state["authored_probe_count"] == 0,
            "SDVK-161 no-probe fixture contains another current authored probe owner")
    pages = _integer(state.get("texture_count"), "CPU page population", 1)
    require(state.get("vulkan_page_count") == pages and state.get("page_count_match") is True,
            "SDVK-161 current CPU/Vulkan atlas pages disagree")
    live = _integer(state.get("live_tiles"), "live tiles", 1)
    require(state.get("valid_live_tiles") == live and state.get("invalid_live_tiles") == 0
            and state.get("sampling_page_bounds_ok") is True,
            "SDVK-161 current lightmap receipts or page bounds are invalid")
    occupancy = state.get("page_live_tiles")
    require(isinstance(occupancy, list) and len(occupancy) == pages
            and all(type(value) is int and value >= 0 for value in occupancy)
            and sum(occupancy) == live, "SDVK-161 atlas occupancy is incomplete")
    for key in ("lightmap_epoch", "probe_epoch"):
        _integer(row.get(key), "current " + key, 1)
    _integer(row.get("levelmesh", {}).get("epoch"), "current mesh owner epoch", 1)
    for key in ("initial_dirty", "geometry_dirty", "light_dirty", "frame_tile_updates", "frame_tile_completions"):
        _integer(state.get(key), key)
    require(state.get("all_clean") is (state["initial_dirty"] == state["geometry_dirty"] == state["light_dirty"] == 0),
            "SDVK-161 dirty-state completion flags disagree")
    return state


def _completed_cycle(resources: dict[int, dict], first: int, last: int, name: str) -> dict:
    states = [resources[frame]["lightmap_state"] for frame in range(first, last + 1)]
    updates = sum(state["frame_tile_updates"] for state in states)
    completions = sum(state["frame_tile_completions"] for state in states)
    require(0 < completions <= updates,
            "SDVK-161 " + name + " did not complete real admitted lightmap work")
    require(states[-1]["all_clean"] is True,
            "SDVK-161 " + name + " did not converge to clean completion")
    return {"frames": last - first + 1, "requested_tile_updates": updates,
            "completed_tiles": completions, "final_all_clean": True}




def _resource_token(value: dict, label: str, *, span=None) -> tuple[int, int, int, int]:
    require(isinstance(value, dict) and value.get("available") is True,
            "SDVK-161 " + label + " has no current bound resource token")
    token = tuple(_integer(value.get(key), label + " " + key, 1)
                  for key in ("index", "generation", "epoch", "span"))
    require(span is None or token[3] == span, "SDVK-161 " + label + " resource span differs")
    return token


def _material(value: dict, shader: dict, texture_index: int, expected_filter: int) -> tuple:
    name = value.get("name")
    spec = MATERIAL_SPECS.get(name, {"shader": 0, "height": -1, "semantics": ["albedo"]})
    require(isinstance(name, str) and (name.startswith("S161") or name in ("SDVW", "SDVFL")),
            "SDVK-161 unexpected submitted special material")
    require(value.get("shader") == spec["shader"] and shader.get("EffectState") == spec["shader"]
            and shader.get("NoFragmentShader") == 0 and shader.get("AlphaTestOnly", 0) == 0,
            "SDVK-161 bound pipeline shader disagrees with submitted material semantics")
    require(value.get("height_texture_index") == spec["height"],
            "SDVK-161 actual height binding differs from authored positive/control material")
    token = _resource_token(value.get("resource", {}), "material " + name)
    require(token[0] == texture_index, "SDVK-161 submitted material is not the bound texture index")
    layers = value.get("layers")
    require(isinstance(layers, list) and layers, "SDVK-161 submitted material layers unavailable")
    authored = []
    bindings = []
    placeholders = []
    for layer in layers:
        binding = _integer(layer.get("binding"), "material layer binding")
        bindings.append(binding)
        semantic = layer.get("semantic")
        role = layer.get("role")
        source = layer.get("source", {})
        sampler = layer.get("sampler", {})
        require(sampler.get("available") is True, "SDVK-161 actual selected material sampler unavailable")
        if role == "fallback-placeholder":
            require(semantic in ("brightmap-emissive", "detail", "glow") and source.get("lump") == 0
                    and source.get("width") == source.get("height") == 1,
                    "SDVK-161 noncanonical material placeholder hides an authored layer")
            placeholders.append(semantic)
            continue
        require(role == "authored-layer" and type(source.get("lump")) is int and source["lump"] > 0
                and type(source.get("width")) is int and source["width"] > 1
                and type(source.get("height")) is int and source["height"] > 1,
                "SDVK-161 authored material layer lacks its real texture source")
        authored.append(semantic)
        expected = 1 if semantic in ("height", "normal") else expected_filter
        # Other PBR channels retain their inherited default material policy.
        require(sampler.get("min_filter") == expected and sampler.get("mag_filter") == expected
                and sampler.get("mipmap_mode") == expected
                and sampler.get("anisotropy") is False,
                "SDVK-161 actual per-layer sampler differs from semantic/reset policy")
        if semantic in ("height", "normal"):
            require(layer.get("requested_sampling") == 1,
                    "SDVK-161 explicit linear semantic sampling was replaced by albedo policy")
    require(authored == spec["semantics"] and placeholders == ["brightmap-emissive", "detail", "glow"],
            "SDVK-161 material authored semantics/control channels differ")
    require(bindings == list(range(len(layers))) and token[3] == len(layers),
            "SDVK-161 material descriptor layer layout is not the current bound span")
    return token


def _receipt(value: dict) -> tuple[int, int, int]:
    require(isinstance(value, dict), "SDVK-161 missing atlas allocation receipt")
    return (_integer(value.get("owner"), "atlas receipt owner", 1),
            _integer(value.get("incarnation"), "atlas allocation incarnation", 1),
            _integer(value.get("slot"), "atlas receipt slot"))


def _tile_census(row: dict) -> dict[int, dict]:
    state = row["lightmap_state"]
    census = state.get("tile_receipts")
    require(isinstance(census, list) and len(census) == state["live_tiles"],
            "SDVK-161 current live tile receipt census is missing or truncated")
    tiles = {}
    identities = set()
    pages = [0] * state["texture_count"]
    dirty_counts = {"initial": 0, "geometry": 0, "light": 0}
    owners = set()
    for tile in census:
        index = _integer(tile.get("tile"), "current census tile")
        require(index not in tiles and tile.get("valid") is True,
                "SDVK-161 current census contains duplicate or invalid tile receipts")
        identity = _receipt(tile.get("receipt"))
        require(identity not in identities, "SDVK-161 distinct live tiles alias one atlas allocation")
        identities.add(identity)
        owners.add(identity[0])
        page = _integer(tile.get("page"), "current census page")
        require(page < len(pages), "SDVK-161 current census page is outside the current atlas")
        pages[page] += 1
        binding = tile.get("binding", {})
        require(type(binding.get("type")) is int and binding["type"] in (1, 2, 3, 4, 5), "SDVK-161 census binding type is unavailable")
        _integer(binding.get("type_index"), "current binding type index")
        _integer(binding.get("control_sector"), "current binding control sector", -1)
        dirty = tile.get("dirty", {})
        for key in dirty_counts:
            require(type(dirty.get(key)) is bool, "SDVK-161 census dirty state unavailable")
            dirty_counts[key] += int(dirty[key])
        tiles[index] = tile
    require(len(owners) == 1 and pages == state["page_live_tiles"],
            "SDVK-161 current atlas receipt owner/occupancy disagrees with resource state")
    require([dirty_counts[key] for key in ("initial", "geometry", "light")]
            == [state[key] for key in ("initial_dirty", "geometry_dirty", "light_dirty")],
            "SDVK-161 receipt census dirty states disagree with lifecycle state")
    return tiles


def _surface_lightmap(value: dict, resource: dict, tiles: dict[int, dict]) -> tuple | None:
    lightmap = value.get("lightmap", {})
    require(type(lightmap.get("eligible")) is bool,
            "SDVK-161 submitted surface lightmap eligibility unavailable")
    require(lightmap.get("epoch") == resource["lightmap_epoch"],
            "SDVK-161 submitted surface samples a stale atlas resource epoch")
    if not lightmap["eligible"]:
        require(lightmap.get("tile") == -1 and lightmap.get("page") == -1
                and lightmap.get("valid") is False
                and lightmap.get("receipt") == {"owner": 0, "incarnation": 0, "slot": 0},
                "SDVK-161 ineligible surface retains an atlas tile/page receipt")
        return None
    tile = _integer(lightmap.get("tile"), "submitted surface tile")
    require(tile in tiles and lightmap.get("valid") is True,
            "SDVK-161 submitted surface has no current live atlas tile")
    current = tiles[tile]
    receipt = _receipt(lightmap.get("receipt"))
    require(receipt == _receipt(current["receipt"]) and lightmap.get("page") == current["page"],
            "SDVK-161 submitted surface uses a stale page/allocation incarnation")
    owner = value["owner"]
    binding = current["binding"]
    type_index = owner["type_index"]
    require(binding == {"type": owner["type"], "type_index": type_index,
                        "control_sector": owner["control_sector"]},
            "SDVK-161 tile belongs to another side/sector/control namespace")
    return (tile, lightmap["page"], *receipt)


def _context(value: dict, map_name: str) -> dict:
    context = value.get("context", {})
    require(context.get("available") is True and context.get("map") == map_name
            and context.get("root_type") == "main" and context.get("type") in ("main", "portal"),
            "SDVK-161 submitted surface is not a current main/portal view")
    _integer(context.get("identity"), "submitted surface context identity", 1)
    _integer(context.get("epoch"), "submitted surface context epoch", 1)
    depth = _integer(context.get("depth"), "submitted surface context depth")
    require((depth == 0 and context.get("type") == "main" and context.get("parent_identity") == 0)
            or (depth > 0 and context.get("type") == "portal"
                and type(context.get("parent_identity")) is int and context["parent_identity"] > 0),
            "SDVK-161 submitted surface context parent/depth is inconsistent")
    return context


def _plane(value: dict, *, z=None, normal=None) -> None:
    plane = value.get("geometry", {}).get("plane")
    require(isinstance(plane, list) and len(plane) == 4
            and all(type(component) in (int, float) and math.isfinite(component) for component in plane),
            "SDVK-161 submitted selected surface plane unavailable")
    if z is not None:
        require(plane == [0, 0, normal, normal * z],
                "SDVK-161 3D-floor selected/flipped control plane is wrong")


def _validate_submitted_surfaces(raw: dict, native: dict, resources: dict[int, dict]) -> dict:
    censuses = {frame: _tile_census(resource) for frame, resource in resources.items()}
    atlas_owners = {}
    for frame, tiles in censuses.items():
        owner = next(iter(tiles.values()))["receipt"]["owner"]
        incarnation = (frame - 1) // 24
        if incarnation not in atlas_owners:
            atlas_owners[incarnation] = owner
        require(atlas_owners[incarnation] == owner,
                "SDVK-161 material reset replaced its retained atlas allocation owner")
    require(len(set(atlas_owners.values())) == 4,
            "SDVK-161 same-map/cross-map reload reused an earlier atlas receipt owner")
    selected = {frame: [] for frame in WITNESS_FRAMES}
    parents = {}
    material_bindings = {frame: [] for frame in WITNESS_FRAMES}
    for record in raw["records"]:
        value = record.get("data", {})
        if record.get("kind") == "pipeline" and value.get("producer") == "levelmesh-indexed-range":
            frame = record.get("frame")
            parents.setdefault(frame, []).append(value)
        if record.get("kind") != "surface":
            continue
        frame = record.get("frame")
        require(frame in selected and type(record.get("count")) is int and record["count"] >= 1,
                "SDVK-161 surface evidence was emitted outside its fixed witness frames")
        validate_surface_record(value)
        require(value.get("producer") in ("levelmesh-surface-range", "immediate-special-surface"),
                "SDVK-161 surface row is an inventory rather than an actual submitted path")
        require(value.get("mesh_epoch") == resources[frame]["levelmesh"]["epoch"],
                "SDVK-161 submitted surface references a stale LevelMesh owner")
        context = _context(value, MAP_A if frame <= 48 else MAP_B)
        owner = value.get("owner", {})
        require((owner.get("type") in (1, 2, 3, 4, 5) or
                owner.get("type") == 0 and value.get("class") in ("horizon", "mirror", "line-to-line-portal")),
                "SDVK-161 submitted semantic surface type unavailable")
        for key, minimum in (("side", -1), ("sector", 0), ("control_sector", -1), ("portal_group", 0), ("type_index", 0)):
            _integer(owner.get(key), "submitted " + key, minimum)
        require(value.get("geometry", {}).get("triangle_mapping_valid") is True,
                "SDVK-161 submitted triangles map to another subsector/surface span")
        _plane(value)
        key = value.get("key", {})
        shader = key.get("shader", {})
        count = _integer(value.get("draw_count"), "submitted draw count", 1)
        if value["producer"] == "levelmesh-surface-range":
            require(value.get("indexed") is True and shader.get("UseLevelMesh") == 1,
                    "SDVK-161 required mesh surface took an immediate or unbound path")
            first = _integer(value.get("first_index"), "submitted first index")
            child_count = _integer(value.get("index_count"), "submitted child index count", 3)
            batch_first = _integer(value.get("batch_first_index"), "submitted batch first index")
            batch_count = _integer(value.get("batch_index_count"), "submitted batch index count", 3)
            require(count == child_count and first % 3 == child_count % 3 == batch_first % 3 == batch_count % 3 == 0
                    and batch_first <= first and first + child_count <= batch_first + batch_count,
                    "SDVK-161 surface range does not belong to its submitted indexed batch")
            require(any(parent.get("indexed") is True and parent.get("first_index") == batch_first
                        and parent.get("draw_count") == batch_count and parent.get("key") == key
                        and parent.get("context") == context for parent in parents.get(frame, [])),
                    "SDVK-161 surface evidence has no same-frame actual parent range/pipeline/context")
        else:
            require(shader.get("UseLevelMesh") == 0 or value.get("class") in ("horizon", "mirror", "line-to-line-portal"),
                    "SDVK-161 immediate special surface inherited a LevelMesh-only pipeline")
        portal_stencil = value.get("class") in ("horizon", "mirror", "line-to-line-portal")
        if not portal_stencil and value["producer"] == "levelmesh-surface-range":
            require(value["geometry"].get("portal_index") == 0 and value["geometry"].get("is_sky") is False,
                    "SDVK-161 material receiver inherited a portal destination/sky-only identity")
        material = value.get("material", {})
        probe = value.get("probe", {})
        if portal_stencil:
            require(material.get("material", material).get("available") is False and value.get("texture_index") == -1
                    and probe.get("available") is False,
                    "SDVK-161 portal stencil invents material or uniform-probe evidence")
        else:
            texture_index = _integer(value.get("texture_index"), "submitted texture index", 1)
            token = _material(material, shader, texture_index, int(17 <= frame <= 32 or 65 <= frame <= 80))
            for earlier_name, earlier_token in material_bindings[frame]:
                overlaps = token[0] < earlier_token[0] + earlier_token[3] and earlier_token[0] < token[0] + token[3]
                require(not overlaps or (material["name"] == earlier_name and token == earlier_token),
                        "SDVK-161 different submitted materials alias one current bound descriptor block")
            material_bindings[frame].append((material["name"], token))
            require(type(probe.get("authored_index")) is int and probe["authored_index"] >= -1
                    and probe.get("runtime_irradiance_index") == 0 and probe.get("fallback") is True
                    and probe.get("probe_epoch") == resources[frame]["probe_epoch"],
                    "SDVK-161 no-probe control inherited another map's probe target/resource")
            if value["producer"] == "levelmesh-surface-range":
                require(probe["authored_index"] == -1
                        and probe.get("authored_scope") == "not stored in mesh; no authored target claim",
                        "SDVK-161 mesh evidence invents an authored probe selector")
            else:
                require(probe.get("authored_scope") == "current immediate authored uniform selector",
                        "SDVK-161 immediate probe selector scope unavailable")
        lightmap = _surface_lightmap(value, resources[frame], censuses[frame])
        require(not portal_stencil or lightmap is None,
                "SDVK-161 portal mask is misrepresented as a baked material receiver")
        selected[frame].append((value, lightmap))

    summaries = {}
    for frame, draws in selected.items():
        require(draws, f"SDVK-161 frame {frame} has no submitted special-surface witnesses")
        if frame <= 48:
            summaries[frame] = _require_a_surfaces(frame, draws, raw)
        else:
            summaries[frame] = _require_b_surfaces(frame, draws, raw)
    return {"witness_frames": list(WITNESS_FRAMES), "frames": summaries,
            "atlas_allocation_owners": atlas_owners,
            "scope": "actual submitted ranges and material bindings at twelve preregistered witness frames"}



def _require_a_surfaces(frame: int, draws: list[tuple], raw: dict) -> dict:
    materials = {}
    for name, side in (("S161PH", 3), ("S161WP", 4), ("S161PN", 5), ("S161HO", 7), ("S161NO", 8)):
        matches = [(value, tile) for value, tile in draws
                   if value.get("material", {}).get("name") == name
                   and value.get("producer") == "levelmesh-surface-range"
                   and all(value["owner"].get(key) == expected for key, expected in
                           {"type": 1, "side": side, "sector": 0, "type_index": side,
                            "control_sector": -1, "portal_group": 0}.items())
                   and value["context"]["type"] == "main" and value["context"]["depth"] == 0]
        require(matches and all(tile is not None for _, tile in matches),
                f"SDVK-161 frame {frame} lacks actually lightmapped main-view {name} side {side}")
        materials[name] = matches
    decals = [(value, tile) for value, tile in draws if value.get("class") == "decal"
              and value.get("material", {}).get("name") == "S161DCL"]
    require(decals and all(value["producer"] == "immediate-special-surface"
                          and value["owner"]["sector"] == 0 and value["owner"]["side"] == 3
                          and value["owner"]["control_sector"] == -1 and tile is not None
                          and any(tile == receiving and value["context"] == wall["context"]
                                  for wall, receiving in materials["S161PH"])
                          for value, tile in decals),
            f"SDVK-161 frame {frame} lacks an actual decal inheriting its current receiver tile")
    glass = [(value, tile) for value, tile in draws
             if value.get("material", {}).get("name") == "S161GL"]
    require(glass and all(value["owner"]["sector"] == 0 and value["owner"]["side"] in (9, 10)
                         and value["owner"]["type"] == 1 and value["owner"]["control_sector"] == -1
                         and value["producer"] == "immediate-special-surface"
                         and value.get("alpha") == 0.5 and tile is None for value, tile in glass),
            f"SDVK-161 frame {frame} lacks the real translucent-wall material/alpha and explicit unlightmapped fallback")
    reflective = [(value, tile) for value, tile in draws
                  if value.get("class") == "reflective-floor"
                  and value.get("material", {}).get("name") == "S161RF"]
    require(reflective and all(value["owner"]["sector"] == 0 and value["owner"]["type"] == 5
                              and value["owner"]["control_sector"] == -1
                              and value.get("alpha") == 0.75 and tile is not None
                              for value, tile in reflective),
            f"SDVK-161 frame {frame} lacks the actual reflective-floor path and inherited lightmap")
    contexts = [record["data"].get("context", {}) for record in raw["records"]
                if record.get("kind") == "context" and record.get("frame") == frame]
    require(any(context.get("map") == MAP_A and context.get("line_mirror") is True
                and context.get("type") == "portal" and context.get("depth", 0) > 0 for context in contexts),
            f"SDVK-161 frame {frame} lacks a real line-mirror render context")
    require(any(context.get("map") == MAP_A and context.get("plane_mirror") is True
                and context.get("type") == "portal" and context.get("depth", 0) > 0 for context in contexts),
            f"SDVK-161 frame {frame} lacks a real reflective-floor plane-mirror render context")
    horizon = [(value, tile) for value, tile in draws if value.get("class") == "horizon"]
    require(horizon and all(value["owner"]["side"] == 2 and value["owner"]["sector"] == 0
                           for value, _ in horizon),
            f"SDVK-161 frame {frame} lacks an actual Line_Horizon submission")
    horizon_planes = []
    for name, kind, z, normal in (("S161RF", 5, 0, 1), ("SDVFL", 4, 160, -1)):
        contents = [(value, tile) for value, tile in draws if value.get("class") == "horizon-contents"
                    and value.get("material", {}).get("name") == name and value["owner"]["type"] == kind]
        require(contents and all(value["producer"] == "immediate-special-surface" and tile is None
                                 and value["owner"]["side"] == 2 and value["owner"]["type_index"] == 2
                                 and value["owner"]["sector"] == 0 and value["owner"]["control_sector"] == -1
                                 and value["owner"]["portal_group"] == 0 and value.get("alpha") == 1
                                 and value["draw_count"] == 4 for value, tile in contents),
                f"SDVK-161 frame {frame} lacks actual {name} horizon contents with explicit unlightmapped policy")
        for value, _ in contents:
            _plane(value, z=z, normal=normal)
        horizon_planes.append(name)
    mirrors = [value for value, _ in draws if value.get("class") == "mirror"
               and value["owner"]["side"] == 6 and value["owner"]["sector"] == 0]
    require(mirrors, f"SDVK-161 frame {frame} lacks an actual line-mirror stencil submission")
    return {"materials": list(materials), "decal_receiver_shared": True,
            "translucent_wall": "explicit immediate unlightmapped fallback", "reflective_floor": True,
            "line_mirror_context": True, "plane_mirror_context": True, "horizon_submission": True,
            "horizon_contents": horizon_planes}


def _require_b_surfaces(frame: int, draws: list[tuple], raw: dict) -> dict:
    results = {}
    for name, kind, control, z, normal in (("S161T4", 5, 4, 48, 1), ("S161B5", 4, 5, 96, -1)):
        matches = [(value, tile) for value, tile in draws if value.get("material", {}).get("name") == name]
        require(matches, f"SDVK-161 frame {frame} lacks actually submitted {name} 3D-floor plane")
        for value, tile in matches:
            owner, context = value["owner"], value["context"]
            require(value["producer"] == "levelmesh-surface-range" and tile is not None
                    and owner["type"] == kind and owner["sector"] == 6 and owner["control_sector"] == control
                    and owner["portal_group"] == 2 and owner["side"] == -1,
                    "SDVK-161 3D-floor plane used the wrong sector/control/type/portal ownership")
            require(context.get("type") == "portal" and context.get("producer") == "LineToLine"
                    and context.get("depth", 0) > 0 and context.get("portal_group") == 2,
                    "SDVK-161 3D-floor plane is not submitted through the actual linked portal")
            _plane(value, z=z, normal=normal)
        results[name] = len(matches)
    for name, control in (("S161S4", 4), ("S161S5", 5)):
        matches = [(value, tile) for value, tile in draws if value.get("material", {}).get("name") == name
                   and value["owner"]["side"] == 34]
        require(matches and all(value["producer"] == "levelmesh-surface-range" and tile is not None
                                and value["owner"]["type"] == 1 and value["owner"]["sector"] == 1
                                and value["owner"]["control_sector"] == control
                                and value["owner"]["portal_group"] == 2 for value, tile in matches),
                f"SDVK-161 frame {frame} lacks the same-side distinct-control {name} receiver")
        results[name] = len(matches)
    wall_bands = {}
    for name, kind, lower, upper in (("S161PN", 2, 144, 160), ("S161HO", 3, 0, 16)):
        matches = [(value, tile) for value, tile in draws
                   if value.get("material", {}).get("name") == name and value["owner"]["side"] == 34]
        require(matches and all(value["producer"] == "levelmesh-surface-range" and value.get("class") == "wall"
                                and tile is not None and value["owner"]["type"] == kind
                                and value["owner"]["type_index"] == 34 and value["owner"]["sector"] == 1
                                and value["owner"]["control_sector"] == -1 and value["owner"]["portal_group"] == 2
                                and value["context"].get("type") == "portal"
                                and value["context"].get("producer") == "LineToLine"
                                and value["context"].get("portal_group") == 2
                                and value["geometry"].get("vertex_z_min") == lower
                                and value["geometry"].get("vertex_z_max") == upper
                                for value, tile in matches),
                f"SDVK-161 frame {frame} lacks actual ordinary upper/lower {name} wall band with current slot/type/owner/height")
        wall_bands[name] = {"type": kind, "side": 34, "sector": 1, "control_sector": -1,
                            "vertex_z_min": lower, "vertex_z_max": upper, "ranges": len(matches)}
    stencils = [value for value, _ in draws if value.get("class") == "line-to-line-portal"
                and value["owner"]["side"] in (3, 10) and value["owner"]["sector"] in (0, 1)]
    require(stencils, f"SDVK-161 frame {frame} lacks an actual linked-portal stencil submission")
    return {"submitted_3d_floor_controls": results, "ordinary_wall_bands": wall_bands, "linked_portal": True,
            "control_planes": {"4": 48, "5": 96}}


def validate_surface_record(value: dict) -> None:
    """Recipe-independent shape/identity checks for the generic observation gate."""
    require(isinstance(value, dict) and value.get("producer") in
            ("levelmesh-surface-range", "immediate-special-surface"),
            "Unknown submitted surface producer")
    require(isinstance(value.get("context"), dict) and value["context"].get("available") is True,
            "Submitted surface context is unavailable")
    owner = value.get("owner", {})
    require(type(owner.get("type")) is int and (owner["type"] in (1, 2, 3, 4, 5)
            or owner["type"] == 0 and value.get("class") in ("horizon", "mirror", "line-to-line-portal")),
            "Submitted surface owner type is invalid")
    for key, minimum in (("side", -1), ("sector", 0), ("control_sector", -1), ("portal_group", 0), ("type_index", 0)):
        _integer(owner.get(key), "surface owner " + key, minimum)
    _integer(value.get("mesh_epoch"), "surface mesh epoch", 1)
    _integer(value.get("draw_count"), "surface draw count", 1)
    material = value.get("material", {})
    portal_stencil = value.get("class") in ("horizon", "mirror", "line-to-line-portal")
    key = value.get("key", {})
    require(isinstance(key, dict) and isinstance(key.get("shader"), dict) and key["shader"],
            "Submitted surface final pipeline/shader unavailable")
    shader = key["shader"]
    if portal_stencil:
        require(value.get("texture_index") == -1 and material.get("material", material).get("available") is False
                and value.get("probe", {}).get("available") is False,
                "Submitted portal stencil invents a material or uniform probe")
    else:
        _integer(value.get("texture_index"), "surface bound texture index", 1)
        token = _resource_token(material.get("resource", {}), "surface material")
        require(token[0] == value["texture_index"], "Submitted surface material does not match its bound index")
        require(isinstance(material.get("name"), str) and material["name"]
                and isinstance(material.get("layers"), list) and material["layers"],
                "Submitted surface material semantics unavailable")
        require(type(shader.get("EffectState")) is int and type(material.get("shader")) is int
                and shader["EffectState"] == material["shader"],
                "Submitted surface material shader disagrees with final bound pipeline")
    _plane(value)
    require(value["geometry"].get("current_uv_tolerance") == CURRENT_UV_TOLERANCE
            and isinstance(value["geometry"].get("uv_scope"), str) and value["geometry"]["uv_scope"],
            "Submitted surface current-UV tolerance/scope differs from the float-writer contract")
    require(value.get("geometry", {}).get("triangle_mapping_valid") is True,
            "Submitted surface triangle-to-surface mapping is invalid")
    lightmap = value.get("lightmap", {})
    require(type(lightmap.get("eligible")) is bool and type(lightmap.get("valid")) is bool,
            "Submitted surface lightmap eligibility/receipt state unavailable")
    _integer(lightmap.get("epoch"), "surface atlas epoch", 1)
    if lightmap["eligible"]:
        require(value["geometry"].get("current_uv_valid") is True,
                "Submitted receiver UVs do not match its current atlas allocation")
        require(lightmap["valid"] is True, "Submitted surface has an invalid atlas receipt")
        _integer(lightmap.get("tile"), "surface tile")
        _integer(lightmap.get("page"), "surface atlas page")
        _receipt(lightmap.get("receipt"))
    else:
        require(value["geometry"].get("current_uv_valid") is False,
                "Ineligible surface invents validated atlas UV evidence")
        require(lightmap.get("tile") == lightmap.get("page") == -1 and lightmap["valid"] is False
                and lightmap.get("receipt") == {"owner": 0, "incarnation": 0, "slot": 0},
                "Ineligible surface retains an atlas tile/page")
    if value["producer"] == "levelmesh-surface-range":
        require(value.get("indexed") is True and shader.get("UseLevelMesh") == 1,
                "Submitted LevelMesh surface has an immediate/unindexed pipeline")
        first = _integer(value.get("first_index"), "surface first index")
        count = _integer(value.get("index_count"), "surface index count", 3)
        batch_first = _integer(value.get("batch_first_index"), "surface batch first index")
        batch_count = _integer(value.get("batch_index_count"), "surface batch index count", 3)
        require(count == value["draw_count"] and first >= batch_first and first + count <= batch_first + batch_count
                and first % 3 == count % 3 == batch_first % 3 == batch_count % 3 == 0,
                "Submitted surface index range escapes its actual batch")
    else:
        require(shader.get("UseLevelMesh") == 0 or portal_stencil,
                "Immediate special surface has a LevelMesh-only pipeline")
        first = _integer(value.get("first_index"), "immediate submitted first vertex")
        count = _integer(value.get("index_count"), "immediate submitted vertex count", 1)
        vertex_first = _integer(value["geometry"].get("vertex_first"), "immediate owner vertex start")
        vertex_count = _integer(value["geometry"].get("vertex_count"), "immediate owner vertex count", 1)
        require(value.get("indexed") is False and count == value["draw_count"]
                and first >= vertex_first and first + count <= vertex_first + vertex_count,
                "Immediate submitted draw does not belong to the current producer vertex range")


def validate_transition_records(raw: dict, stdout: str, native: dict) -> dict:
    """Validate one authenticated attempt; never pool observations across runs."""
    validate_recipe({"id": SCENE, "native": native})
    require(raw.get("observed_frames") == FRAMES,
            "SDVK-161 retained frame budget differs")
    expected = [f"SDVK161_INPUT phase={phase['phase']} after_main_views={phase['after_main_views']}"
                for phase in SCHEDULE]
    actual = [line for line in stdout.splitlines() if line.startswith("SDVK161_INPUT")]
    require(actual == expected, "SDVK-161 input driver order/count differs from preregistration")
    frames = _one_per_frame(raw, "frame")
    resources = _one_per_frame(raw, "resource")
    owners = {}
    for frame in range(1, FRAMES + 1):
        map_name = MAP_A if frame <= 48 else MAP_B
        incarnation = (frame - 1) // 24
        require(frames[frame].get("map") == map_name,
                "SDVK-161 frame map owner differs from fixed lifecycle phase")
        settings = settings_for_frame(native, frame)
        for key in ("gl_levelmesh", "lm_dynlights", "gl_lightprobe", "gl_texture_filter", "gl_texture_filter_anisotropic"):
            require(frames[frame].get("settings", {}).get(key) == settings[key],
                    "SDVK-161 actual frame setting differs from fixed lifecycle phase")
        _resource_state(resources[frame], map_name)
        owner = (resources[frame]["lightmap_epoch"], resources[frame]["probe_epoch"],
                 resources[frame]["levelmesh"]["epoch"])
        if incarnation not in owners:
            owners[incarnation] = owner
        require(owners[incarnation] == owner,
                "SDVK-161 material sampler reset replaced a retained atlas/probe/mesh owner")
    for incarnation in range(1, 4):
        require(all(right > left for left, right in zip(owners[incarnation - 1], owners[incarnation])),
                "SDVK-161 map reload did not advance every atlas/probe/mesh resource owner")
    cycles = {"invalidate_a_1": _completed_cycle(resources, 9, 24, "first A invalidation"),
              "reload_a": _completed_cycle(resources, 25, 40, "same-map A reload"),
              "invalidate_a_2": _completed_cycle(resources, 41, 48, "second A invalidation"),
              "invalidate_b_1": _completed_cycle(resources, 57, 72, "first B invalidation"),
              "reload_b": _completed_cycle(resources, 73, 88, "same-map B reload"),
              "invalidate_b_2": _completed_cycle(resources, 89, 96, "second B invalidation")}
    require(all(resources[frame]["lightmap_state"]["all_clean"] is True for frame in WITNESS_FRAMES),
            "SDVK-161 lifecycle equivalent-state RGB witness has unconverged lightmap state")
    submitted = _validate_submitted_surfaces(raw, native, resources)
    return {"status": "PASS", "frames": FRAMES, "cycles": cycles,
            "submitted_surfaces": submitted, "resource_owners": owners,
            "physical_gpu_qualified": False,
            "scope": "same-attempt submitted special-surface/material state and current atlas receipt owners; "
                     "no executed-shader or per-texel GPU probe-readback claim"}




def validate_checkpoint_artifacts(artifacts: dict) -> None:
    """Require original checkpoint pins before any retained image is re-read.

    The run validator's existing checked() pass authenticates each pin against
    disk. Membership is a separate obligation: an omitted file cannot become
    authenticated merely because it can still be decoded and pinned today.
    """
    require(isinstance(artifacts, dict), "SDVK-161 checkpoint artifact manifest is unavailable")
    expected = {f"native.surface-{frame}.png" for frame in WITNESS_FRAMES}
    actual = {name for name in artifacts if isinstance(name, str)
              and name.startswith("native.surface-") and name.endswith(".png")}
    require(actual == expected,
            "SDVK-161 original artifact manifest does not pin exactly twelve checkpoint images")
    for name in expected:
        value = artifacts[name]
        require(isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}
                and value.get("path") == name,
                "SDVK-161 checkpoint artifact pin has a wrong filename or shape")
        require(type(value.get("bytes")) is int and 33 <= value["bytes"] <= 16 * 1024 * 1024,
                "SDVK-161 checkpoint artifact pin has an invalid PNG byte count")
        require(isinstance(value.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None,
                "SDVK-161 checkpoint artifact pin has an invalid SHA-256")


def validate_checkpoint_images(root: Path, raw: dict) -> dict:
    """Admit every fixed witness screenshot from this authenticated attempt."""
    from tools.renderer_oracle import images
    root = Path(root).resolve(strict=True)
    require(raw.get("observed_frames") == FRAMES, "SDVK-161 checkpoint capture frame budget differs")
    expected = {frame: f"native.surface-{frame}.png" for frame in WITNESS_FRAMES}
    records = {}
    for record in raw["records"]:
        if record.get("kind") != "surface-checkpoint":
            continue
        frame = record.get("frame")
        value = record.get("data", {})
        require(type(frame) is int and frame in expected and frame not in records
                and type(record.get("count")) is int and record["count"] == 1,
                "SDVK-161 missing/duplicate/wrong-frame checkpoint image record")
        require(value.get("producer") == "completed-main-view-screenshot"
                and value.get("map") == (MAP_A if frame <= 48 else MAP_B)
                and value.get("image") == expected[frame]
                and type(value.get("main_views")) is int and value["main_views"] == WARMUP + frame,
                "SDVK-161 checkpoint image owner/frame/file differs from preregistration")
        records[frame] = value
    require(set(records) == set(expected), "SDVK-161 checkpoint images do not cover all twelve witness frames")
    require({path.name for path in root.glob("native.surface-*.png")} == set(expected.values()),
            "SDVK-161 checkpoint image files are missing or include unregistered frames")
    checkpoints = []
    for frame, name in expected.items():
        path = artifact_path(root, name)
        extent, pixels = images.decode(path)
        require(extent == (640, 480), "SDVK-161 checkpoint screenshot extent differs from 640x480")
        checkpoints.append({"frame": frame, "map": records[frame]["map"],
                            "image": pin(path, relative_to=root), "extent": list(extent),
                            "rgb_sha256": sha256(pixels)})
    groups = {}
    for name, map_name, filtering, frames in LIFECYCLE_RGB_GROUPS:
        reference = frames[0]
        comparisons = []
        for frame in frames[1:]:
            comparison = images.compare(root / expected[reference], root / expected[frame], {"metric": "exact-rgb8"})
            comparisons.append({"reference_frame": reference, "frame": frame, "comparison": comparison})
            require(comparison["passed"] is True and comparison["changed_pixels"] == 0,
                    f"SDVK-161 lifecycle equivalent-state RGB differs: group={name} "
                    f"reference_frame={reference} frame={frame} "
                    f"changed_pixels={comparison['changed_pixels']} max_channel_error={comparison['max_channel_error']}")
        groups[name] = {"map": map_name, "gl_texture_filter": filtering,
                        "frames": list(frames), "comparisons": comparisons}
    return {"status": "PASS", "checkpoints": checkpoints, "lifecycle_equivalent_state_rgb": groups,
            "image_policy": {"metric": "exact-rgb8"}}



def compare_checkpoint_images(left: Path, right: Path) -> dict:
    """Compare corresponding map/phase images with the existing exact RGB decoder."""
    from tools.renderer_oracle import images
    require(Path(left).resolve() != Path(right).resolve(),
            "SDVK-161 checkpoint comparison needs independent attempt directories")
    comparisons = []
    for frame in WITNESS_FRAMES:
        name = f"native.surface-{frame}.png"
        result = images.compare(Path(left) / name, Path(right) / name, {"metric": "exact-rgb8"})
        comparisons.append({"frame": frame, "map": MAP_A if frame <= 48 else MAP_B,
                            "image": name, "comparison": result})
    return {"status": "PASS" if all(row["comparison"]["passed"]
                                     and row["comparison"]["changed_pixels"] == 0
                                     for row in comparisons) else "FAIL",
            "comparisons": comparisons, "image_policy": {"metric": "exact-rgb8"}}



def captured_negatives(raw: dict, stdout: str, native: dict) -> dict:
    """Falsify copied, admitted emitted evidence without another native process."""
    validate_transition_records(raw, stdout, native)
    source_digest = sha256(canonical(raw))
    records = raw["records"]

    def target(name, frame, *, side=None):
        matches = [index for index, record in enumerate(records)
                   if record.get("kind") == "surface" and record.get("frame") == frame
                   and record["data"].get("material", {}).get("name") == name
                   and (side is None or record["data"].get("owner", {}).get("side") == side)]
        require(matches, "SDVK-161 captured negative lacks its actual emitted target: " + name)
        return matches[0]

    wall = target("S161PH", 8)
    underside = target("S161B5", 56)
    side = target("S161S5", 56)
    horizon = target("SDVFL", 8)
    ordinary_upper = target("S161PN", 56, side=34)
    ordinary_lower = target("S161HO", 56, side=34)
    first_frame = next(index for index, record in enumerate(records)
                       if record.get("kind") == "frame" and record.get("frame") == 25)
    tests = [
        ("wrong-submitted-mesh-path", wall, ["data", "key", "shader", "UseLevelMesh"], 0,
         "immediate/unindexed pipeline"),
        ("wrong-bound-material-shader", wall, ["data", "key", "shader", "EffectState"], 0,
         "shader disagrees"),
        ("same-page-stale-receiver-uv", wall, ["data", "geometry", "current_uv_valid"], False,
         "receiver UVs do not match its current atlas allocation"),
        ("stale-allocation-incarnation", wall, ["data", "lightmap", "receipt", "incarnation"],
         records[wall]["data"]["lightmap"]["receipt"]["incarnation"] + 1, "stale page/allocation incarnation"),
        ("cross-control-same-side-substitution", side, ["data", "owner", "control_sector"], 4,
         "another side/sector/control namespace"),
        ("wrong-selected-3d-floor-plane", underside, ["data", "geometry", "plane"], [0, 0, -1, -112],
         "selected/flipped control plane"),
        ("inherited-3d-floor-portal-destination", underside, ["data", "geometry", "portal_index"], 1,
         "inherited a portal destination"),
        ("wrong-actual-horizon-plane", horizon, ["data", "geometry", "plane"], [0, 0, -1, -112],
         "selected/flipped control plane"),
        ("wrong-actual-horizon-material", horizon, ["data", "material", "name"], "S161NO",
         "lacks actual SDVFL horizon contents"),
        ("wrong-ordinary-upper-wall-slot-type", ordinary_upper, ["data", "owner", "type"], 1,
         "another side/sector/control namespace"),
        ("wrong-ordinary-lower-wall-control-owner", ordinary_lower, ["data", "owner", "control_sector"], 4,
         "another side/sector/control namespace"),
        ("wrong-ordinary-upper-wall-height-band", ordinary_upper, ["data", "geometry", "vertex_z_min"], 96,
         "ordinary upper/lower S161PN wall band"),
        ("wrong-current-probe-epoch", wall, ["data", "probe", "probe_epoch"],
         records[wall]["data"]["probe"]["probe_epoch"] + 1, "another map's probe target/resource"),
        ("wrong-lifecycle-map-owner", first_frame, ["data", "map"], MAP_B,
         "frame map owner differs"),
    ]
    controls = []
    for name, index, path, replacement, expected in tests:
        changed = copy.deepcopy(raw)
        current = changed["records"][index]
        for component in path[:-1]:
            current = current[component]
        before = copy.deepcopy(current[path[-1]])
        current[path[-1]] = replacement
        try:
            validate_transition_records(changed, stdout, native)
        except EvidenceError as error:
            require(expected in str(error), "SDVK-161 captured negative rejected for an unintended reason: " + name)
            controls.append({"name": name, "status": "REJECTED", "reason": str(error),
                             "record_index": index, "path": path, "before": before, "after": replacement,
                             "mutant_sha256": sha256(canonical(changed))})
        else:
            raise EvidenceError("SDVK-161 captured negative was incorrectly accepted: " + name)
    changed = copy.deepcopy(raw)
    warp_index, height_index = target("S161WP", 8), target("S161HO", 8)
    warp = changed["records"][warp_index]["data"]
    replacement = copy.deepcopy(records[height_index]["data"]["material"]["resource"])
    before = {"resource": copy.deepcopy(warp["material"]["resource"]), "texture_index": warp["texture_index"]}
    warp["material"]["resource"] = replacement
    warp["texture_index"] = replacement["index"]
    try:
        validate_transition_records(changed, stdout, native)
    except EvidenceError as error:
        require("different submitted materials alias one current bound descriptor block" in str(error),
                "SDVK-161 bound-material alias control rejected for an unintended reason")
        controls.append({"name": "different-material-same-live-bound-block", "status": "REJECTED",
                         "reason": str(error), "record_index": warp_index,
                         "before": before, "after": {"resource": replacement, "texture_index": replacement["index"]},
                         "mutant_sha256": sha256(canonical(changed))})
    else:
        raise EvidenceError("SDVK-161 captured negative accepted another material's live descriptor block")
    changed = copy.deepcopy(raw)
    affected = []
    for index, record in enumerate(changed["records"]):
        if record.get("kind") == "resource" and 9 <= record.get("frame", -1) <= 24:
            record["data"]["lightmap_state"]["frame_tile_completions"] = 0
            affected.append(index)
    try:
        validate_transition_records(changed, stdout, native)
    except EvidenceError as error:
        require("complete real admitted lightmap work" in str(error),
                "SDVK-161 missing-completion negative rejected for an unintended reason")
        controls.append({"name": "missing-actual-invalidation-completion", "status": "REJECTED",
                         "reason": str(error), "record_indices": affected,
                         "path": ["data", "lightmap_state", "frame_tile_completions"], "after": 0,
                         "mutant_sha256": sha256(canonical(changed))})
    else:
        raise EvidenceError("SDVK-161 captured negative accepted no actual invalidation completion")
    require(sha256(canonical(raw)) == source_digest, "SDVK-161 captured controls altered their native source packet")
    return {"schema": "sdvk161-captured-negatives/v1", "status": "PASS", "source_sha256": source_digest,
            "native_execution": False, "controls": controls,
            "scope": "named copies of this independently admitted capture; original emitted state and images unchanged"}


def qualify(args) -> dict:
    from tools.renderer_oracle import native_ci, prepare, run, sdvk010_sun_native
    out = run.fresh_directory(args.out)
    result = {
        "schema": "sdvk161-special-surface-qualification/v1", "status": "FAIL", "steps": [],
        "physical_stop_active": True, "physical_gpu_qualified": False, "performance_accepted": False,
        "physical_cost_scaling_stability": "HELD / NOT ACCEPTED",
        "historical_physical_root_cause": "UNDETERMINED", "automatic_retries": 0,
    }
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit) is not None,
                "Expected exact build commit required")
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()),
                "No CFX experiments in this gate")
        result["software_host"] = sdvk010_sun_native.software_host_guard()
        result["preflight"] = native_ci.preflight(args, out)
        prepared = out / "prepared"
        manifest = prepare.prepare(prepared, [SCENE])
        captures = []
        for name in ("lifecycle-1", "lifecycle-2"):
            target = out / name
            options = argparse.Namespace(
                exe=args.exe, iwad=args.iwad, prepared=prepared, out=target, scene=SCENE,
                mode="state", frames=FRAMES, warmup=WARMUP, timeout=DEADLINE, gpu=False,
                include_stress=True, image_policy="exact", extent=None, collision_snapshot=False,
                publication_witness=False, expected_commit=args.expected_commit, require_clean=True)

            def capture_and_admit():
                receipt = run.capture(options)
                require(receipt.get("status") == "COLLECTED", "Native special-surface capture failed")
                root, _, raw, _ = run.validate_run(target)
                validation = validate_transition_records(raw, (root / "stdout.log").read_text(),
                                                         manifest["scenes"][0]["native"])
                validation["checkpoint_images"] = validate_checkpoint_images(root, raw)
                negatives = captured_negatives(raw, (root / "stdout.log").read_text(), manifest["scenes"][0]["native"])
                negatives["source"] = pin(root / "native.renderer.json", relative_to=root)
                write_json(target / "negative-controls.json", negatives)
                write_json(target / "special-surface-lifecycle.json", validation)
                return receipt

            step = native_ci.attempt(out, name, capture_and_admit, ("COLLECTED",))
            result["steps"].append(step)
            require(step["status"] == "PASS",
                    "Native special-surface attempt failed; no retry/dependent run")
            captures.append(target)
        comparison = run.compare_runs(*captures)
        write_json(out / "repeatability.json", comparison)
        require(comparison.get("status") == "PASS" and comparison.get("state_equal") is True
                and comparison.get("image", {}).get("passed") is True
                and comparison["image"].get("changed_pixels") == 0,
                "SDVK-161 exact semantic state/RGB repeatability failed")
        checkpoints = compare_checkpoint_images(*captures)
        write_json(out / "checkpoint-repeatability.json", checkpoints)
        require(checkpoints["status"] == "PASS", "SDVK-161 checkpoint RGB repeatability failed")
        result.update(status="PASS", checkpoint_comparison=pin(out / "checkpoint-repeatability.json", relative_to=out),
                      captures=[pin(path / "run.json", relative_to=out) for path in captures],
                      comparison=pin(out / "repeatability.json", relative_to=out),
                      lifecycle=[pin(path / "special-surface-lifecycle.json", relative_to=out) for path in captures],
                      negative_controls=[pin(path / "negative-controls.json", relative_to=out) for path in captures],
                      prepared_scene=manifest["scenes"][0]["id"])
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        write_json(out / "qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("exe", "iwad", "iwad-license", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    result = qualify(parser.parse_args(argv))
    print(json.dumps({key: result.get(key) for key in ("schema", "status", "error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
