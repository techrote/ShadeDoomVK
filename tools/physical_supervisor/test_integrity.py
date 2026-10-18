"""CPU-only liveness and terminal namespace invalidation controls.

Synthetic oracle/native Python children never represent renderer evidence.
All GPU/event readers are synthetic; no hardware discovery runs here.
"""
from __future__ import annotations

import os
import sys
import hashlib
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from .common import Gate, Journal, Stop, exclusive, pin, read_json, root_expectations, verify_roots, digest, open_read, normalized
from .integrity import IntegrityWatch, valid_proof, POLICY
from . import test_integration as fixture
from . import test_supervisor as cpu_fixture
from .windows import RootGuard


class ProofTests(unittest.TestCase):
    def test_final_receipt_is_invisible_until_complete_flush(self):
        with tempfile.TemporaryDirectory() as directory:
            final=Path(directory)/"receipt.json";entered=threading.Event();release=threading.Event();errors=[]
            original=os.fsync
            def delayed(fd):entered.set();release.wait(2);original(fd)
            def produce():
                try:exclusive(final,{"complete":"CPU atomic publication"})
                except BaseException as error:errors.append(error)
            with patch("os.fsync",side_effect=delayed):
                worker=threading.Thread(target=produce);worker.start()
                self.assertTrue(entered.wait(1));self.assertFalse(final.exists())
                release.set();worker.join(2)
            self.assertFalse(errors);self.assertEqual(read_json(final),{"complete":"CPU atomic publication"})
            with self.assertRaises(FileExistsError):exclusive(final,{"replacement":True})
    def test_generation_time_request_and_identity_fail_closed(self):
        now=time.monotonic();packet={"packet_sha256":"a"*64,"runtime_roots":[],"integrity_policy":POLICY};stage={"name":"cpu"};owner={"creation_ticks":123}
        request={"schema":"physical-supervisor/integrity-request-v1","packet_sha256":"a"*64,"stage":"cpu",
                 "supervisor":owner,"collector":None,"role":"collector","source_preflight":{},
                 "nonce":"a"*32,"requested_monotonic":now-.2}
        value={"schema":"physical-supervisor/integrity-generation-v1","packet_sha256":"a"*64,"stage":"cpu",
               "supervisor":owner,"status":"PASS","started_monotonic":now-.1,"finished_monotonic":now-.05,"request":request,
               "generation":0,"checks":{"closed_roots":0,"log_append_only":"PASS","generated_pins":0},"policy":POLICY,"utc":"synthetic CPU clock"}
        valid_proof(value,packet,stage,owner,request=request,boundary=True)
        for delta in ({"packet_sha256":"b"*64},{"supervisor":{}},{"started_monotonic":now-11},
                      {"finished_monotonic":now-.6},{"started_monotonic":now-.3},{"finished_monotonic":now+1},
                      {"request":{"nonce":"b"*32}}):
            with self.subTest(delta=delta),self.assertRaises(Stop):
                valid_proof({**value,**delta},packet,stage,owner,request=request,boundary=True)
        # A freshly completed proof cannot extend the one-use request deadline.
        stale={**request,"requested_monotonic":now-10.01}
        with self.assertRaises(Stop):valid_proof({**value,"request":stale},packet,stage,owner,request=stale,boundary=True)

    def test_cached_expectations_still_inspect_actual_membership_and_reparse(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);asset=root/"asset";asset.write_text("CPU input")
            packet={"runtime_roots":[{"path":str(root),"files":[str(asset)]}],"files":[pin(asset)]}
            expected=root_expectations(packet);verify_roots(packet,expected)
            (root/"extra").write_text("unexpected")
            with self.assertRaises(Stop):verify_roots(packet,expected)


