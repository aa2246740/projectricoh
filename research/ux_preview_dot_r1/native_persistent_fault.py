"""Expose the boundary: a unit that stops answering cannot be compensated."""
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import native_ux as ux

def main():
    dat,elf=ux.configure(False,'50mm-persistent-fault')
    r=dict(unit='50mm',dat_sha256=ux.m.sha(dat.read_bytes()),engine_elf_sha256=ux.m.sha(elf.read_bytes()))
    try:
        h,p,w=ux.m.boot('50mm');ins=ux.instrument(h,p)
        ux.m.published(h,p,w);ux.arm_entries(h,p,ins)
        original=p.rpc.call;calls=0
        def failed(cmd,value):
            nonlocal calls
            calls+=1
            if calls==16:
                original(cmd,value)
                p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,injected=True)
                return -1
            if calls>16:
                p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,injected=True))
                return -1
            return original(cmd,value)
        p.rpc.call=failed
        r['move']=ux.measure_move(h,p,0x20,ins)
        r['rpc_calls']=calls;r['state']=ux.snap(h,p)
        assert r['state']['list']['uncertain']==1
        try:ux.matches(h,p,4)
        except AssertionError as error:r['not_complete04']=str(error)
        else:raise AssertionError('Expected the persistent transport outage to prevent full compensation')
        assert not any(ux.m.no_writes(p).values())
        r['file_mutations']=ux.m.no_writes(p);r['rpc_log']=p.rpc.log
        r['status']='EXPECTED_LIMITATION'
        r['finding']='Finite compensation cannot restore complete rows while all subsequent RPC calls fail; reboot is required.'
        print('CONFIRMED LIMITATION: persistent RPC outage leaves uncertain partial rows; no file writes',flush=True)
    except Exception:
        r['status']='TEST_ERROR';r['error']=traceback.format_exc()
        ux.save('persistent-fault-50mm.json',r);raise
    ux.save('persistent-fault-50mm.json',r)

if __name__=='__main__':main()
