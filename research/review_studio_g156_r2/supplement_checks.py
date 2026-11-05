"""Supplement checks blocked by read-only frontend outputs and compare regression tests with r1."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_checks import run, STUDIO

def frontend():
    source=STUDIO/'frontend'
    dest=HERE/'tmp/frontend'
    shutil.copytree(source,dest,symlinks=True,ignore=shutil.ignore_patterns('.vite-temp'),dirs_exist_ok=True)
    rows=[]
    for path in source.rglob('*'):
        relative=path.relative_to(source)
        if not path.is_file() or 'node_modules' in relative.parts:
            continue
        content=path.read_bytes()
        assert (dest/relative).read_bytes()==content
        rows.append(dict(path=str(relative),sha256=hashlib.sha256(content).hexdigest()))
    (HERE/'evidence/frontend-copy.json').write_text(json.dumps(dict(source=str(source),copy=str(dest),files=rows),indent=2)+'\n')
    code=("import importlib.util; spec=importlib.util.spec_from_file_location('checker',"+repr(str(STUDIO/'scripts/check_frontend.py'))+
          "); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.FRONTEND=m.Path("+repr(str(dest))+
          "); raise SystemExit(m.main())")
    run('frontend-copy',['python','-B','-c',code])

def regression():
    py=str(STUDIO/'.venv/bin/python')
    selection='parse_rejects_g156_engine or pack_rejects_g156_engine or inspect_rejects_g156_engine or pack_binds_all'
    run('new-22-regressions',[py,'-I','-B','-m','pytest','-q','tests/test_g156.py','-k',selection])
    # Only substitute the previous codec in memory. The new tests and intake source stay unchanged.
    code=("import sys;sys.path.insert(0,"+repr(str(HERE))+
          ");import pytest;raise SystemExit(pytest.main(['-q','tests/test_g156.py','-k',"+repr(selection)+",'-p','old_codec_plugin']))")
    run('old-22-regressions',[py,'-I','-B','-c',code],extra={
        'PYTEST_ADDOPTS':f'--force-reruns 0 --maxfail=30 --basetemp={HERE}/tmp/pytest-old-22 --ignore=tests/test_gpu_parity.py'})

if __name__=='__main__':
    if sys.argv[1]=='frontend':frontend()
    else:regression()
