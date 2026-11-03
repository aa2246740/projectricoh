"""Rebuild in an isolated local package; compare final artifact bytes."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard()
    builder=load(HERE/'build.py','probe3_rebuild')
    builder.HERE=HERE/'local/rebuild';builder.TMP=TMP/'rebuild'
    builder.PACKAGE=HERE/'local/rebuild/package'
    builder.main()
    results=[]
    for name in ('SD_ROOT/GXRCE.DAT','build/engine.bin','build/reloc.bin','build/trust.bin'):
        got=(builder.PACKAGE/'local'/name).read_bytes();wanted=(PACKAGE/'local'/name).read_bytes()
        assert got==wanted,name
        results.append(dict(file=name,bytes=len(got),sha256=sha(got)))
    assert (builder.HERE/'local/expected.json').read_bytes()==(HERE/'local/expected.json').read_bytes()
    save(HERE/'evidence/reproduce.json',dict(status='PASS',files=results,expected_bytes_equal=True))
    print(json.dumps(dict(status='PASS',byte_identical_files=len(results))))


if __name__=='__main__':main()
