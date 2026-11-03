"""Inspect the complete setup reopen already recorded by final latch cases."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,load,file_sha,save

checker=load(ROOT/'research/g122_keep_list/audit_records.py','g123_final_open_count_auditor')
results=[]
for index,unit in enumerate(('50mm','28mm','mount')):
    path=OUT/f'local/lock-cases/{unit}-write_latch.json'
    d=json.loads(path.read_text());assert d['dat_sha256']==file_sha(DAT)
    before=d['selected']['rpc'];after=d['verified_reopen']['rpc']
    log=d['rpc_log'][before:after];rows,t=checker.maps(DAT.read_bytes(),index)
    expected=[(23,t[0]),(21,t[1])]
    for base,size in rows:
        page=base>>16;expected.append((23,page))
        for address in range(base&~1,(base+size+1)&~1,2):
            if address>>16!=page:page=address>>16;expected.append((23,page))
            expected.append((21,address&65535))
    assert [(x['cmd'],x['value']) for x in log]==expected
    assert len(log)==(265 if index==0 else 264) and not any(x['cmd']==22 for x in log)
    checker.check_log(log,(rows,t))
    save(f'local/final-normal-open-{unit}.json',dict(status='PASS',unit=unit,
        dat_sha256=file_sha(DAT),rpc_log=log,source=str(path.relative_to(OUT)),
        source_sha256=file_sha(path),range=[before,after]))
    results.append(dict(unit=unit,RPC=len(log),W=0,all_nine_rows_and_T=True))
save('evidence/final-normal-open.json',dict(status='PASS',dat_sha256=file_sha(DAT),steps=results,
    scope='Extraction from the final locked-case setup logs; no additional native run. Native settings do not use X/V/W.'))
print('PASS final artifact reopen streams',results)
