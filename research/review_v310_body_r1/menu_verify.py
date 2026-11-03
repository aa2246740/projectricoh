#!/usr/bin/python3
"""Recheck actual first-menu bytes and run official text conversion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BODY = ROOT / 'research/v310_body'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')
sys.path.insert(0, str(HERE))
from audit import snapshot, memory


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
    PB.CACHE = TEMP / 'menu-decode' / a.backend
    target = HERE / 'evidence' / ('menu-verify-' + a.backend + '.json')
    assert not target.exists()
    DAT = (ROOT / 'firmware/package_v310_g155b_test/GXRCE.DAT').read_bytes()
    code_offset = int.from_bytes(DAT[132:136], 'big')
    relocation_offset = int.from_bytes(DAT[144:148], 'big')
    relocation_bytes = int.from_bytes(DAT[148:152], 'big')
    elf = ROOT / 'firmware/engine_v66_g155b/candidate/local/boot-on/engine.elf'
    table = subprocess.check_output([str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '-t', str(elf)], text=True)
    t_rows = [line.split() for line in table.splitlines() if line.split() and line.split()[-1] == 't_seen']
    assert len(t_rows) == 1 and t_rows[0][3] == '.engine' and int(t_rows[0][4], 16) == 4
    t_offset = int(t_rows[0][0], 16)
    maps = json.loads((BODY / 'fix/evidence/studio-compatibility.json').read_text())['results'][1]['maps']
    cases = [('mount-builtin', 2, 6, '>6 '), ('mount-look', 2, 7, '>M9 STD'),
             ('mount-user', 2, 7, '>FCC*002'), ('28mm-builtin', 1, 6, '>6 '),
             ('50mm-user', 0, 7, '>FCC*002')]
    rows = []
    for name, unit, row, prefix in cases:
        source = BODY / 'fix/r2/local' / ('first-image-' + name + '-r2-first-image.pkl.z')
        saved = snapshot(source)
        state = saved['cpu']
        mem = lambda at, n: memory(state, at, n)
        u = lambda at, n=4: int.from_bytes(mem(at, n), 'big')
        base = u(0x20054770) - code_offset
        relocated = bytearray(DAT)
        for off in range(relocation_offset, relocation_offset + relocation_bytes, 8):
            patch, relative = struct.unpack_from('>II', DAT, off)
            struct.pack_into('>I', relocated, patch, base + relative)
        peer = next(d for t, d in zip(state['device_types'], state['devices']) if t == 'StartupRegisters')['rpc_state']
        assert DAT[t_offset:t_offset + 4] == b'\xff' * 4
        assert u(base + t_offset) == peer['t']
        struct.pack_into('>I', relocated, t_offset, peer['t'])
        assert mem(base, len(DAT)) == relocated
        assert (u(0x205d9bf8), u(0x205d9c00), u(0x2022f5ac, 1)) == (8, 56, 8)
        assert u(0x2022f726, 1) == u(0x205a2944, 1) == row
        actual_glyphs = mem(u(u(u(0x2022f5a8) + 4 * (row - 1))), 70).split(b'\0', 1)[0]
        b = PB.PythonBackend()
        for at, data, writable in state['regions']:
            b.map(at, data, writable)
        regs = state['registers']
        b.set_reg('psw', regs['psw'])
        for i in range(16):
            b.set_reg('r' + str(i), regs['r' + str(i)])
        for key in ('spi', 'spu', 'bpc', 'bbpc', 'evb'):
            if key in regs:
                b.set_reg(key, regs[key])
        b.map(0x10000000, bytes(8192), True)
        stop = b.call(0x201dc180, [], 0x7ffffff0, 2000)
        assert stop.reason == 'return'
        language = b.get_reg('r0')
        raw = prefix.encode('ascii')
        b.write(0x10000000, raw + b'\0')
        for i, value in enumerate((0x10000000, len(raw), 0x10001000, language), 4):
            b.set_reg('r' + str(i), value)
        stop = b.call(0x201d73e0, [], 0x7ffffff0, 100000)
        assert stop.reason == 'return'
        expected = b.read(0x10001000, 70).split(b'\0', 1)[0]
        assert expected and actual_glyphs.startswith(expected)
        colour_target = (BODY / 'fix/local' / (name + '-target.bin')).read_bytes()
        assert len(colour_target) == 552
        g = saved.get('symbols', {}).get('g')
        if g is None:
            g = snapshot(BODY / 'fix/r2/local/h52-success-time-key-2.pkl.z')['symbols']['g']
        assert mem(base + g + 1461, 552) == colour_target
        peer = next(d for t, d in zip(state['device_types'], state['devices']) if t == 'StartupRegisters')['rpc_state']
        overlay = {int(k): v for k, v in peer['overlay'].items()}
        image = (ROOT / 'artifacts/firmware/gxr-1.51' / ('jlaunch3', 'qlaunch3', 'l08firm3')[unit]).read_bytes()
        sections = [struct.unpack_from('>5I', image, 32 + 20 * i) for i in range(16)]
        def byte(at):
            aligned = at & ~1
            if aligned in overlay:
                return overlay[aligned] >> (0 if at & 1 else 8) & 255
            for pos, lo, n, _, _ in sections:
                if lo <= at < lo + n:
                    return image[512 + pos + at - lo]
            raise ValueError(hex(at))
        mapping = bytes.fromhex(maps[unit])
        hashes = []
        for i in range(9):
            at, length, offset = struct.unpack_from('>IHH', mapping, 32 + 12 * i)
            actual = bytes(byte(at + j) for j in range(length))
            assert actual == colour_target[offset:offset + length]
            hashes.append(sha(actual))
        assert peer['t'] == int.from_bytes(colour_target[445:447], 'big')
        plan = json.loads((BODY / 'fix/evidence' / ('valid-' + name + '-r5-acceptance.json')).read_text())['S_plan']
        S = u(0x200c0dac)
        assert all(mem(S + int(k, 0), 1)[0] == value for k, value in plan.items())
        run = json.loads((BODY / 'fix/r2/evidence' / ('first-image-' + name + '-r2.json')).read_text())
        assert run['error'] is None and run['additional_W_T'] == 0 and run['T_unchanged']
        rows.append(dict(case=name, source=str(source.relative_to(ROOT)), source_sha256=sha(source.read_bytes()),
            DAT_image_equal_after_relocation_and_runtime_t_seen=True,
            runtime_t_seen=dict(offset=t_offset, value=peer['t'], ELF_sha256=sha(elf.read_bytes())), first_menu_rows=8,
            highlighted_row=row, expected_prefix=prefix, actual_glyphs=actual_glyphs.hex(),
            expected_glyphs=expected.hex(), native_conversion_steps=stop.steps,
            cache_552_equal=True, nine_row_hashes=hashes, unit_T_equal=True,
            S_plan_equal=True, retained_colour_writes_on_menu=0))
    result = dict(status='PASS', backend=a.backend, cases=rows, DAT_sha256=sha(DAT),
        runner_sha256=sha(Path(__file__).read_bytes()),
        layer='Retained actual menu snapshots, direct byte comparisons and independent C/Python official text conversion',
        boundary='The original full GPIO-to-menu trajectories are retained implementation runs; this script does not rerun all five trajectories')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', backend=a.backend, cases=len(rows))))


if __name__ == '__main__':
    main()
