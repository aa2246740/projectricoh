"""Independent final-artifact checks; retain metadata, never firmware bytes."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
ROOT, HERE = scope.ROOT, scope.HERE
BUILD = ROOT / 'firmware/engine_diag_v38_g143/candidate/local/full-r1'


def u16(b, at):
    return int.from_bytes(b[at:at+2], 'big')


def u32(b, at):
    return int.from_bytes(b[at:at+4], 'big')


def symbol_bytes(elf, name):
    sym = elf.symbols[name]
    section = elf.sections[sym['section']]
    at = sym['value'] - section['va']
    return elf.content(section)[at:at+sym['size']]


def main():
    scope.freeze_check()
    dat_path = ROOT / 'firmware/package_v38_diag143/SD_ROOT/GXRCE.DAT'
    dat = dat_path.read_bytes()
    assert scope.sha(dat_path) == '52a19ed1e8ac987b716cbe5d803fae1bcc88d62c1aa2216dfebaed2482de9904'
    assert dat == (BUILD / 'GXRCE.DAT').read_bytes()
    assert len(dat) == 27252 and u32(dat, 28) == 143
    header = bytearray(dat[:256]);header[20:24] = bytes(4)
    assert zlib.crc32(header) == u32(dat, 20)
    assert zlib.crc32(dat[256:]) == u32(dat, 24)
    g137 = (ROOT / 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert hashlib.sha256(g137).hexdigest() == '78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[48:112] == g137[48:112]
    assert dat[80:112].hex() == trust['resident_build_id']
    assert dat[212:228] == g137[212:228] == bytes.fromhex(trust['resident_abi_id'])
    code_off, code_bytes = u32(dat, 132), u32(dat, 136)
    engine = (BUILD / 'engine.bin').read_bytes()
    assert dat[code_off:code_off+code_bytes] == engine
    reader = scope.load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'review143_elf')
    elf = reader.Elf(BUILD / 'engine.elf')
    compared = []
    for section in elf.sections:
        if section['flags'] & 2 and section['type'] != 8 and section['size']:
            at = section['va'] - code_off
            assert elf.content(section) == engine[at:at+section['size']], section['name']
            compared.append(section['name'])
    layout = json.loads((BUILD / 'layout.json').read_text())
    for p in (ROOT/'firmware/engine_diag_v38_g143/candidate/engine_services').iterdir():
        if p.is_file():
            old_service=ROOT/'firmware/engine_diag_v38/candidate/engine_services'/p.name
            assert old_service.is_file() and p.read_bytes()==old_service.read_bytes(), p.name
    for name, digest in layout['sources'].items():
        assert scope.sha(ROOT / name) == digest, name
    dis = subprocess.run([str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),
                          '-d', '--no-show-raw-insn', str(BUILD / 'engine.elf')],
                         capture_output=True, text=True, check=True, timeout=4200).stdout
    (scope.SCRATCH / 'diag.dis').write_text(dis)
    lines = dis.splitlines();calls = []
    for i, line in enumerate(lines):
        if re.search(r'\bbl(?:\.l)?\s+[0-9a-f]+ <rv_rpc8_native>', line):
            commands = re.findall(r'ldi r0,#(\d+)', ' '.join(lines[max(0,i-8):i]))
            assert commands and int(commands[-1]) in (21,23), line
            calls.append({'elf_offset': '0x' + line.strip().split(':')[0], 'command': int(commands[-1])})
    assert len(calls) == 5
    assert [c['command'] for c in calls] == [23,21,23,21,23]
    bridges = sorted(name for name in elf.symbols if name.startswith('rv_native_') or name == 'rv_rpc8_native')
    assert set(bridges) == {'rv_native_ascii','rv_native_language','rv_native_draw','rv_native_context',
                            'rv_native_rpc_ready','rv_native_rpc_limit','rv_rpc8_native'}
    rows_blob = symbol_bytes(elf, 'diag_rows')
    expect_blob = symbol_bytes(elf, 'diag_expect')
    assert len(rows_blob) == 240 and len(expect_blob) == 108
    units = ('jlaunch','qlaunch','l08firm')
    image_names = ('jlaunch3','qlaunch3','l08firm3')
    shared = u32(g137,192)
    checks = []
    for unit, name in enumerate(units):
        directory = u32(g137,156) + 64*unit
        assert g137[directory:directory+8].rstrip(bytes(1)) == name.encode()
        mapping = u32(g137,directory+12)
        table = u32(g137,directory+20)
        desc = next(table+16+20*i for i in range(g137[table+5]) if g137[table+16+20*i] == 4)
        expanded = bytearray(552)
        for off,size,kind,index in zip((20,82,115,216,284,346,379,412,456,518),
                                       (62,33,96,56,62,33,33,33,62,33),
                                       (0,1,2,3,0,1,1,1,0,1),g137[desc+8:desc+18]):
            pool=shared+16+12*kind
            assert u16(g137,pool+2) == size
            at=shared+u32(g137,pool+4)+size*index
            expanded[off:off+size]=g137[at:at+size]
        raw=(ROOT/'firmware/package_v38_g137/local/SD_ROOT'/image_names[unit]).read_bytes()
        unit_checks=[]
        for row in range(9):
            at=mapping+32+12*row
            address,n,entry_off=u32(g137,at),u16(g137,at+4),u16(g137,at+6)
            compiled=8*(10*unit+row)
            assert (u32(rows_blob,compiled),u16(rows_blob,compiled+4)) == (address,n)
            expected=bytes(expanded[entry_off:entry_off+n])
            assert len(expected) == n
            mapped=None
            for seg in range(16):
                file_off,base,length,_,_=struct.unpack_from('>5I',raw,0x20+20*seg)
                if base <= address and address+n <= base+length:
                    pos=0x200+file_off+address-base
                    mapped=raw[pos:pos+n]
                    break
            assert mapped == expected, (name,row)
            assert zlib.crc32(expected) == u32(expect_blob,4*(9*unit+row))
            rebuilt=bytearray(n)
            lead=address&1;reads=[]
            for i in range(-lead,n,2):
                read_at=(address&~1)+(i+lead)
                for seg in range(16):
                    file_off,base,length,_,_=struct.unpack_from('>5I',raw,0x20+20*seg)
                    if base <= read_at and read_at+2 <= base+length:
                        pos=0x200+file_off+read_at-base
                        value=int.from_bytes(raw[pos:pos+2],'big');break
                else:
                    raise AssertionError('read outside initialized unit image')
                if i >= 0: rebuilt[i]=value>>8
                if i+1 < n: rebuilt[i+1]=value&255
                reads.append((read_at>>16,read_at&65535))
            assert rebuilt == expected
            unit_checks.append({'row_zero_based':row,'address':hex(address),'bytes':n,
                                'v_reads':len(reads),'pages':sorted({hex(p) for p,_ in reads})})
        t_page,t_off=u16(g137,mapping+28),u16(g137,mapping+30)
        assert (t_page,t_off) == (0x12c0,0x2444)
        assert (u32(rows_blob,8*(10*unit+9)),u16(rows_blob,8*(10*unit+9)+4)) == (t_page,t_off)
        checks.append({'unit':name,'t_page':hex(t_page),'t_offset':hex(t_off),'rows':unit_checks})
    result={'dat_sha256':scope.sha(dat_path),'dat_bytes':len(dat),'elf_sha256':scope.sha(BUILD/'engine.elf'),
            'code_bytes':code_bytes,'elf_sections_equal_to_dat':compared,'crc_checks':'PASS',
            'resident_build_id':trust['resident_build_id'],'resident_abi_id':trust['resident_abi_id'],
            'native_bridges':bridges,'rpc_call_sites':calls,'rows':checks,
            'main_request_bytes':7504+((len(dat)+u32(dat,116)+3)&~3),
            'main_physical_span_bytes':7516+((len(dat)+u32(dat,116)+3)&~3),
            'g137_main_request_bytes':108124,'g137_main_physical_span_bytes':108136,
            'source_hashes_match_layout':True,'frozen_inputs':scope.freeze_check()}
    assert result['main_request_bytes'] == 49380 and result['main_physical_span_bytes'] == 49392
    current_case = HERE/'cases/28mm-publish/accept.json'
    if current_case.is_file():
        own = json.loads(current_case.read_text())['own_block']
        assert int(own[1],16)-int(own[0],16) == result['main_request_bytes']
    scope.save(HERE/'static-review.json',result)
    print('STATIC_PASS',len(checks)*9,'rows; five RPC sites; final DAT and ELF agree')


if __name__ == '__main__':
    main()
