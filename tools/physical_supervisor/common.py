"""Immutable records, packet validation and a shared durable spawn/STOP gate."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid


class Stop(RuntimeError):
    pass


ENV_KEYS = ("PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
            "PROGRAMDATA", "HOMEDRIVE", "HOMEPATH", "COMSPEC", "PATHEXT", "SystemDrive", "SYSTEMDRIVE",
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "DOOMWADDIR", "DOOMWADPATH",
            "VK_DRIVER_FILES", "VK_ICD_FILENAMES", "VK_INSTANCE_LAYERS", "VK_LAYER_PATH", "VK_ADD_LAYER_PATH",
            "VK_LOADER_DRIVERS_SELECT", "VK_LOADER_DRIVERS_DISABLE", "VK_LOADER_LAYERS_ENABLE", "VK_LOADER_LAYERS_DISABLE",
            "VK_LOADER_LAYERS_ALLOW", "VK_LOADER_DEBUG", "SDL_VIDEODRIVER", "DISPLAY", "WAYLAND_DISPLAY",
            "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "MESA_SHADER_CACHE_DISABLE", "MESA_SHADER_CACHE_DIR",
            "MESA_LOADER_DRIVER_OVERRIDE", "LP_NUM_THREADS", "OMP_NUM_THREADS", "CFX_TRACE_FILE", "CFX_RUN_ID",
            "CFX_RESOURCE_TRACE", "CFX_WITNESS_DIR")


def environment_policy(extra_keys=()):
    # Windows environment keys are case-insensitive. Preserve one canonical
    # uppercase spelling and explicit null for absent reviewed controls.
    ambient = {key.upper(): value for key, value in os.environ.items()}
    keys = {key.upper() for key in (*ENV_KEYS, *extra_keys)} | {key for key in ambient if key.startswith(("VK_", "SDL_", "MESA_", "CFX_", "LD_", "DYLD_"))}
    return {key: ambient.get(key) for key in sorted(keys)}


def sealed_environment(packet):
    require(environment_policy(packet.get("environment_extra_keys", ())) == packet["environment_policy"], "Reviewed renderer/loader environment changed")
    return {key: value for key, value in packet["environment_policy"].items() if value is not None}


REGISTRY_KEYS = ["SOFTWARE\\Khronos\\Vulkan\\" + name for name in ("Drivers", "ImplicitLayers", "ExplicitLayers")]
DISPLAY_CLASS = "SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}"
CONTROL_VIDEO = "SYSTEM\\CurrentControlSet\\Control\\Video"


def read_registry_policy(specifications):
    """Native64 read-only complete value snapshots, including explicit absence."""
    if os.name != "nt":
        require(not specifications, "Native Windows registry read required")
        return []
    import winreg
    result = []
    for specification in specifications:
        hive, key = specification["hive"], specification["key"]
        require(hive in ("HKLM", "HKCU"), "Unsupported Vulkan registry hive")
        root = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER
        row = {"hive": hive, "key": key, "present": False, "values": []}
        try:
            handle = winreg.OpenKey(root, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        except FileNotFoundError:
            result.append(row)
            continue
        with handle:
            row["present"] = True
            count = winreg.QueryInfoKey(handle)[1]
            for index in range(count):
                name, value, kind = winreg.EnumValue(handle, index)
                if isinstance(value, bytes):
                    value = {"binary_hex": value.hex()}
                row["values"].append({"name": name, "type": kind, "value": value})
            row["values"].sort(key=lambda value: value["name"].casefold())
        result.append(row)
    return sorted(result, key=lambda row: (row["hive"], row["key"].casefold()))


def read_registry_enumeration_policy(specifications):
    if os.name != "nt":
        require(not specifications, "Native Windows registry enumeration required")
        return []
    import winreg
    rows=[]
    for specification in specifications:
        hive,key=specification["hive"],specification["key"]
        require(hive in ("HKLM","HKCU"),"Unsupported registry enumeration hive")
        root=winreg.HKEY_LOCAL_MACHINE if hive=="HKLM" else winreg.HKEY_CURRENT_USER
        row={"hive":hive,"key":key,"present":False,"subkeys":[]}
        try:
            handle=winreg.OpenKey(root,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY)
        except FileNotFoundError:
            rows.append(row)
            continue
        with handle:
            row["present"]=True
            count=winreg.QueryInfoKey(handle)[0]
            row["subkeys"]=sorted((winreg.EnumKey(handle,index) for index in range(count)),key=str.casefold)
        rows.append(row)
    return sorted(rows,key=lambda row:(row["hive"],row["key"].casefold()))


def verify_registry(packet):
    expected = packet["registry_policy"]
    require(read_registry_policy(expected) == expected, "Vulkan driver/layer registry policy changed")
    enumeration=packet.get("registry_enumeration_policy",[])
    require(read_registry_enumeration_policy(enumeration)==enumeration,"Vulkan device registry key enumeration changed")


def verify_oracle_python_pins(packet):
    pins={normalized(row["path"]) for row in packet["files"]}
    roots=[Path(row["path"]).resolve(strict=True) for row in packet["runtime_roots"]]
    for relative in ("tools/renderer_oracle","tools/pf_oracle"):
        directory=Path(packet["oracle_source_root"])/relative
        require(directory.is_dir(),"Frozen oracle Python dependency package missing")
        require(any(directory.resolve().is_relative_to(root) for root in roots),"Frozen oracle import root is not closed/pinned")
        require(all(normalized(path) in pins for path in directory.rglob("*.py")),"Frozen oracle Python dependency is not pinned")
    decoder=Path(packet["oracle_source_root"])/"tools/pf_oracle/run_freeze_dense_runtime.py"
    require(normalized(decoder) in pins,"Frozen dynamic PNG decoder is not pinned")


def require(condition, message):
    if not condition:
        raise Stop(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def read_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    with open_read(path) as stream:
        raw=stream.read()
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Stop("Nonfinite JSON")))


def open_read(path):
    """Transient read compatibility, never an immutable-input lock or retry."""
    if os.name=="nt":
        # windows imports common; keep the native file adapter lazy.
        from .windows import open_shared_read
        return open_shared_read(path)
    return Path(path).open("rb")


def digest(path):
    with open_read(path) as stream:
        return stream_digest(stream)


def stream_digest(stream):
    hasher = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        hasher.update(chunk)
    return hasher.hexdigest()


def normalized(path):
    return os.path.normcase(str(Path(path).resolve(strict=True)))


def linklike(path):
    path = Path(path)
    # Python3.10 lacks Path.is_junction. NTFS reparse points include junctions
    # and symlinks, and are never accepted in a closed runtime inventory.
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def pin(path):
    original = Path(path)
    for part in [original, *original.parents]:
        require(not linklike(part), "Pinned path/ancestor is a link/junction")
    path = original.resolve(strict=True)
    require(path.is_file() and not linklike(path), "Pin is not a regular file")
    return {"path": str(path), "sha256": digest(path), "size": path.stat().st_size}


def verify_pin(row):
    require(type(row.get("size")) is int and row["size"] >= 0, "Invalid pin size")
    require(re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")), "Invalid pin hash")
    require(Path(row["path"]).is_absolute(), "Pins must use absolute paths")
    actual = pin(row["path"])
    require(actual["size"] == row["size"] and actual["sha256"] == row["sha256"], "Pinned file changed: " + row["path"])
    return actual


def exclusive(path, value, *, raw=False):
    """Publish complete bytes atomically without replacing an existing receipt.

    A sibling temporary file is flushed before its no-overwrite atomic
    publication. A crashed writer can leave pending evidence, never a partly
    readable final coordination file. Windows rename refuses existing targets;
    POSIX uses hard-link publication because rename there would overwrite.
    """
    path = Path(path)
    pending=path.with_name(".pending-"+uuid.uuid4().hex)
    with pending.open("xb") as stream:
        stream.write(value if raw else canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    if os.name=="nt":os.rename(pending,path)
    else:
        os.link(pending,path)
        try:pending.unlink()
        except OSError:
            pass  # Final complete receipt is published; retain pending evidence.


class Journal:
    """Exclusive numbered hash-chain entries; partial/crashed entries cannot pass audit."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.sequence = 0
        self.previous = "0" * 64

    def append(self, kind, value):
        item = {"sequence": self.sequence, "previous_sha256": self.previous,
                "utc": utc(), "kind": kind, "value": value}
        data = canonical(item)
        exclusive(self.root / f"{self.sequence:06d}-{kind}.json", data, raw=True)
        self.previous = hashlib.sha256(data).hexdigest()
        self.sequence += 1
        return item

    @staticmethod
    def audit(root):
        previous = "0" * 64
        files = sorted(Path(root).glob("*.json"))
        require(files, "Missing journal")
        for index, path in enumerate(files):
            row = read_json(path)
            require(row["sequence"] == index and row["previous_sha256"] == previous, "Journal chain gap/change")
            require(path.name.startswith(f"{index:06d}-"), "Journal name mismatch")
            previous = digest(path)
        return previous


