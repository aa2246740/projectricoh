"""Bounded final replay and MOUNT evidence refresh after all solver jobs stop."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON='/opt/homebrew/bin/python3'


def run(script,*args):
    command=['nice','-n','15',PYTHON,'-I','-B',str(HERE/script),*args]
    print('FINAL STAGE',script,' '.join(args),flush=True)
    subprocess.run(command,cwd=ROOT,check=True,timeout=1500)


def pair(commands):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run,*command) for command in commands]
        for future in futures:future.result()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('canonical','replay','mount','quantize','report'))
    args=ap.parse_args()
    if args.stage=='canonical':
        for unit in ('mount-a12','a12-50','a12-28'):
            run('canonicalize_common.py','--unit',unit,'--tag','shared_mode_final_lens_r5')
    elif args.stage=='replay':
        def scopes():
            run('mount_L1_domain.py')
            run('ramp_scope.py')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run,'verify.py'),pool.submit(scopes)]
            for job in jobs:job.result()
    elif args.stage=='mount':
        run('prepare_holdout_bank.py','--tag','mount_L1_before_new7_lens_r5')
        run('new7_holdout.py','--level','1','--tag','lens_r5','--bank','local/mount_L1_before_new7_lens_r5/candidate_registry.json')
        run('verify_new7.py','--level','1','--tag','lens_r5')
    elif args.stage=='quantize':
        for ranges in (('0:9','9:18'),('18:27','27:35')):
            pair([('mount_bracket_sensitivity.py','--stage','quantize','--indices',span,'--tag','bracket_rounding_lens_r5') for span in ranges])
        run('mount_bracket_sensitivity.py','--stage','summarize','--tag','bracket_rounding_lens_r5')
    else:
        run('confirmation.py','summarize')
        run('provenance_review.py')
        run('final_report.py')


if __name__=='__main__':main()
