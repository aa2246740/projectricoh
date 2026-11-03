"""Check implementation receipts and result freshness; do not call this a rerun."""
from pathlib import Path
import collections
import datetime
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'research/g139_fix'
PIN='aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def timestamp(value):
    return datetime.datetime.fromisoformat(value).timestamp()

events=[json.loads(line) for line in (SOURCE/'evidence/runs.jsonl').read_text().splitlines()]
starts={row['name']:row for row in events if row['event']=='start'}
finishes={row['name']:row for row in events if row['event']=='finish'}
matrix=json.loads((SOURCE/'REGRESSIONS.json').read_text())
assert matrix['total']==len(matrix['rows'])==81
rows=[]
for row in matrix['rows']:
    receipt_path=SOURCE/row['receipt'];receipt=json.loads(receipt_path.read_text())
    assert receipt['returncode']==row['returncode']==0 and row['status']=='PASS'
    assert receipt['dat_sha256']==PIN and receipt['seconds']==row['seconds']
    log=ROOT/receipt['log']
    assert sha(log)==receipt['log_sha256'],log
    start,end=timestamp(starts[receipt['name']]['utc']),timestamp(finishes[receipt['name']]['utc'])
    assert end>=start and abs((end-start)-receipt['seconds'])<3
    expected=row.get('review_g138_seconds')
    assert row['contract']=='g139-current' or not expected or receipt['seconds']>=0.5*expected
    work=SOURCE/'run/local/jobs'/receipt['name']
    summaries=[]
    for path in work.rglob('result-*.json'):
        data=json.loads(path.read_text());mtime=path.stat().st_mtime
        assert start-2<=mtime<=end+2,(path,start,mtime,end)
        assert data['returncode']==0 and data['dat_sha256']==PIN,(path,data)
        summaries.append(dict(path=str(path.relative_to(ROOT)),mtime_ns=path.stat().st_mtime_ns,
                              sha256=sha(path),seconds=data.get('seconds'),observations=data.get('observations')))
    assert summaries,receipt['name']
    rows.append(dict(name=row['name'],receipt=str(receipt_path.relative_to(ROOT)),
                     receipt_sha256=sha(receipt_path),log_sha256=sha(log),seconds=receipt['seconds'],
                     start_utc=starts[receipt['name']]['utc'],end_utc=finishes[receipt['name']]['utc'],
                     result_summaries=summaries))
checks=[]
for path in sorted((SOURCE/'tests/local/checks').glob('*.json')):
    data=json.loads(path.read_text())
    assert data['status']=='PASS' and data['seconds']>0
    assert data['case']=='my-replay' or data['seconds']>10
    checks.append(dict(path=str(path.relative_to(ROOT)),status=data['status'],case=data['case'],unit=data['unit'],
                       seconds=data['seconds'],mtime_ns=path.stat().st_mtime_ns,sha256=sha(path),
                       reported_dat_sha256=data['dat_sha256'],
                       scope='native MY dispatcher without DAT menu load' if data['case']=='my-replay' else 'DAT menu path'))
assert len(checks)==82 and collections.Counter(row['unit'] for row in checks)=={'50mm':52,'28mm':15,'mount':15}
result=dict(status='PASS_RECORD_AUDIT',matrix_count=len(rows),current_contract_groups=12,
            new_check_count=len(checks),units=dict(collections.Counter(row['unit'] for row in checks)),
            independent_rerun=False,
            limitation='These are implementation records. OS exit and elapsed time do not replace inner assertions or an independent rerun. User-entry checks report the release hash in the original JSON although their source selects the test DAT; this review reruns selected checks with the test package as the default.',
            matrix=rows,checks=checks)
(HERE/'evidence/implementation-record-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:value for key,value in result.items() if key not in ('matrix','checks')}),flush=True)
