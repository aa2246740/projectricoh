#!/usr/bin/env python3
"""Compare compiled hook call chains, including declared indirect targets."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local/stack'
OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'

def functions(text):
    return {m[2]:(int(m[1],16),m[3]) for m in re.finditer(
        r'^([0-9a-f]+) <([^>]+)>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)',text,re.M|re.S)}

def artifact(label,elf,su_dirs):
    text=subprocess.check_output([str(OBJDUMP),'-d',str(elf)],text=True)
    (LOCAL/(label+'.txt')).write_text(text)
    funcs=functions(text);frames={};graph={};indirect={};tails={}
    for folder in su_dirs:
        for p in folder.glob('*.su'):
            for line in p.read_text().splitlines():
                parts=line.split('\t')
                if len(parts)==3:
                    assert parts[2]=='static',(str(p),line)
                    frames[parts[0].rsplit(':',1)[-1]]=int(parts[1])
    for name,(start,body) in funcs.items():
        children=[]
        for pc,target,callee in re.findall(r'^\s*([0-9a-f]+):.*?\bbl ([0-9a-f]+) <([^>]+)>',body,re.M):
            callee=callee.split('+')[0]
            if callee==name:continue # PIC link-to-next instruction.
            if callee in funcs:children.append(callee)
        graph[name]=sorted(set(children))
        tails[name]=sorted(set(c.split("+")[0] for c in re.findall(r"\bbra [0-9a-f]+ <([^>]+)>",body) if c.split("+")[0]!=name and c.split("+")[0] in funcs))
        indirect[name]=bool(re.search(r'\bjl r\d+\b',body))
        # .su is authoritative for C. Assembly/PIC fallbacks count all pushes
        # and negative SP reserves before the first real call/branch.
        if name not in frames:
            reserve=0
            for line in body.splitlines():
                reserve+=4*len(re.findall(r'\bpush (?:r\d+|lr|fp)\b',line))
                for n in re.findall(r'\b(?:addi sp,#|add3 sp,sp,#)(-\d+)',line):reserve-=int(n)
                if re.search(r'\b(?:jl |bra |jmp |beq|bne|bc |bnc )',line):break
                call=re.search(r'\bbl ([0-9a-f]+)',line)
                pc=re.match(r'\s*([0-9a-f]+):',line)
                if call and pc and int(call[1],16)!=int(pc[1],16)+4:break
            frames[name]=reserve
        if name.startswith(('rv_native_','gxr_')) and name not in ('gxr_crc',):
            frames[name]=28;graph[name]=[];indirect[name]=False;tails[name]=[]
        if name in ('rv_rpc8_native','rfw_rpc8_native'):
            frames[name]=40;graph[name]=[];indirect[name]=False;tails[name]=[]
    return dict(functions=funcs,frames=frames,graph=graph,indirect=indirect,tails=tails)

def add(a,name,targets):
    for key in a['graph']:
        if key==name or key.startswith(name+'.'):
            a['graph'][key]=sorted(set(a['graph'][key]+[t for t in targets if t in a['graph']]))
            a['indirect'][key]=False

def peak(a,entry,blocked=(),seen=()):
    if entry in blocked:return 0,[]
    if entry in seen:raise AssertionError(('unmodeled recursion',seen,entry))
    choices=[peak(a,c,blocked,seen+(entry,)) for c in a['graph'].get(entry,[]) ]
    n,chain=max(choices,default=(0,[]),key=lambda p:p[0])
    normal=(a['frames'].get(entry,0)+n,[entry]+chain)
    tail=[peak(a,c,blocked,seen+(entry,)) for c in a['tails'].get(entry,[])]
    return max([normal]+[(v,[entry]+ch) for v,ch in tail],key=lambda x:x[0])

def main():
    LOCAL.mkdir(exist_ok=True)
    resident=artifact('resident',HERE/'local/resident/build/resident.elf',[HERE/'local/resident/build'])
    product=artifact('product',HERE/'local/product/m32r-lto/engine.elf',[HERE/'local/product/m32r-lto',HERE/'local/resident/engine-services'])
    stage=artifact('stage2l',ROOT/'firmware/stage2l_switch/build/payload.elf',[ROOT/'firmware/stage2l_switch/build'])
    for name in ('svc','pn_call','core_call'):add(product,name,['core_call'] if name=='svc' else ['rv_call'])
    add(product,'rv_call',['rv_service'])
    add(product,'disarm',['grain_snapshot']);add(product,'eng_apply',['grain_snapshot'])
    add(product,'read_object',['io_open','io_read','io_close'])
    add(product,'gxts_load',['io_open','io_read','io_close'])
    add(product,'gxts_save',['io_open','io_read','io_write','io_close','io_remove','io_rename'])
    add(product,'inspect',['verify']);add(product,'a4_finish',['io_open','io_read','io_write','io_close','io_remove','io_rename']);
    add(product,'ps_install',['verify']);add(product,'pn_ui_render',['pn_native_from_seed'])
    add(product,'rpc',['rv_call']);add(product,'pn_address',['address'])
    add(stage,'rv1_apply',['rfw_acquire','rfw_request_preview','rfw_release'])
    # Native bridges and the explicit old settings callbacks are the only
    # dynamic edges in these Stage2l chains.
    stage_entries={1:'ricoh_recipe_open',2:None,5:None,6:'recipe_fn2_guard',7:'ricoh_recipe_action',8:'recipe_live_commit',9:'recipe_grain_hook'}
    prod_entries={1:['ig_bootstrap','ig_init','ig_menu'],2:[],5:[],6:['ig_panel_open'],7:['ig_event'],8:['ig_apply'],9:[]}
    probes={}
    for variant in ('life','notice','view'):
        probe=artifact('probe-'+variant,HERE/'local/probes/build'/variant/'engine.elf',
                       [HERE/'local/probes/build'/variant,HERE/'local/resident/engine-services'])
        add(probe,'call',['rv_call']);add(probe,'rv_call',['rv_service']);probes[variant]=probe
    probe_entries={1:['pv_entry','pv_entry_init','pv_entry_menu'],2:[],5:[],6:['pv_entry_panel_open'],
                   7:['pv_entry_event'],8:['pv_entry_apply'],9:[]}
    rows=[]
    for hook in (1,2,5,6,7,8,9):
        choices=[]
        for profile,model,entries in [('product',product,prod_entries[hook])]+[(v,m,probe_entries[hook]) for v,m in probes.items()]:
            for entry in entries:
                p,pchain=peak(model,entry)
                prefix=68+resident['frames']['rv_hook_observe']+resident['frames']['rv_engine']+resident['frames']['rv_invoke']
                if hook==1 and entry in ('ig_bootstrap','ig_init','pv_entry','pv_entry_init'):
                    prefix+=resident['frames']['rv_load']
                choices.append(dict(profile=profile,entry=entry,engine_peak=p,live_prefix=prefix,peak=prefix+p,chain=pchain))
        worst=max(choices,default=dict(profile=None,entry=None,engine_peak=0,live_prefix=0,peak=0,chain=[]),key=lambda x:x['peak'])
        blocked=set()
        if hook!=1:blocked.add('rv_load')
        if hook in (2,5,9):blocked.add('rv_engine')
        n,nchain=peak(resident,'rv_hook_observe',blocked)
        if hook==5:n=resident['frames']['rv_hook_observe']+peak(resident,'owned')[0];nchain=['rv_hook_observe','owned']
        if hook==9:n=resident['frames']['rv_hook_observe']+peak(resident,'rv_grain')[0];nchain=['rv_hook_observe','rv_grain']
        candidate=max(68+n,worst['peak'])
        s,schain=peak(stage,stage_entries[hook]) if stage_entries[hook] else (0,[])
        rows.append(dict(hook=hook,resident_and_bridges_peak=68+n,engine_peak=worst['engine_peak'],
                         engine_chain=worst['chain'],worst_profile=worst['profile'],profile_paths=choices,
                         candidate_modeled_peak=candidate,resident_chain=nchain,stage2l_modeled_peak=s,
                         stage2l_chain=schain,target_met=candidate<=s))
    def serial(a):
        return {k:v for k,v in a.items() if k!='functions'}
    result=dict(rows=rows,method='conservative compiled C .su frames plus actual assembly saves and declared indirect call edges; shared observer branch pruning; excludes native firmware callees, interrupts and existing task frames',
                task_stack_remaining_known=False,all_targets_met=all(r['target_met'] for r in rows),
                artifacts=dict(resident=serial(resident),product=serial(product),stage2l=serial(stage),probes={v:serial(m) for v,m in probes.items()}),
                unresolved_indirect={label:[n for n,v in a['indirect'].items() if v] for label,a in [('product',product),('stage2l',stage)]+list(probes.items())})
    (LOCAL/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(rows=[{k:r[k] for k in ('hook','candidate_modeled_peak','stage2l_modeled_peak','worst_profile','target_met')} for r in rows],all_targets_met=result['all_targets_met'],task_stack_remaining_known=False)))
if __name__=='__main__':main()
