"""重新生成源码、构建和组包，逐字节比较关键产物。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BUILT=ROOT/'firmware/engine_v63_g154/candidate/local/full-r13'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    paths=[p for p in BUILT.iterdir() if p.is_file() and (p.suffix in ('.bin','.elf') or p.name in ('GXRCE.DAT','layout.json'))]
    for suffix in ('','_test'):
        base=ROOT/('firmware/package_v39_g154'+suffix)
        paths += [p for p in base.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='SHA256SUMS']
    source=ROOT/'firmware/engine_v63_g154'
    paths += [p for p in source.rglob('*') if p.is_file() and 'local' not in p.relative_to(source).parts]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def main():
    before=snapshot();assert len(before)>100;started=time.monotonic()
    for name in ('prepare','build','package'):
        path=HERE/(name+'.py');spec=importlib.util.spec_from_file_location('g154_reproduce_'+name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);module.main()
    after=snapshot();assert before==after,[p for p in before if before[p]!=after.get(p)]
    result=dict(status='PASS',seconds=time.monotonic()-started,compared=len(before),files=after)
    (HERE/'evidence/reproduce.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',compared=len(before),seconds=result['seconds'])))


if __name__=='__main__':main()
