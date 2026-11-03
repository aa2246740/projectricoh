"""Build a temporary API6 library without the new event-name check and verify detection."""
from pathlib import Path
import hashlib,json,os,subprocess,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')

def main():
    folder=OUT/'mutation';folder.mkdir(exist_ok=False)
    temporary=TMP/'mutation';temporary.mkdir(exist_ok=False)
    build=json.loads((ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json').read_text())
    command=list(build['command']);command.insert(1,'-DGXR_TEST_SKIP_EVENT_BINDING=1')
    command[-1]=str(temporary/Path(build['library']).name)
    started=time.monotonic()
    result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,TMPDIR=str(temporary),CLANG_MODULE_CACHE_PATH=str(temporary/'clang')),capture_output=True,timeout=3600)
    (folder/'build.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('temporary control library build failed')
    build.update(command=command,library=command[-1],sha256=hashlib.sha256(Path(command[-1]).read_bytes()).hexdigest())
    manifest=folder/'build.json';manifest.write_text(json.dumps(build,indent=2)+'\n')
    script=OUT/'event_validation_mutation.py'
    script.write_text((OUT/'event_validation.py').read_text().replace("folder = OUT / 'event-validation'","folder = OUT / 'event-validation-mutation'"))
    env=dict(os.environ,GXR_CCORE_BUILD_MANIFEST=str(manifest),TMPDIR=str(temporary))
    command=['/usr/bin/sandbox-exec','-f',str(OUT/'fence.sb'),'/usr/bin/python3','-I','-B',str(script)]
    with (folder/'run.log').open('wb') as stream:run=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
    value=json.loads((OUT/'event-validation-mutation/summary.json').read_text())
    proof={'detected':run.returncode==1 and value['c_pass_python_fail'] and value['filter_off_equal'],
           'returncode':run.returncode,'wall_seconds':time.monotonic()-started,'api':6,'library_sha256':build['sha256'],
           'command':command,'build':build,'results':value}
    (folder/'summary.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:proof[k] for k in ('detected','returncode','wall_seconds','api','library_sha256')}),flush=True)
    return 0 if proof['detected'] else 1

if __name__=='__main__':raise SystemExit(main())
