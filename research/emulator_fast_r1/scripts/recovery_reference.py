"""Continuous unmodified batch-model recovery, split into bounded CPU.run calls."""
import argparse,json,os,pickle,sys,time,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable();import bootstrap


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True);p.add_argument('--budget',type=int,default=2000000000)
    a=p.parse_args();target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    began=time.perf_counter();ctx=bootstrap.construct('batch','recovery',a.name)
    m=ctx.machine;c=m.cpu
    from recovery_long import terminal_hook
    from snapshots import fingerprint,arch_state,sha
    terminal_hook(m)
    phase=dict(confirmed=False,keys_done=False,presses=[]);ctx.controls['recovery']=phase
    result=dict(name=a.name,impl='unmodified-batch',segments=[],inputs=ctx.inputs.captured,
                library_sha256=sha(ctx.tool/'build/libgxr_m32r.dylib'),load_before=os.getloadavg(),complete=False)
    stopped=None
    def run(n):
        nonlocal stopped
        start=c.steps;t=time.perf_counter();stop=c.run(n)
        row=dict(start=start,end=c.steps,seconds=time.perf_counter()-t,stop=stop.to_dict(),load=os.getloadavg())
        result['segments'].append(row);print(json.dumps(dict(name=a.name,**row)),flush=True)
        if stop.reason!='max_steps':stopped=stop
    try:
        run(65975242);assert not stopped and c.get_reg('pc')==0x2036c9e4
        phase['confirmed']=True;result['confirmation']=fingerprint(m,ctx.controls)
        m.panel.set_key('UP',False)
        for key in ('DOWN','OK'):
            for pressed,budget in ((True,400000),(False,700000)):
                m.panel.set_key(key,pressed);run(budget)
                phase['presses'].append(dict(key=key,pressed=pressed,step=c.steps))
                assert not stopped
        phase['keys_done']=True
        while c.steps<a.budget and not stopped:
            run(min(50000000,a.budget-c.steps))
            result['steps']=c.steps;result['seconds']=time.perf_counter()-began
            target.write_text(json.dumps(result,indent=2)+'\n')
        result.update(steps=c.steps,seconds=time.perf_counter()-began,stop=stopped.to_dict() if stopped else dict(reason='budget'),
                      terminal=bool(stopped),status='model-terminal' if stopped else 'budget-without-completion',
                      fingerprint=fingerprint(m,ctx.controls),signed_r0=(c.get_reg('r0')+2**31)%2**32-2**31,
                      ui_initializers=m.observer.ui_initializers,sd_counts=dict(m.sd.counts),sd_events=list(m.sd.events),phase=phase)
        record=dict(cpu=c.snapshot(),architecture=arch_state(c),observer={k:v for k,v in vars(m.observer).items() if k!='cpu'},
                    events=m.events,pending_returns=m.pending_returns,return_hooks=getattr(m,'return_hooks',set()),
                    panel={k:v for k,v in vars(m.panel).items() if k not in ('cpu','devices')},controls=ctx.controls)
        artifact=HERE/'local'/(a.name+'-terminal-state.pkl.z');artifact.write_bytes(zlib.compress(pickle.dumps(record,protocol=4),3))
        result['terminal_state_sha256']=sha(artifact)
        nand=HERE/'local'/(a.name+'-nand.json');nand.write_text(json.dumps({str(k):bytes(v).hex() for k,v in sorted(m.devices['nand'].pages.items())})+'\n')
        result['nand_sha256']=sha(nand);result['load_after']=os.getloadavg();result['wall_seconds']=time.perf_counter()-began
    finally:
        target.write_text(json.dumps(result,indent=2)+'\n');m.close()


if __name__=='__main__':main()
