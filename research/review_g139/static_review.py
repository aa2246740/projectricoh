"""Independent package, compiled-input, ELF and user-record checks."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINE = ROOT / 'firmware/engine_v56_g139'
BUILD = ENGINE / 'candidate/local/full-r13'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def u16(data, at):
    return struct.unpack_from('>H', data, at)[0]

def u32(data, at):
    return struct.unpack_from('>I', data, at)[0]

def elf_sections(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x02'
    header = struct.unpack_from('>16sHHIIIIIHHHHHH', data)
    sections = [struct.unpack_from('>10I', data, header[6]+i*header[11]) for i in range(header[12])]
    strings = sections[header[13]]
    names = data[strings[4]:strings[4]+strings[5]]
    return {names[s[0]:].split(b'\0', 1)[0].decode():
            dict(base=s[3], bytes=s[5], type=s[1], data=data[s[4]:s[4]+s[5]]) for s in sections}

def body_at(body, address, size):
    for index in range(16):
        source, base, length, _, _ = struct.unpack_from('>5I', body, 0x20+20*index)
        if base <= address and address+size <= base+length:
            at = source+0x200+address-base
            return body[at:at+size]
    raise AssertionError('address has no initialized section')

def crcs(data):
    header = bytearray(data[:256]); header[20:24] = bytes(4)
    assert u32(data, 20) == zlib.crc32(header) & 0xffffffff
    assert u32(data, 24) == zlib.crc32(data[256:]) & 0xffffffff

def users(data):
    # Literal checks corresponding to ui_v2_data.c lines 59-76.
    at = u32(data, 204)+1408
    extension = data[at:at+1984]
    assert u32(extension, 36) == 1216
    count = u16(extension, 24)
    assert count <= 32
    order = [0]*8
    entries = []
    groups = ('GRP', 'GRN', 'HCB', 'STD', 'FCC', 'FCN', 'LCH', 'LVI')
    for i in range(count):
        record = extension[1216+24*i:1216+24*(i+1)]
        slot = record[0]
        assert 1 <= slot <= 8 and record[1] == record[9] == record[21] == 0
        order[slot-1] += 1
        assert u16(record, 22) == order[slot-1]
        values = struct.unpack_from('11b', record, 10)
        per_unit = []
        for unit in range(3):
            config = extension[64+48*(8*unit+slot-1):][:48]
            ranges = []
            for k, value in enumerate(values):
                low, high, default = struct.unpack_from('3b', config, 15+3*k)
                assert low <= value <= high and (k < 4 or value == 0)
                ranges.append([low, high])
            per_unit.append(ranges)
        expected = '%s%s%03d' % (groups[slot-1], '*' if any(values) else '-', order[slot-1])
        name = record[2:9].decode('ascii')
        assert name == expected
        entries.append(dict(name=name, base=slot, values=values, ranges=per_unit, raw=record.hex()))
    assert extension[1216+24*count:] == bytes(24*(32-count))
    return at, entries

def main():
    release = ROOT / 'firmware/package_v38_g139/local/SD_ROOT'
    test = ROOT / 'firmware/package_v38_g139_test/local/SD_ROOT'
    dat, test_dat = (release/'GXRCE.DAT').read_bytes(), (test/'GXRCE.DAT').read_bytes()
    assert sha(dat) == 'aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21'
    assert sha(test_dat) == '2378a88c5f963ff58bb27e099d5e8668d721f043ce77d3f958b02d8e47c80dd5'
    assert len(dat) == len(test_dat) == 88104 and u32(dat, 28) == u32(test_dat, 28) == 139
    crcs(dat); crcs(test_dat)
    assert dat == (BUILD/'GXRCE.DAT').read_bytes()
    sections = elf_sections(BUILD/'engine.elf')
    engine, bss = sections['.engine'], sections['.bss']
    assert dat[engine['base']:engine['base']+engine['bytes']] == engine['data']
    assert test_dat[engine['base']:engine['base']+engine['bytes']] == engine['data']
    assert bss['base'] == len(dat) and bss['type'] == 8 and bss['bytes'] == u32(dat, 116) == 9148
    layout = json.loads((BUILD/'layout.json').read_text())
    checked = {}
    for kind in ('sources', 'headers', 'tools'):
        checked[kind] = len(layout[kind])
        for name, expected in layout[kind].items():
            assert sha((ROOT/name).read_bytes()) == expected, name
    body = (test/'ilaunch3').read_bytes()
    assert sha(body) == 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
    native = elf_sections(ROOT/'firmware/resident_v38/local/resident/build/resident.elf')['.resident']
    assert body_at(body, native['base'], native['bytes']) == native['data']
    trust = json.loads((ROOT/'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[80:112].hex() == test_dat[80:112].hex() == trust['resident_build_id']
    assert dat[212:228].hex() == trust['resident_abi_id']
    unchanged = []
    for path in test.iterdir():
        if path.name != 'GXRCE.DAT':
            assert path.read_bytes() == (release/path.name).read_bytes() == (ROOT/'firmware/package_v38_g137/SD_ROOT'/path.name).read_bytes()
            unchanged.append(path.name)
    assert len(unchanged) == 29
    for path in (ENGINE/'resident').iterdir():
        if path.is_file():
            assert path.read_bytes() == (ROOT/'firmware/resident_v38/resident'/path.name).read_bytes()
    _, empty = users(dat); at, records = users(test_dat)
    assert empty == [] and [u['name'] for u in records] == ['FCC-001', 'FCC*002', 'GRN*001']
    assert records[2]['values'][:4] == (2, 5, 5, -5)
    changed = [i for i in range(len(dat)) if dat[i] != test_dat[i]]
    assert all(20 <= i < 28 or at <= i < at+1984 for i in changed)
    for unit in range(3):
        bank = u32(dat, u32(dat, 156)+64*unit+16)
        assert all(dat[bank+32+64*slot+3] == 1 for slot in range(8))
    request = 7504+((len(dat)+bss['bytes']+3)&~3)
    assert request == 104756 <= 106124
    result = dict(status='PASS_STATIC', release_sha256=sha(dat), test_sha256=sha(test_dat),
                  elf_sha256=sha((BUILD/'engine.elf').read_bytes()), code_matches_both_packages=True,
                  checked_compilation_inputs=checked, unchanged_body_files=len(unchanged),
                  resident_build_id=trust['resident_build_id'], dat_bytes=len(dat), bss_bytes=bss['bytes'],
                  main_request=request, reserve_limit=106124, budget_limit=108124,
                  changed_bytes=len(changed), extension_changed_bytes=sum(at <= i < at+1984 for i in changed),
                  users=records, release_users=empty, all_24_S_selectors_are_1=True)
    (HERE/'evidence/static-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'users'}), flush=True)

if __name__ == '__main__':
    main()
