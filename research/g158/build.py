"""Link the real g158 image against the unchanged v3.10 resident trust."""
from pathlib import Path
import argparse
import json
import shutil
import struct
import sys
import types
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
D=C.D
def compile_engine(profile,data_bytes):
    C.compute_gate('link-'+profile)
    candidate=C.ENGINE/'candidate'
    cfg=types.ModuleType('common')
    for key,value in dict(ROOT=C.ROOT,HERE=candidate,LOCAL=candidate/'local',RESIDENT=C.ENGINE/'resident',GCC=C.GCC,LD=C.LD,OBJDUMP=C.OBJDUMP,
                          guard=lambda: None,run=C.run,sha=lambda p:C.sha(Path(p).read_bytes())).items():setattr(cfg,key,value)
    def load(path,name):
        if name=='approved_service_profile':path=C.ROOT/'firmware/resident_v37/resident/build.py'
        return C.load(path,name)
    cfg.load=load;sys.modules['common']=cfg
    cfg.LOCAL.mkdir(parents=True,exist_ok=True)
    service=C.load(candidate/'service_build.py','g158_service_build')
    service.LOCAL.mkdir(parents=True,exist_ok=True)
    reader=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g158_elf_reader')
    service.engine_library(reader)
    runtime=types.ModuleType('runtime')
    for key,value in dict(HERE=C.PRODUCT,ROOT=C.ROOT,LOCAL=candidate/'local/product-r13',SRC=C.PRODUCT/'src',GCC=C.GCC,LD=C.LD,OBJDUMP=C.OBJDUMP,
                          guard=lambda:None,load=load,run=C.run,sha=cfg.sha).items():setattr(runtime,key,value)
    runtime.LOCAL.mkdir(parents=True,exist_ok=True);sys.modules['runtime']=runtime
    builder=C.load(C.PRODUCT/'build.py','g158_product_build')
    builder.FLAGS+=['-DG158_BOOT='+str(int(profile=='test'))]
    original=builder.sources
    builder.sources=lambda:[(C.ENGINE/'resident/shared.c' if p.name=='shared.c' else p,svc) for p,svc in original()]
    layout=builder.build(data_bytes,True,'oz')
    source=runtime.LOCAL/'m32r-lto-oz'
    output=C.artifact(profile)['build']
    output.mkdir(parents=True,exist_ok=True)
    for name in ('engine.elf','engine.bin','reloc.bin','engine.map','size.json','relocations.json'):
        shutil.copyfile(source/name,output/name)
    return output,layout
def package(profile,manifest,reuse=False):
    template=R.serialize(manifest)
    sections=D.sections(template)
    data_bytes=sum(n for _,n in sections[2:])
    output=C.artifact(profile)['build']
    if reuse:
        layout=json.loads((output/'size.json').read_text());assert layout['data_bytes']==data_bytes
    else:output,layout=compile_engine(profile,data_bytes)
    parts=[(output/'engine.bin').read_bytes(),(output/'reloc.bin').read_bytes()]+[template[at:at+n] for at,n in sections[2:]]
    starts=[];at=256
    for part in parts:starts.append(at);at+=len(part)
    assert layout['file_bytes']==at
    directory=bytearray(parts[2])
    for u in range(3):
        for field,index in ((12,3),(16,4),(20,5),(24,6)):
            old=D.u32(directory,64*u+field)
            struct.pack_into('>I',directory,64*u+field,old+starts[index]-sections[index][0])
    parts[2]=directory
    header=bytearray(template[:256]);struct.pack_into('>I',header,16,at)
    struct.pack_into('>IIH',header,112,layout['entries']['ig_bootstrap'],layout['bss_bytes'],len(parts[1])//8)
    for i,part in enumerate(parts):struct.pack_into('>II',header,132+12*i,starts[i],len(part))
    raw=D.seal(header+b''.join(parts));D.sections(raw);fx=D.strict_effects(raw)
    for u in range(3):assert D.expand(raw,u,4)==D.expand(template,u,4)
    request=7628+D.align4(len(raw)+layout['bss_bytes'])
    result=dict(generation=158,body='v3.10',profile=profile,boot=int(profile=='test'),diagnostics=True,readback=True,
        dat_sha256=C.sha(raw),dat_bytes=len(raw),code_bytes=len(parts[0]),code_limit=69632,bss_bytes=layout['bss_bytes'],
        main_request=request,main_limit=107612,main_headroom=107612-request,users=3,looks_per_unit=18,global_looks=fx['count'],
        engine_arena_limit=5120,diagnostic_arena_limit=1024,linked=True,pic_translation_verified=layout['pic_translation_verified'],
        records_manifest_sha256=C.sha(Path(manifest).read_bytes()),camera_verified=False,status='ACCEPTANCE_PENDING',
        tradeoff=json.loads(Path(manifest).read_text())['tradeoff'])
    C.save(output/'capacity.json',result)
    # Keep rejected linked results inspectable; do not publish an over-limit package.
    assert len(raw)<=98304 and len(parts[0])<=69632 and request<=107612,result
    (output/'GXRCE.DAT').write_bytes(raw)
    layout.update(file_bytes=len(raw),dat_sha256=C.sha(raw),generation=158,profile=profile)
    C.save(output/'layout.json',layout)
    result['dataset']=C.DATASET
    target=C.artifact(profile)['package'];sd=target/'SD_ROOT';sd.mkdir(parents=True,exist_ok=True)
    (sd/'GXRCE.DAT').write_bytes(raw)
    C.save(target/'MANIFEST',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=('test','release'),required=True);p.add_argument('--dataset',choices=('control','model'),default='control');p.add_argument('--manifest',type=Path);p.add_argument('--reuse-link',action='store_true');a=p.parse_args()
    C.setup();C.DATASET=a.dataset;C.compute_gate('package-'+a.dataset+'-'+a.profile)
    package(a.profile,a.manifest or C.artifact(a.profile)['records'],a.reuse_link)
