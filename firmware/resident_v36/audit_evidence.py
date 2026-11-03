"""Check every reported product run against its raw log and final generation."""
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
BASE=HERE/'acceptance'
PHASES=('legacy','historical','behavior','faults','additional','reviewer','boundary','policy',
        'upgrade','first-frame','actual-upgrade','actual-pair')


def main():
    summaries={}
    for label,folder,phases,target in (
        ('r8',BASE/'local',PHASES,2638),
        ('r9',BASE/'local/r9-acceptance',PHASES+('power','migration'),2730)):
        total=0;hashes={};limited=0
        for phase in phases:
            path=folder/('run-'+phase+'.json')
            value=json.loads(path.read_text());assert value['status']=='PASS'
            assert len(value['cases'])==value['host_runs']
            assert sum(row['assertions'] for row in value['cases'])==value['assertions']
            for row in value['cases']:
                name=Path(row['log']).name
                log=folder/'logs'/name
                output=log.read_text();lines=output.rstrip().splitlines()
                assert lines[-1].startswith('OK '),(phase,name,lines[-1])
                observed=int(re.search(r'assertions=(\d+)',lines[-1])[1])
                assert observed==row['assertions'],(phase,name,observed,row['assertions'])
                assert 'FAIL scenario=' not in output
                if phase=='actual-upgrade' and label=='r9':
                    assert 'old_card_browse_writes=0' in output
                if row['status']=='LIMITATION_REPRODUCED':limited+=1
                row['log']=str(log.relative_to(BASE))
                hashes[str(log.relative_to(BASE))]=hashlib.sha256(log.read_bytes()).hexdigest()
            # Correct only stale log locations from the inherited R8 writer.
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
            total+=value['host_runs']
        assert total==target
        summaries[label]=dict(status='PASS',host_runs=total,unique_raw_logs=len(hashes),
            accepted_limitation_runs=limited,raw_log_sha256=hashes)
    (HERE/'local/recovery/evidence-audit.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print('PASS raw evidence: full-r8=2638 full-r9=2730 recorded assertion counts match logs')


if __name__=='__main__':main()
