#!/usr/bin/python3
"""Observe real GPIO HALF/FULL entries after a fresh no-DAT cold start."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')
sys.path.insert(0, str(HERE))
from audit import snapshot


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def model(name):
    path = ROOT / 'research/v310_body/fix/emulator' / (name.replace('-', '_') + '.py')
    spec = importlib.util.spec_from_file_location('review_extra_' + name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.install()
    return dict(name=name, sha256=sha(path.read_bytes()))


def observe():
    target = HERE / 'evidence/cold-reset-GPIO-keys.json'
    assert not target.exists()
    sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_standby'))
    configuration = [model(v) for v in ('nand-word', 'preview-link', 'sd-long-response', 'nand-read-tail')]
    import storage_run, outputs
    from panel import Panel
    outputs.declare_media(TEMP)
    cold = json.loads((HERE / 'evidence/nodat-mount-empty-r2-batch.json').read_text())
    assert cold['status'] == 'PASS' and cold['extra']['model_configuration'] == configuration
    source = HERE / 'local/nodat-mount-empty-r2-batch-end.pkl.z'
    assert sha(source.read_bytes()) == cold['snapshot_sha256']
    saved = snapshot(source)
    record = next(d['medium_record'] for t, d in zip(saved['cpu']['device_types'], saved['cpu']['devices']) if t == 'SdHost')
    original = Path(record['path'])
    assert original.resolve().is_relative_to(TEMP)
    assert sha(original.read_bytes()) == record['sha256']
    rows = []
    for key, raw in (('HALF', 13), ('FULL', 14)):
        medium = TEMP / ('cold-key-' + key.lower() + '.img')
        assert not medium.exists()
        shutil.copyfile(original, medium)
        m = storage_run.Machine(medium)
        c = m.cpu
        c.restore(saved['cpu'])
        c.set_mode('fast')
        c.set_batch(True)
        p = Panel(c, m.devices)
        p.chain(c)
        u = lambda at, n=4: int.from_bytes(c.read(at, n), 'big')
        assert u(0x205d9c00) == 5 and u(0x200547ec) == 2
        entries = []
        def entered(cpu):
            message = cpu.get_reg('r4')
            row = dict(step=cpu.steps, raw=u(message + 12), pressed=u(message + 16),
                word=u(0x200547ec), path=None)
            entries.append(row)
            if row['raw'] == raw and row['pressed'] and 'snapshot' not in row:
                state = dict(registers={name: cpu.get_reg(name) for name in saved['cpu']['registers']},
                    regions=[(base, bytes(data), writable) for base, data, writable in cpu.regions], steps=cpu.steps)
                path = HERE / 'local' / ('cold-key-' + key.lower() + '-entry.pkl.z')
                assert not path.exists()
                path.write_bytes(zlib.compress(pickle.dumps(state, protocol=4), 3))
                row.update(snapshot=str(path.relative_to(ROOT)), snapshot_sha256=sha(path.read_bytes()))
            return False
        c.add_breakpoint(0x202afe98, entered)
        def continued(cpu):
            if entries:
                entries[-1]['path'] = 'continue'
            return False
        c.add_breakpoint(0x202afe9c, continued)
        actions = [p.set_key(key, True)]
        stop = None
        for _ in range(12):
            stop = c.run(2000000)
            if stop.reason != 'max_steps' or any(v['raw'] == raw and v['pressed'] for v in entries):
                break
        actions.append(p.set_key(key, False))
        matching = [v for v in entries if v['raw'] == raw and v['pressed']]
        assert matching and all(v['word'] == 2 and v['path'] == 'continue' for v in matching)
        rows.append(dict(key=key, entries=entries, physical_inputs=actions,
            status='PASS_C01_CONTINUATION', stop=stop.to_dict(), photo_complete=False))
        m.close()
    target.write_text(json.dumps(dict(status='PASS_C01_CONTINUATION', source=str(source.relative_to(ROOT)),
        source_sha256=sha(source.read_bytes()), backend='original-batch',
        model_configuration=configuration, cases=rows,
        scope='Actual GPIO inputs and actual C01 continuation after the fresh cold start; full capture is untested'), indent=2) + '\n')
    print(json.dumps(dict(status='PASS_C01_CONTINUATION', keys=len(rows))))


def verify(backend):
    target = HERE / 'evidence' / ('cold-key-replay-' + backend + '.json')
    assert not target.exists()
    os.environ['GXR_HARNESS_BACKEND'] = backend
    sys.path.insert(0, str(ROOT / 'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE = TEMP / 'cold-key-decode' / backend
    rows = []
    for key in ('half', 'full'):
        source = HERE / 'local' / ('cold-key-' + key + '-entry.pkl.z')
        state = pickle.loads(zlib.decompress(source.read_bytes()))
        b = PB.PythonBackend()
        for at, data, writable in state['regions']:
            b.map(at, data, writable)
        regs = state['registers']
        b.set_reg('psw', regs['psw'])
        for name in ('spi', 'spu', 'bpc', 'bbpc', 'evb'):
            b.set_reg(name, regs[name])
        for i in range(16):
            b.set_reg('r' + str(i), regs['r' + str(i)])
        b.set_reg('acc', (regs['acch'] << 32) | regs['accl'])
        b.add_breakpoint(0x202afe9c, lambda cpu: True)
        stop = b.call(0x202afe98, [], regs['r14'], 20000)
        assert stop.reason == 'breakpoint' and stop.pc == 0x202afe9c
        rows.append(dict(key=key, source_sha256=sha(source.read_bytes()), steps=stop.steps, path='continue'))
    target.write_text(json.dumps(dict(status='PASS', backend=backend, cases=rows), indent=2) + '\n')
    print(json.dumps(dict(status='PASS', backend=backend, keys=len(rows))))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--backend', choices=('c', 'python'))
    a = p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    if a.backend:
        verify(a.backend)
    else:
        observe()
