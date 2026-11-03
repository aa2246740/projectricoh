"""Corrected-read port (review_g135) of research/review_g126/ui_acceptance.py, transitions and values groups.
Every key/screen/ownership/RPC assertion is kept; only the old-design label arrays and the old +-5 cursor indices are replaced (see PORT_NOTES.md).
"""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'review_g126'))
from ui_test_support import *
from decode_error import decode

KEYS=('UP','DOWN','DISP','OK','ADJ','HALF')

def fork_case(session,name,body,results):
    sys.stdout.flush()
    pid=os.fork()
    if pid==0:
        record={};code=0
        try:
            body(record)
            record['status']='PASS'
        except BaseException:
            record.update(status='FAIL',error=traceback.format_exc());code=1
        record.update(session.report())
        save('local/ui-cases/'+session.unit+'-'+name+'.json',record)
        print(session.unit,name,record['status'],record.get('error','')[-600:],flush=True)
        os._exit(code)
    _,status=os.waitpid(pid,0)
    results.append(dict(case=name,wait_status=status))

def seed(unit,tag):
    s=Session(unit,tag)
    assert s.state()['labels']==[' 1 GRPos',' 2 GRNeg',' 3 HC BW','>4 Std',' 5 F-CC',' 6 F-CN',' 7 L-Chr',' 8 L-Viv']
    s.press('DOWN');s.match(5,[0]*11);s.press('OK');s.reopen()
    return s

def transitions(unit):
    s=seed(unit,'transitions');results=[]
    def run_view(name,expected):
        for key in KEYS:
            def case(record,key=key):
                before=s.state();actual=s.match() if not before['failed'] else None
                S_before=s.h.b.read(s.h.u(0x200c0dac),0xc9e)
                at=len(s.p.rpc.log)
                after=s.press(key)
                if key in ('OK','ADJ','HALF'):
                    assert after['overlay']==0 and (key=='HALF' or after['rows']==7),after
                    if not before['failed']:
                        assert s.match()==actual
                        opened=s.reopen()
                        assert opened['slot']==before['slot'] and opened['levels']==before['levels']
                    record['retained_effect']=actual
                else:
                    screen,cur=expected[key]
                    assert (after['screen'],after['cur'])==(screen,cur),after
                    if not after['failed']:
                        s.match()
                if before['failed']:
                    assert len(s.p.rpc.log)==at
                    # Native half-shutter has its own S updates; plain arrows and DISP must not.
                    if key in ('UP','DOWN','DISP'):
                        assert s.h.b.read(s.h.u(0x200c0dac),0xc9e)==S_before
                    record['ERR']=decode(before['labels'][0])
            fork_case(s,name+'-'+key,case,results)
    run_view('L1',{'UP':(0,3),'DOWN':(0,5),'DISP':(1,1)})
    s.press('DISP')
    assert s.state()['labels']==['<5 F-CC','C 0 H 0','S 0 F 0!','V 0 W 0','T 0 P 0','Amt 100%','Default',' ']
    run_view('card',{'UP':(1,0),'DOWN':(1,2),'DISP':(2,1)})
    s.press('DISP')
    assert s.state()['labels']==['<5 F-CC','Cont   0','High   0','Shad   0','Fade!  0','Satu   0','Warm   0','Tint   0']
    run_view('items',{'UP':(2,0),'DOWN':(2,2),'DISP':(3,9)})
    s.press('DISP')
    assert s.state()['labels'][s.state()['physical']]=='Cont   0'
    run_view('value',{'UP':(3,8),'DOWN':(3,10),'DISP':(2,1)})
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,0);s.press('DISP')
    s.goto(0,9);s.press('DISP')
    assert s.state()['screen']==4
    run_view('groups',{'UP':(4,0),'DOWN':(4,2),'DISP':(5,1)})
    s.press('DISP')
    assert s.state()['labels']==[' < Back',' None',' ',' ',' ',' ',' ',' ']
    run_view('entries-empty',{'UP':(5,0),'DOWN':(5,1),'DISP':(5,1)})
    s.goto(5,0);s.press('DISP');s.goto(4,0);s.press('DISP');s.goto(0,4)
    s.press('OK');s.reopen()
    original=s.p.rpc.call;fired=[False]
    def fault(command,value):
        if not fired[0] and command==22:
            result=original(command,value);s.p.rpc.log[-1].update(device_result=result,result=-1,simulated=True)
            fired[0]=True;return -1
        if fired[0]:
            s.p.rpc.log.append(dict(cmd=command,value=value,page=s.p.rpc.page,result=-1,t=s.p.rpc.t,simulated=True));return -1
        return original(command,value)
    s.p.rpc.call=fault
    s.press('DOWN');s.p.rpc.call=original
    assert fired[0] and s.state()['failed'] and s.state()['rows']==8
    assert s.state()['labels'][1:]==[' ']*7
    run_view('ERR',{'UP':(6,0),'DOWN':(6,0),'DISP':(6,0)})
    save('evidence/port-transitions-'+unit+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',
         dat_sha256=sha(s.p.dat),cases=results,screen_keys=len(results),native_UI_hand_seeded=False))
    assert all(x['wait_status']==0 for x in results),results

