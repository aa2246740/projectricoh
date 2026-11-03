"""Compare compiled final-engine stack paths, with native callees still open."""
import importlib.util
import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('stack_model',HERE/'stack_checks.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args()
    out=HERE/('local/stack-r9' if args.final else 'local/stack-r8');out.mkdir(exist_ok=True);s.LOCAL=out
    profiles={}
    inputs=[('r7',ROOT/'firmware/engine_v33d','local/full-r7/engine.elf','local/product/m32r-lto'),
            ('r8',HERE/'acceptance','local/full-r8/engine.elf','local/product/m32r-lto')]
    if args.final:inputs.append(('r9',HERE/'acceptance','local/full-r9/engine.elf','local/product-r9/m32r-lto'))
    for label,base,elf,su in inputs:
        model=s.artifact(label,base/elf,[base/su,base/'local/resident/engine-services'])
        for name,targets in (
            ('svc',['core_call']),('pn_call',['rv_call']),('core_call',['rv_call']),('rv_call',['rv_service']),
            ('disarm',['grain_snapshot']),('eng_apply',['grain_snapshot']),
            ('read_object',['io_open','io_read','io_close']),('gxts_load',['io_open','io_read','io_close']),
            ('gxts_save',['io_open','io_read','io_write','io_close','io_remove','io_rename']),
            ('inspect',['verify','last_verify']),('ps_install',['verify']),('pn_ui_render',['pn_native_from_seed']),
            ('a4_finish',['io_open','io_read','io_write','io_close','io_remove','io_rename']),
            ('rpc',['rv_call']),('pn_address',['address'])):
            s.add(model,name,targets)
        entries={name:dict(zip(('bytes','chain'),s.peak(model,name))) for name in ('ig_bootstrap','ig_init','ig_menu','ig_panel_open','ig_event','ig_apply')}
        profiles[label]=dict(entries=entries,unresolved_indirect=[k for k,v in model['indirect'].items() if v])
    resident=json.loads((HERE/'local/stack/comparison.json').read_text())
    frames=resident['artifacts']['resident']['frames']
    direct={row['hook']:row['resident_and_bridges_peak'] for row in resident['rows']}
    prefix=68+sum(frames[name] for name in ('rv_hook_observe','rv_engine','rv_invoke'))
    combined={}
    for label,profile in profiles.items():
        entries=profile['entries']
        combined[label]={1:max(prefix+entries['ig_menu']['bytes'],prefix+frames['rv_load']+max(entries[n]['bytes'] for n in ('ig_bootstrap','ig_init'))),
                         2:direct[2],5:direct[5],6:prefix+entries['ig_panel_open']['bytes'],7:prefix+entries['ig_event']['bytes'],
                         8:prefix+entries['ig_apply']['bytes'],9:direct[9]}
    result=dict(status='PASS',profiles=profiles,combined_modeled_hook_bytes=combined,
        method='compiled .su and saved registers, declared indirect edges; no native callees/IRQ/task baseline',
        global_safety_proven=False,camera_stack_waterline_measured=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({label:{k:v['bytes'] for k,v in profile['entries'].items()} for label,profile in profiles.items()}))


if __name__=='__main__':main()
