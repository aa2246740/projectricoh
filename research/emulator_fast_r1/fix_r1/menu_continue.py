"""Continue independently generated checkpoints into first Image Settings."""
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
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--name',required=True)
    a=p.parse_args()
    R.setup(a.backend)
    signal.alarm(1700)
    import snapshots as S
    ctx=R.construct('boot-menu',a.name)
    m,c=ctx.machine,ctx.machine.cpu
    restored=S.restore(ctx,a.snapshot)
    def official(address,size):
        at=m.image.offset(address,size)
        assert at is not None
        return m.image.raw[at:at+size]
    codes=struct.unpack('>72I',official(0x200c5e78,288))
    proof=[]
    for name,code in (('ADJ_LEFT',27),('ADJ_RIGHT',26)):
        index=codes.index(code)
        words=struct.unpack('>10I',official(0x200c5338+40*index,40))
        assert index in (32,33)
        record={'index':index,'code':code,'active':words[6],'pin':words[2],'kind':words[1],
                'row':(index-32)//5,'column_mask':words[3]>>24}
        m.panel.records[name]=record
        proof.append({'name':name,**record})
    target=R.RUNS/(a.name+'.json')
    assert not target.exists()
    rec={'backend':a.backend,'restored':restored,'points':{},'rows':[],'hid_proof':proof,'status':'RUNNING'}
    def u(address,size=4):
        return int.from_bytes(c.read(address,size),'big')
    def observe(label):
        row={'label':label,'steps':c.steps,'pc':hex(c.get_reg('pc')),'state':u(0x205d9c00),
             'activity':u(0x205d9bf8),'rows':u(0x2022f5ac,1),'cursor':u(0x2022f726,1),
             'root':u(0x20054705,1),'busy':u(0x20054706,1),'code_entry':hex(u(0x20054770))}
        rec['rows'].append(row)
        rec['points'][label]=R.fingerprint(ctx)
        target.write_text(json.dumps(rec,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        return row
    def run(label,n):
        stop=c.run(n)
        c.materialize_native()
        rec['last_stop']=stop.to_dict()
        row=observe(label)
        if stop.reason!='max_steps':
            raise RuntimeError(str(stop.to_dict()))
        return row
    try:
        observe('start')
        for index,key in enumerate(('HALF','ADJ','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT','ADJ_RIGHT')):
            m.panel.set_key(key,True)
            run(str(index)+'-'+key+'-press',400003)
            m.panel.set_key(key,False)
            row=run(str(index)+'-'+key+'-release',12000007)
            if row['activity']==8 and row['rows']==8:
                rec['menu_open']=True
                break
        else:
            rec['menu_open']=False
        if rec['menu_open']:
            run('first-menu-settle',10000019)
        rec['snapshot']=S.save(ctx,R.HERE/(a.name+'.snap.z'))
        rec['status']='COMPLETE'
    except BaseException as exc:
        rec['status']='ERROR'
        rec['error']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        if c._native_driver:
            rec['native']=c._native_driver.stats()
        rec['sd_counts']=dict(m.sd.counts)
        target.write_text(json.dumps(rec,indent=2)+'\n')
        m.close()
        signal.alarm(0)


if __name__=='__main__':
    main()
