#!/usr/bin/env python3
"""Prepare or explicitly launch one bounded, genuine in-process PF110 restart.

This is independent of historical CFX campaigns and never probes the GPU. Only
--launch starts one reviewed child; normal engine debug_restart supplies cleanup.
Native raw, value-token lifetime, startup provenance and presentation are separate
gates. Source/build/input hashes remain frozen throughout the process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle import run_indexed_material_runtime as base

SCHEMA = "pf110-bounded-native-restart/v1"
NATIVE_SCHEMA = "shadedoomvk-pf110-indexed-restart/v1"
PROTOCOL_SOURCES = (
    "tools/pf_oracle/run_indexed_material_restart.py",
    "tools/pf_oracle/tests/test_indexed_restart_runner.py",
    "src/common/utility/m_argv.cpp", "src/common/utility/m_argv.h",
    "src/r_data/v_palette.cpp", "src/g_level.cpp",
    "src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp",
)
require = base.require


def protocol_path(path):
    text = base.safe_console_path(path)
    require(len(text) <= 1024 and all(32 <= ord(c) < 127 and c not in ';"' for c in text),
            "Native restart paths require bounded printable ASCII without separators")
    return text


def command_chain(commands):
    text = "; ".join(commands) + "\n"
    require(len(text.encode("ascii")) <= 4094, "Restart exec exceeds the native physical-line bound")
    return text


def scripts(out):
    before_prefix = protocol_path(out / "before/native")
    after_prefix = protocol_path(out / "after/native")
    after_exec = protocol_path(out / "after/execute.cfg")
    before = command_chain(("wait 105", "vid_setsize 640 480", "wait 35",
        f'pf_indexedmaterial_restart_before "{before_prefix}" "{after_prefix}" "{after_exec}"'))
    after = command_chain(("wait 35", "map PF110", "wait 105", "vid_setsize 640 480", "wait 35",
        f'pf_indexedmaterial_restart_after "{after_prefix}"', "wait 35", "pf110_overlay true", "wait 35",
        f'screenshot "{protocol_path(out / "after/presentation.png")}"', "wait 5", "quit"))
    return before, after


def argv(case, out):
    command = base.execution_command(case, out)
    command[command.index("+exec") + 1] = str(out / "before/execute.cfg")
    return command


def snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt=None):
    result = base.immutable_snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt)
    for name in PROTOCOL_SOURCES:
        result["sources"][name] = base.identity(base.source_path(name))
    return result


def generated_identity(out):
    paths = {"configInput": out / "fixture-input.ini", "beforeExec": out / "before/execute.cfg",
             "afterExec": out / "after/execute.cfg", "settings": out / "vk_layer_settings.txt"}
    return {name: base.identity(path) for name, path in paths.items()}


def prepare(manifest_path, case_name, executable, out, mode, layer_dir, candidate_receipt=None):
    manifest_path, executable = manifest_path.resolve(strict=True), executable.resolve(strict=True)
    manifest = base.read_json(manifest_path)
    case = base.checked_case(manifest, case_name, executable)
    before = snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt)
    recipe = base.settings_recipe(mode)
    out = out.resolve()
    require(not out.exists(), "Restart output must be fresh; existing evidence is immutable")
    require(not out.is_relative_to(executable.parent), "Output must be outside the frozen staged runtime")
    before_script, after_script = scripts(out)
    (out / "before").mkdir(parents=True)
    (out / "after").mkdir()
    config = Path(case["config"]).read_bytes()
    (out / "fixture-live.ini").write_bytes(config)
    (out / "fixture-input.ini").write_bytes(config)
    (out / "before/execute.cfg").write_text(before_script, encoding="ascii", newline="\n")
    (out / "after/execute.cfg").write_text(after_script, encoding="ascii", newline="\n")
    (out / "vk_layer_settings.txt").write_text("\n".join("khronos_validation." + item for item in recipe)
        + "\nkhronos_validation.debug_action = VK_DBG_LAYER_ACTION_LOG_MSG\n"
        + "khronos_validation.report_flags = error;warn;info\n"
        + "khronos_validation.log_filename = " + base.safe_console_path(out / "validation.log") + "\n",
        encoding="utf-8", newline="\n")
    receipt = {"schema": SCHEMA, "status": "PREPARED", "preparedUtc": base.utc(), "gpuExecuted": False,
        "case": case_name, "validationMode": mode, "argv": argv(case, out), "cwd": str(out),
        "watchdogSeconds": base.WATCHDOG_SECONDS, "before": before, "generated": generated_identity(out),
        "configLiveBefore": base.identity(out / "fixture-live.ini"),
        "diagnosticPrefixes": {phase: str(out / phase / "native") for phase in ("before", "after")},
        "limitations": ["Normal engine debug_restart is required; no direct cleanup, palette clear or allocator reset is substituted.",
            "One child, two actual archive startup blocks and persistent Vulkan/layer activation are independently checked.",
            "Raw material/state evidence is distinct from synthetic presentation and value-token lifetime evidence.",
            "No performance, global frame budget, historical campaign or physical palette-address inequality claim."]}
    base.save(out / "receipt.json", receipt)
    return receipt, manifest, case


def resume_prepared(manifest_path, case_name, executable, out, mode, layer_dir, candidate_receipt=None):
    manifest = base.read_json(manifest_path)
    case = base.checked_case(manifest, case_name, executable)
    receipt = base.read_json(out / "receipt.json")
    require(receipt.get("schema") == SCHEMA and receipt.get("status") == "PREPARED" and receipt.get("gpuExecuted") is False,
            "Only an unexecuted PREPARED restart receipt may launch")
    require(receipt.get("case") == case_name and receipt.get("validationMode") == mode and receipt.get("cwd") == str(out)
            and receipt.get("argv") == argv(case, out) and receipt.get("watchdogSeconds") == base.WATCHDOG_SECONDS,
            "Reviewed restart case/command differs")
    require(snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt) == receipt.get("before"),
            "Prepared restart source/input/build/layer identities changed")
    require(generated_identity(out) == receipt.get("generated") and base.identity(out / "fixture-live.ini") == receipt.get("configLiveBefore"),
            "Prepared restart commands/configuration/layer settings changed")
    before, after = scripts(out)
    require((out / "before/execute.cfg").read_text(encoding="ascii") == before
            and (out / "after/execute.cfg").read_text(encoding="ascii") == after, "Prepared restart protocol changed")
    return receipt, manifest, case


def package_startups(out, before):
    text = base.log_text(out / "stdout.log")
    markers = list(re.finditer(r"^W_Init: Init WADfiles\.\s*$", text, re.M))
    require(len(markers) == 2, "Genuine restart requires exactly two actual W_Init startup blocks")
    require(not re.search(r"^adding .+, [0-9]+ lumps\s*$", text[:markers[0].start()], re.M),
            "Loaded package line occurred outside the two startup blocks")
    expected = {str(Path(row["path"]).resolve()) for row in before["build"].values() if Path(row["path"]).suffix.lower() == ".pk3"}
    expected.update(str(Path(before["inputs"][name]["path"]).resolve()) for name in ("iwad", "mod"))
    require(len(expected) == 7, "Restart requires the exact seven pinned runtime packages")
    blocks = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i == 0 else len(text)
        evidence = base.loaded_package_evidence(out, before, startup_text=text[marker.start():end])
        evidence["startupOrdinal"] = i
        require(evidence["verified"] and evidence["packageCount"] == 7
                and {row["path"] for row in evidence["orderedPackages"]} == expected,
                f"Restart startup block{i} has duplicate/missing/unpinned package identities: {evidence['errors']}")
        blocks.append(evidence)
    return {"verified": True, "startupCount": 2, "blocks": blocks,
            "scope": "Each actual startup independently loads every exact pinned package once; no global duplicate waiver."}


def persistent_vulkan(out, mode):
    result = base.validation_evidence(out, mode)
    require(result["requestedModeVerified"] and result["errorCount"] == result["warningCount"] == 0,
            "Actual validation activation or errors/warnings failed")
    stderr, stdout = base.log_text(out / "stderr.log"), base.log_text(out / "stdout.log")
    instance = re.findall(r'^.*\bInsert instance layer "VK_LAYER_KHRONOS_validation".*$', stderr, re.M)
    device = re.findall(r'^.*\bInserted device layer "VK_LAYER_KHRONOS_validation".*$', stderr, re.M)
    startup_device = re.findall(r"^Vulkan device: .+$", stdout, re.M)
    versions = re.findall(r"^Vulkan version: .+$", stdout, re.M)
    blocks = result["currentValidationEnabledBlocks"]
    handles = re.findall(r"\bVkInstance\s+(0x[0-9a-fA-F]+)\b", blocks[0]) if len(blocks) == 1 else []
    require(len(instance) == len(device) == len(startup_device) == len(versions) == len(blocks) == len(handles) == 1
            and int(handles[0], 16) > 0, "Restart must preserve one actual Vulkan instance/device/layer activation")
    return {**result, "instanceInsertionLines": instance, "deviceInsertionLines": device, "startupDeviceLines": startup_device,
            "startupVersionLines": versions, "observedVkInstance": handles[0],
            "scope": "Actual loader insertion and vkCreateInstance CURRENT block plus source-grounded startup log; native value identities independently check persistence."}


def positive_identity(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9]+", value)) and int(value) > 0


def restart_evidence(out, case, before_snapshot):
    phases = {}
    for phase in ("before", "after"):
        path = out / phase / ("native.restart-" + phase + ".json")
        data = base.read_json(path)
        require(data.get("schema") == NATIVE_SCHEMA and type(data.get("schemaVersion")) is int and data["schemaVersion"] == 1
                and data.get("stage") == phase and data.get("status") == "PASS"
                and not data.get("error"), "Native restart phase did not pass")
        require(Path(data.get("prefix", "")).resolve() == out / phase / "native"
                and Path(data.get("nativeReceipt", "")).resolve() == out / phase / "native.json"
                and Path(data.get("beforeNativePrefix", "")).resolve() == out / "before/native"
                and Path(data.get("afterNativePrefix", "")).resolve() == out / "after/native"
                and Path(data.get("afterExec", "")).resolve() == out / "after/execute.cfg", "Native restart paths do not match exact prepared protocol")
        require(data.get("valueOnlyCheckpoint") is True and data.get("oldResourcePointersDereferenced") is False
                and data.get("paletteAddressInequalityRequired") is False, "Restart used an unsafe pointer/address checkpoint")
        require(data.get("oldTokensCheckedBeforeProducer") is (phase == "after"), "AFTER old-token checks did not precede fresh producers")
        require(type(data.get("rendererMode")) is int and type(data.get("globalTextureFilter")) is int
                and data["rendererMode"] == case["rendererMode"] and data["globalTextureFilter"] == case["globalFilter"],
                "Native restart changed selected route/filter")
        for name in ("iwad", "mod"):
            require(Path(data.get(name, "")).resolve() == Path(before_snapshot["inputs"][name]["path"]).resolve(), "Native restart package identity differs")
        for name in ("managerIdentity", "deviceIdentity", "framebufferIdentity"):
            require(positive_identity(data.get(name)) and data.get("actual" + name[0].upper() + name[1:]) == data[name],
                    "Restart replaced its actual framebuffer/manager/device")
        tokens = data.get("tokens", [])
        require(len(tokens) == 2 and tokens[0].get("index") != tokens[1].get("index") and all(type(token.get("span")) is int and token["span"] == 2
                and all(type(token.get(key)) is int and token[key] >= (0 if key == "index" else 1)
                        for key in ("index", "generation", "epoch")) for token in tokens), "Restart has no two retained live pair tokens")
        require(type(data.get("beforeCounter")) is int and data["beforeCounter"] >= 0
                and type(data.get("actualCounter")) is int and data["actualCounter"] == data["beforeCounter"] + (phase == "after"),
                "Restart counter does not prove exactly one normal cleanup")
        live = data.get("oldTokensLive", [])
        require(len(live) == 2 and all(type(value) is bool for value in live)
                and live == ([True, True] if phase == "before" else [False, False]),
                "Retained pair tokens were not live before and stale after cleanup")
        for field in ("beforeLifetime", "actualLifetime"):
            stats = data.get(field, {})
            require(all(type(stats.get(key)) is int and stats[key] >= 0 for key in
                        ("activations", "retirements", "resets", "staleRejects", "invalidRetires", "duplicateActivations")),
                    "Native restart omitted actual lifetime counters")
        if phase == "after":
            old, actual = data["beforeLifetime"], data["actualLifetime"]
            require(actual["retirements"] >= old["retirements"] + 2 and actual["resets"] == old["resets"]
                    and actual["invalidRetires"] == old["invalidRetires"] and actual["duplicateActivations"] == old["duplicateActivations"]
                    and actual["staleRejects"] >= old["staleRejects"] + 2,
                    "Restart did not use ordinary owner retirement without resets/invalid frees")
        else:
            require(data["actualLifetime"] == data["beforeLifetime"], "BEFORE lifetime baseline differs from its actual retained state")
        phases[phase] = {"identity": base.identity(path), "actualJson": data}
    first, second = phases["before"]["actualJson"], phases["after"]["actualJson"]
    for key in ("beforeCounter", "managerIdentity", "deviceIdentity", "framebufferIdentity", "tokens", "beforeLifetime", "iwad", "mod",
                "afterExec", "beforeNativePrefix", "afterNativePrefix"):
        require(first[key] == second[key], "AFTER checkpoint differs from actual retained BEFORE state")
    text = base.log_text(out / "stdout.log")
    require(len(re.findall(r"^PF110_RESTART_BEFORE PASS counter=" + str(first["beforeCounter"]) + r" blocks=2; .+$", text, re.M)) == 1
            and len(re.findall(r"^PF110_RESTART_AFTER PASS counter=" + str(second["actualCounter"]) + r" old_blocks_stale=2; .+$", text, re.M)) == 1,
            "Actual one-shot BEFORE/AFTER completion markers were not observed")
    return {"status": "PASS", "phases": phases,
            "scope": "Value-only old descriptor pair rejection before the fresh diagnostic producer, after normal restart/map warm-up; actual normal debug_restart cleanup."}


def collect_evidence(receipt, out, case, manifest):
    collectors = (("loadedPackages", lambda: package_startups(out, receipt["before"])),
                  ("validation", lambda: persistent_vulkan(out, receipt["validationMode"])),
                  ("restart", lambda: restart_evidence(out, case, receipt["before"])),
                  ("exitSettings", lambda: base.exit_settings_evidence(out, case)),
                  ("presentation", lambda: base.screenshot_evidence(out / "after/presentation.png", manifest, case, base.log_text(out / "stdout.log"))))
    for phase in ("before", "after"):
        key = phase + "RawReadback"
        if key not in receipt:
            try:
                receipt[key] = {"status": "PASS", **base.diagnostic_evidence(out / phase, case)}
                receipt["gpuExecuted"] = True
            except Exception as error:
                receipt[key + "Unavailable"] = f"{type(error).__name__}: {error}"
    for key, collect in collectors:
        if key not in receipt:
            try:
                receipt[key] = collect()
            except Exception as error:
                receipt[key + "Unavailable"] = f"{type(error).__name__}: {error}"


def launch(receipt, manifest, case, manifest_path, executable, out, mode, layer_dir, candidate_receipt=None):
    require(snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt) == receipt["before"], "Immutable restart prelaunch identities changed")
    require(generated_identity(out) == receipt["generated"] and base.identity(out / "fixture-live.ini") == receipt["configLiveBefore"], "Generated restart inputs changed")
    env, receipt["environment"] = base.environment(out, layer_dir)
    receipt.update(status="RUNNING", startedUtc=base.utc(), process={"launchCount": 0, "pid": None})
    base.save(out / "receipt.json", receipt)
    process = None
    try:
        with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(receipt["argv"], cwd=out, env=env, stdout=stdout, stderr=stderr)
            receipt.update(applicationLaunched=True, gpuExecuted=None, pid=process.pid)
            receipt["process"] = {"launchCount": 1, "pid": process.pid, "protocol": "one child containing normal engine debug_restart"}
            base.save(out / "receipt.json", receipt)
            base.wait_child(process, out, receipt, Path(manifest["mod"]["path"]).name)
        require(receipt["exitCode"] == 0, "Restart application exited nonzero")
        collect_evidence(receipt, out, case, manifest)
        require(all(key in receipt for key in ("beforeRawReadback", "afterRawReadback", "restart", "loadedPackages", "validation", "exitSettings", "presentation")),
                "Restart acceptance evidence is incomplete")
        require(receipt["exitSettings"]["verified"] and receipt["presentation"]["status"] == "PASS", "Restart saved state/presentation acceptance failed")
        receipt["status"] = "PASS"
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.kill()
            receipt["exitCode"] = process.wait(timeout=10)
            receipt["interruptionAction"] = {"action": "kill own Popen child", "pid": process.pid}
        receipt["status"], receipt["error"] = "FAIL", f"{type(error).__name__}: {error}"
    finally:
        receipt["finishedUtc"] = base.utc()
        collect_evidence(receipt, out, case, manifest)
        try:
            receipt["after"] = snapshot(manifest_path, executable, layer_dir, manifest, case, candidate_receipt)
            receipt["immutableInputsUnchanged"] = receipt["before"] == receipt["after"]
            require(receipt["immutableInputsUnchanged"] and generated_identity(out) == receipt["generated"], "Immutable restart inputs changed during execution")
        except Exception as error:
            receipt["status"], receipt["identityError"] = "FAIL", f"{type(error).__name__}: {error}"
        receipt["outputs"] = {}
        try:
            artifacts = []
            for path in out.rglob("*"):
                if path.name != "receipt.json" and path.is_file():
                    artifacts.append(path)
                    require(len(artifacts) <= 512, "Restart artifact inventory exceeds512files")
            for path in sorted(artifacts):
                name = str(path.relative_to(out))
                try:
                    receipt["outputs"][name] = base.identity(path)
                except Exception as error:
                    receipt["status"] = "FAIL"
                    receipt.setdefault("outputUnavailable", {})[name] = f"{type(error).__name__}: {error}"
            require(not receipt.get("outputUnavailable"), "Restart output identity is unavailable")
        except Exception as error:
            receipt["status"], receipt["artifactError"] = "FAIL", f"{type(error).__name__}: {error}"
        base.save(out / "receipt.json", receipt)
    return 0 if receipt["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "exe", "out", "layer-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=("core", "sync"), required=True)
    parser.add_argument("--candidate-receipt", type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    try:
        prepare_fn = resume_prepared if args.launch and args.out.exists() else prepare
        receipt, manifest, case = prepare_fn(args.manifest.resolve(), args.case, args.exe.resolve(), args.out.resolve(),
                                            args.mode, args.layer_dir.resolve(), args.candidate_receipt)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    try:
        code = launch(receipt, manifest, case, args.manifest.resolve(), args.exe.resolve(), args.out.resolve(), args.mode,
                      args.layer_dir.resolve(), args.candidate_receipt) if args.launch else 0
    except (OSError, ValueError, KeyError) as error:
        receipt["status"], receipt["prelaunchError"] = "FAIL", f"{type(error).__name__}: {error}"
        base.save(args.out.resolve() / "receipt.json", receipt)
        code = 1
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out.resolve() / "receipt.json"), "gpuExecuted": receipt["gpuExecuted"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
