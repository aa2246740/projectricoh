#!/usr/bin/python3
"""Additional real GPIO and colour checks on the original batch runtime."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import struct
import sys
import types
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--cycle', action='store_true')
    p.add_argument('--readonly', action='store_true')
    p.add_argument('--expect-target', type=Path)
    p.add_argument('--diagnostic', action='store_true')
    extra, remaining = p.parse_known_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    tool = ROOT / 'tools/gxr_emulator_standby'
    sys.path.insert(0, str(tool))
    import storage_run
    original = storage_run.Backend
    configuration = []
    for name in ('nand-word', 'preview-link', 'sd-long-response', 'nand-read-tail'):
        path = ROOT / 'research/v310_body/fix/emulator' / (name.replace('-', '_') + '.py')
        module = load('review_extra_' + name.replace('-', '_'), path)
        module.install()
        configuration.append(dict(name=name, sha256=sha(path.read_bytes())))
    class ReviewBatchBackend(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.model_revision = configuration
            self.library_path = tool / 'build/libgxr_m32r.dylib'
            self._observer_owners = []
            self._native_driver = None
        def materialize_native(self):
            return None
        def add_write_trace(self, lo, hi, callback, native=None):
            return super().add_write_trace(lo, hi, callback)
    storage_run.Backend = ReviewBatchBackend
    starts = []
    diagnostic = dict(events=[])

    def capture_before(a, m, c, row):
        if row['operation'] != 257:
            return
        S = int.from_bytes(c.read(0x200c0dac, 4), 'big')
        T = int.from_bytes(c.read(0x200c0d9c, 4), 'big')
        data = c.read(S, 4096)
        (HERE / 'local' / (a.name + '-BOOT-before-S.bin')).write_bytes(data)
        row['before_S_sha256'] = sha(data)
        row['before_parameter_T_sha256'] = sha(c.read(T, 16384))
        row['before_unit_t'] = m.devices['startup'].rpc_state.get('t', 2)
        row['before_W_count'] = sum(v['cmd'] == 22 for v in m.devices['startup'].rpc_state.get('log', []))
        u = lambda at, n=4: int.from_bytes(c.read(at, n), 'big')
        row['before_context'] = dict(mode=u(0x205d9a7f, 1), my=u(0x205d9aa3, 1),
            pending=u(0x205da00b, 1), state=u(0x205d9c00), activity=u(0x205d9bf8),
            S_selector=c.read(S + 0x36e, 1)[0], S_white_balance=c.read(S + 0x6dd, 2).hex())
        if extra.diagnostic:
            assert a.dat.read_bytes().hex().startswith('4758524345303031')
            base = u(0x20054770) - int.from_bytes(a.dat.read_bytes()[132:136], 'big')
            for offset, label in ((0x5f04, 'eng_boot_check'), (0x7204, 'boot_acquire'), (0x72a4, 'boot_release')):
                def hit(cpu, label=label):
                    if len(diagnostic['events']) < 1000:
                        diagnostic['events'].append(dict(label=label, step=cpu.steps,
                            pc=hex(cpu.get_reg('pc')), lr=hex(cpu.get_reg('lr')),
                            root=u(0x20054705, 1), inflight=u(0x20054706, 1), word=u(0x200547ec)))
                    return False
                c.add_breakpoint(base + offset, hit)
        starts.append(row)

    def save_diagnostic(a, m, c, result):
        if not extra.diagnostic:
            return
        state = c.snapshot()
        for device in state['devices']:
            if isinstance(device, dict):
                for key in list(device):
                    if callable(device[key]):
                        del device[key]
        path = HERE / 'local' / (a.name + '-budget-end.pkl.z')
        assert not path.exists()
        path.write_bytes(zlib.compress(pickle.dumps(dict(cpu=state), protocol=4), 3))
        diagnostic.update(snapshot=str(path.relative_to(ROOT)), snapshot_sha256=sha(path.read_bytes()),
            root=int.from_bytes(c.read(0x20054705, 1), 'big'),
            inflight=int.from_bytes(c.read(0x20054706, 1), 'big'),
            source_extension_sha256=sha(Path(__file__).read_bytes()))
        result['diagnostic'] = diagnostic

    def after_boot(a, m, c, observed, result, calls):
        u = lambda at, n=4: int.from_bytes(c.read(at, n), 'big')
        S, T = u(0x200c0dac), u(0x200c0d9c)
        peer = m.devices['startup']
        details = dict(extension_sha256=sha(Path(__file__).read_bytes()),
            runtime_tool=str(tool.relative_to(ROOT)), actual_backend_module=str(sys.modules['backend'].__file__),
            backend='original-batch', native_machine_used=False,
            model_configuration=configuration, physical_inputs=[], observations=[])
        result['extra'] = details
        if extra.readonly and a.dat:
            assert len(starts) == 1
            before = starts[0]
            assert before['before_S_sha256'] == sha(c.read(S, 4096))
            assert before['before_parameter_T_sha256'] == sha(c.read(T, 16384))
            assert before['before_unit_t'] == peer.rpc_state.get('t', 2)
            assert before['before_W_count'] == result['rpc_write_count'] == 0
            assert not result['BOOT_S_writes'] and not result['word'] & 12
            details['BOOT_zero_colour_writes'] = True
            details['BOOT_complete_S_equal_before'] = True
            details['BOOT_parameter_T_equal_before'] = True
        if extra.expect_target:
            target = extra.expect_target.read_bytes()
            assert len(target) == 552
            maps = json.loads((ROOT / 'research/v310_body/fix/evidence/studio-compatibility.json').read_text())['results'][1]['maps']
            index = {'50mm': 0, '28mm': 1, 'mount': 2}[a.unit]
            mapping = bytes.fromhex(maps[index])
            overlay = peer.rpc_state.get('overlay', {})
            from unit_peer import UnitImage
            image = UnitImage(a.unit).raw
            sections = [struct.unpack_from('>5I', image, 32 + 20 * i) for i in range(16)]
            def byte(at):
                aligned = at & ~1
                if aligned in overlay:
                    return (overlay[aligned] >> (0 if at & 1 else 8)) & 255
                for pos, lo, n, _, _ in sections:
                    if lo <= at < lo + n:
                        return image[512 + pos + at - lo]
                raise ValueError(hex(at))
            rows = []
            for i in range(9):
                at, length, offset = struct.unpack_from('>IHH', mapping, 32 + 12 * i)
                actual = bytes(byte(at + j) for j in range(length))
                assert actual == target[offset:offset + length]
                rows.append(dict(index=i, bytes=length, sha256=sha(actual)))
            assert peer.rpc_state['t'] == int.from_bytes(target[445:447], 'big')
            assert (c.read(S + 0x36e, 1), c.read(S + 0x6dd, 2)) == (b'\x01', b'\x09\x09')
            assert result['word'] == 2 and starts and starts[0]['result'] == 1
            details.update(target_sha256=sha(target), nine_rows=rows,
                unit_T_equal_target=True, S_plan_equal=True)
        if extra.cycle:
            initial_calls = len(calls)
            initial_words = len([v for v in observed.events if v['address'] == 0x200547ec])
            initial_record = c.read(S + 0xfd4, 40)
            initial_W = result['rpc_write_count']
            for phase, expected in (('open', 56), ('close', 5)):
                details['physical_inputs'].append(m.panel.set_key('ADJ', True))
                stop = c.run(400000)
                assert stop.reason == 'max_steps'
                details['physical_inputs'].append(m.panel.set_key('ADJ', False))
                for _ in range(12):
                    stop = c.run(10000000)
                    details['observations'].append(dict(phase=phase, step=c.steps, state=u(0x205d9c00), stop=stop.to_dict()))
                    assert stop.reason == 'max_steps'
                    if u(0x205d9c00) == expected:
                        break
                assert u(0x205d9c00) == expected, (phase, u(0x205d9c00))
            new_calls = calls[initial_calls:]
            assert not any(v['operation'] == 257 for v in new_calls)
            assert initial_words == len([v for v in observed.events if v['address'] == 0x200547ec])
            assert c.read(S + 0xfd4, 40) == initial_record
            assert sum(v['cmd'] == 22 for v in peer.rpc_state.get('log', [])) == initial_W
            details.update(cycle_status='PASS', later_BOOT_calls=0,
                later_fixed_word_writes=0, later_colour_W=0, record_unchanged=True,
                final_word=u(0x200547ec), final_steps=c.steps)

    script = HERE / 'cold.py'
    source = script.read_text()
    source = source.replace("str(ROOT/'tools/gxr_emulator_fast')", 'str(' + repr(str(tool)) + ')')
    old = 'calls.append(row);ret=cpu.get_reg(\'lr\');task=m.task();previous=cpu.breakpoints.get(ret)'
    assert source.count(old) == 1
    source = source.replace(old, 'capture_before(a,m,c,row);' + old)
    old = "        result['status']='PASS'"
    assert source.count(old) == 1
    source = source.replace(old, '        after_boot(a,m,c,observed,result,calls)\n' + old)
    old = "        if a.dat:assert len(boot)==1 and 'end' in boot[0]"
    assert source.count(old) == 1
    source = source.replace(old, '        save_diagnostic(a,m,c,result)\n' + old)
    old = "state=dict(cpu=c.snapshot(),image_sha256=result['image_sha256'])"
    assert source.count(old) == 1
    source = source.replace(old, "state=dict(cpu=c.snapshot(),image_sha256=result['image_sha256'])\n            for device in state['cpu']['devices']:\n                if isinstance(device,dict):\n                    for key in list(device):\n                        if callable(device[key]):del device[key]")
    runner = types.ModuleType('review_extra_driver')
    runner.__file__ = str(script)
    runner.capture_before = capture_before
    runner.after_boot = after_boot
    runner.save_diagnostic = save_diagnostic
    sys.modules[runner.__name__] = runner
    exec(compile(source, str(script), 'exec'), runner.__dict__)
    sys.argv = [str(script), *remaining]
    runner.main()


if __name__ == '__main__':
    main()
