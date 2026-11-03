"""Extract complete normal re-open streams from the completed main matrix."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,DAT,save,file_sha,ROOT,load
checker=load(ROOT/'research/g122_keep_list/audit_records.py','g123_count_auditor')

def main():
    raw=DAT.read_bytes();results=[]
    for index,unit in enumerate(('50mm','28mm','mount')):
        path=OUT/'local/native'/('matrix-'+unit+'.json');doc=json.loads(path.read_text())
        assert doc['status']=='PASS' and doc['dat_sha256']==file_sha(DAT)
        streams=doc['rpc_sessions'];assert streams and streams[0]['unit']==unit
        full=streams[0]['rpc_log'];rows,t=checker.maps(raw,index)
        expected=[(23,t[0]),(21,t[1])]
        for base,size in rows:
            page=base>>16;expected.append((23,page))
            for address in range(base&~1,(base+size+1)&~1,2):
                if address>>16!=page:page=address>>16;expected.append((23,page))
                expected.append((21,address&65535))
        for name in ('adj','ok'):
            before=doc[name]['after']['rpc'];after=doc[name]['reopened']['rpc'];log=full[before:after]
            assert [(x['cmd'],x['value']) for x in log]==expected
            assert len(log)==(265 if index==0 else 264) and not any(x['cmd']==22 for x in log)
            checker.check_log(log,(rows,t))
            save('local/open-counts-123-'+unit+'-'+name+'.json',dict(status='PASS',unit=unit,
                dat_sha256=file_sha(DAT),operation='verified_reopen_after_'+name,RPC=len(log),W=0,rpc_log=log,
                source=str(path.relative_to(OUT)),source_sha256=file_sha(path),range=[before,after]))
            results.append(dict(unit=unit,operation=name,RPC=len(log),W=0,all_nine_rows_and_T=True))
    save('evidence/normal-open.json',dict(status='PASS',dat_sha256=file_sha(DAT),steps=results,
        scope='Expanded X/V calls from full native matrix session logs. Native settings verification runs in the validator but uses no X/V/W. No camera-time claim.'))
    print('PASS normal re-open full streams',results,flush=True)
if __name__=='__main__':main()
