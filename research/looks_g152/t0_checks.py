"""Run the unchanged startup-T case against the current final DAT."""
from pathlib import Path
import argparse,json,sys,time,traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import regressions as R
from apply_checks import ui_audit
from dat_format import sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',required=True,choices=('50mm','mount'));a=p.parse_args()
    made=[];original=R.H.Camera
    def camera(*args,**kwargs):
        cam=original(*args,**kwargs);made.append(cam);return cam
    R.H.Camera=camera
    row=dict(unit=a.unit,dat_sha256=sha(R.H.DAT.read_bytes()),started_ns=time.time_ns());tick=time.monotonic()
    try:
        row['details']=R.G.CASES['t-boot'](a.unit)
        row.update(status='PASS',native_UI_audits=[ui_audit(c) for c in made])
    except Exception:
        row.update(status='FAIL',error=traceback.format_exc(),frames=[c.state() for c in made]);raise
    finally:
        row.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'evidence'/('t0-'+a.unit+'.json')).write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(row),flush=True)
if __name__=='__main__':main()
