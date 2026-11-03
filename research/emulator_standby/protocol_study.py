#!/usr/bin/python3
"""Verify archive members and record bounded M32R instruction windows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'evidence'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1')
ZIP = ROOT / 'artifacts/downloads/gxr-151.zip'
ZIP_SHA = '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    assert sha(ZIP.read_bytes()) == ZIP_SHA
    rows = []
    with zipfile.ZipFile(ZIP) as archive:
        for item in archive.infolist():
            if item.is_dir() or not item.filename.startswith('GXR Update/Firmware rel 1.51/'):
                continue
            name = Path(item.filename).name
            data = archive.read(item)
            local = ROOT / 'artifacts/firmware/gxr-1.51' / name
            actual = sha(local.read_bytes()) if local.is_file() else None
            rows.append(dict(member=item.filename, size=len(data), sha256=sha(data),
                             local=str(local.relative_to(ROOT)), local_sha256=actual,
                             equal=actual == sha(data)))
    assert len(rows) == 29
    assert all(r['equal'] for r in rows)
    result = dict(zip_sha256=ZIP_SHA, members=rows)
    (OUT / 'archive-members.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def window(name, start, end):
    rows = json.loads((OUT / 'archive-members.json').read_text())['members']
    member = next(r for r in rows if Path(r['member']).name == name)
    raw = (ROOT / member['local']).read_bytes()
    assert sha(raw) == member['sha256']
    for i in range(16):
        at, base, length, _, _ = struct.unpack_from('>5I', raw, 0x20 + 20*i)
        if base <= start < end <= base + length:
            data = raw[at + 0x200 + start - base:at + 0x200 + end - base]
            path = TEMP / f'{name}-{start:08x}-{end:08x}.bin'
            path.write_bytes(data)
            command = [str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),
                       '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                       f'--adjust-vma={start}', str(path)]
            text = subprocess.check_output(command, text=True)
            target = OUT / 'static' / f'{name}-{start:08x}-{end:08x}.txt'
            target.parent.mkdir(exist_ok=True)
            target.write_text(text)
            meta = dict(image=name, image_sha256=sha(raw), start=hex(start), end=hex(end),
                        bytes_sha256=sha(data), listing_sha256=sha(target.read_bytes()),
                        section=i, file_offset=at + 0x200 + start - base, command=command)
            target.with_suffix('.json').write_text(json.dumps(meta, indent=2) + '\n')
            return str(target.relative_to(ROOT))
    raise ValueError('requested window is not within a section')


if __name__ == '__main__':
    assert Path(os.environ['TMPDIR']).resolve() == TEMP
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', nargs='?')
    parser.add_argument('ranges', nargs='*')
    args = parser.parse_args()
    if not args.image:
        result = verify()
        print(json.dumps(dict(members=len(result['members']), all_equal=True)))
    else:
        for spec in args.ranges:
            start, end = [int(s, 16) for s in spec.split(':')]
            print(window(args.image, start, end))