def values(unit):
    s=seed(unit,'values');results=[]
    CONTROL=(1,2,3,5)   # control ids behind the four old parameters (Cont, High, Shad, Satu)
    ROW=(1,2,3,5)       # their rows in the items view of recipe 5
    ZERO=[100]+[0]*9    # new 10-control vector, Amount 100
    for param in range(4):
        def case(record,param=param):
            s.open_numeric(param)
            labels=('Cont','High','Shad','Satu')
            assert s.state()['cur']==9 and s.state()['levels']==ZERO
            actual=[]
            for value in range(1,10):
                state=s.press('UP');expected=list(ZERO);expected[CONTROL[param]]=value
                assert state['levels']==expected and state['cur']==9-value,state
                actual.append(s.match(5,expected))
            top=s.press('UP')
            assert top['cur']==0 and top['labels'][0]==labels[param]+'! +9',top
            for value in range(8,-10,-1):
                state=s.press('DOWN');expected=list(ZERO);expected[CONTROL[param]]=value
                assert state['levels']==expected and state['cur']==9-value,state
                actual.append(s.match(5,expected))
            low=s.press('DOWN')
            assert low['cur']==18 and low['labels'][low['physical']]==labels[param]+'! -9',low
            record.update(values=actual,both_limits_clamp=True,native_wrap_consumed=True)
            s.press('DISP')
            assert s.state()['screen']==2 and s.state()['cur']==ROW[param]
            s.goto(2,0);s.press('DISP');assert s.state()['screen']==1 and s.state()['cur']==1
            s.press('OK');assert s.state()['rows']==7
            s.match(5,expected);s.reopen();s.match(5,expected)
        fork_case(s,'all-values-'+str(param),case,results)
    def scroll(record):
        s.goto(0,0)
        first=s.state();at=len(s.p.rpc.log);s.press('UP')
        assert s.state()['cur']==0 and s.state()['physical']==0
        assert s.events[-1]['result']['cursor_before']==1 and s.events[-1]['result']['cursor_after']==1
        traces=[]
        for row in range(1,10):
            state=s.press('DOWN');assert state['cur']==row,state;traces.append(state)
            if row>=8:
                s.match(8,[100]+[0]*9)
        assert s.state()['labels'][-2:]==[' DISP:Tw',' MyRec']
        assert s.state()['rows']==8 and s.state()['count']==10 and s.state()['cur']==9
        s.press('DOWN');assert s.state()['cur']==9
        # Hint is the ninth logical line and opens the verified current recipe.
        s.press('UP');assert s.state()['cur']==8;s.press('DISP')
        assert s.state()['screen']==1 and s.state()['slot']==8
        record.update(first=first,virtual_rows=traces,boundary_RPC=len(s.p.rpc.log)-at)
    fork_case(s,'L1-virtual-scroll',scroll,results)
    def default(record):
        s.open_numeric(0);s.press('UP');s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,6)
        assert s.state()['levels']==[100,1]+[0]*8
        s.press('DISP');assert s.state()['armed']==1 and s.state()['labels'][6]=='Sure?'
        s.press('UP');s.press('DOWN');assert not s.state()['armed'] and s.state()['levels'][1]==1
        s.press('DISP');assert s.state()['armed']==1
        s.press('DISP');assert s.state()['levels']==[100]+[0]*9 and not s.state()['armed']
        assert s.state()['labels'][0]=='<5 F-CC'
        record['after_default']=s.match(5,[100]+[0]*9)
    fork_case(s,'default-double-DISP',default,results)
    def back_pair(record):
        s.press('DISP');s.press('DOWN');s.press('DISP')
        assert s.state()['screen']==2 and s.state()['cur']==3
        s.goto(2,0);s.press('DISP')
        assert s.state()['screen']==1 and s.state()['cur']==1
        record['last_selected_item_return']=True
    fork_case(s,'back-from-second-pair',back_pair,results)

    save('evidence/port-values-'+unit+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',dat_sha256=sha(s.p.dat),cases=results))
    assert all(x['wait_status']==0 for x in results),results

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('group',choices=('transitions','values'))
    parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=parser.parse_args()
    (transitions if args.group=='transitions' else values)(args.unit)

if __name__=='__main__':
    main()
