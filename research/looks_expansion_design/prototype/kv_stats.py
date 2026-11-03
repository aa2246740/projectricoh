"""Read-only: kv2 knob-table statistics of a gen 150 GXRCE.DAT. Usage: kv_stats.py DAT"""
import struct, sys, json, hashlib
from pathlib import Path
raw = Path(sys.argv[1]).read_bytes()
u16 = lambda b, o: struct.unpack_from('>H', b, o)[0]
s16 = lambda b, o: struct.unpack_from('>h', b, o)[0]
u32 = lambda b, o: struct.unpack_from('>I', b, o)[0]
sec7 = u32(raw, 132 + 12 * 6); len7 = u32(raw, 136 + 12 * 6)
kv = raw[sec7 + 3392: sec7 + 3392 + 17384]
assert kv[:7] == b'GXKV2R2', kv[:8]
out = dict(section7=dict(offset=sec7, length=len7), kv_magic=kv[:8].decode('latin1'))
recipes = []
for i in range(24):
    r = kv[64 + 16 * i: 80 + 16 * i]
    unit, slot, count, first = r[0], r[1], r[2], u16(r, 4)
    items = []
    for j in range(count):
        it = kv[448 + 16 * (first + j): 464 + 16 * (first + j)]
        n = it[1]; off = u32(it, 12)
        pts = kv[off: off + 4 * n]
        items.append(dict(control=it[0], n=n, head=it[:12].hex(), doses=[s16(pts, 4 * k + 2) for k in range(n)],
                          levels=[s16(pts, 4 * k) for k in range(n)]))
    recipes.append(dict(unit=unit, slot=slot, items=items))
pts_total = sum(it['n'] for r in recipes for it in r['items'])
out['points'] = pts_total
out['point_bytes'] = pts_total * 4
out['dose_only_bytes'] = pts_total * 2
# unit duplication: same slot, same items (head + doses)
dup = {}
for slot in range(1, 9):
    sig = []
    for unit in range(3):
        r = [x for x in recipes if x['unit'] == unit and x['slot'] == slot][0]
        sig.append(json.dumps([(it['head'], it['doses']) for it in r['items']]))
    dup[slot] = dict(u28_eq_50=sig[1] == sig[0], mount_eq_50=sig[2] == sig[0],
                     points=sum(it['n'] for it in [x for x in recipes if x['unit'] == 0 and x['slot'] == slot][0]['items']))
out['unit_dup'] = dup
# distinct (head,doses) items across everything
distinct = {}
for r in recipes:
    for it in r['items']:
        distinct.setdefault((it['head'], tuple(it['doses'])), it['n'])
out['distinct_items'] = len(distinct)
out['distinct_points'] = sum(distinct.values())
print(json.dumps(out, indent=1))
