"""逐个前台运行，失败时用 Python 确认并停止，不把失败计为通过。"""
from pathlib import Path
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def jobs():
    result=[]
    for unit in ('50mm','mount','28mm'):
        for kind,number in (('builtin',2),('look',1),('user',3)):
            result.append((unit+'-'+kind,'boot_tests.py',['--case','success','--unit',unit,'--kind',kind,'--number',str(number)]))
    for case in ('not-pure','not-pure-T','not-pure-rows','my1','my2','my3','pending','unknown-my','unknown-pending',
                 'crc','unit','identity','v1','controls','unknown-tail','empty','busy','raw-mode','release'):
        result.append(('gate-'+case,'boot_tests.py',['--case',case]))
    for unit in ('50mm','mount'):
        for case in ('late-busy','late-busy-T1','row-once','row-persistent','retire','lease','epoch','object','unit'):
            result.append((unit+'-'+case,'fault_tests.py',['--unit',unit,'--case',case]))
    result += [('manual','manual_tests.py',[]),('identity','identity_tests.py',[]),('equality','equality_tests.py',[])]
    for unit in ('50mm','mount','28mm'):
        result.append(('navigation-'+unit,'verify.py',['navigation','--unit',unit]))
    for unit in ('50mm','mount'):
        for group in ('busy','cross'):
            result.append((group+'-'+unit,'state_checks.py',[group,'--unit',unit]))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--start',type=int,default=0)
    p.add_argument('--stop',type=int,default=len(jobs()));args=p.parse_args();selected=jobs()[args.start:args.stop]
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    rows=[];overall=time.monotonic()
    for name,entry,arguments in selected:
        # The 3-hour task deadline stays separate from each generous test timeout.
        if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,11,2,3,36,11,tzinfo=datetime.timezone.utc):
            raise TimeoutError('任务时限已到，未启动下一组')
        command=['/usr/bin/python3','-I','-B',HERE/'run.py','--name',args.tag+'-'+name,
                 'research/g155/'+entry,*arguments]
        env=dict(os.environ,GXR_HARNESS_BACKEND='c',TMPDIR='/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1')
        start=time.monotonic();process=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,timeout=10800)
        row=dict(name=name,returncode=process.returncode,seconds=time.monotonic()-start);rows.append(row)
        if process.returncode:
            env['GXR_HARNESS_BACKEND']='python';command[5]=args.tag+'-'+name+'-python'
            check=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,timeout=10800)
            row['python_returncode']=check.returncode
        (HERE/'evidence'/('batch-'+args.tag+'.json')).write_text(json.dumps(dict(jobs=rows,
            status='FAIL' if process.returncode else 'PASS' if len(rows)==len(selected) else 'RUNNING',
            seconds=time.monotonic()-overall),indent=2)+'\n')
        if process.returncode:return process.returncode
    return 0

if __name__=='__main__':sys.exit(main())
