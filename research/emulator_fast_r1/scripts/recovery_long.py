"""One bounded recovery segment, with exact resumable machine state."""
import argparse,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable()
import bootstrap


def terminal_hook(machine):
    cpu=machine.cpu;address=0x2005ccf0;prior=cpu.breakpoints.get(address)
    def returned(current):
        previous=prior(current) if prior else False
        return bool(previous) or bool(current.get_reg('r0')&0x80000000)
    returned._gxr_native_ops=list(getattr(prior,'_gxr_native_ops',()))+[
        ('reg-stop',dict(register=0,mask=0x80000000,value=0x80000000))]
    cpu.add_breakpoint(address,returned)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--impl',choices=('fast','reference'),required=True);p.add_argument('--name',required=True)
    p.add_argument('--span',type=int,default=200000000);p.add_argument('--resume',type=Path)
    a=p.parse_args();assert 0<a.span<=250000000
    assert a.name.replace('-','').replace('_','').isalnum()
    target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    setup=time.perf_counter();ctx=bootstrap.construct(a.impl,'recovery',a.name)
    m=ctx.machine;c=m.cpu
    from snapshots import fingerprint,save,restore,sha
    terminal_hook(m);phase=dict(confirmed=False,keys_done=False,presses=[]);ctx.controls['recovery']=phase
    result=dict(name=a.name,impl=a.impl,segments=[],load_before=os.getloadavg(),inputs=ctx.inputs.captured,
                library_sha256=sha(c.library_path),nice=os.getpriority(os.PRIO_PROCESS,0),complete=False)
    if a.resume:result['resume']=restore(ctx,a.resume)
    phase=ctx.controls['recovery'];start=c.steps;end=start+a.span
    result['setup_seconds']=time.perf_counter()-setup
    began=time.perf_counter();stopped=None
    def run(n):
        nonlocal stopped
        before=c.steps;t=time.perf_counter();stop=c.run(n);c.materialize_native()
        row=dict(start=before,end=c.steps,seconds=time.perf_counter()-t,stop=stop.to_dict(),
                 pc=hex(c.get_reg('pc')),load=os.getloadavg())
        result['segments'].append(row);print(json.dumps(dict(name=a.name,**row)),flush=True)
        if stop.reason!='max_steps':stopped=stop
    try:
        if not phase['confirmed']:
            run(min(end,65975242)-c.steps)
            if c.steps==65975242 and not stopped:
                assert c.get_reg('pc')==0x2036c9e4
                phase['confirmed']=True
                result['confirmation']=dict(steps=c.steps,fingerprint=fingerprint(m,ctx.controls))
                result['confirmation_snapshot']=save(ctx,HERE/'local'/(a.name+'-confirm.snap.z'))
        if phase['confirmed'] and not phase['keys_done'] and not stopped and c.steps<end:
            m.panel.set_key('UP',False)
            for key in ('DOWN','OK'):
                for pressed,budget in ((True,400000),(False,700000)):
                    m.panel.set_key(key,pressed);run(budget)
                    phase['presses'].append(dict(key=key,pressed=pressed,step=c.steps))
                    if stopped:break
                if stopped:break
            phase['keys_done']=True
        while c.steps<end and not stopped:run(min(50000000,end-c.steps))
        result.update(steps=c.steps,pc=hex(c.get_reg('pc')),seconds=time.perf_counter()-began,
                      terminal=bool(stopped),stop=stopped.to_dict() if stopped else dict(reason='segment-budget'),
                      fingerprint=fingerprint(m,ctx.controls),signed_r0=(c.get_reg('r0')+2**31)%2**32-2**31,
                      ui_initializers=m.observer.ui_initializers,sd_counts=dict(m.sd.counts),
                      sd_events=list(m.sd.events),phase=phase)
        result['snapshot']=save(ctx,HERE/'local'/(a.name+'-end.snap.z'))
        nand=HERE/'local'/(a.name+'-nand.json')
        nand.write_text(json.dumps({str(k):bytes(v).hex() for k,v in sorted(m.devices['nand'].pages.items())})+'\n')
        result['nand_sha256']=sha(nand)
        if stopped:
            result['completion_basis']='native UI initializer returned a negative result' if c.get_reg('pc')==0x2005ccf0 and c.get_reg('r0')&0x80000000 else 'emulator stopped'
        else:result['completion_basis']='segment budget; continuation required'
        result['status']='model-terminal' if stopped else 'segment-complete'
    except BaseException as exc:
        result['status']='error';result['error']=dict(type=type(exc).__name__,message=str(exc),steps=c.steps)
        raise
    finally:
        driver=getattr(c,'_native_driver',None)
        if driver:result['native_machine']=driver.stats()
        result['batch_stats']=dict(c.batch_stats);result['load_after']=os.getloadavg()
        target.write_text(json.dumps(result,indent=2)+'\n');m.close()


if __name__=='__main__':main()
