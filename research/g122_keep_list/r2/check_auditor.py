"""Check actual record types and reject changed pages, ranges and edge bytes."""
from pathlib import Path
import copy
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit_records as audit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import OUT,DAT,save,sha

checks=[]
def rejected(name,fn):
    try:fn()
    except AssertionError as error:
        checks.append(dict(check=name,status='PASS',rejected=str(error)))
    else:raise AssertionError(('Expected review failure',name))

raw=DAT.read_bytes()
for i,unit in enumerate(audit.UNITS):
    matrix=json.loads((OUT/('native/matrix-'+unit+'.json')).read_text())
    events=matrix['cold_failure']['simulation']['events']
    assert audit.record_type(events,'/cold_failure/simulation/events')=='failure_events'
    mapping=audit.maps(raw,i)
    opened=json.loads((OUT/('open-counts-122-'+unit+'.json')).read_text())
    stream=opened['steps'][1]['rpc_log']
    assert audit.record_type(stream,'/steps/1/rpc_log')=='rpc_log'
    audit.check_log(stream,mapping)
    audit.sentinel_logs(OUT/('open-counts-122-'+unit+'.json'),mapping,sha(raw))
    checks.append(dict(check='actual summary, complete stream and contained sentinels',unit=unit,status='PASS'))
    rejected(unit+' sparse summary cannot replace rpc_log',lambda:audit.record_type(events,'/rpc_log'))
    changed=copy.deepcopy(stream);changed[0]['value']=65535
    rejected(unit+' page outside mapping',lambda:audit.check_log(changed,mapping))
    rows,t=mapping
    base=rows[0][0];page=base>>16
    outside=next(n for n in range(0,65536,2) if not any((a&~1)<=(page<<16|n) and (page<<16|n)+2<=((a+s+1)&~1) for a,s in rows))
    bad=[dict(cmd=23,value=page,page=page,result=page,t=2),dict(cmd=21,value=outside,page=page,result=0,t=2)]
    rejected(unit+' row access outside mapping',lambda:audit.check_log(bad,mapping))

mapping=([(0x10001,3)],(0x12c0,0))
stream=[dict(cmd=23,value=1,page=1,result=1,t=2),dict(cmd=21,value=0,page=1,result=0xabcd,t=2),
        dict(cmd=22,value=0xab12,page=1,result=0xab12,t=2)]
audit.check_log(stream,mapping)
changed=copy.deepcopy(stream);changed[-1]['value']=0x3412
rejected('leading adjacent byte changed',lambda:audit.check_log(changed,mapping))
mapping=([(0x10000,3)],(0x12c0,0))
stream=[dict(cmd=23,value=1,page=1,result=1,t=2),dict(cmd=21,value=2,page=1,result=0xabcd,t=2),
        dict(cmd=22,value=0x12cd,page=1,result=0x12cd,t=2)]
audit.check_log(stream,mapping)
changed=copy.deepcopy(stream);changed[-1]['value']=0x1234
rejected('trailing adjacent byte changed',lambda:audit.check_log(changed,mapping))
save('r2/auditor-checks.json',dict(status='PASS',dat_sha256=sha(raw),auditor_sha256=sha(Path(audit.__file__).read_bytes()),checks=checks))
print('PASS record review checks',len(checks),flush=True)
