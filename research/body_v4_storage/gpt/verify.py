#!/usr/bin/env python3
"""Reproduce research in one Python process, or seal/check root-relative hashes."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e

EXTRA=(
 'docs/RESEARCH_PROTOCOL.md',
 'research/irom_storage/local/address_candidates.json',
 'firmware/resident_v34c/policy_machine.py',
 'firmware/stage2l_switch/tools/build.py',
 'firmware/resident_v36/resident/resident.c',
 'firmware/resident_v36/resident/loader.c',
 'firmware/resident_v36/resident/hooks.c',
 'firmware/resident_v36/resident/build.py',
 'firmware/resident_v36/resident/resident.ld',
 'firmware/resident_v36/local/resident/hooks.json',
 'firmware/resident_v36/local/resident/size.json',
 'firmware/resident_v36/local/resident/build/resident.elf',
 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc',
 'research/tooling_m32r_asm/prefix/bin/m32r-elf-as',
)

def extra_inputs():
    files={e.ROOT/r for r in EXTRA}
    files.update((e.ROOT/'research/irom_storage/local').glob('section*.asm.txt'))
    return {str(p.relative_to(e.ROOT)):e.sha(p) for p in sorted(files)}

def check_protected():
    before=json.loads((e.OUT/'protected-before.json').read_text())
    changes=[r for r,d in before.items() if not (e.ROOT/r).is_file() or e.sha(e.ROOT/r)!=d]
    extras=json.loads((e.OUT/'additional-inputs.json').read_text())
    changed_extra=[r for r,d in extras.items() if not (e.ROOT/r).is_file() or e.sha(e.ROOT/r)!=d]
    result=dict(status='PASS' if not changes and not changed_extra else 'FAIL',
        initial_files=len(before),additional_files=len(extras),changed=changes,additional_changed=changed_extra)
    e.save('protected-check.json',result)
    assert result['status']=='PASS',result
    return result

def pin_extra():
    path=e.OUT/'additional-inputs.json'
    now=extra_inputs()
    if path.exists():assert json.loads(path.read_text())==now,'additional input changed'
    else:e.save('additional-inputs.json',now)
    e.save('session.json',dict(task='body-v4-storage-r1-gpt',
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=e.ROOT,text=True).strip(),
        root=str(e.ROOT),write_scope=str(HERE),read_exclusion='The other two body_v4_storage directories were never opened.',
        additional_input_pin='Captured after discovery; not claimed as the start-of-task snapshot.',
        python=sys.executable,python_flags=dict(isolated=sys.flags.isolated,dont_write_bytecode=sys.dont_write_bytecode)))

def run_module(name):
    spec=importlib.util.spec_from_file_location('body_storage_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def full():
    pin_extra()
    refs,_=e.verify_references()
    e.save('references.json',refs)
    check_protected()
    run_module('static').collect()
    run_module('census').main()
    run_module('replay').main()
    run_module('model').main()
    run_module('size').main()
    run_module('trampoline_replay').main()
    replay=json.loads((e.OUT/'replay-results.json').read_text())
    model=json.loads((e.OUT/'protocol-model.json').read_text())
    census=json.loads((e.OUT/'census.json').read_text())
    windows=json.loads((e.OUT/'windows.json').read_text())
    constructors={r['entry']:r['packet']['message'] for r in replay['rows'] if r['case']=='constructor_queue2'}
    producer_map=[]
    image=e.Image()
    for entry,opcode in sorted(constructors.items()):
        calls=[r for r in census['calls'] if r['target']==entry and 'branch' not in r]
        pointers=[]
        needle=int(entry,16).to_bytes(4,'big')
        for section in image.sections:
            raw=image.raw(section['vma'],section['size'])
            at=raw.find(needle)
            while at>=0:
                pointers.append(dict(vma=hex(section['vma']+at),file=hex(section['file']+at),aligned4=at%4==0))
                at=raw.find(needle,at+1)
        producer_map.append(dict(constructor=entry,opcode=opcode,direct_call_candidates=calls,
            literal_pointer_candidates=pointers))
    sends=[r for r in census['calls'] if r['target']=='0x2005e034']
    unresolved=[r for r in sends if 'r4' not in r['args']]
    e.save('producer-map.json',dict(status='BOUNDED_CENSUS_NOT_ALL_PRODUCERS_PROOF',
        constructors=producer_map,rtos_send_candidates=len(sends),unknown_destination_candidates=unresolved,
        warning='Zero hits do not exclude computed targets, register propagation or nonstandard trap callers.'))
    protected=check_protected()
    result=dict(status='PASS_STATIC_AND_HOST_ONLY',windows=len(windows),
       dispatch_cells=33,queue_constructors=18,instruction_replay_cases=replay['cases'],
       research_trampoline_replay_cases=8,
       protocol_model_schedules=model['ordering']['schedules'],
       checked_linear_disassembly_bytes=census['verified_disassembly_bytes'],protected=protected,
       open_obligations=['All capture acceptance roots','All queue 2 and direct-storage producers',
          'RAW+JPEG menu to object identity mapping','Finite native I/O and drain bounds',
          'USB/module/card transitions','Lower-close error slot release','Image layout and hardware acceptance'],
       camera='NOT_RUN',storage_card='NOT_RUN',network='NOT_USED',product_changes='NONE',firmware_images='NONE')
    e.save('verification.json',result)
    print(json.dumps(result,indent=2))

def files():
    return [p for p in sorted(HERE.rglob('*')) if p.is_file() and
        p.name!='SHA256SUMS' and '__pycache__' not in p.parts]

def seal():
    check_protected()
    assert (HERE/'REPORT.md').read_text().startswith(('找到可行桥：','仍不可行：'))
    lines=[e.sha(p)+'  '+str(p.relative_to(e.ROOT)) for p in files()]
    (HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print('SEALED',len(lines),'root-relative entries')

def check_seal():
    rows=[]
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest,rel=line.split(maxsplit=1)
        path=e.ROOT/rel
        assert path.resolve().is_relative_to(HERE),rel
        assert path.is_file() and e.sha(path)==digest,rel
        rows.append(path)
    assert set(rows)==set(files()),'manifest does not cover exactly the owned files'
    check_protected()
    print('PASS_SEAL',len(rows),'entries; protected inputs unchanged')

def main():
    assert sys.flags.isolated and sys.flags.dont_write_bytecode
    assert HERE==e.ROOT/'research/body_v4_storage/gpt'
    e.preflight()
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=('pin-inputs','full','seal','check-seal'))
    args=ap.parse_args()
    {'pin-inputs':pin_extra,'full':full,'seal':seal,'check-seal':check_seal}[args.action]()

if __name__=='__main__':main()
