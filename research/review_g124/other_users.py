"""Complete native application/exit checks for the seven non-FCC user entries."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True);a=p.parse_args()
    tool=json.loads((OUT/'evidence/user-tool.json').read_text());fixture=ROOT/tool['fixture']
    s=Session(a.unit,'other-users',fixture);s.match(4,[0]*11)
    meta=s.p.image_base+int.from_bytes(s.p.dat[204:208],'big');length=len(s.p.dat)-int.from_bytes(s.p.dat[204:208],'big')
    before=s.h.b.read(meta,length);rows=[]
    for i,base in enumerate((1,2,3,4,6,7,8)):
        s.goto(0,9);s.press('DISP');s.goto(4,base);s.press('DISP')
        assert s.state()['screen']==5 and s.state()['count']==2
        s.press('DISP');assert s.state()['screen']==1 and s.state()['applied_user']
        applied=s.match(base,[0]*11);key=('OK','ADJ','HALF')[i%3]
        after=s.press(key);assert after['overlay']==0
        retained=s.match(base,[0]*11);assert retained==applied
        s.reopen();assert s.state()['cur']==9 and s.state()['applied_user']
        reopened=s.match(base,[0]*11);assert reopened==applied
        rows.append(dict(base=base,exit_key=key,applied=applied,retained=retained,reopened=reopened))
    assert before==s.h.b.read(meta,length)
    result=s.report();result.update(status='PASS',seven_other_base_users=rows,readonly_metadata_unchanged=True,
        supplement_to_25_FCC_entries=True,cold_boot_scope='Nine unit rows, T and mode; startup WB input is synthetic.')
    save('local/other-users-'+a.unit+'.json',result)
    save('evidence/other-users-'+a.unit+'.json',{k:v for k,v in result.items() if k not in ('rpc_log','events')})
    print('PASS',a.unit,'seven other bases, complete S plan, three exit types and verified reopen')
if __name__=='__main__':main()
