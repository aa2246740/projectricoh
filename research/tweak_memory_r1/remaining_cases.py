"""Run bounded retained-session cases with one worker and separate receipts."""
import argparse
import datetime
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from repro_flow import phase


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lane', choices=('mount', 'units'), required=True)
    p.add_argument('--after-build', action='store_true')
    p.add_argument('--attempt', type=int, default=1)
    a = p.parse_args()
    rows = []
    receipt = HERE/'evidence'/('remaining-'+a.lane+('-resume'+str(a.attempt) if a.after_build else '')+'-flow.json')
    assert not receipt.exists()
    try:
        if a.lane == 'mount':
            if not a.after_build:
                phase('menu_recheck.py', [], 'menu-ok-recheck-run', rows)
                phase('store_result_check.py', [], 'store-result-check-run', rows)
                phase('build.py', ['--boot', 1, '--release-auto'], 'build-release-auto-run', rows)
            suffix = 'envelope-check-r'+str(a.attempt) if a.after_build else 'envelope-check'
            phase('envelope_check.py', ['--name', suffix], suffix+'-run', rows)
            phase('case_flow.py', ['--case', 'mount-look', '--cycles', 1, '--adjust-one',
                '--resume-init', HERE/'local/g155c-mount-builtin-choose-final.pkl.z'], 'remaining-mount-look-run', rows)
            phase('case_flow.py', ['--case', 'mount-user', '--cycles', 1, '--adjust-one',
                '--resume-init', HERE/'local/g155c-mount-builtin-choose-final.pkl.z'], 'remaining-mount-user-run', rows)
            phase('old_reject.py', [], 'remaining-old-reject-run', rows)
        else:
            source = HERE/'local/gate-cross-unit-session.pkl.z'
            if not source.exists():
                source = HERE/'local/g155c-28mm-builtin-init-session.pkl.z'
            phase('case_flow.py', ['--case', '28mm-builtin', '--cycles', 1, '--adjust-one',
                '--prefix', 'g155c-28mm-builtin-r2', '--resume-init', source], 'remaining-28mm-run', rows)
            phase('case_flow.py', ['--case', '50mm-builtin', '--cycles', 1, '--adjust-one'], 'remaining-50mm-run', rows)
    finally:
        receipt.write_text(json.dumps(dict(phases=rows, ended=datetime.datetime.now(datetime.timezone.utc).isoformat()), indent=2)+'\n')


if __name__ == '__main__':
    main()
