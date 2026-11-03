"""Check the latch after the model reports a row-write failure."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]

def run(session,output):
    layout=json.loads((ROOT/'research/review_g129/local/focus-layout/review_g126/local/layout/layout.json').read_text())
    session_layout=json.loads((ROOT/'research/g129_knobs/adapter-layout.json').read_text())
    original=session.p.rpc.call;counts={'failed_write':0}
    def call(command,value):
        result=original(command,value)
        if command==22:
            counts['failed_write']+=1
            return -1
        return result
    session.p.rpc.call=call
    session.press('DOWN')
    g=session.p.symbol_pc('g');n=session.p.symbol_pc('n');h=session.h
    flags={key:h.u(g+layout[key],1) for key in ('uncertain','write_started','ready','busy')}
    flags['failed']=h.u(n+session_layout['failed'],1)
    result={'unit':session.unit,'counts':counts,'flags':flags,'status':'PASS' if counts['failed_write'] and flags['uncertain']==1 and flags['write_started']==1 and flags['failed']==1 else 'FAIL'}
    Path(output,'write-failure-'+session.unit+'.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['status']=='PASS'
