"""Reject sparse RPC substitutes and corrupt page, range and edge records."""
from pathlib import Path
import copy,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,load
a=load(ROOT/'research/g122_keep_list/audit_records.py','g123_authoritative_rpc_auditor')
from common import OUT,DAT,save,sha
checks=[]
def reject(label,fn):
    try:fn()
    except AssertionError:checks.append(dict(check=label,status='PASS'))
    else:raise AssertionError(('Expected rejection',label))
raw=DAT.read_bytes()
for i,unit in enumerate(a.UNITS):
    document=json.loads((OUT/f'local/lock-cases/{unit}-write_latch.json').read_text())
    stream=document['rpc_log'];mapping=a.maps(raw,i)
    assert a.record_type(stream,'/rpc_log')=='rpc_log';a.check_log(stream,mapping)
    sparse=[dict(at=j,cmd=x['cmd'],value=x['value']) for j,x in enumerate(stream)]
    assert a.record_type(sparse,'/simulation/events')=='failure_events'
    reject(unit+' sparse events are not a full stream',lambda:a.record_type(sparse,'/rpc_log'))
    changed=copy.deepcopy(stream);changed[0]['value']=65535
    reject(unit+' page outside mapping',lambda:a.check_log(changed,mapping))
    rows,t=mapping;base=rows[0][0];page=base>>16
    outside=next(n for n in range(0,65536,2) if not any((b&~1)<=(page<<16|n) and (page<<16|n)+2<=((b+s+1)&~1) for b,s in rows))
    bad=[dict(cmd=23,value=page,page=page,result=page,t=2),dict(cmd=21,value=outside,page=page,result=0,t=2)]
    reject(unit+' V outside mapping',lambda:a.check_log(bad,mapping))
    bad[-1]['result']=-1
    reject(unit+' failed V outside mapping is still rejected',lambda:a.check_log(bad,mapping))
    checks.append(dict(check=unit+' complete recorded stream',status='PASS'))
for base,last,value in ((0x10001,3,0xab12),(0x10000,3,0x12cd)):
    index=0 if base&1 else 2;mapping=([(base,last)],(0x12c0,0))
    stream=[dict(cmd=23,value=1,page=1,result=1,t=2),dict(cmd=21,value=index,page=1,result=0xabcd,t=2),dict(cmd=22,value=value,page=1,result=value,t=2)]
    a.check_log(stream,mapping);stream[-1]['value']^=256 if base&1 else 1
    reject('adjacent byte preservation '+str(base&1),lambda:a.check_log(stream,mapping))
save('evidence/auditor-checks.json',dict(status='PASS',dat_sha256=sha(raw),checks=checks))
print('PASS RPC auditor checks',len(checks),flush=True)
