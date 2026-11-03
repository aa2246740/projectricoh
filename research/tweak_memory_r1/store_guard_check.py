"""Recheck the observed logical-capacity refusal with both instruction cores."""
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import load_snapshot, TEMP, sha


def main():
    os.environ['GXR_TWEAK_UNIT68_RESULT']='0'
    os.environ['GXR_TWEAK_POWER_COMPLETE']='1'
    trace=json.loads((HERE/'evidence/store-path-trace-r2.json').read_text())
    call=next(x for x in trace['rows'] if x['function']=='0x2009b6bc')
    source=ROOT/call['error_snapshot']['path']
    saved=load_snapshot(source)
    state=saved['cpu']
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    rows=[]
    for backend,Backend in [('c',PB.PythonBackend),('python',PB.PurePythonBackend)]:
        PB.CACHE=TEMP/'store-guard-check'/backend
        b=Backend()
        for at,raw,writable in state['regions']:b.map(at,raw,writable)
        for key in ['psw',*['r'+str(i) for i in range(16)],'spi','spu','bpc','bbpc','evb']:
            b.set_reg(key,state['registers'][key])
        for index,value in enumerate(call['args'],4):b.set_reg('r'+str(index),value)
        capacity=int.from_bytes(b.read(0x204b6b2c,4),'big')
        assert capacity==0 and call['args'][0]==22226
        S=int.from_bytes(b.read(0x200c0dac,4),'big')
        before=b.read(S,4096)
        stop=b.call(0x2009b6bc,[],0x7ffffff0,1000)
        assert stop.reason=='return' and b.get_reg('r0')==240 and b.read(S,4096)==before
        rows.append(dict(backend=backend,steps=stop.steps,result=240,logical_block=call['args'][0],
            observed_logical_block_count=capacity,complete_S_unchanged=True))
    result=dict(status='OPEN',recheck='PASS',layer='实际存储快照的 C/Python 原厂 helper 调用',
        rows=rows,snapshot=str(source),source_sha256=sha(source.read_bytes()),native_state_presets=[],
        boundary='The actual cold session has logical capacity zero. The original range guard returns 0xF0 before NAND programming. No capacity word or storage return is replaced.')
    path=HERE/'evidence/store-guard-check.json'
    assert not path.exists()
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
