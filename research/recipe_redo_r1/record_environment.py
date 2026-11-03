"""Record installed numerical dependencies without importing the numerical runtime."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import sys

HERE=Path(__file__).resolve().parent


def main():
    packages={}
    for name in ('numpy','scipy','Pillow'):
        packages[name]=importlib.metadata.version(name)
    builds=[]
    for path in (HERE/'local/fast_engine/build').glob('*.json'):
        record=json.loads(path.read_text())
        builds.append(dict(source_sha256=record['source_sha256'],library_sha256=record['library_sha256'],
                           compiler=record['compiler']))
    result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        python=sys.version,executable=sys.executable,platform=platform.platform(),machine=platform.machine(),
        packages=packages,recording_process_nice=os.getpriority(os.PRIO_PROCESS,0),
        numerical_thread_policy={name:'1' for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS')},
        thread_policy_source_sha256=hashlib.sha256((HERE/'runtime_std.py').read_bytes()).hexdigest(),
        fitting_solver='fit-fast frozen exact path',native_builds=builds,new_dependencies_installed=False)
    (HERE/'environment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Environment recorded',packages)


if __name__=='__main__':main()
