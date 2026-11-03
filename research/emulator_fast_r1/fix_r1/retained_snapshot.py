"""Readonly snapshot collection must permit ordinary borrowed state."""
import argparse,json,signal,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
from edge_cases import loop


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    R.setup(a.backend);signal.alarm(120)
    import snapshots as S
    ctx=R.construct('main',a.name);c=loop(ctx)
    target=None
    try:
        held=ctx.machine.devices['gpio'].inputs
        assert c.run(7).reason=='max_steps'
        path=R.HERE/'acceptance/local'/(a.name+'.snap.z')
        saved=S.save(ctx,path)
        assert held is ctx.machine.devices['gpio'].inputs
        assert c.run(19).reason=='max_steps'
        expected=R.fingerprint(ctx)
        target=R.construct('main',a.name+'-restored')
        S.restore(target,path)
        assert target.machine.cpu.run(19).reason=='max_steps'
        assert expected==R.fingerprint(target)
        result=dict(status='PASS',backend=a.backend,borrowed_reference_preserved=True,snapshot=saved,state=expected)
        out=R.RUNS/(a.name+'.json');assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status='PASS',borrowed_reference_preserved=True,continued_steps=19)))
    finally:
        if target:target.machine.close()
        ctx.machine.close()


if __name__=='__main__':main()