INTEGRITY_POLICY={"timeout_seconds":10,"start_freshness_seconds":10,
                  "boundary_finish_freshness_seconds":.5,"gate_busy_seconds":1,
                  "heartbeat_period_seconds":.5,"heartbeat_freshness_seconds":2,
                  "owned_exit_settle_milliseconds":50,
                  "owned_exit_settle_operation":"QueryFullProcessImageNameW","owned_exit_settle_winerror":5,
                  "filesystem":"local-fixed-NTFS","namespace_change":"terminal-stop"}


class Gate:
    """All launchers serialize STOP, registration and resume with this OS lock.

    HELD.json is retained forever; a release refers only to one approved packet.
    STOP files are append-only. A failed write propagates and forbids launch.
    """
    def __init__(self, root, packet_sha256):
        self.root = Path(root).resolve(strict=True)
        self.packet_sha256 = packet_sha256
        self.lock_path = self.root / "gate.lock"
        self.lock = None

    def acquire(self, timeout=10):
        require(self.lock is None or self.lock.closed, "Gate already acquired")
        self.lock = self.lock_path.open("a+b")
        self.lock.seek(0)
        if os.name == "nt":
            import msvcrt
            until = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= until:
                        self.lock.close()
                        return False
                    time.sleep(.01)
        else:
            import fcntl
            until = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= until:
                        self.lock.close()
                        return False
                    time.sleep(.01)
        return True

    def __enter__(self):
        require(self.acquire(), "Shared gate lock timeout")
        return self

    def __exit__(self, *args):
        if os.name == "nt":
            import msvcrt
            self.lock.seek(0)
            msvcrt.locking(self.lock.fileno(), msvcrt.LK_UNLCK, 1)
        self.lock.close()

    def check(self):
        require(self.lock is not None and not self.lock.closed, "Spawn gate is not locked")
        require(read_json(self.root / "HELD.json")["status"] == "HELD", "Missing/modified initial STOP")
        require(not list(self.root.glob("STOP-*.json")), "Durable STOP is active")
        release = read_json(self.root / ("release-" + self.packet_sha256 + ".json"))
        require(release["packet_sha256"] == self.packet_sha256, "Missing exact packet release")
        future(release["expires_utc"])

    def stop(self, reason):
        require(self.lock is not None and not self.lock.closed, "STOP publication gate is not locked")
        exclusive(self.root / ("STOP-" + uuid.uuid4().hex + ".json"),
                  {"status": "STOP", "packet_sha256": self.packet_sha256, "utc": utc(), "reason": str(reason)})


