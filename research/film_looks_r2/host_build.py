"""Load-gated native build of the frozen pure-C math probe, using no new dependencies."""
import ast
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

assert sys.flags.isolated
LOCAL=Path(__file__).resolve().parent/'local'
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
assert os.getpriority(os.PRIO_PROCESS,0)==15


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,d):
    p=LOCAL/p if not Path(p).is_absolute() else Path(p)
    assert p.resolve().is_relative_to(LOCAL);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,indent=2)+'\n')


def main():
    if time.time()>=json.loads((LOCAL/'task_deadline.json').read_text())['deadline_unix']:raise SystemExit(78)
    source=LOCAL/'frozen/research/model_c040_r1/local/c040_common.py'
    tree=ast.parse(source.read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='admission')
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),globals())
    admission()
    temp=LOCAL/'clang_tmp';temp.mkdir(exist_ok=True)
    command=['/usr/bin/clang','-O2','-dynamiclib',str(LOCAL/'contract_sources/kv_math.c'),'-o',str(LOCAL/'flags_host.dylib')]
    env=dict(os.environ,TMPDIR=str(temp))
    with (LOCAL/'flags_host_compile.log').open('w') as output:
        result=subprocess.run(command,env=env,stdout=output,stderr=subprocess.STDOUT)
    assert result.returncode==0,'Inspect flags_host_compile.log'
    dump('flags_host_build.json',dict(status='PASS_NATIVE_HOST_BUILD',command=command,
        source_sha256=sha(LOCAL/'contract_sources/kv_math.c'),header_sha256=sha(LOCAL/'contract_sources/kv_math.h'),
        dylib_sha256=sha(LOCAL/'flags_host.dylib'),actual_nice=os.getpriority(os.PRIO_PROCESS,0),no_camera_or_DAT=True))
    print('HOST MATH BUILT',sha(LOCAL/'flags_host.dylib'),flush=True)


if __name__=='__main__':main()
