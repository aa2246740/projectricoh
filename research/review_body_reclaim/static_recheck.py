#!/usr/bin/python3
"""Bind H40 stock-frame and byte-comparison checks to the actual local images."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/static'
OUT.mkdir(exist_ok=True)
images={name:(ROOT/rel).read_bytes() for name,rel in {
 'official':'artifacts/firmware/gxr-1.51/ilaunch3',
 'v38':'firmware/resident_v38/local/body/ilaunch3'}.items()}

def read_image(raw,address,n):
    for i in range(16):
        source,base,size,_,_=struct.unpack_from('>5I',raw,0x20+20*i)
        if base<=address and address+n<=base+size:
            off=source+0x200+address-base;return raw[off:off+n]
    raise ValueError(hex(address))

records=[]
for name,begin,end in [('h40-outer',0x2015f854,0x2015f9dc),('encoder-wrapper',0x2016583c,0x20165ab4)]:
    official=read_image(images['official'],begin,end-begin)
    assert official==read_image(images['v38'],begin,end-begin)
    start=time.monotonic()
    result=subprocess.run(['/usr/bin/python3','-I','-B',str(ROOT/'research/body_next_steps/tools/dis.py'),hex(begin),hex(end)],
                          capture_output=True,text=True,timeout=600)
    assert result.returncode==0,result.stderr
    (OUT/f'{name}.txt').write_text(result.stdout)
    records.append({'range':name,'begin':hex(begin),'end':hex(end),
                    'official_equal_v38':True,'sha256':hashlib.sha256(official).hexdigest(),
                    'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':600})
outer=(OUT/'h40-outer.txt').read_text().splitlines()
stack_lines=[line for line in outer if re.search(r'\b(push|pop)\b',line) or re.search(r'\b(?:addi|add3|add|sub|mv)\s+(?:sp|r15)\b',line)]
registers=[register for line in stack_lines for register in re.findall(r'\bpush\s+(\w+)',line)]
assert registers==['r8','r9','r10','r11','r12','lr','fp'],registers
result=subprocess.run([str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-d',str(HERE/'local/rebuild/v/r3/build/resident.elf')],capture_output=True,text=True,timeout=600)
assert result.returncode==0,result.stderr
(OUT/'r3-disassembly.txt').write_text(result.stdout)
section=result.stdout.split('<rv_equal>:',1)[1].split('\n\n',1)[0]
assert 'ldub' in section
summary={'classification':'static official bytes and linked resident disassembly',
         'images':{k:hashlib.sha256(v).hexdigest() for k,v in images.items()},
         'records':records,'outer_stack_instructions':stack_lines,
         'outer_saved_lr_offset_from_stock_sp':4,'resident_rv_equal_uses_byte_loads':True}
(HERE/'local/static-result.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
