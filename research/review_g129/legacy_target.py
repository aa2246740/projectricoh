"""Run the final initialization code with old-format entry fixtures."""
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

def main():
    local=WORK/'local/legacy-target';local.mkdir(parents=True,exist_ok=True)
    source=ROOT/'research/g129_knobs';sys.path.insert(0,str(source))
    loaded=runpy.run_path(str(source/'target_check.py'))
    loaded['loader'].__globals__['LOCAL']=local
    Backend=loaded['loader']()
    Elf=runpy.run_path(str(ROOT/'firmware/stage2l_switch/tools/build.py'))['Elf']
    elf=Elf(ROOT/'firmware/engine_v49_knobs/candidate/local/full-r13/engine.elf')
    resident_path=ROOT/'firmware/resident_v36/local/resident/build/resident.elf'
    resident=Elf(resident_path)
    symbol=lambda name:next(value['value'] for key,value in elf.symbols.items() if key==name)
    offsets=json.loads((WORK/'session-layout.json').read_text())
    adapter=json.loads((ROOT/'research/g129_knobs/adapter-layout.json').read_text())
    dat=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    assert hashlib.sha256(dat).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    extension=struct.unpack_from('>I',dat,128+12*6+4)[0]+1408
    entries=records();expected=[]
    for raw in entries:
        old=struct.unpack('11b',raw[10:21]);expected.append([100,old[0],old[1],old[2],0,old[3],0,0,0,0])
    def fixture(position=None):
        value=bytearray(dat);struct.pack_into('>H',value,extension+24,32)
        value[extension+1216:extension+1984]=b''.join(entries)
        if position is not None:value[extension+1216+position]=1
        value[extension+16:extension+20]=bytes(4)
        struct.pack_into('>I',value,extension+16,zlib.crc32(value[extension:extension+1984])&0xffffffff)
        struct.pack_into('>I',value,24,zlib.crc32(value[256:])&0xffffffff)
        value[20:24]=bytes(4);struct.pack_into('>I',value,20,zlib.crc32(value[:256])&0xffffffff)
        assert value[256:60644]==dat[256:60644]
        return value
    complete=[]
    for unit,job in [('50mm','focus-product-50mm'),('28mm','focus-product-28mm-r17'),('mount','focus-product-mount')]:
        folder=WORK/'local'/job/'review_g126'/f'target-state-{unit}-0'
        state=json.loads((folder/'state.json').read_text())
        regions=[(r['base'],(folder/r['file']).read_bytes(),r['writable']) for r in state['regions']]
        original=Backend()
        for base,data,writable in regions:original.map(base,data,writable)
        image=loaded['locate'](regions,dat);n=image+symbol('n')
        request=original.read(n+offsets['request'],64)
        context=struct.unpack('>I',original.read(n+offsets['context'],4))[0]
        root=struct.unpack('>I',original.read(context+8,4))[0]
        resident_entry=resident.symbols['rv_engine']['value']
        function=resident.symbols['rv_engine'];section=resident.sections[function['section']]
        start=function['value']-section['va'];code=resident.content(section)[start:start+function['size']]
        assert original.read(resident_entry,len(code))==code,'resident entry bytes differ from the captured model'
        for position in (None,1,9,14,15,16,17,18,19,20,21):
            backend=Backend()
            for base,data,writable in regions:backend.map(base,data,writable)
            backend.map(0x30000000,bytes(0x20000),True)
            value=fixture(position);relocation,count=struct.unpack_from('>II',dat,144)
            for at in range(relocation,relocation+count,8):
                patch,target=struct.unpack_from('>II',dat,at);struct.pack_into('>I',value,patch,image+target)
            backend.write(image,value);backend.write(n+offsets['initialized'],bytes(1))
            backend.write(n+offsets['active'],bytes(1));backend.write(0x30000100,request)
            backend.write(0x30000200,bytes(32));backend.set_reg('r15',0x3001f000)
            saved=n+adapter['ui']+adapter['ui.saved'];backend.write(saved,bytes([90])*(32*20))
            stop=backend.call(resident_entry,[root,symbol('ig_init'),0x30000100,0x30000200],0x3fff0000,50000000)
            assert stop.reason=='return',('legacy_target_stop',unit,position,stop.reason)
            assert backend.read(0x30000200,4)==b'\x00\x01\x00\x20',('legacy_reply_header',unit,position)
            status=struct.unpack('>i',backend.read(0x30000204,4))[0]
            if position is None:
                detail={'name':'legacy_init_counts','returncode':backend.get_reg('r0'),
                        'entry_visits':backend.visits[image+symbol('ig_init')],
                        'initialized_count':int.from_bytes(backend.read(n+offsets['initialized'],1),'big'),
                        'reply_status':status,'steps':stop.steps}
                (WORK/'legacy-target-diagnostic.json').write_text(json.dumps(detail,indent=2)+'\n')
            if position is None:
                assert status==0 and backend.read(n+offsets['initialized'],1)==bytes([1]),('legacy_target_init',unit,status)
                for index,wanted in enumerate(expected):assert list(struct.unpack('>10h',backend.read(saved+20*index,20)))==wanted
            else:
                assert status!=0 and backend.read(n+offsets['initialized'],1)==bytes(1)
                assert backend.read(saved,640)==bytes([90])*640
            complete.append({'unit':unit,'reserved_position':position,'status':status,'steps':stop.steps,
                             'records':32 if position is None else 0,'fixture_sha256':hashlib.sha256(fixture(position)).hexdigest()})
        print(json.dumps({'name':'legacy_target_'+unit,'returncode':0,'valid_records':32,'rejection_cases':10}),flush=True)
    result={'status':'PASS','base_dat_sha256':hashlib.sha256(dat).hexdigest(),'target_records':96,
            'resident_elf_sha256':hashlib.sha256(resident_path.read_bytes()).hexdigest(),
            'target_rejections':30,'scope':'Final code with synthetic GXUI v1 records in an existing model session. No loader reread or camera.','cases':complete}
    (WORK/'legacy-target-results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
