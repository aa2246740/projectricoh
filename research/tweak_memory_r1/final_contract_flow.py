"""Run the added contract checks serially after the first successful final cold."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from repro_flow import phase


def run(prefix,settings):
    rows=[];out=HERE/'evidence/final-contract-flow.json';assert not out.exists()
    try:
        phase('mode_gate_check.py',['--prefix',prefix,'--name','final-transaction-contract','--entry','boot_run'],
            'final-transaction-contract-run',rows)
        phase('final_fault_guard.py',['--source',HERE/'local'/(prefix+'-boot_run.pkl.z'),
            '--name','final-guard-check'],'final-guard-check-run',rows)
        phase('no_dat_recovery.py',['--name','final-noDAT-recovery','--settings',settings,
            '--guard-receipt',HERE/'evidence/final-guard-check.json'],'final-noDAT-recovery-run',rows)
    finally:out.write_text(json.dumps(rows,indent=2)+'\n')
