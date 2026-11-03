"""Inspect the frozen first-build boundary. All derived bytes stay in local/."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

ORIGINAL = c.ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
APPROVED = c.ROOT / 'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'


def segments(raw):
    return [struct.unpack_from('>5I', raw, 32 + 20 * i) for i in range(16)]


def at(raw, address, count):
    src, base, _, _, _ = next(s for s in segments(raw)
                              if s[1] <= address and address + count <= s[1] + s[2])
    offset = 512 + src + address - base
    return raw[offset:offset + count], offset


def inspect():
    original = ORIGINAL.read_bytes()
    approved = APPROVED.read_bytes()
    assert hashlib.sha256(original).hexdigest() == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    assert hashlib.sha256(approved).hexdigest() == '05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
    regions = [('build', 0x20287080, 0x202871d8),
               ('get-mode', 0x20271fec, 0x20272074),
               ('push', 0x201c07e0, 0x201c092c),
               ('init', 0x201c3fd4, 0x201c4110),
               ('dispatch-draw', 0x201d82fc, 0x201d8500),
               ('details', 0x201feb90, 0x201fec50),
               ('after-stores', 0x20285724, 0x20285900),
               ('close', 0x202871d8, 0x20287260),
               ('entry-caller', 0x202ba6e0, 0x202ba7a0),
               ('tag33-draw-dispatch', 0x201ffd68, 0x201fff20),
               ('layer-after-build', 0x201c092c, 0x201c0aa0)]
    hooks = json.loads((c.UPSTREAM / 'local/resident/hooks.json').read_text())
    ranges = [(int(h['va'], 16), h['length']) for h in hooks if h['number'] not in (3, 4)]
    result = []
    for name, start, end in regions:
        data, offset = at(original, start, end-start)
        patched, approved_offset = at(approved, start, end-start)
        differences = [start+i for i, (a, b) in enumerate(zip(data, patched)) if a != b]
        assert all(any(base <= p < base+n for base, n in ranges) for p in differences)
        p = c.LOCAL / 'native' / (name + '.bin')
        c.write(p, data)
        output = c.run([c.OBJDUMP, '-D', '-EB', '-b', 'binary', '-m', 'm32r',
                        '--adjust-vma=' + hex(start), p], 'native-' + name)
        result.append(dict(name=name, start=hex(start), end=hex(end), file_offset=offset,
                           approved_offset=approved_offset, sha256=c.sha(p),
                           hook_only_differences=[hex(p) for p in differences],
                           lines=len(output.stdout.splitlines())))
    # Literal pointer references can reveal additional native entry dispatchers.
    refs = []
    for address in (0x20287080, 0x2028709c, 0x202871d8, 0x201febe4):
        needle = struct.pack('>I', address)
        for src, base, n, _, _ in segments(original):
            blob = original[512+src:512+src+n]
            refs.extend(dict(target=hex(address), source=hex(base+m.start()),
                             file_offset=512+src+m.start())
                        for m in re.finditer(re.escape(needle), blob))
            for register in range(14):
                pair = bytes((0xd0+register, 0xc0)) + needle[:2]
                pair += bytes((0x80+register, 0xe0+register)) + needle[2:]
                refs.extend(dict(target=hex(address), source=hex(base+m.start()),
                                 file_offset=512+src+m.start(), kind='seth-or3')
                            for m in re.finditer(re.escape(pair), blob))
    c.save(c.LOCAL / 'native-regions.json', result)
    c.save(c.LOCAL / 'native-literal-references.json', refs)
    enum, _ = at(original, 0x20287040, 0x1d8)
    traces = []
    rows = []
    for mode in range(256):
        registers = [0]*16
        registers[2] = mode
        registers[0] = 5
        pc = 0x202870ac
        condition = False
        trace = []
        for _ in range(64):
            if pc == 0x20287118:
                break
            offset = pc - 0x20287040
            a, b = enum[offset:offset+2]
            half = (a << 8) | b
            trace.append(hex(pc))
            if 0xb0 <= a <= 0xbf:
                displacement = struct.unpack_from('>h', enum, offset+2)[0]
                equal = registers[a & 15] == registers[b & 15]
                assert b >> 4 in (0, 1)
                take = equal if b >> 4 == 0 else not equal
                pc = (pc & ~3) + displacement*4 if take else pc+4
            elif a in (0x7d, 0x7f):
                displacement = b if b < 128 else b-256
                pc = (pc & ~3) + displacement*4 if a == 0x7f or not condition else pc+2
            elif 0x60 <= a <= 0x6f:
                registers[a & 15] = b if b < 128 else b-256
                pc += 2
            elif a < 16 and b & 0xf0 == 0x40:
                condition = registers[a] < registers[b & 15]
                pc += 2
            elif half in (0xf000, 0x7000):
                pc += 2
            else:
                raise AssertionError((hex(pc), hex(half)))
        assert pc == 0x20287118 and 1 <= registers[8] <= 7
        rows.append(registers[8])
        traces.append(dict(mode=mode, native_row=registers[8], instruction_addresses=trace))
    prior = c.ROOT / 'research/review_full_r6/local'
    assert traces[:11] == json.loads((prior / 'native-enum-traces.json').read_text())
    assert all(row==1 for row in rows[11:])
    header = 'static const unsigned native_mode_rows[11]={' + ','.join(map(str, rows[:11])) + '};\n'
    assert header == (prior / 'native_enum.h').read_text()
    c.write(c.LOCAL / 'native_enum.h', header.encode())
    c.save(c.LOCAL / 'native-enum-traces.json', traces)
    # The real caller invokes this S getter before H02 and the enum. Invalid
    # raw bytes are normalized to 1, so the enum's direct fallback row 1 is
    # not the visible result of an invalid S byte on the native entry path.
    getter,_=at(original,0x20271fec,0x88)
    listing=(c.LOCAL/'logs/native-get-mode.log').read_text().splitlines()
    decoded={int(line.split(':',1)[0],16):line.split('\t')[-1].strip()
             for line in listing if re.match(r'^[0-9a-f]+:',line)}
    for address,mnemonic in {
        0x20271fec:'seth r0,#0x200c',0x20271ff0:'or3 r0,r0,#0xdac',
        0x20271ff4:'ld r0,@r0 || nop',0x20271ff8:'ldub r2,@(878,r0)',
        0x20272050:'seth r0,#0x200c',0x20272054:'or3 r0,r0,#0xdac',
        0x20272058:'ld r1,@r0 -> ldi r0,#1',0x2027205c:'stb r0,@(878,r1)',
        0x20272060:'seth r0,#0x200c',0x20272064:'or3 r0,r0,#0xdac',
        0x20272068:'ld r0,@r0 || nop',0x2027206c:'ldub r0,@(878,r0)',
        0x20272070:'jmp lr || nop'}.items():assert decoded[address]==mnemonic
    getter_traces=[];normalized=[];visible=[]
    for mode in range(256):
        registers=[0]*16;registers[2]=mode;registers[0]=5
        pc=0x20271ffc;condition=False;trace=[]
        for _ in range(64):
            if pc in (0x20272050,0x20272060):break
            offset=pc-0x20271fec;a,b=getter[offset:offset+2];half=(a<<8)|b
            trace.append(hex(pc))
            if 0xb0<=a<=0xbf:
                displacement=struct.unpack_from('>h',getter,offset+2)[0]
                assert b>>4==0
                pc=(pc&~3)+displacement*4 if registers[a&15]==registers[b&15] else pc+4
            elif a in (0x7d,0x7f):
                displacement=b if b<128 else b-256
                pc=(pc&~3)+displacement*4 if a==0x7f or not condition else pc+2
            elif 0x60<=a<=0x6f:
                registers[a&15]=b if b<128 else b-256;pc+=2
            elif a<16 and b&0xf0==0x40:
                condition=registers[a]<registers[b&15];pc+=2
            elif half in (0xf000,0x7000):pc+=2
            else:raise AssertionError((hex(pc),hex(half)))
        assert pc in (0x20272050,0x20272060)
        value=1 if pc==0x20272050 else mode
        assert value in (1,3,4,5,6,9,10)
        normalized.append(value);visible.append(rows[value])
        getter_traces.append(dict(raw_S=mode,normalized_S=value,native_row=rows[value],instruction_addresses=trace,normalization_store=pc==0x20272050))
    c.write(c.LOCAL/'native_get_mode.h',('static const unsigned native_s_modes[256]={'+','.join(map(str,normalized))+'};\n').encode())
    c.save(c.LOCAL/'native-get-mode-traces.json',getter_traces)
    c.save(c.LOCAL/'native-highlight-table.json',dict(raw_S=list(range(256)),normalized_S=normalized,visible_rows=visible,source='official getter 0x20271FEC followed by enum 0x202870AC'))
    print(json.dumps(dict(regions=result, literal_references=refs)))


if __name__ == '__main__':
    c.guard()
    c.freeze_check()
    inspect()
    c.freeze_check()
