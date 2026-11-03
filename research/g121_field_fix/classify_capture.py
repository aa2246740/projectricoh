"""Identify the observed device-register gap without changing its raw error."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,DAT,save,file_sha

for unit in ('50mm','28mm','mount'):
    name='field/121-'+unit+'-capture_exit.json'
    x=json.loads((OUT/name).read_text())
    assert x['dat_sha256']==file_sha(DAT)
    assert 'unmapped memory 0xf0218814/4' in x['error']
    assert "pc=540860652" in x['error']
    assert not x['failed_writes']
    x['status']='INCOMPLETE_DEVICE_REGISTER'
    x['scope']='The full-shutter prefix reached the unmodeled device register 0xf0218814 at native PC 0x203ce0ec. The raw traceback is retained.'
    save(name,x)
    summary='field/121-'+unit+'.json'
    y=json.loads((OUT/summary).read_text());y['status']='INCOMPLETE_CAPTURE';save(summary,y)
print('Classified three native device-register gaps; raw traces retained',flush=True)
