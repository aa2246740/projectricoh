"""Require a completed foreground batch and no remaining test children."""
from pathlib import Path
import hashlib,json,sys,time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from controller_guard import controller_lease,workers
def main():
    phase=sys.argv[1];q=HERE/('queue-fix-'+phase+'.json')
    complete=HERE/'evidence'/('queue-fix-'+phase+'-complete.json')
    d=json.loads(complete.read_text());retired=[]
    if d['status']!='PASS':
        correction=json.loads((HERE/'review_fix/fixture_revision.json').read_text())
        retired=[r['job']['name'] for r in d['results'] if r['status']!='PASS']
        assert phase in ('native','retry') and retired and set(retired).issubset(correction['retired_jobs'])
        required={j['name'] for j in json.loads((HERE/'queue-fix-required.json').read_text())}
        assert not required.intersection(retired)
        for result in d['results']:
            if result['job']['name'] in retired:
                proof=json.loads((HERE/result['outputs'][0]['path']).read_text())
                assert proof['status']=='FAIL' and 'assert cam.h.u(0x2022f5ac,1)==7' in proof['error']
    jobs=json.loads(q.read_text())
    with controller_lease(jobs):
        remaining=workers({x['script'] for x in jobs});assert not remaining
        record=dict(status='PASS',phase=phase,complete_sha256=hashlib.sha256(complete.read_bytes()).hexdigest(),remaining=[],retired_fixture_attempts=retired,recorded_ns=time.time_ns())
        (HERE/'review_fix/evidence'/('handoff-'+phase+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
if __name__=='__main__':main()
