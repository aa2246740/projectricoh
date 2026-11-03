#!/usr/bin/python3 -I
"""Run one isolated Python-model case on frozen body and DAT bytes."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import sys
import time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g151_body/evidence'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g151')
TESTS=ROOT/'research/body_v39/tests'
SCRIPT_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
sys.path.insert(0,str(TESTS))
import v39_host as H


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def check_backend(cam):
    name=type(cam.h.b).__module__
    assert name=='python_backend',name
    return dict(module=name,source=str(Path(sys.modules[name].__file__).resolve()))


def configure_body(version):
    if version=='c0':
        H.PACKAGE=ROOT/'research/body_v39/local/combos/c0-g149/local/SD_ROOT'
        H.RESIDENT=ROOT/'research/body_v39/local/c0/resident.elf'
        H.ENGINE=ROOT/'firmware/engine_v58_g149/candidate/local/full-r13/engine.elf'
        H.BODY_SHA='c0f8065d58e78fda09ad13580c941647a4a20d1e3225e302dbed0b05251d6f3f'
    elif version=='v38':
        H.PACKAGE=ROOT/'firmware/package_v38_g150/local/SD_ROOT'
        H.RESIDENT=ROOT/'firmware/resident_v38/local/resident/build/resident.elf'
        H.ENGINE=ROOT/'firmware/engine_v58_g150/candidate/local/full-r13/engine.elf'
        H.BODY_SHA='d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
    else:
        assert version=='new'
    H.BODY=H.PACKAGE/'ilaunch3';H.DAT=H.PACKAGE/'GXRCE.DAT'


def route(unit,name):
    version,scenario=name.split(':',1)
    configure_body(version)
    H.setup();cam=H.Camera(unit)
    backend=check_backend(cam)
    files=cam.p.files
    dats={
        'g149':ROOT/'research/body_v39/local/combos/c0-g149/local/SD_ROOT/GXRCE.DAT',
        'g151':ROOT/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT',
        'g151-test':ROOT/'firmware/package_v39_g151_test/local/SD_ROOT/GXRCE.DAT',
        'g150':ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT',
        'g139':ROOT/'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT',
        'g137':ROOT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
        'probe148':ROOT/'firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT'}
    if scenario in dats:
        files.paths['/ATA1/GXRCE.DAT']=dats[scenario].read_bytes()
    elif scenario in ('ctl','ctl-bad'):
        raw=bytearray((ROOT/'firmware/package_v39_g151/local/disable/GXRCE.CTL').read_bytes())
        if scenario=='ctl-bad':raw[-1]^=1
        files.paths['/ATA1/GXRCE.CTL']=bytes(raw)
    elif scenario=='no-card':
        files.paths.pop('/ATA1/GXRCE.DAT',None)
        files.paths['/IROM/GXRCE0.DAT']=dats['g139'].read_bytes()
        files.present=False
    else:assert scenario=='release'
    calls={'rv_engine':0,'rv_invoke':0}
    handshakes=[]
    for label in calls:
        address=cam.h.symbols[label]
        def observe(b,label=label):
            calls[label]+=1
            if label=='rv_engine' and cam.h.u(H.R+5,1)==2:
                reply=b.core.r[3]
                record=dict(state_before=2,flags_before=cam.h.u(H.R+212))
                handshakes.append(record)
                active=[True]
                def returned(current):
                    if active[0]:
                        active[0]=False
                        record.update(state_after=cam.h.u(H.R+5,1),flags_after=cam.h.u(H.R+212),
                            status=cam.h.u(reply+4),actual=cam.h.u(reply+12),
                            capabilities=cam.h.u(reply+24),detail=cam.h.u(reply+28))
                    return False
                cam.h.b.add_breakpoint(b.core.r[14],returned)
            return False
        cam.h.b.add_breakpoint(address,observe)
    reads=[]
    original_read=files.read
    def read_file(fd,buf,n,h):
        current=files.live.get(fd)
        entry=dict(path=current[0] if current else None,requested=n)
        entry['returned']=original_read(fd,buf,n,h)
        reads.append(entry)
        return entry['returned']
    files.read=read_file
    cam.h.parent()
    opened,_,error=cam.m.fr.publish(cam.h,cam.p,cam.w)
    assert opened['ok'] and error is None,(opened,error)
    state=cam.h.u(H.R+5,1);flags=cam.h.u(H.R+212)
    rows=cam.h.u(0x2022f5ac,1);names=cam.h.u(0x2022f5a8)
    positive=(scenario in ('release','ctl-bad') or version=='new' and scenario in ('g151','g151-test'))
    if positive:
        assert state==3 and rows==8 and flags&128,(state,rows,flags)
        if version!='v38':
            assert len(handshakes)==1,handshakes
            h=handshakes[0]
            assert h['state_after']==2 and not(h['flags_before']&128 or h['flags_after']&128),h
            assert h['status']==0 and h['actual']==40 and h['detail']==0x49 and h['capabilities']&(1<<20),h
    else:
        assert state==6 and rows==7 and names==0x2022d610,(state,rows,hex(names))
        assert flags&1 and not flags&128,flags
        if scenario!='ctl':
            assert calls=={'rv_engine':0,'rv_invoke':0},calls
            assert cam.h.u(H.R+56)==0 and cam.h.u(H.R+112)==0
            assert all(r['requested']<=256 for r in reads),reads
    raw=files.paths.get('/ATA1/GXRCE.DAT')
    return dict(status='PASS',unit=unit,case=name,backend=backend,body_sha256=H.sha(H.BODY),
        dat_sha256=hashlib.sha256(raw).hexdigest() if raw else None,positive=positive,
        root_state=state,flags=flags,rows=rows,names=hex(names),dat_calls=calls,
        handshake=handshakes,reads=reads,files_opened=files.log,native_return=opened,
        heap_capacity=cam.h.u(0x200c0dc4),main_request=cam.h.u(H.R+104))


def main():
    kind,unit=sys.argv[1:3]
    case=sys.argv[3] if len(sys.argv)>3 else ''
    safe=('-'.join((kind,unit,case))).replace(':','-')
    assert safe.replace('-','').isalnum()
    job=TMP/f'{safe}-p{os.getpid()}'
    job.mkdir(parents=True,exist_ok=False)
    H.TMP=job;H.LOCAL=job/'model'
    os.environ.update(TMPDIR=str(job),CLANG_MODULE_CACHE_PATH=str(job/'modules'),PYTHONDONTWRITEBYTECODE='1')
    signal.alarm(7200)
    started=time.monotonic()
    if kind=='route':
        result=route(unit,case)
    elif kind in ('dat','rotate'):
        if kind=='rotate':
            H.PACKAGE=ROOT/'research/body_v39/local/fntest-package-g151/local/SD_ROOT'
            H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
            H.ENGINE=ROOT/'firmware/engine_v59_g151/variants/fn-test/candidate/local/full-r13/engine.elf'
            assert H.sha(H.DAT)=='a2e5df429f9fa69c6a752f75f79a6c62f3a2ff56baf1ea8b3ab38f8f8facf8a3'
            # The Fn package intentionally contains only the files used by the host model.
        module=load(TESTS/('dat_body.py' if kind=='dat' else 'dat_rotate.py'),'review_case')
        module.OUT=OUT
        original=H.Camera.__init__
        backends=[]
        def initialize(self,*args,**kwargs):
            original(self,*args,**kwargs);backends.append(check_backend(self))
        H.Camera.__init__=initialize
        sys.argv=[str(TESTS/('dat_body.py' if kind=='dat' else 'dat_rotate.py')),unit]
        if kind=='dat':sys.argv.append(case or 'ABCDH')
        module.main()
        result=dict(status='PASS',kind=kind,unit=unit,parts=case,backends=backends)
    else:
        assert kind=='lock'
        H.PACKAGE=ROOT/'firmware/package_v39_g151_test/local/SD_ROOT'
        H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
        H.setup()
        sys.modules['g139_host']=H
        location=ROOT/'research/body_v39/g151check'
        sys.path.insert(0,str(location));sys.path.insert(0,str(location/'tests'))
        module=load(location/'g150_checks.py','review_g150_checks')
        module.I.ROOT=ROOT;module.I.TMP=job
        cam,details=module.CASES[case](unit)
        result=dict(status='PASS_M32R',unit=unit,case=case,backend=check_backend(cam),
            body_sha256=H.sha(H.BODY),dat_sha256=H.sha(H.DAT),details=details)
    result['seconds']=round(time.monotonic()-started,3)
    result.update(temporary_directory=str(job),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),
        runner_sha256=SCRIPT_SHA,engine_elf_sha256=H.sha(H.ENGINE),resident_elf_sha256=H.sha(H.RESIDENT))
    (OUT/f'{safe}.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps(result,default=str),flush=True)


if __name__=='__main__':
    main()
