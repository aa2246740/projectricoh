"""Re-enter Image Settings after asynchronous DAT publication has completed."""
import argparse
import json
from pathlib import Path
import signal
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend',choices=('native','reference'),required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--snapshot',type=Path,required=True)
    a=p.parse_args()
    R.setup(a.backend,'nand-word,preview-link,sd-long-response,nand-read-tail')
    signal.alarm(1700)
    import snapshots as S
    ctx=R.construct('boot-menu',a.name)
    m,c=ctx.machine,ctx.machine.cpu
    def official(address,size):
        at=m.image.offset(address,size)
        assert at is not None
        return m.image.raw[at:at+size]
    codes=struct.unpack('>72I',official(0x200c5e78,288))
    for name,code in (('ADJ_LEFT',27),('ADJ_RIGHT',26)):
        index=codes.index(code)
        words=struct.unpack('>10I',official(0x200c5338+40*index,40))
        m.panel.records[name]={'index':index,'code':code,'active':words[6],'pin':words[2],
            'kind':words[1],'row':(index-32)//5,'column_mask':words[3]>>24}
    ctx.controls['review_phase']={'confirmation':False,'key_index':0,'recovery_target':None,'menu_seen':False}
    values=dict(ctx.inputs.values,flow=R.HERE/'segmented_scenarios.py',
                configuration='segmented-four-fixes-menu',serial_boot_input=[2,0])
    ctx.inputs=S.Inputs(**values)
    del ctx.identity_bound
    ctx.identity_bound=S.identity(ctx)
    restored=S.restore(ctx,a.snapshot)
    ctx.inputs=S.Inputs(**dict(values,flow=Path(__file__),source_checkpoint=a.snapshot,
                              configuration='published-DAT-first-render'))
    del ctx.identity_bound
    ctx.identity_bound=S.identity(ctx)
    out=R.RUNS/(a.name+'.json')
    assert not out.exists()
    result={'backend':a.backend,'restored':restored,'points':{},'rows':[],'status':'RUNNING'}
    def u(address,size=4):
        return int.from_bytes(c.read(address,size),'big')
    def point(label,n=0):
        stop=c.run(n) if n else None
        c.materialize_native()
        row={'label':label,'steps':c.steps,'state':u(0x205d9c00),'activity':u(0x205d9bf8),
             'rows':u(0x2022f5ac,1),'root_state':u(0x20054705,1),'root_inflight':u(0x20054706,1),
             'entry':hex(u(0x20054770)),'pc':hex(c.get_reg('pc')),'stop':stop.to_dict() if stop else None}
        result['rows'].append(row)
        result['points'][label]=R.fingerprint(ctx)
        out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        if stop and stop.reason!='max_steps':
            raise RuntimeError(str(stop.to_dict()))
        return row
    try:
        assert u(0x20054705,1)==3,'DAT has not been published'
        point('start')
        result['menu_open']=False
        for index,key in enumerate(('HALF','ADJ','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT')):
            m.panel.set_key(key,True)
            point(str(index)+'-'+key+'-press',400003)
            m.panel.set_key(key,False)
            row=point(str(index)+'-'+key+'-release',12000007)
            if row['activity']==8 and row['rows']==8 and row['root_state']==3:
                result['menu_open']=True
                break
        result['snapshot']=S.save(ctx,R.HERE/(a.name+'.snap.z'))
        result['final']=R.fingerprint(ctx)
        result['status']='COMPLETE' if result['menu_open'] else 'MENU_NOT_OPEN'
    except BaseException as exc:
        result['status']='ERROR'
        result['error']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        if c._native_driver:
            result['native']=c._native_driver.stats()
        out.write_text(json.dumps(result,indent=2)+'\n')
        m.close()
        signal.alarm(0)


if __name__=='__main__':
    main()
