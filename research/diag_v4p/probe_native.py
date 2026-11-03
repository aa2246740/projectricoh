"""Execute the factory slot computation before diagnostic callbacks."""
from pathlib import Path
import json,sys,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H
s.enable()
c=H.Session(sys.argv[1],True);c.configuring=True
print('context',hex(c.h.u(0x200c0d9c)),flush=True)
out=c.fr.native(c.h,0x2016c060,(0x8482de00,0x87f7bfff),steps=3000000)
print(out,flush=True)
print('descriptors',c.h.u(0x20578288),flush=True)
print([(i,c.h.u(0x2057828c+4*i),c.h.u(0x2057841c+4*i),c.h.u(0x205785ac+76*i)) for i in range(12)],flush=True)
s.save(s.HERE/'evidence'/('native-slots-execution-'+sys.argv[1]+'.json'),dict(result=out,context=c.h.u(0x200c0d9c),rows=[[c.h.u(0x2057828c+4*i),c.h.u(0x2057841c+4*i),*[c.h.u(0x205785ac+76*i+4*j) for j in range(19)]] for i in range(99)]))
