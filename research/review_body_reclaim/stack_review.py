#!/usr/bin/python3
"""Separate static resident prefixes from unmeasured task/native/IRQ depth."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
frames={}
for variant in ['base','vH','vS1','r1','c4','r3','r4']:
    table={}
    for path in (HERE/f'local/rebuild/v/{variant}/build').glob('*.su'):
        for line in path.read_text().splitlines():
            name,size,*_=line.split('\t');table[name.split(':')[-1]]=int(size)
    frames[variant]=table
reference={}
for path in (HERE/'local/observer-reference/build').glob('*.su'):
    for line in path.read_text().splitlines():
        name,size,*_=line.split('\t');reference[name.split(':')[-1]]=int(size)
frames['observer-reference']=reference
assembly=(HERE/'local/rebuild/v/r3/linked_hooks.S').read_text()
shared=assembly.split('rv_hook_shared:',1)[1].split('.section',1)[0]
shared_bytes=4*sum(line.strip().startswith('push ') for line in shared.splitlines())
assert shared_bytes==64
f=frames['r3'];prefix=4+shared_bytes+f['rv_hook_observe']
chain=f['rv_engine']+f['rv_check']+f['rv_session']+f['rv_allocation']
result={'classification':'static per-function frames and selected resident call-chain sums',
        'observer_frames':{v:t['rv_hook_observe'] for v,t in frames.items()},
        'shared_frame_bytes':shared_bytes,'outer_lr_bytes':4,
        'r3':{'h40_resident_peak':prefix+chain,
              'h40_dat_entry_prefix':prefix+f['rv_engine']+f['rv_invoke'],
              'h10_resident_peak':prefix+f['ui_call']+chain,
              'h10_dat_entry_prefix':prefix+f['ui_call']+f['rv_engine']+f['rv_invoke'],
              'h01_load_resident_peak':prefix+f['rv_load']+chain,
              'h01_load_dat_entry_prefix':prefix+f['rv_load']+f['rv_engine']+f['rv_invoke']},
        'task_stacks':{'6':{'begin':'0x20442200','end':'0x20446200','bytes':16384},
                       '26':{'begin':'0x20461a00','end':'0x20465a00','bytes':16384}},
        'stack_record_source':'research/body_next_steps/local/emulator/stack-fill-r1.json',
        'unknown':['native call-chain depth at each hook','production DAT peak and native subcalls',
                   'IRQ stack limits, nesting, and hook reachability','real capture high-water marks']}
(HERE/'local/stack-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
