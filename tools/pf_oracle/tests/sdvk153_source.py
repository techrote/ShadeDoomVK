"""Exact SDVK-153 producer extraction and immutable pre-fix source pins."""
from pathlib import Path
import hashlib
import json
from tools.pf_oracle.tests.sdvk014_source import block, current as builder_source

ROOT = Path(__file__).resolve().parents[3]
RETAINED = ROOT / 'tools/pf_oracle/tests/fixtures/sdvk153-pre-fix.json'
RETAINED_SHA256 = '770c900ee93196a33104ee022eb5ef9f7328c70f3f3b76cac9ec7fd1be5b4ad1'


def retained() -> dict:
    raw = RETAINED.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RETAINED_SHA256:
        raise AssertionError('SDVK-153 historical source receipt changed')
    data = json.loads(raw)
    for key, value in data['functions'].items():
        if hashlib.sha256(value['content'].encode()).hexdigest() != value['sha256']:
            raise AssertionError('SDVK-153 historical fragment changed: ' + key)
    return data


def fragments(original: bool = False) -> dict[str, str]:
    functions = retained()['functions']
    result = {key: value['content'] if original else block((ROOT/value['path']).read_text(), value['signature'])
              for key, value in functions.items()}
    if not original:
        result['fixed'] = block((ROOT/functions['reset']['path']).read_text(),
                                'void VkDescriptorSetManager::UpdateFixedTextureDescriptors()')
    return result
