"""Copy build and Host drivers, changing only output routing and the guard."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TREE=HERE/'isolated'
CAND=TREE/'candidate'

def main():
    assert not CAND.exists(), 'already prepared'
    original=ROOT/'firmware/engine_v37'
    shutil.copytree(original/'candidate', CAND, ignore=shutil.ignore_patterns('local','__pycache__'))
    shutil.copytree(original/'resident',TREE/'resident',ignore=shutil.ignore_patterns('local','__pycache__'))
    (TREE/'baseline/engine_services').mkdir(parents=True)
    shutil.copyfile(original/'baseline/engine_services/native_seed.c',TREE/'baseline/engine_services/native_seed.c')
    (TREE/'baseline/engine_services/engine_services.h').write_text((original/'baseline/engine_services/engine_services.h').read_text())
    local=CAND/'local';local.mkdir()
    for name in ('native_seed_model.h','native_enum.h','native_get_mode.h'):
        shutil.copyfile(original/'candidate/local'/name,local/name)
    common=CAND/'common.py';text=common.read_text()
    text=text.replace('ROOT = HERE.parents[2]', 'ROOT = Path('+repr(str(ROOT))+')')
    start=text.index('def guard():');end=text.index('\ndef freeze_check():',start)
    text=text[:start]+'''def guard():
    assert HERE == Path('''+repr(str(CAND))+''')
    LOCAL.resolve().relative_to(Path('''+repr(str(HERE))+'''))
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)

'''+text[end:]
    common.write_text(text)
    # Keep GCC's original random-seed text so copied paths do not change LTO identity.
    service=CAND/'service_build.py';text=service.read_text()
    text=text.replace("'-frandom-seed='+str(src.relative_to(c.ROOT))", "'-frandom-seed='+str(src.relative_to(c.ROOT)).replace('research/review_v35_container/isolated/candidate/', 'firmware/engine_v37/candidate/')")
    service.write_text(text)
    changes=[]
    for p in sorted(CAND.rglob('*')):
        rel=p.relative_to(CAND);src=original/'candidate'/rel
        if not p.is_file() or not src.is_file() or 'local' in rel.parts: continue
        if p.read_bytes()!=src.read_bytes():
            changes.extend(difflib.unified_diff(src.read_text().splitlines(True),p.read_text().splitlines(True),fromfile=str(src.relative_to(ROOT)),tofile=str(p.relative_to(HERE))))
    (HERE/'routing.patch').write_text(''.join(changes))
    (HERE/'copied-sources.json').write_text(json.dumps({str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(TREE.rglob('*')) if p.is_file()},indent=2)+'\n')
    print('PASS isolated source copy; routing changes only in common.py and service_build.py')

if __name__=='__main__':main()
