#!/usr/bin/env python3
"""Read-only static evidence collection for body-v4-storage-r1-gemini.
All Ricoh-derived bytes and disassemblies stay inside local/."""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
EXPECTED = {
    OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    BODY: '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
}


def preflight():
    p = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert p['MountPoint'] == '/Volumes/Workspace'
    assert p['FilesystemType'] == 'apfs'
    assert p['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert p['WritableVolume']
    OUT.mkdir(parents=True, exist_ok=True)
    ignored = subprocess.run(['git', 'check-ignore', '-q', str(OUT / 'guard')], cwd=ROOT)
    assert ignored.returncode == 0, 'local/ must be ignored before derived writes'
    return {k: p[k] for k in ('MountPoint', 'FilesystemType', 'VolumeUUID', 'WritableVolume')}


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, obj):
    assert re.fullmatch(r'[a-zA-Z0-9_.-]+', name)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


class Image:
    def __init__(self):
        for p, expected in EXPECTED.items():
            assert sha(p) == expected, str(p)
        self.data = OFFICIAL.read_bytes()
        self.body = BODY.read_bytes()
        self.sections = []
        for i in range(16):
            src, va, n, bss, bn = struct.unpack_from('>IIIII', self.data, 32 + i * 20)
            assert src + 512 + n <= len(self.data)
            self.sections.append(dict(index=i, file=src + 512, vma=va, size=n, bss=bss, bss_size=bn))

    def off(self, va, n=1):
        hits = [s['file'] + va - s['vma'] for s in self.sections
                if s['vma'] <= va and va + n <= s['vma'] + s['size']]
        assert len(hits) == 1, hex(va)
        return hits[0]

    def raw(self, va, n):
        o = self.off(va, n)
        return self.data[o:o+n]

    def dump(self, start, end, label):
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+', label)
        raw = self.raw(start, end - start)
        o = self.off(start, len(raw))
        assert self.body[o:o+len(raw)] == raw, 'v3.6 changes this window: ' + label
        p = OUT / (label + '.bin')
        p.write_bytes(raw)
        args = [str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                '--adjust-vma=' + hex(start), str(p)]
        result = subprocess.check_output(args, text=True)
        (OUT / (label + '.asm.txt')).write_text(
            '# Official bytes equal fixed v3.6 body in this window. Linear disassembly includes data.\n'
            + '# File offset ' + hex(o) + ', VMA ' + hex(start) + '\n' + result)
        print(label, hex(start), hex(end), len(raw), sha(p))

    def compare(self, start, end, label):
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+', label)
        off = self.off(start, end - start)
        official, body = self.raw(start, end - start), self.body[off:off+end-start]
        rows = [{'vma': hex(start+i), 'file': hex(off+i), 'official': x, 'body': y}
                for i, (x, y) in enumerate(zip(official, body)) if x != y]
        save(label + '.compare.json', {
            'start': hex(start), 'end': hex(end), 'file': hex(off),
            'equal': not rows, 'differences': rows
        })
        for suffix, raw in (('', official), ('.body', body)):
            binary = OUT / (label + suffix + '.bin')
            binary.write_bytes(raw)
            output = subprocess.check_output([
                str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                '--adjust-vma=' + hex(start), str(binary)
            ], text=True)
            target = OUT / (label + ('.body.txt' if suffix else '.asm.txt'))
            target.write_text('# Compare sidecar records official/body differences; no equality claim.\n' + output)
        print(label, 'compared', len(rows), 'different bytes')


def inputs():
    files = set(EXPECTED) | {
        OBJDUMP,
        ROOT / 'docs/RESEARCH_PROTOCOL.md',
        ROOT / 'firmware/resident_v34c/policy_machine.py',
        ROOT / 'firmware/stage2l_switch/tools/build.py',
        ROOT / 'firmware/resident_v36/REPORT.md',
        ROOT / 'firmware/resident_v36/native_contract.py',
        ROOT / 'firmware/resident_v36/local/resident/size.json',
        ROOT / 'firmware/resident_v36/local/resident/hooks.json',
        ROOT / 'firmware/resident_v36/local/resident/build/resident.elf',
    }
    for folder in (
        'research/user_storage_r1',
        'research/user_storage_r2',
        'research/user_storage_r3',
        'firmware/resident_v36/resident',
    ):
        files.update(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update((ROOT / 'research/irom_storage/local').glob('section*.asm.txt'))
    files.add(ROOT / 'research/irom_storage/local/address_candidates.json')
    return {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(files)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('before', 'after', 'dump', 'compare', 'refs', 'pointers', 'words'))
    ap.add_argument('rest', nargs='*')
    a = ap.parse_args()
    volume = preflight()
    im = Image()
    if a.action in ('before', 'after'):
        now = inputs()
        if a.action == 'before':
            if not (OUT / 'protected-before.json').exists():
                save('protected-before.json', now)
                save('volume.json', volume)
                save('sections.json', im.sections)
        else:
            before = json.loads((OUT / 'protected-before.json').read_text())
            changes = [k for k in sorted(before.keys() | now.keys()) if before.get(k) != now.get(k)]
            save('protected-after.json', now)
            save('protected-check.json', {'status': 'PASS' if not changes else 'FAIL', 'changes': changes})
            assert not changes, changes
        print(a.action, len(now), 'protected inputs')
    elif a.action == 'dump':
        im.dump(int(a.rest[0], 0), int(a.rest[1], 0), a.rest[2])
    elif a.action == 'compare':
        im.compare(int(a.rest[0], 0), int(a.rest[1], 0), a.rest[2])
    elif a.action == 'refs':
        lo = int(a.rest[0], 0)
        hi = int(a.rest[1], 0) if len(a.rest) > 1 else lo + 1
        rows = json.loads((ROOT / 'research/irom_storage/local/address_candidates.json').read_text())
        selected = [r for r in rows if lo <= r['target'] < hi]
        save('refs-' + hex(lo) + '.json', selected)
        for r in selected:
            print(json.dumps({k: hex(v) if isinstance(v, int) else v for k, v in r.items()}))
        print('syntactic candidates:', len(selected))
    elif a.action == 'pointers':
        target = int(a.rest[0], 0)
        value = target.to_bytes(4, 'big')
        rows = []
        for s in im.sections:
            raw = im.raw(s['vma'], s['size'])
            at = raw.find(value)
            while at >= 0:
                rows.append({
                    'vma': hex(s['vma'] + at),
                    'file': hex(s['file'] + at),
                    'target': hex(target),
                    'aligned4': at % 4 == 0,
                })
                at = raw.find(value, at + 1)
        save('pointers-' + hex(target) + '.json', rows)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif a.action == 'words':
        lo, hi = (int(x, 0) for x in a.rest)
        for va in range(lo, hi, 16):
            b = im.raw(va, min(16, hi - va))
            print(hex(va), b.hex(), ''.join(chr(x) if 32 <= x < 127 else '.' for x in b))


if __name__ == '__main__':
    main()
