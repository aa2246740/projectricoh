#!/usr/bin/env python3
"""Read-only M32R evidence extraction. All firmware-derived output stays in local/."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
FW = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
TOOL = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
PIN = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'


def preflight():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert v['MountPoint'] == '/Volumes/Workspace'
    assert v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['FilesystemType'] == 'apfs' and v['WritableVolume'] and v['WritableMedia']
    assert ROOT == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
    assert HERE == ROOT / 'research/stack_headroom' and os.access(HERE, os.W_OK)
    subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', str(LOCAL/'check.bin')], check=True)
    return v


def sections(data):
    out = []
    for i in range(16):
        src, va, n, bss, bs = struct.unpack_from('>IIIII', data, 0x20+20*i)
        assert src+512+n <= len(data)
        out.append(dict(index=i, file=src+512, va=va, end=va+n, size=n, bss=bss, bss_size=bs))
    return out


def read(data, secs, va, n):
    for s in secs:
        if s['va'] <= va and va+n <= s['end']:
            off = s['file']+va-s['va']
            return data[off:off+n]
    raise ValueError(f'unmapped {va:#x}+{n:#x}')


def dump(raw, lo):
    return subprocess.check_output([str(TOOL), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
        '--disassemble-zeroes', f'--adjust-vma={lo:#x}', str(raw)], text=True)


def instructions(asm):
    # Objdump places each operation of an M32R packet on a separate line.
    for line in asm.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ){1,7}[0-9a-f]{2})\s+(.+)$', line)
        if m:
            yield int(m[1], 16), bytes.fromhex(m[2]), m[3].strip()


def window(data, secs, lo, hi):
    assert lo % 4 == 0 and hi % 4 == 0 and hi > lo
    stem = f'body-{lo:08x}-{hi:08x}'
    raw = LOCAL/(stem+'.bin')
    raw.write_bytes(read(data, secs, lo, hi-lo))
    asm = dump(raw, lo)
    (LOCAL/(stem+'.asm.txt')).write_text(asm)
    checked = 0
    for pc, code, _ in instructions(asm):
        assert code == read(data, secs, pc, len(code)), (hex(pc), code.hex())
        checked += len(code)
    assert checked == hi-lo, (stem, checked, hi-lo)
    return stem, asm


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['inventory', 'win', 'words', 'find', 'verify'])
    ap.add_argument('values', nargs='*')
    ap.add_argument('--limit', type=int, default=70)
    a = ap.parse_args()
    v = preflight()
    data = FW.read_bytes()
    assert hashlib.sha256(data).hexdigest() == PIN
    secs = sections(data)
    if a.action == 'inventory':
        identity = dict(firmware=str(FW.relative_to(ROOT)), sha256=PIN, size=len(data), sections=secs,
            objdump_sha256=hashlib.sha256(TOOL.read_bytes()).hexdigest(),
            objdump_version=subprocess.check_output([str(TOOL), '--version'], text=True).splitlines()[0],
            volume_uuid=v['VolumeUUID'], scope='read-only static; no target execution or firmware build')
        (LOCAL/'inventory.json').write_text(json.dumps(identity, indent=2)+'\n')
        print(json.dumps(identity, indent=2))
    elif a.action == 'win':
        lo, hi = [int(x, 16) for x in a.values]
        stem, asm = window(data, secs, lo, hi)
        lines = [line for line in asm.splitlines() if re.match(r'^\s*[0-9a-f]+:', line)]
        print(f'{stem}: {hi-lo} bytes checked; {len(lines)} operations')
        print('\n'.join(lines[:a.limit]))
    elif a.action == 'words':
        lo, hi = [int(x, 16) for x in a.values]
        rows = []
        for pc in range(lo, hi, 4):
            b = read(data, secs, pc, 4)
            rows.append(dict(address=f'{pc:#010x}', bytes=b.hex(), word=f'{int.from_bytes(b,"big"):#010x}'))
        (LOCAL/f'words-{lo:08x}-{hi:08x}.json').write_text(json.dumps(rows, indent=2)+'\n')
        print('\n'.join(f'{r["address"]} {r["bytes"]} {r["word"]}' for r in rows[:a.limit]))
    elif a.action == 'find':
        value = int(a.values[0], 16)
        needle = value.to_bytes(4, 'big')
        hits = []
        for s in secs:
            region = data[s['file']:s['file']+s['size']]
            off = region.find(needle)
            while off >= 0:
                hits.append(dict(address=hex(s['va']+off), section=s['index'], aligned=off%4==0))
                off = region.find(needle, off+1)
        (LOCAL/f'find-{value:08x}.json').write_text(json.dumps(hits, indent=2)+'\n')
        print(json.dumps(hits[:a.limit]))
    else:
        checked = 0
        windows = []
        for p in sorted(LOCAL.glob('body-*.bin')):
            lo, hi = [int(x,16) for x in re.fullmatch(r'body-([0-9a-f]+)-([0-9a-f]+)\.bin',p.name).groups()]
            assert p.read_bytes() == read(data, secs, lo, hi-lo)
            asm = p.with_suffix('.asm.txt').read_text()
            assert dump(p, lo) == asm
            n = 0
            for pc, code, _ in instructions(asm):
                assert code == read(data, secs, pc, len(code)), hex(pc)
                n += len(code)
            assert n == hi-lo, (p.name, n, hi-lo)
            checked += n
            windows.append(p.name)
        assert windows
        result = dict(status='PASS_STATIC_BYTES', firmware_sha256=PIN, windows=len(windows),
            decoded_bytes_checked=checked, camera_access=False, firmware_build=False)
        (LOCAL/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
