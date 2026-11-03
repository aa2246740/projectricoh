from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
LOCAL = OUT / 'local/jobs' / os.environ.get('REVIEW_JOB', 'layout-current')
PRODUCT = ROOT / 'firmware/engine_v53_g135/candidate/containers/product'
sys.path.insert(0, str(OUT))
from elf_fields import section


def main():
    compiler = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    common = [str(compiler), '-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-fpic', '-m32r', '-mmodel=medium', '-msdata=none', '-G0', '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER', '-I', str(PRODUCT), '-I', str(PRODUCT / 'src/firmware/engine/core')]
    core_names = ['bytes', 'epoch', 'current', 'confirmed', 'tweak', 'confirmed_tweak', 'list', 'stock', 'live', 'staging', 'ready', 'bound', 'busy', 'committed', 'uncertain', 't_checked', 't_warn', 't_pending', 'neighbor', 'neighbor_valid', 'stage', 'remember_checked', 'confirmed_valid', 'previewing', 'view_lost', 'write_started', 'recheck', 'settings_pending']
    adapter_names = ['bytes', 'ui', 'values', 'failed', 'context', 'ui.levels', 'ui.saved', 'ui.text', 'ui.nav', 'ui.frame', 'ui.screen', 'ui.cur', 'ui.top', 'ui.physical', 'ui.count', 'ui.slot', 'ui.param', 'ui.group', 'ui.armed', 'ui.applied_user', 'ui.origin', 'ui.l1_cur', 'ui.card_cur', 'ui.item_cur', 'ui.entry_cur', 'ui.confirmed_user', 'list', 'failed_text']
    summary = {'status': 'PASS', 'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(), 'checks': []}
    for name, fields in [('core_layout', core_names), ('adapter_layout', adapter_names)]:
        source = ROOT / 'research/g135_v37' / (name + '.c')
        output = LOCAL / (name + '.o')
        completed = subprocess.run(common + ['-c', str(source), '-o', str(output)], capture_output=True, text=True)
        (LOCAL / (name + '.log')).write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 0
        raw = section(output.read_bytes(), '.layout')
        values = struct.unpack('>' + 'I' * len(fields), raw)
        layout = dict(zip(fields, values))
        if name == 'core_layout':
            expected = json.loads((ROOT / 'research/g135_v37/layout-bindings.json').read_text())['layouts']['current']
        else:
            expected = json.loads((ROOT / 'research/g135_v37/adapter-layout.json').read_text())
        assert layout == expected, name
        (OUT / ('evidence/' + name + '.json')).write_text(json.dumps(layout, indent=2) + '\n')
        summary['checks'].append({'name': name, 'fields': len(fields), 'equal': True, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    (OUT / 'evidence/layout-current.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    sys.tracebacklimit = 0
    try:
        main()
    except BaseException as error:
        print(type(error).__name__, str(error)[:500], flush=True)
        raise SystemExit(1)
