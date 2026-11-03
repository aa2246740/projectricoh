"""Reproduce full-r5 read-only, change two aliases, link v3.3 and pack 108."""
from pathlib import Path
import copy
import json
import shutil
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import service_build


def model():
    sys.path.insert(0,str(c.PRODUCT))
    candidates=c.load(c.PRODUCT/'candidates.py','v33_candidates')
    pack=candidates.pack
    r5=c.load(c.ROOT/'firmware/full_r5/build.py','frozen_r5_pipeline')
    u=c.load(c.ROOT/'firmware/full_r5/common.py','frozen_r5_common')
    u.LOCAL=c.LOCAL/'r5-reproduction';u.LOCAL.mkdir(exist_ok=True)
    r5.c=u
    modules=r5.reproduce_r4(candidates,pack)
    source=r5.negative_tables(pack)
    for mi,key in ((0,'negative50'),(2,'negative_mount')):
        modules[mi]['entries'][2]=source[key]
    base=c.ROOT/'firmware/full_r5/local/full-r5'
    assert c.sha(base/'GXRCE.DAT')=='7034a8afde38f260c7095ff6183725ba64208d4d4174886a5fb0fb5b295dd385'
    layout=json.loads((base/'layout.json').read_text())
    assert pack.pack_model(copy.deepcopy(modules),107,**r5.arguments(base,layout))[0]==(base/'GXRCE.DAT').read_bytes()
    before=copy.deepcopy(modules)
    m=modules[0]
    for slot in (9,10):
        m['records'][slot-1]=pack.v1.alias_record(slot)
        m['refs'][slot-1]=4;m['ranges'][slot-1]=copy.deepcopy(m['ranges'][10])
        del m['entries'][slot]
    checks=[]
    for mi in range(3):
        for slot in range(1,17):
            a,b=before[mi],modules[mi]
            changed=mi==0 and slot in (9,10)
            if not changed:
                assert a['records'][slot-1]==b['records'][slot-1]
                assert a['entries'][a['refs'][slot-1]]==b['entries'][b['refs'][slot-1]]
                assert a['ranges'][slot-1]==b['ranges'][slot-1]
            else:
                assert b['records'][slot-1]==pack.v1.alias_record(slot)
                assert b['entries'][b['refs'][slot-1]]==b['entries'][4]
            checks.append(dict(unit=mi,slot=slot,changed=changed))
    c.save(c.LOCAL/'model-proof.json',dict(full_r5_reproduced=True,changed=[[0,9],[0,10]],checks=checks))
    return candidates,modules,r5


def main():
    raise SystemExit('STOP_R6_01: no approved engine-only first-build cursor fix; generation 109 is not built')
    c.guard();c.freeze_check()
    candidates,modules,r5=model();pack=candidates.pack
    service_build.main()
    inert,_,_=pack.pack_model(copy.deepcopy(modules),108)
    layout=candidates.build.build(len(inert)-256-len(pack.STUB),lto=True)
    built=c.LOCAL/'product/m32r-lto';out=c.LOCAL/'full-r6';out.mkdir(exist_ok=True)
    relraw=(built/'reloc.bin').read_bytes()
    approved=c.ROOT/'firmware/full_r5/local/full-r5/GXRCE.DAT'
    raw=approved.read_bytes()
    blob,trust,stats=pack.pack_model(modules,108,engine=(built/'engine.bin').read_bytes(),
        relocations=[struct.unpack_from('>II',relraw,i) for i in range(0,len(relraw),8)],
        bss=layout['bss_bytes'],entry=layout['entries']['ig_bootstrap'],
        resident_id=raw[80:112],abi_id=raw[212:228])
    assert len(blob)==layout['file_bytes'] and len(blob)<=65536
    assert b'v3.3\0' in blob[256:256+layout['engine_bytes']]
    for name in ('engine.bin','engine.elf','engine.map','reloc.bin'):
        shutil.copyfile(built/name,out/name)
    (out/'GXRCE.DAT').write_bytes(blob);(out/'trust.bin').write_bytes(trust)
    (out/'effective-rows.bin').write_bytes(r5.golden(modules,pack))
    c.save(out/'layout.json',layout)
    r5.identity_proof(candidates.build.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','v33_elf_reader'),blob,pack)
    # The frozen helper's output guard was redirected to this task's local/.
    c.save(out/'manifest.json',dict(status='BUILT_HOST_ONLY',generation=108,engine_version='v3.3',
        sha256=c.sha(out/'GXRCE.DAT'),changes=[[0,9],[0,10]],**stats,
        bss_bytes=layout['bss_bytes'],main_request=7504+((len(blob)+layout['bss_bytes']+3)&~3),
        body_trust_sha256=raw[48:80].hex(),
        approved_body_image_sha256='05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c',
        resident_elf_sha256='f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58',
        resident_build=raw[80:112].hex(),abi=raw[212:228].hex(),
        camera_acceptance=False))
    (c.LOCAL/'product/entries.h').write_text(''.join(f'#define OFF_{k.upper()} {v}u\n' for k,v in layout['entries'].items()))
    for mi,m in enumerate(modules):
        for slot in range(1,17):
            path=out/'expanded'/m['name']/f'{slot:02}.entry';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(m['entries'][m['refs'][slot-1]])
    c.freeze_check()
    print(json.dumps(dict(status='PASS',generation=108,file_bytes=len(blob),**{k:layout[k] for k in ('engine_bytes','bss_bytes')},sha256=c.sha(out/'GXRCE.DAT'))))


if __name__=='__main__':main()
