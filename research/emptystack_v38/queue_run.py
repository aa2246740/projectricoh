from pathlib import Path
import contextlib
import datetime
import json
import os
import runpy
import signal
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, save, sha, neutral

class Log:
    def __init__(self, file):
        self.file = file
    def write(self, value):
        return self.file.write(neutral(value))
    def flush(self):
        return self.file.flush()
    def __getattr__(self, name):
        return getattr(self.file, name)

def main():
    setup()
    if (LOCAL / 'queue-stop').exists():
        print('Queue stopped between jobs',flush=True)
        return
    queue_path = Path(sys.argv[1]).resolve()
    index = int(sys.argv[2]) if len(sys.argv)>2 else 0
    jobs = json.loads(queue_path.read_text())
    state_path = LOCAL / (queue_path.stem + '-state.json')
    state = json.loads(state_path.read_text()) if state_path.exists() else {'jobs':[]}
    if index>=len(jobs):
        print(json.dumps({'queue':queue_path.name,'complete':True,'jobs':len(state['jobs']),'failed':sum(x['returncode']!=0 for x in state['jobs'])}),flush=True)
        return
    job = jobs[index]
    dat = ROOT / 'firmware/package_v38_g137/SD_ROOT/GXRCE.DAT'
    pinned = sha(dat)
    started = time.monotonic()
    script = ROOT / job['script']
    sys.argv = [str(script)] + job.get('args',[])
    code = 0
    with (LOCAL / (job['name']+'.log')).open('w') as file:
        output = Log(file)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit as error:
                code = error.code if isinstance(error.code,int) else 1 if error.code else 0
            except BaseException:
                code = 1
                output.write(traceback.format_exc())
    assert sha(dat)==pinned
    record = {'index':index,'name':job['name'],'returncode':code,'seconds':round(time.monotonic()-started,3),'dat_sha256':pinned}
    state['jobs'].append(record)
    save(state_path,state)
    print(json.dumps(record),flush=True)
    os.execv('/usr/bin/python3',['/usr/bin/python3','-I','-B',str(WORK/'queue_run.py'),str(queue_path),str(index+1)])

if __name__ == '__main__':
    main()