class WorkerTests(unittest.TestCase):
    def worker(self,root):
        control=root/"control";control.mkdir()
        packet={"packet_sha256":"a"*64,"runtime_roots":[],"files":[],"integrity_policy":POLICY}
        scanner=type("CPUScanner",(),{"check":lambda self,paths:None})()
        return IntegrityWatch(packet,{"name":"cpu","generated_pins":[]},control,{"pid":1,"creation_ticks":2},[],scanner,[],Journal(root/"journal"))

    def test_queue_overflow_is_terminal_and_retains_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=self.worker(Path(directory));worker.messages=queue.Queue(maxsize=1)
            worker.start();worker.thread.join(2)
            self.assertFalse(worker.thread.is_alive());self.assertEqual(worker.failure,"Full")
            with self.assertRaises(Stop):worker.check()
            self.assertEqual(worker.failure_evidence["generation"],1)
            with self.assertRaises(Stop):worker.finish()

    def test_foreign_collector_request_rejected_before_authentication_or_audit(self):
        from . import windows
        with tempfile.TemporaryDirectory() as directory:
            worker=self.worker(Path(directory));control=worker.control
            exclusive(control/"collector-identity.json",{"pid":2,"creation_ticks":3})
            exclusive(control/"integrity-target-request.json",{
                "schema":"physical-supervisor/integrity-request-v1","packet_sha256":"a"*64,"stage":"cpu",
                "supervisor":worker.supervisor,"role":"target","collector":{"pid":4,"creation_ticks":5},
                "source_preflight":{},"nonce":"b"*32,"requested_monotonic":time.monotonic()})
            with patch.object(windows.Process,"open",side_effect=AssertionError("Foreign owner must not be opened")) as opened:
                worker.start();worker.thread.join(2)
                with self.assertRaises(Stop):worker.check()
                opened.assert_not_called()
            self.assertIn("not the registered collector",worker.failure)
            with self.assertRaises(Stop):worker.finish()


@unittest.skipUnless(os.name=="nt","Native Windows root invalidation")
class NativeRootGuardTests(unittest.TestCase):
    def test_atomic_publisher_survives_immediate_no_delete_reader(self):
        from .windows import FileLock
        with tempfile.TemporaryDirectory() as directory:
            final=Path(directory)/"receipt.json";held=[];ready=threading.Event();release=threading.Event()
            def read():
                while not final.exists():time.sleep(.0001)
                held.append(FileLock(pin(final)));ready.set();release.wait(2)
                held[0].close()
            worker=threading.Thread(target=read);worker.start()
            try:
                exclusive(final,{"complete":"CPU native publication"})
                self.assertTrue(ready.wait(1));held[0].verify()
                with self.assertRaises(FileExistsError):exclusive(final,{"replacement":True})
            finally:release.set();worker.join(2)
    def test_add_delete_restore_is_terminal_and_ancestor_rename_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);root=parent/"closed";root.mkdir()
            roots=RootGuard({"runtime_roots":[{"path":str(root)}]})
            try:
                roots.check()
                with self.assertRaises(OSError):parent.rename(parent.with_name(parent.name+"-renamed"))
                extra=root/"extra";extra.write_text("CPU control");extra.unlink()
                with self.assertRaises(Stop):roots.check()
                with self.assertRaises(Stop):roots.check()
            finally:roots.close()

    def test_invalid_native_change_handle_fails_closed(self):
        from . import windows
        with tempfile.TemporaryDirectory() as directory:
            roots=RootGuard({"runtime_roots":[{"path":directory}]})
            try:
                windows.change_close(roots.changes[0]);roots.changes[0]=None
                with self.assertRaises(Stop):roots.check()
            finally:roots.close()

    def test_closed_guard_cannot_authorize_an_empty_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            roots=RootGuard({"runtime_roots":[{"path":directory}]});roots.close()
            with self.assertRaises(Stop):roots.check()

    def test_native_junction_creation_invalidates_and_alias_root_rejects(self):
        import _winapi
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);root=parent/"closed";root.mkdir();other=parent/"other";other.mkdir()
            roots=RootGuard({"runtime_roots":[{"path":str(root)}]})
            try:
                _winapi.CreateJunction(str(other),str(root/"alias"))
                with self.assertRaises(Stop):roots.check()
                with self.assertRaises(Stop):RootGuard({"runtime_roots":[{"path":str(root/"alias")}]})
            finally:roots.close()