def future(text):
    value = dt.datetime.fromisoformat(text)
    require(value.tzinfo is not None, "Timestamp requires timezone")
    require(value > dt.datetime.now(dt.timezone.utc), "Expired packet/approval")


def validate_packet(packet, *, check_files=True):
    require(packet["schema"] == "physical-supervisor/packet-v1", "Unsupported packet")
    require(canonical(packet["integrity_policy"])==canonical(INTEGRITY_POLICY),"Missing/changed prospective integrity policy")
    require(re.fullmatch(r"[A-Za-z0-9_-]{8,100}", packet["experiment_id"]), "Invalid experiment ID")
    require(packet["kind"] == "diagnostic", "Campaign launch is not qualified by this diagnostic supervisor version")
    require(re.fullmatch(r"[0-9a-f]{40}", packet["source"]["commit"]) and
            re.fullmatch(r"[0-9a-f]{40}", packet["source"]["tree"]), "Missing source identity")
    require(packet["automatic_retries"] == 0, "Retries prohibited")
    host=packet["host_identity"]
    require(set(host)=={"schema","native_pointer_bits","os_major","os_minor","os_build","os_platform_id",
                        "service_pack","boot_time_100ns"} and host["schema"]=="physical-supervisor/host-v1",
            "Missing native OS/boot identity")
    require(all(type(host[key]) is int for key in ("native_pointer_bits","os_major","os_minor","os_build","os_platform_id","boot_time_100ns"))
            and host["native_pointer_bits"]==64 and host["os_major"]>0 and host["os_minor"]>=0 and host["os_build"]>0
            and host["os_platform_id"]==2 and host["boot_time_100ns"]>=116444736000000000 and
            isinstance(host["service_pack"],str),"Invalid native OS/boot identity")
    require(packet["monitor"] == {"gpu_seconds": 1, "event_seconds": 5, "reader_timeout_seconds": 10,
                                  "completion_grace_seconds": 15}, "Monitoring contract changed")
    require(0 < packet["temperature_limit_c"] <= 80 and math.isfinite(packet["temperature_limit_c"]), "Bad thermal limit")
    future(packet["expires_utc"])
    require(Path(packet["stop_root"]).is_absolute(), "STOP root must be absolute")
    require(packet["files"] and packet["runtime_roots"], "Missing pinned assets/runtime inventory")
    sealed_environment(packet)
    require({(row["hive"], row["key"].casefold()) for row in packet["registry_policy"]} >=
            {(hive, key.casefold()) for hive in ("HKLM", "HKCU") for key in REGISTRY_KEYS}, "Missing standard driver/layer registry coverage")
    verify_registry(packet)
    enum_keys={(row["hive"],row["key"].casefold()) for row in packet["registry_enumeration_policy"]}
    require({("HKLM",DISPLAY_CLASS.casefold()),("HKLM",CONTROL_VIDEO.casefold())} <= enum_keys,
            "Missing device driver key enumeration coverage")
    value_keys={(row["hive"],row["key"].casefold()) for row in packet["registry_policy"]}
    for row in packet["registry_enumeration_policy"]:
        if row["hive"]!="HKLM" or not row["present"]:continue
        if row["key"].casefold()==CONTROL_VIDEO.casefold():
            require(all(("HKLM",(row["key"]+"\\"+name).casefold()) in enum_keys for name in row["subkeys"]),
                    "ControlVideo GUID enumeration incomplete")
        if row["key"].casefold()==DISPLAY_CLASS.casefold() or row["key"].casefold().startswith(CONTROL_VIDEO.casefold()+"\\"):
            require(all(("HKLM",(row["key"]+"\\"+name).casefold()) in value_keys for name in row["subkeys"] if re.fullmatch(r"\d{4}",name)),
                    "Device class/control video value inventory incomplete")
    expected = packet["telemetry"]
    for key in ("name", "pci_bus_id", "driver_version", "uuid", "pci_device_id"):
        require(isinstance(expected[key], str) and expected[key].strip(), "Missing reviewed GPU identity")
    for key in ("power_limit_watts", "max_graphics_clock_mhz", "max_memory_clock_mhz", "default_power_limit_watts"):
        require(type(expected[key]) in (int, float) and math.isfinite(expected[key]) and expected[key] > 0,
                "Invalid reviewed policy readback")
    require(expected["allowed_clock_event_reasons"] and all(re.fullmatch(r"0x[0-9a-f]{16}", reason)
            for reason in expected["allowed_clock_event_reasons"]), "Invalid reviewed clock reasons")
    names = [normalized(row["path"]) for row in packet["files"]]
    require(len(names) == len(set(names)), "Duplicate file pins")
    pins = {normalized(row["path"]): row for row in packet["files"]}
    verify_oracle_python_pins(packet)
    module_policy=packet["module_policy"]
    require(module_policy["sample_seconds"]==.25 and module_policy["reader_timeout_seconds"]==10 and
            module_policy["unknown_policy"]=="record-system-only" and module_policy["required_paths"],"Actual module observer policy missing/changed")
    require(all(normalized(path) in pins for path in module_policy["required_paths"]+module_policy["optional_paths"]),
            "Required/optional driver-layer module is not preregistered")
    for key in ("python", "renderer", "nvidia_smi", "git"):
        require(normalized(packet[key]) in pins, "Unpinned executable: " + key)
    require(normalized(packet["build_receipt"]["path"]) in pins, "Build provenance receipt unpinned")
    build = read_json(packet["build_receipt"]["path"])
    require(build["schema"] and build["source"] == {**packet["source"], "dirty": False}, "Build source provenance mismatch")
    renderer_pin = pins[normalized(packet["renderer"])]
    require(all(build["executable"][key] == renderer_pin[key] for key in ("sha256", "size")), "Build executable provenance mismatch")
    require(normalized(build["executable"]["path"]) in pins, "Original build executable pin missing")
    require(build["configuration"] and build["toolchain"] and "flags" in build, "Build toolchain provenance missing")
    require(normalized(build["source_snapshot"]["path"]) in pins, "Build source snapshot unpinned")
    require(packet["renderer_sha256"] == pins[normalized(packet["renderer"])]["sha256"], "Renderer declared hash differs")
    require(set(packet["native_device"]) >= {"vendor_id", "device_id", "device_type", "driver_version_raw"}, "Native device readbacks missing")
    require(any(normalized(packet["renderer"]) in {normalized(p) for p in r["files"]}
                for r in packet["runtime_roots"]), "Renderer runtime inventory missing")
    require(packet["stages"], "No approved stages")
    if packet["kind"] == "diagnostic":
        require([s["name"] for s in packet["stages"]] == ["compositing", "shadow-boundary-1", "shadow-boundary-2"],
                "Diagnostic must have three fixed stages in order")
    else:
        require(len(packet["stages"]) == 41, "Full campaign must have 41 processes")
    expected_scenes = ("compositing", "shadow-boundary", "shadow-boundary")
    output_paths = []
    for index, stage in enumerate(packet["stages"]):
        require(stage["deadline_seconds"] == 180, "Physical diagnostic deadline must be 180 seconds")
        require(stage["mode"] == "oracle", "Physical CLI only accepts the frozen oracle adapter")
        require(stage["expected_argv"] and normalized(stage["expected_argv"][0]) == normalized(packet["renderer"]), "Stage executable mismatch")
        require(stage["generated_pins"] and stage["required_outputs"], "Missing stage evidence pins")
        mutable = stage["mutable_runtime_config"]
        require(Path(mutable["path"]) == Path(stage["capture"]["out"]) / "fixture.ini" and mutable in stage["generated_pins"],
                "Only the exact live fixture.ini may be mutable after resume")
        original = [row for row in stage["generated_pins"] if Path(row["path"]) == Path(stage["capture"]["out"]) / "input/fixture.ini"]
        require(len(original) == 1 and all(original[0][key] == mutable[key] for key in ("sha256", "size")),
                "Immutable input config must pin the original mutable-config bytes")
        require(stage["capture"]["warmup"] == 120 and stage["capture"]["timeout"] == 180, "Workload/deadline changed")
        if packet["kind"] == "diagnostic":
            require(stage["capture"]["mode"] == "state" and stage["capture"]["frames"] == 1 and
                    stage["capture"]["extent"] == "640x480", "Diagnostic workload changed")
            capture = stage["capture"]
            require(set(capture) == {"exe", "iwad", "prepared", "out", "scene", "mode", "frames", "warmup", "timeout",
                                     "gpu", "include_stress", "image_policy", "extent", "expected_commit", "require_clean"},
                    "Unexpected/missing diagnostic capture controls")
            require(capture["scene"] == expected_scenes[index] and capture["image_policy"] == "exact" and
                    capture["gpu"] is False and capture["include_stress"] is True and capture["require_clean"] is True and
                    capture["expected_commit"] == packet["source"]["commit"], "Diagnostic fixture/oracle policy changed")
            for capture_key, packet_key in (("exe", "renderer"), ("iwad", "iwad"), ("prepared", "prepared")):
                require(normalized(capture[capture_key]) == normalized(packet[packet_key]), "Capture input identity changed")
            require(Path(capture["out"]).is_absolute(), "Capture output must be absolute")
            output_paths.append(str(Path(capture["out"]).resolve()))
            if index == 2:
                require(stage.get("compare_with") == packet["stages"][1]["capture"]["out"], "Shadow pair comparison missing/changed")
            else:
                require("compare_with" not in stage, "Unexpected diagnostic comparison")
        require(all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in stage["required_outputs"]),
                "Required artifact escapes stage output")
    require(len(set(output_paths)) == 3, "Diagnostic outputs overlap/retry an earlier process")
    baseline = packet["event_baseline"]
    require(baseline["channel"] == "System" and baseline["last_id"] >= baseline["oldest_id"] > 0,
            "Invalid System event baseline")
    require(baseline["epoch"] and baseline["bookmark"] and re.fullmatch(r"[0-9a-f]{64}", baseline["anchor_sha256"]),
            "Missing event epoch/bookmark/anchor")
    if check_files:
        for row in packet["files"]:
            verify_pin(row)
        verify_roots(packet)
        verify_pin(packet["build_receipt"])
        verify_pin(build["source_snapshot"])
        verify_pin(build["executable"])
        verify_source(packet)
    return hashlib.sha256(canonical(packet)).hexdigest()


