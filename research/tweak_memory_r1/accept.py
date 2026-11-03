"""Compare retained real sessions with complete independent recipe targets."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime as R
from runtime import ROOT, load_snapshot, sha, symbols, layout
from reference import Reference, expand, expand_effect, u32


def check(source, engine, elf, expected_path=None, record_required=True):
    saved = load_snapshot(source)
    cpu = saved['cpu']
    dat = R.snapshot_dat(saved) if hasattr(R,'snapshot_dat') else Path(saved['dat_path']).read_bytes()
    assert sha(dat) == saved['dat_sha256']
    def mem(at, n):
        for base, data, _ in cpu['regions']:
            if base <= at and at+n <= base+len(data):
                return data[at-base:at-base+n]
        raise ValueError(hex(at))
    def u(at, n=4):
        return int.from_bytes(mem(at, n), 'big')
    base = u(0x20054770)-u32(dat, 132)
    syms, offsets = symbols(elf), layout(engine)
    def at(name):
        return base+syms[name.split('.')[0]]+offsets[name]
    reference = mem(at('g.current'), 56)
    unit, slot, effect = reference[0], reference[1], reference[51]
    levels = list(struct.unpack('>10h', mem(at('g.tweak'), 20)))
    if expected_path:
        target = expected_path.read_bytes()
    else:
        original = expand_effect(dat, effect-1) if effect else expand(dat, unit, slot)
        math = Reference(engine.name)
        status, target = math.compute(dat, unit, original, levels)
        assert status == 0
    assert len(target) == 552
    live = mem(at('g.live'), 552)
    assert live == target, ('complete 552 B mismatch', sha(live), sha(target))
    native = next(d for t, d in zip(cpu['device_types'], cpu['devices']) if t == 'StartupRegisters')['rpc_state']
    image = (ROOT/'artifacts/firmware/gxr-1.51'/('jlaunch3', 'qlaunch3', 'l08firm3')[unit]).read_bytes()
    segments = [struct.unpack_from('>5I', image, 32+20*i) for i in range(16)]
    overlay = {int(k):v for k, v in native['overlay'].items()}
    def actual(address):
        aligned = address & ~1
        if aligned in overlay:
            return overlay[aligned] >> (0 if address & 1 else 8) & 255
        for off, start, size, _, _ in segments:
            if start <= address < start+size:
                return image[512+off+address-start]
        raise ValueError(hex(address))
    directory = u32(dat, 156)+64*unit
    mapping = dat[u32(dat, directory+12):][:152]
    rows = []
    for i in range(9):
        address, n, offset = struct.unpack_from('>IHH', mapping, 32+12*i)
        raw = bytes(actual(address+j) for j in range(n))
        assert raw == target[offset:offset+n], ('row mismatch', i)
        rows.append(dict(row=i, bytes=n, sha256=sha(raw), equal=True))
    assert native['t'] == int.from_bytes(target[445:447], 'big')
    S = mem(u(0x200c0dac), 4096)
    bank = u32(dat, directory+16)+32+64*(slot-1)
    record_data = dat[bank:bank+64]
    mode = record_data[3]
    colour = [0x36f, 0x370, 0x371, *range(0x8ac, 0x8b6)]
    fields = colour if mode == 4 else [0x645, 0x646] if mode == 3 else [0x641, 0x642, 0x644, 0x643] if mode == 6 else []
    plan = {off:record_data[36+i] for i, off in enumerate(fields)}
    plan.update({0x6dd:record_data[49]+9, 0x6de:record_data[50]+9, 0x36e:mode})
    assert all(S[key] == value for key, value in plan.items())
    record = S[0xfd4:0xffc]
    if record_required:
        assert record[:4] == b'GXR2' and record[4] in (1, 3) and record[6:8] == bytes((unit, 1))
        assert list(struct.unpack('>10h', record[8:28])) == levels
        assert record[28:36] == dat[20:28]
        assert zlib.crc32(record[:36]) == int.from_bytes(record[36:], 'big')
    return dict(status='PASS', layer='模拟器实测；目标由主机 C 数学参照独立计算',
        snapshot=str(source.relative_to(ROOT)), snapshot_sha256=sha(source.read_bytes()),
        dat_sha256=sha(dat), source_cold_step=cpu['steps'], unit=unit, slot=slot, effect=effect,
        levels=levels, record=record.hex(), target_sha256=sha(target), complete_552_equal=True,
        nine_rows=rows, T_equal=True, T=native['t'], S_plan={hex(k):v for k, v in plan.items()},
        S_plan_equal=True, native_state_presets=[]), target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--expected', type=Path)
    p.add_argument('--record-optional', action='store_true')
    a = p.parse_args()
    a.source=a.source.resolve()
    a.engine=a.engine.resolve()
    a.elf=a.elf.resolve()
    if a.expected:a.expected=a.expected.resolve()
    result, target = check(a.source, a.engine, a.elf, a.expected, not a.record_optional)
    path = HERE/'evidence'/(a.name+'.json')
    assert not path.exists()
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (HERE/'local'/(a.name+'-target.bin')).write_bytes(target)
    print(json.dumps(dict(status='PASS', name=a.name, unit=result['unit'], levels=result['levels'])))


if __name__ == '__main__':
    main()
