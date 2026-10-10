"""Structural and cross-record gates for native SDVK observations.

Passing this validator establishes a complete, internally consistent collection,
not universal renderer correctness or performance acceptance.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import copy
import math
import re

try:
    from .common import EvidenceError, canonical, finite, integer, number, require, sha256
except ImportError:
    from common import EvidenceError, canonical, finite, integer, number, require, sha256

KINDS = {"frame", "context", "material", "light-query", "probe", "shadow", "resource", "pipeline", "timing", "sprite-basis"}
VISUAL_TIME_SCOPES = {"main-owner", "main-sibling", "main-portal", "non-main-fallback", "main-view-owner"}
CONTEXT_TYPES = {"main", "camera-texture", "light-probe", "save-picture", "portal"}
ROOT_CONTEXT_TYPES = {"main", "camera-texture", "light-probe", "save-picture"}
VISUAL_TIME_REASONS = {"none", "first-frame", "explicit-reset", "pause", "resume", "level-load", "wipe",
                       "camera-cut", "long-frame-clamped", "clock-rollback", "invalid-timestamp",
                       "repeated-timestamp", "interpolation-disabled", "interpolation-enabled"}


def _visual_time(value, *, context=None, frame=False):
    require(isinstance(value, dict), "Visual-time state is missing or malformed")
    require(value.get("scope") in VISUAL_TIME_SCOPES, "Unknown visual-time scope")
    delta = number(value.get("delta_seconds"), "visual delta seconds")
    accumulated = number(value.get("accumulated_seconds"), "accumulated visual seconds")
    require(0 <= delta <= 0.2 and accumulated >= 0, "Visual-time bounds are invalid")
    integer(value.get("generation"), "visual-time generation")
    integer(value.get("main_frame"), "visual-time main frame")
    for key in ("delta_valid", "interpolation_valid", "clamped"):
        require(type(value.get(key)) is bool, f"Visual-time {key} must be boolean")
    require(value.get("discontinuity") in VISUAL_TIME_REASONS, "Unknown visual-time discontinuity")
    require(value["delta_valid"] or delta == 0, "Invalid visual delta must be zero")
    require(not value["clamped"] or (abs(delta - 0.2) <= 1e-12 and not value["interpolation_valid"]
                                     and value["discontinuity"] == "long-frame-clamped"),
            "Clamped visual-time sample is inconsistent")
    if frame:
        require(value["scope"] == "main-view-owner", "Frame visual-time state must describe the main-view owner")
    if context is not None:
        require(type(value.get("advances_main_clock")) is bool, "Context visual-time ownership flag is missing")
        if context["root_type"] != "main":
            expected_scope = "non-main-fallback"
        elif context["type"] == "portal":
            expected_scope = "main-portal"
        elif context["eye"] == 0:
            expected_scope = "main-owner"
        else:
            expected_scope = "main-sibling"
        require(value["scope"] == expected_scope, "PF-010 context and visual-time scope disagree")
        require(value["advances_main_clock"] is (expected_scope == "main-owner"),
                "PF-010 context visual-time owner is inconsistent")
        if expected_scope == "non-main-fallback":
            require(delta == 0 and accumulated == 0 and not value["delta_valid"] and
                    not value["interpolation_valid"] and not value["clamped"],
                    "Non-main render context contains main visual-time state")
    return value


def _availability(value, label):
    require(isinstance(value, dict) and type(value.get("available")) is bool,
            f"{label} must explicitly declare availability")
    if not value["available"]:
        reason = value.get("reason") or value.get("unavailable_batches")
        require(bool(reason), f"Unavailable {label} needs a reason")


def _vector(value, size, label):
    require(isinstance(value, list) and len(value) == size and
            all(type(v) in (int, float) for v in value), f"Invalid {label}")
    finite(value)


def _resource(value, label):
    _availability(value, label)
    if value["available"]:
        integer(value.get("index"), label + " index")
        for key in ("generation", "epoch", "span"):
            integer(value.get(key), label + " " + key, minimum=1)


def _sampler(value):
    _availability(value, "selected sampler")
    if value["available"]:
        for key in ("min_filter", "mag_filter", "mipmap_mode", "address_u", "address_v", "address_w"):
            integer(value.get(key), "sampler " + key)
        for key in ("min_lod", "max_lod", "max_anisotropy"):
            number(value.get(key), "sampler " + key)
        require(value["min_lod"] <= value["max_lod"], "Sampler LOD range is reversed")
        require(type(value.get("lod_bias")) in (int, float), "Sampler LOD bias is missing")
        require(type(value.get("anisotropy")) is bool, "Sampler anisotropy mode is missing")


def _context(value):
    _availability(value, "context")
    if not value["available"]:
        return None
    for key in ("semantic_key", "producer", "map", "type", "root_type"):
        require(isinstance(value.get(key), str) and value[key], f"Context {key} is missing")
    require(value["type"] in CONTEXT_TYPES, "Unknown PF-010 context type")
    require(value["root_type"] in ROOT_CONTEXT_TYPES, "Unknown PF-010 root context type")
    require((value["type"] == "portal") == (value["depth"] > 0), "PF-010 portal type/depth disagree")
    require(value.get("angle_space") == "hardware-view", "Context angle domain is missing")
    for key in ("epoch", "identity"):
        integer(value.get(key), f"context {key}", minimum=1)
    integer(value.get("parent_identity"), "context parent identity")
    integer(value.get("depth"), "context depth", maximum=31)
    require((value["parent_identity"] == 0) == (value["depth"] == 0), "Context parent/depth disagree")
    require(value["parent_identity"] != value["identity"], "Context is its own parent")
    for key in ("mirrored", "line_mirror", "plane_mirror", "history_eligible", "postprocess_eligible"):
        require(type(value.get(key)) is bool, f"Context {key} must be boolean")
    require(value["mirrored"] == (value["line_mirror"] != value["plane_mirror"]), "Context mirror parity disagrees")
    _vector(value.get("position"), 3, "context position")
    _vector(value.get("angles"), 3, "context angles")
    number(value.get("fraction"), "context tic fraction")
    require(value["fraction"] <= 1, "Context tic fraction exceeds one")
    if "visual_time" in value:
        _visual_time(value["visual_time"], context=value)
    return value["epoch"], value["identity"]


def _sprite_basis(value):
    """SDVK-007: validate the *emitted draw* uniform and PF-009 provenance."""
    require(value.get("uniform_scope") == "emitted-vulkan-draw-after-apply-surface-uniforms",
            "Sprite tangent exists only as a proposed buffer value, not emitted draw state")
    require(type(value.get("indexed")) is bool and not value["indexed"],
            "Immediate sprite card must be an unindexed quad")
    integer(value.get("draw_count"), "sprite draw vertex count", minimum=4, maximum=4)
    integer(value.get("shader"), "sprite material shader", minimum=-1)
    integer(value.get("height_texture_index"), "sprite height semantic index", minimum=-1)
    require(isinstance(value.get("material"), str), "Sprite material identity absent")
    surface = value.get("surface")
    require(isinstance(surface, dict) and surface.get("contract") == "sdvk-007-final-quad/v1" and
            surface.get("orientation_source") == "pf-009-calculate-vertices",
            "Sprite tangent claims explicit ownership without PF-009 state")
    for key in ("source", "presentation", "sprite_type", "actor_sprite", "actor_frame",
                "source_portal_group", "render_portal_group", "through_portal_mode"):
        integer(surface.get(key), "sprite surface " + key, minimum=-2147483648)
    require(surface["source"] in (0, 1, 2) and surface["presentation"] in (0, 1, 2, 3, 4),
            "Sprite tangent may not claim a model/unknown presentation")
    for key in ("frame_mirrored", "uv_mirror_x", "uv_mirror_y", "portal_mirrored",
                "xy_billboard", "faces_camera", "basis_valid"):
        require(type(surface.get(key)) is bool, "Sprite " + key + " missing")
    require(surface.get("selection") in ("explicit-sprite", "legacy-derivative-fallback"),
            "Unknown sprite tangent fallback")
    require(isinstance(surface.get("basis_reason"), str) and surface["basis_reason"],
            "Missing explicit sprite tangent derivation/fallback reason")
    _vector(surface.get("uv"), 4, "sprite signed UV endpoints")
    _vector(surface.get("render_angles"), 3, "sprite render angles")
    _vector(surface.get("view_angles"), 3, "sprite view angles")
    _vector(value.get("tangent"), 3, "emitted tangent")
    _vector(value.get("normal"), 3, "emitted normal")
    handedness = number(value.get("handedness"), "sprite tangent handedness", minimum=-1)
    u_sign = number(surface.get("u_sign"), "sprite U sign", minimum=-1)
    v_sign = number(surface.get("v_sign"), "sprite V sign", minimum=-1)
    expected_hand = number(surface.get("expected_handedness"), "sprite expected hand", minimum=-1)
    parity = number(surface.get("view_parity"), "sprite parity", minimum=-1)
    explicit = value.get("explicit")
    require(type(explicit) is bool and explicit is surface["basis_valid"] and
            (surface["selection"] == "explicit-sprite") is explicit,
            "Explicit sprite basis state disagrees with source selection")
    context = value.get("context")
    require(isinstance(context, dict) and context.get("available") is True and
            context.get("mirrored") is surface["portal_mirrored"],
            "Sprite tangent source and active PF-010 mirror context disagree")
    if explicit:
        require(u_sign in (-1, 1) and v_sign in (-1, 1) and
                handedness in (-1, 1) and expected_hand == -u_sign*v_sign and
                handedness == expected_hand,
                "Impossible sprite tangent handedness or signed-UV mirror parity")
        uv = surface["uv"]
        require((uv[1] - uv[0])*u_sign > 0 and (uv[3] - uv[2])*v_sign > 0,
                "Sprite tangent was not derived from the selected frame UV endpoints")
        require(parity == handedness*(-1 if surface["portal_mirrored"] else 1),
                "Sprite view mirror parity was inverted twice or omitted")
        # Actor GetSpriteUR->UL is the inherited non-mirror convention.
        if surface["source"] == 0:
            require(surface["uv_mirror_x"] is (u_sign > 0) and
                    surface["uv_mirror_y"] is (v_sign < 0),
                    "PF-009 actor frame/flip flags disagree with final signed UV axes")
        tangent, normal = value["tangent"], value["normal"]
        dot = sum(a*b for a, b in zip(tangent, normal))
        for axis in (tangent, normal):
            require(abs(sum(c*c for c in axis) - 1.0) <= 2e-3, "Unnormalized sprite tangent axis")
        require(abs(dot) <= 2e-3, "Nonorthogonal sprite tangent axes")
        bitangent = [handedness*(normal[1]*tangent[2]-normal[2]*tangent[1]),
                     handedness*(normal[2]*tangent[0]-normal[0]*tangent[2]),
                     handedness*(normal[0]*tangent[1]-normal[1]*tangent[0])]
        require(abs(sum(c*c for c in bitangent)-1) <= 2e-3,
                "Degenerate reconstructed sprite bitangent")
    else:
        require(handedness == expected_hand == parity == 0 and
                value["tangent"] == [0, 0, 0] and value["normal"] == [0, 0, 0],
                "Fallback sprite draw retained stale explicit vectors/handedness")


def observation(data, *, required_kinds=(), expected_map=None, expected_frames=None, expected_extent=None):
    try:
        return _observation(data, required_kinds=required_kinds, expected_map=expected_map,
                            expected_frames=expected_frames, expected_extent=expected_extent)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise EvidenceError("Malformed native observation field: " + str(error)) from error


def _observation(data, *, required_kinds, expected_map, expected_frames, expected_extent):
    require(isinstance(data, dict) and data.get("schema") == "sdvk-renderer-observation/v1", "Unknown native observation schema")
    finite(data)
    require(data.get("status") == "COLLECTED_PENDING_VALIDATION" and data.get("error") == "",
            "Native collector failed or did not finish")
    require(data.get("mode") in ("state", "timing"), "Unknown observation mode")
    require(type(data.get("gpu_timing_requested")) is bool, "GPU timing request mode is missing")
    require(data.get("performance_accepted") is False, "A collector cannot award performance acceptance")
    count = integer(data.get("observed_frames"), "observed frames", minimum=1, maximum=4096)
    require(count == integer(data.get("requested_frames"), "requested frames", minimum=1, maximum=4096),
            "Native frame interval is incomplete")
    if expected_frames is not None:
        require(count == expected_frames, "Native frame count differs from the preregistered request")
    integer(data.get("warmup_frames"), "warmup frames", maximum=100000)
    require(type(data.get("dropped_records")) is int and data["dropped_records"] == 0, "Truncated native observations are not evidence")
    build = data.get("build", {})
    require(isinstance(build, dict) and re.fullmatch(r"[0-9a-f]{40}", build.get("commit", "")),
            "Native build needs a full source commit")
    require(build.get("working_tree") in ("clean", "modified"), "Unknown native working-tree identity")
    for key in ("backend", "device", "renderer", "identity"):
        require(isinstance(build.get(key), str) and build[key], f"Native build {key} is missing")
    records = data.get("records")
    require(isinstance(records, list) and 0 < len(records) <= 65536, "Native record count out of bounds")
    limits = data.get("limits", {})
    require(limits.get("retained_records") == len(records), "Native retained record count differs")
    require(integer(limits.get("retained_bytes"), "retained bytes") <= 16 * 1024 * 1024,
            "Native retained bytes exceed the declared limit")
    for key, exact in (("max_frames", 4096), ("max_records", 65536), ("max_record_bytes", 16384),
                       ("max_retained_bytes", 16 * 1024 * 1024)):
        require(limits.get(key) == exact, f"Unknown collector bound: {key}")
    availability = data.get("availability", {})
    for channel in ("cpu_timing", "gpu_timing", "gpu_total_frame", "state"):
        _availability(availability.get(channel), channel)
    require(availability["cpu_timing"]["available"] is True, "Complete renderer frames need CPU measurements")
    require(availability["state"]["available"] is (data["mode"] == "state"), "Mode/state availability mismatch")
    require(availability["gpu_total_frame"]["available"] is False, "Named GPU groups do not establish whole-frame GPU time")
    frames, kinds, contexts, frame_kinds, material_frames = {}, set(), {}, {}, set()
    for record in records:
        require(isinstance(record, dict) and set(record) == {"kind", "frame", "count", "data"}, "Invalid observation record envelope")
        kind = record["kind"]
        require(kind in KINDS, f"Unknown observation kind: {kind}")
        frame = integer(record["frame"], "record frame", minimum=1, maximum=count)
        integer(record["count"], "record multiplicity", minimum=1)
        value = record["data"]
        require(isinstance(value, dict) and value, "Observation record has no data")
        kinds.add(kind)
        frame_kinds.setdefault(frame, set()).add(kind)
        if kind == "frame":
            require(frame not in frames and record["count"] == 1, "Duplicate/multiplied native frame sample")
            frames[frame] = value
            number(value.get("cpu_render_view_ms"), "CPU RenderView time")
            if "visual_time" in value:
                _visual_time(value["visual_time"], frame=True)
            require(value.get("state_instrumentation") is (data["mode"] == "state"), "Frame instrumentation/mode mismatch")
            require(value.get("hardware_renderer") is True, "Software game renderer is not a Vulkan renderer observation")
            light_counter_keys = ("authored_lights", "active_lights", "spot_lights", "subtractive_lights", "additive_lights",
                                  "actor_light_queries", "actor_light_candidates", "actor_light_selected", "actor_light_filtered",
                                  "actor_light_duplicates", "actor_light_traces")
            present_light_counters = [key for key in light_counter_keys if key in value]
            if present_light_counters:
                require(len(present_light_counters) == len(light_counter_keys),
                        "Many-light frame counters must be emitted as one complete group")
                if value["state_instrumentation"]:
                    for key in light_counter_keys:
                        integer(value.get(key), key, minimum=0)
                    require(value["actor_light_candidates"] == value["actor_light_selected"] + value["actor_light_filtered"] + value["actor_light_duplicates"],
                            "Actor-light aggregate partition disagrees")
                else:
                    require(all(value.get(key) is None for key in light_counter_keys),
                            "Timing-mode many-light counters must remain null")
            integer(value.get("gametic"), "actual simulation tic")
            camera = value.get("camera", {})
            _vector(camera.get("position"), 3, "actual camera position")
            _vector(camera.get("angles"), 3, "actual camera angles")
            _vector(camera.get("hardware_angles"), 3, "actual hardware view angles")
            number(camera.get("fraction"), "actual camera fraction")
            require(camera["fraction"] <= 1, "Actual camera fraction exceeds one")
            number(camera.get("fov"), "actual camera FOV")
            require(isinstance(value.get("settings"), dict) and value["settings"], "Actual renderer settings are missing")
            for key in ("walls", "flats", "sprites", "decals", "portals", "vertices", "width", "height"):
                integer(value.get(key), key)
            if expected_map is not None:
                require(value.get("map") == expected_map, "Captured a different map/title screen")
            if expected_extent is not None:
                require([value["width"], value["height"]] == list(expected_extent), "Native client extent differs")
        elif kind == "context":
            context = value.get("context")
            token = _context(context)
            require(token is not None, "Actual scene context may not be marked unavailable")
            key = (frame, *token)
            require(key not in contexts or contexts[key] == context, "One context token names different scene state")
            contexts[key] = context
        elif kind == "light-query":
            require(value.get("decision") in ("selected", "actor-policy-rejected", "radius-rejected", "duplicate-rejected", "visibility-rejected",
                                               "attenuation-or-shadow-rejected", "query-empty", "query-summary"),
                    "Unknown actual light decision")
            require(isinstance(value.get("candidate_source"), str) and value["candidate_source"], "Light query source is missing")
            if value["decision"] == "query-summary":
                for key in ("considered", "selected", "filtered", "duplicates", "traces"):
                    integer(value.get(key), "light query " + key)
                require(value["considered"] == value["selected"] + value["filtered"] + value["duplicates"],
                        "Light query partition disagrees")
            elif value["decision"] == "query-empty":
                _availability(value.get("light"), "empty light query candidate")
                require(value["light"]["available"] is False, "Empty light query unexpectedly names a candidate")
            else:
                require(isinstance(value.get("light"), dict) and value["light"].get("semantic_key"), "Light identity is missing or unavailable")
        elif kind == "material":
            if "material" in value:
                _availability(value["material"], "draw material")
                require(value["material"]["available"] is False, "A present material needs its semantic identity and layers")
            else:
                require(isinstance(value.get("semantic_key"), str) and isinstance(value.get("name"), str), "Material semantic identity is missing")
                layers = value.get("layers")
                require(isinstance(layers, list) and layers and len(layers) <= 256, "Material has no bounded semantic layers")
                require([layer.get("binding") for layer in layers] == list(range(len(layers))), "Material layer bindings are missing/duplicate/unordered")
                for layer in layers:
                    require(isinstance(layer.get("semantic"), str) and layer["semantic"], "Layer semantic is missing")
                    require(layer.get("role") in ("authored-layer", "fallback-placeholder", "global-custom",
                                                  "shader-required auxiliary resource, not an authored semantic layer"),
                            "Material layer role is missing or unknown")
                    _sampler(layer.get("sampler"))
                height_layers = [layer for layer in layers if layer.get("semantic") == "height" and layer.get("role") == "authored-layer"]
                height_index = integer(value.get("height_texture_index", -1), "height texture index", minimum=-1)
                require(len(height_layers) <= 1, "Material has duplicate height semantic bindings")
                require(height_index == (height_layers[0]["binding"] if height_layers else -1),
                        "Height semantic binding and shader-visible index disagree")
                _resource(value.get("resource"), "material resource identity")
                material_frames.add(frame)
        elif kind == "sprite-basis":
            _sprite_basis(value)
        elif kind == "probe":
            require(value.get("mode") == "uniform-environment-pair", "Unknown probe identity domain")
            integer(value.get("authored_index"), "authored probe index", minimum=-1)
            integer(value.get("runtime_irradiance_index"), "runtime probe index")
            require(value.get("fallback") is (value["runtime_irradiance_index"] == 0), "Probe sentinel/fallback disagree")
            _resource(value.get("resource"), "probe resource identity")
            if value["resource"]["available"]:
                require(value["resource"]["index"] == value["runtime_irradiance_index"], "Probe uniform/resource indices disagree")
            require(not value["fallback"] or value["resource"]["available"] is False,
                    "No-probe sentinel unexpectedly has a live resource")
        elif kind == "pipeline":
            require(isinstance(value.get("key"), dict) and isinstance(value["key"].get("shader"), dict)
                    and value["key"]["shader"], "Pipeline/shader field identity is missing")
            integer(value.get("draw_count"), "draw count")
        elif kind == "resource":
            capacity = integer(value.get("descriptor_capacity"), "descriptor capacity", minimum=1)
            current = integer(value.get("descriptor_current"), "descriptor current")
            high = integer(value.get("descriptor_high_water"), "descriptor high water")
            start = integer(value.get("descriptor_dynamic_start"), "descriptor dynamic start")
            require(start <= capacity and current <= high <= capacity - start, "Descriptor range/high-water accounting disagrees")
            light_uploads = value.get("light_uploads")
            if light_uploads is not None:
                _availability(light_uploads, "dynamic-light uploads")
                if light_uploads["available"]:
                    range_capacity = integer(light_uploads.get("range_capacity"), "light range capacity", minimum=1)
                    record_capacity = integer(light_uploads.get("record_capacity"), "light record capacity", minimum=1)
                    range_capacity_bytes = integer(light_uploads.get("range_capacity_bytes"), "light range capacity bytes", minimum=16)
                    record_capacity_bytes = integer(light_uploads.get("record_capacity_bytes"), "light record capacity bytes", minimum=80)
                    require(range_capacity_bytes == range_capacity * 16 and record_capacity_bytes == record_capacity * 80,
                            "Dynamic-light capacity byte accounting disagrees")
                    ranges = integer(light_uploads.get("range_entries_used"), "light range entries used", minimum=0)
                    records_used = integer(light_uploads.get("records_used"), "light records used", minimum=0)
                    attempts = integer(light_uploads.get("attempts"), "light upload attempts", minimum=0)
                    successful = integer(light_uploads.get("successful"), "successful light uploads", minimum=0)
                    failed = integer(light_uploads.get("failed"), "failed light uploads", minimum=0)
                    index_failures = integer(light_uploads.get("index_capacity_failures"), "light range-capacity failures", minimum=0)
                    data_failures = integer(light_uploads.get("data_capacity_failures"), "light data-capacity failures", minimum=0)
                    classes = [integer(light_uploads.get(key), key, minimum=0) for key in
                               ("normal_records", "subtractive_records", "additive_records")]
                    uploaded = integer(light_uploads.get("uploaded_bytes"), "light uploaded bytes", minimum=0)
                    peak = integer(light_uploads.get("peak_records_per_upload"), "peak records per upload", minimum=0)
                    require(ranges <= range_capacity and records_used <= record_capacity, "Dynamic-light upload usage exceeds capacity")
                    require(attempts == successful + failed and ranges == successful, "Dynamic-light upload attempt accounting disagrees")
                    require(sum(classes) == records_used, "Dynamic-light class totals disagree with uploaded records")
                    require(uploaded == successful * 16 + records_used * 80, "Dynamic-light upload byte accounting disagrees")
                    histogram = light_uploads.get("records_per_upload_histogram")
                    require(isinstance(histogram, dict), "Dynamic-light upload histogram is missing")
                    bins = [integer(histogram.get(key), "light upload histogram " + key, minimum=0) for key in
                            ("empty", "1_4", "5_16", "17_64", "65_256", "257_plus")]
                    require(sum(bins) == successful, "Dynamic-light upload histogram does not cover successful uploads")
                    require(peak <= records_used and index_failures <= failed and data_failures <= failed,
                            "Dynamic-light upload peak/failure accounting disagrees")
                    require(failed == 0, "Dynamic-light upload capacity fallback occurred")
            for key in ("texture_epoch", "lightmap_epoch", "probe_epoch", "async_upload_epoch"):
                integer(value.get(key), key, minimum=1)
        elif kind == "shadow":
            require(value.get("mode") in ("disabled", "dynamic-1d-shadow-map", "world-trace", "world-trace-precise"),
                    "Unknown shadow representation")
            require(value.get("caster") == "world-geometry", "Unsupported shadow caster claim")
            if "decision" in value:
                require(value["decision"] in ("selected", "capacity-rejected", "not-eligible"), "Unknown shadow selection decision")
                row = integer(value.get("row"), "shadow row", minimum=-1, maximum=1023)
                require((row >= 0) == (value["decision"] == "selected"), "Shadow row/selection disagree")
        elif kind == "timing":
            if value.get("available") is False:
                _availability(value, "GPU batch")
            else:
                require(record["count"] == 1, "Timing samples must preserve their individual observations")
                require(value.get("clock") == "gpu" and isinstance(value.get("name"), str) and value["name"], "Unknown GPU timing scope")
                number(value.get("milliseconds"), "GPU timestamp duration")
        if "context" in value and kind != "context":
            _context(value["context"])
    require(set(frames) == set(range(1, count + 1)), "Missing native frame samples")
    for key, context in contexts.items():
        if context["parent_identity"]:
            parent = contexts.get((key[0], context["epoch"], context["parent_identity"]))
            require(parent is not None and parent["depth"] + 1 == context["depth"], "Context parent is missing or has wrong depth")
    for record in records:
        context = record["data"].get("context")
        if context and context.get("available"):
            require(contexts.get((record["frame"], context["epoch"], context["identity"])) == context,
                    "Draw/query references an unobserved or inconsistent context")
    require(set(required_kinds).issubset(KINDS), "Required observation kind is unknown")
    require(set(required_kinds).issubset(kinds), "Required observation channels missing: " + ", ".join(sorted(set(required_kinds) - kinds)))
    for frame in range(1, count + 1):
        require(set(required_kinds).issubset(frame_kinds[frame]), f"Frame {frame} is missing a required observation channel")
        if "material" in required_kinds:
            require(frame in material_frames, f"Frame {frame} has no actual material binding")
    gpu_groups = sum(r["count"] for r in records if r["kind"] == "timing" and r["data"].get("clock") == "gpu")
    require(integer(availability["gpu_timing"].get("groups"), "resolved GPU groups") == gpu_groups
            and availability["gpu_timing"]["available"] is bool(gpu_groups), "GPU group accounting/availability disagrees")
    require(not gpu_groups or data["gpu_timing_requested"], "Unrequested GPU timing groups were recorded")
    require(data["mode"] == "state" or not (kinds - {"frame", "resource", "timing"}), "Timing-only mode contains per-draw state instrumentation")
    return {"status": "PASS", "scope": "collection integrity and declared state-channel coverage",
            "frames": count, "records": len(records), "kinds": sorted(kinds),
            "working_tree": build["working_tree"], "native_acceptance_awarded": False}


def state_projection(data, *, static_scene=False):
    """Keep decisions/order/counts; normalize only proven context-local tokens.

