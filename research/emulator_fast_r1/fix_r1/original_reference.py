"""Independent original batch-directory sanity check, without source edits."""
import argparse
import json
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
p=argparse.ArgumentParser()
p.add_argument('--name',default='original-main-10m-02')
a=p.parse_args()
R.setup('reference')
ORIGINAL=R.ROOT/'tools/gxr_emulator_batch'
sys.path.insert(0,str(ORIGINAL))
import backend
assert Path(backend.__file__).resolve().parent==ORIGINAL
original_init=backend.Backend.__init__
def init(self,*args,**kwargs):
    original_init(self,*args,**kwargs)
    # Host-side observation adapters only. The original run loop and device
    # transitions remain the functions loaded from the original directory.
    self.model_revision=[]
    self.materialize_native=lambda:None
    self._native_driver=None
    self.library_path=ORIGINAL/'build/libgxr_m32r.dylib'
    self.backend_kind='original-reference'
backend.Backend.__init__=init
signal.alarm(300)
ctx=R.construct('main','original-main-10m-01')
c=ctx.machine.cpu
if not hasattr(c,'_observer_owners'):
    c._observer_owners=[ctx.machine.observer]
try:
    wall=time.perf_counter()
    cpu=time.process_time()
    stop=c.run(10000000)
    c.materialize_native()
    seconds=time.perf_counter()-wall
    cpu_seconds=time.process_time()-cpu
    result={'stop':stop.to_dict(),'steps':c.steps,'state':json.loads(json.dumps(R.fingerprint(ctx))),
            'seconds':seconds,'cpu_seconds':cpu_seconds,
            'original_modules':{k:str(Path(sys.modules[k].__file__).resolve()) for k in
                ('backend','devices','storage_run','board','peripherals','panel','sdcard','observe')},
            'library_sha256':R.sha(c.library_path.read_bytes())}
    benchmark=json.loads((R.RUNS/'benchmark-02.json').read_text())
    expected=benchmark['pairs'][0]['records']['native']['fingerprint']
    result['same_as_native']=result['state']==expected
    result['different_fields']=[k for k in expected if expected[k]!=result['state'].get(k)]
    target=R.RUNS/(a.name+'.json')
    assert not target.exists()
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('steps','same_as_native','different_fields','library_sha256')}))
finally:
    ctx.machine.close()
    signal.alarm(0)
