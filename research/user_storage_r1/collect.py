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
    'file-open-read-write-close': (0x200a40b4, 0x200a46f0),
    'file-open-low': (0x200a65f8, 0x200a6750),
    'file-seek-wrappers': (0x200a46f0, 0x200a4910),
    'seek-low': (0x200ad9c0, 0x200ae5c0),
    'write-close-low': (0x200aaf00, 0x200ab4f0),
    'file-close-core': (0x200a6750, 0x200a6cc0),
    'seek-candidate': (0x200a4c60, 0x200a4f30),
    'seek-wrapper-tail': (0x200a4e90, 0x200a5320),
    'seek-core': (0x200a7c48, 0x200a8ad0),
    'fat-file-init': (0x200b3ccc, 0x200b4020),
    'fat-open-existing': (0x200b4824, 0x200b4da0),
    'fat-sync-metadata': (0x200b8880, 0x200b8b40),
    'fat-flags': (0x200b78b8, 0x200b7a10),
    'fat-directory-write': (0x200b55c0, 0x200b5890),
    'fat-close-directory-fields': (0x200b4b5c, 0x200b4f00),
    'settings-default-transfer': (0x20066b00, 0x20066e90),
    'settings-save-restore': (0x20067460, 0x20067d00),
    'settings-load-init': (0x20067cd8, 0x20067f80),
    'settings-persist-full': (0x20067bb4, 0x20067cd8),
    'settings-power-save': (0x2006a050, 0x2006a224),
    'settings-storage-copy': (0x20099764, 0x200998d0),
    'settings-high-fields': (0x2027039c, 0x20270420),
    'restore-default-candidate': (0x2035c980, 0x2035ce80),
    'irom-update-format': (0x2010d70c, 0x2010d7e0),
    'irom-format-wrapper': (0x200994cc, 0x20099570),
    'irom-format-core': (0x20099960, 0x20099a00),
    'format-wrapper': (0x200a3e64, 0x200a3eb8),
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
    files = set(EXPECTED) | {OBJDUMP}
    for d in ('firmware/engine_v38_b36/resident',
              'firmware/engine_v38_b36/candidate/engine_services',
              'firmware/resident_v36/resident'):
        files.update(p for p in (ROOT / d).rglob('*')
                     if p.is_file() and p.suffix in ('.c', '.h', '.S', '.ld', '.py'))
    for rel in ('research/irom_storage/REPORT.md', 'research/irom_storage/STORAGE_ABI.md',
                'research/stage1_data/REPORT.md', 'research/review_full_r4/REPORT.md',
                'research/daily_bugs_20261024/REPORT.md',
                'research/review_v35_container/REVIEW.md',
                'research/review_v35_container/native_probe.py',
                'research/review_v35_container/native/replay-results.json',
                'research/irom_storage/local/address_candidates.json',
                'research/irom_storage/local/query.py',
                'firmware/image_v36/REPORT.md',
                'firmware/engine_v38_b36/candidate/containers/product/adapter.c',
                'firmware/engine_v38_b36/candidate/containers/product/service_build.py',
                'firmware/engine_v38_b36/candidate/service_build.py'):
        p = ROOT / rel
        if p.is_file():
            files.add(p)
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
