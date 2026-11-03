#!/usr/bin/env python3
"""Run offline gates; retain the Stage2l stack comparison as measurement input."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local/verification'

def main():
    spec=importlib.util.spec_from_file_location('guard',HERE/'resident/build.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);b.preflight()
    LOCAL.mkdir(exist_ok=True);runs=[]
    jobs=['resident/verify.py','containers/product/verify.py','containers/probes/verify.py',
          'machine_checks.py','native_contract.py','audit.py','stack_checks.py',
          'regression.py','policy_machine.py','full_checks.py','scope_checks.py']
    for script in jobs:
        p=subprocess.run([sys.executable,'-I','-B',str(HERE/script)],cwd=ROOT,text=True,capture_output=True)
        name=script.replace('/','-');(LOCAL/(name+'.log')).write_text(p.stdout+p.stderr)
        runs.append(dict(script=script,returncode=p.returncode,log=str((LOCAL/(name+'.log')).relative_to(HERE))))
        (LOCAL/'runs.json').write_text(json.dumps(runs,indent=2)+'\n')
        print(script+': '+str(p.returncode),flush=True)
        if p.returncode:raise SystemExit(p.returncode)
    validator=HERE/'local/product/host/validate';validations=[]
    for name in ('life','notice','view'):
        folder=HERE/'local/probes/candidates'/name
        for unit in ('jlaunch','qlaunch','l08firm'):
            p=subprocess.run([str(validator),str(folder/'GXRCE.DAT'),str(folder/'trust.bin'),unit],cwd=ROOT,text=True,capture_output=True)
            (LOCAL/('validate-'+name+'-'+unit+'.log')).write_text(p.stdout+p.stderr)
            assert p.returncode==0,p.stderr
            validations.append(dict(container=name,unit=unit,status='PASS'))
    (LOCAL/'full-validator-probes.json').write_text(json.dumps(validations,indent=2)+'\n')
    stack=json.loads((HERE/'local/stack/comparison.json').read_text())
    result=dict(functional_machine_and_container_gates='PASS',probe_container_unit_validations=len(validations),
                stack_target_met=stack['all_targets_met'],camera_acceptance=False,body_image_generated=False,
                status='OFFLINE_PASS_HARDWARE_UNTESTED')
    (LOCAL/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
