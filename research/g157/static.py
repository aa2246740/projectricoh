"""Real host C parsers plus independent serialized-record and private-range audits."""
from pathlib import Path
import ctypes as T
import argparse
import json
import struct
import subprocess
import sys
import types
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
D=C.D
def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=('control','model'),default='control');a=p.parse_args()
    C.setup();C.DATASET=a.dataset;C.compute_gate('host-C-parsers')
    module=C.load(C.ROOT/'research/v39_g153/format_checks.py','g157_host_parsers')
    module.ROOT=C.ROOT;module.PRODUCT=C.PRODUCT;module.TMP=C.LOCAL/'parser';module.HERE=C.LOCAL
    module.subprocess=types.SimpleNamespace(run=lambda argv,**kw:subprocess.run([*argv,'-DRV_HOST'],**kw))
    (C.LOCAL/'evidence').mkdir(exist_ok=True)
    lib=module.library();rows=[];readbacks=[]
    layout=json.loads((C.LOCAL/'layout.json').read_text())
    for profile,package in C.PACKAGES.items():
        manifest,slots,looks=R.read_manifest(C.artifact(profile)['records'])
        raw=C.artifact(profile)['dat'].read_bytes();D.sections(raw);fx=D.strict_effects(raw)
        assert D.u32(raw,28)==157 and fx['count']<=48
        ext=D.u32(raw,204)+1408;assert D.u16(raw,ext+24)==3
        for u in range(3):
            result=lib.check_dat(raw,len(raw),module.trust(raw),u);assert result==0,(profile,u,result)
            rows.append(dict(profile=profile,unit=C.UNITS[u],case='final',result=result))
            for generation in (156,155,158):
                bad=bytearray(raw);struct.pack_into('>I',bad,28,generation);bad=D.seal(bad)
                result=lib.check_dat(bad,len(bad),module.trust(bad),u);assert result!=0
                rows.append(dict(profile=profile,unit=C.UNITS[u],case='header-generation-'+str(generation),result=result))
            for s in range(1,9):
                actual=D.expand(raw,u,s);assert actual==slots[u][s]
                readbacks.append(dict(profile=profile,unit=C.UNITS[u],kind='builtin',slot=s,full_552_equal=True,sha256=C.sha(actual)))
            a,_=D.effect_area(raw);visible=[]
            for i in range(D.u16(raw,a+10)):
                e=raw[a+32+32*i:a+64+32*i]
                if not e[18]>>u&1:continue
                name=e[20:].split(b'\0')[0].decode();actual=D.expand_effect(raw,i)
                _,source,exact=next(r for r in looks[u] if r[0]==name)
                assert actual[:4]+actual[8:]==source[:4]+source[8:]
                assert not exact or actual==source
                visible.append(name);readbacks.append(dict(profile=profile,unit=C.UNITS[u],kind='look',name=name,index=i,full_552_equal=True,source_identity_crc_rebound=actual!=source,sha256=C.sha(actual)))
            assert len(visible)==18 and set(C.RESTORE)<=set(visible)
            base=R.frozen(Path('firmware/package_v310_g156/GXRCE.DAT'))
            assert D.expand(raw,u,4)==D.expand(base,u,4)
    before=json.loads((C.LOCAL/'frozen.json').read_text())
    drift=[r['path'] for r in before['files'] if C.sha((C.ROOT/r['path']).read_bytes())!=r['sha256']]
    assert not drift,drift
    copies=[p for p in (C.ENGINE/'resident').iterdir() if p.is_file()]
    assert all(p.read_bytes()==(C.BASE/'resident'/p.name).read_bytes() for p in copies)
    assert layout['sizes']['Engine']<=5120 and layout['sizes']['BootDiagnostic']<=1024
    assert not list(C.PRODUCT.glob('blackbox.*'))
    C.save(C.receipt('static.json'),dict(status='PASS',dataset=C.DATASET,parser_cases=rows,readbacks=readbacks,original04_equal_all_units=True,
        old_inputs_unchanged=True,resident_copy_byte_identical=True,arena=layout,legacy_blackbox_writers=0,
        DAT_sha256={p:C.sha(C.artifact(p)['dat'].read_bytes()) for p in ('test','release')},
        record_manifest_sha256={p:C.sha(C.artifact(p)['records'].read_bytes()) for p in ('test','release')}))
    print(json.dumps(dict(status='PASS',parser_cases=len(rows),readbacks=len(readbacks),sizes=layout['sizes'])))
if __name__=='__main__':main()
