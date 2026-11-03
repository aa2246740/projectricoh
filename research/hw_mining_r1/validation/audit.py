#!/usr/bin/env python3
"""Read official GXR bytes; write evidence only below this directory.

Run with /usr/bin/python3 -I -B. This script never executes target firmware,
builds software, opens a device, or imports the other researchers' scripts.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
assert OUT == ROOT / 'research/hw_mining_r1/validation'
ZIP = ROOT / 'artifacts/downloads/gxr-151.zip'
ZIP_SHA = '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
BODY_SHA = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
J_SHA = '951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
STEMS = ('ilaunch', 'jlaunch', 'qlaunch', 'l08firm', 'klaunch', 'nlaunch', 'l06firm')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    path = (OUT / path).resolve()
    assert path.is_relative_to(OUT), path
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding='utf-8')
    return path


def save(path, data):
    return write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


class Image:
    def __init__(self, name):
        assert name in [s + '3' for s in STEMS]
        self.name = name
        self.path = OUT / 'official' / name
        self.data = self.path.read_bytes()
        if name == 'ilaunch3':
            assert digest(self.data) == BODY_SHA
        if name == 'jlaunch3':
            assert digest(self.data) == J_SHA
        self.segments = []
        for i in range(16):
            source, vma, size, bss, bss_size = struct.unpack_from('>5I', self.data, 0x20 + 20*i)
            assert source + 0x200 + size <= len(self.data)
            self.segments.append(dict(index=i, source=source, file_offset=source + 0x200,
                                      vma=vma, size=size, bss=bss, bss_size=bss_size))

    def offset(self, vma, n=1):
        matches = [s for s in self.segments if s['vma'] <= vma and vma+n <= s['vma']+s['size']]
        assert len(matches) == 1, (self.name, hex(vma), n)
        s = matches[0]
        return s['file_offset'] + vma - s['vma']

    def address(self, offset):
        s = next(s for s in self.segments if s['file_offset'] <= offset < s['file_offset'] + s['size'])
        return s['vma'] + offset - s['file_offset']

    def read(self, vma, n):
        a = self.offset(vma, n)
        return self.data[a:a+n]

    def u16(self, vma):
        return struct.unpack('>H', self.read(vma, 2))[0]

    def u32(self, vma):
        return struct.unpack('>I', self.read(vma, 4))[0]

    def disasm(self, a, b, label):
        assert a % 4 == 0 and b > a
        raw = self.read(a, b-a)
        stem = f'evidence/{self.name}-{label}-{a:08x}-{b:08x}'
        target = write(stem + '.bin', raw)
        cmd = [str(OBJDUMP), '-D', '-z', '-b', 'binary', '-m', 'm32r', '-EB',
               f'--adjust-vma=0x{a:x}', str(target)]
        run = subprocess.run(cmd, capture_output=True, text=True, check=True)
        write(stem + '.asm', run.stdout)
        save(stem + '.json', dict(image=self.name, image_sha256=digest(self.data),
             start=hex(a), end_exclusive=hex(b), file_offset=hex(self.offset(a)),
             bytes=len(raw), sha256=digest(raw), command=cmd, stderr=run.stderr))
        return stem


def verify_manifests():
    result = {}
    for name in ('gpt', 'grok', 'gemini'):
        base = ROOT / 'research/hw_mining_r1' / name
        rows = []
        for line in (base / 'SHA256SUMS').read_text().splitlines():
            h, rel = line.split(None, 1)
            rel = rel.lstrip('* ')
            p = (base / rel).resolve()
            assert p.is_relative_to(base.resolve())
            actual = sha_file(p) if p.is_file() else None
            rows.append(dict(path=rel, expected=h, actual=actual, ok=h == actual))
        result[name] = dict(entries=len(rows), all_ok=all(r['ok'] for r in rows), files=rows)
    save('input-manifests.json', result)
    print(json.dumps({k: {'entries': v['entries'], 'all_ok': v['all_ok']} for k, v in result.items()}))


def init():
    actual = sha_file(ZIP)
    assert actual == ZIP_SHA, actual
    members = {}
    wanted = {s + suffix for s in STEMS for suffix in ('3', '8')} | {'ilaunch4'}
    with zipfile.ZipFile(ZIP) as archive:
        for member in archive.infolist():
            name = Path(member.filename).name
            if name not in wanted:
                continue
            assert member.filename.startswith('GXR Update/Firmware rel 1.51/')
            assert name not in members
            data = archive.read(member)
            if name == 'ilaunch3':
                assert digest(data) == BODY_SHA
            if name == 'jlaunch3':
                assert digest(data) == J_SHA
            write('official/' + name, data)
            members[name] = dict(member=member.filename, bytes=len(data), sha256=digest(data))
    assert set(members) == wanted
    save('official-inputs.json', dict(zip=str(ZIP), sha256=actual, members=members,
         objdump=str(OBJDUMP), objdump_sha256=sha_file(OBJDUMP),
         objdump_version=subprocess.run([str(OBJDUMP), '--version'], capture_output=True,
                                       text=True, check=True).stdout))
    save('segments.json', {s+'3': Image(s+'3').segments for s in STEMS})
    protected = [ZIP, OBJDUMP, ROOT / 'research/hw_mining_r1/SYNTHESIS.md']
    for name in ('gpt', 'grok', 'gemini'):
        protected += [ROOT / 'research/hw_mining_r1' / name / f for f in ('REPORT.md', 'SHA256SUMS')]
    save('inputs-before.json', {str(p.relative_to(ROOT)): sha_file(p) for p in protected})
    verify_manifests()
    print('Official ZIP and 15 extracted members verified; correct ilaunch3 selected.')


def full_disasm(name):
    im = Image(name)
    windows = []
    for s in im.segments:
        if s['size']:
            windows.append(im.disasm(s['vma'], s['vma']+s['size'], f"sec{s['index']:02d}"))
    save(f'{name}-full-disasm.json', windows)
    print(name, len(windows), 'segments disassembled')


def refs(name, targets):
    im = Image(name)
    rows = {hex(t): dict(direct=[], constant_calls=[], constructions=[], pointers=[]) for t in targets}
    for rel in json.loads((OUT / f'{name}-full-disasm.json').read_text()):
        p = OUT / (rel + '.asm')
        registers = {}
        for no, line in enumerate(p.read_text().splitlines(), 1):
            m = re.match(r'^([0-9a-f]{8}):', line)
            if not m:
                continue
            for match in re.finditer(r'\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bgtz|blez|bltz)\s+([^|]*?)\b(0x[0-9a-f]+)', line):
                t = int(match[3], 16)
                if t in targets:
                    rows[hex(t)]['direct'].append(dict(pc=m[1], file_offset=hex(im.offset(int(m[1],16))),
                         text=line, source=str(p.relative_to(OUT)), line=no))
            code = re.split(r'\t', line)[-1]
            for insn in re.split(r'\s*(?:->|\|\|)\s*', code):
                op = insn.split(None,1)[0] if insn.strip() else ''
                body = insn.split(None,1)[1] if ' ' in insn else ''
                args = body.split(',')
                value = None
                dest = args[0] if args else ''
                if op in ('seth', 'ld24', 'ldi') and len(args) == 2:
                    value = int(args[1].lstrip('#'), 0)
                    if op == 'seth':
                        value <<= 16
                elif op in ('or3','add3','and3') and len(args) == 3:
                    src = registers.get(args[1])
                    imm = int(args[2].lstrip('#'),0)
                    if src is not None:
                        value = (src | imm) if op == 'or3' else ((src + imm) if op == 'add3' else (src & imm))
                elif op == 'mv' and len(args) == 2:
                    value = registers.get(args[1])
                elif op == 'addi' and len(args) == 2 and dest in registers:
                    value = registers[dest] + int(args[1].lstrip('#'),0)
                elif op in ('jl', 'jmp'):
                    target = registers.get(dest)
                    if target in targets:
                        rows[hex(target)]['constant_calls'].append(dict(pc=m[1], op=op, register=dest,
                            text=line, source=str(p.relative_to(OUT)), line=no,
                            note='Linear constant candidate; manually check preceding CFG.'))
                    if op == 'jl':
                        for reg in ['r'+str(i) for i in range(8)] + ['lr']:
                            registers.pop(reg, None)
                    else:
                        registers.clear()
                    continue
                if value is not None and re.fullmatch(r'r\d+|lr|fp|sp', dest):
                    registers[dest] = value & 0xffffffff
                    if registers[dest] in targets:
                        rows[hex(registers[dest])]['constructions'].append(dict(pc=m[1], text=line,
                            source=str(p.relative_to(OUT)), line=no))
                elif re.fullmatch(r'r\d+|lr|fp|sp', dest) and op not in (
                        'st','sth','stb','push','cmp','cmpu','cmpi','cmpui','beq','bne',
                        'beqz','bnez','bgez','bgtz','blez','bltz'):
                    registers.pop(dest, None)
    for t in targets:
        pattern = struct.pack('>I', t)
        off = 0
        while True:
            off = im.data.find(pattern, off)
            if off < 0:
                break
            try:
                vma = hex(im.address(off))
            except StopIteration:
                vma = None
            rows[hex(t)]['pointers'].append(dict(file_offset=hex(off), vma=vma,
                                                aligned=off % 4 == 0))
            off += 1
    outname = f'evidence/{name}-refs-' + '-'.join(f'{t:08x}' for t in targets)
    if len(outname) > 180:
        outname = f'evidence/{name}-refs-{digest(str(targets).encode())[:16]}'
    save(outname + '.json', rows)
    for target, group in rows.items():
        print(target, 'direct', len(group['direct']), 'constant calls',len(group['constant_calls']),
              'constructions', len(group['constructions']), 'pointers', len(group['pointers']))
        for r in group['direct'] + group['constant_calls']:
            print(r['text'])
        for r in group['pointers']:
            print(' pointer', r)


def params(name):
    data = (OUT / 'official' / name).read_bytes()
    page = address = domain = None
    sparse = {}
    writes = []
    for no, raw in enumerate(data[512:].splitlines(), 1):
        m = re.fullmatch(r'([XVWU])([0-9A-Fa-f]{4})', raw.strip().decode('latin1'))
        if not m:
            continue
        op, value = m[1], int(m[2], 16)
        if op == 'X':
            page = value
        elif op == 'U':
            domain = value
        elif op == 'V':
            address = value
        elif op == 'W':
            writes.append(dict(line=no, page=page, domain=domain, address=address, value=value))
            if domain == 0xEEF1 and page == 0x12C0 and address is not None:
                for i, x in enumerate(value.to_bytes(2, 'big')):
                    sparse[address+i] = x
            if address is not None:
                address += 2
    save(f'evidence/{name}-params.json', dict(writes=writes, bytes=sparse))
    return sparse


def seal():
    baseline = json.loads((OUT / 'inputs-before.json').read_text())
    now = {p: sha_file(ROOT / p) for p in baseline}
    save('inputs-after.json', now)
    assert baseline == now, 'Protected input drift'
    for name in ('source-input-hashes.json','metric-input-hashes.json','supplemental-input-hashes.json'):
        hashes=json.loads((OUT/'evidence'/name).read_text())
        assert all(sha_file(ROOT/p)==(h if isinstance(h,str) else h['sha256'])
                   for p,h in hashes.items()), name
    product=json.loads((OUT/'evidence/product-map.json').read_text())
    assert sha_file(ROOT/product['source'])==product['sha256']
    verification=json.loads((OUT/'evidence/verification.json').read_text())
    assert verification['all_ok']
    verify_manifests()
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    write('SHA256SUMS', ''.join(f'{sha_file(p)}  {p.relative_to(OUT)}\n' for p in files))
    check = []
    for line in (OUT / 'SHA256SUMS').read_text().splitlines():
        h, rel = line.split('  ', 1)
        ok = sha_file(OUT / rel) == h
        check.append(ok)
        print(f'{rel}: {"OK" if ok else "FAILED"}')
    assert all(check)
    print(f'{len(check)} files: ALL OK; protected inputs unchanged; report manifests ALL OK')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'full', 'window', 'refs', 'params', 'seal'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    if args.command == 'init':
        init()
    elif args.command == 'full':
        for name in args.args:
            full_disasm(name)
    elif args.command == 'window':
        print(Image(args.args[0]).disasm(int(args.args[1],0), int(args.args[2],0), args.args[3]))
    elif args.command == 'refs':
        refs(args.args[0], [int(t,0) for t in args.args[1:]])
    elif args.command == 'params':
        for name in args.args:
            sparse = params(name)
            print(name, {hex(a): sparse.get(a) for a in (0x2410,0x2418,0x2420,0x2444,0x2445)})
    elif args.command == 'seal':
        seal()


if __name__ == '__main__':
    main()
