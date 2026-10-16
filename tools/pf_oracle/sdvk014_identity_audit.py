#!/usr/bin/env python3
"""Collect SDVK-014 CPU/source identity counterexamples; never start Vulkan.

Exit 0 normally means the declared evidence was reproduced, including blocked
invariants. --require-clean returns 2 while any reproduced clean invariant fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.tests.test_sdvk014_identity_audit import CASES, SOURCES, build

BASE = 'ca254b6ea08228c8408562ebba26bbc1060a0311'
TREE = 'ea20650fefbe454b5a43f82119e879df75ed8e4f'
PATHS = sorted({row[0] for row in SOURCES.values()} | {
    'src/common/rendering/hwrenderer/data/hw_rectpacker.h',
    'src/common/rendering/hwrenderer/data/hw_rectpacker.cpp',
    'src/common/rendering/hwrenderer/data/hw_lightmaptile.h',
    'src/common/rendering/hwrenderer/data/hw_levelmesh.h',
    'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp',
    'src/common/rendering/hwrenderer/data/hw_resourcegeneration.h',
    'src/common/rendering/hwrenderer/data/hw_probe_selection.h',
    'src/common/rendering/hwrenderer/data/hw_cvars.cpp',
    'src/rendering/hwrenderer/doom_levelmesh.h',
    'src/rendering/hwrenderer/doom_levelmesh.cpp',
    'src/rendering/hwrenderer/scene/hw_drawinfo.cpp',
    'src/maploader/maploader.cpp',
    'src/common/rendering/vulkan/descriptorsets/vk_bindless.h',
    'src/common/rendering/vulkan/textures/vk_texture.h',
    'src/common/rendering/vulkan/textures/vk_texture.cpp',
    'src/common/rendering/vulkan/samplers/vk_samplers.cpp',
    'src/common/rendering/vulkan/vk_levelmesh.cpp',
    'src/common/utility/bounds.cpp',
    'wadsrc/static/shaders/lightmap/frag_copy.glsl',
    'wadsrc/static/shaders/scene/lightmodel_pbr.glsl',
})


def collect() -> dict:
    records = []
    with tempfile.TemporaryDirectory(prefix='sdvk014-identity-receipt-') as tmp:
        executable = build(Path(tmp) / 'current')
        for case, (code, reason) in CASES.items():
            result = subprocess.run([str(executable), case], text=True, capture_output=True, timeout=10)
            if result.returncode != code or reason not in result.stdout + result.stderr:
                raise RuntimeError(f'Unexpected {case} result: {result.returncode}\n{result.stdout}{result.stderr}')
            records.append({'case': case, 'returncode': result.returncode,
                            'invariant': 'PASS' if code == 0 else 'BLOCKED_NOT_ACCEPTED',
                            'stdout': result.stdout, 'stderr': result.stderr})
        control = build(Path(tmp) / 'counterfactual', preserve_probe_slots=True)
        result = subprocess.run([str(control), 'probe-preserve-control'],
                                text=True, capture_output=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        records.append({'case': 'counterfactual-preserve-probe-slots', 'returncode': 0,
                        'invariant': 'CPU_CONTROL_ONLY_NOT_A_PRODUCTION_FIX',
                        'stdout': result.stdout, 'stderr': result.stderr})
    files = {}
    for path in PATHS:
        raw = (ROOT / path).read_bytes()
        files[path] = {'sha256': hashlib.sha256(raw).hexdigest(),
                       'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
    return {
        'schema': 'sdvk014-durable-identity-audit/v1',
        'assessed_master': BASE, 'assessed_tree': TREE,
        'upstream_blocker': 153,
        'source_bundle': {
            'source_run': 38930148555, 'artifact': 12057998317,
            'archive_sha256': 'f74d6f3630af5b3e7cd27a66b05f3f9bfbcd58afb6a3fce41e309c0b5ff975be',
            'local_merge_ref': '1b97276ea1358087c818fcfc10216efd06d6aed7',
            'tree_equals_assessed_master': True,
        },
        'claim': 'source-owned CPU audit; no Vulkan device or renderer execution',
        'audit_result': 'BLOCKED_NOT_ACCEPTED',
        'counterexamples_reproduced': sum(row['returncode'] == 11 for row in records),
        'records': records, 'source_files': files,
        'adapters': [
            'symbolic view objects and sampled-descriptor write sink; pending writes treated as submitted',
            'empty material/colormap populations; real PF-003 slot allocator and PF-012 CPU selection',
            'sampler hardware-reset counter; source check verifies retained probe samplers are outside that reset',
            'real RectPacker, LightmapTile and BBox constructors; allocation/error services only',
            'counterfactual deletes only the probe retirement loop in an extracted temporary definition',
        ],
        'limits': {
            'atlas_aba': 'injected copied old tile receipt inside a live packer; no native reachability claimed',
            'probe_reset': 'actual owner/reset/lookup/upload bodies and allocator; no rendered pixels claimed',
            'disk_lightmap': 'semantic rebinding audited; authored bake-content freshness is not authenticated',
            'historical_failure_causality': 'UNDETERMINED',
        },
        'physical_stop_active': True,
        'physical_performance': 'HELD_NOT_ACCEPTED',
        'sdvk014_software_complete': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--require-clean', action='store_true')
    args = parser.parse_args()
    result = collect()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in ('schema', 'audit_result', 'counterexamples_reproduced')}))
    return 2 if args.require_clean and result['audit_result'] != 'PASS' else 0


if __name__ == '__main__':
    raise SystemExit(main())
