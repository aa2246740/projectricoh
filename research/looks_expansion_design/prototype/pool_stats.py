"""Read-only: row-pool statistics of a GXRCE.DAT (gen 13x-15x). Usage: pool_stats.py DAT"""
import struct, sys, json
from pathlib import Path
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
sys.path.insert(0, str(ROOT / 'research/g139m'))
import decode as D
pack = D.pack
u16 = lambda b, o: struct.unpack_from('>H', b, o)[0]
u32 = lambda b, o: struct.unpack_from('>I', b, o)[0]
raw = Path(sys.argv[1]).read_bytes()
shared = u32(raw, 192)
out = {'file_bytes': len(raw), 'shared_offset': shared, 'pools': []}
for kind in range(4):
    pool = shared + 16 + 12 * kind
    out['pools'].append(dict(kind=kind, hdr=raw[pool:pool + 12].hex(), size=u16(raw, pool + 2),
                             count=u16(raw, pool), offset=u32(raw, pool + 4), extra=u32(raw, pool + 8)))
mods = []
for mi, name in enumerate(pack.NAMES):
    d = raw[u32(raw, 156) + 64 * mi:u32(raw, 156) + 64 * (mi + 1)]
    table = u32(d, 20)
    descs = []
    for i in range(d[30]):
        desc = raw[table + 16 + 20 * i:table + 36 + 20 * i]
        descs.append(dict(slot=desc[0], flags=desc[1], idx=list(desc[8:18])))
    mods.append(dict(name=name, entries=d[30], descs=descs))
out['modules'] = mods
# rows used by 04 vs each slot (50mm)
m = mods[0]
s4 = [x for x in m['descs'] if x['slot'] == 4][0]['idx']
diff = {}
for x in m['descs']:
    nd = [k for k in range(10) if x['idx'][k] != s4[k]]
    diff[x['slot']] = dict(flags=x['flags'], rows_diff_vs_04=nd,
                           bytes_diff=sum(pack.ROW_BYTES[k] for k in nd))
out['jlaunch_diff_vs_04'] = diff
# unique row usage across all modules
used = {k: set() for k in range(4)}
for mm in mods:
    for x in mm['descs']:
        for k in range(10):
            used[pack.KINDS[k]].add(x['idx'][k])
out['unique_rows_used'] = {k: len(v) for k, v in used.items()}
print(json.dumps(out, indent=1, default=str))