@unittest.skipUnless(os.name=="nt","Native receipt sharing and ownership controls")
class NativeReceiptReadTests(unittest.TestCase):
    def publication_handle(self,path):
        from . import windows
        handle=windows.create_file(str(path),0x80000000|0x10000,1|2|4,None,3,0x80,None)
        self.assertNotIn(handle,(None,windows.c.c_void_p(-1).value))
        return handle

    def test_delete_metadata_owner_allows_complete_json_digest_without_retry(self):
        from . import windows
        with tempfile.TemporaryDirectory() as directory:
            pending=Path(directory)/"pending";final=Path(directory)/"receipt.json"
            data=b'{"complete":"CPU publication control"}\n';pending.write_bytes(data)
            handle=self.publication_handle(pending)
            try:
                os.rename(pending,final)
                with self.assertRaises(PermissionError):final.read_bytes()
                original=windows.create_file
                with patch.object(windows,"create_file",wraps=original) as opened:
                    self.assertEqual(read_json(final),{"complete":"CPU publication control"})
                    self.assertEqual(digest(final),hashlib.sha256(data).hexdigest())
                    self.assertEqual(pin(final)["size"],len(data))
                    self.assertEqual(opened.call_count,3)
                    for call in opened.call_args_list:
                        self.assertEqual(call.args[1:3],(0x80000000,1|2|4))
            finally:
                windows.close(handle)

    def test_partial_receipt_and_actual_sharing_denial_fail_immediately(self):
        from . import windows
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"receipt.json";path.write_bytes(b'{"incomplete":')
            handle=self.publication_handle(path)
            try:
                with self.assertRaises(ValueError):read_json(path)
            finally:windows.close(handle)
            handle=windows.create_file(str(path),0x80000000,0,None,3,0x80,None)
            self.assertNotIn(handle,(None,windows.c.c_void_p(-1).value))
            try:
                original=windows.create_file
                with patch.object(windows,"create_file",wraps=original) as opened:
                    with self.assertRaises(OSError):read_json(path)
                    self.assertEqual(opened.call_count,1)
            finally:windows.close(handle)

    def test_transient_reader_does_not_weaken_immutable_file_lock(self):
        from .windows import FileLock
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input";path.write_bytes(b"immutable CPU input")
            lock=FileLock(pin(path))
            try:
                with open_read(path) as stream:
                    self.assertFalse(os.get_inheritable(stream.fileno()))
                    self.assertFalse(stream.writable())
                    self.assertEqual(stream.read(),b"immutable CPU input")
                    with self.assertRaises(OSError):path.write_bytes(b"changed")
                    with self.assertRaises(OSError):path.unlink()
                lock.verify()
            finally:lock.close()

    def test_native_to_crt_failure_closes_only_current_owner(self):
        from . import windows
        import msvcrt
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input";path.write_bytes(b"CPU input")
            original=windows.close
            with patch.object(msvcrt,"open_osfhandle",side_effect=OSError("CPU conversion fault")), \
                 patch.object(windows,"close",wraps=original) as closed:
                with self.assertRaises(OSError),open_read(path):pass
                self.assertEqual(closed.call_count,1)
            original_close=os.close
            with patch.object(os,"fdopen",side_effect=OSError("CPU stream construction fault")), \
                 patch.object(os,"close",wraps=original_close) as descriptor_close, \
                 patch.object(windows,"close",wraps=original) as native_close:
                with self.assertRaises(OSError),open_read(path):pass
                self.assertEqual(descriptor_close.call_count,1);native_close.assert_not_called()

    def test_stream_failure_cannot_consume_descriptor_or_close_an_unrelated_fd(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input";path.write_bytes(b"CPU input")
            other=Path(directory)/"unrelated";other.write_bytes(b"unrelated CPU file")
            original=os.fdopen;unrelated=[];owned=[]
            def failed(descriptor,*args,**kwargs):
                owned.append(descriptor)
                self.assertIs(kwargs.get("closefd"),False)
                stream=original(descriptor,*args,**kwargs);stream.close()
                self.assertEqual(os.fstat(descriptor).st_size,len(b"CPU input"))
                unrelated.append(os.open(other,os.O_RDONLY|os.O_BINARY))
                self.assertNotEqual(unrelated[-1],descriptor)
                raise OSError("CPU failure after non-owning stream closed")
            try:
                with patch.object(os,"fdopen",side_effect=failed):
                    with self.assertRaises(OSError),open_read(path):pass
                with self.assertRaises(OSError):os.fstat(owned[0])
                self.assertEqual(os.read(unrelated[0],99),b"unrelated CPU file")
            finally:
                for descriptor in unrelated:os.close(descriptor)

@unittest.skipUnless(os.name=="nt","Native same-object exit transition controls")
class NativeExitRaceTests(cpu_fixture.TempCase):
    spawn=cpu_fixture.NativeWindowsTests.spawn

    @staticmethod
    def image_error(code=5,operation="QueryFullProcessImageNameW"):
        error=Stop("Synthetic native image-query failure")
        error.evidence={"operation":operation,"winerror":code}
        return error

    def test_exit_between_poll_and_image_query_never_terminates(self):
        from . import windows
        child,identity=self.spawn("pass");child.resume(identity)
        until=time.monotonic()+5
        while child.poll() is None and time.monotonic()<until:time.sleep(.01)
        self.assertEqual(child.poll(),0)
        # A real exited retained object, with the exact image-query failure
        # Windows may return during teardown after an earlier active poll.
        with patch.object(child,"poll",side_effect=[None,0]), \
             patch.object(windows,"get_path",return_value=False), \
             patch.object(windows.c,"get_last_error",return_value=5), \
             patch.object(windows,"terminate",side_effect=AssertionError("Exited object must not be terminated")) as kill:
            self.assertFalse(child.kill(identity));kill.assert_not_called()
        wrong={**identity,"creation_ticks":identity["creation_ticks"]+1}
        with patch.object(child,"poll",side_effect=[None,0]),patch.object(windows,"get_path",return_value=False):
            with self.assertRaises(Stop):child.kill(wrong)

    def test_live_image_query_failure_still_withholds_termination(self):
        from . import windows
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        with patch.object(windows,"get_path",return_value=False), \
             patch.object(windows.c,"get_last_error",return_value=5), \
             patch.object(windows,"terminate",side_effect=AssertionError("Unverified live object must not be terminated")) as kill:
            with self.assertRaises(Stop):child.kill(identity)
            kill.assert_not_called();self.assertIsNone(child.poll())

    def test_real_benign_exit_signal_after_reviewed_image_failure(self):
        from . import windows
        ready=self.root/"ready";release=self.root/"release"
        child,identity=self.spawn("from pathlib import Path;import time;Path("+repr(str(ready))+
            ").write_text('ready')\nwhile not Path("+repr(str(release))+").exists():time.sleep(.001)")
        child.resume(identity)
        until=time.monotonic()+5
        while not ready.exists() and time.monotonic()<until:time.sleep(.005)
        self.assertTrue(ready.exists())
        def deny(*args):release.write_text("exit");windows.c.set_last_error(5);return False
        with patch.object(windows,"get_path",side_effect=deny) as image, \
             patch.object(windows,"terminate",side_effect=AssertionError("No unverified termination")) as kill:
            self.assertFalse(child.kill(identity));image.assert_called_once();kill.assert_not_called()
        rows=child.take_exit_observations();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["requested_wait_milliseconds"],50)
        self.assertEqual(rows[0]["native_wait_result"],0)
        self.assertEqual(rows[0]["post_wait_creation_ticks"],identity["creation_ticks"])

    def test_missing_nonfinite_or_insufficient_budget_never_waits(self):
        from . import windows
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        native_wait=windows.wait
        for deadline in (None,float("nan"),float("inf"),time.monotonic()+.01):
            error=self.image_error()
            with self.subTest(deadline=deadline),patch.object(windows,"wait",wraps=native_wait) as wait:
                self.assertFalse(child.exited_owned(identity,error=error,settle_deadline=deadline))
                self.assertNotIn(50,[call.args[1] for call in wait.call_args_list])
                self.assertEqual(error.evidence["exit_observation"]["requested_wait_milliseconds"],0)
                self.assertIn("budget_checked_monotonic",error.evidence["exit_observation"])
        self.assertEqual(len(child.take_exit_observations()),4)

    def test_live_timeout_and_native_wait_failure_retain_facts_without_kill(self):
        from . import windows
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        error=self.image_error()
        self.assertFalse(child.exited_owned(identity,error=error,settle_deadline=time.monotonic()+1))
        self.assertEqual(error.evidence["exit_observation"]["native_wait_result"],258)
        native_wait=windows.wait
        def failed(handle,milliseconds):return 0xffffffff if milliseconds==50 else native_wait(handle,milliseconds)
        with patch.object(windows,"wait",side_effect=failed),patch.object(windows,"terminate") as kill:
            error=self.image_error()
            self.assertFalse(child.exited_owned(identity,error=error,settle_deadline=time.monotonic()+1))
            kill.assert_not_called();self.assertEqual(error.evidence["exit_observation"]["native_wait_result"],0xffffffff)

    def test_original_attestation_and_exact_error_are_required_even_after_exit(self):
        child,identity=self.spawn("pass");child.resume(identity)
        until=time.monotonic()+5
        while child.poll() is None and time.monotonic()<until:time.sleep(.01)
        self.assertEqual(child.poll(),0)
        for key,value in (("creation_ticks",identity["creation_ticks"]+1),("path","wrong path"),
                          ("sha256","f"*64),("parent_creation_ticks",0)):
            with self.subTest(key=key):
                self.assertFalse(child.exited_owned({**identity,key:value},error=self.image_error(),cleanup=True))
        for error in (Stop("Known identity mismatch"),self.image_error(6),self.image_error(5,"EnumProcessModulesEx")):
            self.assertFalse(child.exited_owned(identity,error=error,cleanup=True))
        child.verified_identity={**identity,"sha256":"f"*64}
        self.assertFalse(child.exited_owned(identity,error=self.image_error(),cleanup=True))

    def test_budget_overrun_after_positive_signal_cannot_classify_success(self):
        from . import windows
        child,identity=self.spawn("pass");child.resume(identity)
        until=time.monotonic()+5
        while child.poll() is None and time.monotonic()<until:time.sleep(.01)
        def delayed(handle,milliseconds):time.sleep(.06);return 0
        error=self.image_error()
        with patch.object(child,"poll",side_effect=[None,0]),patch.object(windows,"wait",side_effect=delayed):
            self.assertFalse(child.exited_owned(identity,error=error,settle_deadline=time.monotonic()+.055))
        row=error.evidence["exit_observation"]
        self.assertGreaterEqual(row["actual_wait_seconds"],.06)
        self.assertGreaterEqual(row["settle_deadline_monotonic"]-row["budget_checked_monotonic"],.05)
        self.assertLessEqual(row["budget_checked_monotonic"],row["wait_started_monotonic"])
        self.assertIn("budget expired",row["reason"])

    def test_pre_wait_failure_keeps_original_native_fault(self):
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        error=self.image_error()
        with patch.object(child,"poll",side_effect=Stop("Synthetic wait failure")):
            self.assertFalse(child.exited_owned(identity,error=error,settle_deadline=time.monotonic()+1))
        row=error.evidence["exit_observation"]
        self.assertEqual(row["original_error_evidence"]["winerror"],5)
        self.assertEqual(row["pre_wait_error"],"Synthetic wait failure")

    def test_known_identity_mismatch_is_not_erased_by_a_later_exit_signal(self):
        from . import windows
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        for key,value in (("path","wrong path"),("sha256","f"*64),("parent_creation_ticks",0)):
            with self.subTest(key=key),patch.object(child,"identity",return_value={**identity,key:value}), \
                 patch.object(child,"poll",side_effect=[None,0]),patch.object(windows,"terminate") as kill:
                with self.assertRaisesRegex(Stop,"identity/creation/parent/path/hash mismatch"):child.kill(identity)
                kill.assert_not_called()

    def test_reopened_inventory_candidate_requires_exact_retained_owner(self):
        from .windows import Process
        child,identity=self.spawn("pass");candidate=Process.open(child.pid)
        self.addCleanup(candidate.close);child.resume(identity)
        until=time.monotonic()+5
        while child.poll() is None and time.monotonic()<until:time.sleep(.01)
        self.assertEqual(child.poll(),0)
        self.assertFalse(candidate.exited_owned(identity,error=self.image_error(),authorized_by=candidate,cleanup=True))
        self.assertTrue(candidate.exited_owned(identity,error=self.image_error(),authorized_by=child,cleanup=True))
        child.verified_identity={**identity,"sha256":"f"*64}
        self.assertFalse(candidate.exited_owned(identity,error=self.image_error(),authorized_by=child,cleanup=True))
        child.verified_identity=identity

    def test_module_enumeration_and_hash_faults_cannot_become_exit_success(self):
        from .supervisor import ModuleWatch
        child,identity=self.spawn("import time;time.sleep(5)");child.resume(identity)
        module=self.root/"module.dll";module.write_bytes(b"CPU file, never loaded")
        packet={"module_policy":{"required_paths":[str(module)],"optional_paths":[]},"files":[pin(module)]}
        health=type("Health",(),{"fail":lambda self,error:None})()
        watcher=ModuleWatch(packet,child,identity,Journal(self.root/"journal"),health)
        with patch.object(child,"poll",side_effect=[None,0]),patch.object(child,"modules",side_effect=Stop("EnumModules fault")):
            with self.assertRaisesRegex(Stop,"EnumModules fault"):watcher.sample()
        module.write_bytes(b"Changed CPU module")
        with patch.object(child,"modules",return_value=[normalized(module)]), \
             patch.object(child,"exited_owned",side_effect=AssertionError("Hash fault is not an exit transition")):
            with self.assertRaisesRegex(Stop,"module differs"):watcher.sample()


