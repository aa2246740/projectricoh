from pathlib import Path
import hashlib
import json
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
LOCAL = OUT / 'local/jobs' / os.environ.get('REVIEW_JOB', 'windows')
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(ROOT / 'research/g135_v37'))
from elf_fields import symbol


def main():
    raw = (ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT').read_bytes()
    elf = (ROOT / 'firmware/engine_v53_g135/candidate/local/full-r13/engine.elf').read_bytes()
    offset, code = symbol(elf, 'uv_window')
    assert raw[offset:offset + len(code)] == code
    target = runpy.run_path(str(ROOT / 'research/g135_v37/target_check.py'), run_name='window_target')
    target['loader'].__globals__['LOCAL'] = LOCAL / 'decode'
    Backend = target['loader']()
    folder = ROOT / 'research/g135_v37/local/checks/review_g126/target-state-50mm'
    state = json.loads((folder / 'state.json').read_text())
    regions = [(row['base'], bytearray((folder / row['file']).read_bytes()), row['writable']) for row in state['regions']]
    target['locate'](regions, raw)
    backend = Backend()
    for base, data, writable in regions:
        backend.map(base, bytes(data), writable)
    metadata = json.loads((ROOT / 'research/g135_v37/target-0.json').read_text())
    entry = metadata['image_address'] + offset
    assert backend.read(entry, len(code)) == code
    backend.map(0x30000000, bytes(0x20000), True)
    count_cases = 0
    digest = hashlib.sha256()
    for count in range(1, 34):
        for current in range(count):
            for previous in range(34):
                backend.write(0x30000100, b'\x5a\xa5\xa5\x5a')
                backend.set_reg('r15', 0x30010000)
                stopped = backend.call(entry, [count, current, previous, 0x30000101], lr_sentinel=0x3fff0000, max_steps=1000)
                output = backend.read(0x30000100, 4)
                top, cursor = output[1:3]
                assert output[0] == output[3] == 0x5a
                assert top + cursor == current and cursor < 8
                assert top <= max(0, count - 8)
                if count <= 8:
                    assert top == 0
                if top > 0:
                    assert cursor > 0
                if top + 8 < count:
                    assert cursor < 7
                assert backend.get_reg('r15') == 0x30010000
                digest.update(bytes([count, current, previous, top, cursor]))
                count_cases += 1
    summary = {'status': 'PASS', 'cases': count_cases, 'count_range': [1, 33], 'previous_range': [0, 33], 'target_symbol': 'uv_window', 'symbol_offset': offset, 'symbol_bytes': len(code), 'code_sha256': hashlib.sha256(code).hexdigest(), 'dat_sha256': hashlib.sha256(raw).hexdigest(), 'elf_sha256': hashlib.sha256(elf).hexdigest(), 'observations_sha256': digest.hexdigest(), 'backend': 'PythonBackend M32R'}
    (OUT / 'evidence/windows.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    sys.tracebacklimit = 0
    try:
        main()
    except BaseException as error:
        print(type(error).__name__, str(error)[:500], flush=True)
        raise SystemExit(1)
