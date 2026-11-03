"""Replay captured original WB setter inputs in C and Python without preset data."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import load_snapshot,TEMP,sha


def main():
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    for backend in ('c','python'):
        out=HERE/'evidence'/('r2-native-wb-setter-'+backend+'.json');assert not out.exists();rows=[]
        for name,value in [('r2-native-auto',0),('r2-native-auto-daylight',1)]:
            receipt=json.loads((HERE/'evidence'/(name+'.json')).read_text())
            calls=[r for r in receipt['native_setters'] if r['name']=='WB-preset' and r['value']==value]
            assert calls and receipt['camera_setting_writes_by_runner']==0
            source=ROOT/calls[-1]['input_snapshot']['path'];saved=load_snapshot(source);state=saved['cpu']
            assert sha(source.read_bytes())==calls[-1]['input_snapshot']['sha256']
            PB.CACHE=TEMP/'r2-wb-setter-check'/backend
            B=PB.PythonBackend if backend=='c' else PB.PurePythonBackend;b=B()
            for at,data,writable in state['regions']:b.map(at,data,writable)
            for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,state['registers'][key])
            S=int.from_bytes(b.read(0x200c0dac,4),'big');before=b.read(S,4096)
            assert b.get_reg('r4')==value and before[0x395]!=value
            stop=b.call(0x20266c58,[],0x7ffffff0,10000);assert stop.reason=='return'
            after=b.read(S,4096);expected=bytearray(before);expected[0x395]=value
            assert after==bytes(expected)
            rows.append(dict(source=name,input_snapshot_sha256=sha(source.read_bytes()),
                body_sha256=saved['body_sha256'],entry='0x20266c58',native_argument_register='r4',
                argument=value,WB_before=before[0x395],WB_after=after[0x395],only_changed_S_offset='0x395',
                WB_compensation_unchanged=True,record_40B_unchanged=True,complete_4096B_comparison=True,
                host_camera_setting_presets=[]))
        out.write_text(json.dumps(dict(status='PASS',backend=backend,rows=rows,
            layer='Captured native GPIO path inputs replayed in the original setter; no WB data were supplied by the runner.'),indent=2)+'\n')
        print(json.dumps(dict(status='PASS',backend=backend,cases=len(rows))),flush=True)


if __name__=='__main__':main()
