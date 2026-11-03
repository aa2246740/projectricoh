#!/usr/bin/python3 -I -B
"""Read official files and keep every derived artifact in this study."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PRIOR = ROOT / 'research/xpan_incamera/local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
AS = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-as'
OBJCOPY = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy'
STOP = 0x207ff000
CFG = 0x20600000
RESULT = 0x20610000
STACK = 0x20700000
BANK = 0x204392a0


def put(path, data):
    path = Path(path).resolve()
    if not path.is_relative_to(HERE) or path == HERE:
        raise ValueError('Output is outside the study')
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (bytes, bytearray)):
        path.write_bytes(data)
    else:
        path.write_text(data)


def record(name, value):
    put(LOCAL / name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(data, pos):
    return struct.unpack_from('>I', data, pos)[0]


def sections(data):
    return [(s+0x200, v, n) for s, v, n, _, _ in
            (struct.unpack_from('>5I', data, 0x20+20*i) for i in range(16)) if n]


def offset(data, address):
    for f, v, n in sections(data):
        if v <= address < v+n:
            return f+address-v
    raise ValueError(f'Address outside segments: {address:#x}')


def address(data, pos):
    for f, v, n in sections(data):
        if f <= pos < f+n:
            return v+pos-f
    return None


def weighted(data):
    length, start = word(data, 0x164), word(data, 0x20)
    body = data[0x200:0x200+length]
    return sum(sum(body[k::6])*((start+k)%6+2) for k in range(6)) & 0xffffffff


def official():
    data = (OFFICIAL / 'jlaunch3').read_bytes()
    assert sha(data) == '951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
    return data


def log(phase, decision, why, evidence, result):
    path = LOCAL / 'decisions.tsv'
    old = path.read_text() if path.exists() else 'ts\tphase\tdecision\twhy\tevidence\tresult\n'
    cells = [datetime.now(timezone.utc).isoformat(), phase, decision, why, evidence, result]
    assert all('\t' not in cell and '\n' not in cell for cell in cells)
    put(path, old+'\t'.join(cells)+'\n')


def init():
    files = [ROOT / 'artifacts/downloads/gxr-151.zip']
    files += sorted(p for p in OFFICIAL.iterdir() if p.is_file())
    files += [ROOT / 'tools/gxr_emulator/backend.py',
              ROOT / 'tools/gxr_emulator/build/libgxr_m32r.dylib', OBJDUMP, AS, OBJCOPY]
    files += [p for p in (ROOT / 'research/xpan_incamera').iterdir() if p.is_file()]
    files += [PRIOR / x for x in ('geometry.json', 'capture.json', 'preview-gnu.json',
                                 'change-sites.json', 'jlaunch3-refs.json')]
    files += sorted((PRIOR / 'disasm').glob('jlaunch3-*.txt'))
    pins = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files}
    assert not (LOCAL / 'inputs.json').exists()
    record('inputs.json', pins)
    data = official()
    put(LOCAL / 'stock/jlaunch3', data)
    record('sections.json', [[hex(x) for x in row] for row in sections(data)])
    git = subprocess.run(['git', '--no-optional-locks', 'status', '--porcelain=v1', '-uall'],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    put(LOCAL / 'git-start.txt', git.stdout)
    record('session.json', dict(start_utc='2026-10-30T01:23:57+00:00',
        deadline_utc='2026-10-30T04:23:57+00:00',
        initialization_utc=datetime.now(timezone.utc).isoformat(),
        initial_read_dispatch='Four shell readers were dispatched together. FAIL.',
        subsequent_execution='Sequential Python runs, at most one child tool.',
        scope='Only this study directory is writable; network is denied.'))
    log('start', '只研究 50mm 的类别 2 L', '保留既有输入和其他工作',
        'local/inputs.json', 'OPEN')
    print('Input pins', len(pins), 'official weighted value', hex(weighted(data)))


def verify_inputs():
    pins = json.loads((LOCAL / 'inputs.json').read_text())
    for name, expected in pins.items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    return len(pins)


def fence():
    target = ROOT / 'research/.xpan_r2_write_probe'
    assert not target.exists()
    try:
        with target.open('wb') as handle:
            handle.write(b'x')
    except PermissionError:
        denied = True
    else:
        raise RuntimeError('Write policy did not deny the outside path')
    assert not target.exists()
    put(LOCAL / 'write-probe.txt', 'Study write allowed.\n')
    record('fence.json', dict(outside_write_denied=denied, local_write_allowed=True,
                             network_policy='deny network*',
                             protected_inputs=verify_inputs()))
    print('Write policy PASS')


def listing(lo, hi):
    for path in sorted((PRIOR / 'disasm').glob('jlaunch3-*.txt')):
        for line in path.read_text().splitlines():
            match = re.match(r'^([0-9a-f]+):\t', line)
            if match and lo <= int(match[1], 16) < hi:
                yield line


def view(lo, hi):
    print('\n'.join(listing(lo, hi)))


def evidence(label, lo, hi, data=None):
    data = official() if data is None else data
    f = offset(data, lo)
    raw = LOCAL / 'slices' / f'{label}.bin'
    put(raw, data[f:f+hi-lo])
    run = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                          f'--adjust-vma={lo:#x}', str(raw)],
                         capture_output=True, text=True, check=True)
    text = f'File SHA256 {sha(data)}\nVMA {lo:#x}..{hi:#x}; file {f:#x}\n'+run.stdout
    put(LOCAL / 'evidence' / f'{label}.txt', text)
    return text


def refs(lo, hi):
    rows = json.loads((PRIOR / 'jlaunch3-refs.json').read_text())
    for row in rows:
        if lo <= row[1] < hi:
            print(hex(row[0]), hex(row[1]), row[2], row[-1])


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def machine(data):
    native = load_module('xpan_r2_gnu', ROOT / 'tools/gxr_emulator/backend.py')
    cpu = native.Backend(mode='debug', trace_limit=10000)
    pos = 0x20000000
    for f, v, n in sorted(sections(data), key=lambda r: r[1]):
        if pos < v:
            cpu.map(pos, bytes(v-pos))
        cpu.map(v, data[f:f+n], v >= 0x20380000)
        pos = v+n
    if pos < 0x20800000:
        cpu.map(pos, bytes(0x20800000-pos))
    return cpu


def integer(cpu, at, size=4):
    return int.from_bytes(cpu.read(at, size), 'big')


def invoke(cpu, at, args=(), end=None, limit=100000):
    for i, value in enumerate(args):
        cpu.set_reg(f'r{4+i}', value)
    cpu.set_reg('sp', STACK)
    if end is not None:
        cpu.add_breakpoint(end, lambda c: True)
    state = cpu.call(at, (), STOP, limit).to_dict()
    expected = 'breakpoint' if end is not None else 'return'
    if end is not None:
        cpu.breakpoints.pop(end)
    if state['reason'] != expected:
        raise RuntimeError(state)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('init', 'fence', 'view', 'refs', 'slice', 'run'))
    parser.add_argument('args', nargs='*')
    ns = parser.parse_args()
    if ns.command == 'init':
        init()
    elif ns.command == 'fence':
        fence()
    elif ns.command == 'view':
        view(*(int(v, 0) for v in ns.args))
    elif ns.command == 'refs':
        refs(*(int(v, 0) for v in ns.args))
    elif ns.command == 'slice':
        print(evidence(ns.args[0], *(int(v, 0) for v in ns.args[1:])))
    elif ns.command == 'run':
        module = load_module('xpan_r2_task', HERE / ns.args[0])
        module.main(ns.args[1:])


if __name__ == '__main__':
    main()
