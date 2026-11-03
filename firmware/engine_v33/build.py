"""Build v3.3/full-r6 without writing any upstream source or artifact."""
import json
from pathlib import Path
import shutil
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import service_build


def main():
    c.guard();frozen=c.freeze_check()
    assert c.sha(c.R5/'GXRCE.DAT')=='7034a8afde38f260c7095ff6183725ba64208d4d4174886a5fb0fb5b295dd385'
    sys.path.insert(0,str(c.PRODUCT))
    candidates=c.load(c.PRODUCT/'candidates.py','v33_candidates')
    pack,build=candidates.pack,candidates.build
    pipeline=c.load(c.ROOT/'firmware/full_r5/build.py','read_only_r5_pipeline')
    modules=pipeline.reproduce_r4(candidates,pack)
    sources=pipeline.negative_tables(pack)
    for mi,key in ((0,'negative50'),(2,'negative_mount')):
        modules[mi]['entries'][2]=sources[key]
    old_layout=json.loads((c.R5/'layout.json').read_text())
    reproduced=pack.pack_model(modules,107,**pipeline.arguments(c.R5,old_layout))[0]
    assert reproduced==(c.R5/'GXRCE.DAT').read_bytes(),'Full-r5 pipeline must reproduce byte-identically'
    assert pipeline.golden(modules,pack)==(c.R5/'effective-rows.bin').read_bytes()
    service_build.main()
    inert=pack.pack_model(modules,108)[0]
    build.LOCAL.mkdir(parents=True,exist_ok=True)
    layout=build.build(len(inert)-16-256,lto=True)
    out=c.OUT;out.mkdir(parents=True,exist_ok=True)
    linked=build.LOCAL/'m32r-lto'
    engine=(linked/'engine.bin').read_bytes();relraw=(linked/'reloc.bin').read_bytes()
    rel=[struct.unpack_from('>II',relraw,i) for i in range(0,len(relraw),8)]
    blob,trust,stats=pack.pack_model(modules,108,engine=engine,relocations=rel,
        bss=layout['bss_bytes'],entry=layout['entries']['ig_bootstrap'],
        resident_id=reproduced[80:112],abi_id=reproduced[212:228])
    assert len(blob)==layout['file_bytes']<=65536
    for name,data in (('GXRCE.DAT',blob),('trust.bin',trust),('engine.bin',engine),('reloc.bin',relraw),
                      ('effective-rows.bin',pipeline.golden(modules,pack))):c.write(out/name,data)
    for name in ('engine.elf','engine.map'):c.write(out/name,(linked/name).read_bytes())
    c.save(out/'layout.json',layout)
    for m in modules:
        for slot in range(1,17):
            c.write(out/'expanded'/m['name']/f'{slot:02}.entry',m['entries'][m['refs'][slot-1]])
    entries=''.join(f'#define OFF_{name.upper()} {value}u\n' for name,value in layout['entries'].items())
    c.write(c.LOCAL/'product/entries.h',entries.encode())
    c.write(c.LOCAL/'product/resident-trust.c',(c.ROOT/'firmware/resident_v32/local/resident/trust.c').read_bytes())
    reader=c.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','v33_elf_reader')
    pipeline.identity_proof(reader,blob,pack)
    main=7504+((len(blob)+layout['bss_bytes']+3)&~3)
    manifest=dict(status='BUILT_HOST_ONLY',engine_version='v3.3',generation=108,
        sha256=c.sha(out/'GXRCE.DAT'),file_bytes=len(blob),engine_bytes=len(engine),bss_bytes=layout['bss_bytes'],
        data_bytes=layout['data_bytes'],main_request=main,relocation_bytes=len(relraw),
        full_r5_reproduced=True,all_48_entries_and_records_unchanged=True,
        visible_rows={'50mm':10,'Mount':8,'28mm':0},camera_acceptance=False,resident_changed=False,
        body_changed=False,ABI_changed=False,comparison_full_r5=dict(file_bytes=59704,engine_bytes=50276,
        bss_bytes=11172,data_bytes=9164,main_request=78380,session_request=912))
    c.save(out/'manifest.json',manifest)
    assert c.freeze_check()==frozen
    print(json.dumps(manifest,sort_keys=True))


if __name__=='__main__':main()
