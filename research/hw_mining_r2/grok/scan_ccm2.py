#!/usr/bin/env python3
"""Second pass: looser matrices, all type-28 rows, DNG context, other-section mul clusters."""
import csv
import struct
from pathlib import Path

ROOT = Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
FW = ROOT / "artifacts/firmware/gxr-1.51/jlaunch3"
CSV = ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv"
DIS = ROOT / "research/tooling_m32r/disasm"
OUT = Path(__file__).resolve().parent / "evidence"

blob = FW.read_bytes()
sections = []
with CSV.open() as f:
    for row in csv.DictReader(f):
        off = int(row["file_offset"])
        size = int(row["initialized_size"])
        vma = int(row["load_address"])
        sections.append((int(row["index"]), vma, blob[off:off + size], off))


def get(vma, n):
    for idx, base, data, foff in sections:
        if base <= vma < base + len(data):
            rel = vma - base
            return data[rel:rel + n], foff + rel, idx
    raise SystemExit(hex(vma))


def sm12(u):
    mag = u & 0x7FF
    return -mag if u & 0x800 else mag


buf, foff, _ = get(0x2012D0C0, 28 * 10)
print("type28 rows at 0x2012D0C0 file", hex(foff))
for r in range(10):
    chunk = buf[r * 28:(r + 1) * 28]
    if len(chunk) < 28:
        break
    u = struct.unpack(">14H", chunk)
    dec = [sm12(x) for x in u[:9]]
    sums = (sum(dec[0:3]), sum(dec[3:6]), sum(dec[6:9]))
    print(f"  row{r} sm12 {dec} sums {sums} tail {[hex(x) for x in u[9:]]}")

print("\nDNG context 0x200C5000")
buf, foff, _ = get(0x200C5000, 0x120)
print("file", hex(foff))
print(buf[:64].hex())
# find MM or II nearby by scanning back
buf, foff, _ = get(0x200C4F00, 0x200)
text = []
for i in range(0, len(buf) - 4):
    if buf[i:i + 2] in (b"MM", b"II") and buf[i + 2:i + 4] in (b"\x00*", b"*\x00"):
        text.append(hex(0x200C4F00 + i))
print("tiff magic", text)

print("\nDNG context 0x20225F00")
buf, foff, sec = get(0x20225F00, 0x100)
print("sec", sec, "file", hex(foff))
print(buf[:32].hex())

# loose look: exact-ish row sums
print("\nloose row-sum hits (tol 4, off-diagonal, not constant)")
SCALES = (128, 256, 512, 1024, 2048, 4096, 8192, 16384)
nloose = 0
for idx, base, data, foff in sections:
    n = len(data) // 2
    if n < 9:
        continue
    s = struct.unpack(">" + "h" * n, data[:n * 2])
    i = 0
    while i <= n - 9:
        if (base + i * 2) & 3:
            i += 1
            continue
        raw = s[i:i + 9]
        sums = (sum(raw[0:3]), sum(raw[3:6]), sum(raw[6:9]))
        if max(sums) - min(sums) > 4:
            i += 1
            continue
        target = sums[0]
        if not any(abs(target - sc) <= 4 for sc in SCALES):
            i += 1
            continue
        off = sum(abs(raw[k]) for k in (1, 2, 3, 5, 6, 7))
        if off < 8:
            i += 1
            continue
        if len(set(raw)) <= 2:
            i += 1
            continue
        # skip if this is the sm12 ycbcr bit pattern already known: check decoded
        print(f"  {base + i * 2:#x} sec{idx} sums {sums} {list(raw)}")
        nloose += 1
        if nloose > 40:
            break
        i += 9
    if nloose > 40:
        break
print("loose count shown", nloose)

# type 9 / 11 / 12 / 17 source snapshots
print("\nknown source snapshots")
for name, vma, n in (
    ("t9", 0x2012B9E4, 64),
    ("t11 area guess", 0x2012B000, 32),
    ("bfb8 index", 0x2012BFB8, 16),
    ("t25 mirror", 0x20142F7C, 40),
    ("t21 index", 0x2012C058, 64),
    ("t6 wider", 0x2012BD40, 0xF0),
):
    buf, foff, sec = get(vma, n)
    print(name, hex(vma), "file", hex(foff), buf.hex())

# mul clusters in other big disasms
print("\nmul clusters outside the ISP builder")
for name in (
    "jlaunch3-sec00-load-2004b000.disasm.txt",
    "jlaunch3-sec06-load-20184800.disasm.txt",
    "jlaunch3-sec14-load-20246800.disasm.txt",
    "jlaunch3-sec04-load-20147400.disasm.txt",
):
    addrs = []
    path = DIS / name
    for line in path.open():
        if "\tmul " not in line:
            continue
        try:
            addrs.append(int(line.split(":", 1)[0], 16))
        except ValueError:
            pass
    clusters = []
    i = 0
    while i < len(addrs):
        j = i
        while j + 1 < len(addrs) and addrs[j + 1] - addrs[i] <= 0x60 and j - i < 30:
            j += 1
        if j - i + 1 >= 8:
            clusters.append((hex(addrs[i]), hex(addrs[j]), j - i + 1))
        i = j + 1 if j > i else i + 1
    print(name, "muls", len(addrs), "clusters", clusters[:12], "n", len(clusters))