class ResumeReceiptTests(cpu_fixture.TempCase):
    def test_resume_exception_eligibility_needs_complete_bound_finite_receipt(self):
        from .supervisor import resume_receipt
        identity={"pid":123,"creation_ticks":456};path=self.root/"target-resumed.json"
        self.assertIsNone(resume_receipt(self.root,identity))
        good={"identity":identity,"utc":"synthetic CPU time","resume_native_call_attempt_monotonic":time.monotonic()}
        exclusive(path,good);self.assertEqual(resume_receipt(self.root,identity),good)
        for delta in ({"identity":{}},{"resume_native_call_attempt_monotonic":float("nan")},
                      {"resume_native_call_attempt_monotonic":True},{"extra":1}):
            path.unlink();path.write_text(__import__("json").dumps({**good,**delta}))
            with self.subTest(delta=delta),self.assertRaises(Stop):resume_receipt(self.root,identity)
        path.write_text('{"identity":')
        with self.assertRaises(ValueError):resume_receipt(self.root,identity)


@unittest.skipUnless(os.name=="nt","Native benign CPU full-control integration")
class LivenessIntegrationTests(unittest.TestCase):
    setUp=fixture.EngineIntegrationTests.setUp
    tearDown=fixture.EngineIntegrationTests.tearDown
    run_engine=fixture.EngineIntegrationTests.run_engine
    spawn_count=fixture.EngineIntegrationTests.spawn_count
    fault=fixture.EngineIntegrationTests.fault
    config_pins=fixture.EngineIntegrationTests.config_pins

    def realistic_packet(self):
        # Eight closed roots and exactly1,359 immutable pins, matching the Q1
        # topology in scale while containing only public synthetic CPU bytes.
        for index in range(5):
            directory=self.root/f"closed-{index}";directory.mkdir()
            self.packet["runtime_roots"].append({"path":str(directory),"files":[]})
        missing=1359-len(self.packet["files"])
        for index in range(missing):
            row=self.packet["runtime_roots"][3+index%5]
            path=Path(row["path"])/f"cpu-{index:04d}.txt";path.write_text(f"synthetic CPU pin {index}")
            row["files"].append(str(path));self.packet["files"].append(pin(path))
        self.assertEqual(len(self.packet["files"]),1359)
        self.assertEqual(len(self.packet["runtime_roots"]),8)

    def heartbeats(self):
        return [read_json(path) for path in sorted((self.root/"control/00-compositing").glob("heartbeat-*.json"))]

    def test_realistic_closed_topology_full_parent_collector_registration(self):
        self.realistic_packet()
        self.fault("none","import time;from pathlib import Path;Path('marker.txt').write_text('CPU benign success');time.sleep(2.2)")
        result=self.run_engine()
        self.assertEqual(result["status"],"COLLECTED_PENDING_ACCEPTANCE",result)
        self.assertEqual(self.spawn_count(),3)
        rows=self.heartbeats();self.assertGreater(len(rows),3)
        self.assertLess(max(b["monotonic"]-a["monotonic"] for a,b in zip(rows,rows[1:])),2)
        self.assertTrue(all("integrity_generation" in row for row in rows))
        proof=read_json(self.root/"control/00-compositing/integrity-target-proof.json")
        self.assertEqual(proof["request"]["role"],"target")
        self.assertTrue((self.root/"control/00-compositing/target-ack.json").exists())

    def test_slow_successful_deep_checks_do_not_suspend_control_heartbeat(self):
        self.realistic_packet()
        original=IntegrityWatch.audit
        def slow(instance):
            time.sleep(2.05)
            return original(instance)
        self.fault("none","import time;from pathlib import Path;Path('marker.txt').write_text('CPU benign success');time.sleep(2.2)")
        with patch.object(IntegrityWatch,"audit",new=slow):result=self.run_engine()
        self.assertEqual(result["status"],"COLLECTED_PENDING_ACCEPTANCE",result)
        rows=self.heartbeats()
        self.assertLess(max(b["monotonic"]-a["monotonic"] for a,b in zip(rows,rows[1:])),2)

    def test_realistic_topology_reaches_native_boundary_without_target_creation(self):
        from . import supervisor
        self.realistic_packet()
        original=supervisor.Process.spawn
        marker=self.root/"no-target-boundary.json"
        def collector_only(argv,cwd,stdout,stderr,**kwargs):
            # The sole permitted native creation is the benign CPU collector.
            # Inside it all three native launch APIs fail before target creation.
            self.assertEqual(argv[0],self.packet["python"])
            prefix=("import sys;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[2]))+");\n"
                "from tools.physical_supervisor.windows import Process\n"
                "from tools.physical_supervisor.common import Stop,exclusive\n"
                "import _winapi,subprocess\n"
                "def native_denied(*a,**k): raise Stop('CPU no-target native API trap')\n"
                "def target_denied(*a,**k):\n"
                " exclusive("+repr(str(marker))+",{'synthetic_cpu_only':True,'before_native_create':True})\n"
                " raise Stop('CPU boundary reached; target deliberately never created')\n"
                "Process.spawn=staticmethod(target_denied)\n"
                "_winapi.CreateProcess=native_denied\nsubprocess.Popen=native_denied\n")
            altered=list(argv);altered[-1]=prefix+argv[-1]
            return original(altered,cwd,stdout,stderr,**kwargs)
        with patch.object(supervisor.Process,"spawn",side_effect=collector_only):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        self.assertEqual(read_json(marker),{"synthetic_cpu_only":True,"before_native_create":True})
        self.assertFalse((self.root/"control/00-compositing/target-request.json").exists())
        rows=[read_json(path) for path in (self.root/"control/journal").glob("*-final-job-inventory.json")]
        self.assertEqual(rows[0]["value"]["remaining_pids"],[])

    def test_worker_failure_blocks_first_collector(self):
        with patch.object(IntegrityWatch,"audit",side_effect=OSError("synthetic root audit denied")):
            result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)

    def test_silent_worker_death_blocks_first_collector(self):
        with patch.object(IntegrityWatch,"loop",new=lambda self:None):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)

    def test_hung_deep_audit_is_bounded_and_never_spawns(self):
        release=threading.Event();calls=[]
        def hung(instance):calls.append(1);release.wait(12);return {}
        try:
            started=time.monotonic()
            with patch.object(IntegrityWatch,"audit",new=hung):result=self.run_engine()
            self.assertLess(time.monotonic()-started,12)
            self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)
            self.assertEqual(len(calls),1)
        finally:release.set()

    def test_expired_target_boundary_proof_never_creates_target(self):
        from . import supervisor
        original=IntegrityWatch.loop
        def delayed(instance):
            # Simulate delayed atomic wrapper publication. The already completed
            # generation must expire; no request/re-audit retries are permitted.
            from . import integrity
            publish=integrity.exclusive
            def delay(path,value,**kwargs):
                if Path(path).name=="integrity-target-proof.json":time.sleep(.6)
                return publish(path,value,**kwargs)
            with patch.object(integrity,"exclusive",side_effect=delay):original(instance)
        with patch.object(IntegrityWatch,"loop",new=delayed):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        self.assertFalse((self.root/"control/00-compositing/target-request.json").exists())

    def test_slow_shared_gate_cannot_suspend_deadline_control(self):
        from . import supervisor
        original=supervisor._registration;held=[];threads=[]
        def intercept(*args,**kwargs):
            value=original(*args,**kwargs)
            if not held and value[0] is not None:
                held.append(1)
                def block():
                    with Gate(self.packet["stop_root"],read_json(self.root/"control/packet.json")["packet_sha256"]):time.sleep(1.4)
                worker=threading.Thread(target=block);threads.append(worker);worker.start()
            return value
        self.fault("none","import time;time.sleep(3)")
        try:
            with patch.object(supervisor,"_registration",side_effect=intercept):result=self.run_engine()
            self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        finally:
            for worker in threads:worker.join(2)

    def test_collector_contains_when_supervisor_stalls_holding_gate(self):
        from . import supervisor
        original=supervisor.Process.poll;stalled=[];contained=[]
        self.fault("none","import time;time.sleep(4)")
        def poll(process):
            control=self.root/"control/00-compositing"
            if not stalled and (control/"target-resumed.json").exists() and process.pid==read_json(control/"collector-identity.json")["pid"]:
                stalled.append(1)
                with Gate(self.packet["stop_root"],read_json(self.root/"control/packet.json")["packet_sha256"]):
                    time.sleep(2.4)
                    identity=read_json(control/"target-request.json")["target"]
                    target=supervisor.Process.open(identity["pid"])
                    try:contained.append(original(target) is not None)
                    finally:target.close()
            return original(process)
        with patch.object(supervisor.Process,"poll",new=poll):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(stalled,[1]);self.assertEqual(contained,[True])
        self.assertEqual(self.spawn_count(),1)

    def test_slow_mutable_publication_expires_proof_before_native_resume(self):
        from . import supervisor
        self.config_pins();original=supervisor.Process.spawn
        def collector_with_delay(argv,cwd,stdout,stderr,**kwargs):
            prefix=("import sys;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[2]))+");\n"
                "import time\nfrom pathlib import Path\n"
                "import tools.physical_supervisor.collector as adapter\n"
                "publish=adapter.exclusive\n"
                "def delayed(path,value,**kwargs):\n"
                " if Path(path).name=='mutable-config-release-ready.json':time.sleep(.6)\n"
                " return publish(path,value,**kwargs)\n"
                "adapter.exclusive=delayed\n")
            altered=list(argv);altered[-1]=prefix+argv[-1]
            return original(altered,cwd,stdout,stderr,**kwargs)
        with patch.object(supervisor.Process,"spawn",side_effect=collector_with_delay):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        self.assertTrue((self.root/"control/00-compositing/target-request.json").exists())
        self.assertFalse((self.root/"control/00-compositing/target-resumed.json").exists())

    def test_slow_mutable_handle_close_expires_proof_before_native_resume(self):
        from . import supervisor
        self.config_pins();original=supervisor.Process.spawn
        live=str(Path(self.stages[0]["capture"]["out"])/"fixture.ini")
        def collector_with_delay(argv,cwd,stdout,stderr,**kwargs):
            prefix=("import sys;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[2]))+");\n"
                "import time\nfrom tools.physical_supervisor.windows import FileLock\n"
                "close=FileLock.release_mutable\n"
                "def delayed(lock):\n"
                " if lock.handle and lock.row['path']=="+repr(live)+":time.sleep(.6)\n"
                " return close(lock)\n"
                "FileLock.release_mutable=delayed\n")
            altered=list(argv);altered[-1]=prefix+argv[-1]
            return original(altered,cwd,stdout,stderr,**kwargs)
        with patch.object(supervisor.Process,"spawn",side_effect=collector_with_delay):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        self.assertTrue((self.root/"control/00-compositing/target-request.json").exists())
        self.assertFalse((self.root/"control/00-compositing/target-resumed.json").exists())

    def test_failed_mutable_close_never_records_release_or_calls_native_resume(self):
        from . import supervisor
        self.config_pins();original=supervisor.Process.spawn
        live=str(Path(self.stages[0]["capture"]["out"])/"fixture.ini")
        attempted=self.root/"unexpected-native-resume.json"
        def collector_with_failure(argv,cwd,stdout,stderr,**kwargs):
            prefix=("import sys;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[2]))+");\n"
                "import ctypes\nimport tools.physical_supervisor.windows as native\n"
                "from tools.physical_supervisor.common import exclusive\n"
                "release=native.FileLock.release_mutable\n"
                "def failed_release(lock):\n"
                " if lock.row['path']!="+repr(live)+":return release(lock)\n"
                " original=native.close\n"
                " def denied(handle):\n"
                "  if handle==lock.handle:ctypes.set_last_error(6);return False\n"
                "  return original(handle)\n"
                " native.close=denied\n"
                " try:return release(lock)\n"
                " finally:native.close=original\n"
                "def forbidden(handle):\n"
                " exclusive("+repr(str(attempted))+",{'native_resume_attempted':True})\n"
                " raise AssertionError('Failed mutable close must withhold ResumeThread')\n"
                "native.FileLock.release_mutable=failed_release\nnative.resume_thread=forbidden\n")
            altered=list(argv);altered[-1]=prefix+argv[-1]
            return original(altered,cwd,stdout,stderr,**kwargs)
        with patch.object(supervisor.Process,"spawn",side_effect=collector_with_failure):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),1)
        control=self.root/"control/00-compositing"
        self.assertTrue((control/"target-request.json").exists())
        self.assertTrue((control/"mutable-config-release-ready.json").exists())
        self.assertFalse((control/"mutable-config-released.json").exists())
        self.assertFalse((control/"target-resumed.json").exists());self.assertFalse(attempted.exists())
        records=[read_json(p) for p in (self.root/"control/journal").glob("*-final-job-inventory.json")]
        self.assertEqual(records[0]["value"]["remaining_pids"],[])

    def test_membership_change_after_generation_blocks_target_creation(self):
        original=IntegrityWatch.audit;changed=[]
        def change(instance):
            result=original(instance)
            if not changed:
                changed.append(1);(Path(self.packet["runtime_roots"][0]["path"])/"unexpected.dll").write_text("CPU unexpected")
            return result
        with patch.object(IntegrityWatch,"audit",new=change):result=self.run_engine()
        self.assertEqual(result["status"],"FAILED_STOP");self.assertEqual(self.spawn_count(),0)


if __name__=="__main__":unittest.main()
