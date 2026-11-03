#!/usr/bin/python3
"""Check DAT identity on the packaged body in the native host model."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', choices=('50mm','28mm','mount'), required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--timeout', type=int, default=10800)
    parser.add_argument('--case',action='append')
    args = parser.parse_args()
    assert Path(os.environ['TMPDIR']).resolve() == TEMP
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    backend = os.environ.get('GXR_HARNESS_BACKEND','c')
    path = ROOT/'research/g155/native_support.py'
    source = path.read_text().replace('g155-boot-r1','v310-body-pack-r1')
    module = types.ModuleType('native_support')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    sys.path.insert(0,str(path.parent))
    exec(compile(source,str(path),'exec'),module.__dict__)
    N,H = module,module.H
    N.OVERLAY = False
    newbody = ROOT/'firmware/image_v310/local/ilaunch3'
    oldbody = ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3'
    newres = ROOT/'firmware/resident_v310_g155/local/resident/resident.elf'
    oldres = ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf'
    newengine = ROOT/'firmware/engine_v64_g155/candidate/local'
    release = ROOT/'firmware/package_v310_g155/local/SD_ROOT/GXRCE.DAT'
    test = ROOT/'firmware/package_v310_g155_test/local/SD_ROOT/GXRCE.DAT'
    cases = [
        ('v310-release',True,newbody,newres,release,newengine/'boot-off/engine.elf'),
        ('v310-test',True,newbody,newres,test,newengine/'boot-on/engine.elf'),
        ('v39-release',False,oldbody,oldres,release,newengine/'boot-off/engine.elf'),
        ('v39-test',False,oldbody,oldres,test,newengine/'boot-on/engine.elf'),
        ('v310-g154',False,newbody,newres,ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT',ROOT/'firmware/engine_v63_g154/candidate/local/full-r13/engine.elf'),
        ('v310-g153',False,newbody,newres,ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT',ROOT/'firmware/engine_v62_g153/candidate/local/full-r13/engine.elf'),
        ('v310-diagv4p',False,newbody,newres,ROOT/'firmware/package_v39_diagv4p/GXRCE.DAT',ROOT/'firmware/engine_v61_diagv4p/build/engine.elf')]
    if args.case:
        cases=[row for row in cases if row[0] in args.case]
        assert len(cases)==len(args.case)
    rows = []
    target = HERE/'evidence'/f'{args.name}.json'
    assert not target.exists()
    started = time.monotonic()
    signal.alarm(args.timeout)
    try:
        for name,accepted,body,resident,dat,engine in cases:
            H.BODY,H.RESIDENT,H.DAT,H.PACKAGE,H.ENGINE = body,resident,dat,dat.parent,engine
            H.BODY_SHA = sha(body.read_bytes())
            cam = N.Camera(args.unit)
            before = (cam.s_bytes(0,4096),copy.deepcopy((cam.p.rpc.overlay,cam.p.rpc.t)),cam.writes())
            # Verify the actual body instructions, without replacing resident RAM.
            rawbody = body.read_bytes()
            for i in range(16):
                import struct
                off,base,size,_,_ = struct.unpack_from('>5I',rawbody,0x20+20*i)
                if base<=0x2005276c and 0x20054800<=base+size:
                    start=off+0x200+0x2005276c-base
                    assert cam.h.b.read(0x2005276c,8340)==rawbody[start:start+8340]
            entries=[]
            raw=dat.read_bytes()
            codeoff=int.from_bytes(raw[132:136],'big')
            entryoff=int.from_bytes(raw[112:116],'big')
            def ready(event):
                code=cam.h.u(0x20054770)
                if 0x20000000<=code<0x21000000:
                    cam.h.b.add_breakpoint(code+entryoff-codeoff,lambda b:entries.append(True) or False)
            cam.h.b.add_write_trace(0x20054770,0x20054774,ready)
            cam.h.parent()
            result=cam.m.fr.native(cam.h,0x20287080,steps=30000000)
            state=cam.h.u(0x20054705,1)
            row=dict(case=name,unit=args.unit,body_sha256=H.BODY_SHA,dat_sha256=sha(raw),
                     native_return=result,root_state=state,bootstrap_entries=entries,
                     rows=cam.h.u(0x2022f5ac,1),resident_ram_replaced=False,
                     expected_accept=accepted)
            try:
                assert result['ok'],result
                if accepted:
                    assert state==3 and entries and row['rows']==8,row
                else:
                    assert state==6 and not entries and row['rows']==7,row
                    assert cam.s_bytes(0,4096)==before[0]
                    assert (cam.p.rpc.overlay,cam.p.rpc.t)==before[1] and cam.writes()==before[2]
                row['status']='PASS'
            except AssertionError as exc:
                row.update(status='FAIL',error=str(exc))
            rows.append(row)
            print(json.dumps(row),flush=True)
            target.write_text(json.dumps(dict(layer='host model',backend=backend,
                fixture='Existing native host startup fixture; not a MAIN cold run.',
                source_sha256=sha(path.read_bytes()),cases=rows,
                seconds=time.monotonic()-started),indent=2)+'\n')
        if any(row['status']!='PASS' for row in rows):
            raise SystemExit(1)
    finally:
        signal.alarm(0)


if __name__=='__main__':
    main()
