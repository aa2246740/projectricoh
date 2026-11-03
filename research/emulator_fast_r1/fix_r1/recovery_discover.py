"""Locate the recovery confirmation boundary with all four model revisions."""
import json
from pathlib import Path
import signal
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
R.setup('native','nand-word,preview-link,sd-long-response,nand-read-tail')
signal.alarm(600)
import snapshots as S
ctx=R.construct('recovery','recovery-discover-01')
m,c=ctx.machine,ctx.machine.cpu
body=R.ROOT/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3'
R.load_body(m,body)
m.devices['serial'].input_bytes[0]=(2,2)
ctx.inputs=S.Inputs(**dict(ctx.inputs.values,body=body,flow=Path(__file__),serial_boot_input=[2,2]))
del ctx.identity_bound
ctx.identity_bound=S.identity(ctx)
def done(current):
    return True
R.tagged(c,0x2036c9e4,done,[('reg-stop',dict(register=0,mask=0,value=0))])
rec={'rows':[],'status':'RUNNING'}
try:
    for _ in range(10):
        stop=c.run(50000000)
        c.materialize_native()
        row={'steps':c.steps,'pc':hex(c.get_reg('pc')),'stop':stop.to_dict(),
             'ui_initializers':m.observer.ui_initializers,'sd_counts':dict(m.sd.counts),
             'nand_pages':len(m.devices['nand'].pages)}
        rec['rows'].append(row)
        (R.RUNS/'recovery-discover-01.json').write_text(json.dumps(rec,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        if stop.reason!='max_steps':
            break
    rec['snapshot']=S.save(ctx,R.HERE/'recovery-discover-01.snap.z')
    rec['fingerprint']=R.fingerprint(ctx)
    rec['native']=c._native_driver.stats()
    rec['status']='COMPLETE'
finally:
    (R.RUNS/'recovery-discover-01.json').write_text(json.dumps(rec,indent=2)+'\n')
    m.close()
    signal.alarm(0)
