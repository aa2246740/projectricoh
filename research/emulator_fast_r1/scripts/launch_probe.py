"""Verify preloading survives a caller's original import-path insertion."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/gxr_emulator_batch'))
import backend
assert Path(backend.__file__).resolve().parent==ROOT/'tools/gxr_emulator_fast'
cpu=backend.Backend(mode='fast')
try:
    cpu.map(0x1000,bytes.fromhex('70007000')*4)
    cpu.set_reg('pc',0x1000);cpu.set_batch(True);stop=cpu.run(4)
    assert stop.reason=='max_steps' and cpu.steps==4 and cpu.get_reg('pc')==0x1008
    result=dict(backend=cpu.backend_kind,library=str(cpu.library_path),stop=stop.to_dict(),passed=True)
    (ROOT/'research/emulator_fast_r1/runs'/('launch-'+sys.argv[1]+'.json')).write_text(json.dumps(result,indent=2)+'\n')
finally:cpu.close()
