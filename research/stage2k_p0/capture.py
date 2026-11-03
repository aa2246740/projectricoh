#!/usr/bin/env python3
"""Capture bounded, private static evidence without changing protected inputs."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/stage2k_p0/local'
EXPECTED_VOLUME = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
ALLOWED = ('research/stage2k_p0/', 'firmware/stage2k_p0/',
           'artifacts/stage2k-p0-packages/')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def preflight():
    info = plistlib.loads(subprocess.check_output(
        ['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == EXPECTED_VOLUME
    assert info['MountPoint'] == '/Volumes/Workspace'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume']
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert ROOT.resolve() == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
    assert (ROOT / 'research/stage2k_p0/.gitignore').read_text() == 'local/\n'
    ignored = subprocess.check_output(['git', 'check-ignore', '-v',
        'research/stage2k_p0/local/check', 'firmware/stage2k_p0/local/check',
        'artifacts/stage2k-p0-packages/check'], cwd=ROOT, text=True)
    assert len(ignored.splitlines()) == 3
    return info, ignored


def main():
    info, ignored = preflight()
    OUT.mkdir(exist_ok=True)
    (OUT / 'tmp').mkdir(exist_ok=True)
    (OUT / 'volume.json').write_text(json.dumps(info, default=str, indent=2) + '\n')
    (OUT / 'ignore.txt').write_text(ignored)
    (OUT / 'df.txt').write_bytes(subprocess.check_output(['df', '-h', '/Volumes/Workspace']))
    paths = [ROOT / 'firmware/stage2j', ROOT / 'artifacts/stage2j-packages',
             ROOT / 'artifacts/firmware/gxr-1.51']
    protected = {str(p.relative_to(ROOT)): digest(p.read_bytes())
                 for base in paths for p in sorted(base.rglob('*')) if p.is_file()}
    before = OUT / 'protected-current-before.json'
    if before.exists():
        assert json.loads(before.read_text()) == protected, 'protected input changed'
    else:
        before.write_text(json.dumps(protected, indent=2) + '\n')
    image = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    assert digest(image) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    assert digest((ROOT / 'artifacts/stage2j-packages/stage2j/candidate/SD_ROOT/ilaunch3').read_bytes()) == 'f181b7a451b28caafe1ef62b93a9b5f64e18a61fbee49aa9ac50dbc305d2c60e'
    segments = [struct.unpack_from('>5I', image, 32 + i * 20) for i in range(16)]
    windows = [(0x2004BAC0,0x2004BAEC), (0x200930E0,0x20093320),
               (0x204026F8,0x2040278C), (0x20401FE4,0x20402080),
               (0x2005BF00,0x2005C11C), (0x2005F164,0x2005F250),
               (0x0500C570,0x0500C5A0), (0x05001000,0x05001300),
               (0x2006DD3C,0x2006DE08), (0x2006E12C,0x2006E200),
               (0x2005276C,0x20052900)]
    objdump = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    records = []
    for a,b in windows:
        hits = [(i,s+512+a-v) for i,(s,v,n,_,_) in enumerate(segments)
                if v <= a and b <= v+n]
        assert len(hits) == 1
        i,pos = hits[0]
        raw = OUT / f'official-{a:08x}-{b:08x}.bin'
        asm = raw.with_suffix('.asm')
        data = image[pos:pos+b-a]
        raw.write_bytes(data)
        command = [str(objdump), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                   f'--adjust-vma={a:#x}', str(raw)]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        asm.write_text(result.stdout)
        records.append(dict(start=hex(a), end=hex(b), segment=i,
            file_offset=hex(pos), sha256=digest(data), disassembly_sha256=digest(result.stdout.encode()),
            command=command))
    (OUT / 'windows.json').write_text(json.dumps(dict(
        image_sha256=digest(image), objdump_sha256=digest(objdump.read_bytes()),
        windows=records), indent=2) + '\n')
    print(json.dumps(dict(protected_files=len(protected), windows=len(records), volume_ok=True)))


if __name__ == '__main__':
    main()
