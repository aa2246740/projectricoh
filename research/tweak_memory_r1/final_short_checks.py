"""Run final-artifact short checks serially in one test process."""
import json
import argparse
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from repro_flow import phase


def main():
    p=argparse.ArgumentParser();p.add_argument('--from-artifact',action='store_true');p.add_argument('--label',default='final');a=p.parse_args()
    rows=[]
    checks=[('release_check.py',[],'final-release-check-run'),
        ('mode_gate_check.py',['--prefix','p1final-init-r2','--name','final-qualification','--entry','eng_boot_check'],'final-qualification-run'),
        ('artifact_audit.py',[],'final-artifact-audit-run'),
        ('source_audit.py',[],'final-source-audit-run'),
        ('envelope_check.py',['--name','p1final-envelope'],'final-envelope-run')]
    if a.from_artifact:checks=checks[2:]
    try:
        for script,args,name in checks:phase(script,args,name+'-'+a.label,rows)
    finally:
        (HERE/'evidence'/('final-short-checks-'+a.label+'.json')).write_text(json.dumps(rows,indent=2)+'\n')


if __name__=='__main__':main()
