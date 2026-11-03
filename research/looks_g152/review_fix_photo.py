"""Complete the native parent transition before the closed-view photo case."""
from pathlib import Path
import argparse,json,sys,time,traceback
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import review_fix_checks as M
from native_support import H,snapshot
from dat_format import sha
def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','mount'),required=True);a=p.parse_args()
    events=[];original=M.exit_menu
    def completed_exit(cam,kind):
        original(cam,kind)
        if kind=='half':
            before=snapshot(cam);count=cam.h.u(0x2022f5ac,1)
            # Half-press handlers return before the parent view is built.
            # Run the same native parent transition used by the constructor.
            cam.h.parent();after=snapshot(cam)
            for field in ('rows','T','S','W'):assert after[field]==before[field],field
            assert cam.h.u(0x2022f5ac,1)==7
            assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\0'
            events.append(dict(rows_after_half=count,rows_after_native_parent=7,physical_state_unchanged=True,live_verified=0))
    M.exit_menu=completed_exit
    row=dict(status='STARTED',unit=a.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns());tick=time.monotonic()
    try:
        row.update(detail=M.changed_state(a.unit,'photo'),parent_transitions=events,status='PASS')
        assert len(events)==2
    except Exception:row.update(status='FAIL',error=traceback.format_exc(),parent_transitions=events);raise
    finally:
        row.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'review_fix/evidence'/('photo-corrected-'+a.unit+'.json')).write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(row),flush=True)
if __name__=='__main__':main()
