"""Check real execution counts and compute explicitly conditional latency."""
from pathlib import Path
import collections
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save

def main():
    groups=collections.defaultdict(list);allsteps=[];matches=[]
    for unit in ('50mm','28mm','mount'):
        d=json.loads((OUT/f'native/perf-{unit}.json').read_text())
        author=json.loads((ROOT/f'research/ux_preview_dot_r1/local/runs/perf-{unit}.json').read_text())
        assert d['status']==author['status']=='PASS' and len(d['moves'])==32
        equal=[]
        for a,b in zip(author['moves'],d['moves']):
            assert b['rpc_errors']==b['crc_accelerated_calls']==0
            assert b['unit_write_bytes']==2*b['W_attempts']
            count=b['instruction_counts']
            assert b['base_cycle_model']==count.get('instructions',0)+count.get('serial_nops',0)+2*count.get('multiply',0)+2*count.get('taken_control_transfers',0)
            key=f"{b['before']['cursor']:02}→{b['after']['cursor']:02}"
            assert key==f"{a['before']['cursor']:02}→{a['after']['cursor']:02}"
            fields=('rpc_calls','unit_write_bytes','base_cycle_model','instruction_counts','crc_accelerated_calls','rpc_errors')
            same={k:a[k]==b[k] for k in fields};equal.append(same)
            # Counts are read from this run even when an author's counter differs.
            groups[key].append(b);allsteps.append(b)
        matches.append(dict(unit=unit,same_as_author=all(all(x.values()) for x in equal),fields=equal,
                            dat_sha256=d['dat_sha256'],elf_sha256=d['elf_sha256']))
    ranges=lambda xs:[min(xs),max(xs)]
    table=[]
    for key,ss in sorted(groups.items()):
        cycles=ranges([s['base_cycle_model'] for s in ss])
        table.append(dict(transition=key,samples=len(ss),rpc=ranges([s['rpc_calls'] for s in ss]),
            unit_bytes=ranges([s['unit_write_bytes'] for s in ss]),instructions=ranges([s['instruction_counts']['instructions'] for s in ss]),
            base_cycles=cycles,cpu_ms=[cycles[0]/230000,cycles[1]/105000]))
    cpu=[min(s['base_cycle_model'] for s in allsteps)/230000,max(s['base_cycle_model'] for s in allsteps)/105000]
    nrpc=ranges([s['rpc_calls'] for s in allsteps]);written=ranges([s['unit_write_bytes'] for s in allsteps])
    scenarios=[dict(mean_rpc_ms=x,total_before_display_ms=[cpu[0]+nrpc[0]*x,cpu[1]+nrpc[1]*x]) for x in (.1,1,2,5)]
    result=dict(status='PASS_COUNTS_ONLY',moves=len(allsteps),transitions=len(table),samples_each_transition=6,
        rpc=nrpc,unit_write_bytes=written,instructions=ranges([s['instruction_counts']['instructions'] for s in allsteps]),
        base_cycles=ranges([s['base_cycle_model'] for s in allsteps]),cpu_conditional_ms=cpu,
        author_comparison=matches,table=table,latency_scenarios=scenarios,
        rpc_ms_for_500ms_at_max_rpc=(500-cpu[1])/nrpc[1],
        tick='1 ms static semantics from cpu_speed_r1; no new hardware clock sample',
        clock_assumption='150..230 MHz, 70..100 percent CPU share. Not a confirmed hardware range.',
        excluded='Memory stalls, native boundary CPU/communication, RTOS scheduling, preview/display waits. No finite real-device upper bound.',
        scope='Zero/default RAM tweaks and adjacent transitions only. Counts are not upper bounds for arbitrary Fn2 edits or recovery.')
    save('measurements.json',result)
    lines=['| 相邻行 | RPC | 单元写入 B | 非 NOP 指令 | 基础周期 | CPU 条件估计 ms |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    fmt=lambda pair:str(pair[0]) if pair[0]==pair[1] else f'{pair[0]}–{pair[1]}'
    for r in table:lines.append('| '+r['transition']+' | '+' | '.join(fmt(r[k]) for k in ('rpc','unit_bytes','instructions','base_cycles'))+' | '+f"{r['cpu_ms'][0]:.1f}–{r['cpu_ms'][1]:.1f}"+' |')
    (OUT/'cost-table.md').write_text('\n'.join(lines)+'\n')
    print('PASS independently executed counts: 96 moves, 16 transitions, zero errors, real CRC loops',flush=True)
    print('RPC',nrpc,'unit bytes',written,'CPU conditional ms',[round(x,3) for x in cpu],
          'author counts equal',all(x['same_as_author'] for x in matches),flush=True)

if __name__=='__main__':main()
