"""Compare the table sections of the merged g150 DAT with the g139m DAT.

  mount_section_check.py G150.DAT G139M.DAT

Sections 4 (unit maps), 6 (row pool and descriptors, all units) and 7 (knob
and UI extension) must be byte-identical. Section 5 (recipe banks) may differ
only in each bank's 16-bit build field and its header CRC (generation 150 vs
148). The decoded MOUNT model (entries, refs, records, ranges, map, pin) must
be equal. Writes research/g150/diff/mount-section-vs-g139m.json. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decode as D  # noqa: E402

u32 = lambda b, o: struct.unpack_from('>I', b, o)[0]


def sections(raw):
    return [(u32(raw, 132 + 12 * i), u32(raw, 136 + 12 * i)) for i in range(7)]


def main():
    new, old = Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes()
    a, b = sections(new), sections(old)
    out = dict(g150=hashlib.sha256(new).hexdigest(), g139m=hashlib.sha256(old).hexdigest(),
               generations=[u32(new, 28), u32(old, 28)], sections={})
    for i, name in ((3, 'maps'), (4, 'banks'), (5, 'shared'), (6, 'tweaks')):
        x = new[a[i][0]:a[i][0] + a[i][1]]; y = old[b[i][0]:b[i][0] + b[i][1]]
        diff = [k for k in range(min(len(x), len(y))) if x[k] != y[k]]
        out['sections'][name] = dict(lengths=[len(x), len(y)], identical=x == y, differing_bytes=len(diff),
                                     sha256=hashlib.sha256(x).hexdigest(), offsets_in_bank=sorted({k % 1056 for k in diff}))
    m1 = {m['name']: m for m in D.modules(new)}; m2 = {m['name']: m for m in D.modules(old)}
    keys = ('entries', 'refs', 'records', 'ranges', 'map', 'pin')
    out['decoded_equal'] = {u: {k: m1[u].get(k) == m2[u].get(k) for k in keys if k in m1[u]} for u in m1}
    s = out['sections']
    out['PASS'] = (s['maps']['identical'] and s['shared']['identical'] and s['tweaks']['identical'] and
                   s['banks']['lengths'][0] == s['banks']['lengths'][1] and
                   all(all(v.values()) for v in out['decoded_equal'].values()) and
                   s['banks']['offsets_in_bank'] == [19, 28, 29, 30, 31] and s['banks']['differing_bytes'] == 15)
    (HERE / 'diff/mount-section-vs-g139m.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
