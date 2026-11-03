#!/usr/bin/env python3
"""Replay official task-8 and close bytes. Stops at named boundaries. No device I/O."""
from pathlib import Path
import hashlib
import importlib.util
import json
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
EXPECTED = {
    OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    BODY: '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
}
WINDOWS = {
    'task8-loop': (0x2010de04, 0x2010e150),
    'return-zero': (0x201106d4, 0x201106dc),
    'photo-tail': (0x2010ef00, 0x2010efe8),
    'high-close': (0x200a437c, 0x200a449c),
}

spec = importlib.util.spec_from_file_location(
    'bridge_cpu', ROOT / 'research/user_storage_r2/host_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class Stop(Exception):
    pass


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def preflight():
    p = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert p['MountPoint'] == '/Volumes/Workspace'
    assert p['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    for path, expected in EXPECTED.items():
        assert sha(path) == expected, str(path)
    OUT.mkdir(exist_ok=True)


class Image:
    def __init__(self):
        self.data = OFFICIAL.read_bytes()
        self.body = BODY.read_bytes()
        self.sections = []
        for i in range(16):
            src, va, n, bss, bn = struct.unpack_from('>IIIII', self.data, 32 + i * 20)
            self.sections.append(dict(file=src + 512, vma=va, size=n))

    def raw(self, va, n):
        hits = [s['file'] + va - s['vma'] for s in self.sections
                if s['vma'] <= va and va + n <= s['vma'] + s['size']]
        assert len(hits) == 1, hex(va)
        return self.data[hits[0]:hits[0] + n]

    def body_eq(self, va, n):
        hits = [s['file'] + va - s['vma'] for s in self.sections
                if s['vma'] <= va and va + n <= s['vma'] + s['size']]
        off = hits[0]
        return self.body[off:off + n] == self.data[off:off + n]


class Program:
    def __init__(self, image):
        self.name = 'bridge'
        self.image = image
        self.symbols = {}
        self.code = {}
        self.width = {}
        self.verified = 0

    def add_asm(self, path, start):
        for line in path.read_text().splitlines():
            m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$', line)
            if not m:
                continue
            pc, raw = int(m[1], 16), bytes.fromhex(m[2])
            assert self.image.raw(pc, len(raw)) == raw, hex(pc)
            self.verified += len(raw)
            if len(raw) in (2, 4):
                self.code[pc] = tuple(native.p.Program.parse(x) for x in re.split(r' -> | \|\| ', m[3]))
                self.width[pc] = len(raw)

    def byte(self, address):
        try:
            return self.image.raw(address, 1)[0]
        except AssertionError:
            return 0


def dump(image):
    rows = []
    for label, (start, end) in WINDOWS.items():
        raw = image.raw(start, end - start)
        assert image.body_eq(start, end - start), label
        path = OUT / (label + '.bin')
        path.write_bytes(raw)
        text = subprocess.check_output(
            [str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
             '--adjust-vma=' + hex(start), str(path)], text=True)
        asm = OUT / (label + '.asm.txt')
        asm.write_text('# Official bytes, equal to fixed v3.6 in this window.\n' + text)
        rows.append({'label': label, 'vma': hex(start), 'end': hex(end),
                     'sha256': hashlib.sha256(raw).hexdigest(), 'body_equal': True})
    return rows


def classify(program):
    rows = []
    table = {
        0x1f02: 0, 0x1f03: 1, 0x1f08: 4, 0x1f0a: 7, 0x1f0b: 8, 0x1f12: 10,
        0x1f13: 9, 0x1f20: 9, 0x1003: 9,
    }
    for code, event in table.items():
        cpu = native.CPU(program)
        cpu.seed(0x204f41ba, code, 2)
        cpu.seed(0x204f41c4, 1)
        cpu.seed(0x204f41c8, 1)
        got = cpu.call(0x2010e094) & 0xffffffff
        assert got == event, (hex(code), got)
        rows.append({'case': 'classify', 'opcode': hex(code), 'subtype': 1, 'event': got})
    for code, subtype, event in ((0x1f04, 7, 2), (0x1f04, 1, 3), (0x1f09, 7, 5), (0x1f09, 1, 6)):
        cpu = native.CPU(program)
        cpu.seed(0x204f41ba, code, 2)
        cpu.seed(0x204f41c4, subtype)
        cpu.seed(0x204f41c8, subtype)
        got = cpu.call(0x2010e094) & 0xffffffff
        assert got == event, (hex(code), subtype, got)
        rows.append({'case': 'classify', 'opcode': hex(code), 'subtype': subtype, 'event': got})
    return rows


def dispatch(program):
    rows = []
    table = 0x201427b4
    cases = (
        (0x1f03, 1, 1, 0x2010e5c8, 'stub', 1),
        (0x1f0b, 8, 1, 0x20111810, 'stub', 2),
        (0x1f12, 10, 1, 0x2010e064, 'real', 1),
        (0x1f13, 9, 1, 0x201106d4, 'real', 0),
        (0x1f13, 9, 2, 0x201106d4, 'real', 0),
    )
    for code, event, state, target, kind, expect in cases:
        cpu = native.CPU(program)
        cpu.seed(0x204f41e8, state, 1)
        cpu.seed(0x204f41ea, 0x40, 1)
        seen = []

        def receive(cc, code=code):
            if seen:
                raise Stop()
            cc.seed(0x204f41ba, code, 2)
            seen.append(code)
            return 48

        native.stub(cpu, 0x20109b28, 'receive', hook=receive)
        native.stub(cpu, 0x2005ff88, 'around_handler')
        assert cpu.read(table + 12 * event + 4 * state) == target
        if kind == 'stub':
            native.stub(cpu, target, 'handler', value=expect)
        try:
            cpu.call(0x2010de04, bound=20000)
        except Stop:
            pass
        else:
            raise AssertionError('loop did not return to receive')
        final = cpu.read(0x204f41e8, 1)
        assert final == expect, (hex(code), state, final, expect)
        assert target in cpu.visits or target in cpu.calls
        rows.append({'case': 'dispatch', 'opcode': hex(code), 'event': event,
                     'initial_state': state, 'handler': hex(target), 'handler_kind': kind,
                     'final_state': final})
    return rows


def terminal(program):
    cpu = native.CPU(program)
    cpu.seed(0x204f41ba, 0x1f11, 2)
    hits = []

    def stop_second(cc):
        hits.append(cc.r[4])
        if len(hits) == 2:
            raise Stop()
        return 0

    native.stub(cpu, 0x201099d8, 'before_terminal')
    native.stub(cpu, 0x200a398c, 'terminal_service')
    native.stub(cpu, 0x2006a6fc, 'terminal_arg6')
    native.stub(cpu, 0x2005de00, 'terminal_wait', hook=stop_second)
    try:
        cpu.call(0x2010de40, bound=20000)
    except Stop:
        pass
    else:
        raise AssertionError('0x1f11 returned to its caller')
    assert hits == [1000, 1000]
    assert 0x20109b28 not in cpu.calls
    return [{'case': 'opcode_1f11_leaves_receive_loop', 'wait_arg': 1000,
             'receive_resumed': False}]


def photo_tail(program):
    cpu = native.CPU(program)
    cpu.seed(0x204f41e8, 2, 1)
    cpu.seed(0x204f41d8, 0)
    def dcf(cc):
        raise Stop()

    native.stub(cpu, 0x20117264, 'dcf_tail', hook=dcf)
    cpu.r[8] = 0
    cpu.r[12] = 22
    try:
        cpu.call(0x2010ef0c, bound=20000)
    except Stop:
        pass
    else:
        raise AssertionError('format 22 did not reach the DCF tail')
    assert cpu.read(0x204f41e8, 1) == 1
    assert 0x2010ef14 in cpu.visits
    assert 0x20117264 in cpu.calls
    return [{'case': 'state_1_before_dcf_tail', 'format': 22, 'state_after_store': 1,
             'dcf_entered': True}]


def close_cases(program):
    rows = []
    cache = 0x204c86ec + 16 * (0x81 & 15)

    def run(status, pointer, write_result, lower_result, count):
        cpu = native.CPU(program)
        cpu.seed(0x204c8668, count)
        cpu.seed(cache, status, 2)
        cpu.seed(cache + 2, 1, 2)
        cpu.seed(cache + 8, pointer)
        native.stub(cpu, 0x0500d4e4, 'sem_wait')
        native.stub(cpu, 0x0500d4fc, 'sem_signal')
        native.stub(cpu, 0x200ab02c, 'tail_write', value=write_result & 0xffffffff)
        native.stub(cpu, 0x200a6750, 'lower_close', value=lower_result & 0xffffffff)
        result = cpu.call(0x200a437c, (0x81,), bound=20000)
        return {'status_in': status, 'pointer': hex(pointer), 'tail_write': write_result,
                'lower_close': lower_result, 'count_in': count, 'count_out': cpu.read(0x204c8668),
                'result': result, 'tail_write_called': 0x200ab02c in cpu.calls,
                'lower_close_called': 0x200a6750 in cpu.calls}

    expect = (
        (0, 0, 0, 0, 1, 0, 0, False),
        (2, 0x100, -1, 0, 1, 0, 0, False),
        (1, 0, -1, 0, 1, 0, 0, False),
        (1, 0x20600000, -1, 0, 1, 1, -1, True),
        (1, 0x20600000, 512, 0, 1, 0, 0, True),
        (0, 0, 0, 34, 1, 0, 34, False),
    )
    for status, pointer, write_result, lower_result, count, count_out, result, wrote in expect:
        row = run(status, pointer, write_result, lower_result, count)
        assert row['count_out'] == count_out, row
        assert row['result'] == result, row
        assert row['tail_write_called'] is wrote, row
        assert row['lower_close_called']
        rows.append(row)
    return rows


def main():
    preflight()
    image = Image()
    windows = dump(image)
    program = Program(image)
    for label in WINDOWS:
        program.add_asm(OUT / (label + '.asm.txt'), WINDOWS[label][0])
    rows = classify(program) + dispatch(program) + terminal(program) + photo_tail(program)
    closed = close_cases(program)
    out = {
        'status': 'PASS_BOUNDED_OFFICIAL_INSTRUCTIONS',
        'verified_window_bytes': program.verified,
        'windows': windows,
        'cases': rows,
        'close': closed,
        'limits': [
            'Host replay of official bytes with stubs at named calls.',
            'No RTOS scheduling, media, camera, or interrupt delivery.',
            '0x1f11 stop is the second wait in its own loop, not a full shutdown.',
        ],
    }
    (OUT / 'replay-results.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print('PASS', len(rows), 'control cases', len(closed), 'close cases', program.verified, 'bytes')


if __name__ == '__main__':
    main()
