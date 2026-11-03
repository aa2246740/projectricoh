"""Record the final H07 machine code and its engine-state symbol."""
from pathlib import Path
import hashlib,json,struct,subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ELF=ROOT/'firmware/engine_v58_g150/candidate/local/full-r13/engine.elf'
raw=ELF.read_bytes()
h=struct.unpack_from('>16sHHIIIIIHHHHHH',raw)
sections=[struct.unpack_from('>10I',raw,h[6]+i*h[11]) for i in range(h[12])]
symbols={}
for section in sections:
    if section[1]!=2:continue
    strings=sections[section[6]]; names=raw[strings[4]:strings[4]+strings[5]]
    for at in range(section[4],section[4]+section[5],section[9]):
        n,address,size,info,other,index=struct.unpack_from('>IIIBBH',raw,at)
        name=names[n:].split(b'\0',1)[0].decode()
        if name=='g' or name.startswith('ig_event') or 'confirm_live' in name:
            symbols[name]=dict(address=address,size=size,info=info)
tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
text=subprocess.check_output([str(tool),'-d','--disassemble=ig_event',str(ELF)],text=True)
(HERE/'evidence/ig_event.txt').write_text(text)
result=dict(status='PASS_STATIC',elf_sha256=hashlib.sha256(raw).hexdigest(),symbols=symbols,
            disassembly_sha256=hashlib.sha256(text.encode()).hexdigest())
(HERE/'evidence/event-symbols.json').write_text(json.dumps(result,indent=1)+'\n')
print(json.dumps(result))
