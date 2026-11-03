"""Target layout, frozen identity, semantic mutants and final binary audit."""
from pathlib import Path
import json
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def main():
    c.guard();frozen=c.freeze_check();sys.path.insert(0,str(c.PRODUCT));import pack,build
    reader=c.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','final_elf_reader')
    out=c.LOCAL/'full-r6';layout=json.loads((out/'layout.json').read_text());raw=(out/'GXRCE.DAT').read_bytes()
    for path,digest in {**layout['sources'],**layout['tools']}.items():assert c.sha(c.ROOT/path)==digest,path
    elf=reader.Elf(out/'engine.elf');engine=next(s for s in elf.sections if s['name']=='.engine')
    bss=next(s for s in elf.sections if s['name']=='.bss')
    assert raw[256:256+engine['size']]==elf.content(engine)==(out/'engine.bin').read_bytes()
    assert b'v3.3\0' in elf.content(engine) and bss['size']==layout['bss_bytes']
    assert len(raw)<=65536 and engine['size']<=65536 and len(raw)+bss['size']<=114688
    assert not [s for s in elf.symbols.values() if s['name'] and s['section']==0]
    for path in c.HERE.rglob('*.S'):
        original=c.ROOT/'firmware/engine_fix_r2'/path.relative_to(c.HERE)
        assert original.is_file() and path.read_bytes()==original.read_bytes()
    obj=c.LOCAL/'target-layout.o'
    c.run([c.GCC,*build.FLAGS,'-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
        '-I',c.PRODUCT,'-c',c.HERE/'layout.c','-o',obj],'target-layout-compile')
    e=reader.Elf(obj);symbol=e.symbols['v33_target_sizes'];section=e.sections[symbol['section']]
    values=struct.unpack('>8I',e.content(section)[symbol['value']-section['va']:][:32])
    sizes=dict(zip(('session_work','PnGxts','PsStore','loader_work','UI_snapshot','Integrated','RvSession','resident_block_overhead'),values))
    assert sizes['resident_block_overhead']==7504
    main_request=7504+((len(raw)+bss['size']+3)&~3)
    sizes.update(file_bytes=len(raw),engine_bytes=engine['size'],bss_bytes=bss['size'],
        data_bytes=layout['data_bytes'],main_request=main_request,
        retained_with_headers=main_request+12+sizes['loader_work']+12+sizes['UI_snapshot']+12+sizes['session_work']+12,
        first_install_with_headers=main_request+12+sizes['loader_work']+12+2*(65536+12),
        install_with_retained_UI=main_request+12+sizes['loader_work']+12+2*(65536+12)+sizes['UI_snapshot']+12)
    old=c.ROOT/'firmware/full_r5/local/full-r5';old_layout=json.loads((old/'layout.json').read_text())
    result=dict(status='PASS',generation=108,engine_version='v3.3',sha256=c.sha(out/'GXRCE.DAT'),sizes=sizes,
        full_r5=dict(file_bytes=59704,engine_bytes=50276,bss_bytes=11172,data_bytes=9164,main_request=78380,
                     session_work=912,loader_work=608,UI_snapshot=1968,retained_with_headers=81916,first_install_with_headers=210108,install_with_retained_UI=212088),
        no_new_asm=True,pic_translation_verified=layout['pic_translation_verified'],relocations=layout['relocations'],
        protected_inputs=frozen,protected_inputs_unchanged=True,camera_acceptance=False)
    c.save(c.LOCAL/'artifact-inspection.json',result)
    mutants=[];target=c.LOCAL/'semantic-mutants';target.mkdir(exist_ok=True)
    for kind in ('wrong-slot','wrong-identity'):
        for unit,slot in ((0,1),(0,2),(0,3),(0,5),(0,7),(0,8),(2,1),(2,2)):
            b=bytearray(raw);bank=pack.u32(raw,180)+unit*1056;record=bank+32+64*(slot-1)
            if kind=='wrong-slot':b[record]=16
            else:b[record+4]=ord('9')
            pack.p32(b,record+60,pack.crc(b[record:record+60]));pack.p32(b,bank+24,pack.crc(b[bank+32:bank+1056]));pack.p32(b,bank+28,pack.crc(b[bank:bank+28]))
            path=target/f'{kind}-{unit}-{slot}.DAT';path.write_bytes(pack.seal(b))
            proc=c.run([c.LOCAL/'host/frozen-expand',path,out/'trust.bin'],f'mutant-{kind}-{unit}-{slot}',check=False)
            assert proc.returncode==3,(kind,unit,slot,proc.returncode)
            mutants.append(dict(kind=kind,unit=unit,slot=slot,rejected=True,all_CRCs_resealed=True))
    c.save(c.LOCAL/'semantic-results.json',dict(status='PASS',mutants=mutants,count=len(mutants)))
    c.freeze_check();print(json.dumps(result))


if __name__=='__main__':main()
