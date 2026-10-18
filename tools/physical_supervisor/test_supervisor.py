"""CPU-only adversarial controls. Never invoke a renderer, version, or Vulkan.

Run: python -B -m unittest tools.physical_supervisor.test_supervisor -v
Windows tests create only benign Python children via native suspended handles.
"""
from __future__ import annotations

import copy
import base64
import datetime as dt
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from .common import Gate, Journal, Stop, approve, canonical, digest, exclusive, pin, read_json, require, utc, validate_packet, verify_pin, verify_roots, environment_policy, sealed_environment, REGISTRY_KEYS, DISPLAY_CLASS, CONTROL_VIDEO, verify_registry, linklike
from .readers import BoundedReaders, NativeEvents, continuity, telemetry, gpu_reader
from .supervisor import LogScanner, Watch, terminate_owned


def baseline():
    return {"channel": "System", "epoch": "synthetic-epoch", "oldest_id": 1, "last_id": 10,
            "bookmark": "bookmark10", "anchor_sha256": "a" * 64}


def batch(count=0):
    return {"channel": "System", "epoch": "synthetic-epoch", "oldest_id": 1, "last_id": 10 + count,
            "bookmark": "bookmark" + str(10 + count), "anchor_sha256": "a" * 64 if not count else "b" * 64,
            "resumed_anchor_sha256": "a" * 64, "resumed_bookmark": "bookmark10",
            "events": [{"record_id": i, "channel": "System", "provider": "benign", "event_id": 1}
                       for i in range(11, 11 + count)]}


EXPECTED = {"name": "synthetic GPU", "pci_bus_id": "synthetic PCI", "driver_version": "synthetic driver",
            "power_limit_watts": 90, "max_graphics_clock_mhz": 2100, "max_memory_clock_mhz": 6000,
            "allowed_clock_event_reasons": ["0x0000000000000000", "0x0000000000000001", "0x0000000000000004", "0x0000000000000005"],
            "uuid": "synthetic UUID", "pci_device_id": "synthetic vendor/device", "default_power_limit_watts": 100}
ROW = ["synthetic GPU", "synthetic PCI", "synthetic driver", "30", "12", "90", "300", "405", "0", "P8",
       "0x0000000000000001", "synthetic UUID", "synthetic vendor/device", "2100", "6000", "100"]


