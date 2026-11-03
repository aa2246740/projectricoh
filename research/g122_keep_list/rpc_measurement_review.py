"""Review observed wire counts without claiming camera latency measurements."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,DAT,file_sha,save

rows=[]
for unit in ('50mm','28mm','mount'):
    for generation in (121,122):
        name='open-counts-'+str(generation)+'-'+unit+'.json'
        path=OUT/name
        if not path.exists():
            rows.append(dict(unit=unit,generation=generation,status='INCOMPLETE'));continue
        data=json.loads(path.read_text())
        if generation==122 and data['dat_sha256']!=file_sha(DAT):
            rows.append(dict(unit=unit,generation=generation,status='INCOMPLETE'));continue
        selected=[row for row in data['steps'] if row['operation'] in ('reopen_recipe','reopen_same_recipe')]
        assert len(selected)==2
        failures=0
        for row in selected:
            assert row['after']['rows']==8 and row['after']['cursor']==5 and row['W']==0
            assert row['RPC']==len(row['rpc_log'])
            for call in row['rpc_log']:
                failures+=not isinstance(call.get('result'),int) or not 0<=call['result']<=65535
        assert failures==0
        values=[row['RPC'] for row in selected]
        rows.append(dict(unit=unit,generation=generation,status='PASS',source=name,
            source_sha256=file_sha(path),observed_reopens=2,RPC=values,range=[min(values),max(values)],
            unsuccessful_RPC=failures,native_rows=8,confirmed_cursor=5))
save('rpc-measurement-review.json',dict(dat_sha256=file_sha(DAT),
    status='PASS' if all(r['status']=='PASS' for r in rows) else 'INCOMPLETE',records=rows,
    claim='Observed synchronous RPC call counts per completed native menu reopen. No camera latency or frame-time claim.',
    limiter='The former path reads every mapped row halfword. The final normal path reads T and one contained halfword from each of nine mapped rows.',
    repeatability='Two consecutive reopens per generation and unit in one official-constructor session. Five alternating latency trials were not run.',
    host_load='The host was busy; load average observed at 2026-10-28T06:21Z was 197.92 on ten logical CPUs. Host elapsed times are not reported as camera times.',
    measured_scope='Slot-8 X/V/W calls only. Native constructor, selected row, W=0, call results and returned list are checked. Device traffic inside preview is outside the model.',
    latency_verdict='INCOMPLETE: physical camera open latency was not measured.'))
print('Reviewed RPC counts',len(rows),flush=True)
