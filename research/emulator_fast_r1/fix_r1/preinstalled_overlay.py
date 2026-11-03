"""A pre-construction model wrapper must retain its ordinary Python behavior."""
import argparse
import functools
import importlib.util
import json
from pathlib import Path
import signal
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
p=argparse.ArgumentParser()
p.add_argument('--backend',choices=('native','reference'),required=True)
p.add_argument('--name',required=True)
a=p.parse_args()
R.setup(a.backend)
signal.alarm(180)
import devices
path=R.ROOT/'research/v310_body/fix/emulator/nand_read_tail.py'
spec=importlib.util.spec_from_file_location('review_known_tail',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.install()
original=devices.NAND.read
@functools.wraps(original)
def wrapped(self,address,size):
    value=original(self,address,size)
    if address==0 and size==1:
        return value^1 if isinstance(value,int) else bytes([value[0]^1])
    return value
devices.NAND.read=wrapped
ctx=R.construct('main',a.name)
m,c=ctx.machine,ctx.machine.cpu
try:
    n=m.devices['nand']
    n.command=0x30
    n.row=3
    n.cursor=0
    n.pages[3]=b'\x55'+b'\xff'*2111
    c.write(0x27f00000,bytes.fromhex('20917000'))
    c.set_reg('r1',0)
    c.set_reg('pc',0x27f00000)
    stop=c.run(1)
    c.materialize_native()
    rec={'backend':a.backend,'copied_marker':getattr(wrapped,'v310_read_tail',False),
         'actual_wrapper_different':wrapped.__code__ is not original.__code__,
         'model_revision':c.model_revision,'stop':stop.to_dict(),'r0':c.get_reg('r0'),
         'state':R.fingerprint(ctx),'native':c._native_driver.stats() if c._native_driver else None}
    out=R.RUNS/(a.name+'.json')
    assert not out.exists()
    out.write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps({k:rec[k] for k in ('backend','copied_marker','actual_wrapper_different','r0','native')}))
finally:
    m.close()
    signal.alarm(0)
