"""Run full legacy-body refusal paths before any generation 160 entry."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H


def refused(cam):
    before=cam.h.b.visits[cam.h.symbols['rv_invoke']];cam.open()
    result=dict(engine_calls=cam.h.b.visits[cam.h.symbols['rv_invoke']]-before,
        state=cam.h.u(H.R+5,1),flags=cam.h.u(H.R+212),rows=cam.h.u(0x2022f5ac,1),names=hex(cam.h.u(0x2022f5a8)))
    assert result['engine_calls']==0 and result['state']==6 and result['rows']==7 and result['names']=='0x2022d610',result
    assert result['flags']&1 and not result['flags']&128,result
    result['audit']=cam.audit();return result


def main():
    s.enable();unit=sys.argv[1];result={};frozen={}
    sources=(('c0',s.ROOT/'research/body_v39/local/c0/ilaunch3',s.ROOT/'research/body_v39/local/c0/resident.elf',
               'c0f8065d58e78fda09ad13580c941647a4a20d1e3225e302dbed0b05251d6f3f'),
             ('v38',s.ROOT/'firmware/resident_v38/local/body/ilaunch3',s.ROOT/'firmware/resident_v38/local/resident/build/resident.elf',
               'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'))
    for name,body,resident,expected in sources:
        assert s.sha(body)==expected
        frozen[str(body.relative_to(s.ROOT))]=s.sha(body);frozen[str(resident.relative_to(s.ROOT))]=s.sha(resident)
        reader=s.load(s.ROOT/'firmware/stage2l_switch/tools/build.py','historical_elf_'+name)
        elf=reader.Elf(resident);section=next(row for row in elf.sections if row['name']=='.resident');raw=body.read_bytes()
        matches=[]
        for index in range(16):
            source,base,size,_,_=struct.unpack_from('>5I',raw,0x20+20*index)
            if base<=section['va'] and section['va']+section['size']<=base+size:
                at=source+0x200+section['va']-base;matches.append(raw[at:at+section['size']]==elf.content(section))
        assert matches==[True],(name,matches)
        cam=H.Session(unit,True,body=body,resident=resident)
        cam.p.files.paths={'/ATA1/GXRCE.DAT':H.DAT.read_bytes()}
        result[name+'_body_new_dat']=refused(cam)
        if name=='c0':
            prior=s.ROOT/'research/body_v39/local/combos/c0-g149/local/SD_ROOT/GXRCE.DAT'
            frozen[str(prior.relative_to(s.ROOT))]=s.sha(prior)
            q=cam.pe.SCRATCH;cam.h.b.write(q,prior.read_bytes()[:256])
            positive=cam.p.call(cam.h.symbols['rv_header'],(q,prior.stat().st_size,cam.h.symbols['rv_trust']))
            assert positive.get('ok') and positive['r0']==0,positive
            result['c0_old_dat_positive_header']=0
    prior=s.ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT'
    frozen[str(prior.relative_to(s.ROOT))]=s.sha(prior)
    assert struct.unpack_from('>I',prior.read_bytes(),28)[0]==150
    cam=H.Session(unit,True);cam.p.files.paths={'/ATA1/GXRCE.DAT':prior.read_bytes()}
    result['g151_body_g150_dat']=refused(cam)
    assert all(s.sha(s.ROOT/path)==digest for path,digest in frozen.items())
    s.save(s.HERE/'evidence'/('historical-headers-'+unit+'.json'),dict(status='PASS',unit=unit,
        dat_sha256=s.sha(H.DAT),inputs=frozen,result=result))
    print('PASS legacy load refusal',unit,flush=True)


if __name__=='__main__':main()
