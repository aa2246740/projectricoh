#!/usr/bin/python3
"""Check unknown-mode refusal independently of MY/pending refusal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--backend', choices=('c', 'python'), required=True)
    a = p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    os.environ['GXR_HARNESS_BACKEND'] = a.backend
    sys.path.insert(0, str(ROOT / 'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE = TEMP / 'mode-decode' / a.backend
    source = ROOT / 'research/v310_body/fix/local/valid-mount-look-r5-gate-input.z'
    state = pickle.loads(zlib.decompress(source.read_bytes()))
    rows = []
    target = HERE / 'evidence' / ('mode-contract-' + a.backend + '.json')
    assert not target.exists()
    for name, changes in (
        ('actual_cold_input', []),
        ('unknown_selected_mode_255', [(0x205d9a7f, 255)]),
        ('unknown_selected_mode_127', [(0x205d9a7f, 127)]),
        ('MY_unknown_255', [(0x205d9aa3, 255)]),
    ):
        b = PB.PythonBackend()
        for at, data, writable in state['regions']:
            b.map(at, data, writable)
        regs = state['registers']
        b.set_reg('psw', regs['psw'])
        for key in ('spi', 'spu', 'bpc', 'bbpc', 'evb'):
            if key in regs:
                b.set_reg(key, regs[key])
        for i in range(16):
            b.set_reg('r' + str(i), regs['r' + str(i)])
        if 'acch' in regs:
            b.set_reg('acc', (regs['acch'] << 32) | regs['accl'])
        original_mode = b.read(0x205d9a7f, 1)[0]
        for at, value in changes:
            b.write(at, bytes([value]))
        S = int.from_bytes(b.read(0x200c0dac, 4), 'big')
        before = b.read(S, 4096)
        word = b.read(0x200547ec, 4)
        stop = b.call(state['expected_function'], [], 0x7ffffff0, 200000)
        assert stop.reason == 'return'
        assert b.read(S, 4096) == before and b.read(0x200547ec, 4) == word
        rows.append(dict(case=name, original_cold_mode=original_mode,
            changes=[dict(address=hex(at), value=value) for at, value in changes],
            qualification_result=b.get_reg('r0'), steps=stop.steps,
            S_unchanged=True, word_unchanged=True,
            input_role='Host-only variants of a captured real cold qualification input'))
    assert rows[0]['qualification_result'] == 1
    assert rows[-1]['qualification_result'] == 0
    missing_refusal = any(v['qualification_result'] != 0 for v in rows[1:3])
    result = dict(status='CONTRACT_FAILURE' if missing_refusal else 'PASS',
        backend=a.backend, source=str(source.relative_to(ROOT)),
        source_sha256=sha(source.read_bytes()), entry=hex(state['expected_function']),
        runner_sha256=sha(Path(__file__).read_bytes()), cases=rows,
        contract='research/v310_resident/ABI.md:13 requires refusal of unknown selected modes before colour writes',
        scope='Qualification function only; these host fixtures do not prove a physical dial can produce the declared values')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], backend=a.backend,
        results=[v['qualification_result'] for v in rows])))


if __name__ == '__main__':
    main()
