#!/usr/bin/env python3
"""Offline evidence collector; writes only beside this file. No firmware build."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import struct
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E = HERE / 'evidence'
OFFICIAL_SHA = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
ZIP_SHA = '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(name, value):
    p = E / name
    p.resolve().relative_to(HERE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def guard():
    v = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert v['FilesystemType'] == 'apfs' and v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['WritableVolume'] and v['WritableMedia']
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/cpu_speed_r1')
    assert not HERE.is_symlink()

def protected():
    dirs = ['firmware/stage2k_p0', 'research/stage2k_p0', 'research/body_lut',
            'research/body_lut_r2', 'firmware/lut_p0_timing', 'research/review_lut_p0_r2',
            'research/review_v35_container', 'firmware/resident_v36', 'firmware/engine_v38_b36']
    result = {}
    for name in dirs:
        for p in sorted((ROOT / name).rglob('*')):
            if p.is_file():
                result[str(p.relative_to(ROOT))] = sha(p.read_bytes())
    for name in ['artifacts/downloads/gxr-151.zip', 'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
                 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc']:
        p = ROOT / name
        result[name] = sha(p.read_bytes())
    return result

def sections(data):
    result = []
    for i in range(16):
        src, base, size, bss, bss_size = struct.unpack_from('>5I', data, 32+20*i)
        result.append(dict(index=i, file_offset=512+src, base=base, size=size, bss=bss, bss_size=bss_size))
    return result

def firmware():
    data = (E/'official/ilaunch3').read_bytes()
    assert sha(data) == OFFICIAL_SHA
    return data

def window(name, start, end):
    data = firmware()
    matches = [s for s in sections(data) if s['base'] <= start < end <= s['base']+s['size']]
    assert len(matches) == 1, (hex(start), hex(end))
    s = matches[0]
    off = s['file_offset']+start-s['base']
    blob = data[off:off+end-start]
    p = E/'native'/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.with_suffix('.bin').write_bytes(blob)
    cmd = [str(OBJDUMP), '-D','-b','binary','-m','m32r','-EB',f'--adjust-vma={start}',str(p.with_suffix('.bin'))]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    p.with_suffix('.txt').write_text(r.stdout)
    save(f'native/{name}.json', dict(start=hex(start), end=hex(end), file_offset=hex(off),sha256=sha(blob),argv=cmd))
    return str(p.with_suffix('.txt').relative_to(HERE))

def init():
    E.mkdir(parents=True, exist_ok=True)
    assert not (E/'protected-before.json').exists(), 'Already initialized'
    save('protected-before.json', protected())
    z = ROOT/'artifacts/downloads/gxr-151.zip'
    assert sha(z.read_bytes()) == ZIP_SHA
    with zipfile.ZipFile(z) as f:
        data = f.read('GXR Update/Firmware rel 1.51/ilaunch3')
    assert sha(data) == OFFICIAL_SHA
    p = E/'official/ilaunch3'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    save('official/identity.json', dict(zip=str(z), zip_sha256=ZIP_SHA, member='GXR Update/Firmware rel 1.51/ilaunch3',
        member_sha256=sha(data), member_size=len(data), sections=sections(data)))
    save('environment.json', dict(cwd=str(ROOT), python=sys.version, no_camera=True, no_card=True,
        no_firmware_build=True, write_root=str(HERE),
        git_status=subprocess.check_output(['git','status','--short','--untracked-files=normal'],cwd=ROOT,text=True)))
    print('initialized; frozen files', len(json.loads((E/'protected-before.json').read_text())))

def finish():
    before=json.loads((E/'protected-before.json').read_text())
    after=protected()
    changes=[p for p in set(before)|set(after) if before.get(p)!=after.get(p)]
    save('protected-verification.json', dict(files=len(before), added_removed_or_changed=sorted(changes), all_ok=not changes))
    assert not changes, changes[:10]
    print('protected inputs all OK:',len(before))

if __name__ == '__main__':
    guard()
    if sys.argv[1]=='init': init()
    elif sys.argv[1]=='window': print(window(sys.argv[2],int(sys.argv[3],0),int(sys.argv[4],0)))
    elif sys.argv[1]=='finish': finish()
    else: raise ValueError(sys.argv[1])
