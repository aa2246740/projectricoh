"""Fresh g154 first-menu and four-revision recovery scenarios."""
import argparse
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R

FIXES='nand-word,preview-link,sd-long-response,nand-read-tail'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend',choices=('native','reference'),required=True)
    p.add_argument('--kind',choices=('menu','recovery'),required=True)
    p.add_argument('--name',required=True)
    a=p.parse_args()
    R.setup(a.backend,FIXES)
    signal.alarm(1700)
    import snapshots as S
    ctx=R.construct('boot-menu' if a.kind=='menu' else 'recovery',a.name)
    m,c=ctx.machine,ctx.machine.cpu
    body=R.ROOT/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3'
    if a.kind=='recovery':
        R.load_body(m,body)
        # Recovery retains the board's declared bit-1 high boot input.
        # The ordinary MAIN input is bit-1 low.
        m.devices['serial'].input_bytes[0]=(2,2)
    else:
        def official(address,size):
            at=m.image.offset(address,size)
            assert at is not None
            return m.image.raw[at:at+size]
        codes=struct.unpack('>72I',official(0x200c5e78,288))
        for name,code in (('ADJ_LEFT',27),('ADJ_RIGHT',26)):
            index=codes.index(code)
            words=struct.unpack('>10I',official(0x200c5338+40*index,40))
            assert index in (32,33)
            m.panel.records[name]={'index':index,'code':code,'active':words[6],'pin':words[2],
                                  'kind':words[1],'row':(index-32)//5,'column_mask':words[3]>>24}
    ctx.inputs=S.Inputs(**dict(ctx.inputs.values,body=body,flow=Path(__file__),
                               configuration='fresh-four-fixes-'+a.kind,
                               serial_boot_input=list(m.devices['serial'].input_bytes[0])))
    del ctx.identity_bound
    ctx.identity_bound=S.identity(ctx)
    target=R.RUNS/(a.name+'.json')
    assert not target.exists()
    rec={'backend':a.backend,'kind':a.kind,'fixes':FIXES,'points':{},'rows':[],
         'inputs':ctx.inputs.captured,'status':'RUNNING'}
    def u(address,size=4):
        return int.from_bytes(c.read(address,size),'big')
    def run(label,n):
        began=time.perf_counter()
        stop=c.run(n)
        c.materialize_native()
        row={'label':label,'steps':c.steps,'pc':hex(c.get_reg('pc')),'state':u(0x205d9c00),
             'activity':u(0x205d9bf8),'rows':u(0x2022f5ac,1),'cursor':u(0x2022f726,1),
             'root_word':c.read(0x20054700,16).hex(),'seconds':time.perf_counter()-began,
             'stop':stop.to_dict(),'load':os.getloadavg()}
        rec['rows'].append(row)
        rec['points'][label]=R.fingerprint(ctx)
        target.write_text(json.dumps(rec,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        if stop.reason!='max_steps':
            raise RuntimeError(str(stop.to_dict()))
        return row
    try:
        points=(1000003,35000017,51000019,203000021) if a.kind=='menu' else (1000003,17000011,49000019,65975242)
        for end in points:
            run(str(end),end-c.steps)
        if a.kind=='recovery':
            rec['confirmation_pc_match']=c.get_reg('pc')==0x2036c9e4
            if not rec['confirmation_pc_match']:
                raise RuntimeError('recovery confirmation checkpoint was not reached')
            m.panel.set_key('UP',False)
            for key in ('DOWN','OK'):
                m.panel.set_key(key,True)
                run(key+'-press',400003)
                m.panel.set_key(key,False)
                run(key+'-release',1000003)
            run('recovery-progress',20000019)
        else:
            rec['menu_open']=False
            for index,key in enumerate(('ADJ','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT')):
                m.panel.set_key(key,True)
                run(str(index)+'-'+key+'-press',400003)
                m.panel.set_key(key,False)
                row=run(str(index)+'-'+key+'-release',12000007)
                if row['activity']==8 and row['rows']==8:
                    rec['menu_open']=True
                    run('first-menu-settle',10000019)
                    break
            if not rec['menu_open']:
                raise RuntimeError('first Image Settings menu did not reach eight rows')
        rec['snapshot']=S.save(ctx,R.HERE/(a.name+'.snap.z'))
        rec['sd_counts']=dict(m.sd.counts)
        rec['sd_events']=list(m.sd.events)
        rec['ui_initializers']=m.observer.ui_initializers
        rec['status']='COMPLETE'
    except BaseException as exc:
        rec['status']='ERROR'
        rec['exception']={'type':type(exc).__name__,'message':str(exc),'steps':c.steps}
        raise
    finally:
        if c._native_driver:
            rec['native']=c._native_driver.stats()
        target.write_text(json.dumps(rec,indent=2)+'\n')
        m.close()
        signal.alarm(0)


if __name__=='__main__':
    main()
