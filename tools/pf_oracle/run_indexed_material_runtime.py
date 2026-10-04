#!/usr/bin/env python3
"""Prepare, or explicitly launch, one bounded #110 native acceptance case.

The default writes a durable PREPARED receipt and never starts a process. Only
--launch starts the exact staged executable. No CFX campaign code is imported,
no GPU probe is launched, and the watchdog can kill only its own Popen child.
Source/binary identity is recorded; the external build receipt must establish
source-to-binary correspondence. This is never a performance measurement.
"""
from __future__ import annotations

import argparse
import ast
import configparser
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "pf110-bounded-native-run-v1"
WATCHDOG_SECONDS = 90
LAYER = "VK_LAYER_KHRONOS_validation"
EXTRA_SOURCES = (
    "tools/pf_oracle/run_indexed_material_runtime.py", "tools/cfx_capture.py",
    "src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp",
    "src/common/rendering/vulkan/textures/vk_imagetransition.h",
    "src/common/rendering/vulkan/textures/vk_imagetransition.cpp",
    "src/common/rendering/vulkan/textures/vk_texture.cpp",
    "src/common/rendering/vulkan/vk_renderstate.cpp",
    "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp",
    "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp",
    "src/common/rendering/vulkan/samplers/vk_samplers.cpp",
    "src/common/console/c_dispatch.cpp", "src/m_misc.cpp", "src/g_game.cpp",
    "src/d_net.cpp", "src/d_main.cpp", "src/common/engine/i_net.h", "src/common/textures/m_png.cpp",
    "src/common/rendering/vulkan/vk_renderdevice.cpp", "src/common/rendering/vulkan/vk_postprocess.cpp",
    "wadsrc/static/shaders/pp/present.fp",
    "src/CMakeLists.txt", "CMakeLists.txt",
)
REQUIRED_CASES = (
    "default", "a-first", "b-after-a", "a-return", "b-return", "a-return-again",
    "b-first", "a-after-b", "b-first-return", "inverse-a", "inverse-b", "off-grid",
    "xy-nomip", "same-id-replaced-b", "same-id-restored-a", "nonpositive",
    "invalid-translation", "luminosity-unremapped", "inactive-unremapped",
    "retire-queued-draw", "recreated-after-retirement", "ordinary-control",
    "ordinary-palette-and-alpha-controls",
    "indexed-alpha-half-opaque", "indexed-colour-tag", "indexed-object-add-colour",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path: Path):
    path = path.resolve(strict=True)
    require(path.is_file(), f"Required file is missing: {path}")
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, maximum=4 * 1024 * 1024):
    require(path.stat().st_size <= maximum, f"JSON exceeds bounded size: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def save(path: Path, receipt):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def safe_console_path(path: Path):
    value = path.resolve().as_posix()
    require(not any(c in value for c in '\r\n"\0'), "Console path contains an unsupported quote/control byte")
    return value


def checked(record, label):
    require(isinstance(record, dict) and record.get("path") and re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", "")),
            f"Missing immutable {label} identity")
    found = identity(Path(record["path"]))
    require(found["sha256"] == record["sha256"], f"{label} changed since preparation")
    expected_size = record.get("bytes", record.get("size"))
    require(expected_size is None or found["bytes"] == expected_size, f"{label} size changed")
    return found


def source_path(name):
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "Manifest source must be repository relative")
    path = (ROOT / relative).resolve(strict=True)
    require(path.is_relative_to(ROOT), "Manifest source escaped the active repository")
    return path


def settings_recipe(mode):
    path = ROOT / "tools/cfx_capture.py"
    source = path.read_text(encoding="utf-8")
    assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "VALIDATION_SETTINGS" for target in node.targets)]
    require(len(assignments) == 1, "Validation recipe constant is ambiguous")
    recipe = ast.literal_eval(assignments[0].value)[mode]
    expected = {
        "core": ("validate_core = true", "validate_sync = false", "gpuav_enable = false"),
        "sync": ("validate_core = false", "validate_sync = true", "gpuav_enable = false", "syncval_submit_time_validation = true"),
    }
    require(tuple(recipe) == expected[mode], "Authoritative core/sync activation recipe changed")
    for text in ("khronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG",
                 "khronos_validation.report_flags = error;warn;info", "khronos_validation.log_filename = "):
        require(text in source, "Authoritative validation log recipe changed")
    return recipe


def layer_identity(directory: Path):
    directory = directory.resolve(strict=True)
    manifest = directory / "VkLayer_khronos_validation.json"
    data = read_json(manifest)
    layer = data.get("layer", {})
    require(layer.get("name") == LAYER and layer.get("library_path"), "Unexpected validation layer manifest")
    library = (directory / layer["library_path"]).resolve(strict=True)
    require(library.is_relative_to(directory), "Validation library must be in the explicitly supplied layer directory")
    return {"manifest": identity(manifest), "library": identity(library),
            "apiVersion": layer.get("api_version"), "implementationVersion": layer.get("implementation_version")}


def build_inventory(executable: Path):
    files = sorted(path for path in executable.parent.iterdir() if path.is_file()
                   and path.suffix.lower() in (".exe", ".dll", ".pk3", ".pdb"))
    require(1 <= len(files) <= 128 and any(path.suffix.lower() == ".pk3" for path in files),
            "Staged runtime must have a bounded executable/resource package inventory")
    return {path.name: identity(path) for path in files}


def candidate_identity(path: Path | None, executable: Path):
    if path is None:
        return None
    data = read_json(path)
    require(data.get("schema") == "pf110-native-candidate/v1" and data.get("native_build", {}).get("exit") == 0,
            "Candidate receipt has no successful native build")
    artifacts = data.get("artifacts", [])
    matches = [record for record in artifacts if Path(record.get("path", "")).resolve() == executable.resolve()]
    require(len(matches) == 1, "Candidate receipt must name the exact staged executable once")
    checked(matches[0], "candidate executable")
    verified_artifacts = []
    for record in artifacts:
        found = checked(record, "candidate runtime artifact")
        if record.get("source"):
            source = checked({**record, "path": record["source"]}, "candidate build counterpart")
            found["buildSource"] = source
        verified_artifacts.append(found)
    source_files = data.get("source_files", {})
    require(isinstance(source_files, dict) and 100 <= len(source_files) <= 10000, "Candidate source closure is missing")
    for name, pins in source_files.items():
        payload = source_path(name).read_bytes()
        require(hashlib.sha256(payload).hexdigest() == pins.get("raw_sha256"), f"Native candidate source changed: {name}")
        require(hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest() == pins.get("normalized_lf_sha256"),
                f"Native candidate normalized source identity differs: {name}")
    return {"receipt": identity(path), "verifiedArtifacts": verified_artifacts, "verifiedSourceFiles": len(source_files),
            "sourceHead": data.get("source_head"), "sourceStatus": data.get("source_status"), "nativeBuild": data["native_build"]}


def immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt=None):
    sources = {}
    declared = manifest.get("fixtureInterfaceSources", {})
    require(isinstance(declared, dict) and 10 <= len(declared) <= 128, "Frozen generator source pins are missing")
    for name, expected in declared.items():
        found = identity(source_path(name))
        require(found["sha256"] == expected, f"Prepared fixture source changed: {name}")
        sources[name] = found
    for name in EXTRA_SOURCES:
        sources[name] = identity(source_path(name))
    inputs = {
        "manifest": identity(manifest_path), "mod": checked(manifest["mod"], "synthetic mod"),
        "iwad": checked(manifest["iwad"], "IWAD"),
        "configuration": checked({"path": case["config"], "sha256": case["configSha256"]}, "prepared config"),
        "captureScript": checked({"path": case["captureScript"], "sha256": case["captureScriptSha256"]}, "prepared capture script"),
    }
    exe = checked(manifest.get("executable"), "staged executable")
    require(Path(exe["path"]) == executable.resolve(strict=True), "--exe differs from the frozen manifest executable")
    return {"sources": sources, "inputs": inputs, "build": build_inventory(executable), "layer": layer_identity(layer_dir),
            "candidate": candidate_identity(candidate_receipt, executable)}


def checked_case(manifest, case_name, executable):
    require(manifest.get("schema") == "pf110-indexed-runtime-inputs-v1"
            and manifest.get("status") == "prepared-unaccepted" and manifest.get("gpuExecuted") is False,
            "Expected a frozen, unexecuted generator manifest")
    matches = [case for case in manifest.get("scenarios", []) if case.get("id") == case_name]
    require(len(matches) == 1, "Case must select exactly one prepared scenario")
    case = matches[0]
    require(re.fullmatch(r"(hardware-truecolour|hardware-palette|software-palette-swcanvas)-(nearest|linear)", case_name),
            "Only the prepared empty-room material cases are supported")
    require(case.get("rendererMode") in (4, 2, 0) and case.get("globalFilter") in (0, 2)
            and case.get("extent") == [640, 480] and case.get("executed") is False,
            "Prepared case contract differs from the bounded fixture")
    expected = [str(executable.resolve()), "-stdout", "-noautoload", "-nosound", "-nojoy", "-iwad", manifest["iwad"]["path"],
                "-file", manifest["mod"]["path"], "-config", case["config"], "-width", "640", "-height", "480",
                "+map", "PF110", "+exec", case["captureScript"]]
    require(case.get("command") == expected, "Prepared argv is not the fixed empty PF110 map command")
    with zipfile.ZipFile(manifest["mod"]["path"]) as archive:
        members = manifest["mod"].get("members", {})
        require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(members),
                "Synthetic mod member inventory changed")
        for name, record in members.items():
            require(archive.getinfo(name).file_size <= 512 * 1024, "Synthetic fixture member exceeds bound")
            payload = archive.read(name)
            require(len(payload) == record["bytes"] and hashlib.sha256(payload).hexdigest() == record["sha256"],
                    f"Synthetic fixture member changed: {name}")
    return case


def execution_script(out):
    # FExecList dispatches each physical line independently. AddCommandString's
    # wait delays only the semicolon-separated remainder of that SAME line.
    # NetUpdate bounds its backlog at BACKUPTICS/2-1 (17 for36). A35-tic
    # post-diagnostic/enable gap crosses that batch; actual callback acknowledgement
    # and decoded panel pixels remain mandatory rather than inferring presentation.
    commands = ("pf110_overlay false", "wait 105", "vid_setsize 640 480", "wait 5",
                'pf_indexedmaterial_validate "' + safe_console_path(out / "native") + '"', "wait 35",
                "pf110_overlay true", "wait 35", 'screenshot "' + safe_console_path(out / "presentation.png") + '"',
                "wait 5", "quit")
    line = "; ".join(commands)
    # C_ParseExecFile uses a 4096-byte buffer and Gets(..., countof(cmd)-1).
    require(len(line.encode("utf-8")) + 1 <= 4094, "Generated exec exceeds the native parser's single-line bound")
    return line + "\n"


def execution_command(case, out):
    command = list(case["command"])
    command[command.index("-config") + 1] = str(out / "fixture-live.ini")
    command[command.index("+exec") + 1] = str(out / "execute.cfg")
    command.insert(command.index("-noautoload") + 1, "-noautoexec")
    return command


def prepare(manifest_path: Path, case_name: str, executable: Path, out: Path, mode: str, layer_dir: Path, candidate_receipt=None):
    manifest_path = manifest_path.resolve(strict=True)
    executable = executable.resolve(strict=True)
    manifest = read_json(manifest_path)
    case = checked_case(manifest, case_name, executable)
    before = immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt)
    recipe = settings_recipe(mode)
    out = out.resolve()
    require(not out.exists(), "Output must be a new directory; existing evidence is immutable")
    require(not out.is_relative_to(executable.parent), "Output must be outside the frozen staged runtime directory")
    out.mkdir(parents=True)
    configuration = out / "fixture-live.ini"
    configuration.write_bytes(Path(case["config"]).read_bytes())
    (out / "fixture-input.ini").write_bytes(configuration.read_bytes())
    prefix, screenshot = out / "native", out / "presentation.png"
    script = out / "execute.cfg"
    script.write_text(execution_script(out), encoding="utf-8", newline="\n")
    settings = out / "vk_layer_settings.txt"
    settings.write_text("\n".join("khronos_validation." + item for item in recipe)
                        + "\nkhronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG\n"
                        + "khronos_validation.report_flags = error;warn;info\n"
                        + "khronos_validation.log_filename = " + safe_console_path(out / "validation.log") + "\n",
                        encoding="utf-8", newline="\n")
    # Prevent user/global autoexec content; the only commands are the generated exec.
    command = execution_command(case, out)
    generated = {name: identity(path) for name, path in (("configInput", out / "fixture-input.ini"),
                 ("configLiveBefore", configuration), ("exec", script), ("settings", settings))}
    receipt = {"schema": SCHEMA, "status": "PREPARED", "preparedUtc": utc(), "gpuExecuted": False,
               "case": case_name, "validationMode": mode, "argv": command, "cwd": str(out),
               "watchdogSeconds": WATCHDOG_SECONDS, "before": before, "generated": generated,
               "diagnosticPrefix": str(prefix), "screenshot": str(screenshot), "sourceToBinaryAttestedHere": False,
               "limitations": ["External native build receipt establishes source-to-binary correspondence.",
                   "Normal exit may rewrite only the live config; immutable input config and saved result are separately hashed.",
                   "Presentation acceptance checks the declared synthetic ROIs, not whole-frame equality or a tint-effect claim.",
                   "No performance measurement or full-frame budget is claimed."]}
    save(out / "receipt.json", receipt)
    return receipt, manifest, case


