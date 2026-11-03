"""Rebuild into a separate new-tree output, preserving the tested candidate."""
from pathlib import Path
import importlib.util
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,sha,save

def main():
    candidate=ROOT/'firmware/engine_v40_ux/candidate'
    sys.path.insert(0,str(candidate))
    sys.modules.pop('common',None)
    spec=importlib.util.spec_from_file_location('rebuild119',candidate/'build119.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.c.LOCAL=candidate/'local/reproduced119'
    module.service_build.LOCAL=module.c.LOCAL/'resident'
    module.main()
    results={}
    for name in ('GXRCE.DAT','engine.elf','engine.bin','reloc.bin'):
        a=(candidate/'local/full-r13'/name).read_bytes()
        b=(module.c.LOCAL/'full-r13'/name).read_bytes()
        assert a==b,name
        results[name]=dict(equal=True,sha256=sha(a),bytes=len(a))
    save('reproducibility.json',dict(status='PASS',files=results,default_v36_trust=True))
    print('PASS independently rebuilt output bytes equal final candidate',flush=True)

if __name__=='__main__':main()
