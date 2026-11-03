"""Check old-format initialization in the complete retained target model."""
from pathlib import Path
import hashlib
import json
import runpy
import struct
import sys
import zlib

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(WORK))
from legacy_cases import records

def run(context,arguments,out,sessions):
    restore=runpy.run_path(str(WORK/'product_post.py'))['restore']
    h,p,w=restore(context,arguments,out,sessions);b=h.b
    unit=arguments[arguments.index('--unit')+1]
    fields=json.loads((WORK/'session-layout.json').read_text())
    adapter=json.loads((ROOT/'research/g129_knobs/adapter-layout.json').read_text())
    image=p.image_base;n=p.symbol_pc('n');dat=p.dat
    assert hashlib.sha256(dat).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    extension=struct.unpack_from('>I',dat,128+12*6+4)[0]+1408
    entries=records();wanted=[]
    for raw in entries:
        values=struct.unpack('11b',raw[10:21]);wanted.append([100,values[0],values[1],values[2],0,values[3],0,0,0,0])
    def fixture(position=None):
        value=bytearray(dat);struct.pack_into('>H',value,extension+24,32)
        value[extension+1216:extension+1984]=b''.join(entries)
        if position is not None:value[extension+1216+position]=1
        value[extension+16:extension+20]=bytes(4)
        struct.pack_into('>I',value,extension+16,zlib.crc32(value[extension:extension+1984])&0xffffffff)
        struct.pack_into('>I',value,24,zlib.crc32(value[256:])&0xffffffff)
        value[20:24]=bytes(4);struct.pack_into('>I',value,20,zlib.crc32(value[:256])&0xffffffff)
        start,length=struct.unpack_from('>II',dat,132)
        assert value[start:start+length]==dat[start:start+length]
        relocation,size=struct.unpack_from('>II',dat,144)
        for at in range(relocation,relocation+size,8):
            patch,target=struct.unpack_from('>II',dat,at);struct.pack_into('>I',value,patch,image+target)
        return value
    snapshot=[(base,bytes(data),writable) for base,data,writable in b.regions]
    registers={f'r{i}':b.get_reg(f'r{i}') for i in range(16)}
    cases=[];saved=n+adapter['ui']+adapter['ui.saved']
    for position in (None,1,9,14,15,16,17,18,19,20,21):
        for base,data,writable in snapshot:
            if writable:b.write(base,data)
        for name,value in registers.items():b.set_reg(name,value)
        assert h.u(n+fields['initialized'],1)==1 and h.u(n+fields['active'],1)==0
        b.write(image,fixture(position));h.put(n+fields['initialized'],0,1)
        b.write(saved,bytes([90])*640)
        before=b.visits[p.symbol_pc('ig_init')]
        result=p.engine(0,[]);assert result.get('ok'),('legacy_model_call',unit,position)
        assert b.visits[p.symbol_pc('ig_init')]>before,('legacy_init_entry',unit,position)
        if position is None:
            assert result.get('reply_status')==0 and h.u(n+fields['initialized'],1)==1,('legacy_model_init',unit,result.get('reply_status'))
            for index,expected in enumerate(wanted):assert list(struct.unpack('>10h',b.read(saved+20*index,20)))==expected
        else:
            assert result.get('reply_status')!=0 and h.u(n+fields['initialized'],1)==0
            assert b.read(saved,640)==bytes([90])*640
        cases.append({'reserved_position':position,'reply_status':result.get('reply_status'),'vectors':32 if position is None else 0})
    result={'status':'PASS','unit':unit,'base_dat_sha256':hashlib.sha256(dat).hexdigest(),
            'vectors':32,'rejections':10,'cases':cases,
            'model_breakpoint_handlers':sum(len(rows) for rows in b.breakpoints.values()),'model_mmio_handlers':len(b.mmio),
            'scope':'Final initialization code and resident dispatch with synthetic GXUI v1 input in the complete retained model.'}
    (out/f'legacy-target-{unit}.json').write_text(json.dumps(result,indent=2)+'\n')
