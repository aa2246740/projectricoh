"""Complete only unrecorded cases after review command time limits."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def combined(group,unit,paths):
    values=[json.loads(path.read_text()) for path in paths]
    assert all(r.get('dat_sha256',r.get('artifact',{}).get('dat_sha256'))==PIN and r.get('status','').startswith('PASS') for r in values)
    result=dict(status='PASS',unit=unit,dat_sha256=PIN,
        cases=[dict(case=p.stem,record=str(p.relative_to(ROOT)),record_sha256=file_sha(p),wait_status=0) for p in paths],
        source='Completed records from the timed initial command plus only its missing cases; initial timeout remains in commands.jsonl.')
    save('evidence/'+group+'-'+unit+'.json',result)
    print('PASS combined',group,unit,len(paths),'actual case records')

def transitions(unit):
    from ui_test_support import Session
    from ui_acceptance import fork_case,KEYS
    expected=[OUT/'local/ui-cases'/(unit+'-'+view+'-'+key+'.json')
              for view in ('L1','card','items','value','groups','entries-empty','ERR') for key in KEYS]
    if all(path.exists() for path in expected):return combined('transitions',unit,expected)
    s=Session(unit,'transitions-complete');s.press('DOWN');s.press('OK');s.reopen()
    original=s.p.rpc.call;fired=[False]
    def fault(cmd,value):
        if not fired[0] and cmd==22:
            result=original(cmd,value);s.p.rpc.log[-1].update(device_result=result,result=-1,simulated=True);fired[0]=True;return -1
        if fired[0]:s.p.rpc.log.append(dict(cmd=cmd,value=value,page=s.p.rpc.page,result=-1,t=s.p.rpc.t,simulated=True));return -1
        return original(cmd,value)
    s.p.rpc.call=fault;s.press('DOWN');s.p.rpc.call=original
    assert fired[0] and s.state()['failed'];results=[]
    for key in KEYS:
        path=OUT/'local/ui-cases'/(unit+'-ERR-'+key+'.json')
        if path.exists():continue
        def case(record,key=key):
            settings=s.h.u(0x200c0dac);before=s.h.b.read(settings,0xc9e);at=len(s.p.rpc.log);setters=[];mode=[]
            for pc in (0x202871dc,0x20268768,0x20268774):
                s.h.b.add_breakpoint(pc,lambda b,pc=pc:setters.append(hex(pc)) or False)
            s.h.b.add_write_trace(settings+0x36e,settings+0x36f,lambda e:mode.append(hex(e.pc)))
            after=s.press(key)
            assert len(s.p.rpc.log)==at and not setters and not mode
            if key in ('UP','DOWN','DISP'):
                assert after['screen']==6 and after['cur']==0 and after['rows']==8
                assert before==s.h.b.read(settings,0xc9e)
            else:assert after['overlay']==0
            record.update(Image_setters=setters,Image_mode_stores=mode)
        fork_case(s,'ERR-'+key,case,results)
    paths=[OUT/'local/ui-cases'/(unit+'-'+view+'-'+key+'.json')
           for view in ('L1','card','items','value','groups','entries-empty','ERR') for key in KEYS]
    combined('transitions',unit,paths)

def exits(unit):
    from run_cases import prepare
    from lock_exits import run
    expected=[OUT/'local/lock-exits'/(f'124-{unit}-'+panel+f'-k{keep}-'+action+'.json')
              for panel in ('list','panel') for keep in (0,1)
              for action in ('confirm','adj','half','release','raw_half','disp_confirm')]
    if all(path.exists() for path in expected):return combined('lock-exits-124',unit,expected)
    fixture=prepare(argparse.Namespace(generation=124,unit=unit,case='lock-exits-complete'))
    paths=[]
    for panel in (False,True):
        for keep in (0,1):
            for action in ('confirm','adj','half','release','raw_half','disp_confirm'):
                name=f'124-{unit}-'+('panel' if panel else 'list')+f'-k{keep}-'+action
                path=OUT/'local/lock-exits'/(name+'.json');paths.append(path)
                if path.exists():continue
                sys.stdout.flush();pid=os.fork()
                if pid==0:
                    record=dict(case=name,generation=124,unit=unit);code=0
                    try:run(fixture,panel,action,keep,record)
                    except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                    save('local/lock-exits/'+name+'.json',record)
                    print(name,record.get('status'),record.get('error','')[-500:],flush=True);os._exit(code)
                _,status=os.waitpid(pid,0);assert status==0,(name,status)
    combined('lock-exits-124',unit,paths)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('group',choices=('transitions','exits'));p.add_argument('--unit',default='50mm')
    a=p.parse_args();(transitions if a.group=='transitions' else exits)(a.unit)
