#!/usr/bin/env python3
"""离线核对官方成员，输出仅位于本脚本目录。"""
import hashlib
import json
import re
import struct
import subprocess
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
assert OUT == ROOT / 'research/hw_mining_r3/validation'
ARCHIVE = ROOT / 'artifacts/downloads/gxr-151.zip'
ARCHIVE_SHA = '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
UNITS = ('jlaunch', 'qlaunch', 'l08firm', 'nlaunch', 'klaunch', 'l06firm')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, data):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding='utf-8')
    return p


def save(name, value):
    return write(name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class Image:
    def __init__(self, name):
        self.name = name
        self.data = (OUT / 'official' / name).read_bytes()
        self.segments = []
        if name.endswith('3'):
            for i in range(16):
                src, vma, size, bss, bs = struct.unpack_from('>5I', self.data, 0x20 + 20*i)
                assert src + 0x200 + size <= len(self.data)
                self.segments.append(dict(index=i, source=src, file=src+0x200,
                                          vma=vma, size=size, bss=bss, bss_size=bs))
        elif name.endswith('0'):
            vma, size = struct.unpack_from('>II', self.data, 0x160)
            assert size+0x200 == len(self.data)
            self.segments = [dict(index=0, source=0, file=0x200, vma=vma, size=size,
                                  bss=0, bss_size=0)]

    def offset(self, address, size=1):
        found = [s for s in self.segments
                 if s['vma'] <= address and address+size <= s['vma']+s['size']]
        assert len(found) == 1, (self.name, hex(address), size)
        s = found[0]
        return s['file'] + address-s['vma']

    def address(self, offset):
        found = [s for s in self.segments if s['file'] <= offset < s['file']+s['size']]
        if len(found) != 1:
            return None
        return found[0]['vma'] + offset-found[0]['file']

    def read(self, address, size):
        p = self.offset(address, size)
        return self.data[p:p+size]

    def u32(self, address):
        return struct.unpack('>I', self.read(address, 4))[0]

    def disasm(self, address, size, label):
        raw = self.read(address, size)
        stem = f'evidence/{self.name}-{label}'
        path = write(stem+'.bin', raw)
        command = [str(OBJDUMP), '-D', '-z', '-b', 'binary', '-m', 'm32r', '-EB',
                   f'--adjust-vma=0x{address:x}', str(path)]
        run = subprocess.run(command, capture_output=True, text=True, check=True)
        write(stem+'.asm', run.stdout)
        save(stem+'.json', dict(member=self.name, member_sha256=sha(self.data),
                               vma=hex(address), file=hex(self.offset(address)), size=size,
                               bytes_sha256=sha(raw), command=command, stderr=run.stderr))
        return run.stdout


def verify_inputs():
    checks = []
    recorded = {}
    for directory in ('research/hw_mining_r3/gpt', 'research/hw_mining_r3/grok',
                      'research/hw_mining_r3/gemini', 'research/mcr_value_model_r1'):
        p = ROOT / directory / 'SHA256SUMS'
        recorded[str(p.relative_to(ROOT))] = sha(p.read_bytes())
        rows = []
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            digest, name = line.split(None, 1)
            f = (p.parent / name.lstrip('*')).resolve()
            assert f.is_relative_to(p.parent.resolve())
            actual = sha(f.read_bytes())
            recorded[str(f.relative_to(ROOT))] = actual
            rows.append(dict(path=str(f.relative_to(ROOT)), expected=digest,
                             actual=actual, ok=actual == digest))
        checks.append(dict(directory=directory, count=len(rows),
                           ok=all(x['ok'] for x in rows), files=rows))
    for name in ('research/hw_mining_r3/SYNTHESIS.md', 'research/t_persistence/REPORT.md',
                 'research/hw_mining_r2/validation/VALIDATION.md'):
        recorded[name] = sha((ROOT / name).read_bytes())
    for directory in ('firmware/engine_v38_b36/candidate/containers/product',
                      'firmware/resident_v36/containers/product'):
        for p in sorted((ROOT / directory).rglob('*')):
            if p.is_file() and p.suffix in ('.c', '.h', '.py'):
                recorded[str(p.relative_to(ROOT))] = sha(p.read_bytes())
    for name in ('firmware/engine_v38_b36/candidate/engine_services/services.c',
                 'firmware/resident_v36/engine_services/services.c'):
        recorded[name] = sha((ROOT / name).read_bytes())
    recorded[str(ARCHIVE.relative_to(ROOT))] = sha(ARCHIVE.read_bytes())
    recorded[str(OBJDUMP.relative_to(ROOT))] = sha(OBJDUMP.read_bytes())
    previous = OUT / 'inputs_before.json'
    if previous.exists():
        old = json.loads(previous.read_text())
        for name, digest in old.items():
            assert sha((ROOT / name).read_bytes()) == digest, name
        old.update(recorded)
        recorded = old
    save('evidence/material_checks.json', checks)
    save('inputs_before.json', recorded)
    assert all(x['ok'] for x in checks)
    return checks


def extract():
    assert sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA
    rows = []
    with zipfile.ZipFile(ARCHIVE) as z:
        for entry in z.infolist():
            if entry.is_dir():
                continue
            name = Path(entry.filename).name
            assert re.fullmatch(r'(?:[ijknq]launch|l0[68]firm)[03458]', name), name
            raw = z.read(entry.filename)
            write('official/'+name, raw)
            rows.append(dict(member=entry.filename, name=name, size=len(raw), sha256=sha(raw)))
    assert sha((OUT/'official/jlaunch3').read_bytes()) == '951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
    assert sha((OUT/'official/ilaunch3').read_bytes()) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    for row in rows:
        row['segments'] = Image(row['name']).segments
    version = subprocess.run([str(OBJDUMP), '--version'], capture_output=True,
                             text=True, check=True).stdout
    save('evidence/official_inputs.json', dict(archive_sha256=ARCHIVE_SHA, members=rows,
                                            objdump_sha256=sha(OBJDUMP.read_bytes()),
                                            objdump_version=version))
    return rows


def main():
    checks = verify_inputs()
    rows = extract()
    im = Image('jlaunch3')
    for s in im.segments:
        if s['size']:
            im.disasm(s['vma'], s['size'], f'segment-{s["index"]:02d}')
    windows = {
        'g1-a': (0x20251180, 0xa0),
        'g1-b': (0x202516a0, 0xa0),
        'g1-c': (0x20252264, 0xa0),
        'g1-d': (0x20252e78, 0xa0),
        'g1-e': (0x20258684, 0xa0),
        'protocol-read': (0x20242940, 0x250),
        'protocol-v': (0x20242b68, 0x1a0),
        'protocol-w': (0x20242d94, 0x2b8),
        'protocol-x': (0x2024304c, 0x160),
        'mcr': (0x20112394, 0xe0),
        'front-apply': (0x2010c474, 0x314),
        'isp-apply': (0x2010c248, 0x1ac),
        'type-dispatch': (0x20255600, 0x140),
        'gate-before': (0x20257de4, 0x64c),
        'gate-after': (0x20258430, 0xcc8),
        'register-writers': (0x20256988, 0xc58),
        'front-start': (0x20250fd4, 0x410),
        'front-second': (0x20251508, 0x520),
        'capture-start': (0x202520a0, 0x5dc),
        'isp-start': (0x2025267c, 0x42c),
        'combined-start': (0x20252aa8, 0x82c),
        'front-controller': (0x20105380, 0x1b0),
        'isp-controller': (0x20105480, 0x134),
        'mcm-writer': (0x20257550, 0xfc),
        'mcm-submit': (0x20113954, 0x18),
        'mcm-packer': (0x2011396c, 0xb80),
        'front-slots': (0x201130e8, 0x250),
        'front-builder': (0x2010d3b4, 0x2d0),
        'capture-apply': (0x201a40c0, 0x520),
        'protocol-wrapper-x': (0x20243178, 0x94),
        'protocol-wrapper-v': (0x20242ce4, 0xb0),
        'isp-build': (0x2010beb0, 0x398),
        'isp-slots': (0x2011a768, 0x160),
        'debug-names': (0x20105678, 0x7a8),
        'unit-loader': (0x20076254, 0x240),
        't-default-copy': (0x20065ca0, 0x50),
        'isp-controller-full': (0x20105480, 0x134),
    }
    for label, (a, n) in windows.items():
        im.disasm(a, n, label)
    print(json.dumps(dict(materials=[dict(directory=x['directory'], count=x['count'], ok=x['ok'])
                                    for x in checks], members=len(rows), windows=len(windows),
                          segments=[{k:hex(v) if k in ('vma','file','size') else v
                                     for k,v in s.items()} for s in im.segments]), ensure_ascii=False))


if __name__ == '__main__':
    main()
