"""Real oracle preparation/PNG import path; zero renderer or collector Git children.

Fixtures and pure regeneration are real. The executable/IWAD/package and parent
supervisor transcript are explicitly synthetic CPU test inputs. Git runs only
outside the protected adapter while preparing the ordinary authored fixture.
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from .collector import prepare_subprocess_adapter,run_oracle,source_proof
from .common import Stop,exclusive,pin,read_json,source_check_requests,utc,verify_oracle_python_pins
from .prepare import frozen_oracle
from .test_integration import synthetic_source_checks
from .test_supervisor import TempCase


class NoTarget(Stop):
    pass


class RealOracleAdapterTests(TempCase):
    def test_stale_pf_package_is_cleared_before_frozen_import(self):
        root=Path(__file__).resolve().parents[2]
        stale=types.ModuleType("tools.pf_oracle");stale.__path__=[str(self.root/"wrong-source")]
        helper=types.ModuleType("tools.pf_oracle.prepare_freeze_view_fixture")
        helper.__file__=str(self.root/"wrong-source/stale-helper.py")
        with patch.dict(sys.modules,{"tools.pf_oracle":stale,"tools.pf_oracle.prepare_freeze_view_fixture":helper}):
            run=frozen_oracle(root)
            prepare=run.preparation_module()
            self.assertEqual(Path(run.__file__).resolve(),root/"tools/renderer_oracle/run.py")
            self.assertEqual(Path(prepare.pf_view.__file__).resolve(),root/"tools/pf_oracle/prepare_freeze_view_fixture.py")

    def setup_packet(self):
        root=Path(__file__).resolve().parents[2]
        run=frozen_oracle(root)
        prepared=self.root/"prepared"
        manifest=run.preparation_module().prepare(prepared,["compositing"])
        commit=manifest["source_identity"]["git_commit"]
        git=shutil.which("git")
        tree=subprocess.run([git,"rev-parse","HEAD^{tree}"],cwd=root,capture_output=True,check=True,text=True).stdout.strip()
        runtime=self.root/"runtime";runtime.mkdir()
        exe=runtime/"SYNTHETIC_NEVER_EXECUTED.exe";exe.write_bytes(b"not an executable; no renderer launches")
        (runtime/"vkdoom.pk3").write_bytes(b"synthetic engine package; never loaded")
        iwad=self.root/"synthetic.wad";iwad.write_bytes(b"synthetic IWAD; never loaded")
        gate=self.gate()
        expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()
        packet={"source":{"commit":commit,"tree":tree},"oracle_source_root":str(root),"git":git,
                "renderer":str(exe),"renderer_sha256":pin(exe)["sha256"],"packet_sha256":"a"*64,
                "stop_root":str(gate.root),"expires_utc":expiry,
                "declared_version_utf8":"ShadeDoomVK synthetic expected declaration\nCommit: "+commit+"\nWorking tree: clean\n"}
        directories=[root/"tools/renderer_oracle",root/"tools/pf_oracle",runtime,prepared]
        packet["runtime_roots"]=[{"path":str(directory),"files":[str(p) for p in directory.rglob("*") if p.is_file()]}
                                  for directory in directories]
        packet["files"]=[pin(path) for row in packet["runtime_roots"] for path in row["files"]]+[pin(iwad),pin(git)]
        out=self.root/"capture"
        stage={"name":"compositing","capture":{"exe":str(exe),"iwad":str(iwad),"prepared":str(prepared),"out":str(out),
               "scene":"compositing","mode":"state","frames":1,"warmup":120,"timeout":180,"gpu":False,
               "include_stress":True,"image_policy":"exact","extent":"640x480","expected_commit":commit,"require_clean":True}}
        control=self.root/"control";control.mkdir()
        identity={"synthetic_cpu_test_supervisor":True}
        exclusive(control/"supervisor-identity.json",identity)
        proof={"schema":"physical-supervisor/source-preflight-v1","packet_sha256":"a"*64,"stage":stage["name"],
               "source":packet["source"],"root":str(root),"git":pin(git),"supervisor":identity,
               "checks":synthetic_source_checks(packet),"utc":utc(),"test_scope":"synthetic parent transcript; no physical evidence"}
        exclusive(control/"source-preflight.json",proof)
        return packet,stage,control,pin(control/"source-preflight.json")

    def test_real_prepared_capture_reaches_target_gate_without_any_process(self):
        packet,stage,control,receipt=self.setup_packet()
        with patch("subprocess.Popen",side_effect=AssertionError("No process may launch inside CPU oracle adapter")) as native, \
             patch("tools.physical_supervisor.collector.gated_target",side_effect=NoTarget("CPU boundary reached; target not created")) as target:
            with self.assertRaises(NoTarget):run_oracle(packet,stage,control,receipt)
        native.assert_not_called();target.assert_called_once()
        declared=read_json(control/"prepared-commit-existence.json")
        self.assertEqual(declared["provenance"],"DECLARED_FROM_SEALED_PARENT_GIT_CHECK")
        self.assertIs(declared["actual_collector_git_process_created"],False)
        self.assertTrue((Path(stage["capture"]["out"])/"request.json").is_file())
        self.assertFalse((control/"target-request.json").exists())
        # Exercise the actual dynamic decoder import too; its file must be in
        # the closed frozen PF root and loading it cannot spawn a process.
        images=importlib.import_module("tools.renderer_oracle.images")
        with patch("subprocess.Popen",side_effect=AssertionError("Decoder import cannot launch a process")):
            decoder=images._decoder()
        decoder_path=Path(decoder.__code__.co_filename).resolve()
        self.assertEqual(decoder_path,Path(packet["oracle_source_root"])/"tools/pf_oracle/run_freeze_dense_runtime.py")
        self.assertIn(str(decoder_path),{row["path"] for row in packet["files"]})

    def test_only_exact_preverified_preparation_query_is_admitted_once(self):
        packet,stage,control,receipt=self.setup_packet()
        proxy=prepare_subprocess_adapter(packet,stage,control,receipt)
        expected=["git","cat-file","-e",packet["source"]["commit"]+"^{commit}"]
        with patch("subprocess.Popen",side_effect=AssertionError("No native child")) as native:
            for api in ("Popen","call","check_call","check_output","getoutput","getstatusoutput"):
                with self.subTest(api=api),self.assertRaises(Stop):getattr(proxy,api)(["git","status"])
            for argv,kwargs in ((["git","status"],{"cwd":packet["oracle_source_root"],"capture_output":True,"check":True}),
                                (expected,{"cwd":self.root,"capture_output":True,"check":True}),
                                (expected,{"cwd":packet["oracle_source_root"],"capture_output":True,"check":False}),
                                (expected,{"cwd":packet["oracle_source_root"],"capture_output":True,"check":True,"timeout":10})):
                with self.subTest(argv=argv,kwargs=kwargs),self.assertRaises(Stop):proxy.run(argv,**kwargs)
            self.assertEqual(proxy.run(expected,cwd=packet["oracle_source_root"],capture_output=True,check=True).returncode,0)
            with self.assertRaises(Stop):proxy.run(expected,cwd=packet["oracle_source_root"],capture_output=True,check=True)
            native.assert_not_called()

    def test_wrong_stale_or_modified_parent_proof_is_rejected(self):
        packet,stage,control,receipt=self.setup_packet()
        proof=read_json(receipt["path"])
        for index,mutation in enumerate((lambda p:p.update(packet_sha256="b"*64),lambda p:p.update(stage="wrong-stage"),
                                         lambda p:p["source"].update(commit="c"*40),
                                         lambda p:p["checks"].pop(),lambda p:p["supervisor"].update(stale=True))):
            changed=copy.deepcopy(proof);mutation(changed)
            case=self.root/f"proof-case-{index}";case.mkdir()
            exclusive(case/"supervisor-identity.json",proof["supervisor"])
            exclusive(case/"source-preflight.json",changed)
            with self.assertRaises(Stop):source_proof(packet,stage,case,pin(case/"source-preflight.json"))
        Path(receipt["path"]).write_bytes(Path(receipt["path"]).read_bytes()+b" ")
        with self.assertRaises(Stop):source_proof(packet,stage,control,receipt)

    def test_missing_frozen_pf_or_dynamic_decoder_pin_rejects_before_import(self):
        packet,stage,control,receipt=self.setup_packet()
        decoder=str(Path(packet["oracle_source_root"])/"tools/pf_oracle/run_freeze_dense_runtime.py")
        packet["files"]=[row for row in packet["files"] if row["path"]!=decoder]
        with self.assertRaises(Stop):verify_oracle_python_pins(packet)


if __name__=="__main__":unittest.main()
