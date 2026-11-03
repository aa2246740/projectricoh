#!/usr/bin/env python3
"""Run all task-owned host probes, then seal hashes from the repository root."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collect


def run(argv,name):
    env = dict(os.environ, TMPDIR=str(collect.OUT/'tmp'), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(x) for x in argv],cwd=collect.ROOT,env=env,text=True,capture_output=True)
    (collect.OUT/(name+'.stdout')).write_text(result.stdout)
    (collect.OUT/(name+'.stderr')).write_text(result.stderr)
    assert result.returncode==0,(name,result.stderr)
    print(name,result.stdout.strip())


def service():
    source=collect.ROOT/'firmware/engine_v38_b36/candidate/engine_services/services.c'
    text=source.read_text()
    prefix=text[:text.index('static RvUiSnapshot *ui_prepare')]
    assert prefix.endswith('}\n')
    (collect.OUT/'storage_prefix.inc').write_text(prefix)
    collect.save('service-source.json',dict(source=str(source.relative_to(collect.ROOT)),sha256=collect.sha(source),
                                          extracted_bytes=len(prefix.encode()),extraction='verbatim prefix before ui_prepare',
                                          stub_boundary='session, range, context, and all native I/O'))
    clang='/usr/bin/clang'
    run([clang,'-std=c11','-O1','-DRV_HOST','-fsanitize=address,undefined','-fno-omit-frame-pointer',
         '-Wno-unused-function','-I',source.parent,'-I',collect.OUT,HERE/'host_service.c',
         '-o',collect.OUT/'host_service'],'host-service-compile')
    run([collect.OUT/'host_service'],'host-service')


def hashes():
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'
                   and '__pycache__' not in p.parts and 'tmp' not in p.relative_to(HERE).parts)
    lines = [collect.sha(p)+'  '+str(p.relative_to(collect.ROOT)) for p in files]
    (HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print('SHA256SUMS',len(lines),'repository-relative files')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seal-only',action='store_true')
    ap.add_argument('--full',action='store_true',help='regenerate static windows, excerpts and the S candidate census')
    args=ap.parse_args()
    collect.preflight()
    (collect.OUT/'tmp').mkdir(exist_ok=True)
    if not (collect.OUT/'protected-before.json').exists():
        assert not args.seal_only, 'run full verification before sealing a new output directory'
        run(['/usr/bin/python3','-I','-B',HERE/'collect.py','before'],'protected-before')
    if not args.seal_only:
        if args.full:
            for command,script in ((['windows'],'collect.py'),([], 'evidence.py'),([], 'settings_census.py')):
                run(['/usr/bin/nice','-n','10','/usr/bin/python3','-I','-B',HERE/script,*command],script[:-3])
        service()
        for name in ('host_native','storage_model'):
            run(['/usr/bin/nice','-n','10','/usr/bin/python3','-I','-B',HERE/(name+'.py')],name)
        for path in HERE.glob('*.py'):
            ast.parse(path.read_text(),filename=str(path))
        run(['/usr/bin/python3','-I','-B',HERE/'collect.py','after'],'protected-after')
    hashes()


if __name__=='__main__':
    main()
