"""Shipped DAT with native geometry modeled as 64 sectors, guarded RAM buffer."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
import accept_diag146 as a

a.HERE=scope.HERE/'cluster32'
a.HERE.mkdir(exist_ok=True)
original_init=a.Card.__init__
def init(card,content,faults):
    original_init(card,content,dict(faults,sectors=64))
a.Card.__init__=init
original_boot=a.boot
state={}
guards=(0x204cbab0-16,0x204cbab0+32768,0x204cbab0+65536)
def boot(*args,**kwargs):
    values=original_boot(*args,**kwargs)
    h=values[1]
    for at in guards:
        h.b.write(at,b'\x6d'*16)
    state['h']=h
    return values
a.boot=boot
sys.argv=[__file__,'50mm']
a.main()
h=state['h']
result={hex(at):h.b.read(at,16)==b'\x6d'*16 for at in guards}
assert all(result.values()),result
scope.save(a.HERE/'buffer-guards.json',dict(guards=result,cluster_bytes=32768,
           slack_bytes_zeroed=32768-8704,other_buffer_stride=65536,
           boundary='Final DAT executed; file, geometry, lock and media operations are modeled.'))
print('CLUSTER32_CASE_DONE',result,flush=True)
