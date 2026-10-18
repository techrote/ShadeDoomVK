"""Bounded native System event reader and conservative telemetry policy."""
from __future__ import annotations

import concurrent.futures
import base64
import csv
import ctypes as c
from ctypes import wintypes as w
import hashlib
import math
import os
import subprocess
import xml.etree.ElementTree as ET

from .common import Stop, canonical, require

NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
FIELDS = "name,pci.bus_id,driver_version,temperature.gpu,power.draw,power.limit,clocks.gr,clocks.mem,utilization.gpu,pstate,clocks_event_reasons.active,uuid,pci.device_id,clocks.max.graphics,clocks.max.memory,power.default_limit"


def raw_evidence(raw, *, maximum=65536):
    raw=raw or b""
    return {"base64":base64.b64encode(raw[:maximum]).decode("ascii"),"bytes":len(raw),
            "retained_bytes":min(len(raw),maximum),"truncated":len(raw)>maximum,
            "sha256":hashlib.sha256(raw).hexdigest()}


def telemetry(raw, expected, limit):
    try:
        require(len(raw)<=65536,"Telemetry evidence budget exceeded")
        return _telemetry(raw,expected,limit)
    except BaseException as error:
        failure=error if isinstance(error,Stop) else Stop("Telemetry decode/validation failed: "+str(error))
        failure.evidence={"reader":"gpu-telemetry","raw_stdout":raw_evidence(raw),"error":str(error)}
        raise failure


def _telemetry(raw, expected, limit):
    rows = list(csv.reader(raw.decode("utf-8", errors="strict").splitlines()))
    require(len(rows) == 1 and len(rows[0]) == 16, "Missing/ambiguous GPU readback")
    row = [v.strip() for v in rows[0]]
    require(row[:3] == [expected[k] for k in ("name", "pci_bus_id", "driver_version")], "GPU/PCI/driver changed")
    numbers = []
    for index in (3, 4, 5, 6, 7, 8):
        try:
            value = float(row[index])
        except ValueError as error:
            raise Stop("Invalid numeric telemetry") from error
        require(math.isfinite(value) and value >= 0, "Nonfinite/negative telemetry")
        numbers.append(value)
    require(numbers[0] < limit, "Temperature stop")
    require(numbers[2] == expected["power_limit_watts"], "Power limit drift")
    require(numbers[3] <= expected["max_graphics_clock_mhz"] and numbers[4] <= expected["max_memory_clock_mhz"], "Clock outside reviewed envelope")
    require(numbers[5] <= 100 and row[9] in {"P"+str(value) for value in range(16)}, "Invalid GPU status")
    require(row[10].lower() in expected["allowed_clock_event_reasons"], "Clock/throttle reason changed")
    require(row[11:13] == [expected["uuid"], expected["pci_device_id"]], "GPU UUID/vendor/device drift")
    for index, key in ((13, "max_graphics_clock_mhz"), (14, "max_memory_clock_mhz"), (15, "default_power_limit_watts")):
        try:
            value = float(row[index])
        except ValueError as error:
            raise Stop("Invalid policy telemetry") from error
        require(math.isfinite(value) and value == expected[key], "Clock/default-power policy drift")
    return {"temperature_c": numbers[0], "power_draw_watts": numbers[1], "power_limit_watts": numbers[2],
            "graphics_clock_mhz": numbers[3], "memory_clock_mhz": numbers[4], "utilization_percent": numbers[5],
            "pstate": row[9], "clock_event_reasons": row[10]}


def parse_event(xml):
    root = ET.fromstring(xml)
    require(root.tag == "{" + NS["e"] + "}Event", "Invalid native event XML")
    system = root.find("e:System", NS)
    return {"record_id": int(system.find("e:EventRecordID", NS).text),
            "provider": system.find("e:Provider", NS).attrib["Name"],
            "event_id": int(system.find("e:EventID", NS).text),
            "channel": system.find("e:Channel", NS).text,
            "time_utc": system.find("e:TimeCreated", NS).attrib["SystemTime"],
            "xml": xml}


def continuity(previous, current):
    """Validate every System ID, including irrelevant providers, without last-N."""
    require(current["channel"] == previous["channel"] == "System", "Channel identity changed")
    require(current["epoch"] == previous["epoch"], "Event log epoch changed/cleared")
    require(current["oldest_id"] <= previous["last_id"] <= current["last_id"], "Event log rotated/backtracked")
    require(current["resumed_anchor_sha256"] == previous["anchor_sha256"], "Event anchor missing/changed")
    require(current["resumed_bookmark"] == previous["bookmark"], "Bookmark resume mismatch")
    ids = [row["record_id"] for row in current["events"]]
    require(ids == list(range(previous["last_id"] + 1, current["last_id"] + 1)), "Event gap/duplicate/truncated enumeration")
    require(all(row["channel"] == "System" for row in current["events"]), "Event channel mismatch")
    # A System log clear is itself an invalid epoch even if platform metadata is stale.
    require(not any(row["event_id"] == 104 and row["provider"] == "Microsoft-Windows-Eventlog"
                    for row in current["events"]), "System log clear event")
    require(not any(row["provider"].casefold() in ("nvlddmkm", "display") for row in current["events"]), "New NVIDIA/Display event")
    require(current["bookmark"], "Missing completion bookmark")
    return {key: current[key] for key in ("channel", "epoch", "oldest_id", "last_id", "bookmark", "anchor_sha256")}


