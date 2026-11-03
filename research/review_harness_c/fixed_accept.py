"""Independent fixed g137 acceptance with output-only adaptation."""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, load, sha

parser=argparse.ArgumentParser()
parser.add_argument('side', choices=('python','c'))
parser.add_argument('--unit', default='50mm', choices=('50mm','28mm','mount'))
args=parser.parse_args()
enable()
out=HERE/'local'/('fixed-'+args.side+'-'+args.unit)
out.mkdir(parents=True, exist_ok=False)
os.environ['GXR_HARNESS_BACKEND']=args.side
sys.path.insert(0, str(ROOT/('tools/native_harness_c' if args.side=='c' else 'tools/native_harness')))
import python_backend
import harness, field_replay, product_execute, engine_bridge
backends=[]
original=python_backend.PythonBackend.__init__
def initialize(self):
    original(self)
    backends.append(self)
python_backend.PythonBackend.__init__=initialize
entry=load(HERE/'adapters/accept_g137.py', 'review_fixed_accept')
entry.HERE=out
entry.TAG=''
started=time.monotonic()
sys.argv=[str(HERE/'adapters/accept_g137.py'), args.unit]
entry.main()
result=json.loads((out/'local'/('accept-'+args.unit+'.json')).read_text())
assert result['generation']==137 and backends
emit(out/'result.json', result)
own=resource.getrusage(resource.RUSAGE_SELF)
child=resource.getrusage(resource.RUSAGE_CHILDREN)
emit(out/'metrics.json', dict(side=args.side, unit=args.unit, nice=os.getpriority(os.PRIO_PROCESS,0),
     wall_seconds=time.monotonic()-started, cpu_seconds=own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,
     instruction_count=sum(b.total_steps for b in backends),
     opcode_count=sum(sum(b.core.ops.values()) for b in backends),
     native_stats=[b.native_stats for b in backends if hasattr(b,'native_stats')],
     dat_sha256=sha(entry.DAT), entry_sha256=sha(HERE/'adapters/accept_g137.py')))
print(json.dumps(dict(side=args.side, instruction_count=sum(b.total_steps for b in backends), result='PASS')), flush=True)
