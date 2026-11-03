"""Preserve first-H01 P1 inputs without changing native state."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n

h,p,w=n.boot()
records=[]
def engine(b):
    if b.get_reg('r1')==288:
        p.state_address()
        pc=p.image_base+p.elf.symbols['probe_p1_capture']
        def capture(b):
            record={hex(a):h.u(a,size) for a,size in ((0x2022f5a8,4),(0x2022f5ac,1),(0x2022f725,1),(0x2022f726,1),
                (0x2022f720,4),(0x205d9bf8,4),(0x205d9c00,4),(0x205a280f,1),(0x205a27d8,4),(0x205a27d4,1),
                (0x205a279c,1),(0x205a27a0,4),(0x205a27a4,1),(0x205a27a8,4))}
            record['root']=n.fr.root_fields(h);record['registers']=[b.get_reg('r'+str(i)) for i in range(4)]
            records.append(record)
            return False
        h.b.add_breakpoint(pc,capture)
    return False
h.b.add_breakpoint(h.symbols['rv_engine'],engine)
result=n.fr.open_settings(h)
n.c.save(n.c.RESEARCH/'evidence/p1-first-debug.json',dict(result=result,records=records,rows=p.rows(),state=p.state()))
print(records,result,p.state(),flush=True)
