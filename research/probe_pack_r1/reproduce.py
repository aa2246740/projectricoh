"""Rebuild the final DAT and compare the actual delivered and linked bytes."""
from pathlib import Path
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard()
    paths=[PACKAGE/'local/SD_ROOT/GXRCE.DAT',PACKAGE/'local/build/engine.bin',
           PACKAGE/'local/build/reloc.bin',PACKAGE/'local/build/trust.bin',HERE/'local/expected.json']
    before={str(p.relative_to(ROOT)):p.read_bytes() for p in paths}
    runpy.run_path(str(HERE/'build.py'),run_name='__main__')
    after={str(p.relative_to(ROOT)):p.read_bytes() for p in paths}
    assert before==after
    result=dict(status='PASS',byte_identical=[dict(path=p,bytes=len(data),sha256=sha(data)) for p,data in before.items()])
    save(HERE/'evidence/reproduce.json',result)
    print(__import__('json').dumps(result))


if __name__=='__main__':main()
