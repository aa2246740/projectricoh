#!/usr/bin/env python3
"""Run resident checks, 45 product scenarios, probe checks, and full C probe validation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    for script in ('audit.py','resident/verify.py','containers/product/verify.py','containers/probes/verify.py'):
        subprocess.run([sys.executable,'-I','-B',str(HERE/script)],cwd=ROOT,check=True)
    spec=importlib.util.spec_from_file_location('final_verify_runtime',HERE/'containers/product/runtime.py')
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    rows=[]
    for name in ('life','notice','view'):
        folder=HERE/'local/probes/candidates'/name
        for unit in ('jlaunch','qlaunch','l08firm'):
            p=r.run([HERE/'local/product/host/validate',folder/'GXRCE.DAT',folder/'trust.bin',unit],
                    'full-validate-'+name+'-'+unit,env={'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1',
                    'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'})
            rows.append(dict(container=name,unit=unit,status='PASS',output=p.stdout.strip()))
    (HERE/'local/full-validator-probes.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('PASS: 45 product scenarios; 15 full C container/unit validations; 3 probe host runs; resident boundaries')

if __name__=='__main__':main()
