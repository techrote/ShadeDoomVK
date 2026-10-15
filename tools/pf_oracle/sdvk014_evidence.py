#!/usr/bin/env python3
"""Collect bounded CPU SDVK-014 evidence. This command never creates Vulkan.

Exit 0 qualifies only the implemented CPU increment. The JSON deliberately
retains BLOCKED campaign status and the current probe-owner counterexample.
Use --require-campaign-complete to fail closed on the unqualified campaign.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.pf_oracle.tests import test_sdvk014_atlas_lifecycle as atlas
from tools.pf_oracle.tests import test_sdvk014_tile_lifecycle as tiles
from tools.pf_oracle.tests import test_sdvk014_probe_owner_boundary as probes
from tools.pf_oracle.tests import test_sdvk014_retained_lifecycle as retained

NEGATIVES={
    'atlas': {'full-height':(10,'Tile too large'),'padded-full-page':(10,'Tile too large'),
              'clear-rebuild':(10,'RectPacker items are corrupted'),
              'invalid-atomic':(11,'invalid-allocation-mutated-owner')},
    'tiles': {'shared-retirement':(11,'retired-tile-still-publishable'),
              'background':(11,'retired-background-binding'),'stats':(11,'retired-statistics'),
              'save-bindings':(11,'ghost-binding-serialized'),
              'readback-isolation':(11,'readback-overwrote-upload-shape'),
              'upload-consumption':(11,'successful-upload-not-consumed'),
              'invalid-owner':(11,'invalid-owner-reached-readback'),
              'live-free':(11,'live-tile-retired'),'bounded-retirement':(11,'retired-stress-update')},
    'probes': {'same-count':(11,'new-owner-not-rebuilt'),
               'same-count-via-empty':(11,'new-owner-not-rebuilt')},
}


def collect() -> dict:
    records=[];timings=[]
    retained_suite = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tools.pf_oracle.tests.test_sdvk014_retained_lifecycle", "-v"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    if retained_suite.returncode != 0:
        raise RuntimeError(
            "Unexpected retained-lifecycle suite failure:\n" +
            retained_suite.stdout + "\n" + retained_suite.stderr)
    records.append({
        'family':'retained-lifecycle','case':'complete-source-and-span-suite',
        'source':'current','disposition':'PASS','returncode':0,
        'intended_reason':'loader admission, completion ordering, page initialization and negative controls',
        'stdout':retained_suite.stdout.strip(),'stderr':retained_suite.stderr.strip(),'wall_ns':None})
    with tempfile.TemporaryDirectory(prefix='sdvk014-evidence-') as temporary:
        for family,module,cases in (('atlas',atlas,atlas.CASES),('tiles',tiles,tiles.CASES),
                                    ('probes',probes,probes.POSITIVE)):
            for original in (False,True):
                directory=Path(temporary)/family/('original' if original else 'current')
                started=time.perf_counter_ns();exe=module.build(directory,original)
                timings.append({'family':family,'source':'retained' if original else 'current',
                                'compile_wall_ns':time.perf_counter_ns()-started})
                targets=list(NEGATIVES[family]) if original else list(cases)
                if family=='probes' and not original:targets+=list(NEGATIVES['probes'])
                for case in targets:
                    blocker=family=='probes' and not original and case in NEGATIVES['probes']
                    expected=NEGATIVES[family][case] if original or blocker else (0,'PASS '+case)
                    started=time.perf_counter_ns()
                    p=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=20)
                    wall=time.perf_counter_ns()-started
                    if p.returncode!=expected[0] or expected[1] not in p.stdout+p.stderr:
                        raise RuntimeError(f'Unexpected {family}/{case}: {p.returncode}\n{p.stdout}\n{p.stderr}')
                    records.append({'family':family,'case':case,'source':'retained' if original else 'current',
                        'disposition':'BLOCKED_NOT_ACCEPTED' if blocker else 'EXPECTED_REJECTION' if original else 'PASS',
                        'returncode':p.returncode,'intended_reason':expected[1],
                        'stdout':p.stdout.strip(),'stderr':p.stderr.strip(),'wall_ns':wall})
    files=[
        'src/common/rendering/hwrenderer/data/hw_rectpacker.cpp',
        'src/common/rendering/hwrenderer/data/hw_rectpacker.h',
        'src/common/rendering/hwrenderer/data/hw_lightmaptile.h',
        'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp',
        'src/common/rendering/hwrenderer/data/hw_levelmesh.h',
        'src/common/rendering/hwrenderer/data/hw_lightprobe.cpp',
        'src/common/rendering/hwrenderer/data/hw_lightprobe.h',
        'src/rendering/hwrenderer/doom_levelmesh.cpp',
        'src/rendering/hwrenderer/doom_lightprobes.cpp',
        'src/rendering/hwrenderer/scene/hw_drawinfo.cpp',
        'src/rendering/hwrenderer/hw_entrypoint.cpp','src/p_setup.cpp',
        'src/common/rendering/vulkan/vk_renderdevice.cpp','src/commandlets/lightmapcmd.cpp',
        'tools/pf_oracle/sdvk014_evidence.py',
    ]
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tools/pf_oracle/tests').glob('*sdvk014*')) if p.is_file()]
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tools/pf_oracle/tests/fixtures').glob('sdvk014*')) if p.is_file()]
    return {
        'schema':'sdvk014-cpu-increment/v2',
        'audited_base':'04a3596115eb397d9e7237aa1ff3625ece1bc5b4',
        'identity_note':'Hashes pin actual tested source bytes, including the retained-lifecycle continuation; audited_base is not the tested publication head.',
        'acceptance':{'implemented_cpu_increment':'PASS','complete_software_campaign':'BLOCKED_NOT_ACCEPTED',
                      'cross_map_probe_lifecycle':'REBLOCKED_BY_150','native_campaign':'NOT_RUN',
                      'physical_performance':'HELD_NOT_ACCEPTED','physical_stop':'ACTIVE',
                      'historical_physical_root_cause':'UNDETERMINED'},
        'execution':{'python':platform.python_version(),'platform':sys.platform,
                     'renderer_executed':False,'vulkan_device_created':False,
                     'timing_classification':'descriptive CPU-fixture wall time only; no GPU cost/scaling/stability claim'},
        'counts':{'positive_cases':sum(r['disposition']=='PASS' for r in records),
                  'retained_intended_rejections':sum(r['disposition']=='EXPECTED_REJECTION' for r in records),
                  'current_blocked_counterexamples':sum(r['disposition']=='BLOCKED_NOT_ACCEPTED' for r in records),
                  'atlas_receipt_mutations':4,'live_region_mutations':11},
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
        'compile_timings':timings,'cases':records,
        'not_qualified':['native atlas/probe pixels and descriptors','durable rectangle/slot generation safety',
                         'native retained-LIGHTMAP round-trip beyond the admitted CPU/source contract','all dynamic update freshness transitions',
                         'cross-map probe publication','special-surface/portal/material lifecycle matrix',
                         'physical GPU bake/update cost, scaling or stability'],
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--require-campaign-complete',action='store_true')
    args=parser.parse_args()
    result=collect();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'acceptance':result['acceptance'],'counts':result['counts']},indent=2))
    return 2 if args.require_campaign_complete else 0


if __name__=='__main__':
    raise SystemExit(main())
