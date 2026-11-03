"""Confirm the fast queue has exited before the matrix queue can start."""
from pathlib import Path
import hashlib,json,sys,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from controller_guard import controller_lease,workers
def main():
    jobs=json.loads((HERE/'queue-required.json').read_text())
    quick=json.loads((HERE/'evidence/queue-resume-quick-complete.json').read_text())
    assert quick['status']=='PASS' and quick['jobs']==19
    with controller_lease(jobs):
        active=workers({j['script'] for j in jobs});assert not active,active
        proof=dict(status='PASS',quick_status=quick['status'],quick_jobs=19,remaining_workers=active,
                   quick_summary_sha256=hashlib.sha256((HERE/'evidence/queue-resume-quick-complete.json').read_bytes()).hexdigest(),
                   recorded_ns=time.time_ns())
        (HERE/'evidence/phase_handoff.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))
if __name__=='__main__':main()
