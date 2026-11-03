"""Check every captured owner of the recognized ready-hold wrapper."""
import argparse,json,signal,sys
from pathlib import Path
from types import FunctionType,MethodType
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
from edge_cases import loop


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',required=True);p.add_argument('--name',required=True)
    p.add_argument('--case',choices=('inner','peer','alias','genuine'),required=True);a=p.parse_args()
    R.setup(a.backend);signal.alarm(120)
    import standby_run
    ctx=R.construct('main',a.name);c=loop(ctx)
    try:
        board=ctx.machine.devices['board'];peer=ctx.machine.devices['startup'];held=[]
        board.enable_ready=True
        ctx.machine.devices['dma'].transmitted=[dict(data=bytes(2048)),dict(data=bytes(4608))]
        peer.hsp_replies=[bytes([0,0,11])+bytes(29)]
        original=board.advance
        def modified(self):original();self.mx_cursor+=1
        advance=MethodType(modified,board) if a.case=='inner' else original
        if a.case=='peer':
            from types import SimpleNamespace
            peer=SimpleNamespace(hsp_rx_queue=[])
        if a.case=='alias':held=peer.hsp_rx_queue
        ctx.controls['held_ready']=held
        code=next(v for v in standby_run.run.__code__.co_consts if getattr(v,'co_name',None)=='advance_with_hold')
        def cell(value):return (lambda:value).__closure__[0]
        values=dict(advance=advance,board=board,peer=peer,held_ready=held)
        board.advance=FunctionType(code,standby_run.__dict__,name='advance_with_hold',closure=tuple(cell(values[k]) for k in code.co_freevars))
        assert c.run(1).reason=='max_steps'
        result=dict(status='COMPLETE',case=a.case,detail=dict(cursor=board.mx_cursor,held_alias=held is ctx.machine.devices['startup'].hsp_rx_queue),
                    state=R.fingerprint(ctx),native=c._native_driver.stats() if c._native_driver else None)
        target=R.RUNS/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(case=a.case,detail=result['detail'],native=result['native']['instructions'] if result['native'] else 0)))
        if a.backend=='native':
            count=result['native']['instructions']
            assert count==(1 if a.case=='genuine' else 0),(a.case,count)
    finally:ctx.machine.close()


if __name__=='__main__':main()