def resume_prepared(manifest_path, case_name, executable, out, mode, layer_dir, candidate_receipt):
    manifest = read_json(manifest_path)
    case = checked_case(manifest, case_name, executable)
    receipt = read_json(out / "receipt.json")
    require(receipt.get("schema") == SCHEMA and receipt.get("status") == "PREPARED" and receipt.get("gpuExecuted") is False,
            "Only an unexecuted PREPARED receipt can be launched; failed/running/completed evidence is immutable")
    require(receipt.get("case") == case_name and receipt.get("validationMode") == mode and receipt.get("cwd") == str(out)
            and receipt.get("watchdogSeconds") == WATCHDOG_SECONDS and receipt.get("argv") == execution_command(case, out),
            "Reviewed prepared case/command differs from requested launch")
    require((out / "execute.cfg").read_text(encoding="utf-8") == execution_script(out), "Prepared diagnostic exec differs")
    require(immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt) == receipt.get("before"),
            "Reviewed prepared source/input/build/layer identities changed")
    return receipt, manifest, case


def environment(out, layer_dir):
    removed = [key for key in os.environ if key.startswith("CFX_") or key in (
        "VK_ADD_LAYER_PATH", "VK_LAYER_PATH", "VK_INSTANCE_LAYERS", "VK_LAYER_SETTINGS_PATH",
        "VK_LOADER_LAYERS_ENABLE", "VK_LOADER_LAYERS_DISABLE", "VK_LOADER_LAYERS_ALLOW", "VK_LAYER_ENABLES", "VK_LAYER_DISABLES")]
    env = {key: value for key, value in os.environ.items() if key not in removed}
    values = {"VK_ADD_LAYER_PATH": str(layer_dir.resolve()), "VK_INSTANCE_LAYERS": LAYER,
              "VK_LAYER_SETTINGS_PATH": str(out / "vk_layer_settings.txt"), "VK_LOADER_DEBUG": "layer"}
    env.update(values)
    require(not any(key.startswith("CFX_") for key in env), "Unexpected CFX environment")
    return env, {"removedNames": sorted(removed), "processScopedOverrides": values}


