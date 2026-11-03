"""Bounded, identical cold workloads with complete checkpoint fingerprints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import cProfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable()
import bootstrap


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--impl',choices=('fast','batch','reference'),required=True)
    p.add_argument('--kind',choices=('main','boot','recovery'),required=True)
    p.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    p.add_argument('--name',required=True)
    p.add_argument('--points')
    p.add_argument('--save',action='store_true')
    p.add_argument('--resume',type=Path)
    p.add_argument('--timeout',type=int,default=1700)
    p.add_argument('--profile',action='store_true')
    args=p.parse_args();signal.alarm(args.timeout)
    assert args.name.replace('-','').replace('_','').isalnum()
    target=HERE/'runs'/(args.name+'.json');assert not target.exists()
    setup=time.perf_counter();context=bootstrap.construct(args.impl,args.kind,args.name,args.unit)
    from snapshots import fingerprint,sha
    import snapshots
    m=context.machine;c=m.cpu
    result=dict(name=args.name,impl=args.impl,kind=args.kind,unit=args.unit,
                inputs=context.inputs.captured,library_sha256=sha(getattr(c,'library_path',context.tool/'build/libgxr_m32r.dylib')),
                nice=os.getpriority(os.PRIO_PROCESS,0),setup_seconds=time.perf_counter()-setup,segments=[],points={})
    if args.resume:
        restored=snapshots.restore(context,args.resume)
        result['resumed']=restored
    points=args.points or dict(main='1000000,50000000',boot='1000000,35537208,50000000,202997601',recovery='1000000,50000000,65975242')[args.kind]
    print(json.dumps(dict(name=args.name,pid=os.getpid(),ready=True)),flush=True)
    try:
        profile=cProfile.Profile() if args.profile else None
        for point in map(int,points.split(',')):
            start=c.steps;load=os.getloadavg();began=time.perf_counter();cpu_began=time.process_time()
            if profile:profile.enable()
            stop=c.run(point-start)
            if hasattr(c,'materialize_native'):c.materialize_native()
            if profile:profile.disable();profile.dump_stats(str(HERE/'runs'/(args.name+'.prof')))
            seconds=time.perf_counter()-began;cpu_seconds=time.process_time()-cpu_began
            segment=dict(start=start,end=c.steps,seconds=seconds,cpu_seconds=cpu_seconds,
                         load_before=load,load_after=os.getloadavg(),steps_per_second=(c.steps-start)/seconds,
                         stop=stop.to_dict(),pc=hex(c.get_reg('pc')),
                         state=int.from_bytes(c.read(0x205d9c00,4),'big'))
            result['segments'].append(segment)
            result['points'][str(point)]=fingerprint(m,context.controls)
            if args.save:
                result.setdefault('snapshots',{})[str(point)]=snapshots.save(context,HERE/'local'/(args.name+'-'+str(point)+'.snap.z'))
            if args.kind=='recovery' and c.steps==65975242:
                nand={str(k):bytes(v).hex() for k,v in sorted(m.devices['nand'].pages.items())}
                out=HERE/'local'/(args.name+'-confirm-nand.json');out.write_text(json.dumps(nand)+'\n')
                result['confirm_nand_sha256']=sha(out)
            print(json.dumps(dict(name=args.name,**segment)),flush=True)
            target.write_text(json.dumps(result,indent=2)+'\n')
            assert c.steps==point and stop.reason=='max_steps',stop.to_dict()
        result['status']='complete'
    except BaseException as exc:
        result['status']='error';result['error']=dict(type=type(exc).__name__,message=str(exc),steps=c.steps)
        raise
    finally:
        driver=getattr(c,'_native_driver',None)
        if driver:result['native_machine']=driver.stats()
        result['batch_stats']=dict(c.batch_stats)
        target.write_text(json.dumps(result,indent=2)+'\n');m.close()
    signal.alarm(0)


if __name__=='__main__':main()