def source_check_requests(packet):
    return [([packet["git"], "--no-optional-locks", "-C", packet["oracle_source_root"], *arguments],expected)
            for arguments,expected in ((["rev-parse","HEAD","HEAD^{tree}"],
                                       [packet["source"]["commit"],packet["source"]["tree"]]),
                                      (["status","--porcelain","--untracked-files=all"],[]),
                                      (["cat-file","-e",packet["source"]["commit"]+"^{commit}"],[]))]


def verify_source(packet):
    """Read-only Git checks, including the exact existence fact reused by collector."""
    checks=[]
    for argv, expected in source_check_requests(packet):
        result = subprocess.run(argv,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False, env=sealed_environment(packet))
        require(result.returncode == 0 and result.stdout.decode("utf-8", errors="strict").splitlines() == expected,
                "Frozen source HEAD/tree/dirty state changed")
        checks.append({"argv":argv,"stdout_utf8":result.stdout.decode("utf-8",errors="strict"),
                       "stderr_utf8":result.stderr.decode("utf-8",errors="strict"),"returncode":result.returncode})
    return checks


def root_expectations(packet):
    """Canonical immutable expectations; never cache current disk membership."""
    pinned = {normalized(row["path"]) for row in packet["files"]}
    result = []
    for root in packet["runtime_roots"]:
        original = Path(root["path"])
        for part in [original, *original.parents]:
            require(not linklike(part), "Runtime root/ancestor is a link")
        directory = original.resolve(strict=True)
        expected = {normalized(path) for path in root["files"]}
        require(expected <= pinned, "Runtime file is not pinned")
        result.append((original, directory, expected))
    return result