def raw(row=ROW):
    return (", ".join(row) + "\n").encode()


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="physical-supervisor-cpu-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.doCleanups()
        self.temp.cleanup()

    def gate(self):
        root = self.root / "stop"
        root.mkdir()
        exclusive(root / "HELD.json", {"status": "HELD"})
        exclusive(root / ("release-" + "a" * 64 + ".json"), {"packet_sha256": "a" * 64,
            "expires_utc":(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()})
        return Gate(root, "a" * 64)


class EvidenceTests(TempCase):
    def test_exclusive_receipt_rejects_replace(self):
        path = self.root / "receipt.json"
        exclusive(path, {"one": 1})
        with self.assertRaises(FileExistsError):
            exclusive(path, {"two": 2})
        self.assertEqual(read_json(path), {"one": 1})

    def test_partial_receipt_fails_closed(self):
        path = self.root / "receipt.json"
        path.write_bytes(b'{"incomplete":')
        with self.assertRaises(ValueError):
            read_json(path)

    def test_duplicate_json_key_rejected(self):
        path = self.root / "receipt.json"
        path.write_bytes(b'{"a":1,"a":2}')
        with self.assertRaises(Stop):
            read_json(path)

    def test_journal_detects_modified_and_missing_entry(self):
        journal = Journal(self.root / "journal")
        journal.append("one", {})
        journal.append("two", {})
        Journal.audit(journal.root)
        first = next(journal.root.glob("000000-*"))
        first.write_bytes(first.read_bytes() + b" ")
        with self.assertRaises(Stop):
            Journal.audit(journal.root)
        first.unlink()
        with self.assertRaises(Stop):
            Journal.audit(journal.root)

    def test_missing_and_modified_asset(self):
        path = self.root / "fixture.pk3"
        path.write_bytes(b"fixture")
        row = pin(path)
        path.write_bytes(b"changed")
        with self.assertRaises(Stop):
            verify_pin(row)
        path.unlink()
        with self.assertRaises(OSError):
            verify_pin(row)

    def test_replaced_executable(self):
        path = self.root / "benign.exe"
        path.write_bytes(b"old")
        row = pin(path)
        path.unlink()
        path.write_bytes(b"new")
        with self.assertRaises(Stop):
            verify_pin(row)

    def test_added_runtime_file(self):
        path = self.root / "benign.exe"
        path.write_bytes(b"cpu")
        packet = {"files": [pin(path)], "runtime_roots": [{"path": str(self.root), "files": [str(path)]}]}
        verify_roots(packet)
        (self.root / "injected.dll").write_bytes(b"extra")
        with self.assertRaises(Stop):
            verify_roots(packet)

    def test_root_symlink(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit symlink creation")
        with self.assertRaises(Stop):
            verify_roots({"runtime_roots": [{"path": str(link), "files": []}], "files": []})

    def test_junction_reparse_flag_on_python310(self):
        path=self.root/"synthetic-junction"
        with patch.object(Path,"is_symlink",return_value=False),patch.object(Path,"lstat",return_value=types.SimpleNamespace(st_file_attributes=0x400)):
            self.assertTrue(linklike(path))
            with self.assertRaises(Stop):verify_roots({"runtime_roots":[{"path":str(path),"files":[]}],"files":[]})

    def test_preparer_rejects_root_alias_before_resolve(self):
        from .prepare import checked_directory
        path=self.root/"synthetic-root-alias"
        with patch("tools.physical_supervisor.prepare.linklike",return_value=True),patch.object(Path,"resolve") as resolve:
            with self.assertRaises(Stop):checked_directory(path)
            resolve.assert_not_called()

    def test_stop_between_check_and_spawn(self):
        gate = self.gate()
        with gate:
            gate.check()
        with gate:
            gate.stop("synthetic between-check failure")
        launches = []
        with self.assertRaises(Stop), gate:
            gate.check()
            launches.append("forbidden")
        self.assertFalse(launches)

    def test_stop_survives_new_gate_no_retry(self):
        gate = self.gate()
        with gate:
            gate.stop("first failure")
        with self.assertRaises(Stop), Gate(gate.root, "a" * 64) as again:
            again.check()
        self.assertEqual(len(list(gate.root.glob("STOP-*"))), 1)

    def test_stop_and_resume_critical_section_is_serialized(self):
        gate=self.gate();waiting=threading.Event();finished=threading.Event();errors=[]
        def publisher():
            waiting.set()
            try:
                with Gate(gate.root,"a"*64) as other:other.stop("synthetic concurrent fault")
            except BaseException as error:errors.append(error)
            finally:finished.set()
        with gate:
            gate.check()
            thread=threading.Thread(target=publisher);thread.start();waiting.wait(1)
            time.sleep(.05)
            self.assertFalse(finished.is_set())
            self.assertFalse(list(gate.root.glob("STOP-*")))
        thread.join(2)
        self.assertTrue(finished.is_set());self.assertFalse(errors)
        with self.assertRaises(Stop),gate:gate.check()

    def test_unlocked_stop_publisher_rejected(self):
        gate=self.gate()
        with self.assertRaises(Stop):gate.stop("not serialized")
        self.assertFalse(list(gate.root.glob("STOP-*")))

    def test_missing_stop_or_release_rejected(self):
        gate = self.gate()
        (gate.root / "HELD.json").unlink()
        with self.assertRaises(OSError), gate:
            gate.check()

    def test_expired_release_blocks_even_when_packet_hash_matches(self):
        root=self.root/"expired-stop";root.mkdir()
        exclusive(root/"HELD.json",{"status":"HELD"})
        exclusive(root/("release-"+"a"*64+".json"),{"packet_sha256":"a"*64,"expires_utc":"2000-01-01T00:00:00+00:00"})
        with self.assertRaises(Stop),Gate(root,"a"*64) as gate:gate.check()

    def test_failure_receipt_write_cannot_skip_termination(self):
        calls = []
        class Child:
            def kill(self, identity):
                calls.append(identity)
                return True
        class FullDisk:
            def append(self, *args):
                raise OSError("synthetic full disk")
        errors = terminate_owned((("target", Child(), "target"), ("collector", Child(), "collector")), FullDisk())
        self.assertEqual(calls, ["target", "collector"])
        self.assertEqual(len(errors), 2)

    def test_kill_misidentification_does_not_block_other_owned_handle(self):
        calls = []
        class Wrong:
            def kill(self, identity):
                raise Stop("PID reuse")
        class Right:
            def kill(self, identity):
                calls.append(identity)
                return True
        journal = Journal(self.root / "journal")
        errors = terminate_owned((("target", Wrong(), "wrong"), ("collector", Right(), "right")), journal)
        self.assertEqual(calls, ["right"])
        self.assertTrue(errors)


class EventTests(unittest.TestCase):
    def test_all_129_events_are_retained(self):
        current = batch(129)
        self.assertEqual(continuity(baseline(), current)["last_id"], 139)
        self.assertEqual(len(current["events"]), 129)

    def test_fault_hidden_beyond_last64_rejected(self):
        current = batch(129)
        current["events"][0]["provider"] = "nvlddmkm"
        with self.assertRaises(Stop):
            continuity(baseline(), current)

    def test_rolling_anchor_advances(self):
        next_base = continuity(baseline(), batch(1))
        following = batch()
        following.update(last_id=11, bookmark="bookmark11", resumed_bookmark="bookmark11",
                         resumed_anchor_sha256="b" * 64, anchor_sha256="b" * 64)
        self.assertEqual(continuity(next_base, following)["anchor_sha256"], "b" * 64)

    def test_log_clear_epoch_and_stale_baseline(self):
        for key, value in (("epoch", "cleared"), ("oldest_id", 11), ("last_id", 9),
                           ("resumed_anchor_sha256", "c" * 64), ("resumed_bookmark", "wrong"), ("channel", "Security")):
            with self.subTest(key=key):
                current = batch()
                current[key] = value
                with self.assertRaises(Stop):
                    continuity(baseline(), current)

    def test_gap_duplicate_and_truncation(self):
        for ids in ([11, 13], [11, 11, 13], [12, 13], [11, 12]):
            current = batch(3)
            current["events"] = [{"record_id": value, "channel": "System", "provider": "benign", "event_id": 1} for value in ids]
            with self.subTest(ids=ids), self.assertRaises(Stop):
                continuity(baseline(), current)

    def test_display_error_and_late_event(self):
        for provider in ("Display", "nvlddmkm"):
            current = batch(1)
            current["events"][0]["provider"] = provider
            with self.assertRaises(Stop):
                continuity(baseline(), current)

    def test_native_log_clear_record(self):
        current = batch(1)
        current["events"][0].update(provider="Microsoft-Windows-Eventlog", event_id=104)
        with self.assertRaises(Stop):
            continuity(baseline(), current)


class TelemetryTests(unittest.TestCase):
    def test_valid_idle_finite_readback(self):
        self.assertEqual(telemetry(raw(), EXPECTED, 80)["temperature_c"], 30)

    def test_nonfinite_temp_power_clock_or_utilization(self):
        for index in (3, 4, 5, 6, 7, 8, 13, 14, 15):
            for value in ("nan", "inf", "-inf", "N/A"):
                row = list(ROW)
                row[index] = value
                with self.subTest(index=index, value=value), self.assertRaises(Stop):
                    telemetry(raw(row), EXPECTED, 80)

    def test_temperature_boundary(self):
        row = list(ROW)
        row[3] = "80"
        with self.assertRaises(Stop):
            telemetry(raw(row), EXPECTED, 80)

    def test_identity_policy_power_and_throttle_drift(self):
        for index in (0, 1, 2, 5, 10, 11, 12, 13, 14, 15):
            row = list(ROW)
            row[index] = "changed"
            with self.subTest(index=index), self.assertRaises(Stop):
                telemetry(raw(row), EXPECTED, 80)

    def test_low_current_clocks_do_not_hide_policy_drift(self):
        row = list(ROW)
        row[13] = "2200"
        with self.assertRaises(Stop):
            telemetry(raw(row), EXPECTED, 80)

    def test_reviewed_reason_masks_and_forbidden_bits(self):
        for mask in (0,1,4,5):
            row=list(ROW);row[10]=f"0x{mask:016x}"
            telemetry(raw(row),EXPECTED,80)
        for mask in (2,8,0x10,0x20,0x40,0x80,0x100,3,7,9,0x105):
            row=list(ROW);row[10]=f"0x{mask:016x}"
            with self.subTest(mask=mask),self.assertRaises(Stop):telemetry(raw(row),EXPECTED,80)

    def test_invalid_pstate_rejected(self):
        for state in ("P999","P-1","P16","P01","UNKNOWN",""):
            row=list(ROW);row[9]=state
            with self.subTest(state=state),self.assertRaises(Stop):telemetry(raw(row),EXPECTED,80)

    def test_multiple_gpu_or_missing_row(self):
        for value in (b"", raw() + raw(), raw().replace(b", 100\n", b"\n")):
            with self.assertRaises(Stop):
                telemetry(value, EXPECTED, 80)


class ReaderTests(TempCase):
    def test_bad_raw_telemetry_survives_observer_failure(self):
        gate=self.gate();journal=Journal(self.root/"journal")
        row=list(ROW);row[3]="nan";bad=raw(row)
        packet={"stop_root":str(gate.root),"packet_sha256":"a"*64,"telemetry":EXPECTED,"temperature_limit_c":80}
        watch=Watch(packet,baseline(),journal,BoundedReaders(lambda:bad,None))
        watch.loop("telemetry",1)
        with self.assertRaises(Stop):watch.check()
        records=[read_json(p) for p in journal.root.glob("*-partial-reader-evidence.json")]
        retained=records[0]["value"]["partial_evidence"]["raw_stdout"]
        self.assertEqual(base64.b64decode(retained["base64"]),bad)
        self.assertFalse(retained["truncated"])

    def test_invalid_utf8_and_thermal_stop_retain_raw_bytes(self):
        row=list(ROW);row[3]="80"
        for bad in (b"\xff\x00invalid UTF8\n",raw(row)):
            with self.subTest(bad=bad),self.assertRaises(Stop) as caught:telemetry(bad,EXPECTED,80)
            self.assertEqual(base64.b64decode(caught.exception.evidence["raw_stdout"]["base64"]),bad)

    def test_gpu_command_failure_preserves_stdout_stderr_returncode(self):
        result=subprocess.CompletedProcess(["synthetic-reader"],17,b"partial stdout\xff",b"stderr\xfe")
        with patch("tools.physical_supervisor.readers.subprocess.run",return_value=result),self.assertRaises(Stop) as caught:
            gpu_reader("synthetic-reader")()
        evidence=caught.exception.evidence
        self.assertEqual(evidence["returncode"],17)
        self.assertEqual(evidence["argv"][0],"synthetic-reader")
        self.assertEqual(base64.b64decode(evidence["raw_stdout"]["base64"]),result.stdout)
        self.assertEqual(base64.b64decode(evidence["raw_stderr"]["base64"]),result.stderr)

    def test_gpu_timeout_preserves_available_partial_bytes(self):
        error=subprocess.TimeoutExpired(["synthetic-reader"],9,output=b"partial",stderr=b"timeout stderr")
        with patch("tools.physical_supervisor.readers.subprocess.run",side_effect=error),self.assertRaises(Stop) as caught:
            gpu_reader("synthetic-reader")()
        self.assertEqual(base64.b64decode(caught.exception.evidence["raw_stdout"]["base64"]),b"partial")
        self.assertIsNone(caught.exception.evidence["returncode"])

    def test_gpu_stderr_only_or_oversized_output_is_bounded_and_retained(self):
        for stdout,stderr in ((b"partial",b"warning without nonzero exit"),(b"x"*70000,b"")):
            result=subprocess.CompletedProcess(["synthetic-reader"],0,stdout,stderr)
            with patch("tools.physical_supervisor.readers.subprocess.run",return_value=result),self.assertRaises(Stop) as caught:
                gpu_reader("synthetic-reader")()
            evidence=caught.exception.evidence["raw_stdout"]
            self.assertEqual(evidence["bytes"],len(stdout))
            self.assertLessEqual(evidence["retained_bytes"],65536)
            self.assertEqual(evidence["sha256"],hashlib.sha256(stdout).hexdigest())

    def test_concurrent_failure_records_do_not_overwrite(self):
        gate=self.gate();journal=Journal(self.root/"journal")
        watch=Watch({"stop_root":str(gate.root),"packet_sha256":"a"*64},baseline(),journal,BoundedReaders(None,None))
        errors=[]
        for name in ("telemetry","event","module"):
            error=Stop(name);error.evidence={"reader":name,"raw":"synthetic-"+name};errors.append(error)
        threads=[threading.Thread(target=watch.fail,args=(error,)) for error in errors]
        for thread in threads:thread.start()
        for thread in threads:thread.join(2)
        with self.assertRaises(Stop):watch.check()
        rows=[read_json(p)["value"]["partial_evidence"]["reader"] for p in journal.root.glob("*-partial-reader-evidence.json")]
        self.assertEqual(set(rows),{"telemetry","event","module"})

    def test_reader_timeout_never_retries(self):
        calls = []
        def stuck():
            calls.append(1)
            time.sleep(.2)
        readers = BoundedReaders(stuck, None, timeout=.02)
        with self.assertRaises(Stop):
            readers.call("telemetry")
        with self.assertRaises(Stop):
            readers.call("telemetry")
        self.assertEqual(calls, [1])

    def test_reader_security_failure(self):
        def denied(*args):
            raise PermissionError("synthetic denied")
        with self.assertRaises(Stop):
            BoundedReaders(None, denied).call("event", baseline())

    def test_output_fault_marker_cross_chunk(self):
        path = self.root / "stdout.log"
        path.write_bytes(b"benign [fau")
        scanner = LogScanner()
        scanner.check([path])
        with path.open("ab") as stream:
            stream.write(b"lt] synthetic CPU fault")
        with self.assertRaises(Stop):
            scanner.check([path])

    def test_output_truncation_rejected(self):
        path = self.root / "stdout.log"
        path.write_bytes(b"benign log")
        scanner = LogScanner()
        scanner.check([path])
        path.write_bytes(b"")
        with self.assertRaises(Stop):
            scanner.check([path])

    def test_output_same_size_replacement_and_prefix_overwrite(self):
        for replace in (False,True):
            path=self.root/("replace.log" if replace else "overwrite.log")
            path.write_bytes(b"benign output")
            scanner=LogScanner(); scanner.check([path])
            if replace: path.unlink()
            path.write_bytes(b"[fault] bytes")
            with self.assertRaises(Stop): scanner.check([path])

    def test_silent_guard_thread_death_rejected(self):
        gate=self.gate(); journal=Journal(self.root/"journal")
        watch=Watch({"stop_root":str(gate.root),"packet_sha256":"a"*64},baseline(),journal,BoundedReaders(None,None))
        watch.threads=[types.SimpleNamespace(is_alive=lambda:False)]
        with self.assertRaises(Stop): watch.check()

    def test_reader_queue_overflow_latches_stop(self):
        gate=self.gate();journal=Journal(self.root/"journal")
        packet={"stop_root":str(gate.root),"packet_sha256":"a"*64,"telemetry":EXPECTED,"temperature_limit_c":80}
        watch=Watch(packet,baseline(),journal,BoundedReaders(lambda:raw(),None))
        for _ in range(64): watch.messages.put_nowait(("synthetic",{}))
        watch.loop("telemetry",1)
        with self.assertRaises(Stop): watch.check()
        self.assertTrue(list(gate.root.glob("STOP-*")))

    def test_guard_event_failure_preserves_offending_batch(self):
        gate = self.gate()
        current = batch(100)
        current["events"][0]["provider"] = "Display"
        readers = BoundedReaders(lambda: raw(), lambda previous: current)
        journal = Journal(self.root / "journal")
        packet = {"stop_root": str(gate.root), "packet_sha256": "a" * 64, "telemetry": EXPECTED, "temperature_limit_c": 80}
        watch = Watch(packet, baseline(), journal, readers)
        watch.loop("event", 5)
        with self.assertRaises(Stop):
            watch.check()
        rows = [read_json(path) for path in journal.root.glob("*-event.json")]
        self.assertEqual(len(rows[0]["value"]["events"]), 100)
        self.assertTrue(list(gate.root.glob("STOP-*")))

    def test_unknown_actual_module_retains_path_before_stop(self):
        from .supervisor import ModuleWatch
        path=self.root/"synthetic-unreviewed-layer.dll";path.write_bytes(b"CPU data, never loaded")
        target=types.SimpleNamespace(poll=lambda:None,modules=lambda expected:[str(path)])
        errors=[];health=types.SimpleNamespace(fail=lambda error:errors.append(error))
        packet={"module_policy":{"required_paths":[str(path)],"optional_paths":[]},"files":[]}
        watch=ModuleWatch(packet,target,{},Journal(self.root/"journal"),health)
        watch.start();watch.thread.join(2)
        with self.assertRaises(Stop):watch.finish(require_complete=False)
        self.assertTrue(errors)
        self.assertEqual(errors[0].evidence["module_paths"],[str(path)])


class PacketAndApprovalTests(TempCase):
    def packet(self):
        runtime=self.root/"runtime";runtime.mkdir()
        exe=runtime/"never-executed.exe";exe.write_bytes(b"synthetic executable bytes, never executed")
        source=self.root/"source";source.mkdir()
        prepared=self.root/"prepared";prepared.mkdir()
        fixture=prepared/"fixture.ini";fixture.write_bytes(b"synthetic fixture")
        snapshot=self.root/"snapshot.json";exclusive(snapshot,{"synthetic":True})
        source_identity={"commit":"1"*40,"tree":"2"*40}
        build=self.root/"build.json"
        exclusive(build,{"schema":"synthetic-build/v1","source":{**source_identity,"dirty":False},"executable":pin(exe),
                         "configuration":"synthetic","toolchain":"synthetic","flags":[],"source_snapshot":pin(snapshot)})
        expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()
        packet={"schema":"physical-supervisor/packet-v1","experiment_id":"CPU-PACKET-TEST","kind":"diagnostic",
                "source":source_identity,"automatic_retries":0,"created_utc":utc(),"expires_utc":expires,
                "monitor":{"gpu_seconds":1,"event_seconds":5,"reader_timeout_seconds":10,"completion_grace_seconds":15},
                "temperature_limit_c":80,"stop_root":str(self.root/"stop"),"telemetry":EXPECTED,"environment_policy":environment_policy(),
                "python":str(exe),"renderer":str(exe),"nvidia_smi":str(exe),"git":str(exe),"oracle_source_root":str(source),
                "renderer_sha256":pin(exe)["sha256"],"iwad":str(fixture),"prepared":str(prepared),"build_receipt":pin(build),
                "native_device":{"vendor_id":1,"device_id":2,"device_type":2,"driver_version_raw":3},
                "event_baseline":baseline(),"files":[pin(p) for p in (exe,fixture,snapshot,build)],
                "registry_policy":[{"hive":hive,"key":key,"present":False,"values":[]} for hive in ("HKLM","HKCU") for key in REGISTRY_KEYS],
                "registry_enumeration_policy":[{"hive":"HKLM","key":key,"present":False,"subkeys":[]} for key in (DISPLAY_CLASS,CONTROL_VIDEO)],
                "runtime_roots":[{"path":str(runtime),"files":[str(exe)]}]}
        packet["module_policy"]={"sample_seconds":.25,"reader_timeout_seconds":10,"unknown_policy":"record-system-only",
                                 "required_paths":[str(exe)],"optional_paths":[]}
        stages=[]
        for index,name in enumerate(("compositing","shadow-boundary-1","shadow-boundary-2")):
            out=self.root/"captures"/name
            live={**pin(fixture),"path":str(out/"fixture.ini")}
            capture={"exe":str(exe),"iwad":str(fixture),"prepared":str(prepared),"out":str(out),
                     "scene":"compositing" if index==0 else "shadow-boundary","mode":"state","frames":1,"warmup":120,
                     "timeout":180,"gpu":False,"include_stress":True,"image_policy":"exact","extent":"640x480",
                     "expected_commit":"1"*40,"require_clean":True}
            stage={"name":name,"mode":"oracle","deadline_seconds":180,"expected_argv":[str(exe)],"capture":capture,
                   "generated_pins":[live,{**live,"path":str(out/"input/fixture.ini")}],"mutable_runtime_config":live,
                   "required_outputs":["run.json","native.renderer.json"]}
            if index==2:stage["compare_with"]=str(self.root/"captures/shadow-boundary-1")
            stages.append(stage)
        packet["stages"]=stages
        return packet

    def test_positive_complete_packet_and_negative_workload_mutations(self):
        packet=self.packet()
        with patch("tools.physical_supervisor.common.verify_source"),patch("tools.physical_supervisor.common.verify_registry"):
            self.assertEqual(validate_packet(packet),hashlib.sha256(canonical(packet)).hexdigest())
            changes=[("scene","lights-zero"),("image_policy","tolerant"),("gpu",True),("require_clean",False),
                     ("expected_commit","3"*40),("extent","1904x1001"),("warmup",119),("frames",2),("timeout",181)]
            for key,value in changes:
                changed=copy.deepcopy(packet);changed["stages"][0]["capture"][key]=value
                with self.subTest(key=key),self.assertRaises(Stop):validate_packet(changed)
            for mutation in (lambda p:p["stages"].reverse(),lambda p:p["stages"].pop(),
                             lambda p:p["stages"][2].pop("compare_with"),lambda p:p.update(kind="campaign"),
                             lambda p:p["source"].update(commit="4"*40),
                             lambda p:p["stages"][0]["expected_argv"].__setitem__(0,str(self.root/"not-pinned.exe")),
                             lambda p:p["environment_policy"].update(VK_DRIVER_FILES="unreviewed")):
                changed=copy.deepcopy(packet);mutation(changed)
                with self.subTest(mutation=mutation),self.assertRaises((Stop,OSError)):validate_packet(changed)

    def test_loader_environment_absent_and_changed_controls(self):
        packet={"environment_policy":environment_policy()}
        sealed_environment(packet)
        with patch.dict(os.environ,{"VK_DRIVER_FILES":"synthetic-unreviewed-driver"}):
            with self.assertRaises(Stop):sealed_environment(packet)
        with patch.dict(os.environ,{"VK_FUTURE_UNKNOWN_KEY":"synthetic-new-control"}):
            with self.assertRaises(Stop):sealed_environment(packet)

    def test_manifest_environment_control_is_preserved_and_drift_rejected(self):
        with patch.dict(os.environ,{"SYNTHETIC_LAYER_DISABLE":"1"}):
            packet={"environment_extra_keys":["SYNTHETIC_LAYER_DISABLE"],"environment_policy":environment_policy(["SYNTHETIC_LAYER_DISABLE"])}
            self.assertEqual(sealed_environment(packet)["SYNTHETIC_LAYER_DISABLE"],"1")
        with self.assertRaises(Stop):sealed_environment(packet)

    def test_registry_value_and_new_driver_key_drift(self):
        policy=[{"hive":"HKLM","key":"synthetic","present":True,"values":[{"name":"layer.json","type":4,"value":0}]}]
        enumeration=[{"hive":"HKLM","key":"synthetic","present":True,"subkeys":["0000"]}]
        packet={"registry_policy":policy,"registry_enumeration_policy":enumeration}
        with patch("tools.physical_supervisor.common.read_registry_policy",return_value=policy),patch("tools.physical_supervisor.common.read_registry_enumeration_policy",return_value=enumeration):verify_registry(packet)
        changed=copy.deepcopy(policy);changed[0]["values"][0]["value"]=1
        with patch("tools.physical_supervisor.common.read_registry_policy",return_value=changed),self.assertRaises(Stop):verify_registry(packet)
        with patch("tools.physical_supervisor.common.read_registry_policy",return_value=policy),patch("tools.physical_supervisor.common.read_registry_enumeration_policy",return_value=[{**enumeration[0],"subkeys":["0000","0001"]}]),self.assertRaises(Stop):verify_registry(packet)

    def test_exact_approval_hash_experiment_scope_expiry_and_predate(self):
        packet=self.packet();sha=hashlib.sha256(canonical(packet)).hexdigest()
        valid={"schema":"physical-supervisor/approval-v1","experiment_id":packet["experiment_id"],"packet_sha256":sha,
               "phrase":"AUTHORIZE CPU-PACKET-TEST (three diagnostic processes only)","decided_utc":utc(),"expires_utc":packet["expires_utc"]}
        mutations=[("packet_sha256","0"*64),("experiment_id","WRONG-EXPERIMENT"),("phrase","AUTHORIZE ALL"),
                   ("expires_utc","2000-01-01T00:00:00+00:00"),("decided_utc","2000-01-01T00:00:00+00:00")]
        for index,(key,value) in enumerate(mutations):
            root=self.root/f"approval-{index}";root.mkdir();exclusive(root/"HELD.json",{"status":"HELD"})
            approval={**valid,key:value}
            with self.subTest(key=key),self.assertRaises(Stop):approve(packet,approval,sha,Gate(root,sha))
            self.assertFalse(list(root.glob("release-*")))
        root=self.root/"approval-good";root.mkdir();exclusive(root/"HELD.json",{"status":"HELD"})
        approve(packet,valid,sha,Gate(root,sha))
        with Gate(root,sha) as gate:gate.check()
        with self.assertRaises(FileExistsError):approve(packet,valid,sha,Gate(root,sha))


@unittest.skipUnless(os.name == "nt", "Native Windows handle controls")
class NativeWindowsTests(TempCase):
    def spawn(self, script):
        from .windows import Process
        self.stdout = (self.root / "stdout.log").open("wb")
        self.stderr = (self.root / "stderr.log").open("wb")
        child = Process.spawn([sys.executable, "-I", "-B", "-c", script], self.root, self.stdout, self.stderr)
        identity = child.identity()
        self.addCleanup(child.close)
        self.addCleanup(self.stdout.close)
        self.addCleanup(self.stderr.close)
        self.addCleanup(lambda: child.kill(identity) if child.handle else None)
        return child, identity

    def test_suspended_child_cannot_execute_before_resume(self):
        marker = self.root / "marker"
        child, identity = self.spawn("from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('CPU only')")
        time.sleep(.1)
        self.assertFalse(marker.exists())
        child.resume(identity)
        until = time.monotonic() + 5
        while child.poll() is None and time.monotonic() < until:
            time.sleep(.01)
        self.assertEqual(child.poll(), 0)
        self.assertEqual(marker.read_text(), "CPU only")

    def test_pid_creation_parent_path_hash_mismatch_never_kills(self):
        child, identity = self.spawn("import time;time.sleep(10)")
        child.resume(identity)
        for field in ("pid", "creation_ticks", "parent_pid", "parent_creation_ticks", "path", "sha256"):
            changed = dict(identity)
            changed[field] = "wrong" if isinstance(identity[field], str) else identity[field] + 1
            with self.subTest(field=field), self.assertRaises(Stop):
                child.kill(changed)
            self.assertIsNone(child.poll())
        self.assertTrue(child.kill(identity))

    def test_locked_asset_rejects_modification_and_replacement(self):
        from .windows import FileLock
        path = self.root / "fixture.pk3"
        path.write_bytes(b"fixture")
        lock = FileLock(pin(path))
        try:
            with self.assertRaises(OSError):
                path.write_bytes(b"changed")
            with self.assertRaises(OSError):
                path.unlink()
            lock.verify()
        finally:
            lock.close()

    def test_job_detects_benign_orphan_child_inventory(self):
        from .windows import Job
        job = Job()
        self.addCleanup(job.close)
        child, identity = self.spawn("import time;time.sleep(10)")
        job.assign(child)
        self.assertEqual(job.pids(), {child.pid})
        child.kill(identity)
        self.assertEqual(job.pids(), set())

    def test_native_system_bookmark_read_only_smoke(self):
        native = NativeEvents()
        before = BoundedReaders(None, native.snapshot).call("event")
        after = BoundedReaders(None, native.snapshot).call("event", before)
        continuity(before, after)
        self.assertTrue(before["anchor_xml"])

    def test_existing_unowned_benign_image_is_rejected_without_kill(self):
        from .windows import reject_unowned_renderer
        child,identity=self.spawn("import time;time.sleep(20)")
        child.resume(identity)
        with self.assertRaises(Stop):reject_unowned_renderer(sys.executable)
        self.assertIsNone(child.poll())

    def test_actual_benign_cpu_loaded_module_identity(self):
        from .supervisor import ModuleWatch
        child,identity=self.spawn("import time;time.sleep(20)")
        child.resume(identity);time.sleep(.1)
        paths=child.modules(identity)
        self.assertIn(os.path.normcase(str(Path(sys.executable).resolve())),paths)
        packet={"module_policy":{"required_paths":[sys.executable],"optional_paths":[],"sample_seconds":.25,
                                 "reader_timeout_seconds":10,"unknown_policy":"record-system-only"},
                "files":[pin(path) for path in paths]}
        errors=[];health=types.SimpleNamespace(fail=lambda error:errors.append(str(error)))
        journal=Journal(self.root/"journal")
        watch=ModuleWatch(packet,child,identity,journal,health)
        watch.start();time.sleep(.3);watch.finish(require_complete=True)
        self.assertFalse(errors)
        self.assertTrue(list(journal.root.glob("*-actual-modules.json")))


if __name__ == "__main__":
    unittest.main()
