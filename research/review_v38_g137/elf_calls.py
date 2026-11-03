import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
path=ROOT/'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf'
raw=path.read_bytes()
header=struct.unpack_from('>16sHHIIIIIHHHHHH',raw)
start,stride,count=header[6],header[11],header[12]
sections=[struct.unpack_from('>IIIIIIIIII',raw,start+i*stride) for i in range(count)]
symbols={}
for section in sections:
    if section[1]!=2:continue
    strings_section=sections[section[6]]
    names=raw[strings_section[4]:strings_section[4]+strings_section[5]]
    for at in range(section[4],section[4]+section[5],section[9]):
        name,value,size,info,other,index=struct.unpack_from('>IIIBBH',raw,at)
        text=names[name:].split(b'\0',1)[0].decode()
        if index and text:symbols[text]={'value':value,'bytes':size,'section':index,'kind':info&15}
targets={name:symbols[next(key for key in symbols if key==name or key.startswith(name+'.'))]['value']
         for name in ['rv_native_preview','rv_native_draw','rv_irq_save','rv_irq_restore','rv_settings_owned']}
calls=[]
for section in sections:
    if not(section[2]&4):continue
    data=raw[section[4]:section[4]+section[5]]
    for offset in range(0,len(data)-3,4):
        word=int.from_bytes(data[offset:offset+4],'big')
        if word>>24 != 0xfe:continue
        relative=word&0xffffff
        if relative&0x800000:relative-=0x1000000
        pc=section[3]+offset
        target=pc+4*relative
        for name,value in targets.items():
            if target!=value:continue
            enclosing=[(n,s) for n,s in symbols.items() if s['kind']==2 and s['value']<=pc<s['value']+s['bytes']]
            calls.append({'target':name,'pc':hex(pc),'function':enclosing[0][0] if enclosing else '',
                          'before8':data[max(0,offset-8):offset].hex()})
result={'elf_sha256':hashlib.sha256(raw).hexdigest(),'targets':{k:hex(v) for k,v in targets.items()},'calls':calls}
(OUT/'evidence/elf-calls.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps([r for r in calls if r['target'] in ['rv_native_preview','rv_native_draw']]))
