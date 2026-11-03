"""Static facts on g137 rows: per-unit row identity, A14==A5/B14==B5, cross-unit sharing, MOUNT 01/02 vs S3 source."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
import hashlib
mods = g137_modules()
LAB = ('A5', 'B5', 'C080', 'C100', 'A20', 'B20', 'CD', 'A14', 'B14')
OFF = (20, 82, 115, 216, 284, 346, 379, 456, 518); SZ = (62, 33, 96, 56, 62, 33, 66, 62, 33)
h = lambda b: hashlib.sha256(b).hexdigest()[:8]
out = {}
for name, m in mods.items():
    E = m['entries']; u = {}
    for slot in range(1, 9):
        e = E[slot]; rows = {l: e[o:o + n] for l, o, n in zip(LAB, OFF, SZ)}
        u[slot] = dict(mask=e[1], rows={l: h(r) for l, r in rows.items()}, a14_eq_a5=rows['A14'] == rows['A5'], b14_eq_b5=rows['B14'] == rows['B5'])
    out[name] = u
    print(name, {s: (u[s]['mask'], u[s]['a14_eq_a5'], u[s]['b14_eq_b5']) for s in u})
    for s in range(1, 9):
        print('  ', s, ' '.join(f"{l}={u[s]['rows'][l]}" for l in LAB))
s3 = S3.read_bytes()
for i, slot in enumerate(SRC.TABLE_SLOTS):
    p = s3[16 + 448 * i:16 + 448 * (i + 1)]
    g = mods['l08firm']['entries'][slot][:448]
    print('mount slot', slot, 'rows equal S3 source:', all(p[o:o + n] == g[o:o + n] for o, n in zip(SRC.ROW_OFFSETS, SRC.ROW_BYTES)))
dump(LOCAL / 'g137_rows.json', out)
