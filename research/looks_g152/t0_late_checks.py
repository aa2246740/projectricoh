"""Check a stable T=0 initial unit state through late-BUSY compensation."""
from pathlib import Path
import argparse,inspect,json,sys,time,traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import unverified_checks as U

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',required=True,choices=('50mm','mount'));a=p.parse_args()
    source=inspect.getsource(U.contract_case)
    before="    P.set_unit_rows(cam,source);cam.put_s"
    after="    source=bytearray(source);source[445:447]=bytes(2);source=bytes(source)\n    P.set_unit_rows(cam,source);cam.put_s"
    assert source.count(before)==1
    exec(compile(source.replace(before,after),str(HERE/'t0_late_checks.py')+':T0-input','exec'),vars(U))
    row=dict(unit=a.unit,dat_sha256=U.sha(U.H.DAT.read_bytes()),started_ns=time.time_ns(),
             scope='The existing unverified first-transaction contract with only initial T changed to 0; original row bytes and S=4 retained.')
    tick=time.monotonic()
    try:
        row['details']=U.contract_case(a.unit,'builtin-effect','late','ok')
        assert row['details']['before']['T']==row['details']['after']['T']==0
        assert not row['details']['S_stores']
        assert row['details']['before']['S_sha256']==row['details']['after']['S_sha256']
        row['status']='PASS'
    except Exception:row.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        row.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'evidence'/('t0-late-'+a.unit+'.json')).write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(row),flush=True)
if __name__=='__main__':main()
