"""Final package dimensions, immutable inputs and byte identity checks."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import struct
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from dat_format import sha,u16,u32,sections,effect_area,align4,strict_effects

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def main():
    start=time.time_ns();tick=time.monotonic();tmp=Path(os.environ['TMPDIR'])/'artifact';tmp.mkdir(parents=True,exist_ok=True)
    old=ROOT/'firmware/package_v38_g150/local/SD_ROOT'
    release=ROOT/'firmware/package_v38_g152/local/SD_ROOT';test=ROOT/'firmware/package_v38_g152_test/local/SD_ROOT'
    raw=(release/'GXRCE.DAT').read_bytes();tested=(test/'GXRCE.DAT').read_bytes();sections(raw);sections(tested)
    package=json.loads((HERE/'package.json').read_text())
    assert sha(raw)==package['release']['dat_sha256'] and sha(tested)==package['test']['dat_sha256']
    bodies=[]
    for path in sorted(old.iterdir()):
        if path.is_file() and path.name!='GXRCE.DAT':
            assert path.read_bytes()==(release/path.name).read_bytes()==(test/path.name).read_bytes()
            bodies.append(dict(name=path.name,bytes=path.stat().st_size,sha256=sha(path.read_bytes())))
    assert len(bodies)==29
    oldtest=(ROOT/'firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    user=lambda data:data[u32(data,204)+1408:u32(data,204)+3392]
    assert user(tested)==user(oldtest) and u16(user(raw),24)==0 and u16(user(tested),24)==3
    assert raw[u32(raw,204)+3392:]==tested[u32(tested,204)+3392:]
    a,n=effect_area(raw);b,m=effect_area(tested);assert raw[a:a+n]==tested[b:b+m]
    assert raw[u32(raw,192):u32(raw,192)+u32(raw,196)]==tested[u32(tested,192):u32(tested,192)+u32(tested,196)]
    frozen=json.loads((HERE/'input_receipt.json').read_text())['files'];inputs=[]
    for name,record in frozen.items():
        actual=(ROOT/name).read_bytes();assert len(actual)==record['bytes'] and sha(actual)==record['sha256'],name
        inputs.append(name)
    reviews=json.loads((HERE/'review_input_receipt.json').read_text())
    for name,hash_value in reviews.items():assert sha((ROOT/name).read_bytes())==hash_value,name
    for row in json.loads((HERE/'lut_receipt.json').read_text()):
        assert sha(Path(row['source']).read_bytes())==sha((ROOT/row['copy']).read_bytes())==row['sha256']
    resident=ROOT/'firmware/engine_v60_g152/resident'
    assert all(p.read_bytes()==(ROOT/'firmware/resident_v38/resident'/p.name).read_bytes() for p in resident.iterdir() if p.is_file())
    source='#include "'+str(resident/'resident.h')+'"\nconst unsigned g152_dimensions[]={sizeof(RvSession),RV_SESSION_BYTES,RV_BLOCK_OVERHEAD,RV_MAX_IMAGE};\n'
    (tmp/'dimensions.c').write_text(source)
    compiler=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(compiler),'-std=c11','-Oz','-ffreestanding','-fno-builtin','-fpic','-m32r','-c',str(tmp/'dimensions.c'),'-o',str(tmp/'dimensions.o')],capture_output=True,check=True,timeout=2400)
    mod=load(ROOT/'firmware/stage2l_switch/tools/build.py','g152_artifact_elf');elf=mod.Elf(tmp/'dimensions.o')
    sym=elf.symbols['g152_dimensions'];data=elf.content(elf.sections[sym['section']])[sym['value']:sym['value']+sym['size']]
    session,aligned,overhead,max_image=struct.unpack('>4I',data);assert(session,aligned,overhead)==(1104,1104,7504)
    layout=json.loads((ROOT/'firmware/engine_v60_g152/candidate/local/full-r13/layout.json').read_text())
    main_request=overhead+align4(len(raw)+layout['bss_bytes'])
    assert len(raw)==len(tested)<=97792 and layout['engine_bytes']<=65536 and main_request<=107612
    assert 108124-main_request>=512 and 98304-len(raw)>=512
    result=dict(status='PASS',started_ns=start,ended_ns=time.time_ns(),seconds=time.monotonic()-tick,
                dat_sha256=sha(raw),test_dat_sha256=sha(tested),body_files=bodies,
                frozen_inputs_unchanged=len(inputs),review_inputs_unchanged=len(reviews),LUT_sources_unchanged=10,
                release_users=0,test_users=3,user_extension_identical_to_g150=True,
                dimensions=dict(file=len(raw),code=layout['engine_bytes'],BSS=layout['bss_bytes'],session=session,
                                overhead=overhead,main_request=main_request,main_margin=108124-main_request,
                                file_margin=98304-len(raw),maximum_image=max_image),effects=strict_effects(raw))
    (HERE/'evidence/artifacts.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='body_files'}))

if __name__=='__main__':main()
