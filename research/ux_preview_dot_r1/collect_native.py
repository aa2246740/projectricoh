"""Extract and disassemble only the official windows used in the UX audit."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools/native_harness'))
from image_loader import Image

def main():
    out = HERE / 'local/native'
    out.mkdir(parents=True, exist_ok=True)
    archive = ROOT / 'artifacts/downloads/gxr-151.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
    with zipfile.ZipFile(archive) as z:
        raw = z.read('GXR Update/Firmware rel 1.51/ilaunch3')
    body = out / 'ilaunch3'
    body.write_bytes(raw)
    image = Image(body, 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7')
    index = []
    for label, start, end in (
        ('constructor', 0x20287080, 0x20287304),
        ('list-render', 0x201ff3d4, 0x20200184),
        ('draw-wrapper', 0x201fd360, 0x201fd418),
        ('confirm-dispatch', 0x202c2abc, 0x202c33e4),
        ('state56-events', 0x203764c8, 0x20376680),
        ('hardware-key-names', 0x20377500, 0x203775b0),
        ('mode-getter', 0x20271fec, 0x20272078),
        ('adj-open-dispatch', 0x202ba5c8, 0x202bab34),
        ('common-key-handlers', 0x202b7d40, 0x202b87c0),
        ('half-first-handler', 0x2029fdc4, 0x202a00e4),
        ('half-second-handler', 0x202bd724, 0x202bdd30),
        ('half-commit-helper', 0x202be978, 0x202becc4),
        ('native-keep-flag', 0x20265818, 0x20265830),
        ('image-item-arm', 0x202ba32c, 0x202ba3d0),
        ('cursor-down', 0x202c25b8, 0x202c2880),
        ('cursor-up', 0x202c2880, 0x202c2abc),
        ('cursor-hook-caller', 0x202bb3c0, 0x202bb520),
        ('native-navigation', 0x202897ac, 0x20289c40),
        ('native-view-cursor', 0x201ca510, 0x201ca7c0),
        ('view-event-dispatch', 0x201c0ea4, 0x201c1100),
        ('key-translator', 0x202afe98, 0x202b01f0),
        ('physical-key-table', 0x20375f00, 0x20375f90),
        ('state5-adj-entry', 0x20375520, 0x20375540),
    ):
        b = image.bytes_at(start, end-start)
        p = out / (label + '.bin'); p.write_bytes(b)
        cmd = [str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),
               '-D', '-z', '-b', 'binary', '-m', 'm32r', '-EB',
               '--adjust-vma=' + hex(start), str(p)]
        run = subprocess.run(cmd, capture_output=True, text=True, check=True)
        (out / (label + '.txt')).write_text(run.stdout)
        index.append(dict(label=label, vma=hex(start), end=hex(end),
                          file_offset=hex(image.offset(start,len(b))),
                          sha256=hashlib.sha256(b).hexdigest(), command=cmd))
    (out / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('PASS official native windows', len(index))

if __name__ == '__main__':
    main()
