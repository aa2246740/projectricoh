"""Derive measured navigation costs; do not turn modeled RTT into a timing fact."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DAT=ROOT/'firmware/engine_v39_ux/candidate/local/full-r13/GXRCE.DAT'

def main():
    identity=hashlib.sha256(DAT.read_bytes()).hexdigest()
    groups=defaultdict(list);units=[];faults=[]
    for unit in ('50mm','28mm','mount'):
        report=json.loads((HERE/'local/runs'/('matrix-'+unit+'.json')).read_text())
        assert report['status']=='PASS' and report['dat_sha256']==identity
        # A compensated cursor must also prime native navigation, so the
        # very next key moves one row rather than repeating the old row.
        first=report['adj']['moves']
        assert len(first)==1 and first[0]['before']['cursor']==4 and first[0]['after']['cursor']==3
        measured=json.loads((HERE/'local/runs'/('perf-'+unit+'.json')).read_text())
        assert measured['status']=='PASS' and measured['dat_sha256']==identity
        steps=measured['moves']
        for step in steps:
            assert step['rpc_errors']==0 and step['refreshes']==1
            assert step['crc_accelerated_calls']==0
            assert not any(step['after']['file_mutations'].values())
            before,after=step['before']['cursor'],step['after']['cursor']
            groups[(before,after)].append(dict(unit=unit,**step))
        units.append(dict(unit=unit,measured_moves=len(steps),functional_fast_moves=len(report['fast_moves']),status=report['status'],
                          file_mutations=report['counters'],
                          dat_sha256=report['dat_sha256']))
        for name,case in [('cold',report['cold_failure']),('fallback04',report['fallback04'])]+[
                ('confirmed03-'+str(i),case) for i,case in enumerate(report['faults'])]+[
                ('fn2',report['fn2'])]:
            s=case['step'];faults.append(dict(unit=unit,case=name,
                rpc_calls=s['rpc_calls'],write_bytes=s['unit_write_bytes'],
                functional_runner_cycle_model=s['base_cycle_model'],
                crc_accelerated_calls=s['crc_accelerated_calls'],restored_row=s['after']['cursor']))
    table=[]
    for (a,b),steps in sorted(groups.items()):
        def bounds(key):return [min(s[key] for s in steps),max(s[key] for s in steps)]
        instr=[s['instruction_counts']['instructions'] for s in steps]
        cycles=bounds('base_cycle_model')
        table.append(dict(from_row=a,to_row=b,samples=len(steps),
            rpc_calls=bounds('rpc_calls'),unit_write_bytes=bounds('unit_write_bytes'),
            instructions=[min(instr),max(instr)],base_cycle_model=cycles,
            cpu_ms_conditional=[cycles[0]/230000,cycles[1]/105000],
            rtt_ms_to_reach_500=(500-cycles[1]/105000)/max(s['rpc_calls'] for s in steps)))
    result=dict(dat_sha256=identity,units=units,transitions=table,faults=faults,
        cpu_assumptions=dict(mhz=[150,230],available_cpu_fraction=[0.7,1.0]),
        not_measured=['physical_cpu_frequency','real_rpc_rtt','preview_display_wait','camera_ticks'],
        cycle_model='nonNOP + serialNOP + 2*MUL + 2*taken_control_transfer',
        latency_formula='base_cycles/(MHz*1000*CPU_fraction) + RPC_count*RTT_ms + display_wait_ms')
    out=HERE/'local/artifacts';out.mkdir(parents=True,exist_ok=True)
    (out/'costs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['| 行 | RPC 次数 | 单元写入 B | 非 NOP 指令 | 基础周期 | CPU 条件估计 ms |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    def pair(x):return str(x[0]) if x[0]==x[1] else str(x[0])+'–'+str(x[1])
    for t in table:
        lines.append('| %02d→%02d | %s | %s | %s | %s | %.1f–%.1f |'%(
            t['from_row'],t['to_row'],pair(t['rpc_calls']),pair(t['unit_write_bytes']),
            pair(t['instructions']),pair(t['base_cycle_model']),*t['cpu_ms_conditional']))
    (out/'cost-table.md').write_text('\n'.join(lines)+'\n')
    print('PASS measured costs: 3 units,',sum(u['measured_moves'] for u in units),'moves,',len(table),'transitions')
    print('\n'.join(lines))

if __name__=='__main__':main()
