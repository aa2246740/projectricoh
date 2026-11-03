"""Re-extract only the still ISP/profile windows needed for the mode comparison."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import struct

# Freeze the existing model's transitive input list, without executing the old task.
inputs = __import__('json').loads((r.ROOT/'research/daily_bugs_20261024/local/model_inputs.json').read_text())
paths = [r.ROOT/p for p in inputs['reused_modules']]
r.freeze.add(paths)
j, m, body = (r.Image(x) for x in ('jlaunch3', 'l08firm3', 'ilaunch3'))
windows = {
    'colour': (0x2010D7BC, 0x2010E544),
    'curve': (0x2010E544, 0x2010EBEC),
    'matrix': (0x20114DAC, 0x20115020),
    'colour_getters': (0x20114150, 0x20114224),
    'toning': (0x20115638, 0x201159D8),
    'normalize': (0x20199760, 0x20199814),
    'profile': (0x20199C80, 0x20199E08),
}
records = []
matches = {}
for name, (a,b) in windows.items():
    records.append(r.disasm(j, 'jlaunch3-'+name, a, b))
    # Match a function prefix. Absolute-address words may differ, so retain
    # exact matches only as locating evidence, then decode the Mount body.
    hits = []
    for n in (16, 12, 8):
        sig = j.read(a,n)
        hits = [i for i in range(len(m.data)) if m.data.startswith(sig,i)]
        if len(hits) == 1:
            break
    matches[name] = {'signature_bytes': n, 'matches': [hex(m.va(i)) for i in hits]}
    if len(hits) == 1:
        v = m.va(hits[0])
        records.append(r.disasm(m, 'l08firm3-'+name, v, v+(b-a)))
for name,a,b in (
    ('standard-packet',0x202D435C,0x202D4484),
    ('bw-packet',0x202D41AC,0x202D41FC),
    ('preset-wrapper',0x20374560,0x20374588),
    ('preset-getter',0x20172E70,0x20172FA8),
    ('raw-normalizer',0x20167CA0,0x20167D24)):
    records.append(r.disasm(body,'ilaunch3-'+name,a,b))
r.dump('re/windows.json', records)
r.dump('re/mount_matches.json', matches)
print(matches)
print('extracted',len(records),'windows')
