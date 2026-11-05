"""Check BOOT's distinct compensation orchestration under every PASM pair."""
from pathlib import Path
import json,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('BOOT-PASM-all-W')
out=C.LOCAL;core=C.PRODUCT/'src/firmware/engine/core';source=out/'fault_harness.c';binary=out/'boot-fault-harness'
args=['/usr/bin/clang','-std=c11','-O2','-fno-builtin','-DENG_HOST','-DRV_HOST','-I'+str(C.PRODUCT),str(source),str(core/'eng_data.c'),str(core/'eng_crc_compat.c'),str(core/'eng_pin_stub.c'),str(C.PRODUCT.parent.parent/'engine_services/crc.c'),str(out/'parser/parsers.dylib'),'-o',str(binary)]
p=subprocess.run(args,capture_output=True,text=True);(out/'boot-fault-build.log').write_text(p.stdout+p.stderr);assert not p.returncode,p.stderr
raw=C.artifact('test')['dat'];rows=[];started=time.monotonic()
for sub in range(4):
    for unit in range(3):
        while True:
            try:C.compute_gate('BOOT-'+str(sub)+'-'+str(unit));break
            except RuntimeError as e:
                if 'LOAD_DEFERRED' not in str(e):raise
                time.sleep(5)
        for target in (0,1,3):
            def run(kind,position):
                argv=[str(binary),str(raw),str(unit),str(kind),str(position),'0',str(out/'settings/test-mount-HC1.bin'),str(target),str(sub)]
                p=subprocess.run(argv,capture_output=True,text=True)
                if p.returncode:
                    C.save(out/'BOOT-C-first-failure.json',dict(unit=unit,submode=sub,target=target,kind=kind,position=position,stdout=p.stdout,stderr=p.stderr,completed=len(rows)))
                    raise AssertionError((sub,unit,target,kind,position,p.stderr))
                r=json.loads(p.stdout);r.update(raw_mode=4,submode=sub,N=(0x8010,0x8020,0x8008,0x8800)[sub],target=('HC+1','Acros','user3','colour05')[target]);rows.append(r)
                assert r['full_colour'] or r['pure04'] or r['dirty']&12,r
                if kind in (1,8,14,15):assert r['triggered']==1
                return r
            base=run(0,0);assert base['full_colour'] and not base['dirty']&12
            for kind in (1,8):
                for pos in range(1,base['writes']+1):run(kind,pos)
            for kind in (14,15):
                for pos in range(1,base['setting_words']+1):run(kind,pos)
            for kind,pos in ((4,1),(5,8),(6,8),(3,1)):
                r=run(kind,pos)
                if kind==5:assert r['dirty']&12
        C.save(out/'BOOT-C-progress.json',dict(cases=len(rows),submode=sub,unit=unit,seconds=time.monotonic()-started))
C.save(out/'BOOT-C-matrix.json',dict(status='PASS',cases=len(rows),rows=rows,DAT_sha256=C.sha(raw.read_bytes()),driver_sha256=C.sha(Path(__file__).read_bytes()),scope='Active test BOOT path, actual product C/math and gate, declared services/peer. Release policy remains off; no claim that BOOT calls apply_impl or recover_confirmed.'))
print(json.dumps(dict(status='PASS',cases=len(rows))))
