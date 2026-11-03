"""List seth/or3 constructions of given absolute addresses in a GXR MAIN image.
usage: xref.py IMAGE ADDR [ADDR...]   (hex)"""
import struct, sys
from pathlib import Path
raw = Path(sys.argv[1]).read_bytes()
secs = [struct.unpack_from('>5I', raw, 0x20+20*i) for i in range(16)]
def vma(fo):
    for off, base, length, _, _ in secs:
        if off+0x200 <= fo < off+0x200+length:
            return base+fo-off-0x200
targets = {int(a, 16) for a in sys.argv[2:]}
for i in range(0x200, len(raw)-8, 2):
    w0, hi = struct.unpack_from('>HH', raw, i)
    if w0 & 0xf0ff != 0xd0c0:
        continue
    reg = (w0 >> 8) & 15
    for j in range(4, 24, 2):
        if i+j+4 > len(raw):
            break
        x0, lo = struct.unpack_from('>HH', raw, i+j)
        if x0 & 0xf0f0 == 0x80e0 and (x0 >> 8) & 15 == reg and x0 & 15 == reg:
            v = (hi << 16) | lo
            if v in targets and vma(i):
                print(hex(vma(i)), hex(v))
            break
