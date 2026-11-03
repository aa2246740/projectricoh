"""Check the distinct black-and-white layout and nonselectable padding using native keys."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=parser.parse_args();s=Session(args.unit,'labels')
    s.press('UP');s.match(3,[0]*11);s.press('DISP')
    assert s.state()['labels']==['<3 HC BW','C 0 H 0 ','S 0 ','Default',' ',' ',' ',' ']
    s.press('DISP')
    assert s.state()['labels']==['<3 HC BW','Cont   0','High   0','Shad   0',' ',' ',' ',' ']
    s.goto(2,3);s.press('DOWN');assert s.state()['cur']==3
    s.press('DISP');s.press('DOWN')
    assert s.state()['levels']==[0,0,-1]+[0]*8
    s.match(3,[0,0,-1]+[0]*8)
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,3)
    s.press('DISP');assert s.state()['armed']==1
    s.press('DOWN');assert s.state()['cur']==3 and not s.state()['armed']
    s.press('DISP');s.press('DISP');s.match(3,[0]*11)
    s.goto(1,0);s.press('DISP');assert s.state()['screen']==0 and s.state()['cur']==2
    assert not any('Satu' in label or 'V' in label for label in s.ascii if label.strip() not in ('8 L-Viv','>8 L-Viv'))
    result=s.report();result.update(status='PASS',black_white_saturation_hidden=True,padding_consumed=True,
                                    maximum_ascii_characters=max(map(len,s.ascii)))
    save('local/labels-'+args.unit+'.json',result)
    save('evidence/labels-'+args.unit+'.json',{key:value for key,value in result.items() if key not in ('rpc_log','events')})
    print('PASS',args.unit,'black-and-white labels, hidden saturation and nonselectable padding')

if __name__=='__main__':
    from completed import reuse
    if not reuse(Path(__file__).stem,sys.argv[1:]):
        main()
