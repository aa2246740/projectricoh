"""Final machine replay, target ABI sizes, envelope and historical negatives."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TASK=ROOT/'firmware/engine_v36_r28'
CAND=TASK/'candidate'
OUT=HERE/'extra'
RES=ROOT/'firmware/resident_v34c/resident'

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def run(argv,label):
    env=dict(os.environ,TMPDIR=str(HERE/'tmp'),CLANG_MODULE_CACHE_PATH=str(HERE/'tmp/modules'),
        ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',LC_ALL='C')
    r=subprocess.run([str(x) for x in argv],cwd=ROOT,env=env,capture_output=True,timeout=600)
    (OUT/(label+'.stdout')).write_bytes(r.stdout);(OUT/(label+'.stderr')).write_bytes(r.stderr)
    with (OUT/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(label=label,argv=[str(x) for x in argv],returncode=r.returncode))+'\n')
    assert not r.returncode,(label,r.stderr[-1800:])
    return r.stdout.decode()

def machine():
    m=load(TASK/'machine115.py','delta_packed_machine');m.OUT=HERE/'packed_machine';m.main()

def sizes():
    sys.path.insert(0,str(CAND/'containers/product'))
    b=load(CAND/'containers/product/build.py','delta_target_flags')
    obj=OUT/'sizes.o'
    run([b.GCC,*b.FLAGS,'-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
        '-I',CAND/'containers/product','-I',RES,'-c',CAND/'layout.c','-o',obj],'target-sizes')
    reader=load(ROOT/'firmware/stage2l_switch/tools/build.py','delta_size_elf');e=reader.Elf(obj)
    s=e.symbols['v33_target_sizes'];sec=e.sections[s['section']];off=s['value']-sec['va']
    values=struct.unpack_from('>8I',e.content(sec),off)
    names=('SessionWork','PnGxts','PsStore','RvLoadWork','RvUiSnapshot','Integrated','RvSession','RV_BLOCK_OVERHEAD')
    measured=dict(zip(names,values));raw=(CAND/'local/full-r13/GXRCE.DAT').read_bytes()
    main=measured['RV_BLOCK_OVERHEAD']+len(raw)+struct.unpack_from('>I',raw,116)[0]
    assert main==84276
    result=dict(sizes=measured,main_request=main,install_buffers=[65536,65536],native_header_each=12,
        first_install=main+measured['RvLoadWork']+131072+48,
        first_install_existing_ui=main+measured['RvLoadWork']+131072+48+measured['RvUiSnapshot']+12,
        steady_all=main+measured['RvLoadWork']+measured['RvUiSnapshot']+measured['SessionWork']+48,
        irom_bytes_two_versions_114_115=65088+65252,irom_bytes_113_114_and_115_temp=64816+65088+65252,
        real_heap_free_and_irom_space_unknown=True)
    (OUT/'sizes.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS independent target ABI and allocation requests',result['first_install_existing_ui'])

def envelope():
    source=OUT/'envelope.c';source.write_bytes((TASK/'envelope115.c').read_bytes())
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',RES]
    objects=[]
    for i,src in enumerate((source,RES/'validate_envelope.inc.c',RES/'runtime.c',ROOT/'firmware/resident_v34c/local/resident/trust.c')):
        obj=OUT/f'envelope-{i}.o';objects.append(obj)
        extra=['-Dmemcpy=rv_memcpy','-Dmemset=rv_memset'] if src.name=='runtime.c' else []
        run(['/usr/bin/clang',*flags,*extra,'-c',src,'-o',obj],f'envelope-compile-{i}')
    binary=OUT/'validate';run(['/usr/bin/clang',*flags,*objects,'-o',binary],'envelope-link')
    original=(CAND/'local/full-r13/GXRCE.DAT').read_bytes()
    def seal(raw):
        struct.pack_into('>I',raw,24,zlib.crc32(raw[256:]));struct.pack_into('>I',raw,20,0)
        struct.pack_into('>I',raw,20,zlib.crc32(raw[:256]));return raw
    word=lambda off:struct.unpack_from('>I',original,off)[0]
    cases=[('valid',bytearray(original),0)]
    for name,off,value,want in [('generation-zero',28,0,3),('entry-outside',112,0,6),
        ('image-overflow',116,114688-len(original)+4,2),('section-overlap',156,word(132),6),
        ('reloc-unaligned',word(144),257,15),('reloc-target-zero',word(144)+4,0,15)]:
        raw=bytearray(original);struct.pack_into('>I',raw,off,value);cases.append((name,seal(raw),want))
    for name,off,want in [('wrong-body',48,7),('wrong-build',80,8),('wrong-abi',212,8)]:
        raw=bytearray(original);raw[off]^=1;cases.append((name,seal(raw),want))
    raw=bytearray(original);struct.pack_into('>H',raw,120,257);cases.append(('reloc-count',seal(raw),15))
    for name,off in [('header-crc',20),('payload-crc',256)]:
        raw=bytearray(original);raw[off]^=1;cases.append((name,raw,5))
    raw=bytearray(original)+bytes(98308-len(original));struct.pack_into('>I',raw,16,len(raw))
    cases.append(('resident-file-limit',seal(raw),2))
    results=[]
    for name,data,want in cases:
        path=OUT/(name+'.DAT');path.write_bytes(data);got=int(run([binary,path],'envelope-'+name));assert got==want,(name,want,got)
        results.append(dict(case=name,expected=want,actual=got))
    (OUT/'envelope.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS frozen resident envelope',len(results))

def historical():
    binary=ROOT/'research/review_publish_v114/host/host'
    old=ROOT/'firmware/engine_v35_publish/candidate/local/full-r12'
    baseline=ROOT/'firmware/resident_v34c/acceptance/local/full-r11'
    legacy=ROOT/'firmware/resident_v33/acceptance/local/full-r9/GXRCE.DAT'
    results=[]
    for gen,folder in ((113,baseline),(114,old)):
        for case in ('basic','first'):
            text=run([binary,case,1,folder/'GXRCE.DAT',folder/'trust.bin',folder/'effective-rows.bin',legacy,'0'],f'historical-{gen}-{case}')
            assert text.splitlines()[-1].startswith('OK ')
            results.append(dict(generation=gen,unit=1,case=case,native_only_assertions=True))
    for unit in range(3):
        text=run([binary,'review',unit,old/'GXRCE.DAT',old/'trust.bin',old/'effective-rows.bin',baseline/'GXRCE.DAT','0'],f'prior-independent-114-{unit}')
        assert text.splitlines()[-1].startswith('OK ')
    (OUT/'historical.json').write_text(json.dumps(dict(historical=results,original_independent_review_cases=3),indent=2)+'\n')
    print('PASS prior independent counterexamples and scoped gen113/114 native-only assertions')

def logs():
    decoder=load(TASK/'decode_blackbox.py','delta_log_decoder');results=[]
    for unit in range(3):
        for boot,kind in ((0,0),(1,4)):
            p=HERE/'host'/f'sticky115-{unit}.BIN-boot{boot}.BIN'
            d=decoder.read_log(p.read_bytes())
            assert d['header']['engine_generation']==115 and d['first_seed_inputs']['type_byte']==kind
            assert d['seed_inputs']['type_byte']==5 and d['first_seed_inputs']['event_sequence']<d['seed_inputs']['event_sequence']
            results.append(dict(source=str(p.relative_to(HERE)),decoded=d))
    for unit in (0,2):
        p=ROOT/f'firmware/engine_v35_publish/local/seed-{unit}.BIN';d=decoder.read_log(p.read_bytes())
        assert d['header']['engine_generation']==114 and d['first_seed_inputs'] is None
    p=ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root'
    for name in ('GXRBX0.BIN','GXRBX1.BIN'):
        d=decoder.read_log((p/name).read_bytes());assert d['header']['engine_generation']==113
        assert d['first_seed_inputs'] is None and d['seed_inputs'] is None
    (OUT/'logs.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS sticky seed across two boots on all three units and old-log compatibility')

if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('machine','sizes','envelope','historical','logs')
    OUT.mkdir(exist_ok=True);(HERE/'tmp').mkdir(exist_ok=True)
    globals()[sys.argv[1]]()
