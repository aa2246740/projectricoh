"""Bounded independent menu/recovery segments with same-backend snapshots."""
import argparse
import json
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
    p.add_argument('--resume',type=Path)
    p.add_argument('--span',type=int,default=100000000)
    a=p.parse_args()
    assert 0<a.span<=120000000
    R.setup(a.backend,FIXES)
    signal.alarm(1700)
    import snapshots as S
    ctx=R.construct('boot-menu' if a.kind=='menu' else 'recovery',a.name)
    m,c=ctx.machine,ctx.machine.cpu
    body=R.ROOT/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3'
    if a.kind=='recovery':
        R.load_body(m,body)
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
    phase={'confirmation':False,'key_index':0,'recovery_target':None,'menu_seen':False}
    ctx.controls['review_phase']=phase
    ctx.inputs=S.Inputs(**dict(ctx.inputs.values,body=body,flow=Path(__file__),
        configuration='segmented-four-fixes-'+a.kind,serial_boot_input=list(m.devices['serial'].input_bytes[0])))
    del ctx.identity_bound
    ctx.identity_bound=S.identity(ctx)
    target=R.RUNS/(a.name+'.json')
    assert not target.exists()
    rec={'backend':a.backend,'kind':a.kind,'inputs':ctx.inputs.captured,'points':{},'rows':[],
         'fixes':FIXES,'status':'RUNNING'}
    if a.resume:
        rec['restored']=S.restore(ctx,a.resume)
        phase=ctx.controls['review_phase']
    start=c.steps
    end=start+a.span
    def u(address,size=4):
        return int.from_bytes(c.read(address,size),'big')
    def observe(label,stop=None,seconds=0):
        row={'label':label,'steps':c.steps,'pc':hex(c.get_reg('pc')),'state':u(0x205d9c00),
             'activity':u(0x205d9bf8),'rows':u(0x2022f5ac,1),'cursor':u(0x2022f726,1),
             'root_state':u(0x20054705,1),'root_inflight':u(0x20054706,1),
             'root_bytes':c.read(0x20054700,256).hex(),'seconds':seconds,
             'stop':stop.to_dict() if stop else None}
        rec['rows'].append(row)
        rec['points'][label]=R.fingerprint(ctx)
        target.write_text(json.dumps(rec,indent=2)+'\n')
        print(json.dumps({k:v for k,v in row.items() if k!='root_bytes'}),flush=True)
        return row
    def run(label,n):
        t=time.perf_counter()
        stop=c.run(n)
        c.materialize_native()
        row=observe(label,stop,time.perf_counter()-t)
        if stop.reason!='max_steps':
            raise RuntimeError(str(stop.to_dict()))
        return row
    try:
        observe('segment-start')
        cold_end=203000021 if a.kind=='menu' else 71387224
        points=(1000003,35000017,51000019,100000000,203000021) if a.kind=='menu' else (1000003,17000011,49000019,71387224)
        for point in points:
            if c.steps<point<=min(end,cold_end):
                run(str(point),point-c.steps)
        if c.steps<min(end,cold_end):
            run(str(min(end,cold_end)),min(end,cold_end)-c.steps)
        if c.steps>=cold_end:
            if a.kind=='recovery' and not phase['confirmation']:
                assert c.get_reg('pc')==0x2036c9e4,hex(c.get_reg('pc'))
                phase['confirmation']=True
                m.panel.set_key('UP',False)
            keys=('ADJ','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT') if a.kind=='menu' else ('DOWN','OK')
            quiet=12000007 if a.kind=='menu' else 1000003
            while phase['key_index']<len(keys) and c.steps+400003+quiet<=end:
                index=phase['key_index']
                key=keys[index]
                m.panel.set_key(key,True)
                run(str(index)+'-'+key+'-press',400003)
                m.panel.set_key(key,False)
                row=run(str(index)+'-'+key+'-release',quiet)
                phase['key_index']+=1
                if a.kind=='menu' and row['activity']==8 and row['rows']==8 and row['root_state']==3:
                    phase['menu_seen']=True
                    break
            if a.kind=='recovery' and phase['key_index']==len(keys):
                if phase['recovery_target'] is None:
                    phase['recovery_target']=c.steps+20000019
                while c.steps<min(end,phase['recovery_target']):
                    n=min(10000000,min(end,phase['recovery_target'])-c.steps)
                    run(str(c.steps+n),n)
            elif a.kind=='menu' and phase['key_index']==len(keys) and not phase['menu_seen']:
                while c.steps<end:
                    row=run(str(c.steps+min(10000000,end-c.steps)),min(10000000,end-c.steps))
                    if row['activity']==8 and row['rows']==8 and row['root_state']==3:
                        phase['menu_seen']=True
                        break
                    if row['root_state']==6:
                        rec['model_menu_declined']=True
                        break
        rec['complete']=bool(phase['menu_seen']) if a.kind=='menu' else bool(phase['recovery_target'] and c.steps>=phase['recovery_target'])
        rec['phase']=phase
        rec['snapshot']=S.save(ctx,R.HERE/(a.name+'.snap.z'))
        rec['final']=R.fingerprint(ctx)
        rec['sd_counts']=dict(m.sd.counts)
        rec['sd_events']=list(m.sd.events)
        rec['ui_initializers']=m.observer.ui_initializers
        rec['status']='COMPLETE' if rec['complete'] else 'SEGMENT_COMPLETE'
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
