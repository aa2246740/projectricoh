"""Serialize the actual post-B settings as a native checksummed read source."""
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard()
    raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    cases=[]
    for unit,name in (('mount','m-owner-c-final'),('50mm','j-owner-c-final'),('28mm','q-owner-c-final')):
        folder=HERE/'local/native'/name
        evidence=json.loads((folder/'result.json').read_text())
        assert evidence['status']=='PASS' and evidence['dat_sha256']==sha(raw)
        original=(folder/'7-B-S.bin').read_bytes();assert len(original)==4096
        checksum=sum(struct.unpack('>2046H',original[:4092]))&0xffffffff
        data=original[:4092]+checksum.to_bytes(4,'big')
        assert data[:4092]==original[:4092]
        out=HERE/'local/restart-inputs'/(unit+'.bin');out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(data)
        cases.append(dict(unit=unit,source=str((folder/'7-B-S.bin').relative_to(ROOT)),
            post_B_sha256=sha(original),serialized_sha256=sha(data),payload_4092_unchanged=True,
            original_checksum_valid=int.from_bytes(original[-4:],'big')==checksum,
            changed_offsets=[i for i in range(4096) if data[i]!=original[i]],
            native_record_zero=data[0xfd4:0xffc]==bytes(40)))
    result=dict(status='PASS',dat_sha256=sha(raw),cases=cases,
        scope='Declared persistent I/O input from actual host B state; only the native container checksum is serialized.')
    save(HERE/'evidence/restart-inputs.json',result);print(json.dumps(result))


if __name__=='__main__':main()