For a corpus-declared static scene, tic/fraction labels can vary after startup.
Context/view numeric representation is canonicalized to 1e-9. The redundant
derived semantic_key text is omitted from equality because its producer is now
an explicit validated field and its numeric components are compared directly.
Renderer-local descriptor slots and selected shadow-map row numbers are
normalized by live identity while preserving aliasing and rejection sentinels.
Raw resource workload counters remain in evidence, but process-cumulative/lazy allocation,
upload and staging-volume telemetry is excluded from semantic equality;
capacities, epochs, resets/cancellations, waits/dedicated staging, failure/
rejection state, aliasing, generation/span, light-list order, pipeline keys and
fallbacks remain compared.
"""
    observation(data)
    require(data["mode"] == "state", "State comparison requires state-mode observations")

    contexts = {(record["frame"], record["data"]["context"]["epoch"], record["data"]["context"]["identity"]): record["data"]["context"]
                for record in data["records"] if record["kind"] == "context"}

    normalized_contexts = {}
    normalized_resources = {}
    normalized_shadow_rows = {}

    def resource_ordinal(resource):
        token = (resource["index"], resource["generation"], resource["epoch"], resource["span"])
        if token not in normalized_resources:
            normalized_resources[token] = len(normalized_resources)
        return normalized_resources[token]

    def shadow_row_ordinal(frame, row):
        # A shadow-map row is an allocator-local frame identity. Keep the -1
        # rejection sentinel exact and normalize selected rows bijectively so
        # aliasing changes still fail comparison.
        if row == -1:
            return -1
        token = (frame, row)
        if token not in normalized_shadow_rows:
            normalized_shadow_rows[token] = sum(1 for key in normalized_shadow_rows if key[0] == frame)
        return normalized_shadow_rows[token]

    def comparison_number(value):
        rounded = round(float(value), 9)
        return 0.0 if rounded == 0 else rounded

    def comparison_vector(value):
        return [comparison_number(item) for item in value]

    def comparison_vector_label(value):
        return "[" + ",".join(format(comparison_number(item), ".15g") for item in value) + "]"

    def visual_time_projection(value):
        # Raw observations retain wall-clock magnitudes and discontinuity state.
        # Cross-process scene equality keeps only stable PF-010 ownership so
        # scheduler/driver pacing cannot become semantic renderer state.
        return {key: value[key] for key in ("scope", "advances_main_clock") if key in value}

    def normalized_context(frame, context):
        token = (frame, context["epoch"], context["identity"])
        if token not in normalized_contexts:
            result = copy.deepcopy(context)
            parent = context["parent_identity"]
            result["parent_context_sha256"] = sha256(canonical(normalized_context(
                frame, contexts[(frame, context["epoch"], parent)]))) if parent else None
            for key in ("epoch", "identity", "parent_identity"):
                result.pop(key, None)
            for key in ("position", "angles"):
                result[key] = comparison_vector(result[key])
            # semantic_key is a human-readable derivative of the explicit
            # producer/context fields and numeric vectors above.
            result.pop("semantic_key", None)
            if "visual_time" in result:
                result["visual_time"] = visual_time_projection(result["visual_time"])
            if static_scene:
                result.pop("gametic", None)
                result.pop("fraction", None)
            normalized_contexts[token] = result
        return normalized_contexts[token]

    def project(value, frame):
        if isinstance(value, list):
            return [project(item, frame) for item in value]
        if not isinstance(value, dict):
            return value
        if value.get("available") is True and "semantic_key" in value and "root_type" in value:
            return normalized_context(frame, value)
        result = {key: project(item, frame) for key, item in value.items()}
        if value.get("available") is True and all(key in value for key in ("index", "generation", "epoch", "span")):
            result["index"] = resource_ordinal(value)
        resource = value.get("resource")
        if isinstance(resource, dict) and resource.get("available") is True and "runtime_irradiance_index" in value:
            result["runtime_irradiance_index"] = resource_ordinal(resource)
        if (value.get("caster") == "world-geometry" and "decision" in value
                and isinstance(value.get("row"), int) and not isinstance(value.get("row"), bool)):
            result["row"] = shadow_row_ordinal(frame, value["row"])
        return result

    ordered = []
    for record in data["records"]:
        if record["kind"] == "timing":
            continue
        row = project(record, record["frame"])
        if row["kind"] == "frame":
            row["data"].pop("cpu_render_view_ms", None)
            if "visual_time" in row["data"]:
                row["data"]["visual_time"] = visual_time_projection(row["data"]["visual_time"])
            camera = row["data"]["camera"]
            for key in ("position", "angles", "hardware_angles"):
                camera[key] = comparison_vector(camera[key])
            camera["fov"] = comparison_number(camera["fov"])
            if static_scene:
                row["data"].pop("gametic", None)
                camera.pop("fraction", None)
        elif row["kind"] == "resource":
            # Raw receipts retain these counters. Fresh processes may perform
            # different lazy allocations/uploads before an otherwise identical
            # frame, so semantic state equality excludes workload telemetry while
            # retaining capacities, epochs and all failure/rejection diagnostics.
            for key in ("descriptor_current", "descriptor_high_water", "descriptor_allocations",
                        "descriptor_reuses", "descriptor_frees", "hardware_textures"):
                row["data"].pop(key, None)
            lifetime = row["data"].get("lifetime")
            if isinstance(lifetime, dict):
                for key in ("activations", "retirements"):
                    lifetime.pop(key, None)
            uploads = row["data"].get("async_uploads")
            if isinstance(uploads, dict):
                for key in ("queued", "completed"):
                    uploads.pop(key, None)
            staging = row["data"].get("staging")
            if isinstance(staging, dict):
                for key in ("requests", "bytes", "high_water", "reuses"):
                    staging.pop(key, None)
        ordered.append(row)
    return ordered
