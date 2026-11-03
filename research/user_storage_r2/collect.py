#!/usr/bin/env python3
"""Read-only source/binary evidence collection. Writes only this task's local/."""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
EXPECTED = {
    OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    BODY: '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
}
WINDOWS = {
    'wrapper-all': (0x200a3d20, 0x200a5650),
    'lower-open-close': (0x200a65f8, 0x200a6cc0),
    'lower-seek': (0x200a7c48, 0x200a8ad0),
    'lower-read-write-geometry': (0x200aad38, 0x200ab670),
    'chain-transition': (0x200b0000, 0x200b10fc),
    'media-dispatch': (0x200b10fc, 0x200b1420),
    'file-init': (0x200b3af8, 0x200b4050),
    'open-existing': (0x200b4824, 0x200b4f00),
    'fat-finalize': (0x200b55c0, 0x200b5890),
    'chain-close': (0x200b71b0, 0x200b82cc),
    'directory-write': (0x200b823c, 0x200b8890),
    'flush-release': (0x200b8890, 0x200ba280),
    'fd-select-init': (0x200af1c0, 0x200afc80),
    'media-error-state': (0x200aaca0, 0x200aad38),
    'native-utils': (0x200ba280, 0x200ba330),
    'photo-create': (0x2010ec00, 0x20110420),
    'photo-path': (0x20114100, 0x20114460),
    'dcf-path': (0x20114d20, 0x20114f80),
    'dcf-path2': (0x20119330, 0x20119700),
    'time-state': (0x200a9b10, 0x200a9bf0),
    'creation-flag': (0x200a8ba0, 0x200a8c60),
    'metadata-times': (0x200acfa0, 0x200ad0e0),
    'photo-name-builder': (0x201166e8, 0x201168b0),
    'native-create-time': (0x200a554c, 0x200a5840),
}



def preflight():
    p = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert p['MountPoint'] == '/Volumes/Workspace'
    assert p['FilesystemType'] == 'apfs'
    assert p['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert p['WritableVolume']
    OUT.mkdir(exist_ok=True)
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


def inputs():
    files = set(EXPECTED) | {OBJDUMP,
        ROOT/'firmware/resident_v34c/policy_machine.py',
        ROOT/'firmware/stage2l_switch/tools/build.py'}
    files.update(p for p in (ROOT/'research/user_storage_r1').rglob('*') if p.is_file())
    previous = json.loads((ROOT/'research/user_storage_r1/local/protected-before.json').read_text())
    files.update(ROOT / rel for rel in previous)
    files.update(ROOT / rel for rel in (
        'research/irom_storage/local/address_candidates.json',
        'research/irom_storage/local/section01.asm.txt',
        'research/irom_storage/REPORT.md',
        'research/irom_storage/STORAGE_ABI.md'))
    return {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)}
            for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('before', 'after', 'dump', 'windows', 'refs', 'words'))
    parser.add_argument('rest', nargs='*')
    a = parser.parse_args()
    volume = preflight()
    im = Image()
    if a.action in ('before', 'after'):
        current = inputs()
        save('protected-' + a.action + '.json', current)
        if a.action == 'before':
            save('volume.json', volume)
            save('sections.json', im.sections)
        else:
            old = json.loads((OUT / 'protected-before.json').read_text())
            changes = [k for k in old.keys() | current.keys() if old.get(k) != current.get(k)]
            save('protected-check.json', {'status': 'PASS' if not changes else 'FAIL', 'changes': changes})
            assert not changes, changes
        print(a.action, len(current), 'protected files')
    elif a.action == 'dump':
        im.dump(int(a.rest[0], 0), int(a.rest[1], 0), a.rest[2])
    elif a.action == 'windows':
        for label, (start, end) in WINDOWS.items():
            im.dump(start, end, label)
    elif a.action == 'refs':
        lo = int(a.rest[0], 0)
        hi = int(a.rest[1], 0) if len(a.rest) > 1 else lo + 1
        rows = json.loads((ROOT / 'research/irom_storage/local/address_candidates.json').read_text())
        selected = [r for r in rows if lo <= r['target'] < hi]
        save('refs-' + hex(lo) + '.json', selected)
        for r in selected:
            print(json.dumps({k: hex(v) if isinstance(v, int) else v for k, v in r.items()}))
        print('syntactic candidates:', len(selected), 'not complete reference coverage')
    else:
        lo, hi = (int(x, 0) for x in a.rest)
        for va in range(lo, hi, 16):
            b = im.raw(va, min(16, hi - va))
            print(hex(va), b.hex(), ''.join(chr(x) if 32 <= x < 127 else '.' for x in b))


if __name__ == '__main__':
    main()
