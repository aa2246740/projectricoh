"""Run one validation group until a fixed deadline and reap its process group."""
import argparse,datetime,json,os,signal,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--until',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('script',type=Path)
    parser.add_argument('args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    target=HERE/'runs'/(args.name+'.json');assert not target.exists()
    deadline=datetime.datetime.fromisoformat(args.until)
    assert deadline.tzinfo is not None
    seconds=(deadline-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    assert seconds>0
    command=[sys.executable,'-I','-B',str(args.script),*args.args]
    child=subprocess.Popen(command,cwd=ROOT,start_new_session=True)
    status='complete'
    try:
        code=child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        status='timeout'
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=10)
        code=124
    result=dict(status=status,returncode=code,command=command,deadline=args.until,
                finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    sys.exit(code)


if __name__=='__main__':main()
