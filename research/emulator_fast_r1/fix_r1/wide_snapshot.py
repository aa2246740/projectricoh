"""Transfer arbitrary integer state losslessly, then execute via reference models."""
import argparse,json,signal,sys
from pathlib import Path
from collections import deque
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
from edge_cases import loop


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    R.setup(a.backend);signal.alarm(120)
    import snapshots as S
    ctx=R.construct('main',a.name);c=loop(ctx);target=None
    try:
        ctx.machine.devices['timer'].counter=(1<<200)+113
        ctx.machine.devices['serial'].clock=(1<<90)+113
        ctx.machine.devices['irq'].pending=deque([65]*300)
        ctx.machine.observer.counts['large']=1<<140
        assert c.run(7).reason=='max_steps'
        path=R.HERE/'acceptance/local'/(a.name+'.snap.z');saved=S.save(ctx,path)
        assert c.run(19).reason=='max_steps';expected=R.fingerprint(ctx)
        target=R.construct('main',a.name+'-restored');S.restore(target,path)
        assert target.machine.cpu.run(19).reason=='max_steps'
        assert expected==R.fingerprint(target)
        stats=[x.machine.cpu._native_driver.stats() if x.machine.cpu._native_driver else None for x in (ctx,target)]
        assert all(row is None or row['instructions']==0 for row in stats)
        result=dict(status='PASS',state=expected,snapshot=saved,native=stats,backend=a.backend)
        out=R.RUNS/(a.name+'.json');assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status='PASS',bits=[200,90,140],pending=300)))
    finally:
        if target:target.machine.close()
        ctx.machine.close()


if __name__=='__main__':main()
