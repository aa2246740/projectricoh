"""Check actual published diagnostic glyph buffers with original converter code.

This proves text publication, not graphics, video scanout or LCD pixels.
"""
from pathlib import Path
import argparse
import json
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--profile',required=True,choices=('test','release'));p.add_argument('--fixture',type=Path,required=True);a=p.parse_args()
C.setup();C.compute_gate('diagnostic-glyph-'+a.profile)
os.environ['GXR_HARNESS_BACKEND']='python'
sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'));import python_backend as P
P.CACHE=C.LOCAL/'glyph-decode'/a.profile
fixture=json.loads(a.fixture.read_text());raw=C.artifact(a.profile,'model')['dat'].read_bytes();assert fixture['DAT_sha256']==C.sha(raw)
cpu=P.PythonBackend()
for region in fixture['regions']:
    content=(C.ROOT/region['file']).read_bytes();assert C.sha(content)==region['sha256'];cpu.map(region['address'],content,True)
cpu.map(0x22000000,bytes(0x20000),True);cpu.set_reg('psw',0x80);cpu.set_reg('r15',0x2201fff0)
def get(at,n=4):return int.from_bytes(cpu.read(at,n),'big')
Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g157_glyph_elf').Elf
symbols=Elf(C.artifact(a.profile,'model')['build']/'engine.elf').symbols
offsets=json.loads((C.LOCAL/'layout.json').read_text())['offsets'];base=fixture['image_base']
text=cpu.read(base+symbols['n']['value']+offsets['n.ui.text'],112)
assert get(base+symbols['n']['value']+offsets['n.ui.screen'],1)==5
assert get(0x2022f5ac,1)==8
stop=cpu.call(0x201dc180,[],0x7ffffff0,10000);assert stop.reason=='return';language=cpu.get_reg('r0')
table=get(0x2022f5a8);rows=[]
for i in range(8):
    ascii_text=text[14*i:14*(i+1)].split(b'\0')[0]
    actual=cpu.read(get(get(table+4*i)),70).split(b'\0')[0]
    cpu.write(0x22000200,ascii_text+b'\0');cpu.write(0x22001000,bytes(128))
    for r,value in enumerate((0x22000200,len(ascii_text),0x22001000,language),4):cpu.set_reg('r'+str(r),value)
    stop=cpu.call(0x201d73e0,[],0x7ffffff0,300000);assert stop.reason=='return'
    expected=cpu.read(0x22001000,70).split(b'\0')[0];assert actual==expected,(i,actual,expected)
    rows.append(dict(row=i,text=ascii_text.decode('ascii'),published_glyphs=actual.hex(),original_converter_equal=True,instructions=stop.steps))
C.save(C.LOCAL/'acceptance/model'/('diagnostic-glyph-'+a.profile+'.json'),dict(status='PASS',DAT_sha256=C.sha(raw),backend='python',rows=rows,scope=__doc__,LCD=False))
print(json.dumps(dict(status='PASS',rows=8,LCD=False)))
