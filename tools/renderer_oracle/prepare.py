#!/usr/bin/env python3
"""Prepare the SDVK renderer corpus without launching or qualifying a renderer.

The retained PF generators remain authoritative and unchanged. Their pure member
generators are called directly; no IWAD pixels are copied. New maps use authored
UDMF, ZScript and generated RGBA textures. Prepared manifests contain relative
paths, fixed archive metadata and actual source hashes, so two preparations of
the same source are byte-for-byte comparable in different output directories.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "tools/renderer_oracle/corpus.json"
SCHEMA = "sdvk-renderer-prepared/v1"
GENERATORS = {"pf_view", "pf_indexed", "pf_pbr", "compositing", "lighting",
              "material_stress", "sun_probes", "sprite_mirror"}
CLASSES = {"sprite_orientation", "semantic_materials", "lights_occlusion",
           "probes_sun", "portals_views", "decals_canvas_translucency",
           "shadows", "resource_stress"}
CHANNELS = {"context", "material", "light-query", "probe", "shadow", "resource", "pipeline", "sprite-basis"}

sys.path.insert(0, str(ROOT))
from tools.pf_oracle import prepare_freeze_view_fixture as pf_view
from tools.pf_oracle import prepare_indexed_material_runtime as pf_indexed
from tools.pf_oracle import prepare_pbr_probe_runtime as pf_pbr


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Expected a nonempty repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or ":" in value:
        raise ValueError(f"Unsafe relative path: {value}")
    return value


def _file(root: Path, value: str) -> Path:
    path = root / relative_path(value)
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Source must be a regular file within the repository: {value}")
    return path


def load_catalog(path: Path = CATALOG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def setting_literal(value: object) -> str:
    """One finite, literal CVar value valid in both INI and console syntax."""
    if type(value) in (bool, int):
        return str(value).lower()
    if type(value) is float and math.isfinite(value):
        return str(value)
    if type(value) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
        return value
    raise ValueError("Fixture setting must be finite or a safe literal string")


def validate_catalog(catalog: dict, root: Path = ROOT) -> None:
    """Reject missing runnable contracts, unsafe paths and overstated coverage."""
    if not isinstance(catalog, dict) or catalog.get("schema") != "sdvk-renderer-corpus/v1":
        raise ValueError("Unsupported renderer corpus schema")
    if set(catalog.get("classes", [])) != CLASSES:
        raise ValueError("Corpus must explicitly name every SDVK-002 reference class")
    contracts = catalog.get("cpu_contracts")
    if not isinstance(contracts, dict) or not contracts:
        raise ValueError("Corpus needs executable retained CPU contracts")
    declarations = catalog.get("cvar_sources", {})
    for name, paths in declarations.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or not paths:
            raise ValueError("Every declared setting needs an actual CVar source")
        pattern = re.compile(r"(?<![\w])(?:CUSTOM_)?CVAR[D]?\s*\(\s*\w+\s*,\s*" + re.escape(name) + r"\s*,")
        for path in paths:
            if not pattern.search(_file(root, path).read_text(encoding="utf-8")):
                raise ValueError(f"Setting {name} has no CVar definition at {path}")
    for name, contract in contracts.items():
        if contract.get("kind") != "cpu_contract" or contract.get("native_rendering_proof") is not False:
            raise ValueError(f"CPU contract {name} must not claim native rendering")
        test_path = relative_path(contract.get("test_path", ""))
        _file(root, test_path)
        command = contract.get("command", [])
        if not isinstance(command, list) or not all(isinstance(x, str) for x in command) or not command or command[0] != "{python}":
            raise ValueError(f"CPU contract {name} requires an explicit Python argv")
        if command[1:4] == ["-m", "unittest", "discover"]:
            try:
                start = command[command.index("-s") + 1]
                pattern = command[command.index("-p") + 1]
            except (ValueError, IndexError) as error:
                raise ValueError(f"CPU contract {name} needs exact discovery directory/pattern") from error
            if str(PurePosixPath(start) / pattern) != test_path or "*" in pattern:
                raise ValueError(f"CPU contract {name} must resolve its named existing test")
        elif len(command) > 3 and command[1] == "tools/pf_oracle/fixture_runner.py" and "--source" in command:
            if command[command.index("--source") + 1] != test_path:
                raise ValueError(f"CPU fixture {name} command/source mismatch")
        else:
            raise ValueError(f"Unsupported CPU contract command {name}")
        if "retained_fixture" in contract:
            _file(root, contract["retained_fixture"])
    seen, covered = set(), set()
    scenes = catalog.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Corpus has no scenes")
    for scene in scenes:
        name = scene.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,47}", name) or name in seen:
            raise ValueError("Scene IDs must be unique, bounded and portable")
        seen.add(name)
        classes = scene.get("classes", [])
        if not classes or not set(classes) <= CLASSES:
            raise ValueError(f"Unknown or absent classes for {name}")
        covered.update(classes)
        selected = scene.get("cpu_contracts", [])
        if not selected or any(key not in contracts for key in selected):
            raise ValueError(f"Scene {name} does not resolve its CPU contracts")
        if scene.get("cpu_commands") != [contracts[key]["command"] for key in selected]:
            raise ValueError(f"Scene {name} CPU argv differs from retained contracts")
        for path in scene.get("source_refs", []) + scene.get("negative_fixtures", []):
            _file(root, path)
        native = scene.get("native", {})
        if native.get("status") != "native_qualification_pending" or native.get("executed") is not False:
            raise ValueError(f"Catalog {name} may not manufacture native qualification")
        if native.get("generator") not in GENERATORS:
            raise ValueError(f"Unknown generator for {name}")
        if not re.fullmatch(r"[A-Z0-9_]{1,8}", native.get("map", "")):
            raise ValueError(f"Invalid map name for {name}")
        for key, leaf in (("pk3", "scene.pk3"), ("config", "fixture.ini"), ("capture_script", "capture.cfg")):
            if relative_path(native.get(key, "")) != f"scenes/{name}/{leaf}":
                raise ValueError(f"Scene {name} has an unexpected {key} destination")
        if native.get("extent") != [640, 480]:
            raise ValueError(f"Scene {name} must declare the bounded reference extent")
        camera = native.get("camera", {})
        position = camera.get("position", [])
        numbers = position + [camera.get(key) for key in ("yaw", "pitch", "roll", "camera_height")]
        if len(position) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in numbers):
            raise ValueError(f"Scene {name} requires a finite explicit camera")
        if type(native.get("seed")) is not int or not 0 <= native["seed"] <= 2**31 - 1:
            raise ValueError(f"Scene {name} requires an explicit supported RNG seed")
        if not set(native.get("settings", {})) <= declarations.keys():
            raise ValueError(f"Scene {name} names an unverified setting")
        for value in native["settings"].values():
            setting_literal(value)
        if native.get("console_queries") != sorted(native["settings"]):
            raise ValueError(f"Scene {name} must query every declared setting after assignment")
        for counter, bounds in native.get("frame_assertions", {}).items():
            if counter not in {"walls", "flats", "sprites", "decals", "portals", "vertices",
                               "shadow_candidates", "shadow_selected", "shadow_dropped"}:
                raise ValueError(f"Scene {name} names an unsupported frame assertion")
            if not isinstance(bounds, dict) or not bounds or not set(bounds) <= {"minimum", "maximum"}:
                raise ValueError(f"Scene {name} requires explicit frame assertion bounds")
            if any(type(value) is not int or value < 0 for value in bounds.values()) or bounds.get("minimum", 0) > bounds.get("maximum", 2**63 - 1):
                raise ValueError(f"Scene {name} has invalid frame assertion bounds")
        state_assertions = native.get("state_assertions", {})
        if not isinstance(state_assertions, dict) or not set(state_assertions) <= {"root_types", "materials", "material_semantics", "material_custom_layers", "material_height_layers", "material_layer_sampling", "line_mirror", "published_probes_minimum", "sun_intensity", "sprite_basis"}:
            raise ValueError(f"Scene {name} has unsupported state assertions")
        for key in ("root_types", "materials"):
            if key not in state_assertions:
                continue
            values = state_assertions[key]
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values) or len(set(values)) != len(values):
                raise ValueError(f"Scene {name} requires distinct named state assertions")
            if key == "root_types" and not set(values) <= {"main", "camera-texture", "light-probe", "save-picture", "portal"}:
                raise ValueError(f"Scene {name} names an unsupported root context")
        sprite_basis = state_assertions.get("sprite_basis")
        if sprite_basis is not None:
            if (not isinstance(sprite_basis, dict) or set(sprite_basis) !=
                    {"minimum_draws", "presentations", "material_examples", "requires_frame_mirror",
                     "requires_uv_mirror_x", "requires_uv_mirror_y", "requires_portal_mirror",
                     "light_material_examples"}
                    or type(sprite_basis["minimum_draws"]) is not int or
                    not 1 <= sprite_basis["minimum_draws"] <= 1000 or
                    not isinstance(sprite_basis["presentations"], list) or
                    not sprite_basis["presentations"] or
                    any(type(v) is not int or v not in range(5) for v in sprite_basis["presentations"]) or
                    not isinstance(sprite_basis["material_examples"], list) or
                    not sprite_basis["material_examples"] or
                    not set(sprite_basis["material_examples"]) <= set(state_assertions.get("materials", [])) or
                    not isinstance(sprite_basis["light_material_examples"], list) or
                    not sprite_basis["light_material_examples"] or
                    not set(sprite_basis["light_material_examples"]) <= set(sprite_basis["material_examples"]) or
                    any(sprite_basis[k] is not True for k in
                        ("requires_frame_mirror", "requires_uv_mirror_x", "requires_uv_mirror_y", "requires_portal_mirror"))):
                raise ValueError("Unbounded or ungrounded sprite tangent native assertions")
        if "line_mirror" in state_assertions and state_assertions["line_mirror"] is not True:
            raise ValueError(f"Scene {name} requires an explicit positive line-mirror assertion")
        if "published_probes_minimum" in state_assertions:
            value = state_assertions["published_probes_minimum"]
            if type(value) is not int or not 1 <= value <= 64:
                raise ValueError(f"Scene {name} has invalid published probe bounds")
        if "sun_intensity" in state_assertions:
            value = state_assertions["sun_intensity"]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Scene {name} has invalid positive sunlight assertion")
        semantic_assertions = state_assertions.get("material_semantics", {})
        if not isinstance(semantic_assertions, dict) or len(semantic_assertions) > 256:
            raise ValueError(f"Scene {name} has invalid material semantic assertions")
        for material, semantics in semantic_assertions.items():
            if (material not in state_assertions.get("materials", []) or not isinstance(semantics, list)
                    or not semantics or not all(isinstance(value, str) and value for value in semantics)
                    or len(set(semantics)) != len(semantics)):
                raise ValueError(f"Scene {name} must bind semantic assertions to required named materials")
        sampling_assertions = state_assertions.get("material_layer_sampling", {})
        if not isinstance(sampling_assertions, dict) or len(sampling_assertions) > 256:
            raise ValueError(f"Scene {name} has invalid material sampling assertions")
        for material, layers in sampling_assertions.items():
            if material not in state_assertions.get("materials", []) or not isinstance(layers, list) or not layers:
                raise ValueError(f"Scene {name} must bind sampler assertions to required named materials")
            for layer in layers:
                if (not isinstance(layer, dict)
                        or not {"semantic", "binding", "requested_sampling"} <= set(layer)
                        or not set(layer) <= {"semantic", "binding", "requested_sampling", "min_filter", "mag_filter", "mipmap_mode"}
                        or not isinstance(layer["semantic"], str) or not layer["semantic"]
                        or type(layer["binding"]) is not int or layer["binding"] < 0
                        or type(layer["requested_sampling"]) is not int
                        or layer["requested_sampling"] not in (-1, 0, 1)
                        or any(type(layer[key]) is not int for key in ("min_filter", "mag_filter", "mipmap_mode") if key in layer)):
                    raise ValueError(f"Scene {name} has invalid material sampling layer assertion")

        custom_assertions = state_assertions.get("material_custom_layers", {})
        if not isinstance(custom_assertions, dict) or len(custom_assertions) > 256:
            raise ValueError(f"Scene {name} has invalid custom material assertions")
        for material, layers in custom_assertions.items():
            if material not in state_assertions.get("materials", []) or not isinstance(layers, list) or not layers:
                raise ValueError(f"Scene {name} must bind custom assertions to required named materials")
            seen_custom_layers = set()
            for layer in layers:
                if (not isinstance(layer, dict)
                        or set(layer) != {"binding", "custom_index", "requested_sampling"}
                        or type(layer["binding"]) is not int or layer["binding"] < 0
                        or type(layer["custom_index"]) is not int or layer["custom_index"] < 0
                        or type(layer["requested_sampling"]) is not int
                        or layer["requested_sampling"] not in (-1, 0, 1)):
                    raise ValueError(f"Scene {name} has invalid custom material layer assertion")
                key = (layer["binding"], layer["custom_index"])
                if key in seen_custom_layers:
                    raise ValueError(f"Scene {name} repeats a custom material layer assertion")
                seen_custom_layers.add(key)
        height_assertions = state_assertions.get("material_height_layers", {})
        if not isinstance(height_assertions, dict) or len(height_assertions) > 256:
            raise ValueError(f"Scene {name} has invalid height material assertions")
        for material, layer in height_assertions.items():
            if (material not in state_assertions.get("materials", []) or not isinstance(layer, dict)
                    or set(layer) != {"binding", "requested_sampling"}
                    or type(layer["binding"]) is not int or layer["binding"] < 0
                    or type(layer["requested_sampling"]) is not int
                    or layer["requested_sampling"] not in (-1, 0, 1)):
                raise ValueError(f"Scene {name} has invalid height material layer assertion")
        if native.get("clock", {}).get("timing") != "ordinary_engine_clock":
            raise ValueError(f"Scene {name} may not time the PF fixed-tic clock")
        if not native.get("pending_coverage"):
            raise ValueError(f"Scene {name} must retain its native qualification limits")
        channels = scene.get("required_state_channels", [])
        if not channels or not set(channels) <= CHANNELS:
            raise ValueError(f"Scene {name} requires supported state producer kinds")
        if scene.get("comparison", {}).get("state_required") is not True:
            raise ValueError(f"Scene {name} cannot accept pixels without state")
        if native.get("generator") == "pf_view" and native.get("generic_capture_supported") is not False:
            raise ValueError("The retained interpolated PF scene needs its own fixed-fraction state driver")
        if native["generator"] == "lighting" and native.get("authored_light_count") not in (0, 1, 64, 256, 1025):
            raise ValueError("Lighting fixture must use one of the bounded declared counts")
        if native["generator"] == "lighting" and native.get("authored_light_count") == 256:
            if native.get("light_layout") not in ("overlap", "dispersed") or native.get("light_profile") != "mixed-static":
                raise ValueError("SDVK-009 dense lighting fixtures require an explicit layout and mixed-static profile")
    if covered != CLASSES:
        raise ValueError("Corpus class coverage is incomplete")


def _chunk(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff)


def png_rgba(width: int, height: int, rgba: bytes, *, offset: tuple[int, int] | None = None) -> bytes:
    """Use stored DEFLATE blocks, avoiding compressor-version-dependent pixels."""
    if not 1 <= width <= 256 or not 1 <= height <= 256 or len(rgba) != width * height * 4:
        raise ValueError("Authored RGBA texture has invalid bounded dimensions")
    scan = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    packed = bytearray(b"\x78\x01")
    for start in range(0, len(scan), 65535):
        block = scan[start:start + 65535]
        packed += bytes((1 if start + len(block) == len(scan) else 0,))
        packed += struct.pack("<HH", len(block), len(block) ^ 0xffff) + block
    packed += struct.pack(">I", zlib.adler32(scan) & 0xffffffff)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    grab = b"" if offset is None else _chunk(b"grAb", struct.pack(">ii", *offset))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + grab + _chunk(b"IDAT", bytes(packed)) + _chunk(b"IEND", b"")


def _texture(width: int, height: int, colour_a: tuple[int, ...], colour_b: tuple[int, ...], *, offset=None) -> bytes:
    pixels = bytes(channel for y in range(height) for x in range(width)
                   for channel in (colour_a if (x // 8 + y // 8) % 2 == 0 else colour_b))
    return png_rgba(width, height, pixels, offset=offset)


def archive_bytes(members: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(members.items()):
            relative_path(name)
            if not isinstance(payload, bytes):
                raise ValueError("Archive members must be bytes")
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = info.external_attr = 0
            archive.writestr(info, payload)
    return output.getvalue()


def _literal(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if type(value) in (int, float) and math.isfinite(value):
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Z0-9_-]{1,8}", value):
        return '"' + value + '"'
    raise ValueError(f"Unsupported authored UDMF value: {value!r}")


class _Map:
    def __init__(self, floor: int = 0, ceiling: int = 128, sky: bool = False):
        self.records = {"vertex": [], "sector": [{"heightfloor": floor, "heightceiling": ceiling,
                        "texturefloor": "SDVFL", "textureceiling": "F_SKY1" if sky else "SDVFL", "lightlevel": 160}],
                        "sidedef": [], "linedef": [], "thing": []}
        self.polygon_areas: list[float] = []

    def boundary(self, points: list[tuple[int, int]], textures: list[str]) -> None:
        if len(points) < 4 or len(points) != len(textures) or len(set(points)) != len(points):
            raise ValueError("Authored boundary requires one texture per unique edge")
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2
        if not area or (not self.polygon_areas and area > 0) or (self.polygon_areas and area < 0):
            raise ValueError("Outer boundary must be clockwise; solid holes counterclockwise")
        self.polygon_areas.append(area)
        first = len(self.records["vertex"])
        self.records["vertex"] += [dict(x=x, y=y) for x, y in points]
        for i, texture in enumerate(textures):
            side = len(self.records["sidedef"])
            self.records["sidedef"].append({"sector": 0, "texturemiddle": texture})
            self.records["linedef"].append({"v1": first + i, "v2": first + (i + 1) % len(points),
                                               "sidefront": side, "blocking": True})

    def thing(self, kind: int, x: float, y: float, height: float = 0, angle: int = 0, tid: int = 0, **extra) -> None:
        if abs(x) > 2048 or abs(y) > 2048 or not 0 <= height <= 256:
            raise ValueError("Authored thing lies outside bounded fixture volume")
        row = {"type": kind, "x": x, "y": y, "height": height, "angle": angle, "id": tid,
               "single": True, "coop": True, "dm": True, **{f"skill{i}": True for i in range(1, 6)}}
        self.records["thing"].append(row | extra)

    def text(self) -> str:
        if len(self.records["thing"]) > 1100 or len(self.records["linedef"]) > 80:
            raise ValueError("Authored map exceeds its compact workload bounds")
        text = ['namespace = "ZDoom";']
        for kind, rows in self.records.items():
            for row in rows:
                text.append(kind + " { " + " ".join(f"{key} = {_literal(value)};" for key, value in row.items()) + " }")
        return "\n".join(text) + "\n"


def _zscript() -> bytes:
    # camera assignment is the same public player_t field used by PlayerPawn
    # and ice actors. Selecting it from Tick avoids map-spawn ordering guesses.
    return b'''version "4.15.1"
class SDVKFixedCamera : Actor
{
    Default { Radius 1; Height 1; CameraHeight 0; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: TNT1 A -1; Stop; }
    override void Tick()
    {
        Super.Tick();
        if (playeringame[0] && players[0].mo != null) players[0].camera = self;
    }
}
class SDVKCanvasCamera : Actor
{
    Default { Radius 1; Height 1; CameraHeight 0; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: TNT1 A -1; Stop; }
    override void PostBeginPlay()
    {
        Super.PostBeginPlay();
        TexMan.SetCameraToTexture(self, "SDVCAM", 90);
    }
}
class SDVKGlass : Actor
{
    Default { Radius 8; Height 64; Alpha 0.5; RenderStyle "Translucent"; +NOGRAVITY +NOBLOCKMAP +WALLSPRITE }
    States { Spawn: SDVG A -1; Stop; }
}
class SDVKMarker : Actor
{
    Default { Radius 8; Height 64; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: SDVO A -1; Stop; }
}
'''


def _base_members() -> dict[str, bytes]:
    return {"ZSCRIPT": _zscript(),
            "textures/SDVW.png": _texture(64, 64, (82, 100, 116, 255), (158, 180, 198, 255)),
            "flats/SDVFL.png": _texture(64, 64, (54, 60, 64, 255), (76, 82, 88, 255)),
            "sprites/SDVGA0.png": _texture(64, 64, (40, 180, 230, 255), (230, 100, 40, 128), offset=(32, 64)),
            "sprites/SDVOA0.png": _texture(64, 64, (220, 185, 40, 255), (40, 75, 140, 255), offset=(32, 64))}


def _material_layers(members: dict[str, bytes]) -> None:
    for name, rgba in {"SDVN": (128, 128, 255, 255), "SDVSP": (160, 160, 160, 255),
                       "SDVM": (64, 64, 64, 255), "SDVR": (128, 128, 128, 255),
                       "SDVZERO": (0, 0, 0, 255), "SDVAO": (255, 255, 255, 255),
                       "SDVH": (192, 192, 192, 255)}.items():
        members[f"textures/{name}.png"] = png_rgba(16, 16, bytes(rgba) * 256)


def _pbr(name: str, kind: str = "texture", roughness: str = "SDVR") -> str:
    return f'material {kind} {name}\n{{\n normal "SDVN"\n metallic "SDVM"\n roughness "{roughness}"\n ao "SDVAO"\n}}\n'


def _light_positions(count: int, layout: str = "legacy") -> list[tuple[int, int]]:
    if count == 0:
        return []
    if count == 1:
        return [(-192, -128)]
    if count == 64:
        # Eight complete rows outside the occluder, with no approximate RNG.
        return [(x, y) for y in (-288, -208, -128, -80, 80, 128, 208, 288)
                for x in (-400, -288, -176, -64, 64, 176, 288, 400)]
    if count == 256:
        if layout == "overlap":
            # 16x16 compact cluster. Radius 192 below makes this a deliberately
            # pathological overlap workload without coincident light origins.
            return [(-240 + x * 8, -60 + y * 8) for y in range(16) for x in range(16)]
        if layout == "dispersed":
            # Matched count/profile distributed across the room, keeping every
            # authored origin outside the central solid occluder.
            candidates = [(x, y) for y in range(-304, 305, 40) for x in range(-432, 433, 48)
                          if not (0 <= x <= 128 and -64 <= y <= 64)]
            return [candidates[i * len(candidates) // count] for i in range(count)]
        raise ValueError("256-light fixture requires overlap or dispersed layout")
    if count == 1025:
        candidates = [(x, y) for y in range(-304, 305, 16) for x in range(-432, 433, 16)
                      if not (0 <= x <= 128 and -64 <= y <= 64)]
        # Select a uniformly spread deterministic subsequence of the whole room.
        return [candidates[i * len(candidates) // count] for i in range(count)]
    raise ValueError("Unsupported authored light count")


def authored_members(scene: dict) -> tuple[dict[str, bytes], dict]:
    native = scene["native"]
    generator, map_name = native["generator"], native["map"]
    members = _base_members()
    is_sun = generator == "sun_probes"
    model = _Map(floor=32 if is_sun else 0, ceiling=160 if is_sun else 128, sky=is_sun)
    camera = native["camera"]["position"]
    floor = model.records["sector"][0]["heightfloor"]
    yaw = math.radians(native["camera"]["yaw"])
    # The fixed camera must not coincide with the live player pawn. A coincident
    # third-person pawn has an undefined view-relative sprite rotation and can
    # select different PLAYA rotations between otherwise identical captures.
    player_start = [camera[0] - round(48 * math.cos(yaw)), camera[1] - round(48 * math.sin(yaw))]
    model.thing(1, player_start[0], player_start[1], tid=2001)
    model.thing(32200, camera[0], camera[1], camera[2] - floor, tid=2002)
    metadata = {"geometry": "authored_udmf", "textures": "generated_rgba_only", "native_executed": False,
                "camera_actor_tid": 2002, "camera_position_world": camera, "player_start_world": player_start, "monsters": 0,
                "animated_or_random_actors": 0, "baked_lightmap_members": 0}
    if generator == "compositing":
        points = [(-256, -192), (-256, 192), (256, 192), (256, 64), (256, -64), (256, -192)]
        model.boundary(points, ["SDVW", "SDVW", "SDVW", "SDVCAM", "SDVW", "SDVW"])
        model.thing(32201, 32, -96, 64, 90, 2010)
        model.thing(32202, 32, 32, 0, 180, 2020)
        model.thing(32202, 96, 32, 0, 180, 2021)
        model.thing(9200, 240, 128, 64, 180, 2030, arg0=25001 & 255, arg1=25001 >> 8)
        # It traces west from x=0: the nearest wall is 256 units away, beyond
        # ADecal::SpawnDecal's fixed 64-unit search. This is an authored negative.
        model.thing(9200, 0, -80, 64, 0, 2031, arg0=25001 & 255, arg1=25001 >> 8)
        members["ANIMDEFS"] = b"cameratexture SDVCAM 128 128 fit 128 128\n"
        members["DECALDEF"] = b"decal SDVKMark 25001\n{\n pic SDVDCL\n solid\n fullbright\n}\n"
        members["graphics/SDVDCL.png"] = _texture(32, 32, (245, 48, 88, 255), (245, 210, 48, 255), offset=(16, 16))
        metadata.update(decal_controls={"attached_candidate_tid": 2030, "distant_negative_tid": 2031,
                        "negative_wall_distance": 256, "actual_attach_count_required": True},
                        translucent_actor_tids=[2020, 2021], camera_texture="SDVCAM")
    elif generator == "sprite_mirror":
        model.boundary([(-256, -192), (-256, 192), (256, 192), (256, -192)], ["SDVW"] * 4)
        # The accepted PF view fixture uses Line_Mirror (182) on the same
        # clockwise east-facing boundary; retain that real engine route.
        model.records["linedef"][2].update(id=2040, special=182)
        members["ZSCRIPT"] += b"""
