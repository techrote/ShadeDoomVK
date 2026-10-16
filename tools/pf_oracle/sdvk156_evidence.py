#!/usr/bin/env python3
"""Collect atlas allocation-incarnation CPU evidence; never launches a renderer."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from tools.pf_oracle.fixture_runner import compilation_command, select_compiler
from tools.pf_oracle.tests.test_sdvk156_atlas_identity import build, build_geometry, CASES, MUTANTS, DATA
from tools.pf_oracle.tests.test_sdvk014_identity_audit import build as build_historical, CASES as AUDIT_CASES
from tools.pf_oracle.tests.sdvk156_source import ROOT, RETAINED, retained_files

PRODUCTION_FILES = (
    'src/common/rendering/hwrenderer/data/hw_rectpacker.h',
    'src/common/rendering/hwrenderer/data/hw_rectpacker.cpp',
    'src/common/rendering/hwrenderer/data/hw_lightmaptile.h',
    'src/common/rendering/hwrenderer/data/hw_levelmesh.h',
    'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp',
    'src/common/rendering/vulkan/vk_lightmapper.h',
    'src/common/rendering/vulkan/vk_lightmapper.cpp',
    'src/rendering/hwrenderer/doom_levelmesh.cpp',
    'src/rendering/hwrenderer/doom_levelmesh.h',
    'src/rendering/hwrenderer/hw_vertexbuilder.cpp',
    'src/rendering/hwrenderer/scene/hw_decal.cpp',
    'src/rendering/hwrenderer/scene/hw_drawinfo.cpp',
    'src/rendering/hwrenderer/scene/hw_drawinfo.h',
    'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp',
    'src/maploader/maploader.cpp',
    'src/commandlets/lightmapcmd.cpp',
    'src/common/utility/bounds.cpp',
)
TEST_FILES = (
    'tools/pf_oracle/sdvk156_evidence.py',
    'tools/pf_oracle/sdvk014_identity_audit.py',
    'tools/pf_oracle/tests/sdvk156_source.py',
    'tools/pf_oracle/tests/test_sdvk156_atlas_identity.py',
    'tools/pf_oracle/tests/sdvk156_atlas_identity_fixture.cpp',
    'tools/pf_oracle/tests/sdvk156_geometry_equivalence_fixture.cpp',
    'tools/pf_oracle/tests/sdvk014_identity_audit_fixture.cpp',
    'tools/pf_oracle/tests/test_sdvk014_identity_audit.py',
    'tools/pf_oracle/tests/test_sdvk014_atlas_lifecycle.py',
    'tools/pf_oracle/tests/test_sdvk014_tile_lifecycle.py',
    'tools/pf_oracle/tests/sdvk014_atlas_fixture.cpp',
    'tools/pf_oracle/tests/sdvk014_tile_fixture.cpp',
    'tools/pf_oracle/tests/sdvk014_source.py',
    'tools/pf_oracle/fixture_runner.py',
)


def run_record(exe: Path, case: str, expected: int=0, reason: str|None=None, **kwargs) -> dict:
    reason=reason or 'PASS '+case
    result=subprocess.run([str(exe),case],text=True,capture_output=True,timeout=30,**kwargs)
    if result.returncode!=expected or reason not in result.stdout+result.stderr:
        raise RuntimeError(f'Unexpected {case}: {result.returncode}\n{result.stdout}{result.stderr}')
    return {'case':case,'returncode':result.returncode,'expected_reason':reason,
            'stdout':result.stdout,'stderr':result.stderr}


def collect(sanitizers: bool=False) -> dict:
    pins=retained_files()
    with tempfile.TemporaryDirectory(prefix='sdvk156-evidence-') as tmp:
        tmp=Path(tmp);current_dir=tmp/'current';current=build(current_dir)
        positives=[run_record(current,case) for case in CASES]
        old=build_historical(tmp/'retained-audit')
        historical=[run_record(old,case,*AUDIT_CASES[case]) for case in AUDIT_CASES if case.startswith('atlas-')]
        mutations=[]
        for name,(mutate,case,reason) in MUTANTS.items():
            exe=build(tmp/name,mutate)
            mutations.append({'mutation':name,**run_record(exe,case,11,reason)})
        traces=[];sizes={}
        for original in (True,False):
            exe=build_geometry(tmp/('geometry-old' if original else 'geometry-current'),original)
            trace=subprocess.run([str(exe)],capture_output=True,check=True,timeout=30)
            traces.append(trace.stdout)
            sizes['retained' if original else 'current']=json.loads(subprocess.check_output([str(exe),'sizes'],text=True))
        if traces[0]!=traces[1] or len(traces[0].splitlines())!=2592:
            raise RuntimeError('Valid geometry differs from retained baseline')
        sanitized=[]
        if sanitizers:
            executable=current_dir/'atlas-sanitized'
            command=compilation_command(select_compiler(),ROOT/'tools/pf_oracle/tests/sdvk156_atlas_identity_fixture.cpp',
                [current_dir,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'],executable)
            subprocess.run(command[:1]+['-fsanitize=address,undefined','-fno-omit-frame-pointer','-O1','-g']+command[1:],
                           check=True,timeout=120)
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
            sanitized=[run_record(executable,case,env=env) for case in CASES]
    paths=set(PRODUCTION_FILES+TEST_FILES)
    paths.update(p.relative_to(ROOT).as_posix() for p in RETAINED.iterdir() if p.is_file())
    hashes={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in sorted(paths)}
    return {'schema':'sdvk156-atlas-incarnation-cpu/v1','status':'CPU_PASS',
        'assessed_master':'ad0833696804e57672ec425d2c33bf36732d05f1',
        'assessed_tree':'ee9b0cffc10316a95a4cc74d2cfd4c0462cd2e29',
        'source_sha256':hashes,'retained_inputs':pins,
        'compiler':select_compiler(),'platform':platform.platform(),
        'positive_case_count':len(positives),'compiled_mutant_count':len(mutations),
        'current':positives,'retained_atlas_audit':historical,'mutants':mutations,
        'valid_geometry_equivalence':{'status':'PASS','allocations':2560,'clear_cycles':32,
             'trace_lines':2592,'sha256':hashlib.sha256(traces[0]).hexdigest()},
        'sizeof_bytes':sizes,'sanitizers':{'executed':sanitizers,'cases':sanitized},
        'model_boundary':[
            'real RectPacker, LightmapTile, exact LevelMesh allocation/packing/checked access and Doom ReleaseTiles bodies',
            'exact scratch SelectTiles/ValidateSelectedTile/SetLevelMesh bodies; symbolic mesh arrays and no Vulkan calls',
            'real same-storage ABA; same-address packer recreation; actually dangling old tile rejected before dereference',
            'compiled mutations must reject a named invariant, not any crash or compiler failure',
            'original copied-receipt failures remain immutable injected counterexamples, not demonstrated native reachability',
            'no renderer, device, per-texel GPU readback, whole native multi-page matrix or physical execution'],
        'acceptance':{'issue156':'CANDIDATE_PENDING_REQUIRED_CI_REVIEW_MERGE',
            'issue14':'NOT_SOFTWARE_COMPLETE','physical_stop':'ACTIVE',
            'physical_cost_scaling_stability':'HELD_NOT_ACCEPTED','historical_physical_root_cause':'UNDETERMINED'}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--sanitizers',action='store_true',help='Additionally compile/run ASan+UBSan+leak controls with PF_CXX')
    args=parser.parse_args(argv)
    if args.out.exists():raise FileExistsError(args.out)
    result=collect(args.sanitizers);args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','positive_case_count','compiled_mutant_count')}))
    return 0


if __name__=='__main__':raise SystemExit(main())
