#!/usr/bin/env python3
"""Finite diagnostics-off final-source Dense comparison; preparation never launches.

The legacy Dense qualification/receipts remain unchanged. This adapter authenticates
the accepted PF113 native baseline and the final current-seams export separately.
CPU snapshots and exact state/pixels require a separate aggregate disposition.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
import zipfile


def repository():
    for path in Path(__file__).resolve().parents:
        if (path / "tools/pf_oracle/run_freeze_view_acceptance.py").is_file() and (path / "AGENTS.md").is_file():
            return path
    raise ValueError("Sole source repository unavailable")


ROOT = repository()
spec = importlib.util.spec_from_file_location("pf020_final_dense_view", ROOT / "tools/pf_oracle/run_freeze_view_acceptance.py")
view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)
dense = view.dense
require, save, identity, read_json = dense.require, dense.save, dense.identity, dense.read_json
SCHEMA = "pf020-final-source-dense-comparison/v2"
ACCEPTED_MASTER = "7d29c7e4d64d61dba05524d9e7f5711ffd915d90"
BASELINE_NATIVE = "a113e2bc1644fe5e7e9079b49ef67308f83eecff"
CURRENT_NATIVE = "569bdb118c709dac00dc6543570d6840c88dad12"
DELTA_SHA256 = "d061eaf9a1b7a5915643691680e2dff2f6fc9eee36737dd3cd14f5b2c0b2db16"
DELTA_BYTES = 85910
DELTA_PATHS = (
    "src/CMakeLists.txt",
    "src/common/rendering/vulkan/pipelines/vk_renderpass.cpp",
    "src/common/rendering/vulkan/shaders/vk_shader.cpp",
    "src/common/rendering/vulkan/shaders/vk_shadercache.cpp",
    "src/common/rendering/vulkan/textures/vk_pfviewdiagnostics.cpp",
    "src/common/rendering/vulkan/textures/vk_pfviewdiagnostics.h",
    "src/common/rendering/vulkan/vk_lightprober.cpp",
    "src/common/rendering/vulkan/vk_renderdevice.cpp",
    "src/d_main.cpp",
    "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp",
    "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.h",
    "src/rendering/hwrenderer/hw_entrypoint.cpp",
    "src/rendering/hwrenderer/scene/hw_drawinfo.cpp",
    "src/rendering/hwrenderer/scene/hw_sprites.cpp",
    "src/rendering/r_utility.cpp",
)
NATIVE_ROOTS = ("src/", "libraries/", "wadsrc/", "wadsrc_bm/", "wadsrc_lights/",
                "wadsrc_extra/", "wadsrc_widepix/", "cmake/", "tools/re2c/", "tools/lemon/",
                "tools/zipdir/", "tools/updaterevision/", "fm_banks/", "soundfont/")
PACKAGE_ROOTS = {"vkdoom.pk3": "wadsrc/static/", "brightmaps.pk3": "wadsrc_bm/static/",
                 "lights.pk3": "wadsrc_lights/static/", "game_support.pk3": "wadsrc_extra/static/",
                 "game_widescreen_gfx.pk3": "wadsrc_widepix/static/"}
QUIET_POLICY = {"minimumIntervals": 30, "maximumIntervals": 120, "secondsEach": 1,
                "lastIntervals": 10, "maxCpuPercent": 15.0,
                "basis": "GetSystemTimes prelaunch only; no claim about load during child"}
NORMAL = {"gl_ubershaders": "true", "gl_light_shadows": "1", "gl_levelmesh": "false"}
QUERIES = dense.QUERIES | NORMAL
ORDER = (("accepted-master", 0), ("final-current", 0),
         ("accepted-master", 1), ("final-current", 1),
         ("final-current", 2), ("accepted-master", 2),
         ("accepted-master", 3), ("final-current", 3),
         ("final-current", 4), ("accepted-master", 4),
         ("accepted-master", 5), ("final-current", 5))
TOOL_PINS = (
    "tools/pf_oracle/run_freeze_final_dense.py", "tools/pf_oracle/tests/test_freeze_final_dense.py",
    "tools/pf_oracle/run_freeze_dense_runtime.py", "tools/pf_oracle/tests/test_freeze_dense_runtime.py",
    "tools/pf_oracle/run_freeze_view_acceptance.py", "tools/pf_oracle/derive_freeze_view_baseline.py",
    "tools/pf_oracle/run_indexed_material_runtime.py", "docs/shadedoomvk/PF-020-FINAL-DENSE-PROTOCOL.md",
)
QUIET_INTERVALS, QUIET_FINAL_INTERVALS, QUIET_MAX_PERCENT = 30, 10, 15.0
QUIET_MAX_INTERVALS = 120


def runtime_tree(commit):
    return {name: {"mode": mode, "gitBlob": oid} for name, mode, oid in view.derive.tree_entries(ROOT, commit)
            if name.startswith(NATIVE_ROOTS) or name.endswith("CMakeLists.txt") or name.endswith(".gitattributes") or name == "vcpkg.json"}


def source_bridge(tool_head):
    baseline, accepted, current, live = [runtime_tree(c) for c in (BASELINE_NATIVE, ACCEPTED_MASTER, CURRENT_NATIVE, tool_head)]
    require(baseline == accepted, "Accepted master differs from authenticated native baseline runtime")
    require(current == live, "Final tool head adds or changes an unqualified runtime input")
    changed = sorted(name for name in set(accepted) | set(current) if accepted.get(name) != current.get(name))
    require(changed == list(DELTA_PATHS), "Complete final runtime delta path closure differs")
    raw = view.derive.git(ROOT, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--full-index", "--binary", "--unified=3",
                          ACCEPTED_MASTER, CURRENT_NATIVE, "--", *changed)
    require(len(raw) == DELTA_BYTES and hashlib.sha256(raw).hexdigest() == DELTA_SHA256,
            "Exact reviewed final runtime delta hunks differ")
    live_raw = {}
    frozen = ROOT / "build/pf020-native/pf020-view-source-07/current"
    for name, row in current.items():
        expected = view.safe_build(frozen / name).read_bytes()
        require(view.derive.git_blob_id(expected) == row["gitBlob"], "Frozen runtime source blob changed: " + name)
        actual = (ROOT / name).read_bytes()
        require(actual.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n"), "Live native input differs: " + name)
        live_raw[name] = {"sha256": view.sha(actual), "bytes": len(actual)}
    return {"baselineNativeHead": BASELINE_NATIVE, "acceptedMaster": ACCEPTED_MASTER, "currentNativeHead": CURRENT_NATIVE,
            "baselineMatchesAcceptedMaster": True, "liveMatchesCurrentRuntime": True,
            "baselineRuntimeFiles": len(accepted), "currentRuntimeFiles": len(current),
            "deltaSha256": DELTA_SHA256, "deltaBytes": len(raw), "liveNativeInputs": live_raw,
            "changed": {name: {"before": accepted.get(name), "after": current.get(name)} for name in changed}}


def text_attributes(commit, names):
    # Read committed attributes, without machine/global attribute authority.
    info = view.derive.git(ROOT, "rev-parse", "--git-path", "info/attributes").decode().strip()
    info_path = Path(info) if Path(info).is_absolute() else ROOT / info
    require(not info_path.exists(), "Local info/attributes would add uncommitted text policy")
    attrs = {}
    for begin in range(0, len(names), 256):
        chunk = names[begin:begin + 256]
        command = ["git", "-c", "core.attributesFile=NUL", "check-attr", "--source=" + commit, "-z", "--stdin", "text"]
        raw = subprocess.run(command, cwd=ROOT, input=b"\0".join(n.encode("utf-8") for n in chunk) + b"\0",
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30).stdout
        fields = raw.split(b"\0")
        require(fields[-1] == b"" and len(fields) == 3 * len(chunk) + 1, "Unexpected committed attribute output")
        for index, name in enumerate(chunk):
            path, attribute, value = fields[index * 3:index * 3 + 3]
            require(path.decode("utf-8") == name and attribute == b"text" and name not in attrs,
                    "Attribute path/order/identity differs")
            attrs[name] = value.decode("ascii")
    return attrs


def index_text_classification(expected):
    paths = list(PACKAGE_ROOTS.values())
    command = ["git", "-c", "core.attributesFile=NUL", "ls-files", "-s", "-z", "--", *paths]
    raw = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30).stdout
    actual = {}
    for record in raw.split(b"\0")[:-1]:
        metadata, name = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        name = name.decode("utf-8")
        require(stage == "0" and name not in actual, "Unmerged/duplicate package index input")
        actual[name] = {"mode": mode, "gitBlob": oid}
    require(actual == expected, "Git index package paths/modes/blobs differ from frozen source")
    command = ["git", "-c", "core.attributesFile=NUL", "ls-files", "--eol", "-z", "--", *paths]
    raw = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30).stdout
    result = {}
    for record in raw.split(b"\0")[:-1]:
        metadata, name = record.split(b"\t", 1)
        name = name.decode("utf-8")
        require(name in expected and name not in result, "Unexpected package EOL classification path")
        result[name] = metadata.decode("ascii").split()[0]
    require(set(result) == set(expected), "Git index EOL classification closure missing")
    return result


def package_member_projection(source, older, newer, attribute, index_eol):
    require(newer == source, "Final package member differs from authenticated Git source")
    if older == source:
        return "raw-identical"
    require(attribute in ("set", "auto"), "Non-text source cannot use a newline projection")
    require(attribute == "set" or (index_eol == "i/lf" and b"\0" not in source), "Auto binary source cannot use text projection")
    require(b"\n" in source and older == source.replace(b"\n", b"\r\n"),
            "Accepted member differs beyond its exact authenticated text newline projection")
    return "git-source-LF-to-CRLF"


def package_equivalence(baseline, current):
    require(set(PACKAGE_ROOTS) == set(dense.PACKAGES) and len(set(PACKAGE_ROOTS.values())) == 5,
            "Complete five package/source-root table required")
    trees = {commit: {n: {"mode": mode, "gitBlob": oid} for n, mode, oid in view.derive.tree_entries(ROOT, commit)}
             for commit in (BASELINE_NATIVE, CURRENT_NATIVE)}
    before_tree, after_tree = trees[BASELINE_NATIVE], trees[CURRENT_NATIVE]
    attr_files = {commit: {n: row for n, row in tree.items() if n.endswith(".gitattributes")}
                  for commit, tree in trees.items()}
    require(attr_files[BASELINE_NATIVE] == attr_files[CURRENT_NATIVE], "Committed package text policy differs")
    all_names = sorted(n for n in after_tree if any(n.startswith(prefix) for prefix in PACKAGE_ROOTS.values()))
    eol = index_text_classification({n: after_tree[n] for n in all_names})
    attrs = {commit: text_attributes(commit, all_names) for commit in trees}
    require(attrs[BASELINE_NATIVE] == attrs[CURRENT_NATIVE], "Source text attributes differ between variants")
    result = {"relation": "authenticated-source-text-newline-projection", "strictOneVariableComparison": False,
              "attributeSources": attr_files, "packages": {}, "memberCount": 0, "rawIdenticalMembers": 0,
              "projectedTextMembers": 0}
    source_root = Path(current["sourceDirectory"])
    for package, prefix in PACKAGE_ROOTS.items():
        expected = {n[len(prefix):]: row for n, row in after_tree.items() if n.startswith(prefix)}
        older_sources = {n[len(prefix):]: row for n, row in before_tree.items() if n.startswith(prefix)}
        require(expected and expected == older_sources, "Complete package source closure differs: " + package)
        require(len({n.casefold() for n in expected}) == len(expected), "Case-aliased package source")
        old_pin, new_pin = baseline["artifacts"][package], current["build"][package]
        require(old_pin["bytes"] <= 128 * 1024 * 1024 and new_pin["bytes"] <= 128 * 1024 * 1024, "Package byte cap exceeded")
        members, decoded = {}, 0
        with zipfile.ZipFile(old_pin["path"]) as old_zip, zipfile.ZipFile(new_pin["path"]) as new_zip:
            for archive in (old_zip, new_zip):
                names = archive.namelist()
                require(len(names) <= 10000 and len(names) == len(set(names)) and set(names) == set(expected)
                        and len({n.casefold() for n in names}) == len(names), "Missing/extra/duplicate/aliased package member")
            for name in sorted(expected):
                view.source_name(name)
                old_info, new_info = old_zip.getinfo(name), new_zip.getinfo(name)
                require(not old_info.is_dir() and not new_info.is_dir() and not (old_info.flag_bits | new_info.flag_bits) & 1
                        and max(old_info.file_size, new_info.file_size) <= 64 * 1024 * 1024, "Unsafe package member")
                decoded += old_info.file_size + new_info.file_size
                require(decoded <= 256 * 1024 * 1024, "Package decoded byte cap exceeded")
                source_name = prefix + name
                source = view.safe_build(source_root / source_name).read_bytes()
                require(expected[name]["mode"] in ("100644", "100755")
                        and view.derive.git_blob_id(source) == expected[name]["gitBlob"], "Unauthenticated package source")
                older, newer = old_zip.read(name), new_zip.read(name)
                relation = package_member_projection(source, older, newer, attrs[CURRENT_NATIVE][source_name], eol[source_name])
                members[name] = {"source": source_name, **expected[name], "textAttribute": attrs[CURRENT_NATIVE][source_name], "indexEol": eol[source_name],
                                 "sourceSha256": view.sha(source), "sourceBytes": len(source), "relation": relation,
                                 "baselineSha256": view.sha(older), "baselineBytes": len(older),
                                 "currentSha256": view.sha(newer), "currentBytes": len(newer)}
                result["memberCount"] += 1
                result["rawIdenticalMembers" if relation == "raw-identical" else "projectedTextMembers"] += 1
        result["packages"][package] = {"sourceRoot": prefix, "baselineRawArchive": old_pin, "currentRawArchive": new_pin,
                                       "memberCount": len(members), "members": members}
    result["rawMemberByteIdentical"] = result["projectedTextMembers"] == 0
    return result


def configuration(seed):
    original = dense.ini_sections(seed)
    require(dense.section_values(original, "GlobalSettings", {"gl_light_shadows": "1"}) == {"gl_light_shadows": "1"},
            "Pinned normal Dense shadow policy differs")
    sections = dense.ini_sections(dense.configuration(seed))
    rows = sections["GlobalSettings"]
    sections["GlobalSettings"] = [(k, v) for k, v in rows if k.lower() not in NORMAL] + list(NORMAL.items())
    return "\n\n".join("[" + section + "]\n" + "\n".join(k + "=" + v for k, v in entries)
                       for section, entries in sections.items()) + "\n"


def script(out):
    commands = ["show_messages false", "con_notifytime 0", "use_mouse false", "m_use_mouse 0", "unbindall",
                "vid_activeinbackground true", "vid_lowerinbackground false", "gl_levelmesh false", "lm_dynlights false",
                "vid_setsize 1904 1001", "wait 35", "vid_fps true", "stat rendertimes", "bench",
                "wait 350", "pause", "wait 60"]
    for _ in range(4): commands += ["bench", "wait 190"]
    commands += ["stat rendertimes", "vid_fps false", *QUERIES, "wait 35",
                 "screenshot " + dense.console_path(out / "scene.png"), "wait 35", "echo PF020_DENSE_COMPLETE", "quit"]
    return "; ".join(commands) + "\n"


def command(exe, inputs, out):
    return dense.execution_command(exe, inputs["iwad"]["path"], inputs["fixture"]["path"], out)


def qualify(paths):
    tool = view.tool_source_identity()
    baseline_path = ROOT / dense.QUALIFIED["candidate"][0]
    baseline_data = read_json(baseline_path)
    require(baseline_data.get("source_head") == BASELINE_NATIVE, "Unexpected accepted native head")
    baseline_exe = next(Path(r["path"]) for r in baseline_data["artifacts"] if Path(r["path"]).name == "vkdoom.exe")
    baseline, _ = dense.build_identity("candidate", baseline_path, baseline_exe)
    current = view.build_identity(Path(paths["currentCandidate"]), "current", Path(paths["derivation"]))
    require(current["sourceHead"] == CURRENT_NATIVE, "Wrong final runtime head; an original-seams build cannot be timed as current")
    current_build = {name: {**pin, "buildCounterpart": identity(Path(r["source"]))}
                     for name, pin in current["build"].items()
                     for r in read_json(Path(paths["currentCandidate"]), 32 * 1024 * 1024)["artifacts"] if Path(r["path"]).name == name}
    builds = {"accepted-master": baseline, "final-current": {"artifacts": current_build, "sourceExportAttestation": current}}
    inputs = {"iwad": dense.checked(paths["iwad"], dense.IWAD_SHA),
              "fixture": dense.checked(paths["fixture"], dense.FIXTURE_SHA), "seed": dense.checked(paths["seed"], dense.SEED_SHA)}
    require(len(dense.wad_members(paths["iwad"], b"IWAD")) == 2928, "Wrong isolated stock IWAD")
    fixture = dense.fixture_evidence(paths["fixture"])
    device = view.read_json(Path(paths["expectedDevice"]))
    require(set(device) == {"name", "type", "apiVersion", "encodedDriver"} and device["name"] == "NVIDIA GeForce GTX 1650 SUPER"
            and device["type"] == "discrete gpu" and all(isinstance(v, str) and 0 < len(v) <= 128 for v in device.values()),
            "Exact native device preregistration missing")
    return {"toolSource": tool, "builds": builds, "inputs": inputs, "fixtureContract": fixture,
            "sourceBridge": source_bridge(tool["commit"]), "expectedDevice": {"fields": device, "file": identity(paths["expectedDevice"])},
            "tools": {name: identity(ROOT / name) for name in TOOL_PINS}, "stops": dense.stop_identity(),
            "packageEquivalence": package_equivalence(baseline, current)}


def generated_inputs(child):
    out = Path(child["directory"])
    return {name: identity(out / name) for name in ("configuration-input.ini", "execute.cfg")}


def output_inventory(out):
    out = view.safe_build(out)
    pending, found = [out], {}
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda e: e.name):
            path = view.safe_build(Path(entry.path))
            require(len(found) < 128, "Own output closure exceeds bound")
            name = path.relative_to(out).as_posix()
            if entry.is_dir(follow_symlinks=False):
                found[name] = {"kind": "directory"}; pending.append(path)
            else:
                require(entry.is_file(follow_symlinks=False) and path.stat().st_size <= 32 * 1024 * 1024,
                        "Own output is not a bounded regular file")
                found[name] = identity(path)
    return found


def prepare(paths, out):
    out = view.safe_build(out, fresh=True)
    before = qualify(paths)
    # Exact package/source projection qualification is completed before launch.
    require("packageEquivalence" in before, "Package source equivalence not yet qualified")
    out.mkdir(parents=True)
    receipt = {"schema": SCHEMA, "status": "PREPARING", "cwd": str(ROOT), "output": str(out), "paths": paths,
               "before": before, "children": [], "createdUtc": dense.utc(), "rendererStarted": False,
               "gpuExecuted": False, "performanceAccepted": False, "freezeAccepted": False}
    save(out / "receipt.json", receipt)
    config = configuration(Path(paths["seed"]).read_text())
    for index, (variant, pair) in enumerate(ORDER):
        child_out = out / f"{index + 1:02d}-{variant}-{'warmup' if pair == 0 else 'pair-' + str(pair)}"
        child_out.mkdir(); (child_out / "work").mkdir(); (child_out / "save").mkdir()
        for name in ("configuration-input.ini", "fixture-live.ini"):
            (child_out / name).write_text(config, encoding="utf-8", newline="\n")
        (child_out / "execute.cfg").write_text(script(child_out), encoding="utf-8", newline="\n")
        exe = before["builds"][variant]["artifacts"]["vkdoom.exe"]["path"]
        child = {"ordinal": index, "variant": variant, "pair": pair, "scored": pair != 0, "directory": str(child_out),
                 "argv": command(exe, before["inputs"], child_out), "status": "PREPARED", "rendererStarted": False}
        child["generated"] = generated_inputs(child)
        child["liveConfigBefore"] = identity(child_out / "fixture-live.ini")
        child["preparedInventory"] = output_inventory(child_out)
        receipt["children"].append(child); save(out / "receipt.json", receipt)
    receipt.update(status="PREPARED", watchdogSeconds=dense.WATCHDOG_SECONDS,
                   quietPolicy=QUIET_POLICY,
                   normalPolicy=NORMAL, clock="ordinary-adaptive", diagnostics=False, validation=False,
                   retainedSnapshotsPerScoredChild=4, rawBlocks=60, scoredSnapshots=40,
                   decodedComponentTolerance=0, agentWarmupPictureReviewRequired=True,
                   cachePolicy="Ordinary shared application/driver caches untouched; no cold-cache claim",
                   limits=dense.LIMITS + ["Text package newline projections require exact source authentication; no arbitrary binary normalization.",
                                         "Baseline is accepted master; current contains precisely the reviewed default-off observer additions."])
    save(out / "receipt.json", receipt)
    return receipt


def system_times():
    require(os.name == "nt", "Windows quiet-host observation requires the approved host")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemTimes.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
    kernel.GetSystemTimes.restype = wintypes.BOOL
    idle, kernel_time, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not kernel.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel_time), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    value = lambda x: (x.dwHighDateTime << 32) | x.dwLowDateTime
    return value(idle), value(kernel_time) + value(user)


class QuietObservationError(ValueError):
    def __init__(self, error, observation):
        super().__init__(str(error))
        self.observation = observation
        self.winerror = getattr(error, "winerror", None)


def quiet_host(*, sample=system_times, wait=time.sleep):
    initial = None; result = []; raw = []; stage = "initial-sample"
    def observation(accepted):
        return {"cpuPercent": result, "rawIntervals": raw, "initialSystemTimes": initial,
                "lastWindowMaximum": max(result[-QUIET_FINAL_INTERVALS:]) if result else None, "accepted": accepted,
                "observedIntervals": len(result), "minimumIntervals": QUIET_INTERVALS, "maximumIntervals": QUIET_MAX_INTERVALS,
                "settlingExtended": len(raw) > QUIET_INTERVALS,
                "acceptedWindowIndices": [len(result) - QUIET_FINAL_INTERVALS, len(result) - 1] if accepted else None,
                "observedUtc": dense.utc(), "basis": "Prelaunch one-second GetSystemTimes intervals; not a continuous in-run CPU measurement"}
    try:
        prior = sample(); initial = list(prior)
        for index in range(QUIET_MAX_INTERVALS):
            stage = "wait"; wait(1)
            stage = "interval-sample"; current = sample()
            stage = "interval-validation"
            idle, total = current[0] - prior[0], current[1] - prior[1]
            raw.append({"index": index, "idleDelta": idle, "totalDelta": total})
            require(total > 0 and 0 <= idle <= total, "System CPU interval invalid")
            result.append(100 * (total - idle) / total); prior = current
            if len(result) >= QUIET_INTERVALS and max(result[-QUIET_FINAL_INTERVALS:]) < QUIET_MAX_PERCENT:
                break
    except BaseException as error:
        rejected = observation(False)
        rejected["observationError"] = {"stage": stage, "type": type(error).__name__, "message": str(error),
                                        "winerror": getattr(error, "winerror", None)}
        raise QuietObservationError(error, rejected) from error
    accepted = len(result) >= QUIET_INTERVALS and max(result[-QUIET_FINAL_INTERVALS:]) < QUIET_MAX_PERCENT
    return observation(accepted)


def run_child(child, receipt, env, *, popen=subprocess.Popen, clock=time.monotonic, token_query=None):
    out = Path(child["directory"])
    query = view.windows_token_info if token_query is None else token_query
    process = None
    with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
        process = popen(child["argv"], cwd=out / "work", env=env, stdout=stdout, stderr=stderr, shell=False)
        try:
            child.update(status="RUNNING", pid=process.pid, rendererStarted=True, startedUtc=dense.utc())
            receipt["rendererStarted"] = True
            try: child["nativeToken"] = query(process.pid)
            except BaseException as error:
                child["nativeTokenQueryError"] = {"error": repr(error), "winerror": getattr(error, "winerror", None)}
                raise
            view.require_medium_token(child["nativeToken"], "Own normal Dense child", process.pid)
            save(Path(receipt["output"]) / "receipt.json", receipt)
            started = clock()
            while process.poll() is None:
                require(clock() - started < dense.WATCHDOG_SECONDS, "90-second owned normal Dense watchdog expired")
                require(sum((out / n).stat().st_size for n in ("stdout.log", "stderr.log")) <= 16 * 1024 * 1024,
                        "Normal Dense log cap exceeded")
                try: process.wait(timeout=.25)
                except subprocess.TimeoutExpired: pass
            child["exit"] = process.wait(timeout=10)
            child["durationSeconds"] = clock() - started
            require(child["exit"] == 0, "Normal Dense child did not exit normally")
        finally:
            if process.poll() is None:
                process.kill(); child["exit"] = process.wait(timeout=10)
                child["cleanupAction"] = "Killed and waited for only the own Popen child"


def adjudicate(child, before):
    out = Path(child["directory"])
    child["before"] = {"build": before["builds"][child["variant"]], "inputs": before["inputs"]}
    dense.adjudicate(out, child)
    text = dense.strip_colours((out / "stdout.log").read_text(errors="replace"))
    require(not re.search(r"PF020_(?:VIEW|VK|VULKAN)|PF11[03]_(?:DIAG|BEGIN|DRAW)|CFX_.*(?:ENABLED|ACTIVATED)", text),
            "Diagnostic observer/clock/cache activation in a normal timing child")
    for key, wanted in NORMAL.items():
        actual = re.findall(r'(?m)^"' + re.escape(key) + r'" is "([^"]*)" \(default: "[^"]*"\)\s*$', text)
        require(actual == [wanted], "Normal startup policy query missing/duplicated/changed: " + key)
        child["actualRuntimeSettings"][key] = actual[0]
    sections = dense.ini_sections((out / "fixture-live.ini").read_text())
    for key, wanted in NORMAL.items():
        values = [v.lower() for rows in sections.values() for k, v in rows if k.lower() == key]
        require(values == ([wanted] if key == "gl_light_shadows" else []), "Normal-exit policy/zero-flag setting differs: " + key)
    require(child["nativeDevice"] == before["expectedDevice"]["fields"], "Actual normal timing device differs")
    child["outputs"] = output_inventory(out)
    require(child["outputs"] == output_inventory(out), "Normal timing output changed during closure")
    child.update(status="CHILD_VALIDATED", gpuExecuted=True, completedUtc=dense.utc())


def paired(children):
    result = []
    require([(c["variant"], c["pair"]) for c in children] == list(ORDER)
            and all(c["status"] == "CHILD_VALIDATED" for c in children), "Incomplete/changed finite normal campaign")
    for pair in range(1, 6):
        a = next(c for c in children if c["pair"] == pair and c["variant"] == "accepted-master")
        b = next(c for c in children if c["pair"] == pair and c["variant"] == "final-current")
        require(a["nativeDevice"] == b["nativeDevice"] and a["actualRuntimeSettings"] == b["actualRuntimeSettings"],
                "Paired normal state/device differs")
        for child in (a, b):
            require(child["cpuBenchmarks"]["retainedIndices"] == [1, 2, 3, 4]
                    and len(child["cpuBenchmarks"]["snapshots"]) == 5, "Normal scoring closure changed")
            require(all(s["counts"] == dense.COUNTS and s["camera"] == [-1850, 0, 41, 0, 0]
                        for s in child["cpuBenchmarks"]["snapshots"]), "Paired normal camera/count state differs")
        pixels_a, image_a = dense.decode_png(Path(a["directory"]) / "scene.png")
        pixels_b, image_b = dense.decode_png(Path(b["directory"]) / "scene.png")
        require(pixels_a == pixels_b, "Exact final-source normal Dense RGB differs")
        metrics = {}
        for metric in ("spriteSetup", "allIncludingFinish"):
            av = [s["cpuMilliseconds"][metric] for s in a["cpuBenchmarks"]["snapshots"][1:]]
            bv = [s["cpuMilliseconds"][metric] for s in b["cpuBenchmarks"]["snapshots"][1:]]
            am, bm = statistics.median(av), statistics.median(bv)
            require(am > 0, "Zero CPU median cannot define a percentage")
            metrics[metric] = {"baselineSnapshotsMs": av, "currentSnapshotsMs": bv,
                               "baselineMedianMs": am, "currentMedianMs": bm, "pairedDifferencePercent": (bm - am) / am * 100}
        result.append({"pair": pair, "status": "PAIRED_EXACT_MATCH", "decodedComponentTolerance": 0,
                       "pixelsCompared": dense.EXTENT[0] * dense.EXTENT[1], "mismatchedPixels": 0,
                       "rgbSha256": image_a["decodedRgbSha256"], "cpuSnapshots": metrics,
                       "gpuTimestampClaimed": False, "causeClaimed": False, "performanceAccepted": False})
    return result


def warmup_picture_review(receipt):
    out = view.safe_build(receipt["output"])
    path = view.safe_build(out / "warmup-image-review.json")
    review = read_json(path, 64 * 1024)
    require(review.get("schema") == "pf020-final-dense-warmup-agent-review/v1" and review.get("status") == "PASS"
            and review.get("inspector") == "root-agent" and review.get("humanApprovalClaimed") is False
            and review.get("toolHead") == receipt["before"]["toolSource"]["commit"]
            and review.get("queryMessagesAbsent") is True and review.get("benchmarkOverlayAbsent") is True
            and review.get("healthyFixtureVisible") is True, "Actual agent warmup picture review absent or invalid")
    images = []
    for child in receipt["children"][:2]:
        png = view.safe_build(Path(child["directory"]) / "scene.png")
        _, decoded = dense.decode_png(png)
        images.append({"variant": child["variant"], "png": identity(png), "decodedRgbSha256": decoded["decodedRgbSha256"]})
    require(review.get("images") == images, "Warmup picture review refers to different actual files/pixels")
    return {"record": identity(path), "images": images, "humanApprovalClaimed": False}


def validate_prepared_child(child, receipt, index, config):
    out = view.safe_build(receipt["output"])
    child_out = view.safe_build(out / f"{index + 1:02d}-{child['variant']}-{'warmup' if child['pair'] == 0 else 'pair-' + str(child['pair'])}")
    exe = receipt["before"]["builds"][child["variant"]]["artifacts"]["vkdoom.exe"]["path"]
    require(child.get("ordinal") == index and child.get("scored") is (child["pair"] != 0)
            and child.get("status") == "PREPARED" and child.get("rendererStarted") is False
            and child.get("directory") == str(child_out) and child.get("argv") == command(exe, receipt["before"]["inputs"], child_out)
            and (child_out / "execute.cfg").read_text() == script(child_out)
            and (child_out / "configuration-input.ini").read_text() == config
            and (child_out / "fixture-live.ini").read_text() == config
            and generated_inputs(child) == child["generated"]
            and identity(child_out / "fixture-live.ini") == child["liveConfigBefore"]
            and output_inventory(child_out) == child["preparedInventory"], "Prepared normal child command/config/source differs")


def launch(receipt, *, popen=subprocess.Popen, clock=time.monotonic, token_query=None, quiet=quiet_host, scored=False):
    require(receipt.get("schema") == SCHEMA
            and receipt.get("status") == ("WARMUPS_READY_FOR_AGENT_PICTURE_REVIEW" if scored else "PREPARED")
            and receipt.get("rendererStarted") is scored,
            "Only unused preregistered warmup/scored phase can launch; no retry")
    out = view.safe_build(receipt["output"])
    require(receipt.get("cwd") == str(ROOT) and receipt.get("normalPolicy") == NORMAL
            and receipt.get("clock") == "ordinary-adaptive" and receipt.get("diagnostics") is False
            and receipt.get("validation") is False and receipt.get("watchdogSeconds") == dense.WATCHDOG_SECONDS
            and receipt.get("retainedSnapshotsPerScoredChild") == 4 and receipt.get("rawBlocks") == 60
            and receipt.get("scoredSnapshots") == 40 and receipt.get("decodedComponentTolerance") == 0
            and receipt.get("quietPolicy") == QUIET_POLICY
            and receipt.get("agentWarmupPictureReviewRequired") is True
            and [(c.get("variant"), c.get("pair")) for c in receipt["children"]] == list(ORDER),
            "Finite normal campaign order/settings/scoring changed")
    require(qualify(receipt["paths"]) == receipt["before"], "Final prelaunch source/build/input/STOP differs")
    config = configuration(Path(receipt["paths"]["seed"]).read_text())
    for index, child in enumerate(receipt["children"]):
        child_out = view.safe_build(out / f"{index + 1:02d}-{child['variant']}-{'warmup' if child['pair'] == 0 else 'pair-' + str(child['pair'])}")
        exe = receipt["before"]["builds"][child["variant"]]["artifacts"]["vkdoom.exe"]["path"]
        if scored and index < 2:
            require(child.get("status") == "CHILD_VALIDATED" and child.get("rendererStarted") is True
                    and child.get("directory") == str(child_out) and output_inventory(child_out) == child["outputs"],
                    "Completed warmup output/state changed before scoring")
            continue
        validate_prepared_child(child, receipt, index, config)
    if scored: receipt["agentWarmupPictureReview"] = warmup_picture_review(receipt)
    receipt.update(status="RUNNING", startedUtc=dense.utc())
    try:
        query = view.windows_token_info if token_query is None else token_query
        receipt["coordinatorToken"] = query()
        view.require_medium_token(receipt["coordinatorToken"], "Final normal Dense coordinator")
        save(out / "receipt.json", receipt)
        for child in receipt["children"][2:] if scored else receipt["children"][:2]:
            require(qualify(receipt["paths"]) == receipt["before"], "Normal source/build/input/STOP changed before child")
            child["hostBefore"] = dense.health(dense.utc())
            try: child["quietHost"] = quiet()
            except QuietObservationError as error:
                child["quietHost"] = error.observation
                save(out / "receipt.json", receipt)
                raise
            save(out / "receipt.json", receipt)
            require(child["quietHost"]["accepted"] is True, "Prelaunch CPU quiet window failed; no timing retry or exclusion")
            require(qualify(receipt["paths"]) == receipt["before"], "Normal source/build/input/STOP changed during quiet preparation")
            validate_prepared_child(child, receipt, child["ordinal"], config)
            env, removed = dense.clean_environment(os.environ)
            child["removedEnvironmentKeys"] = removed
            run_child(child, receipt, env, popen=popen, clock=clock, token_query=query)
            child["hostAfter"] = dense.health(child["startedUtc"])
            require(qualify(receipt["paths"]) == receipt["before"], "Normal source/build/input/STOP changed during child")
            require(generated_inputs(child) == child["generated"], "Immutable normal input changed during child")
            adjudicate(child, receipt["before"])
            receipt["gpuExecuted"] = True
            save(out / "receipt.json", receipt)
        if scored:
            receipt["comparisons"] = paired(receipt["children"])
            receipt.update(status="PASS_EXACT_EQUIVALENCE_WITH_CPU_SNAPSHOTS", performanceAccepted=False, freezeAccepted=False)
        else:
            receipt.update(status="WARMUPS_READY_FOR_AGENT_PICTURE_REVIEW", performanceAccepted=False, freezeAccepted=False)
    except BaseException as error:
        receipt.update(status="FAIL", error=f"{type(error).__name__}: {error}", winerror=getattr(error, "winerror", None))
    finally:
        receipt["finishedUtc"] = dense.utc()
        try:
            receipt["after"] = qualify(receipt["paths"])
            require(receipt["after"] == receipt["before"], "Final normal source/build/input/STOP changed")
        except BaseException as error: receipt.update(status="FAIL", identityError=repr(error))
        save(out / "receipt.json", receipt)
    return 0 if receipt["status"] in ("PASS_EXACT_EQUIVALENCE_WITH_CPU_SNAPSHOTS", "WARMUPS_READY_FOR_AGENT_PICTURE_REVIEW") else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-candidate", type=Path)
    parser.add_argument("--derivation", type=Path)
    parser.add_argument("--expected-device", type=Path)
    parser.add_argument("--iwad", type=Path, default=dense.IWAD)
    parser.add_argument("--fixture", type=Path, default=dense.FIXTURE)
    parser.add_argument("--config-seed", type=Path, default=dense.SEED)
    parser.add_argument("--out", type=Path, required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--launch", action="store_true", help="Run only the two unscored warmups")
    actions.add_argument("--launch-scored", action="store_true", help="Run the fixed ten scored children after actual agent picture review")
    args = parser.parse_args(argv)
    out = view.safe_build(args.out, fresh=not (args.launch or args.launch_scored))
    try:
        if args.launch or args.launch_scored: return launch(read_json(out / "receipt.json", 64 * 1024 * 1024), scored=args.launch_scored)
        require(all((args.current_candidate, args.derivation, args.expected_device)), "Preparation needs exact current build/source/device inputs")
        paths = {"currentCandidate": str(view.safe_build(args.current_candidate)), "derivation": str(view.safe_build(args.derivation)),
                 "expectedDevice": str(view.safe_build(args.expected_device)), "iwad": str(dense.absolute(args.iwad)),
                 "fixture": str(dense.absolute(args.fixture)), "seed": str(dense.absolute(args.config_seed))}
        receipt = prepare(paths, out)
        print(json.dumps({"status": receipt["status"], "rendererStarted": False, "receipt": str(out / "receipt.json")}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        if out.is_dir():
            partial = read_json(out / "receipt.json", 64 * 1024 * 1024) if (out / "receipt.json").exists() else {"schema": SCHEMA, "output": str(out)}
            partial.update(status="FAIL", error=f"{type(error).__name__}: {error}", freezeAccepted=False, performanceAccepted=False)
            save(out / "receipt.json", partial)
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
