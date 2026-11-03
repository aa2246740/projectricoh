"""Check physical state across the native half-press and next constructor."""
from pathlib import Path
import argparse,hashlib,inspect,json,sys,time,traceback
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import review_fix_checks as M
from native_support import H,snapshot
from dat_format import sha
def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','mount'),required=True);a=p.parse_args()
    source=inspect.getsource(M.changed_state)
    assumption='    assert cam.h.u(0x2022f5ac,1)==7\n'
    assert source.count(assumption)==1
    executed=source.replace(assumption,"    assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\0'\n")
    exec(compile(executed,str(HERE/'review_fix_photo_v3.py')+':half-contract','exec'),vars(M))
    events=[];original=M.exit_menu
    def checked_exit(cam,kind):
        before=snapshot(cam);original(cam,kind);after=snapshot(cam)
        if kind=='half':
            for field in ('rows','T','S','W'):assert after[field]==before[field],field
            assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\0'
            events.append(dict(rows_metadata_after_half=cam.h.u(0x2022f5ac,1),physical_state_unchanged=True,
                               live_verified=0,native_state=cam.h.state()))
    M.exit_menu=checked_exit
    row=dict(unit=a.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns(),
             shared_function_sha256=sha(source.encode()),executed_function_sha256=sha(executed.encode()),
             correction='The closed-boundary contract is rows/T/full S/W and expired qualification. Row-count metadata after the native half-press is observed, not used as a view-ownership assertion.')
    tick=time.monotonic()
    try:
        row.update(detail=M.changed_state(a.unit,'photo'),half_transitions=events,status='PASS');assert len(events)==2
    except Exception:row.update(status='FAIL',error=traceback.format_exc(),half_transitions=events);raise
    finally:
        row.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'review_fix/evidence'/('photo-final-'+a.unit+'.json')).write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
if __name__=='__main__':main()
