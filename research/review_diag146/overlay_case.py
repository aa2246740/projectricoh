"""Observe the DAT recording an injected glyph-conversion failure on refusal."""
from pathlib import Path
import hashlib
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
import accept_diag146 as a

a.HERE=scope.HERE/'overlay-case'
a.HERE.mkdir(exist_ok=True)
nonce=bytes(range(0x40,0x50))
card=a.Card(a.L.blank(nonce),{})
m,h,p,w,syms,_=a.boot('28mm',1,{'/ATA1/GXRCE.DAT':a.DAT.read_bytes()},card)
fr=m.fr
armed=[False]
def entered(b):
    block=h.u(a.R+56)
    if block:
        p.image_base=h.u(block+312)
    return False
h.b.add_breakpoint(h.symbols['rv_invoke'],entered)
def observed(b):
    if armed[0] and b.get_reg('r1')==1:
        b.write(0x205a280f,b'\0')
    return False
h.b.add_breakpoint(syms['rv_hook_observe'],observed)
s_base=h.u(0x200c0dac)
s0=hashlib.sha256(h.b.read(s_base,4096)).hexdigest()
def opened():
    h.parent()
    assert fr.native(h,0x20287080,(),steps=40000000).get('ok')
opened()
assert fr.press(h,0x23,steps=40000000).get('ok')
armed[0]=True
h.b.breakpoints[0x201d73e0]=[]
h.stub(0x201d73e0,'glyph_conversion_boundary',value=0)
opened()
decoded=a.decode_trace.decode(bytes(card.content),nonce)
entry=decoded['slots'][1]['entries'][-1]
assert entry['outcome']=='X' and entry['overlay_on']==0 and entry['ov_fail']==1,entry
assert not card.violations
assert hashlib.sha256(h.b.read(s_base,4096)).hexdigest()==s0
(a.HERE/'GXRTRACE.BIN').write_bytes(bytes(card.content))
scope.save(a.HERE/'result.json',dict(entry=entry,decoded=decoded,s_hash_same=True,
           dat_sha256=scope.sha(a.DAT),boundary='Final DAT and resident instructions; glyph conversion failure and file device are modeled.'))
print('OVERLAY_FAILURE_RECORDED',entry,flush=True)
