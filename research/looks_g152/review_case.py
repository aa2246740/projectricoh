"""Run one unchanged review case with its actual Camera DAT identity."""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import regressions as R
from dat_format import sha
from apply_checks import ui_audit

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=tuple(R.REVIEW.CASES))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True);args=p.parse_args()
    result=dict(case=args.case,unit=args.unit,started_ns=time.time_ns());tick=time.monotonic()
    try:
        cam,detail=R.REVIEW.CASES[args.case](args.unit)
        result.update(status='PASS',dat_path=str(cam.dat_path),dat_sha256=sha(cam.dat_path.read_bytes()),
                      details=detail,native_UI_audit=ui_audit(cam))
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'evidence'/f'review-{args.case}-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='details'}),flush=True)

if __name__=='__main__':main()
