"""Replay the full g150 unverified-late reporter in independent directories."""
from pathlib import Path
import difflib,hashlib,json,os,resource,subprocess,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')

def main():
    base=OUT/'observation';base.mkdir(exist_ok=False)
    copies=[];records=[]
    for side in ('c','python'):
        folder=base/side;(folder/'tests').mkdir(parents=True)
        for relative in ('independent_checks.py','g150_checks.py','review_checks.py','previous_state_checks.py','decode.py','tests/g139_host.py','tests/g139_check.py'):
            source=ROOT/'research/review_g150'/relative;a=source.read_text();b=a
            for needle in ('ROOT = HERE.parents[1]','ROOT = Path(__file__).resolve().parents[2]','ROOT = Path(__file__).resolve().parents[3]'):
                b=b.replace(needle,'ROOT = Path('+repr(str(ROOT))+')')
            target=folder/relative;compile(b,str(target),'exec');target.write_text(b)
            copies.append({'source':str(source.relative_to(ROOT)),'copy':str(target.relative_to(ROOT)),
                           'source_sha256':hashlib.sha256(a.encode()).hexdigest(),'copy_sha256':hashlib.sha256(b.encode()).hexdigest(),
                           'diff':''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True)))})
        for name in ('backend_select.py','input_trace.py','input_trace_strict.py'):
            source=OUT/'entry/run'/name;b=source.read_text()
            if name=='backend_select.py':
                b=b.replace('ROOT = Path(__file__).resolve().parents[4]','ROOT = Path('+repr(str(ROOT))+')')
                b=b.replace('from input_trace import InputTrace','from input_trace_strict import InputTrace')
            (folder/name).write_text(b)
        launch=folder/'launch.py'
        launch.write_text("""from pathlib import Path
import runpy,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from backend_select import install
install()
sys.argv=[str(HERE/'previous_state_checks.py'),'unverified-late','--unit','mount']
runpy.run_path(sys.argv[0],run_name='__main__')
""")
        temporary=TMP/('observation-'+side);temporary.mkdir(exist_ok=False)
        env=dict(os.environ,TMPDIR=str(temporary),GXR_HARNESS_BACKEND=side,GXR_HARNESS_UI_AUDIT='1',
                 GXR_HOST_METRICS_DIR=str(folder/'metrics'),GXR_INPUT_RECEIPT_DIR=str(folder/'inputs'),
                 GXR_INPUT_EXCLUDE_WORK=str(folder/'tests/local'),REVIEW_JOB='unverified-late-mount',
                 G139_PACKAGE='firmware/package_v38_g150_test',G139_ENGINE='firmware/engine_v58_g150',
                 G150_RELEASE_PACKAGE='firmware/package_v38_g150',G150_TEST_PACKAGE='firmware/package_v38_g150_test')
        env.pop('GXR_CCORE_BUILD_MANIFEST',None)
        command=['/usr/bin/sandbox-exec','-f',str(OUT/'fence.sb'),'/usr/bin/python3','-I','-B',str(launch)]
        started=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        print(json.dumps({'event':'start','side':side,'case':'unverified-late-mount'}),flush=True)
        with (folder/'raw.log').open('wb') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'side':side,'returncode':result.returncode,'wall_seconds':time.monotonic()-started,
             'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
             'command':command,'timeout_seconds':10800,'nice':os.getpriority(os.PRIO_PROCESS,0)}
        records.append(row);(base/'progress.json').write_text(json.dumps(records,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    (base/'complete.json').write_text(json.dumps(records,indent=2)+'\n')
    (base/'copies.json').write_text(json.dumps(copies,indent=2)+'\n')

if __name__=='__main__':main()
