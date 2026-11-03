"""Read-only DAT entries through native group, list and card screens."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=parser.parse_args()
    complete=OUT/'local'/('users-'+args.unit+'.json')
    if complete.exists():
        old=json.loads(complete.read_text())
        if old.get('status')=='PASS' and old.get('full_committed_settings_checked'):
            print('Already executed with complete committed S-plan checks:',args.unit,complete)
            return
    tool=json.loads((OUT/'evidence/user-tool.json').read_text())
    path=ROOT/tool['fixture']
    assert file_sha(path)==tool['fixture_sha256']
    s=Session(args.unit,'users',path)
    assert s.state()['slot']==4 and s.state()['levels']==[0]*11 and not s.state()['applied_user']
    cold04=s.match(4,[0]*11)
    metadata=s.p.image_base+int.from_bytes(s.p.dat[204:208],'big')
    before=bytes(s.h.b.read(metadata,len(s.p.dat)-int.from_bytes(s.p.dat[204:208],'big')))
    s.goto(0,9);s.press('DISP');s.goto(4,5)
    assert s.state()['labels'][5]==' FCC  25',s.state()
    s.press('DISP')
    assert s.state()['screen']==5 and s.state()['count']==26
    assert s.state()['labels'][1]==' FCC*025'
    s.match(8,[0]*11)
    s.press('DISP');assert s.state()['screen']==1
    s.match(5,[1]+[0]*10)
    s.goto(1,0);s.press('DISP');assert s.state()['screen']==5
    names=[]
    for row in range(1,26):
        s.goto(5,row)
        current=s.state();label=current['labels'][current['physical']]
        expected='>FCC'+('-' if row==25 else '*')+f'{26-row:03d}'
        assert label==expected,(row,current,expected)
        names.append(label)
    last=s.state();s.press('DOWN');assert s.state()['cur']==25
    s.press('DISP')
    assert s.state()['screen']==1 and s.state()['labels'][0]=='<FCC-001'
    assert not any(label.strip() in ('Save','Save*','Copy','Delete') for label in s.state()['labels'])
    s.press('DISP');s.press('DISP');s.press('UP')
    assert s.state()['levels']==[1]+[0]*10
    assert s.state()['labels'][s.state()['physical']]=='Cont  +1'
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,3)
    s.press('DISP');s.press('DISP');assert s.state()['levels']==[0]*11
    default_effect=s.match(5,[0]*11)
    s.goto(1,0);s.press('DISP');assert s.state()['screen']==5 and s.state()['cur']==25
    s.goto(5,0);s.press('DISP');assert s.state()['screen']==4
    s.goto(4,0);s.press('DISP');assert s.state()['screen']==0 and s.state()['cur']==9
    assert '>MyRec' in s.state()['labels']
    # Returning up through the 25 rows previews each crossed entry; the
    # latest FCC*025 is active by the time the Back row is reached.
    assert s.state()['levels']==[1]+[0]*10
    before_exit=s.match(5,[1]+[0]*10)
    s.press('OK');assert s.match(5,[1]+[0]*10)==before_exit;s.reopen()
    assert s.state()['cur']==9 and s.state()['applied_user']
    assert bytes(s.h.b.read(metadata,len(before)))==before,'Runtime changed read-only DAT metadata'
    report=s.report();report.update(status='PASS',entry_names=names,maximum_group_rows=26,edge_clamp=True,
         readonly_metadata_unchanged=True,default_effect=default_effect,exit_retained=before_exit,fixture_sha256=tool['fixture_sha256'],cold_boot_pure04=cold04)
    save('local/users-'+args.unit+'.json',report)
    save('evidence/users-'+args.unit+'.json',{k:v for k,v in report.items() if k not in ('rpc_log','events')})
    print('PASS',args.unit,'user groups, 25 entries, numeric editing, Default and exit retention')

if __name__=='__main__':
    from completed import reuse
    if not reuse(Path(__file__).stem,sys.argv[1:]):
        main()