def verify_roots(packet, expectations=None):
    for original, directory, expected in expectations or root_expectations(packet):
        for part in [original, *original.parents]:
            require(not linklike(part), "Runtime root/ancestor is a link")
        require(original.resolve(strict=True) == directory, "Runtime root binding changed")
        actual = set()
        for path in directory.rglob("*"):
            require(not linklike(path), "Runtime contains a link/junction")
            if path.is_file():
                actual.add(normalized(path))
        require(actual == expected, "Runtime file set changed")


def approve(packet, approval, packet_sha256, gate):
    expected = f"AUTHORIZE {packet['experiment_id']} ({'three diagnostic processes only' if packet['kind'] == 'diagnostic' else '41 campaign processes only'})"
    require(approval["schema"] == "physical-supervisor/approval-v1" and approval["phrase"] == expected,
            "Fresh explicit exact-scope approval required")
    require(approval["experiment_id"] == packet["experiment_id"] and approval["packet_sha256"] == packet_sha256,
            "Approval is for a different packet")
    future(approval["expires_utc"])
    require(dt.datetime.fromisoformat(approval["decided_utc"]) >= dt.datetime.fromisoformat(packet["created_utc"]),
            "Approval predates packet")
    with gate:
        require(read_json(gate.root / "HELD.json")["status"] == "HELD", "Missing initial STOP")
        require(not list(gate.root.glob("STOP-*.json")), "STOP latched; new reviewed experiment/root required")
        exclusive(gate.root / ("release-" + packet_sha256 + ".json"), approval)
