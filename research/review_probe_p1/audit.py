"""Independent offline checks for the fixed generation 141 review inputs."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-probe')
OBJ = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
DAT = ROOT / 'firmware/package_v38_probe_p1/SD_ROOT/GXRCE.DAT'
ELF = ROOT / 'firmware/engine_probe_p1/candidate/local/full-r1/engine.elf'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(args, name):
    r = subprocess.run([str(OBJ)] + list(map(str, args)), capture_output=True,
                       text=True, check=True)
    (OUT / name).write_text(r.stdout)
    return r.stdout


def elf_sections(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x02'
    at = struct.unpack_from('>I', data, 32)[0]
    size, count, names = struct.unpack_from('>HHH', data, 46)
    rows = [struct.unpack_from('>10I', data, at + i * size) for i in range(count)]
    words = data[rows[names][4]:rows[names][4]+rows[names][5]]
    result = {}
    for row in rows:
        end = words.find(b'\0', row[0])
        name = words[row[0]:end].decode()
        result[name] = {'kind': row[1], 'flags': row[2], 'address': row[3],
                        'offset': row[4], 'size': row[5],
                        'bytes': data[row[4]:row[4]+row[5]] if row[1] != 8 else b''}
    return result


def instructions(text):
    result = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} ?)+)\t(.+)$', line)
        if m:
            result[int(m[1], 16)] = (bytes.fromhex(m[2]), m[3])
    return result


def rpc_constants(rows):
    flat = []
    for address, (_, line) in rows.items():
        if address >= 0x2c44:
            continue
        for item in re.split(r' -> | \|\| ', re.sub(r'\s*<[^>]*>', '', line)):
            op, _, args = item.partition(' ')
            flat.append((address, op, args.strip()))
    result = []
    for index,(address,op,args) in enumerate(flat):
        if op != 'bl' or int(args,16) != 0x2bfc:
            continue
        found = {}
        for reg in ('r0','r1'):
            for _, prior, operands in reversed(flat[max(0,index-40):index]):
                if prior in ('bl','jl'):
                    break
                first = operands.split(',')[0]
                if first != reg or prior in ('st','stb','sth','push','cmp','cmpu','cmpi','cmpui','beqz','bnez','beq','bne','bltz','bgez'):
                    continue
                assert prior in ('ldi','ld24'), (hex(address),reg,prior,operands)
                token=operands.split(',')[1].lstrip('#')
                found[reg] = int(token,16 if prior=='ld24' else 0) & 0xffffffff
                break
        assert set(found)=={'r0','r1'}, (hex(address),found)
        result.append({'address':hex(address),'command':found['r0'],'value':found['r1']})
    allowed={(23,0x12c0),(23,0x2012),(21,0x3b06),(21,0x3b10),(21,0x3b00),
             (21,0xebe2),(21,0xebe0),(22,0x7fff),(22,0xffff)}
    assert {(s['command'],s['value']) for s in result}==allowed
    assert [(s['address'],s['value']) for s in result if s['command']==22]==[('0x27ec',0x7fff),('0x2880',0xffff)]
    return result


def flow_checks(rows):
    region={a:v for a,v in rows.items() if 0x22a8<=a<0x2a64}
    graph={}
    for address,(raw,line) in region.items():
        next_address=address+len(raw)
        graph[address]=set()
        branch=False
        for part in re.split(r' -> | \|\| ',re.sub(r'\s*<[^>]*>', '',line)):
            op,_,args=part.partition(' ')
            if op in ('bra','bc','bnc','beq','bne','beqz','bnez','bltz','bgez'):
                target=int(args.split(',')[-1],16)
                graph[address].add(target)
                if op!='bra':graph[address].add(next_address)
                branch=True;break
            if op=='jmp':branch=True;break
        if not branch:graph[address].add(next_address)
    def reaches(target, blocked_nodes=(), blocked_edges=(), start=0x22a8):
        seen=set();todo=[start]
        while todo:
            node=todo.pop()
            if node in seen or node in blocked_nodes:continue
            if node==target:return True
            seen.add(node)
            todo.extend(n for n in graph.get(node,()) if (node,n) not in blocked_edges)
        return False
    checks=[]
    for write,read,select,guard,success in [(0x27ec,0x27ac,0x2798,0x27b0,0x27bc),
                                           (0x2880,0x2844,0x2830,0x284c,0x2850)]:
        assert reaches(write)
        assert not reaches(write,blocked_nodes=(read,))
        assert not reaches(write,blocked_nodes=(select,))
        assert not reaches(write,blocked_edges=((guard,success),))
        assert not reaches(write,start=write+4)
        checks.append({'write':hex(write),'required_X':hex(select),'required_V':hex(read),
                       'old_value_edge':[hex(guard),hex(success)],'same_entry_second_W':False})
    return checks


def check_sums(rel):
    rows = []
    for line in (ROOT / rel).read_text().splitlines():
        h, p = line.split(maxsplit=1)
        p = p.lstrip('*')
        q = ROOT / p
        ok = q.is_file() and digest(q.read_bytes()) == h
        rows.append({'path': p, 'sha256': h, 'ok': ok})
    assert rows and all(r['ok'] for r in rows)
    return rows


def unit_sections(data):
    rows = []
    for i in range(16):
        source, address, size, zero, zero_size = struct.unpack_from('>5I', data, 0x20 + 20*i)
        assert size and source + 0x200 + size <= len(data)
        rows.append({'index': i, 'file': source + 0x200, 'address': address,
                     'size': size, 'zero_address': zero, 'zero_size': zero_size})
    return rows


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    dat = DAT.read_bytes()
    assert len(dat) == 21148 and digest(dat) == 'a79020be40486ca4848511de48cfca2a544d034e977e1e014b64de444bdc0d3e'
    assert int.from_bytes(dat[28:32], 'big') == 141
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[80:112].hex() == trust['resident_build_id']
    assert dat[212:228].hex() == trust['resident_abi_id']
    assert dat[48:80].hex() == digest((ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes())
    header = bytearray(dat[:256]); header[20:24] = b'\0'*4
    assert zlib.crc32(header) == int.from_bytes(dat[20:24], 'big')
    assert zlib.crc32(dat[256:]) == int.from_bytes(dat[24:28], 'big')
    sections = [struct.unpack_from('>HHII', dat, 128+12*i) for i in range(7)]
    _, _, begin, length = sections[0]
    code = dat[begin:begin+length]
    es = elf_sections(ELF)
    assert es['.engine']['address'] == begin == 256
    assert es['.engine']['bytes'] == code
    assert code == (ELF.parent / 'engine.bin').read_bytes()
    assert es['.bss']['size'] == int.from_bytes(dat[116:120], 'big') == 1068
    assert es['.bss']['address'] == len(dat)
    reloc = dat[sections[1][2]:sections[1][2]+sections[1][3]]
    assert len(reloc) == 8 and int.from_bytes(dat[120:122], 'big') == 1
    patch, target = struct.unpack('>II', reloc)
    assert int.from_bytes(dat[patch:patch+4], 'big') == target
    (TMP / 'dat-code.bin').write_bytes(code)
    text = run(['-d', ELF], 'engine-elf.txt')
    raw = run(['-D', '-EB', '-b', 'binary', '-m', 'm32r', '--adjust-vma=256', TMP/'dat-code.bin'], 'dat-code.txt')
    run(['-h', '-t', ELF], 'engine-layout.txt')
    a, b = instructions(text), instructions(raw)
    executable = {x for x in a if x < 0x2c44}
    assert executable == {x for x in b if x < 0x2c44}
    assert all(a[x] == b[x] or (a[x][0] == b[x][0] and
               re.sub(r' <[^>]*>', '', a[x][1]).replace('0x','') ==
               re.sub(r' <[^>]*>', '', b[x][1]).replace('0x','')) for x in executable)
    calls = []
    for address, (_, line) in a.items():
        if re.search(r'\bbl 2bfc\b', line):
            nearby = [(x, a[x][1]) for x in sorted(a) if address-16 <= x < address]
            calls.append({'address': hex(address), 'before': nearby})
    assert len(calls) == 19
    save('rpc-sites.json', calls)
    save('rpc-constants.json', rpc_constants(a))
    save('rpc-flow.json', flow_checks(a))
    blocked = [0x200a544c,0x200a45e8,0x200a49d8,0x200a4910,0x200a40b4,
               0x200a449c,0x200a437c,0x200a3240,0x202d6f38,0x201c092c,
               0x2005bf5c,0x2005c038,0x20063f64,0x200c0dac,0x200c0db0]
    assert all(n.to_bytes(4, 'big') not in code for n in blocked)
    unit_path = ROOT/'firmware/package_v38_probe_p1/SD_ROOT/jlaunch3'
    unit = unit_path.read_bytes()
    assert digest(unit) == '951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
    us = unit_sections(unit)
    def at(address, size):
        matches = [s for s in us if s['address'] <= address and address+size <= s['address']+s['size']]
        assert len(matches) == 1
        s = matches[0]; offset = s['file']+address-s['address']
        return offset, unit[offset:offset+size], s
    offset, cell, section = at(0x2012ebe0, 4)
    assert offset == 0xe3de0 and cell == b'\xff'*4
    counter_at, counters, _ = at(0x2024615c, 16)
    assert counters == b'\0'*16
    for lo, hi, name in [(0x2024296c,0x2024321c,'unit-rpc.txt'),
                         (0x20241f70,0x202420b0,'unit-counters.txt'),
                         (0x20076254,0x200764a8,'unit-loader.txt'),
                         (0x20075e44,0x20075e88,'unit-main-read.txt'),
                         (0x2008dac0,0x2008db28,'unit-copy.txt')]:
        off, chunk, _ = at(lo, hi-lo)
        path = TMP/(name+'.bin'); path.write_bytes(chunk)
        run(['-D','-EB','-b','binary','-m','m32r','--adjust-vma='+str(lo),path],name)
    body_path=ROOT/'firmware/package_v38_probe_p1/SD_ROOT/ilaunch3'
    body=body_path.read_bytes()
    assert digest(body)=='d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
    resident_path=ROOT/'firmware/resident_v38/local/resident/build/resident.elf'
    resident=elf_sections(resident_path)
    body_sections=unit_sections(body)
    resident_matches={}
    for name in ('.resident','.root_pins'):
        s=resident[name]
        segment=next(x for x in body_sections if x['address']<=s['address'] and s['address']+s['size']<=x['address']+x['size'])
        off=segment['file']+s['address']-segment['address']
        assert body[off:off+s['size']]==s['bytes']
        resident_matches[name]={'address':hex(s['address']),'file':hex(off),'bytes':s['size'],'sha256':digest(s['bytes'])}
    resident_text=run(['-d',resident_path],'resident-elf.txt')
    run(['-h','-t',resident_path],'resident-layout.txt')
    resident_calls=[hex(address) for address,(_,line) in instructions(resident_text).items() if re.search(r'\bbl 20052ef8\b',line)]
    assert resident_calls==['0x20052924','0x200529c4','0x20053914','0x200539ac']
    run(['-d',ROOT/'firmware/peaking_probe/local/build/module_B.elf'],'old-core.txt')
    manifests = {p: check_sums(p) for p in ['research/peaking_probe_dat/SHA256SUMS',
                                         'firmware/package_v38_probe_p1/SHA256SUMS']}
    save('static.json', {'dat_sha256': digest(dat), 'dat_size': len(dat), 'generation': 141,
         'elf_sha256': digest(ELF.read_bytes()), 'code_sha256': digest(code),
         'resident_build_id': trust['resident_build_id'], 'resident_abi_id': trust['resident_abi_id'],
         'dat_elf_equal': True, 'dat_elf_disassembly_equal': True, 'rpc_calls': 19,
         'relocation': {'patch':hex(patch),'target':hex(target)},
         'checked_address_bytes': [hex(x) for x in blocked],
         'unit_sha256': digest(unit), 'unit_sections': us,
         'D_source': {'address':'0x2012ebe0','file':hex(offset),'bytes':cell.hex(),'section':section},
         'counter_source': {'file':hex(counter_at),'bytes':counters.hex()},
         'body_sha256':digest(body),'resident_elf_sha256':digest(resident_path.read_bytes()),
         'resident_matches':resident_matches,'resident_engine_call_sites':resident_calls,
         'manifest_counts': {p:len(rows) for p,rows in manifests.items()}})
    save('input-manifests.json', manifests)
    print('PASS: DAT identity, CRCs, ELF code equality, disassembly equality, 19 RPC sites, unit data, manifests')


if __name__ == '__main__':
    main()
