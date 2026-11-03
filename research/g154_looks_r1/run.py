"""同进程前台运行，保存完整日志、耗时及退出回执。"""
from pathlib import Path
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import runpy
import signal
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-looks-r1')


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--timeout',type=int,default=10800);p.add_argument('entry',nargs=argparse.REMAINDER)
    args=p.parse_args();assert args.entry and args.timeout>=1800
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    stop=HERE/'local/stop-before-next'
    if stop.exists():
        row=dict(status='STOPPED',name=args.name,reason=stop.read_text().strip(),started=False)
        (HERE/'evidence'/('stopped-'+args.name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        return 75
    receipt=HERE/'evidence'/('job-'+args.name+'.json');assert not receipt.exists(),receipt
    os.environ.update(TMPDIR=str(TMP),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    TMP.mkdir(parents=True,exist_ok=True)
    record=dict(name=args.name,argv=args.entry,timeout=args.timeout,pid=os.getpid(),nice=10,
        backend=os.environ.get('GXR_HARNESS_BACKEND','c'),started_ns=time.time_ns(),
        entry_sha256=hashlib.sha256((ROOT/args.entry[0]).read_bytes()).hexdigest(),
        dat_sha256={s:hashlib.sha256((ROOT/('firmware/'+s+'/local/SD_ROOT/GXRCE.DAT')).read_bytes()).hexdigest() for s in ('package_v39_g154_test','package_v39_g154_looks18_test')})
    started=time.monotonic();code=0
    def timeout(signum,frame):raise TimeoutError('前台作业达到时限')
    previous=signal.signal(signal.SIGALRM,timeout);signal.alarm(args.timeout)
    try:
        with (HERE/'evidence'/('job-'+args.name+'.log')).open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            try:
                sys.argv=args.entry;runpy.run_path(str(ROOT/args.entry[0]),run_name='__main__')
            except SystemExit as error:code=error.code if isinstance(error.code,int) else int(bool(error.code))
            except BaseException:
                traceback.print_exc();code=1
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
        record.update(returncode=code,status='PASS' if code==0 else 'FAIL',ended_ns=time.time_ns(),seconds=time.monotonic()-started)
        receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        with (HERE/'PROGRESS.md').open('a') as stream:
            stream.write(datetime.datetime.now().astimezone().isoformat()+' '+args.name+' '+record['status']+' '+str(round(record['seconds'],1))+' s。\n')
    print(json.dumps(record,ensure_ascii=False),flush=True)
    return code


if __name__=='__main__':sys.exit(main())
