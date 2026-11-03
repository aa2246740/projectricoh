"""Serial foreground acceptance stages after the paired product runs finish."""
import argparse,json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=('compare','gates','rest','tapes','all'),default='all');args=parser.parse_args();enable()
    if not (HERE/'local/measurements/complete.json').is_file():raise RuntimeError('paired real groups must finish first')
    for path in HERE.rglob('*.py'):
        if 'local' not in path.relative_to(HERE).parts:compile(path.read_bytes(),str(path),'exec')
    jobs=[]
    if args.stage in ('compare','all'):jobs.append('compare_products.py')
    if args.stage in ('gates','all'):jobs+=['validate.py','comparator_checks.py']
    if args.stage in ('rest','all'):jobs+=['integration_checks.py','profile_run.py','tapes_run.py']
    if args.stage=='tapes':jobs.append('tapes_run.py')
    out=HERE/'local/stages';out.mkdir(exist_ok=True)
    records=[]
    for script in jobs:
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic();label=Path(script).stem
        command=[sys.executable,'-I','-B',str(HERE/script)]
        print(json.dumps({'stage':'start','name':label,'load':os.getloadavg()}),flush=True)
        with (out/(label+'.log')).open('w') as stream:result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=32400)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'stage':label,'returncode':result.returncode,'wall_seconds':time.monotonic()-start,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'load_end':os.getloadavg()}
        records.append(row);emit(out/(args.stage+'-progress.json'),records);print(json.dumps(row),flush=True)
        if result.returncode:print((out/(label+'.log')).read_text()[-6500:],flush=True);raise RuntimeError(label+' failed')
    emit(out/(args.stage+'-complete.json'),{'passed':True,'records':records})
if __name__=='__main__':main()
