"""Exhaust every manual peer-W edge against the product C and final recipe data."""
from pathlib import Path
import argparse, json, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--submode',type=int,required=True);a=p.parse_args()
C.setup();C.DATASET='model';C.compute_gate('fix-r1-C-matrix')
out=C.LOCAL;review=C.ROOT/'research/review_g157_r1/local'
source=(C.LOCAL/'fault_harness.c').read_text()
file=out/('fault_harness-'+str(a.submode)+'.c');file.write_text(source);binary=out/('fault-harness-'+str(a.submode))
core=C.PRODUCT/'src/firmware/engine/core'
argv=['/usr/bin/clang','-std=c11','-O2','-g','-fno-builtin','-DENG_HOST','-DRV_HOST','-I'+str(C.PRODUCT),str(file),str(core/'eng_data.c'),str(core/'eng_crc_compat.c'),str(core/'eng_pin_stub.c'),str(C.PRODUCT.parent.parent/'engine_services/crc.c'),str(C.LOCAL/'parser/parsers.dylib'),'-o',str(binary)]
compiled=subprocess.run(argv,capture_output=True,text=True);(out/('fault-build-'+str(a.submode)+'.log')).write_text(compiled.stdout+compiled.stderr);assert not compiled.returncode,compiled.stderr
settings=out/'settings/test-mount-vivid09.bin';rows=[];start=time.monotonic()
def run(profile,u,kind,at,entry,target):
    args=[str(binary),str(C.artifact(profile)['dat']),str(u),str(kind),str(at),str(entry),str(settings),str(target),str(a.submode)]
    proc=subprocess.run(args,capture_output=True,text=True)
    if proc.returncode:
        failure=dict(profile=profile,unit=u,kind=kind,at=at,entry=entry,target=target,stdout=proc.stdout,stderr=proc.stderr,completed=len(rows))
        if not (out/'C-first-failure.json').exists():C.save(out/'C-first-failure.json',failure)
        C.save(out/('C-failure-'+str(time.time_ns())+'.json'),failure)
        raise AssertionError((profile,u,kind,at,entry,target,proc.stderr))
    row=json.loads(proc.stdout);row.update(submode=a.submode,raw_mode=4,native_selection=(0x8010,0x8020,0x8008,0x8800)[a.submode],profile=profile,entry=('boot','standard','Vivid09','WB')[entry],target=('HC+1','Acros','user3','colour05')[target],DAT_sha256=C.sha(C.artifact(profile)['dat'].read_bytes()))
    rows.append(row);return row
for profile in ('test','release'):
    for u in range(3):
        while True:
            try:C.compute_gate('C-'+profile+'-'+str(u));break
            except RuntimeError as e:
                if 'LOAD_DEFERRED' not in str(e):raise
                time.sleep(5)
        for entry in (1,2,3):
            for target in (0,1,2,3):
                base=run(profile,u,0,1,entry,target)
                for kind in (1,8):
                    for at in range(1,base['writes']+1):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                for kind in (14,15):
                    for at in range(1,base['setting_words']+1):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                t0=run(profile,u,18,0,entry,target)
                assert t0['writes']>=base['writes']+1
                for kind in (16,17):
                    for at in sorted({1,2,t0['writes']}):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                for kind in (3,4,10,11,12,13,5,6):run(profile,u,kind,8 if kind in (5,6) else 1,entry,target)
        C.save(out/('C-progress-'+str(a.submode)+'.json'),dict(completed=len(rows),profile=profile,unit=u,seconds=time.monotonic()-start))
C.save(out/('C-matrix-'+str(a.submode)+'.json'),dict(status='PASS',cases=len(rows),rows=rows,seconds=time.monotonic()-start,
    scope='Product C/math and final DAT data, declared peer/services; every actual W position has ACK failure and BUSY after the peer write. Includes settings/preview/memory and persistent faults. Does not replace final-DAT ISA or cold MAIN evidence.'))
print(json.dumps(dict(status='PASS',cases=len(rows))))