class NativeEvents:
    """wevtapi enumeration of ALL System records with exact bookmark seek.

    The surrounding supervisor bounds this whole operation at ten seconds. No
    provider-only query or count limit can hide a >64-event fault batch.
    """
    def __init__(self):
        require(os.name == "nt", "Windows Event Log API unavailable")
        self.e = c.WinDLL("wevtapi", use_last_error=True)
        specs = {
            "EvtOpenLog": (w.HANDLE, [w.HANDLE, w.LPCWSTR, w.DWORD]),
            "EvtGetLogInfo": (w.BOOL, [w.HANDLE, c.c_int, w.DWORD, c.c_void_p, c.POINTER(w.DWORD)]),
            "EvtQuery": (w.HANDLE, [w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.DWORD]),
            "EvtNext": (w.BOOL, [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE), w.DWORD, w.DWORD, c.POINTER(w.DWORD)]),
            "EvtRender": (w.BOOL, [w.HANDLE, w.HANDLE, w.DWORD, w.DWORD, c.c_void_p, c.POINTER(w.DWORD), c.POINTER(w.DWORD)]),
            "EvtCreateBookmark": (w.HANDLE, [w.LPCWSTR]),
            "EvtUpdateBookmark": (w.BOOL, [w.HANDLE, w.HANDLE]),
            "EvtSeek": (w.BOOL, [w.HANDLE, c.c_longlong, w.HANDLE, w.DWORD, w.DWORD]),
            "EvtClose": (w.BOOL, [w.HANDLE]),
        }
        for name, (result, args) in specs.items():
            function = getattr(self.e, name)
            function.restype, function.argtypes = result, args

    def check(self, value, message):
        if not value:
            raise Stop(message + ": " + str(c.WinError(c.get_last_error())))
        return value

    def render(self, handle, flags=1):
        used, count = w.DWORD(), w.DWORD()
        self.e.EvtRender(None, handle, flags, 0, None, c.byref(used), c.byref(count))
        require(c.get_last_error() == 122 and 0 < used.value <= 16 * 1024 * 1024, "Invalid event XML buffer")
        buffer = c.create_unicode_buffer((used.value + 1) // 2)
        self.check(self.e.EvtRender(None, handle, flags, used.value, buffer, c.byref(used), c.byref(count)), "Render event")
        return buffer.value

    def info(self):
        log = self.check(self.e.EvtOpenLog(None, "System", 1), "Open System metadata")
        try:
            result = {}
            for key, field in (("created", 0), ("count", 5), ("oldest", 6)):
                buffer = c.create_string_buffer(32)
                used = w.DWORD()
                self.check(self.e.EvtGetLogInfo(log, field, len(buffer), buffer, c.byref(used)), "System metadata")
                # EVT_VARIANT scalar union is 8 bytes, Count at8, Type at12.
                kind = c.c_uint32.from_buffer(buffer, 12).value
                require(kind in (10, 17, 21), "Unexpected event metadata type")
                result[key] = c.c_uint64.from_buffer(buffer).value
            return result
        finally:
            self.e.EvtClose(log)

    def query(self, xpath, *, reverse=False, bookmark=None):
        query = self.check(self.e.EvtQuery(None, "System", xpath, 1 | (0x200 if reverse else 0x100)), "Query complete System stream")
        mark = self.check(self.e.EvtCreateBookmark(bookmark), "Open native bookmark")
        rows = []
        total_characters = 0
        try:
            if bookmark is not None:
                # RelativeToBookmark|Strict: cannot silently seek around a missing anchor.
                self.check(self.e.EvtSeek(query, 0, mark, 0, 4 | 0x10000), "Strict bookmark seek")
            while True:
                handles = (w.HANDLE * 32)()
                count = w.DWORD()
                if not self.e.EvtNext(query, 32, handles, 1000, 0, c.byref(count)):
                    require(c.get_last_error() == 259, "Native event enumeration failed/timed out")
                    break
                try:
                    for handle in handles[:count.value]:
                        xml = self.render(handle)
                        total_characters += len(xml)
                        require(total_characters <= 32 * 1024 * 1024, "Event XML budget exceeded; continuity incomplete")
                        rows.append(parse_event(xml))
                        self.check(self.e.EvtUpdateBookmark(mark, handle), "Update event bookmark")
                        require(len(rows) <= 1_000_000, "Event evidence budget exceeded; no truncation allowed")
                finally:
                    for handle in handles[:count.value]:
                        self.e.EvtClose(handle)
                if reverse:
                    break  # Used only to establish latest ID; forward reads are unlimited.
            return rows, self.render(mark, 2) if rows else bookmark
        except BaseException as error:
            failure = error if isinstance(error, Stop) else Stop("Event decode/enumeration failed: " + str(error))
            failure.evidence = {"query": xpath, "partial_events": rows, "error": str(error)}
            raise failure
        finally:
            self.e.EvtClose(mark)
            self.e.EvtClose(query)

    def snapshot(self, previous=None):
        before = self.info()
        require(before["count"] and before["oldest"], "Empty/unavailable System channel")
        latest, _ = self.query("*", reverse=True)
        require(latest, "No System event high watermark")
        last = latest[0]["record_id"]
        if previous:
            require(previous["last_id"] >= before["oldest"], "Baseline rotated before read")
            anchor_rows, _ = self.query(f"*[System[EventRecordID={previous['last_id']}]]")
            require(len(anchor_rows) == 1, "Missing/ambiguous event anchor")
            resumed_anchor_sha = hashlib.sha256(anchor_rows[0]["xml"].encode()).hexdigest()
            # Resume the unfiltered System query at exactly the previous bookmark,
            # retain the anchor separately and enumerate to the captured high mark.
            stream, bookmark = self.query(f"*[System[EventRecordID <= {last}]]", bookmark=previous["bookmark"])
            require(stream and stream[0]["record_id"] == previous["last_id"], "Bookmark no longer references anchor")
            rows = stream[1:]
            resumed = previous["bookmark"]
            anchor_xml = stream[-1]["xml"]
        else:
            anchor_rows, bookmark = self.query(f"*[System[EventRecordID={last}]]")
            require(len(anchor_rows) == 1, "Cannot create baseline anchor")
            anchor_xml = anchor_rows[0]["xml"]
            resumed_anchor_sha = ""
            rows, resumed = [], ""
        after = self.info()
        require(before["created"] == after["created"] and before["oldest"] == after["oldest"], "System log changed epoch/rotated while reading")
        return {"channel": "System", "epoch": str(before["created"]), "oldest_id": before["oldest"],
                "last_id": last, "anchor_sha256": hashlib.sha256(anchor_xml.encode()).hexdigest(), "bookmark": bookmark,
                "resumed_anchor_sha256": resumed_anchor_sha, "anchor_xml": anchor_xml,
                "metadata_before": before, "metadata_after": after,
                "resumed_bookmark": resumed, "events": rows}


class BoundedReaders:
    """Single outstanding reader; timeout is terminal and never retried.

    Worker threads are daemon threads so a stuck native API cannot prevent the
    supervisor from latching STOP and authenticating/terminating owned children.
    """
    def __init__(self, telemetry_function, event_function, timeout=10):
        require(0 < timeout <= 10, "Reader timeout exceeds contract")
        self.telemetry_function, self.event_function = telemetry_function, event_function
        self.timeout, self.failed = timeout, False

    def call(self, name, *args):
        import queue
        import threading
        require(not self.failed, "Reader already failed; no retry")
        result = queue.Queue(maxsize=1)
        def work():
            try:
                result.put((True, getattr(self, name + "_function")(*args)))
            except BaseException as error:
                result.put((False, error))
        threading.Thread(target=work, daemon=True).start()
        try:
            ok, value = result.get(timeout=self.timeout)
        except queue.Empty as error:
            self.failed = True
            failure=Stop("Reader timeout; no retry")
            failure.evidence={"reader":name,"timeout_seconds":self.timeout,
                              "raw_output":"unavailable: reader did not complete"}
            raise failure from error
        if not ok:
            self.failed = True
            if isinstance(value, Stop):
                raise value
            raise Stop("Reader failure: " + str(value)) from value
        return value


def gpu_reader(executable):
    def read():
        argv=[executable, "--query-gpu=" + FIELDS, "--format=csv,noheader,nounits"]
        try:
            result = subprocess.run(argv,stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=9, check=False,
                                    creationflags=0x08000000 if os.name == "nt" else 0)
        except (OSError,subprocess.SubprocessError) as error:
            failure=Stop("GPU reader command failed: "+str(error))
            failure.evidence={"reader":"gpu-command","argv":argv,"returncode":None,"error":str(error),
                              "raw_stdout":raw_evidence(getattr(error,"stdout",None)),
                              "raw_stderr":raw_evidence(getattr(error,"stderr",None))}
            raise failure from error
        if result.returncode != 0 or result.stderr or len(result.stdout)>65536:
            failure=Stop("GPU reader failed/ambiguous")
            failure.evidence={"reader":"gpu-command","argv":argv,"returncode":result.returncode,
                              "raw_stdout":raw_evidence(result.stdout),"raw_stderr":raw_evidence(result.stderr)}
            raise failure
        return result.stdout
    return read
