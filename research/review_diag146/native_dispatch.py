"""Inspect indirect native dispatch sites and fixed error jump-table targets."""
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
import callgraph as cg
from m32r_listing import read,dis

image=scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
raw=image.read_bytes()
g=cg.Graph(image)
keys=sorted(g.insn)
sites=[]
for i,at in enumerate(keys):
    text=g.insn[at]
    if text.startswith('or3 ') and text.endswith(',#0x8940'):
        sites.append(at)
with (scope.HERE/'dispatch-table-references.txt').open('w') as f:
    for at in sites:
        f.write(dis(raw,max(at-48,0x2004b000),at+120)+'\n\n')
offsets=struct.unpack('>37h',read(raw,0x200cfb84,74))
targets=sorted({0x200af528+n for n in offsets})
roots=[0x200a32a8,0x200a3358,*targets]
report=g.walk(roots)
scope.save(scope.HERE/'native-dispatch.json',dict(
    error_jump_table_base='0x200cfb84',error_jump_base='0x200af528',
    error_jump_offsets=list(offsets),error_jump_targets=[hex(a) for a in targets],
    dispatch_table_references=[hex(a) for a in sites],
    graph=report,
    semaphore_leaves={k:v for k,v in report.items() if v.get('leaf') in tuple(cg.SEM47.values())+tuple(cg.RAW_SEM.values())},
    indirect={k:v['indirect'] for k,v in report.items() if v.get('indirect')}))
for fn,lo,hi in [('device-callbacks',0x200a3200,0x200a3400),('native-error-full',0x200af4ec,0x200af654)]:
    (scope.HERE/(fn+'.txt')).write_text(dis(raw,lo,hi))
print('DISPATCH_INSPECTED',len(report),'functions',len(sites),'table references',flush=True)
