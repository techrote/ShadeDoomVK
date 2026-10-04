#!/usr/bin/env python3
"""Prepare or explicitly launch one bounded #113 candidate-only native case.

Preparation never starts a process. --launch starts one reviewed Popen child,
with the existing source-linked core/sync recipes and own-child watchdog. This
tool never launches an unsafe original shader, a CFX campaign or a GPU probe.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def load_sibling(name):
    spec = importlib.util.spec_from_file_location("pf113_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_sibling("run_indexed_material_runtime")
inputs = load_sibling("prepare_pbr_probe_runtime")
require, identity, read_json, save = base.require, base.identity, base.read_json, base.save
SCHEMA = "pf113-bounded-native-run/v1"
PACKAGES = {"brightmaps.pk3", "game_support.pk3", "game_widescreen_gfx.pk3", "lights.pk3", "vkdoom.pk3"}
WATCHDOG_SECONDS = base.WATCHDOG_SECONDS
CONTROL_NAMES = ("uniform-zero", "gather-allzero", "gather-mixed", "gather-live", "uniform-live-a", "uniform-live-b",
                 "quad-zero-live", "quad-live-live", "roughness-zero-live-a", "roughness-one-live-a",
                 "original-uniform-a", "original-uniform-b")
CONTROL_ROWS = ["irradiance", "prefiltered", "diffuse", "specular", "Lo", "final", "N+roughness", "R+runtime", "taps", "weights"]
TOLERANCE = .0003


def checked_case(manifest, name, executable):
    require(manifest.get("schema") == inputs.SCHEMA and manifest.get("status") == "prepared-unaccepted"
            and manifest.get("gpuExecuted") is False, "Expected unexecuted PF113 inputs")
    cases = manifest.get("scenarios", [])
    require(len(cases) == 1 and name == "hardware-truecolour-nearest" and cases[0].get("id") == name,
            "Only the authored PF113 hardware truecolour scene is supported")
    case = cases[0]
    require(all(case.get(key) == value and type(case.get(key)) is type(value) for key, value in inputs.SETTINGS.items())
            and case.get("extent") == [640, 480] and case.get("executed") is False, "Prepared fixture settings changed")
    expected = inputs.command(executable, Path(manifest["iwad"]["path"]), Path(manifest["mod"]["path"]),
                              Path(case["config"]), Path(case["captureScript"]), Path(case["earlyPrefix"]))
    require(case.get("command") == expected, "Prepared argv differs from exact PF113 input command")
    require(manifest["iwad"].get("sha256") == inputs.IWAD_SHA256 and manifest["iwad"].get("copiedIntoMod") is False,
            "IWAD identity or publication policy changed")
    scene = manifest.get("scene", {})
    require(scene.get("map") == "PF113" and scene.get("probes") == inputs.PROBES
            and scene.get("probeThingType") == 9892 and scene.get("prebakedProbeOrLightmapLumps") is False
            and scene.get("sectorTarget") == {"sector": 0, "origin": [0, 0, 64], "expectedOrdinal": 1}
            and scene.get("sideTarget") == {"side": 2, "origin": [128, 0, 64], "expectedOrdinal": 1}
            and scene.get("materialNames") == ["PF113W", "PF113FL"], "Authored scene contract differs")
    expected_files = inputs.members()
    with zipfile.ZipFile(manifest["mod"]["path"]) as archive:
        require(len(archive.namelist()) == len(expected_files) and set(archive.namelist()) == set(expected_files),
                "Synthetic mod member closure changed")
        for key, wanted in expected_files.items():
            require(archive.getinfo(key).file_size <= 512*1024, "Synthetic member exceeds bound")
            found = archive.read(key)
            require(found == wanted and manifest["mod"]["members"].get(key) == {"sha256": inputs.sha(found), "bytes": len(found)},
                    "Authored synthetic member differs: " + key)
    require(Path(case["config"]).read_text() == inputs.configuration(), "Fixed fixture configuration changed")
    require(Path(case["captureScript"]).read_text() == inputs.capture_script(Path(case["nativePrefix"]), Path(case["presentationCapture"])),
            "Prepared wait/diagnostic/capture chain changed")
    return case


def candidate_identity(path, executable):
    require(path is not None, "PF113 requires the exact native candidate build/source receipt")
    data = read_json(path, maximum=8*1024*1024)
    require(data.get("schema") == "pf113-native-candidate/v1" and data.get("native_build", {}).get("exit") == 0
            and data.get("source_closure_unchanged_during_engine_compile") is True
            and data.get("accepted") is False and data.get("gpu_executed") is False,
            "Candidate receipt lacks successful unchanged-source native build or is a different candidate")
    artifacts = data.get("artifacts", [])
    require(isinstance(artifacts, list) and 7 <= len(artifacts) <= 128, "Native build artifact closure missing")
    names = [Path(row.get("path", "")).name for row in artifacts]
    require(len(names) == len(set(names)) and PACKAGES.issubset(names), "Candidate package artifact closure differs")
    found = []
    for row in artifacts:
        record = base.checked(row, "candidate build artifact")
        require(row.get("source"), "Candidate artifact lacks actual build counterpart")
        record["buildSource"] = base.checked({**row, "path": row["source"]}, "native build counterpart")
        found.append(record)
    matches = [row for row in found if Path(row["path"]) == executable.resolve(strict=True)]
    require(len(matches) == 1, "Candidate receipt does not name exact staged executable once")
    closure = data.get("source_files", {})
    require(isinstance(closure, dict) and 100 <= len(closure) <= 10000, "Full candidate source closure missing")
    for name, pin in closure.items():
        payload = base.source_path(name).read_bytes()
        require(inputs.sha(payload) == pin.get("raw_sha256")
                and inputs.sha(payload.replace(b"\r\n", b"\n")) == pin.get("normalized_lf_sha256"),
                "Native candidate source changed: " + name)
    require(re.fullmatch(r"[0-9a-f]{40}", data.get("source_head", "")), "Candidate source head missing")
    return {"receipt": identity(path), "verifiedArtifacts": found, "verifiedSourceFiles": len(closure),
            "sourceHead": data["source_head"], "sourceStatus": data.get("source_status"),
            "nativeBuild": data["native_build"], "unchangedDuringCompile": True}


def require_staged_inventory(build, candidate, executable):
    declared = {}
    for row in candidate["verifiedArtifacts"]:
        path = Path(row["path"])
        require(path.parent == executable.resolve(strict=True).parent and path.suffix.lower() in (".exe", ".dll", ".pk3", ".pdb"),
                "Candidate artifact is outside the exact staged runtime inventory")
        require(path.name not in declared, "Candidate staged artifact name duplicated")
        declared[path.name] = {key: row[key] for key in ("path", "sha256", "bytes")}
    require(len(declared) == 8 and build == declared, "Actual staged exe/dll/pk3/pdb inventory differs from the complete eight-artifact native candidate")


def snapshot(manifest_path, executable, layer_dir, manifest, case, candidate):
    declared = manifest.get("fixtureInterfaceSources", {})
    require(set(declared) == set(inputs.SOURCE_FILES), "Fixture source closure differs from exact producer/consumer/tool closure")
    sources = {}
    for name, wanted in declared.items():
        record = identity(base.source_path(name))
        require(record["sha256"] == wanted, "Prepared fixture/source changed: " + name)
        sources[name] = record
    exe = base.checked(manifest.get("executable"), "manifest executable")
    require(Path(exe["path"]) == executable.resolve(strict=True), "Requested executable differs from frozen manifest")
    build = base.build_inventory(executable)
    require({name for name in build if name.lower().endswith(".pk3")} == PACKAGES, "Staged resource package inventory must be exactly five")
    attested = candidate_identity(candidate, executable)
    require_staged_inventory(build, attested, executable)
    return {"sources": sources, "inputs": {
                "manifest": identity(manifest_path), "iwad": base.checked(manifest["iwad"], "isolated IWAD"),
                "mod": base.checked(manifest["mod"], "synthetic mod"),
                "configuration": base.checked({"path": case["config"], "sha256": case["configSha256"]}, "fixture config"),
                "captureScript": base.checked({"path": case["captureScript"], "sha256": case["captureScriptSha256"]}, "fixture capture chain")},
            "build": build, "layer": base.layer_identity(layer_dir), "candidate": attested}


def execution_command(case, out):
    command = list(case["command"])
    for option, value in (("-config", out/"fixture-live.ini"), ("-pf113observe", out/"early"), ("+exec", out/"execute.cfg")):
        command[command.index(option)+1] = str(value)
    return command


def execution_script(out):
    return inputs.capture_script(out/"native", out/"presentation.png")


def prepare(manifest_path, case_name, executable, out, mode, layer_dir, candidate):
    manifest_path, executable, layer_dir = [path.resolve(strict=True) for path in (manifest_path, executable, layer_dir)]
    require(mode in ("core", "sync"), "Only independent core or synchronization validation is supported")
    manifest = read_json(manifest_path)
    case = checked_case(manifest, case_name, executable)
    before = snapshot(manifest_path, executable, layer_dir, manifest, case, candidate)
    out = out.resolve()
    inputs.safe_path(out)
    require(not out.exists() and not out.is_relative_to(executable.parent), "Output must be fresh and outside frozen runtime")
    out.mkdir(parents=True)
    cfg = out/"fixture-live.ini"
    cfg.write_bytes(Path(case["config"]).read_bytes())
    (out/"fixture-input.ini").write_bytes(cfg.read_bytes())
    script = out/"execute.cfg"
    script.write_text(execution_script(out), encoding="utf-8", newline="\n")
    settings = out/"vk_layer_settings.txt"
    settings.write_text("\n".join("khronos_validation."+item for item in base.settings_recipe(mode))
                        + "\nkhronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG\n"
                        + "khronos_validation.report_flags = error;warn;info\n"
                        + "khronos_validation.log_filename = " + inputs.safe_path(out/"validation.log") + "\n",
                        encoding="utf-8", newline="\n")
    generated = {name: identity(path) for name, path in (("configInput", out/"fixture-input.ini"),
                 ("configLiveBefore", cfg), ("exec", script), ("settings", settings))}
    receipt = {"schema": SCHEMA, "status": "PREPARED", "preparedUtc": base.utc(), "gpuExecuted": False,
               "case": case_name, "validationMode": mode, "argv": execution_command(case, out), "cwd": str(out),
               "watchdogSeconds": WATCHDOG_SECONDS, "before": before, "generated": generated,
               "earlyPrefix": str(out/"early"), "diagnosticPrefix": str(out/"native"),
               "screenshot": str(out/"presentation.png"), "sourceToBinaryAttestedHere": False,
               "limitations": ["Native build receipt establishes source-to-binary identity; preparation alone never executes GPU work.",
                   "Only immediate specialized PBR rendering is exercised; no LevelMesh/uber/default-path parity claim.",
                   "No unsafe original missing/divergent-cube shader is launched.",
                   "Separate core/sync runs are not GPU-assisted validation.",
                   "Fixed-scene PNG context is not whole-frame parity, performance, human acceptance or probe calibration."]}
    save(out/"receipt.json", receipt)
    return receipt, manifest, case


def resume(manifest_path, case_name, executable, out, mode, layer_dir, candidate):
    manifest = read_json(manifest_path)
    case = checked_case(manifest, case_name, executable)
    receipt = read_json(out/"receipt.json")
    require(receipt.get("schema") == SCHEMA and receipt.get("status") == "PREPARED" and receipt.get("gpuExecuted") is False,
            "Only fresh unexecuted PREPARED evidence can launch")
    require(receipt.get("case") == case_name and receipt.get("validationMode") == mode and receipt.get("cwd") == str(out)
            and receipt.get("argv") == execution_command(case, out) and receipt.get("watchdogSeconds") == WATCHDOG_SECONDS,
            "Prepared process/input interface changed")
    require((out/"execute.cfg").read_text() == execution_script(out), "Prepared command chain changed")
    require(snapshot(manifest_path, executable, layer_dir, manifest, case, candidate) == receipt.get("before"),
            "Prepared immutable identities changed")
    return receipt, manifest, case


def package_evidence(out, before):
    result = base.loaded_package_evidence(out, before)
    expected = {Path(row["path"]) for name, row in before["build"].items() if name in PACKAGES}
    expected |= {Path(before["inputs"][name]["path"]) for name in ("iwad", "mod")}
    observed = {Path(row["path"]) for row in result["orderedPackages"]}
    result["exactSevenPackages"] = len(result["orderedPackages"]) == 7 and observed == expected
    result["verified"] = result["verified"] and result["exactSevenPackages"]
    return result


def artifact(out, stem, suffix, expected_size=None):
    require(isinstance(stem, str) and re.fullmatch(r"(?:early|native)(?:-[A-Za-z0-9_-]+)?", stem), "Native artifact stem invalid")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", suffix), "Native artifact suffix invalid")
    path = out/(stem+suffix)
    require(path.resolve(strict=True).parent == out.resolve(strict=True), "Native artifact escaped output directory")
    record = identity(path)
    require(record["bytes"] <= 16*1024*1024 and (expected_size is None or record["bytes"] == expected_size),
            "Native artifact byte extent invalid")
    return path.read_bytes(), record


def named_artifact(out, path, expected_name, expected_size=None):
    require(isinstance(path, str) and Path(path).name == expected_name
            and Path(path).resolve(strict=True).parent == out.resolve(strict=True), "Native artifact path/name differs")
    record = identity(Path(path))
    require(record["bytes"] <= 16*1024*1024 and (expected_size is None or record["bytes"] == expected_size),
            "Native artifact byte extent differs")
    return Path(path).read_bytes(), record


def spirv(payload, *, nonuniform=False):
    require(20 <= len(payload) <= 8*1024*1024 and len(payload) % 4 == 0, "SPIR-V byte extent invalid")
    words = struct.unpack("<"+"I"*(len(payload)//4), payload)
    require(words[0] == 0x07230203 and words[1] in (0x10000, 0x10100, 0x10200, 0x10300, 0x10400, 0x10500, 0x10600)
            and 0 < words[3] <= 1000000 and words[4] == 0, "SPIR-V header invalid")
    position, capabilities, decorations, explicit, implicit = 5, [], [], 0, 0
    while position < len(words):
        count, opcode = words[position] >> 16, words[position] & 0xffff
        require(count > 0 and position+count <= len(words), "SPIR-V instruction boundary invalid")
        operands = words[position+1:position+count]
        if opcode == 17:
            require(len(operands) == 1, "SPIR-V capability instruction invalid")
            capabilities.append(operands[0])
        if opcode == 71 and len(operands) >= 2 and operands[1] == 5300:
            decorations.append(operands[0])
        explicit += opcode == 88
        implicit += opcode == 87
        position += count
    require(1 in capabilities, "SPIR-V Shader capability absent")
    if nonuniform:
        require(5301 in capabilities and 5307 in capabilities and decorations, "Compiled scene fragment lacks sampled-image NonUniform qualification")
        require(explicit > 0, "Compiled fragment lacks explicit-LOD image sampling")
    return {"words": len(words), "version": words[1], "bound": words[3], "capabilities": sorted(set(capabilities)),
            "nonuniformDecoratedIds": sorted(set(decorations)), "explicitLodInstructions": explicit, "implicitLodInstructions": implicit,
            "scope": "Structural SPIR-V/qualification observations; not a substitute for native typed sampling/readback controls."}


def view_contract(row, kind, levels):
    require(isinstance(row, dict) and row.get("basis") == "captured-successful-vkCreateImageView-arguments"
            and row.get("type") == kind and row.get("baseMip") == 0 and row.get("mips") == levels
            and row.get("baseLayer") == 0 and row.get("layers") == (6 if kind == 3 else 1)
            and row.get("aspect") == 1 and row.get("handle", 0) > 0 and row.get("image", 0) > 0,
            "Captured application view creation contract differs")


def sampler_contract(row):
    require(isinstance(row, dict) and row.get("basis") == "captured-successful-vkCreateSampler-arguments"
            and row.get("handle", 0) > 0 and row.get("minFilter") == 1 and row.get("magFilter") == 1
            and row.get("bias") == 0 and row.get("anisotropy") is False and row.get("minLod") == 0
            and row.get("maxLod", 0) >= 4 and row.get("address") == [2, 2, 2],
            "Captured dedicated sampler creation contract differs")


def early_evidence(out):
    data = read_json(out/"early.json")
    require(data.get("schema") == "shadedoomvk-pf113-startup-observer/v1" and data.get("status") == "PASS",
            "Actual startup missing/publication observer receipt absent or failed")
    fixed = data.get("fixed", {})
    require(fixed.get("nullSlot") == 0 and fixed.get("brdfSlot") == 1, "Actual fixed descriptor slots differ")
    view_contract(fixed.get("null"), 1, 1)
    view_contract(fixed.get("brdf"), 1, 1)
    events = data.get("events", [])
    require(len(events) == 2 and [row.get("kind") for row in events] == ["before-completed-publication", "completed-publication"],
            "Actual first publication event order absent")
    for ordinal, row in enumerate(events):
        require(row.get("sequence") == ordinal and row.get("irradiancePairs") == ordinal+1
                and row.get("prefilterPairs") == ordinal+1 and row.get("authoredCount") == 2
                and row.get("authoredPositions") == [{"ordinal": i, "position": p} for i, p in enumerate(inputs.PROBES)],
                "Actual authored geometry/publication counts differ")
    draws = data.get("draws", [])
    require(len(draws) == 3 and {row.get("kind") for row in draws} == {"initial-missing-probe1", "initial-live-authored0", "published-live-probe1"},
            "Missing, actual authored0 and later live actual PBR draws required")
    authored_zero = next(row.get("state", {}).get("runtimeProbe") for row in draws if row.get("kind") == "initial-live-authored0")
    require(type(authored_zero) is int and authored_zero > 1, "Actual emitted authored0 live runtime pair absent")
    records = []
    for draw in draws:
        published = draw["kind"] == "published-live-probe1"
        zero_draw = draw["kind"] == "initial-live-authored0"
        live = published or zero_draw
        state = draw.get("state", {})
        token = state.get("runtimeProbe")
        require(draw.get("material") in ("PF113W", "PF113FL") and state.get("authoredProbe") == (0 if zero_draw else 1)
                and type(token) is int and (token > 1 if live else token == 0)
                and state.get("uniformProbe") == token
                and state.get("publishedPairs") == (2 if published else 1)
                and (state.get("publicationCount", 0) >= 1 if published else state.get("publicationCount") == 0)
                and state.get("shaderIndex") == 4 and state.get("effectState") == 4
                and state.get("commandBuffer", 0) > 0 and state.get("pipeline", 0) > 0 and state.get("drawCount", 0) > 0
                and 1 <= state.get("targetWidth", 0) <= 4096 and 1 <= state.get("targetHeight", 0) <= 4096,
                "Actual bound PBR missing/live draw state differs")
        if published:
            require(token != authored_zero, "Published probe1 aliases actual emitted probe0 runtime pair")
        require(state.get("viewOwnerOrdinal") == (1 if published else 0)
                and state.get("missingTokenSamplesNoCube") is (not live), "Missing-token and retained-owner semantics differ")
        view_contract(state.get("irradianceView"), 3, 1)
        view_contract(state.get("prefilterView"), 3, 5)
        sampler_contract(state.get("irradianceSampler"))
        sampler_contract(state.get("prefilterSampler"))
        stem = "early-"+draw["kind"]
        vert, vert_pin = named_artifact(out, draw.get("vertexSpirv"), stem+".vert.spv")
        frag, frag_pin = named_artifact(out, draw.get("fragmentSpirv"), stem+".frag.spv")
        size, probe_offset, texture_offset = [state.get(key) for key in ("uniformSize", "probeOffset", "textureOffset")]
        require((size, probe_offset, texture_offset) == (400, 380, 372), "Actual bound uniform ABI differs from pinned SurfaceUniforms")
        uniform, uniform_pin = named_artifact(out, draw.get("uniformBytes"), stem+".uniforms.bin", size)
        require(struct.unpack_from("<i", uniform, probe_offset)[0] == token
                and struct.unpack_from("<i", uniform, texture_offset)[0] == state.get("uniformTexture"),
                "Retained actual bound uniform bytes differ from draw state")
        records.append({"kind": draw["kind"], "material": draw["material"], "state": state,
                        "vertexSpirv": {**vert_pin, **spirv(vert)},
                        "fragmentSpirv": {**frag_pin, **spirv(frag, nonuniform=True)}, "uniformBytes": uniform_pin})
    require(1 <= data.get("completedPublicationsAtFinalCommand", 0) <= 5, "Actual final publication counter differs")
    packaged, pin = artifact(out, "early", "-packaged-pbr.glsl")
    require(packaged.replace(b"\r\n", b"\n") == (ROOT/"wadsrc/static/shaders/scene/lightmodel_pbr.glsl").read_bytes().replace(b"\r\n", b"\n"),
            "Actual packaged production PBR shader differs from candidate source")
    return {"identity": identity(out/"early.json"), "fixed": fixed, "events": events, "draws": records,
            "completedPublicationsAtFinalCommand": data["completedPublicationsAtFinalCommand"], "packagedShader": pin,
            "scope": "Actual emitted immediate specialized PBR commands; application creation arguments, not driver queries."}


def screenshot_evidence(out):
    path = out/"presentation.png"
    pixels, decoded = base.decode_screenshot_png(path)
    # Actual native draw state establishes PBR identity. This bounded interior
    # screen region only rejects empty/missing presentation; it is no radiometry.
    samples = [tuple(pixels[(y*640+x)*3:(y*640+x)*3+3]) for y in range(80, 360, 4) for x in range(80, 560, 4)]
    colours = len(set(samples))
    positive = sum(max(row) > 8 for row in samples)
    require(colours >= 16 and positive >= len(samples)//4, "Fixed-scene screenshot is empty or lacks visible scene variation")
    return {"status": "PASS", "identity": identity(path), "decode": decoded,
            "roi": [80, 80, 480, 280], "sampleStride": 4, "distinctColours": colours, "positiveSamples": positive,
            "scope": "Decoded fixed-scene context only; actual PBR/publication identity is separately observed."}


def function_text(source, signature):
    require(source.count(signature) == 1, "Packaged function boundary ambiguous: " + signature)
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        depth += source[position] == "{"
        depth -= source[position] == "}"
        if depth == 0:
            return source[start:position+1]
    raise ValueError("Packaged function is incomplete")


def control_shader_sources(out):
    packaged, packaged_pin = artifact(out, "native", "-packaged-pbr.glsl")
    calibration, calibration_pin = artifact(out, "native", "-packaged-calibration.glsl")
    source = packaged.decode().replace("\r\n", "\n")
    require(source == (ROOT/"wadsrc/static/shaders/scene/lightmodel_pbr.glsl").read_text().replace("\r\n", "\n"),
            "Native packaged PBR source differs")
    shared = calibration.decode().replace("\r\n", "\n")
    require(shared == (ROOT/"wadsrc/static/shaders/scene/lightmodel_shared.glsl").read_text().replace("\r\n", "\n"),
            "Native packaged PBR calibration differs")
    consumer = function_text(source, "vec3 ProcessMaterialLight(")
    gather = "uvec4 probeIndexes = textureGather(uintTextures[nonuniformEXT(vLightmapIndex + 1)], vLightmap.xy);"
    for before, after in ((gather, gather+"\n\tdiagTaps = probeIndexes;"),
                          ("float t11 = t.x * t.y;", "float t11 = t.x * t.y;\n\tdiagWeights = vec4(t00,t10,t01,t11);"),
                          ("return color;", "diagIrradiance=irradiance; diagPrefiltered=prefilteredColor; diagDiffuse=diffuse; diagSpecular=specular;\n"
                           "diagLo=Lo; diagFinal=color; diagN=N; diagR=R;\n\treturn color;")):
        require(consumer.count(before) == 1, "Native observation-only insertion boundary changed")
        consumer = consumer.replace(before, after)
    pins = {"packagedPbr": packaged_pin, "packagedCalibration": calibration_pin}
    for variant in ("candidate", "original-uniform"):
        shader, shader_pin = artifact(out, "native", "-"+variant+".frag.glsl")
        shader = shader.decode().replace("\r\n", "\n")
        wanted = consumer
        if variant == "original-uniform":
            wanted = wanted.replace("irradiance = SampleProbeIrradiance(uint(uLightProbeIndex), N);",
                                    "irradiance = texture(cubeTextures[uLightProbeIndex], N).rgb;")
            wanted = wanted.replace("prefilteredColor = SampleProbePrefiltered(uint(uLightProbeIndex), R, roughness * MAX_REFLECTION_LOD);",
                                    "prefilteredColor = textureLod(cubeTextures[uLightProbeIndex + 1], R, roughness * MAX_REFLECTION_LOD).rgb;")
        require(wanted in shader, "Compiled native control does not contain exact observation-only production consumer")
        for signature in ("float DistributionGGX(", "float GeometrySchlickGGX(", "float GeometrySmith(", "vec3 fresnelSchlick(",
                          "vec3 fresnelSchlickRoughness(", "vec3 SampleProbeIrradiance(", "vec3 SampleProbePrefiltered("):
            require(function_text(source, signature) in shader, "Compiled native helper differs: " + signature)
        require(shared[:shared.index("float distanceAttenuation")] in shader, "Native calibration constants changed")
        pins[variant] = shader_pin
    return pins


def raw_control_relationships(values, pair_a, pair_b):
    """Recompute relationships from actual GPU float files, not native PASS."""
    require(set(values) == set(CONTROL_NAMES), "Native float control inventory differs")
    for name, row in values.items():
        require(len(row) == 32*10*4 and all(math.isfinite(value) for value in row), "Native float result is nonfinite or truncated: " + name)
    def at(name, band, x, channel):
        return values[name][(band*32+x)*4+channel]
    maximum_parity, maximum_gather, maximum_quad = 0., 0., 0.
    for x in range(32):
        for name in ("uniform-zero", "gather-allzero"):
            for band in range(4):
                require(all(at(name, band, x, c) == 0. for c in range(3)), "Missing IBL contains a cube contribution")
        for name in ("uniform-zero", "gather-allzero", "quad-zero-live"):
            for c in range(3):
                require(at(name, 4, x, c) > 0 and abs(at(name, 4, x, c)-at("uniform-live-a", 4, x, c)) <= TOLERANCE,
                        "Missing case changed independent positive Lo")
                if name != "quad-zero-live" or x % 3 == 0:
                    require(abs(at(name, 5, x, c)-at(name, 4, x, c)) <= TOLERANCE, "Zero final differs from retained Lo")
        for suffix in ("a", "b"):
            for band in range(8):
                for c in range(3):
                    error = abs(at("uniform-live-"+suffix, band, x, c)-at("original-uniform-"+suffix, band, x, c))
                    maximum_parity = max(maximum_parity, error)
                    require(error <= TOLERANCE, "Live result differs from legal original uniform comparison")
                    if band < 2:
                        require(at("uniform-live-"+suffix, band, x, c) > 0, "Live cube control lacks positive sampling")
        for name in ("gather-mixed", "gather-live", "gather-allzero"):
            taps = [at(name, 8, x, i) for i in range(4)]
            expected_taps = {"gather-mixed": [pair_b, 0, 0, pair_a], "gather-live": [pair_a, pair_b, pair_b, pair_a],
                             "gather-allzero": [0, 0, 0, 0]}[name]
            require(taps == expected_taps, "Actual gathered token order differs from retained 2x2 R16 map")
            weights = [at(name, 9, x, i) for i in range(4)]
            require(all(abs(a-b) < 1.e-6 for a, b in zip(weights, (.30, .10, .45, .15))), "Actual original gather coefficients changed")
            for band in range(2):
                for c in range(3):
                    expected = sum(at("uniform-live-a" if token == pair_a else "uniform-live-b", band, x, c)*weight
                                   for token, weight in zip(taps, weights) if token)
                    error = abs(at(name, band, x, c)-expected)
                    maximum_gather = max(maximum_gather, error)
                    require(error <= TOLERANCE, "Mixed/live gather renormalizes, substitutes, reorders or changes sampled radiance")
        for name in ("quad-zero-live", "quad-live-live"):
            expected_name = "uniform-zero" if name == "quad-zero-live" and x % 3 == 0 else (
                "uniform-live-b" if name == "quad-live-live" and x % 3 == 0 else "uniform-live-a")
            expected_token = 0 if expected_name == "uniform-zero" else (pair_b if expected_name.endswith("b") else pair_a)
            require(at(name, 7, x, 3) == expected_token, "Actual divergent quad runtime identity differs")
            for band in range(8):
                for c in range(3):
                    error = abs(at(name, band, x, c)-at(expected_name, band, x, c))
                    maximum_quad = max(maximum_quad, error)
                    require(error <= TOLERANCE, "Adjacent zero/live or differing live fragment differs from corresponding uniform result")
        for name in CONTROL_NAMES:
            require(all(at(name, band, x, 3) == 1. for band in range(6)), "Native diagnostic pixel was not completely written")
            roughness = 0. if name == "roughness-zero-live-a" else 1. if name == "roughness-one-live-a" else .375
            require(at(name, 6, x, 3) == roughness, "Actual material roughness changed")
            n = [at(name, 6, x, c) for c in range(3)]
            reflection = [at(name, 7, x, c) for c in range(3)]
            require(abs(sum(v*v for v in n)-1.) <= 1.e-5, "Actual N is not normalized")
            require(all(abs(n[c]-at("uniform-live-a", 6, x, c)) <= 1.e-6
                        and abs(reflection[c]-at("uniform-live-a", 7, x, c)) <= 1.e-6 for c in range(3)), "Native N/R directions changed between controls")
    lod_delta = max(abs(at("roughness-zero-live-a", 1, x, c)-at("roughness-one-live-a", 1, x, c)) for x in range(32) for c in range(3))
    spatial_delta = max(abs(at("uniform-live-a", 0, x, c)-at("uniform-live-a", 0, 0, c)) for x in range(32) for c in range(3))
    pair_delta = max(abs(at("uniform-live-a", 0, x, c)-at("uniform-live-b", 0, x, c)) for x in range(32) for c in range(3))
    require(lod_delta > .05 and spatial_delta > .01 and pair_delta > .1, "Live spatial, LOD or differing-pair positive witnesses are constant")
    return {"maximumLiveParityError": maximum_parity, "maximumGatherError": maximum_gather, "maximumQuadError": maximum_quad,
            "lodDelta": lod_delta, "spatialDelta": spatial_delta, "pairDelta": pair_delta, "tolerance": TOLERANCE,
            "controls": 12, "pixelsPerControl": 320, "scope": "Independent numerical relationships recomputed from actual retained GPU RGBA32F outputs."}


def native_evidence(out, case):
    early = early_evidence(out)
    data = read_json(out/"native.json")
    require(data.get("schema") == "shadedoomvk-pf113-native-probe-controls/v1" and data.get("status") == "PASS"
            and data.get("error") == "" and 16000 <= data.get("checks", 0) <= 200000,
            "Native control receipt absent, failed or incomplete")
    require(data.get("width") == 32 and data.get("height") == 10 and data.get("format") == "rgba32float-little-endian"
            and data.get("rows") == CONTROL_ROWS and data.get("tolerance") == TOLERANCE,
            "Native float control extent/row/tolerance contract changed")
    require(Path(data.get("startupReceipt", "")).resolve(strict=True) == (out/"early.json").resolve(strict=True), "Native startup receipt identity differs")
    settings = data.get("settings", {})
    require(settings.get("rendererMode") == case["rendererMode"] and settings.get("globalTextureFilter") == case["globalFilter"]
            and settings.get("lightProbeEnabled") is True and settings.get("levelMesh") is False and settings.get("uberShaders") is False
            and settings.get("lightShadows") == 0 and settings.get("clientExtent") == [640, 480] and settings.get("renderExtent") == [640, 480],
            "Actual completed command settings/extent differ from fixture")
    require(data.get("fixedBefore") == early["fixed"] and data.get("fixedAfter") == data["fixedBefore"]
            and data.get("normalPrivateRetirement") is True and data.get("retirementFenceCompleted") is True,
            "Private controls changed fixed owners or skipped ordinary retirement/final normal fence")
    resources = data.get("resources", {})
    pair_a, pair_b = resources.get("pairA"), resources.get("pairB")
    require(type(pair_a) is int and type(pair_b) is int and 1 < pair_a <= 65535 and 1 < pair_b <= 65535
            and pair_b != pair_a+2 and pair_a != 1 and pair_b != 3
            and len({pair_a, pair_b, resources.get("unusedGap"), resources.get("probeMap")}) == 4,
            "Actual private allocator-returned separated resource identity differs")
    cube_views = resources.get("ownedCubeViews", [])
    require(len(cube_views) == 4, "Actual private four-cube inventory missing")
    sampler_contract(resources.get("irradianceSampler"))
    sampler_contract(resources.get("prefilterSampler"))
    view_contract(resources.get("mapView"), 1, 1)
    require(resources["mapView"].get("format") == 74, "Actual probe map is not R16_UINT")
    require(resources.get("mapSampler", {}).get("minFilter") == 0 and resources["mapSampler"].get("magFilter") == 0,
            "Actual integer probe map sampler is not nearest")
    view_contract(resources.get("target"), 1, 1)
    require(resources["target"].get("format") == 109, "Legal own control target is not RGBA32F")
    uploads = []
    for number, view in enumerate(cube_views):
        mips, size = (1, 32) if number % 2 == 0 else (5, 128)
        view_contract(view, 3, mips)
        require(view.get("format") == 97, "Actual private cube is not RGBA16F")
        expected = bytearray()
        for face in range(6):
            for mip in range(mips):
                extent = size >> mip
                for y in range(extent):
                    for x in range(extent):
                        expected.extend(struct.pack("<4e", *[.125*(number+1)+(c+face)/32.+x/256.+y/512.+mip/16. for c in range(3)], 1.))
        payload, pin = artifact(out, "native", f"-cube{number}.rgba16f", len(expected))
        require(payload == expected, "Actual private cube upload bytes differ from exact authored spatial values")
        uploads.append(pin)
    require(len({view["handle"] for view in cube_views}) == 4 and len({view["image"] for view in cube_views}) == 4, "Private cube views/images alias")
    cases = data.get("cases", [])
    require(len(cases) == 12 and [row.get("name") for row in cases] == list(CONTROL_NAMES), "Actual native control inventory/order differs")
    values, artifacts = {}, []
    for row in cases:
        name = row["name"]
        mode = 0 if name == "uniform-zero" else 1 if name.startswith("gather-") else 2 if name == "quad-zero-live" else 3 if name == "quad-live-live" else 4
        roughness = 0. if name == "roughness-zero-live-a" else 1. if name == "roughness-one-live-a" else .375
        require(row.get("mode") == mode and row.get("roughness") == roughness and row.get("referenceUniformOriginal") is name.startswith("original-")
                and row.get("drawVertices") == 3 and row.get("normalFenceWaited") is True and row.get("bytes") == 5120,
                "Actual native draw route/roughness/fence differs: " + name)
        payload, pin = named_artifact(out, row.get("file"), "native-"+name+".rgba32f", 5120)
        values[name] = struct.unpack("<1280f", payload)
        probe_map, map_pin = named_artifact(out, row.get("mapFile"), "native-"+name+".probe-map-r16", 8)
        expected_map = (pair_a, 0, pair_b, 0) if name == "gather-mixed" else (pair_a, pair_b, pair_a, pair_b) if name == "gather-live" else (0, 0, 0, 0)
        require(struct.unpack("<4H", probe_map) == expected_map, "Retained actual uploaded probe map differs")
        artifacts.append({"name": name, "readback": pin, "probeMap": map_pin})
    comparison = raw_control_relationships(values, pair_a, pair_b)
    require(data.get("zeroSamples") == 768 and data.get("positiveLiveSamples") == 384 and data.get("divergenceWitnesses") == 128,
            "Native zero/live/divergence sample inventory differs")
    require(abs(data.get("maximumLiveParityError", math.inf)-comparison["maximumLiveParityError"]) <= 1.e-6
            and abs(data.get("maximumMixedError", math.inf)-comparison["maximumGatherError"]) <= 1.e-6,
            "Native comparison summaries differ from independently decoded actual floats")
    source_pins = control_shader_sources(out)
    spv_rows = {}
    require(data.get("spirv", {}).get("compiledByEngine") is True, "Native shader compiler identity missing")
    for key, name in (("candidate", "native-candidate.frag.spv"), ("legalOriginalUniform", "native-original-uniform.frag.spv"), ("vertex", "native-control.vert.spv")):
        payload, pin = named_artifact(out, data["spirv"].get(key), name)
        spv_rows[key] = {**pin, **spirv(payload, nonuniform=key == "candidate")}
    marker = re.findall(r"^PF113 PASS: ([0-9]+) checks, ([0-9]+) retained controls;", base.log_text(out/"stdout.log"), re.M)
    require(marker == [(str(data["checks"]), "12")], "Actual unique native PASS completion not observed")
    return {"identity": identity(out/"native.json"), "early": early, "actualJson": data, "comparison": comparison,
            "readbackArtifacts": artifacts, "cubeUploads": uploads, "shaderSources": source_pins, "spirv": spv_rows,
            "scope": "Actual production body/helper bounded private fragment controls plus independent natural scene/publication observation."}


def retained_output_identities(out, receipt):
    """Retain partial inventories and a durable failure even if one hash fails."""
    receipt["nativeArtifacts"], receipt["outputs"] = {}, {}
    try:
        files = sorted(path for path in out.iterdir() if path.is_file() and path.name.startswith(("native", "early")))
        require(len(files) <= 512, "Native artifact count exceeds bound")
    except Exception as error:
        receipt.update(status="FAIL", artifactError=f"Native artifact inventory: {type(error).__name__}: {error}")
        files = []
    artifact_errors = []
    for path in files:
        try:
            receipt["nativeArtifacts"][path.name] = identity(path)
        except Exception as error:
            artifact_errors.append(f"{path.name}: {type(error).__name__}: {error}")
    if artifact_errors:
        receipt.update(status="FAIL", artifactError="Native artifact identity failure", artifactIdentityErrors=artifact_errors)
    output_errors = []
    for path in (out/"stdout.log", out/"stderr.log", out/"validation.log", out/"fixture-live.ini"):
        try:
            if path.is_file():
                receipt["outputs"][path.name] = identity(path)
        except Exception as error:
            output_errors.append(f"{path.name}: {type(error).__name__}: {error}")
    if output_errors:
        receipt.update(status="FAIL", outputError="Retained output identity failure", outputIdentityErrors=output_errors)


def launch(receipt, manifest, case, manifest_path, executable, out, mode, layer_dir, candidate):
    require(snapshot(manifest_path, executable, layer_dir, manifest, case, candidate) == receipt["before"], "Prelaunch identities changed")
    for row in receipt["generated"].values():
        require(identity(Path(row["path"])) == row, "Generated launch input changed")
    env, env_record = base.environment(out, layer_dir)
    receipt.update(status="RUNNING", startedUtc=base.utc(), environment=env_record)
    save(out/"receipt.json", receipt)
    process = None
    try:
        with (out/"stdout.log").open("wb") as stdout, (out/"stderr.log").open("wb") as stderr:
            process = subprocess.Popen(receipt["argv"], cwd=out, env=env, stdout=stdout, stderr=stderr)
            receipt.update(pid=process.pid, applicationLaunched=True, gpuExecuted=None)
            save(out/"receipt.json", receipt)
            base.wait_child(process, out, receipt, Path(manifest["mod"]["path"]).name)
        require(receipt.get("exitCode") == 0, "Native child did not exit normally")
        receipt["loadedPackages"] = package_evidence(out, receipt["before"])
        require(receipt["loadedPackages"]["verified"], "Actual seven-package startup closure differs")
        receipt["validation"] = base.validation_evidence(out, mode)
        require(receipt["validation"]["requestedModeVerified"], "Actual CURRENT requested mode/loader activation not observed")
        require(receipt["validation"]["errorCount"] == 0 and receipt["validation"]["warningCount"] == 0, "Native validation errors/warnings observed")
        receipt["exitSettings"] = base.exit_settings_evidence(out, case)
        require(receipt["exitSettings"]["verified"], "Normal-exit saved renderer/filter differs")
        receipt["native"] = native_evidence(out, case)
        receipt["gpuExecuted"] = True
        receipt["presentation"] = screenshot_evidence(out)
        receipt["status"] = "PASS"
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.kill()
            receipt["exitCode"] = process.wait(timeout=10)
            receipt["interruptionAction"] = {"action": "kill own Popen child", "pid": process.pid}
        receipt.update(status="FAIL", error=f"{type(error).__name__}: {error}")
    finally:
        receipt["finishedUtc"] = base.utc()
        try:
            receipt["after"] = snapshot(manifest_path, executable, layer_dir, manifest, case, candidate)
            receipt["immutableInputsUnchanged"] = receipt["after"] == receipt["before"]
            require(receipt["immutableInputsUnchanged"], "Source/build/input/layer changed during execution")
            for key in ("configInput", "exec", "settings"):
                require(identity(Path(receipt["generated"][key]["path"])) == receipt["generated"][key], "Generated immutable input changed")
        except Exception as error:
            receipt.update(status="FAIL", identityError=f"{type(error).__name__}: {error}")
        for key, collect in (("loadedPackages", lambda: package_evidence(out, receipt["before"])),
                             ("validation", lambda: base.validation_evidence(out, mode)),
                             ("native", lambda: native_evidence(out, case)), ("presentation", lambda: screenshot_evidence(out))):
            if key not in receipt:
                try:
                    receipt[key] = collect()
                except Exception as error:
                    receipt[key+"Unavailable"] = f"{type(error).__name__}: {error}"
        retained_output_identities(out, receipt)
        save(out/"receipt.json", receipt)
    return 0 if receipt["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case", default="hardware-truecolour-nearest")
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("core", "sync"), required=True)
    parser.add_argument("--layer-dir", type=Path, required=True)
    parser.add_argument("--candidate-receipt", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare", action="store_true", help="Prepare reviewed inputs only (default)")
    action.add_argument("--launch", action="store_true", help="Explicitly launch only the reviewed candidate child")
    args = parser.parse_args()
    try:
        args.manifest, args.exe, args.out, args.layer_dir, args.candidate_receipt = [path.resolve() for path in
            (args.manifest, args.exe, args.out, args.layer_dir, args.candidate_receipt)]
        if args.launch and args.out.exists():
            receipt, manifest, case = resume(args.manifest, args.case, args.exe, args.out, args.mode, args.layer_dir, args.candidate_receipt)
        else:
            receipt, manifest, case = prepare(args.manifest, args.case, args.exe, args.out, args.mode, args.layer_dir, args.candidate_receipt)
        result = launch(receipt, manifest, case, args.manifest, args.exe, args.out, args.mode, args.layer_dir, args.candidate_receipt) if args.launch else 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out/"receipt.json"), "gpuExecuted": receipt["gpuExecuted"]}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
