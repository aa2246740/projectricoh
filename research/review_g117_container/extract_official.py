"""Extract fresh genuine ranges, explicitly decoding M32R as big endian."""
from pathlib import Path
import hashlib
import json
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
native = OUT / 'native'
native.mkdir(exist_ok=True)
raw = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
ranges = json.loads((ROOT / 'firmware/engine_v38_ro/native/ranges.json').read_text())
for row in ranges:
    start, end = int(row['vma_start'], 16), int(row['vma_end'], 16)
    part = raw[start - 0x2004ae00:end - 0x2004ae00]
    assert hashlib.sha256(part).hexdigest() == row['sha256']
    binary = native / (row['name'] + '.bin')
    binary.write_bytes(part)
    args = [str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '-D', '-b', 'binary',
            '-m', 'm32r', '-EB', '--adjust-vma=' + hex(start), str(binary)]
    output = subprocess.check_output(args, text=True)
    (native / (row['name'] + '.txt')).write_text(output)
(native / 'ranges.json').write_text(json.dumps(ranges, indent=2) + '\n')
print('PASS genuine official ranges freshly decoded with -EB:', len(ranges))
