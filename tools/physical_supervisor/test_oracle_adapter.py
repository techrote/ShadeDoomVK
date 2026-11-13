"""Real oracle preparation/PNG import path; zero renderer or collector Git children.

Fixtures and pure regeneration are real. The executable/IWAD/package and parent
supervisor transcript are explicitly synthetic CPU test inputs. Git and lazy
read-only platform metadata probes run outside the protected adapter during
ordinary fixture preparation; no renderer or Vulkan is executed.
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
from .common import Stop,environment_policy,exclusive,pin,read_json,utc,verify_oracle_python_pins,verify_source
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

    def setup_packet(self, *, split_source=False):
        # Match production execute(), including Windows TEMP short-name aliases.
        self.root=self.root.resolve(strict=True)
        root=Path(__file__).resolve().parents[2]
        git=shutil.which("git")
        split = {}
        if split_source:
            # Keep the current real oracle files, but create fresh Git history.
            # Hosted pull request checkouts may contain only their merge commit.
            def git_at(cwd, *args):
                return subprocess.check_output([git, "-C", str(cwd), *args], text=True).strip()

            renderer = self.root / "renderer-source"
            renderer.mkdir()
            git_at(renderer, "init", "-q")
            git_at(renderer, "-c", "user.name=CPU fixture", "-c", "user.email=cpu@example.invalid",
                   "commit", "-q", "--allow-empty", "-m", "Synthetic renderer identity")
            renderer_commit, renderer_tree = git_at(renderer, "rev-parse", "HEAD", "HEAD^{tree}").splitlines()
            oracle = self.root / "oracle-source"
            git_at(renderer, "clone", "-q", str(renderer), str(oracle))
            # Copy the actual oracle source inventory and module dependencies
            # without importing unrelated engine files or ignored outputs.
            preparation = frozen_oracle(root).preparation_module()
            catalog = preparation.load_catalog()
            inputs = set(preparation._source_inventory(catalog, root))
            for contract in catalog["cpu_contracts"].values():
                inputs.add(contract["test_path"])
                if "retained_fixture" in contract:
                    inputs.add(contract["retained_fixture"])
            for directory in ("tools/renderer_oracle", "tools/pf_oracle"):
                inputs.update(path.relative_to(root).as_posix() for path in (root / directory).rglob("*.py"))
            for name in sorted(inputs):
                path = oracle / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / name, path)
            git_at(oracle, "-c", "core.autocrlf=false", "add", "-f", ".")
            git_at(oracle, "-c", "user.name=CPU fixture", "-c", "user.email=cpu@example.invalid",
                   "commit", "-q", "-m", "Frozen real oracle source")
            oracle_commit, oracle_tree = git_at(oracle, "rev-parse", "HEAD", "HEAD^{tree}").splitlines()
            split = {"renderer_source_root": str(renderer),
                     "oracle_source": {"commit": oracle_commit, "tree": oracle_tree}}
            source = {"commit": renderer_commit, "tree": renderer_tree}
            root = oracle

        run=frozen_oracle(root)
        # Linux Python3.10 can lazily run uname for real platform metadata.
        # Warm its shared stdlib caches before the strict zero-process trap.
        run.host_profile()
        prepared=self.root/"prepared"
        scene = "lights-one-shadow-off" if split_source else "compositing"
        manifest=run.preparation_module().prepare(prepared,[scene])
        commit=manifest["source_identity"]["git_commit"]
        if split_source:
            self.assertEqual(commit, split["oracle_source"]["commit"])
        else:
            tree=subprocess.check_output([git,"rev-parse","HEAD^{tree}"],cwd=root,text=True).strip()
            source = {"commit": commit, "tree": tree}
        runtime=self.root/"runtime";runtime.mkdir()
        exe=runtime/"SYNTHETIC_NEVER_EXECUTED.exe";exe.write_bytes(b"not an executable; no renderer launches")
        (runtime/"vkdoom.pk3").write_bytes(b"synthetic engine package; never loaded")
        iwad=self.root/"synthetic.wad";iwad.write_bytes(b"synthetic IWAD; never loaded")
        gate=self.gate()
        expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()
        packet={"source":source,"oracle_source_root":str(root),"git":git,**split,
                "environment_policy":environment_policy(),
                "renderer":str(exe),"renderer_sha256":pin(exe)["sha256"],"packet_sha256":"a"*64,
                "stop_root":str(gate.root),"expires_utc":expiry,
                "declared_version_utf8":"ShadeDoomVK synthetic expected declaration\nCommit: "+source["commit"]+"\nWorking tree: clean\n"}
        directories=[root/"tools/renderer_oracle",root/"tools/pf_oracle",runtime,prepared]
        packet["runtime_roots"]=[{"path":str(directory),"files":[str(p) for p in directory.rglob("*") if p.is_file()]}
                                  for directory in directories]
        packet["files"]=[pin(path) for row in packet["runtime_roots"] for path in row["files"]]+[pin(iwad),pin(git)]
        out=self.root/"capture"
        stage={"name":scene,"capture":{"exe":str(exe),"iwad":str(iwad),"prepared":str(prepared),"out":str(out),
               "scene":scene,"mode":"state","frames":1,"warmup":120,"timeout":180,"gpu":False,
               "include_stress":True,"image_policy":"exact","extent":"1904x1001" if split_source else "640x480",
               "expected_commit":source["commit"],"require_clean":True}}
        control=self.root/"control";control.mkdir()
        identity={"synthetic_cpu_test_supervisor":True}
        exclusive(control/"supervisor-identity.json",identity)
        proof={"schema":"physical-supervisor/source-preflight-v1","packet_sha256":"a"*64,"stage":stage["name"],
               "source":packet["source"],"root":str(root),"git":pin(git),"supervisor":identity,
               "checks":verify_source(packet) if split_source else synthetic_source_checks(packet),
               "utc":utc(),"test_scope":"CPU test parent transcript; no physical evidence"}
        exclusive(control/"source-preflight.json",proof)
        return packet,stage,control,pin(control/"source-preflight.json")

    def test_fixture_root_is_canonical_but_proof_guard_still_rejects_alias(self):
        canonical=self.root.resolve(strict=True)
        (canonical/"spelling").mkdir()
        self.root=canonical/"spelling"/".."
        packet,stage,control,receipt=self.setup_packet()
        self.assertEqual(self.root,canonical)
        self.assertEqual(control,canonical/"control")
        self.assertEqual(Path(receipt["path"]),control/"source-preflight.json")
        source_proof(packet,stage,control,receipt)
        (control/"spelling").mkdir()
        with self.assertRaises(Stop):source_proof(packet,stage,control/"spelling"/"..",receipt)

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

    def test_distinct_oracle_preparation_reaches_target_gate_without_any_process(self):
        packet, stage, control, receipt = self.setup_packet(split_source=True)
        self.assertNotEqual(packet["source"]["commit"], packet["oracle_source"]["commit"])
        with (
            patch("subprocess.Popen", side_effect=AssertionError("No collector subprocess")) as native,
            patch("tools.physical_supervisor.collector.gated_target", side_effect=NoTarget("CPU target boundary")) as target,
        ):
            with self.assertRaises(NoTarget):
                run_oracle(packet, stage, control, receipt)
        native.assert_not_called()
        target.assert_called_once()
        declared = read_json(control / "prepared-commit-existence.json")
        self.assertEqual(declared["argv"], ["git", "cat-file", "-e", packet["oracle_source"]["commit"] + "^{commit}"])
        self.assertFalse(declared["actual_collector_git_process_created"])
        argv = target.call_args.args[3]
        self.assertEqual(argv[argv.index("-width") + 1], "1904")
        self.assertEqual(argv[argv.index("-height") + 1], "1001")
        script = (Path(stage["capture"]["out"]) / "capture.cfg").read_bytes()
        self.assertIn(b"; vid_setsize 1904 1001; ", script)
        self.assertNotIn(b"; vid_setsize 640 480; ", script)
        self.assertFalse((control / "target-request.json").exists())

    def test_real_adapter_preregisters_exact_support_before_target_boundary(self):
        packet,stage,control,receipt=self.setup_packet()
        run=frozen_oracle(packet["oracle_source_root"])
        support=Path(packet["renderer"]).parent/"id24res.wad"
        support.write_bytes(b"Synthetic support WAD; never loaded")
        declaration={"iwad":run.pin(stage["capture"]["iwad"]),"packages":[run.pin(support)]}
        packet["iwad_support"]=declaration
        stage["capture"]["iwad_support"]=declaration
        packet["files"].append(pin(support))
        with patch("subprocess.Popen",side_effect=AssertionError("No native process permitted")) as native, \
             patch("tools.physical_supervisor.collector.gated_target",side_effect=NoTarget("CPU target boundary")) as target:
            with self.assertRaises(NoTarget):run_oracle(packet,stage,control,receipt)
        native.assert_not_called();target.assert_called_once()
        request=read_json(Path(stage["capture"]["out"])/"request.json")
        self.assertEqual(request["iwad_support"],declaration)
        self.assertEqual(request["packages"][str(support)],declaration["packages"][0])

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
