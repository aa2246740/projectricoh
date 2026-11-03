"""Serialize actual post-probe settings; only native SUM16 trailer is updated."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard();raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();cases=[]
    for unit,prefix in [('mount','m'),('50mm','j'),('28mm','q')]:
        folder=HERE/'local/native'/(prefix+'-final-owner-c');result=json.loads((folder/'result.json').read_text())
        assert result['status']=='PASS' and result['dat_sha256']==sha(raw)
        inputs=[]
        for path in sorted(folder.glob('*-S.bin'),key=lambda p:int(p.name.split('-')[0])):
            if '-A-' in path.name:continue
            b=path.read_bytes();assert len(b)==4096 and b[0xfd4:0xffc]==bytes(40)
            serialized=b[:4092]+(sum(struct.unpack('>2046H',b[:4092]))&0xffffffff).to_bytes(4,'big')
            inputs.append(dict(file=str(path.relative_to(ROOT)),original_sha256=sha(b),serialized_sha256=sha(serialized),
                payload_4092_unchanged=True,changed_offsets=[i for i in range(4096) if b[i]!=serialized[i]]))
        assert inputs
        assert len({r['serialized_sha256'] for r in inputs})==1,'different saved settings require separate cold boots'
        original=Path(ROOT/inputs[-1]['file']).read_bytes()
        serialized=original[:4092]+(sum(struct.unpack('>2046H',original[:4092]))&0xffffffff).to_bytes(4,'big')
        target=HERE/'local/restart-inputs'/(unit+'.bin');target.parent.mkdir(exist_ok=True);target.write_bytes(serialized)
        cases.append(dict(unit=unit,all_post_probe_inputs=inputs,equivalent_sources=len(inputs),
            restart_source=str(target.relative_to(ROOT)),serialized_sha256=sha(serialized)))
    save(HERE/'evidence/restart-inputs.json',dict(status='PASS',dat_sha256=sha(raw),cases=cases,
        scope='Logical native persistence-read source; actual physical power-loss/NAND timing is outside this model.'))
    print(json.dumps(dict(status='PASS',units=3,post_probe_settings=sum(r['equivalent_sources'] for r in cases))))


if __name__=='__main__':main()
