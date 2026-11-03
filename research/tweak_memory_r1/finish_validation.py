"""Run the remaining bounded lanes without adding concurrent workers."""
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
    p.add_argument('--lane', choices=('units', 'mount'), required=True)
    a = p.parse_args()
    rows = []
    receipt = HERE/'evidence'/('finish-'+a.lane+'-flow.json')
    assert not receipt.exists()
    result = dict(status='RUNNING', phases=rows)
    def run(script, args, name):
        phase(script, args, name, rows)
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    try:
        if a.lane == 'units':
            run('case_flow.py', ['--case','50mm-builtin','--cycles',1,'--adjust-one',
                '--prefix','final50'], 'final50-full-run')
            run('old_reject.py', [], 'old-body-new-test-full-run')
        else:
            run('case_flow.py', ['--case','mount-user','--cycles',1,'--adjust-one',
                '--prefix','finaluser','--resume-init',HERE/'local/g155c-mount-builtin-choose-final.pkl.z'],
                'finaluser-full-run')
            run('gates.py', ['--case','zero'], 'gate-zero-full-run')
        result['status'] = 'PASS'
    except BaseException as exc:
        result.update(status='OPEN', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        result['ended'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
