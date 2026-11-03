"""Read approved ELF/image bytes; derive allocation and compatibility evidence."""
from pathlib import Path
import json
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def symbol(e,name):
    s=e.symbols[name];section=e.sections[s['section']]
    return e.content(section)[s['value']-section['va']:s['value']-section['va']+s['size']]


def at(e,address,length):
    for section in e.sections:
        if section['va']<=address and address+length<=section['va']+section['size']:
            return e.content(section)[address-section['va']:address-section['va']+length]
    raise ValueError(hex(address))


def main():
    c.guard()
    reader=c.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','allocation_elf_reader')
    e=reader.Elf(c.UPSTREAM/'local/resident/build/resident.elf')
    approved=c.ROOT/'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'
    assert c.sha(approved)=='05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
    raw=approved.read_bytes();segments=[struct.unpack_from('>5I',raw,32+20*i)for i in range(16)]
    def image_at(address,n):
        for source,base,size,_,_ in segments:
            if base<=address and address+n<=base+size:
                start=512+source+address-base;return raw[start:start+n]
        raise ValueError(hex(address))
    payload=next(s for s in e.sections if s['name']=='.payload')
    assert image_at(payload['va'],payload['size'])==e.content(payload)
    assert image_at(e.symbols['rv_pins']['value'],12)==symbol(e,'rv_pins')
    final=c.LOCAL/'product/candidates/full-r2/GXRCE.DAT';blob=final.read_bytes()
    trust=symbol(e,'rv_trust');assert len(trust)==80 and trust==blob[48:112]+blob[212:228]
    original=c.UPSTREAM/'local/product/candidates/full/GXRCE.DAT';old=original.read_bytes()
    assert c.sha(original)=='24f420731b354de270d7d98636ee3783ff5bd2ca4b104d35f32f0373521d3c57'
    rb=c.load(c.RESIDENT/'build.py','approved_allocation_flags')
    assert rb.build_identity()==trust[32:64]
    source=c.LOCAL/'target-layout.c';obj=c.LOCAL/'target-layout.o'
    source.write_text('#include "'+str(c.RESIDENT/'loader.c')+'"\n#include "'+str(c.PRODUCT/'integrated.h')+'"\n'
        'const uint32_t r2_layout[]={sizeof(RvSession),RV_BLOCK_OVERHEAD,RV_STATE_BYTES,RV_UI_CAPACITY,'
        'sizeof(RvLoadWork),sizeof(RvUiSnapshot),sizeof(PnGxts),sizeof(EngTweak)};\n')
    c.run([c.GCC,*rb.FLAGS,'-mmodel=medium','-DPN_CORE_HEADER="../core/eng_core.h"',
           '-I',c.RESIDENT,'-c',source,'-o',obj],'frozen-target-layout')
    layout_e=reader.Elf(obj);values=struct.unpack('>8I',symbol(layout_e,'r2_layout'))
    layout=dict(zip(('session','overhead','state','ui_capacity','loader_work','ui_snapshot','GXTS_temporary','tweak_value'),values))
    overhead=layout['overhead']
    assert at(e,0x20053764,4)==b'\x84\xa4'+overhead.to_bytes(2,'big')
    assert at(e,0x200537bc,4)==b'\x91\xf0'+layout['session'].to_bytes(2,'big')
    assert overhead==layout['session']+layout['state']+layout['ui_capacity']
    dis=c.run([c.OBJDUMP,'-d',c.UPSTREAM/'local/resident/build/resident.elf'],'frozen-resident-disassembly').stdout
    allocation_lines=[line.strip()for line in dis.splitlines()if re.match(r'\s*200537(?:5c|60|64|bc):',line)]
    u32=lambda b,o:int.from_bytes(b[o:o+4],'big')
    oldlayout=json.loads((c.UPSTREAM/'local/product/candidates/full/layout.json').read_text())
    newlayout=json.loads((final.parent/'layout.json').read_text())
    result={}
    for name,b,data in (('original_full',old,oldlayout),('full_r2',blob,newlayout)):
        request=overhead+((len(b)+u32(b,116)+3)&~3)
        result[name]=dict(file_bytes=len(b),engine_bytes=u32(b,136),BSS_bytes=u32(b,116),
            data_bytes=data['data_bytes'],main_request=request,main_with_native_header=request+12,
            loader_and_UI_including_headers=request+12+layout['loader_work']+12+layout['ui_snapshot']+12,
            sha256=__import__('hashlib').sha256(b).hexdigest())
    c.save(c.LOCAL/'artifact-inspection.json',dict(status='PASS',layout=layout,artifacts=result,
        approved_image_sha256=c.sha(approved),resident_elf_sha256=c.sha(c.UPSTREAM/'local/resident/build/resident.elf'),
        resident_payload_bytes=payload['size'],resident_payload_matches_approved_image=True,
        trust_bytes_equal=80,body=trust[:32].hex(),build=trust[32:64].hex(),abi=trust[64:].hex(),
        source_identity_matches=True,pins=symbol(e,'rv_pins').hex(),allocation_instructions=allocation_lines,
        formula='overhead + align4(file_bytes + BSS_bytes)',resident_rebuilt=False,camera_acceptance=False))
    engine=reader.Elf(final.parent/'engine.elf')
    c.save(c.LOCAL/'bss-symbols.json',dict(sorted(((name,s['size'])for name,s in engine.symbols.items()
        if 0<s['section']<len(engine.sections) and engine.sections[s['section']]['name']=='.bss'),key=lambda row:-row[1])))
    print(json.dumps(dict(main_request=result['full_r2']['main_request'],file_bytes=len(blob),BSS_bytes=u32(blob,116),
                         sha256=c.sha(final),resident_identity='80/80 bytes match')))


if __name__=='__main__':main()
