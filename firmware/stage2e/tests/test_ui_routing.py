#!/usr/bin/env python3
"""Execute the actual patched ADJ dispatcher in a bounded instruction model.

The model stops at a native case entry. It does not execute the camera UI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits-1)) else value


class Image:
    def __init__(self, data):
        self.data = data
        self.segments = [struct.unpack_from('>5I',data,32+i*20) for i in range(16)]

    def read(self, va, count):
        for src,base,n,_,_ in self.segments:
            if base <= va and va+count <= base+n:
                start = src+512+va-base
                return self.data[start:start+count]
        raise AssertionError(f'unmapped model read {va:#x}')


def route(image, activity, stops):
    r = [0] * 16
    memory = {0x205d9bf8:activity}
    writes = []
    condition = False
    pc = 0x202ba6fc
    for _ in range(100):
        if pc in stops:
            return pc, memory[0x205d9bf8], writes
        raw = image.read(pc,4)
        first,second = struct.unpack('>2H',raw)
        next_pc = pc+4
        if first & 0x8000:
            dest,base = (first >> 8) & 15, first & 15
            if first & 0xf0ff == 0xd0c0: r[dest] = second << 16
            elif first & 0xf0f0 == 0x80e0: r[dest] = r[base] | second
            elif first & 0xf0f0 == 0xa0c0:
                address = (r[base] + signed(second,16)) & 0xffffffff
                r[dest] = memory[address] if address in memory else int.from_bytes(image.read(address,4),'big')
            elif first & 0xf0f0 == 0xa040:
                address = (r[base] + signed(second,16)) & 0xffffffff
                memory[address] = r[dest]; writes.append((address,r[dest]))
            elif first & 0xfff0 == 0x8050:
                condition = r[base] < second
            elif raw[0] == 0xff:
                next_pc = (pc + 4*signed(int.from_bytes(raw,'big') & 0xffffff,24)) & 0xffffffff
            elif raw[0] == 0xfd:
                if not condition: next_pc = pc + 4*signed(int.from_bytes(raw,'big') & 0xffffff,24)
            else: raise AssertionError(f'unsupported dispatcher word {pc:#x}: {raw.hex()}')
        else:
            for index, op in enumerate((first,second & 0x7fff)):
                dest,base = (op >> 8) & 15, op & 15
                if op == 0x7000: continue
                if op & 0xf000 == 0x6000: r[dest] = signed(op & 255,8) & 0xffffffff
                elif op & 0xf000 == 0x4000: r[dest] = (r[dest] + signed(op & 255,8)) & 0xffffffff
                elif op & 0xf0e0 == 0x5040: r[dest] = (r[dest] << (op & 31)) & 0xffffffff
                elif op & 0xf0f0 == 0x00a0: r[dest] = (r[dest] + r[base]) & 0xffffffff
                elif op & 0xf0f0 == 0x20a0: r[dest] = signed(int.from_bytes(image.read(r[base],2),'big'),16) & 0xffffffff
                elif op & 0xfff0 == 0x1fc0: next_pc = r[base]; break
                else: raise AssertionError(f'unsupported dispatcher halfword {pc+index*2:#x}: {op:04x}')
        pc = next_pc
    raise AssertionError('dispatcher failed to reach a native case')


def check(candidate):
    official = Image(OFFICIAL.read_bytes())
    image = Image(candidate)
    table = official.read(0x20377434,44)
    cases = {i+1:0x202ba72c+struct.unpack_from('>h',table,i*2)[0] for i in range(22)}
    stops = set(cases.values()) | {0x202ba9e8}
    results = []
    failures = []
    for activity in list(range(24)) + [0xffffffff]:
        expected = cases.get(activity,0x202ba9e8)
        actual, after, writes = route(image,activity,stops)
        ok = actual == expected and after == activity and not writes
        results.append(dict(activity=activity,expected=hex(expected),actual=hex(actual),
                            activity_after=after,writes=writes,passed=ok))
        if not ok: failures.append(results[-1])
    assert cases[8] == 0x202ba764
    return dict(candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                cases=results,passed=not failures,failures=failures,
                method='bounded host instruction model of candidate bytes; native case bodies are not executed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = check(args.candidate.read_bytes())
    if args.output:
        permitted = [ROOT/'research/stage2a_deep_isp',ROOT/'firmware/stage2a_deep_isp',
                     ROOT/'research/stage2b_deep_select_fix',ROOT/'firmware/stage2b_deep_select_fix',
                     ROOT/'research/stage2c_category_gate',ROOT/'firmware/stage2c_category_gate',
                     ROOT/'artifacts/stage2c-packages']
        assert any(args.output.resolve().is_relative_to(p) for p in permitted)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'cases':len(result['cases']),'failures':len(result['failures'])}))
    raise SystemExit(0 if result['passed'] else 1)
