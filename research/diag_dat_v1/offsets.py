"""Extract actual M32R type offsets without assuming host pointer width."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope import *
sys.path.insert(0,str(ENGINE/'candidate'))
import common as c

NAMES=('sample','first','opens','rows','page','captured','changed','error','active','list','glyphs')


def main():
    c.guard()
    out=OUT/'local/layout';out.mkdir(parents=True,exist_ok=True)
    src=out/'probe.c'
    product=ENGINE/'candidate/containers/product'
    src.write_text('#include "'+str(product/'diag.c')+'"\n'+
        'const uint32_t diag_offsets[]={'+','.join('offsetof(Diagnostic,'+n+')' for n in NAMES)+'};\n')
    c.run([c.GCC,'-std=c11','-Os','-ffreestanding','-fpic','-m32r','-mmodel=medium','-msdata=none',
           '-G0','-fno-builtin','-c',src,'-o',out/'probe.o'],'diag-offsets')
    reader=load(ROOT/'firmware/stage2l_switch/tools/build.py','diag_offset_reader')
    elf=reader.Elf(out/'probe.o');s=elf.symbols['diag_offsets']
    blob=elf.content(elf.sections[s['section']])[s['value']:s['value']+4*len(NAMES)]
    import struct
    result=dict(zip(NAMES,struct.unpack('>'+str(len(NAMES))+'I',blob)))
    save(OUT/'local/offsets.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
