"""Independently compare the recorded P1 rows with literal final-DAT entries."""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import decode as D

def sha(data):return hashlib.sha256(data).hexdigest()
raw=(ROOT/'firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
modules=D.modules(raw)
out=[]
for unit,index,job in (('mount',2,'unverified-late-mount-irq'),('50mm',0,'unverified-late-50mm-irq')):
    path=HERE/'tests/local'/job/'checks'/(unit+'-unverified-late.json')
    result=json.loads(path.read_text());x=result['detail'];module=modules[index]
    def entry(slot):return module['entries'][module['refs'][slot-1]]
    def hashes(slot):
        e=entry(slot);table=module['map'];rows=[]
        for row in range(9):
            offset=int.from_bytes(table[38+12*row:40+12*row],'big')
            size=int.from_bytes(table[36+12*row:38+12*row],'big')
            rows.append(sha(e[offset:offset+size]))
        return rows
    assert result['status']=='OBSERVED_P1' and result['dat_sha256']==sha(raw)
    assert x['before']['row_sha256']==hashes(2)
    assert x['after']['row_sha256']==hashes(4)
    assert x['after']['row_sha256']!=hashes(2) and x['after']['row_sha256']!=hashes(5)
    assert x['before']['S_sha256']==x['after']['S_sha256'] and not x['S_stores']
    assert x['after']['W']-x['before']['W']==506 and x['after']['T']==x['before']['T']==2
    assert [(c['op'],c['returned'],c['irq_enabled']) for c in x['calls']]==[(6,0,True),(2,-2,True)]
    assert x['frame']['failed']==x['reopened']['failed']==0 and x['closed']['rows']==7
    assert x['native_UI_audit']['host_UI_writes']==0 and not x['native_UI_audit']['getter_stub_present']
    assert not [e for e in result['file_log'] if e['op'] in ('create','write','rename','delete')]
    out.append(dict(unit=unit,status='OBSERVED_P1',path=str(path.relative_to(ROOT)),result_sha256=sha(path.read_bytes()),
                    dat_sha256=sha(raw),seconds=result['seconds'],before_entry=2,after_entry=4,target_entry=5,
                    S_unchanged=True,W=506,T=2,ERR=False,IRQ_enabled_at_owner_change=True,
                    op6_return=0,op2_return=-2,OK_closes=True,reopen_ERR=False,host_UI_writes=0,file_mutations=0))
target=HERE/'evidence/p1-summary.json'
target.write_text(json.dumps(dict(status='OBSERVED_P1',finding='unverified prior row ledger is replaced by stock after late S busy',cases=out),ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'status':'OBSERVED_P1','units':[r['unit'] for r in out],'all_checks':True}))