class SDVKRotated : Actor
{
    Default { Radius 8; Height 48; Scale 0.5; +NOGRAVITY +NOBLOCKMAP }
    States { Spawn: SDVR A -1; Stop; }
}
class SDVKWall : SDVKRotated { Default { +WALLSPRITE } }
class SDVKFlat : SDVKRotated { Default { +FLATSPRITE } }
class SDVKFlipX : SDVKRotated { Default { +XFLIP } }
class SDVKFlipY : SDVKRotated { Default { +YFLIP } }
class SDVKPBR : SDVKRotated { States { Spawn: SDVP A -1; Stop; } }
class SDVKLegacy : SDVKRotated { States { Spawn: SDVL A -1; Stop; } }
"""
        rotation_names = ["SDVRA1", "SDVRA2A8", "SDVRA3A7", "SDVRA4A6", "SDVRA5"]
        _material_layers(members)
        # Directionally asymmetric RG, never an ambiguous blue-only normal.
        normal_pixels = bytes(ch for y in range(16) for x in range(16)
                              for ch in ((216, 76, 219, 255) if x < 8 else (81, 185, 235, 255)))
        members["textures/SDVN.png"] = png_rgba(16, 16, normal_pixels)
        definitions = []
        for i, name in enumerate(rotation_names):
            # Deliberately asymmetric authored pixels expose mirrored frames.
            colour = ((40 + i * 43) % 256, (190 - i * 27) % 256, 70 + i * 31, 255)
            pixels = bytes(channel for y in range(64) for x in range(64)
                           for channel in (colour if x < 20 or (y < 20 and x < 48)
                                           else (235, 225, 190, 255)))
            members[f"sprites/{name}.png"] = png_rgba(64, 64, pixels, offset=(32, 64))
            if i == 0:
                definitions.append(f'material sprite {name}\n{{\n normal "SDVN" {{ filter linear }}\n specular "SDVSP"\n height "SDVH" {{ filter linear }}\n}}\n')
            else:
                definitions.append(f'material sprite {name}\n{{\n normal "SDVN"\n specular "SDVSP"\n}}\n')
        members["sprites/SDVPA0.png"] = _texture(64, 64, (85, 156, 224, 255), (234, 194, 74, 255), offset=(32, 64))
        members["sprites/SDVLA0.png"] = _texture(64, 64, (210, 130, 108, 255), (65, 92, 175, 255), offset=(32, 64))
        definitions.append(_pbr("SDVPA0", kind="sprite"))
        members["GLDEFS"] = "".join(definitions).encode()
        for k, (x, y) in enumerate((x, y) for x in (0, 64) for y in (-72, -24, 24, 72)):
            yaw = (math.degrees(math.atan2(y - camera[1], x - camera[0])) - ((2*k + .5)*22.5 - 202.5)) % 360
            model.thing(32210, x, y, angle=round(yaw) % 360, tid=4201+k)
        for kind, x, y, height, tid in ((32211, 96, -112, 32, 4301), (32212, 96, 112, 8, 4302),
                                       (32213, 128, -48, 0, 4303), (32214, 128, 48, 0, 4304)):
            model.thing(kind, x, y, height, tid=tid)
        model.thing(32215, 128, 150, 0, tid=4305)
        model.thing(32216, 128, -150, 0, tid=4306)
        # One fixed coloured light activates actual normal/specular/PBR response
        # in software Vulkan. The mode-2 per-pixel path is asserted below.
        model.thing(9800, 96, 0, 64, tid=4500, arg0=255, arg1=142, arg2=74, arg3=256)
        metadata.update(direction_light_tid=4500, per_pixel_sprite_light_mode=2,
                        pbr_sprite_material="SDVPA0", legacy_unmapped_sprite="SDVLA0",
                        rotation_material_names=rotation_names, rotation_actor_tids=list(range(4201, 4209)),
                        paired_frame_mirroring=True, mirror_line_id=2040,
                        actual_mirrored_context_and_materials_required=True)
    elif generator == "lighting":
        model.boundary([(-512, -384), (-512, 384), (512, 384), (512, -384)], ["SDVW"] * 4)
        model.boundary([(0, -64), (128, -64), (128, 64), (0, 64)], ["SDVW"] * 4)
        count = native["authored_light_count"]
        layout = native.get("light_layout", "legacy")
        profile = native.get("light_profile", "point")
        positions = _light_positions(count, layout)
        for i, (x, y) in enumerate(positions):
            colour = ((255, 72, 40), (48, 224, 112), (64, 112, 255))[i % 3]
            kind = (9800, 9810, 9820, 9840, 9850, 9860)[i % 6] if profile == "mixed-static" else 9800
            model.thing(kind, x, y, 64, angle=(i * 37) % 360, tid=3000 + i, arg0=colour[0], arg1=colour[1], arg2=colour[2],
                        arg3=192 if count == 256 else 96, light_noshadowmap=False, light_shadowminquality=1)
        model.thing(32203, -96, 160, tid=2020)
        model.thing(32203, 224, 160, tid=2021)
        metadata.update(authored_light_count=count, light_layout=layout, light_profile=profile,
                        light_types=sorted({thing["type"] for thing in model.records["thing"] if 9800 <= thing["type"] <= 9884}),
                        solid_occluder_xy=[[0, -64], [128, 64]],
                        shadow_capacity=1024, actual_selection_not_inferred=True)
    elif generator == "material_stress":
        points = [(-512, -384), (-512, 384)] + [(512, 384 - 12 * i) for i in range(65)]
        names = [f"SM{i:04d}" for i in range(64)]
        # Edge 2 begins the east wall; all 64 authored panels face the fixed camera.
        model.boundary(points, ["SDVW", "SDVW"] + names + ["SDVW"])
        _material_layers(members)
        # SDVK-004 extends the existing rich-material native scene rather than
        # introducing a parallel diagnostic workload. Eight PBR panels bind a
        # real custom hardware shader texture through the inherited GLDEFS
        # parser/descriptor path; alternating filter requests exercise both
        # custom sampler overrides while the observer records semantic/sampler
        # state beside the image.
        members["textures/SDVCU.png"] = _texture(
            16, 16, (255, 64, 24, 255), (24, 96, 255, 255))
        members["shaders/sdvk004.fp"] = b"""vec4 Process(vec4 color)
{
    float height = SampleMaterialHeight(vTexCoord.st);
    return texture(SDVKExtra, vTexCoord.st) * color * vec4(vec3(0.75 + 0.25 * height), 1.0);
}
"""
        definitions = []
        custom_names = []
        custom_filters = {}
        for i, name in enumerate(names):
            a = ((31 + i * 37) % 256, (91 + i * 19) % 256, (173 + i * 11) % 256, 255)
            b = (255 - a[0], 255 - a[1], 255 - a[2], 255)
            members[f"textures/{name}.png"] = _texture(16, 16, a, b)
            if i == 4:
                definitions.append(f'material texture {name}\n{{\n height "SDVH" {{ filter linear }}\n}}\n')
            elif i % 4 == 1:
                if i == 1:
                    definitions.append(f'material texture {name}\n{{\n normal "SDVN" {{ filter linear }}\n specular "SDVSP"\n height "SDVH" {{ filter linear }}\n}}\n')
                else:
                    definitions.append(f'material texture {name}\n{{\n normal "SDVN"\n specular "SDVSP"\n}}\n')
            elif i % 8 == 2:
                custom_filter = "nearest" if (i // 8) % 2 == 0 else "linear"
                definitions.append(
                    f'material texture {name}\n{{\n'
                    ' normal "SDVN" { filter linear }\n metallic "SDVM" { filter linear }\n roughness "SDVR" { filter linear }\n ao "SDVAO" { filter linear }\n'
                    ' height "SDVH" { filter linear }\n'
                    ' shader "shaders/sdvk004.fp"\n'
                    f' texture SDVKExtra "SDVCU" {{ filter {custom_filter} }}\n'
                    '}\n')
                custom_names.append(name)
                custom_filters[name] = custom_filter
            elif i == 6:
                definitions.append(f'material texture {name}\n{{\n normal "SDVN" {{ filter linear }}\n metallic "SDVM" {{ filter linear }}\n roughness "SDVR" {{ filter linear }}\n ao "SDVAO" {{ filter linear }}\n height "SDVH" {{ filter linear }}\n}}\n')
            elif i % 4 >= 2:
                definitions.append(_pbr(name, roughness="SDVZERO" if i % 4 == 3 else "SDVR"))
        members["GLDEFS"] = "".join(definitions).encode()
        metadata.update(
            authored_material_count=64,
            material_families=["albedo_only", "legacy_normal_specular", "pbr",
                               "pbr_custom_shader", "pbr_zero_roughness"],
            material_names=names,
            custom_shader_material_names=custom_names,
            custom_shader_binding="SDVKExtra",
            custom_shader_texture="SDVCU",
            custom_shader_filters=custom_filters,
            height_material_names=["SM0001", "SM0002", "SM0004", "SM0006", "SM0010", "SM0018", "SM0026", "SM0034", "SM0042", "SM0050", "SM0058"],
            height_texture="SDVH",
            native_visibility_and_allocation_required=True)
    elif generator == "sun_probes":
        model.boundary([(-256, -192), (-256, 192), (256, 192), (256, -192)], ["SDVW"] * 4)
        _material_layers(members)
        members["GLDEFS"] = (_pbr("SDVW") + _pbr("SDVFL", "flat")).encode()
        members["textures/SDVSKY.png"] = _texture(256, 128, (120, 156, 194, 255), (180, 194, 210, 255))
        model.thing(9890, 0, 0, angle=0, pitch=45, lm_suncolor=16774336, lm_sunintensity=1, lm_sampledist=64)
        # The current 9892 parser stores the authored Z directly as probe world Z.
        model.thing(9892, -96, -96, 80)
        model.thing(9892, 96, 96, 112)
        # HasDynamicLights requires an actual light or lightmap. These authored
        # controls exercise the actor query hook even before any bake exists;
        # their presence is not evidence that sunlight or probe sampling works.
        model.thing(9800, 0, 0, 64, tid=3000, arg0=160, arg1=160, arg2=160, arg3=96)
        model.thing(32203, 0, -64, 0, tid=2020)
        model.thing(32203, 96, 96, 0, tid=2021)
        metadata.update(authored_probe_positions=[[-96, -96, 80], [96, 96, 112]],
                        query_control_light_tid=3000, query_marker_tids=[2020, 2021],
                        sunlight=copy.deepcopy(native["sun_input"]), full_bake_qualified=False)
    else:
        raise ValueError(f"Not an authored generator: {generator}")
    sky = ' sky1 = "SDVSKY", 0' if is_sun else ""
    members["MAPINFO"] = (f'map {map_name} "SDVK {scene["id"]}" {{ nointermission{sky} }}\n'
                          'DoomEdNums\n{\n 32200 = SDVKFixedCamera\n 32201 = SDVKCanvasCamera\n'
                          ' 32202 = SDVKGlass\n 32203 = SDVKMarker\n}\n').encode()
    if generator == "sprite_mirror":
        members["MAPINFO"] += ("DoomEdNums\n{\n 32210 = SDVKRotated\n 32211 = SDVKWall\n"
                               " 32212 = SDVKFlat\n 32213 = SDVKFlipX\n 32214 = SDVKFlipY\n 32215 = SDVKPBR\n 32216 = SDVKLegacy\n}\n").encode()
    textmap = model.text().encode()
    members[f"maps/{map_name}.wad"] = pf_indexed.wad([(map_name, b""), ("TEXTMAP", textmap), ("ENDMAP", b"")])
    metadata["counts"] = {kind: len(rows) for kind, rows in model.records.items()}
    metadata["boundary_signed_areas"] = model.polygon_areas
    return members, metadata


def scene_assets(scene: dict) -> tuple[bytes, dict[str, bytes], dict]:
    generator = scene["native"]["generator"]
    module = {"pf_view": pf_view, "pf_indexed": pf_indexed, "pf_pbr": pf_pbr}.get(generator)
    if module is not None:
        members = module.members()
        return module.archive_bytes(members), members, {"retained_pf_generator": module.__name__,
               "member_bytes_unchanged": True, "native_executed": False,
               "historical_receipt_is_not_new_qualification": True}
    members, metadata = authored_members(scene)
    return archive_bytes(members), members, metadata


def configuration(scene: dict) -> bytes:
    settings = scene["native"]["settings"]
    rows = ["[GlobalSettings]"]
    for key, value in sorted(settings.items()):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("Unsupported fixture setting")
        rows.append(f"{key}={setting_literal(value)}")
    rows += ["", "[Doom.ConsoleVariables]", "screenblocks=12", "crosshair=0", "", "[Doom.Bindings]", ""]
    return "\n".join(rows).encode()


def capture_script(scene: dict) -> bytes:
    # Repeat non-archived CVars on the real command path, rather than assuming
    # every engine CVar is persisted in the same INI section.
    commands = [f"{key} {setting_literal(value)}" for key, value in sorted(scene["native"]["settings"].items())]
    commands += scene["native"]["console_commands"]
    commands += scene["native"]["console_queries"]
    if any(any(ch in cmd for ch in ('\n', '\r', ';', '"')) for cmd in commands):
        raise ValueError("Preparation commands must be literal single console statements")
    raw = ("; ".join(commands) + "\n").encode()
    if len(raw) + 1 > 4094:
        raise ValueError("Capture script exceeds the inherited exec parser line bound")
    # The generic observer owns the frame budget, screenshot and orderly quit.
    return raw


def _source_inventory(catalog: dict, root: Path) -> dict[str, dict]:
    names = {"tools/renderer_oracle/corpus.json", "tools/renderer_oracle/prepare.py",
             "tools/renderer_oracle/tests/test_corpus.py",
             "tools/pf_oracle/fixture_runner.py", "src/d_main.cpp", "src/common/console/c_dispatch.cpp",
             "src/common/rendering/hwrenderer/data/hw_cvars.cpp", "src/common/rendering/hwrenderer/postprocessing/hw_postprocess_cvars.cpp",
             "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnosticcore.h",
             "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp",
             "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.h"}
    for paths in catalog["cvar_sources"].values():
        names.update(paths)
    for scene in catalog["scenes"]:
        names.update(scene["source_refs"])
        names.update(scene["negative_fixtures"])
    for module in (pf_view, pf_indexed, pf_pbr):
        names.update(module.SOURCE_FILES)
    inventory = {}
    for name in sorted(names):
        raw = _file(root, name).read_bytes()
        inventory[name] = {"bytes": len(raw), "sha256": digest(raw)}
    return inventory


def prepare(out: Path, scene_ids: list[str] | None = None, *, root: Path = ROOT) -> dict:
    root = Path(root).resolve(strict=True)
    catalog = load_catalog(root / "tools/renderer_oracle/corpus.json")
    validate_catalog(catalog, root)
    ids = set(scene_ids) if scene_ids is not None else {scene["id"] for scene in catalog["scenes"]}
    if not ids or (scene_ids is not None and len(ids) != len(scene_ids)):
        raise ValueError("Select at least one scene, without duplicate IDs")
    if ids - {scene["id"] for scene in catalog["scenes"]}:
        raise ValueError("Unknown scene ID: " + ", ".join(sorted(ids - {scene["id"] for scene in catalog["scenes"]})))
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Preparation output must be a fresh directory; existing evidence is preserved")
    before = _source_inventory(catalog, root)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                            capture_output=True, check=True).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError("Could not identify the repository commit")
    files: dict[str, bytes] = {}
    prepared_scenes = []
    for original in catalog["scenes"]:
        if original["id"] not in ids:
            continue
        scene = copy.deepcopy(original)
        archive, members, authoring = scene_assets(scene)
        native = scene["native"]
        files[native["pk3"]] = archive
        files[native["config"]] = configuration(scene)
        files[native["capture_script"]] = capture_script(scene)
        scene["prepared_assets"] = {"authoring": authoring, "pk3_sha256": digest(archive),
                                    "members": {name: {"sha256": digest(raw), "bytes": len(raw)}
                                                for name, raw in sorted(members.items())}}
        prepared_scenes.append(scene)
    after = _source_inventory(catalog, root)
    if before != after:
        raise ValueError("Fixture sources changed during preparation; preserve source and retry into a fresh directory")
    manifest = {"schema": SCHEMA, "status": "prepared_only", "programme": "SDVK-002",
                "native_executed": False, "native_qualified": False,
                "catalog_sha256": before["tools/renderer_oracle/corpus.json"]["sha256"],
                "source_identity": {"git_commit": commit, "tree_cleanliness": "not_asserted",
                                    "content_hashes_authoritative": True, "files": before},
                "cpu_contracts": catalog["cpu_contracts"], "scenes": prepared_scenes,
                "files": {name: {"sha256": digest(raw), "bytes": len(raw)} for name, raw in sorted(files.items())},
                "limits": ["Preparation validates inputs and records provenance; it does not compile native content or render a frame.",
                           "Actual executable, IWAD, loaded packages, device/driver, settings, map/camera, state and output images belong in the run evidence.",
                           "PF member bytes and original negative fixtures are retained. Their earlier receipts do not qualify these new preparations.",
                           "Timings require ordinary engine time. A PF fixed-tic/fixed-fraction state replay is not a performance workload.",
                           "Source hashes describe actual files even before commit; git_commit alone does not claim a clean tree."]}
    out.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = out / relative_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    # Written last: a directory without this complete receipt is not prepared.
    (out / "prepared.json").write_bytes(canonical_json(manifest))
    return manifest


def verify_prepared(directory: Path, *, root: Path = ROOT) -> dict:
    """Authenticate a preparation against current source and pure regeneration.

    Rehashing a modified asset and its manifest is insufficient: this checks the
    expected generator bytes, recipe, source inventory and every listed member.
    It does not execute the engine or promote a preparation to native evidence.
    The caller should also pin its copied runtime inputs before launching them.
    """
    directory, root = Path(directory).resolve(strict=True), Path(root).resolve(strict=True)
    receipt = _file(directory, "prepared.json")
    if receipt.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Prepared receipt exceeds the bounded corpus manifest size")
    manifest = json.loads(receipt.read_text(encoding="utf-8"))
    if (manifest.get("schema") != SCHEMA or manifest.get("status") != "prepared_only"
            or manifest.get("native_executed") is not False or manifest.get("native_qualified") is not False):
        raise ValueError("Unknown or overstated prepared receipt")
    catalog = load_catalog(root / "tools/renderer_oracle/corpus.json")
    validate_catalog(catalog, root)
    before = _source_inventory(catalog, root)
    source = manifest.get("source_identity", {})
    if source.get("files") != before:
        raise ValueError("Prepared source inventory differs from current source; prepare fresh inputs")
    if source.get("tree_cleanliness") != "not_asserted" or source.get("content_hashes_authoritative") is not True:
        raise ValueError("Prepared source identity overstates its commit-only provenance")
    commit = source.get("git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError("Prepared source commit is not an explicit Git identity")
    subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=root,
                   capture_output=True, check=True)
    if manifest.get("catalog_sha256") != before["tools/renderer_oracle/corpus.json"]["sha256"]:
        raise ValueError("Prepared catalog identity changed")
    if manifest.get("cpu_contracts") != catalog["cpu_contracts"]:
        raise ValueError("Prepared CPU contract commands differ from the corpus")
    originals = {scene["id"]: scene for scene in catalog["scenes"]}
    selected, expected_files = set(), {}
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Prepared receipt has no selected scene")
    for recorded in scenes:
        name = recorded.get("id")
        if name not in originals or name in selected:
            raise ValueError("Prepared scene selection is unknown or duplicated")
        selected.add(name)
        expected = copy.deepcopy(originals[name])
        archive, members, authoring = scene_assets(expected)
        native = expected["native"]
        expected_files[native["pk3"]] = archive
        expected_files[native["config"]] = configuration(expected)
        expected_files[native["capture_script"]] = capture_script(expected)
        expected["prepared_assets"] = {"authoring": authoring, "pk3_sha256": digest(archive),
                                       "members": {path: {"sha256": digest(raw), "bytes": len(raw)}
                                                   for path, raw in sorted(members.items())}}
        if recorded != expected:
            raise ValueError(f"Prepared scene {name} differs from its authored source recipe")
    expected_inventory = {path: {"sha256": digest(raw), "bytes": len(raw)} for path, raw in sorted(expected_files.items())}
    if manifest.get("files") != expected_inventory:
        raise ValueError("Prepared file identities do not match regenerated fixture inputs")
    for name, expected_raw in expected_files.items():
        path = _file(directory, name)
        if path.is_symlink() or path.read_bytes() != expected_raw:
            raise ValueError(f"Prepared asset changed or links elsewhere: {name}")
    if before != _source_inventory(catalog, root):
        raise ValueError("Source changed during prepared-input verification")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--scene", action="append", help="scene ID; repeat to select a subset (default: all)")
    args = parser.parse_args()
    try:
        result = prepare(args.out, args.scene)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps({"status": result["status"], "native_executed": False,
                      "manifest": str(args.out.resolve() / "prepared.json"), "scenes": len(result["scenes"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
