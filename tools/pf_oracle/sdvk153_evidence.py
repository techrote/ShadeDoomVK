#!/usr/bin/env python3
"""Collect exact-source SDVK-153 CPU evidence. No Vulkan/device entry points."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import tempfile
from tools.pf_oracle.fixture_runner import select_compiler
from tools.pf_oracle.tests.test_sdvk153_descriptor_lifetime import build, CASES, NEGATIVES
from tools.pf_oracle.tests.sdvk153_source import ROOT, retained, RETAINED_SHA256


def collect() -> dict:
    evidence=[]
    with tempfile.TemporaryDirectory(prefix='sdvk153-evidence-') as directory:
        directory=Path(directory)
        for original in (False,True):
            exe=build(directory/('original' if original else 'candidate'),original)
            cases=NEGATIVES if original else CASES
            for case in cases:
                result=subprocess.run([str(exe),case],text=True,capture_output=True,timeout=15)
                expected=11 if original else 0
                reason=NEGATIVES[case] if original else 'PASS '+case
                if result.returncode!=expected or reason not in result.stdout+result.stderr:
                    raise RuntimeError(f'Unexpected {case} result: {result.returncode}\n{result.stdout}{result.stderr}')
                evidence.append({'source':'retained' if original else 'candidate','case':case,
                                 'returncode':result.returncode,'expected_reason':reason,
                                 'stdout':result.stdout,'stderr':result.stderr,
                                 'disposition':'EXPECTED_REJECTION' if original else 'PASS'})
    paths=sorted({entry['path'] for entry in retained()['functions'].values()}|{
        'src/common/rendering/vulkan/descriptorsets/vk_descriptorset.h',
        'src/common/rendering/vulkan/descriptorsets/vk_bindless.h',
        'src/common/rendering/vulkan/textures/vk_texture.cpp',
        'src/common/rendering/vulkan/samplers/vk_samplers.cpp',
        'src/common/rendering/hwrenderer/data/hw_lightprobe.cpp',
        'tools/pf_oracle/tests/sdvk153_descriptor_lifetime_fixture.cpp',
        'tools/pf_oracle/tests/test_sdvk153_descriptor_lifetime.py',
        'tools/pf_oracle/tests/sdvk153_source.py',
    })
    hashes={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths}
    return {'schema':'sdvk153-descriptor-lifetime-cpu/v1','status':'CPU_PASS_NATIVE_PENDING',
            'assessed_master':'ca254b6ea08228c8408562ebba26bbc1060a0311',
            'audit_parent':'0b6e12d2aa942792a2c7e2d3f8d52fdc18db6c59',
            'implementation_parent':'d57137c3a383e912e2e7376759ec45d4503adfb9',
            'retained_sha256':RETAINED_SHA256,'source_sha256':hashes,
            'compiler':select_compiler(),'platform':platform.platform(),
            'positive_cases':len(CASES),'retained_named_failures':len(NEGATIVES),'records':evidence,
            'model_boundary':['exact producer definitions and PF-003 allocator/PF-012 selector/#150 builder',
                             'symbolic images/samplers/descriptor writes/frame retirement',
                             'source audit of real grow-only views and probe sampler ownership',
                             'no GPU submission, ZScript VM, texel readback, timing or hardware evidence'],
            'acceptance':{'issue153':'NOT_ACCEPTED_NATIVE_CI_PENDING','issue14':'NOT_SOFTWARE_COMPLETE',
                          'physical_stop':'ACTIVE','physical_cost_scaling_stability':'HELD_NOT_ACCEPTED',
                          'historical_physical_root_cause':'UNDETERMINED'}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.out.exists():raise FileExistsError(args.out)
    result=collect();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'positive_cases':result['positive_cases'],
                      'retained_named_failures':result['retained_named_failures']}))
    return 0


if __name__=='__main__':raise SystemExit(main())