def log_text(path):
    if not path.is_file():
        return ""
    require(path.stat().st_size <= 32 * 1024 * 1024, f"Log exceeds bounded analysis size: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def fixture_script_error(text, mod_name):
    """Recognize only a compiler error naming the frozen synthetic package."""
    pattern = (r'\bScript error,\s*"[^"\r\n]*' + re.escape(mod_name)
               + r':[^"\r\n]+" line [0-9]+:')
    for line in text.splitlines():
        if re.search(pattern, line, re.I):
            return line
    return None


def wait_child(process, out, receipt, mod_name):
    """Poll bounded log chunks; terminate only this child on proven failure."""
    started = time.monotonic()
    offsets = {name: 0 for name in ("stdout.log", "stderr.log")}
    tails = {name: "" for name in offsets}
    while True:
        pending_logs = False
        for name in offsets:
            path = out / name
            if not path.is_file():
                continue
            require(path.stat().st_size <= 32 * 1024 * 1024, f"Log exceeds bounded analysis size: {path}")
            with path.open("rb") as stream:
                stream.seek(offsets[name])
                chunk = stream.read(64 * 1024)
            offsets[name] += len(chunk)
            pending_logs |= offsets[name] < path.stat().st_size
            combined = tails[name] + chunk.decode("utf-8", errors="replace")
            tails[name] = combined[-8192:]
            header = fixture_script_error(combined, mod_name)
            if header:
                still_running = process.poll() is None
                receipt["startupAbort"] = {"reason": "Synthetic fixture script compilation failed", "log": name,
                    "matchedHeader": header, "pid": process.pid, "elapsedSeconds": time.monotonic() - started,
                    "action": "kill own Popen child" if still_running else "own child already exited"}
                if still_running:
                    process.kill()
                receipt["exitCode"] = process.wait(timeout=10)
                raise ValueError("Synthetic fixture script compilation failed: " + header)
        exit_code = process.poll()
        if exit_code is not None:
            if pending_logs:
                continue  # Drain already-written bounded chunks before classifying an exited child.
            receipt["exitCode"] = exit_code
            return
        remaining = WATCHDOG_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            receipt["watchdogAction"] = {"action": "kill own Popen child", "pid": process.pid, "seconds": WATCHDOG_SECONDS}
            process.kill()
            receipt["exitCode"] = process.wait(timeout=10)
            raise ValueError("90-second child watchdog expired")
        try:
            process.wait(timeout=min(0.25, remaining))
        except subprocess.TimeoutExpired:
            pass


def loaded_package_evidence(out, before, *, startup_text=None):
    """Compare the filesystem's actual ordered startup inventory to pinned inputs."""
    allowed = {Path(record["path"]).resolve(): record for record in before["build"].values()
               if Path(record["path"]).suffix.lower() == ".pk3"}
    for name in ("iwad", "mod"):
        record = before["inputs"][name]
        path = Path(record["path"]).resolve()
        require(path not in allowed, "Pinned runtime package identities overlap")
        allowed[path] = record
    mandatory = {Path(before["inputs"][name]["path"]).resolve() for name in ("iwad", "mod")}
    for name in ("vkdoom.pk3", "game_support.pk3"):
        record = before["build"].get(name)
        require(record is not None, f"Mandatory staged resource package is missing: {name}")
        mandatory.add(Path(record["path"]).resolve())
    # A caller may supply one explicitly delimited startup block. The default
    # deliberately retains whole-log duplicate rejection for ordinary one-run use.
    text = log_text(out / "stdout.log") if startup_text is None else startup_text
    require(isinstance(text, str) and len(text.encode("utf-8")) <= 32 * 1024 * 1024, "Startup text exceeds bounded analysis size")
    lines = re.findall(r"^adding (.+), ([0-9]+) lumps\s*$", text, re.M)
    require(len(lines) <= 130, "Actual loaded-package inventory exceeds bounded size")
    actual, seen, errors = [], set(), []
    for raw_path, lumps in lines:
        path = Path(raw_path)
        path = (path if path.is_absolute() else out / path).resolve()
        entry = {"ordinal": len(actual), "printedPath": raw_path, "path": str(path), "lumps": int(lumps),
                 "pinned": path in allowed}
        if path in seen:
            errors.append(f"Duplicate loaded package: {path}")
        seen.add(path)
        if path not in allowed:
            errors.append(f"Unpinned loaded package: {path}")
        try:
            entry.update(identity(path))
            expected = allowed.get(path)
            if expected and (entry["sha256"] != expected["sha256"] or entry["bytes"] != expected["bytes"]):
                errors.append(f"Loaded package differs from its pinned identity: {path}")
        except (OSError, ValueError) as error:
            entry["identityUnavailable"] = f"{type(error).__name__}: {error}"
            errors.append(f"Loaded package identity is unavailable: {path}")
        actual.append(entry)
    for path in sorted(mandatory - seen):
        errors.append(f"Mandatory pinned package was not observed loading: {path}")
    return {"verified": not errors, "orderedPackages": actual, "packageCount": len(actual), "errors": errors,
            "requiredPackages": [str(path) for path in sorted(mandatory)],
            "scope": "Actual startup adding-PATH-lumps lines; every loaded package is pinned and rehashed."}


def validation_severity(line, log_name):
    """Use emitted severity headers, never severity words inside information text."""
    header = re.match(r"\s*Validation(?: Layer)?\s+(Error|Warning)\s*(?::|-)\s*", line, re.I)
    if header:
        return "errors" if header[1].lower() == "error" else "warnings"
    # The engine's VkDebugUtils callback prints the actual message severity here.
    callback = re.match(r"\s*\[(?:vulkan|validation)\s+(error|warning)\]\s*", line, re.I)
    if callback:
        return "errors" if callback[1].lower() == "error" else "warnings"
    severity = re.match(r"\s*(?:\[Vulkan Loader\]\s*)?(ERROR|WARNING)\b", line, re.I)
    if severity and ((log_name == "validation.log" and re.match(r"\s*(?:ERROR|WARNING)\s*:", line, re.I))
                     or re.search(r"\b(?:VUID|SYNC-HAZARD)\b", line, re.I)):
        return "errors" if severity[1].lower() == "error" else "warnings"
    return None


def validation_evidence(out, mode):
    logs = {name: log_text(out / name) for name in ("stdout.log", "stderr.log", "validation.log")}
    insertion = [line for line in logs["stderr.log"].splitlines()
                 if LAYER in line and re.search(r"\b(?:Insert\w*|Loading|using)\b", line, re.I)]
    validation = logs["validation.log"]
    blocks = []
    for marker in re.finditer("CURRENT-VALIDATION-ENABLED", validation):
        block = validation[marker.start():]
        following = re.search(r"\n(?:Validation (?:Information|Warning|Error)|INFO|WARNING|ERROR)\b", block)
        blocks.append(block[:following.start()] if following else block)
    labels = {"core": "  - Core Checks", "sync": "  - Synchronization", "gpu-assisted": "  - GPU-AV"}
    enabled = {name: any(label in block for block in blocks) for name, label in labels.items()}
    findings = {"errors": [], "warnings": []}
    for name, text in logs.items():
        for line in text.splitlines():
            severity = validation_severity(line, name)
            if severity:
                findings[severity].append({"log": name, "line": line})
    require(len(findings["errors"]) + len(findings["warnings"]) <= 8192, "Validation finding count exceeds bound")
    return {"loaderInsertionLines": insertion, "currentValidationEnabledBlocks": blocks,
            "enabled": enabled, "requestedModeVerified": bool(insertion and blocks and enabled[mode]
                and not enabled["gpu-assisted"] and not enabled["sync" if mode == "core" else "core"]),
            "errorCount": len(findings["errors"]), "warningCount": len(findings["warnings"]), **findings}


def native_filter_evidence(data, case):
    observed = data.get("globalTextureFilter")
    return {"observed": observed, "requested": case["globalFilter"],
            "verified": type(observed) is int and observed == case["globalFilter"],
            "scope": "Actual completed native diagnostic's gl_texture_filter value."}


def exit_settings_evidence(out, case):
    path = out / "fixture-live.ini"
    require(path.stat().st_size <= 1024 * 1024, "Saved configuration exceeds bounded size")
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    # The engine's INI intentionally stores repeated Path entries in search/autoexec
    # sections. Parse only GlobalSettings strictly; never inherit DEFAULT values.
    global_lines, in_global, global_sections = [], False, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        section = parser.SECTCRE.match(line.strip())
        if section:
            in_global = section["header"] == "GlobalSettings"
            if in_global:
                global_sections += 1
                require(global_sections == 1, "Duplicate saved GlobalSettings section")
                global_lines.append(line)
        elif in_global:
            global_lines.append(line)
    parser.read_string("\n".join(global_lines))
    require(parser.has_section("GlobalSettings"), "Saved GlobalSettings section is missing")
    observed = {name: parser.getint("GlobalSettings", name) for name in ("vid_rendermode", "gl_texture_filter")}
    requested = {"vid_rendermode": case["rendererMode"], "gl_texture_filter": case["globalFilter"]}
    return {"identity": identity(path), "observed": observed, "requested": requested, "verified": observed == requested,
            "scope": "Saved GlobalSettings observed at normal exit; this does not prove per-draw renderer state."}


def native_participation_evidence(data, case, cases):
    mode = data.get("rendererMode")
    require(type(mode) is int and mode == case["rendererMode"], "Actual native diagnostic renderer mode differs from the selected case")
    by_name = {row["name"]: row for row in cases}
    require(len(by_name) == len(cases), "Native diagnostic contains duplicate case names")
    controls = {
        "indexed-alpha-half-opaque": "public-alpha-half-inherited-opaque",
        "indexed-colour-tag": "public-colour-command-luminance-white-vertex",
        "indexed-object-add-colour": "actual-getTexel-add-object-before-palette",
    }
    for name, control in controls.items():
        row = by_name.get(name, {})
        require(row.get("indexed") is True and row.get("pixelOracleApplied") is True
                and row.get("pixelMismatches") == 0 and row.get("control") == control,
                f"Required actual indexed material control is missing or failed: {name}")
    alpha, colour, object_add = (by_name[name] for name in controls)
    require(alpha.get("publicAlpha") == 0.5 and alpha.get("whiteVertexColour") is True,
            "Public indexed alpha control did not retain its authored half-alpha/white-vertex state")
    require(type(colour.get("publicColor")) is int and colour["publicColor"] not in (0, 0xffffffff)
            and colour.get("whiteVertexColour") is True, "Public indexed colour tag control is missing its inherited white vertices")
    require(object_add.get("addRedByte") == 16 and object_add.get("objectRedByte") == 128
            and object_add.get("changedPixels", 0) > 0 and object_add.get("rejectedOrderingPixels", 0) > 0,
            "Actual indexed shader object/add colour ordering witness is missing")
    return {"rendererMode": mode, "controls": controls,
            "scope": "Actual native command mode and public material controls; no DTA_Color object-uniform equivalence claimed."}


def software_canvas_evidence(out, data, case, cases):
    software = data.get("softwareCanvas", {})
    mode = case["rendererMode"]
    require(software.get("actualMode") == mode and software.get("required") is (mode == 0),
            "Native software-canvas requirement differs from the selected mode")
    observers = [row for row in cases if row.get("name") == "software-existing-swcanvas"]
    if mode != 0:
        require(software.get("observed") is False and not observers, "Hardware mode unexpectedly claimed a software producer observation")
        return {"actualJson": software, "artifacts": {}, "scope": "Software producer observation is not required in this actual mode."}
    require(software.get("observed") is True and software.get("ownerCount") == 2
            and software.get("registryUnchanged") is True and software.get("hostPixelsWritten") is False
            and software.get("producerCreationPerformed") is False and software.get("softwareDrawPerformedByDiagnostic") is False,
            "Actual mode0 must observe two pre-existing SWCanvas producers without creating or drawing substitutes")
    require(software.get("before") == software.get("after") and isinstance(software.get("before"), dict)
            and all(type(software["before"].get(key)) is int and software["before"][key] >= 0
                    for key in ("materials", "hardwareTextures", "gameTextures", "descriptorEntries")),
            "Software observer changed or omitted producer registry counts")
    require(len(observers) == 1 and observers[0].get("descriptorOnly") is True
            and observers[0].get("shaderResultClaimed") is False and observers[0].get("observerOnly") is True
            and all(observers[0].get(key) == value for key, value in software.items()), "Software observer case metadata is inconsistent")
    records = software.get("records", [])
    require(len(records) == 2, "Actual mode0 must retain both rotating software owner records")
    artifacts, owners, materials = {}, set(), set()
    for i, record in enumerate(records):
        for key in ("ownerPointer", "materialPointer", "indexImage", "indexView", "paletteImage", "paletteView"):
            require(isinstance(record.get(key), str) and re.fullmatch(r"[0-9]+", record[key]) and int(record[key]) > 0,
                    f"Existing software producer has no actual {key}")
        owners.add(record["ownerPointer"])
        materials.add(record["materialPointer"])
        require(record.get("sourceName") == "" and record.get("sourceScaleFlags") == 0
                and record.get("wrapperColorFormat") == 0 and record.get("layerCount") == 2
                and [record.get("width"), record.get("height")] == case["extent"], "Software producer identity/extent differs from its canonical wrapper")
        require(record.get("trackedBaseLayout") == 1 and record.get("trackedPaletteLayout") == 5
                and record.get("nativeOffsetBytes") == 0 and type(record.get("nativeRowPitchBytes")) is int
                and record["nativeRowPitchBytes"] == record.get("producerPitchBytes") >= record["width"]
                and record.get("pitchMatchesProducer") is True, "Mapped software pitch/offset or tracked layouts contradict its producer")
        require(record.get("mappedReadAfterNormalFence") is True and record.get("mappedImageTransferred") is False
                and record.get("indexedAuxiliaryImagesAbsent") is True and record.get("indexedPaletteDescriptorAbsent") is True,
                "Software observer transferred or substituted its existing mapped producer")
        tokens = record.get("tokens", [])
        require(1 <= len(tokens) <= 128 and all(token.get("live") is True and token.get("span") == 2
                and all(type(token.get(key)) is int and token[key] >= (0 if key == "index" else 1)
                        for key in ("index", "generation", "epoch")) for token in tokens), "Existing software descriptor tokens are not live two-resource blocks")
        stem = Path(record["artifactStem"]).resolve()
        require(stem.parent == out and stem.name == f"native-software-existing-swcanvas-{i}", "Software artifact escaped the fresh output directory")
        for suffix, size, declared in ((".mapped-r8", record["width"] * record["height"], "mappedBytes"),
                                       (".resident-palette-bgra8", 1024, "paletteBytes")):
            artifact = Path(str(stem) + suffix)
            require(record.get(declared) == size and artifact.stat().st_size == size, "Software mapped/palette artifact size differs from its actual producer")
            artifacts[stem.name + suffix] = identity(artifact)
    require(len(owners) == 2 and len(materials) == 2, "Software observation duplicated one owner/material instead of both rotating producers")
    return {"actualJson": software, "artifacts": artifacts,
            "scope": "Pre-existing software producer state and mapped bytes after its normal fence; layouts are tracked CPU state, not driver layout queries; no software shader-result equivalence."}


def diagnostic_evidence(out, case):
    path = out / "native.json"
    data = read_json(path)
    require(data.get("schema") == "shadedoomvk-pf110-native-indexed/v1", "Native diagnostic schema missing")
    checks = data.get("checks", [])
    require(data.get("status") == "PASS" and not data.get("error") and checks
            and data.get("assertions") == len(checks) and all(check.get("pass") is True for check in checks),
            "Native diagnostic did not complete all assertions")
    filtering = native_filter_evidence(data, case)
    require(filtering["verified"], "Actual native diagnostic texture filter differs from the selected case")
    cases = data.get("cases", [])
    require(len(cases) <= 64 and all(name in [case.get("name") for case in cases] for name in REQUIRED_CASES),
            "Required native material cases are missing")
    participation = native_participation_evidence(data, case, cases)
    software = software_canvas_evidence(out, data, case, cases)
    artifacts = dict(software["artifacts"])
    for case in cases:
        if case.get("descriptorOnly"):
            continue
        stem = Path(case["artifactStem"]).resolve()
        require(stem.parent == out and stem.name == "native-" + case["name"], "Native artifact escaped the fresh output directory")
        result = Path(str(stem) + ".rgba8")
        require(result.stat().st_size == case.get("rgbaBytes") == 128 * 20 * 4, "Native result readback extent mismatch")
        require(not case.get("pixelOracleApplied") or case.get("pixelMismatches") == 0, "Native pixel oracle failed")
        for suffix in (".rgba8", ".input-r8", ".expected-r8", ".basepalette-bgra8"):
            artifacts[case["name"] + suffix] = identity(Path(str(stem) + suffix))
        if not case.get("retiredBeforeWait"):
            suffixes = (".resident-r8", ".resident-palette-bgra8") if case["indexed"] else (".resident-bgra8",)
            for suffix in suffixes:
                artifacts[case["name"] + suffix] = identity(Path(str(stem) + suffix))
    for name in ("native-ordinary-palette.resident-r8", "native-ordinary-alpha.resident-r8", "native-ordinary-alpha.expected-r8"):
        artifacts[name] = identity(out / name)
    return {"identity": identity(path), "actualJson": data, "artifacts": artifacts, "textureFilter": filtering,
            "participation": participation, "softwareCanvas": software}


PRESENTATION_ROWS = (
    ("neutral-indexed", "neutral-ordinary", "neutral-flat"),
    ("a-first-A", "a-first-B", "a-repeat-A"),
    ("b-first-B", "b-first-A", "b-repeat-B"),
    ("inverse-A", "inverse-reference", "rejected-row-order-model"),
    ("tinted-indexed-A", "tinted-reference", "ordinary-red-is-alpha"),
    ("boundary-indexed-A", "boundary-reference", "boundary-flat"),
    ("ordinary-translation-A", "missing-input", "indexed-translucent-A"),
)
PRESENTATION_INDICES = (5, 5, 250, 250, 10, 10, 20, 20, 96, 96, 160, 160, 200, 200, 32, 32)
PRESENTATION_ORDINARY = frozenset(("neutral-ordinary", "rejected-row-order-model", "ordinary-red-is-alpha",
                                  "boundary-reference", "ordinary-translation-A"))


def decode_screenshot_png(path):
    """Decode the engine's bounded RGB8/noninterlaced screenshot, without PIL.

    VkRenderDevice::GetScreenshotBuffer supplies SS_RGB to M_CreatePNG. This
    decoder validates actual PNG structure/CRC/zlib and all five PNG row filters;
    accepting an IHDR alone is deliberately insufficient.
    """
    require(33 <= path.stat().st_size <= 4 * 1024 * 1024, "Presentation PNG file size is invalid")
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", "Presentation PNG signature is invalid")
    position, compressed, saw_idat, ended_idat, finished = 8, bytearray(), False, False, False
    chunk_types = []
    for _ in range(1024):
        require(position + 12 <= len(data), "Presentation PNG chunk is truncated")
        length, kind = struct.unpack_from(">I4s", data, position)
        require(re.fullmatch(b"[A-Za-z]{4}", kind) and not (kind[2] & 32), "Presentation PNG chunk type is invalid")
        end = position + 12 + length
        require(end <= len(data), "Presentation PNG chunk data is truncated")
        body = data[position + 8:position + 8 + length]
        crc = struct.unpack_from(">I", data, position + 8 + length)[0]
        require(zlib.crc32(kind + body) & 0xffffffff == crc, "Presentation PNG CRC mismatch")
        require(chunk_types or kind == b"IHDR", "Presentation PNG IHDR is not first")
        if kind == b"IHDR":
            require(not chunk_types and length == 13, "Presentation PNG IHDR is invalid/duplicated")
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            require((width, height) == (640, 480), "Actual presentation screenshot differs from the prepared 640x480 extent")
            require((depth, colour, compression, filtering, interlace) == (8, 2, 0, 0, 0),
                    "Presentation PNG must use the actual engine RGB8 noninterlaced format")
        elif kind == b"IDAT":
            require(not ended_idat, "Presentation PNG IDAT chunks are not contiguous")
            compressed.extend(body)
            saw_idat = True
        elif kind == b"IEND":
            require(length == 0 and saw_idat and end == len(data), "Presentation PNG IEND/trailing bytes are invalid")
            finished = True
        else:
            require(kind[0] & 32 or kind == b"PLTE", "Presentation PNG contains an unsupported critical chunk")
            if kind == b"PLTE":
                require(not saw_idat and 0 < length <= 768 and length % 3 == 0 and kind not in chunk_types,
                        "Presentation PNG optional RGB palette is invalid")
            if saw_idat:
                ended_idat = True
        chunk_types.append(kind)
        position = end
        if finished:
            break
    require(finished and compressed, "Presentation PNG IEND or compressed image is missing")
    stride, expected = 640 * 3, 480 * (640 * 3 + 1)
    inflater = zlib.decompressobj()
    try:
        filtered = inflater.decompress(bytes(compressed), expected + 1)
    except zlib.error as error:
        raise ValueError("Presentation PNG compressed image is invalid") from error
    require(len(filtered) == expected and inflater.eof and not inflater.unconsumed_tail and not inflater.unused_data,
            "Presentation PNG decoded byte count or compressed stream boundary is invalid")
    pixels, previous, filters = bytearray(), bytearray(stride), []
    for y in range(480):
        start = y * (stride + 1)
        mode = filtered[start]
        require(mode <= 4, "Presentation PNG row filter is invalid")
        row = bytearray(filtered[start + 1:start + 1 + stride])
        for x in range(stride):
            left, above = (row[x - 3] if x >= 3 else 0), previous[x]
            upper_left = previous[x - 3] if x >= 3 else 0
            if mode == 1:
                prediction = left
            elif mode == 2:
                prediction = above
            elif mode == 3:
                prediction = (left + above) // 2
            elif mode == 4:
                base = left + above - upper_left
                distances = (abs(base - left), abs(base - above), abs(base - upper_left))
                prediction = (left, above, upper_left)[distances.index(min(distances))]
            else:
                prediction = 0
            row[x] = (row[x] + prediction) & 255
        pixels.extend(row)
        previous = row
        filters.append(mode)
    return bytes(pixels), {"format": "RGB8/noninterlaced", "decodedBytes": len(pixels),
                          "decodedRgbSha256": hashlib.sha256(pixels).hexdigest(),
                          "rowFiltersObserved": sorted(set(filters)), "chunks": [kind.decode("ascii") for kind in chunk_types]}


def presentation_contract(manifest):
    """Fail closed when frozen input metadata no longer describes this fixture."""
    expected = [{"name": name, "rect": [x, y, 128, 20],
                 "interiorSamples": [[x + 4 + column * 8, y + 10] for column in range(16)]}
                for row, y in zip(PRESENTATION_ROWS, (54, 104, 154, 204, 254, 304, 354))
                for name, x in zip(row, (120, 284, 448))]
    actual = manifest.get("rois", [])
    require(len(actual) == len(expected) and all(all(row.get(key) == value for key, value in wanted.items())
            for row, wanted in zip(actual, expected)), "Presentation ROI metadata differs from the source-declared fixture")
    source = manifest.get("syntheticInput", {})
    require(source.get("width") == 16 and source.get("height") == 4
            and source.get("rowMajorIndices") == list(PRESENTATION_INDICES) * 4,
            "Presentation source index lanes differ from the declared producer")
    require(manifest.get("scene", {}).get("roomStrip") == [0, 404, 640, 76], "Presentation clear/background boundary changed")
    return expected


def overlay_acknowledgement(text, case):
    lines = [line.strip() for line in text.splitlines() if "PF110_OVERLAY_READY" in line]
    expected = f'PF110_OVERLAY_READY mode={case["rendererMode"]} filter={case["globalFilter"]} extent=640x480 frames=2'
    return {"verified": lines == [expected], "observedLines": lines, "expected": expected,
            "scope": "Actual enabled RenderOverlay callback acknowledgement; pixel checks independently prove captured content."}


def screenshot_evidence(path, manifest, case, stdout_text):
    contract = presentation_contract(manifest)
    pixels, decode = decode_screenshot_png(path)
    result = {**identity(path), "extent": [640, 480], "decode": decode, "status": "FAIL",
              "units": "presented RGB bytes, separate from raw native shader readbacks", "checks": [], "rois": {},
              "acknowledgement": overlay_acknowledgement(stdout_text, case),
              "scope": "Declared synthetic panel relationships and presence; no raw-to-presentation, whole-frame or cross-mode equality claim.",
              "maximumRgbDifference": 1, "ordinaryFilteredObservations": []}
    checks, rois = result["checks"], result["rois"]

    def pixel(x, y):
        start = (y * 640 + x) * 3
        return tuple(pixels[start:start + 3])

    def close(a, b):
        return max(abs(x - y) for x, y in zip(a, b)) <= 1

    def check(name, passed, **details):
        checks.append({"name": name, "pass": bool(passed), **details})

    check("enabled-overlay-frame-acknowledgement", result["acknowledgement"]["verified"])
    for row in contract:
        x, y, width, height = row["rect"]
        samples = [pixel(*position) for position in row["interiorSamples"]]
        roi_bytes = b"".join(pixels[((y + dy) * 640 + x) * 3:((y + dy) * 640 + x + width) * 3] for dy in range(height))
        rois[row["name"]] = {**row, "rgbSamples": samples, "rgbSha256": hashlib.sha256(roi_bytes).hexdigest()}

    def samples(name):
        return rois[name]["rgbSamples"]

    def equal(left, right, full_inset=False, gate=True):
        differences = [max(abs(a - b) for a, b in zip(l, r)) for l, r in zip(samples(left), samples(right))]
        if full_inset:
            lx, ly, width, height = rois[left]["rect"]
            rx, ry, _, _ = rois[right]["rect"]
            differences.extend(max(abs(a - b) for a, b in zip(pixel(lx + x, ly + y), pixel(rx + x, ry + y)))
                               for y in range(2, height - 2) for x in range(2, width - 2))
        details = {"name": left + "==" + right, "comparedSamples": len(differences),
                   "fullInsetCompared": full_inset, "maximumDifference": max(differences)}
        if gate:
            check(details.pop("name"), all(value <= 1 for value in differences), **details)
        else:
            result["ordinaryFilteredObservations"].append({**details, "equalAtDiscreteTolerance": all(value <= 1 for value in differences),
                "scope": "Configured ordinary global-linear sampler; difference from indexed-nearest is recorded, not a parity requirement."})

    # Source panels contain pairs of equal lanes; positive diversity prevents a
    # blank/wrong room screenshot from satisfying only equalities.
    flats = {"neutral-flat", "boundary-flat"}
    for name in rois:
        if name in flats or name == "missing-input":
            continue
        values = samples(name)
        diverse = len(set(values)) >= (2 if name == "ordinary-red-is-alpha" else 4)
        pairs = all(close(values[i], values[i + 1]) for i in range(0, 16, 2))
        x, y, _, _ = rois[name]["rect"]
        vertical = all(close(value, pixel(x + 4 + i * 8, y + offset)) for i, value in enumerate(values) for offset in (4, 15))
        pair_gate = not (case["globalFilter"] == 2 and name in PRESENTATION_ORDINARY)
        check(name + "-authored-lane-shape", diverse and (pairs or not pair_gate) and vertical,
              distinctSamples=len(set(values)), equalPairedLanes=pairs, pairedLanesRequired=pair_gate, verticalRowsAgree=vertical,
              samplingScope="ordinary global-linear diversity/vertical control" if not pair_gate else "discrete authored-lane control")

    for left, right in (("a-first-A", "a-repeat-A"), ("a-first-A", "b-first-A"),
                        ("a-first-B", "b-first-B"), ("a-first-B", "b-repeat-B"),
                        ("neutral-indexed", "neutral-ordinary"), ("inverse-A", "inverse-reference"),
                        ("tinted-indexed-A", "tinted-reference"), ("a-first-A", "boundary-indexed-A"),
                        ("boundary-indexed-A", "boundary-reference"), ("a-first-A", "ordinary-translation-A"),
                        ("a-first-A", "indexed-translucent-A")):
        equal(left, right, full_inset=(left, right) in (("a-first-A", "a-repeat-A"), ("a-first-A", "b-first-A"),
                  ("a-first-B", "b-first-B"), ("a-first-B", "b-repeat-B"),
                  ("tinted-indexed-A", "tinted-reference"), ("a-first-A", "indexed-translucent-A")),
              gate=not (case["globalFilter"] == 2 and (left in PRESENTATION_ORDINARY or right in PRESENTATION_ORDINARY)))
    for left, right, label in (("a-first-A", "a-first-B", "different-canonical-translations-visible"),
                               ("inverse-A", "rejected-row-order-model", "noncommuting-inverse-order-visible")):
        differing = [i for i, (a, b) in enumerate(zip(samples(left), samples(right))) if not close(a, b)]
        check(label, bool(differing), differingSampleLanes=differing)

    # The actual flat is64x64: four repeats of the16-index row, stretched to128.
    # It is not the16x4 patch and must not be compared to its lane vector directly.
    neutral = samples("neutral-indexed")
    for name, origin, width in (("neutral-flat", 0, 128), ("boundary-flat", .25, 127.5)):
        mapping = [int((4 + i * 8 + .5 - origin) * 64 / width) % 16 for i in range(16)]
        differences = [max(abs(a - b) for a, b in zip(value, neutral[lane])) for value, lane in zip(samples(name), mapping)]
        check(name + "-actual64texel-coordinate-mapping", max(differences) <= 1, sourceSampleLanes=mapping, maximumDifference=max(differences))

    # Clear outside labels/panels at y380 and the missing-input panel must agree.
    background = pixel(300, 380)
    probes = ((100, 80), (600, 80), (100, 230), (600, 330), (100, 380), (600, 380))
    check("declared-overlay-clear-background", all(close(pixel(*position), background) for position in probes)
          and max(background) <= 64, backgroundRGB=background, probeCoordinates=probes)
    missing = samples("missing-input")
    check("missing-input-emits-no-draw", all(close(value, background) for value in missing))
    check("authored-panels-visible-over-clear", sum(not close(value, background) for value in samples("neutral-indexed")) >= 8)
    result["status"] = "PASS" if all(item["pass"] for item in checks) else "FAIL"
    return result


def launch(receipt, manifest, case, manifest_path, executable, out, mode, layer_dir, candidate_receipt=None):
    env, env_record = environment(out, layer_dir)
    require(immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt) == receipt["before"], "Immutable prelaunch identities changed")
    for key in ("configInput", "configLiveBefore", "exec", "settings"):
        require(identity(Path(receipt["generated"][key]["path"])) == receipt["generated"][key], "Generated launch input changed")
    receipt["environment"] = env_record
    receipt["status"] = "RUNNING"
    receipt["startedUtc"] = utc()
    save(out / "receipt.json", receipt)
    process = None
    try:
        with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(receipt["argv"], cwd=out, env=env, stdout=stdout, stderr=stderr)
            receipt["pid"] = process.pid
            receipt["applicationLaunched"] = True
            receipt["gpuExecuted"] = None  # launching a process does not prove native GPU execution.
            save(out / "receipt.json", receipt)
            wait_child(process, out, receipt, Path(manifest["mod"]["path"]).name)
        require(receipt["exitCode"] == 0, "Application exited nonzero")
        receipt["exitSettings"] = exit_settings_evidence(out, case)
        require(receipt["exitSettings"]["verified"], "Saved normal-exit renderer/filter settings differ from the selected case")
        receipt["loadedPackages"] = loaded_package_evidence(out, receipt["before"])
        require(receipt["loadedPackages"]["verified"], "Actual loaded-package closure did not match pinned inputs")
        receipt["validation"] = validation_evidence(out, mode)
        require(receipt["validation"]["requestedModeVerified"], "Loader insertion and CURRENT validation-mode activation not proved")
        require(receipt["validation"]["errorCount"] == 0 and receipt["validation"]["warningCount"] == 0,
                "Validation errors or warnings were observed")
        receipt["diagnostic"] = diagnostic_evidence(out, case)
        receipt["rawReadback"] = {"status": "PASS", "nativeReceiptIdentity": receipt["diagnostic"]["identity"],
                                  "assertions": receipt["diagnostic"]["actualJson"]["assertions"],
                                  "scope": "Native material/state/raw-byte gate; independent of captured presentation acceptance."}
        receipt["gpuExecuted"] = True
        require(re.search(r"\bPF110 PASS:", log_text(out / "stdout.log")), "Native PASS console completion was not observed")
        receipt["presentation"] = screenshot_evidence(out / "presentation.png", manifest, case, log_text(out / "stdout.log"))
        require(receipt["presentation"]["status"] == "PASS", "Captured presentation failed decoded-overlay/ROI acceptance")
        receipt["status"] = "PASS"
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.kill()
            receipt["exitCode"] = process.wait(timeout=10)
            receipt["interruptionAction"] = {"action": "kill own Popen child", "pid": process.pid}
        receipt["status"], receipt["error"] = "FAIL", f"{type(error).__name__}: {error}"
    finally:
        receipt["finishedUtc"] = utc()
        try:
            receipt["after"] = immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt)
            receipt["immutableInputsUnchanged"] = receipt["after"] == receipt["before"]
            require(receipt["immutableInputsUnchanged"], "Source/input/build/layer identity changed during execution")
            for key in ("configInput", "exec", "settings"):
                require(identity(Path(receipt["generated"][key]["path"])) == receipt["generated"][key], "Immutable generated input changed during execution")
        except Exception as error:
            receipt["status"] = "FAIL"
            receipt["identityError"] = f"{type(error).__name__}: {error}"
        # Failed activation or application exit must still retain observations.
        for key, collect in (("loadedPackages", lambda: loaded_package_evidence(out, receipt["before"])),
                             ("validation", lambda: validation_evidence(out, mode)),
                             ("diagnostic", lambda: diagnostic_evidence(out, case)),
                             ("presentation", lambda: screenshot_evidence(out / "presentation.png", manifest, case, log_text(out / "stdout.log")))):
            if key not in receipt:
                try:
                    receipt[key] = collect()
                except Exception as error:
                    receipt[key + "Unavailable"] = f"{type(error).__name__}: {error}"
        if receipt.get("exitCode") == 0 and "exitSettings" not in receipt:
            try:
                receipt["exitSettings"] = exit_settings_evidence(out, case)
            except Exception as error:
                receipt["exitSettingsUnavailable"] = f"{type(error).__name__}: {error}"
        native = out / "native.json"
        if native.is_file():
            receipt["nativeReceiptIdentity"] = identity(native)
            try:
                receipt["actualNativeJson"] = read_json(native)
            except Exception as error:
                receipt["actualNativeJsonUnavailable"] = f"{type(error).__name__}: {error}"
        native_artifacts = sorted(path for path in out.glob("native*") if path.is_file())
        if len(native_artifacts) <= 512:
            receipt["nativeArtifacts"] = {path.name: identity(path) for path in native_artifacts}
        else:
            receipt["status"], receipt["artifactError"] = "FAIL", "Native artifact inventory exceeds 512 files"
        if "diagnostic" in receipt:
            receipt["gpuExecuted"] = True
            receipt.setdefault("rawReadback", {"status": "PASS", "nativeReceiptIdentity": receipt["diagnostic"]["identity"],
                               "assertions": receipt["diagnostic"]["actualJson"]["assertions"],
                               "scope": "Native material/state/raw-byte gate; independent of captured presentation acceptance."})
        receipt["outputs"] = {path.name: identity(path) for path in (out / "stdout.log", out / "stderr.log", out / "validation.log", out / "fixture-live.ini") if path.is_file()}
        save(out / "receipt.json", receipt)
    return 0 if receipt["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("core", "sync"), required=True)
    parser.add_argument("--layer-dir", type=Path, required=True)
    parser.add_argument("--candidate-receipt", type=Path, help="Exact root native build/artifact/source receipt")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare", action="store_true", help="Write PREPARED evidence only (the default)")
    action.add_argument("--launch", action="store_true", help="Start the reviewed PREPARED child once, or prepare a fresh case then start")
    args = parser.parse_args()
    try:
        if args.launch and args.out.exists():
            receipt, manifest, case = resume_prepared(args.manifest.resolve(), args.case, args.exe.resolve(), args.out.resolve(),
                                                     args.mode, args.layer_dir.resolve(), args.candidate_receipt)
        else:
            receipt, manifest, case = prepare(args.manifest, args.case, args.exe, args.out, args.mode, args.layer_dir, args.candidate_receipt)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    try:
        result = launch(receipt, manifest, case, args.manifest.resolve(), args.exe.resolve(), args.out.resolve(), args.mode,
                        args.layer_dir.resolve(), args.candidate_receipt) if args.launch else 0
    except (OSError, ValueError, KeyError) as error:
        receipt["status"], receipt["prelaunchError"] = "FAIL", f"{type(error).__name__}: {error}"
        save(args.out.resolve() / "receipt.json", receipt)
        result = 1
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out.resolve() / "receipt.json"), "gpuExecuted": receipt["gpuExecuted"]}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
