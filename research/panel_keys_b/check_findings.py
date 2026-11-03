#!/usr/bin/env python3
"""Recheck the study's bounded claims, without assembly or firmware execution."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct

HERE=Path(__file__).resolve().parent
ns=runpy.run_path(str(HERE/'analyze.py'))
ROOT,LOCAL,FW=ns['ROOT'],ns['LOCAL'],ns['FW']


def load(name):
    return json.loads((LOCAL/name).read_text())


def save(name,value):
    ns['save'](name,value)


def elf_sections(path):
    d=path.read_bytes()
    assert d[:6]==bytes([127,69,76,70,1,2])
    shoff=struct.unpack_from('>I',d,32)[0]
    entsize,n,strings=struct.unpack_from('>HHH',d,46)
    rows=[struct.unpack_from('>10I',d,shoff+i*entsize) for i in range(n)]
    names=d[rows[strings][4]:rows[strings][4]+rows[strings][5]]
    return {names[r[0]:].split(bytes([0]),1)[0].decode():dict(type=r[1],va=r[3],offset=r[4],size=r[5]) for r in rows}


def main():
    ns['preflight']()
    data=FW.read_bytes();assert hashlib.sha256(data).hexdigest()==ns['PIN']
    secs=ns['sections'](data)
    extras=['firmware/resident_v3/resident/resident.ld',
            'firmware/resident_v3/local/resident/size.json',
            'firmware/resident_v3/local/resident/build/resident.elf',
            'firmware/resident_v3/local/resident/build/resident.map',
            'firmware/resident_v3/local/resident/linked_hooks.S',
            'research/tooling_m32r/src/binutils-2.43/cpu/m32r.cpu',
            'firmware/resident_v3/containers/product/src/firmware/engine/panel/panel_ui.c',
            'firmware/resident_v3/containers/product/src/firmware/engine/panel/panel.h']
    pinfile=LOCAL/'extra-inputs.json'
    if not pinfile.exists():
        save('extra-inputs.json',[dict(path=p,sha256=ns['sha'](ROOT/p)) for p in extras])
    changed=[r['path'] for r in load('inputs.json')+load('extra-inputs.json')
             if ns['sha'](ROOT/r['path'])!=r['sha256']]
    assert not changed,changed
    words,ins=ns['decode'](LOCAL/'section-09.txt',data,secs)
    by_pc={w['pc']:w for w in words}; half={i['pc']:i for i in ins}
    assertions=load('assertions.json')
    for address,expected in assertions['words'].items():
        assert by_pc[int(address,0)]['asm']==expected,(address,by_pc[int(address,0)])
    states=load('state-tables.json')
    assert states[56]['pointer']==0x203764c8
    assert [s['state'] for s in states if s['pointer']==0x203764c8]==[56]
    routes={r['event']:r for r in states[56]['rows']}
    for event,first,second in assertions['routes']:
        assert (routes[event]['first'],routes[event]['second'])==(first,second)
    functions=load('function-range-xrefs.json')
    for f in functions[:2]:
        assert len(f['pointers'])==2
        assert all(r['target']==f['start'] for r in f['pointers'])
        assert not any(f[k] for k in ('external_direct','constants','constant_calls','relative_hits'))
    shared_states=sorted({s['state'] for s in states for r in s['rows'] if r['first']==0x202b848c})
    assert shared_states==[51,52,56]
    xref=load('target-xrefs.json');encoded=load('encoded-hits.json')
    candidates=[]
    for address in assertions['candidates']:
        w=by_pc[address];raw=bytes.fromhex(w['raw'])
        assert len(raw)==4 and address%4==0
        if raw[0]>>4==13 and raw[1]==0xc0:
            dest=f'r{raw[0]&15}';value=int.from_bytes(raw[2:],'big')<<16
            assert w['asm']==f'seth {dest},#0x{value>>16:x}'
            transfer={dest:hex(value),'PSW':'unchanged','memory':'unchanged','SP':'unchanged',
                      'other_registers':'unchanged','PC_relative':False,'grouping':'one 32-bit instruction'}
        else:
            assert raw[0]>>4==1 and raw[1]&0xf0==0x80
            assert int.from_bytes(raw[2:],'big')==0xf000
            dr,sr=raw[0]&15,raw[1]&15
            assert w['asm']==f'mv r{dr},r{sr} || nop'
            transfer={f'r{dr}':f'entry r{sr}','PSW':'unchanged','memory':'unchanged','SP':'unchanged',
                      'other_registers':'unchanged','PC_relative':False,'grouping':'parallel move and nop'}
        assert not any(r['target']==address+2 for r in xref['direct']+xref['pointers']+encoded)
        assert not any(r['value']==address+2 for r in xref['constants'])
        assert not any(address+2 in t.get('targets',[]) for t in load('relative-tables.json'))
        candidates.append(dict(va=address,file_offset=ns['at'](secs,address,4),original=w,
                               transfer=transfer,resume=address+4,
                               relocation_proof='Same symbolic transfer at any aligned trampoline PC; requires exact entry state restoration.'))
    save('replay-symbolic.json',candidates)
    relative=load('relative-tables.json')
    table={t['jump']:t for t in relative}
    assert table[0x202ba72a]['targets'][7]==0x202ba764
    assert table[0x202c2cc6]['targets'][7]==0x202c2d54
    local_tables=[{k:t[k] for k in ('jump','table','base','width','count_candidate','bounds_proven')}
                  for t in relative if any(abs(t['base']-a)<32768 for a in assertions['candidates'])]
    save('nearby-relative-tables.json',local_tables)
    sz=json.loads((ROOT/'firmware/resident_v3/local/resident/size.json').read_text())
    e=elf_sections(ROOT/'firmware/resident_v3/local/resident/build/resident.elf')
    assert e['.payload']['va']==0x2005276c and e['.payload']['size']==7532
    assert sz['payload_bytes']==e['.payload']['size'] and sz['root_bytes']==256
    physical=0x20054700-(e['.payload']['va']+e['.payload']['size'])
    text=(ROOT/'firmware/resident_v3/resident/resident.ld').read_text()
    m=re.search(r'__resident_code_end <= 0x20054700 - (\d+)',text);assert m
    reserve=int(m[1]);assert (physical,reserve,physical-reserve)==(552,300,252)
    save('budget.json',dict(payload_bytes=e['.payload']['size'],root_bytes=256,
        physical_gap=physical,required_gap=reserve,additional_bytes_without_changing_link_contract=physical-reserve,
        fixed_two_stubs=64,observer_estimate=[72,128],ownership_estimate=[32,64],
        existing_hook_adaptations_estimate=[48,96],alignment_estimate=[4,16],
        narrow_total_estimate=[220,368],complete_panel_estimate=[300,500],
        estimated_not_compiled=True))
    checks=dict(official_sha256=ns['PIN'],pinned_inputs_unchanged=True,
        instruction_assertions=len(assertions['words']),state_routes_checked=len(assertions['routes']),
        relocation_candidates_checked=len(candidates),shared_first_states=shared_states,
        range_xref_functions=len(functions),recognized_relative_tables=len(relative),
        nearby_relative_tables=len(local_tables),
        first_column_activity_clear_is_present=True,
        h08_is_reachable_from_navigation=True,
        all_runtime_indirect_targets_closed=False,
        setting_playback_update_exclusion_proven=False,
        physical_key_phases_proven=False,firmware_built=False,camera_tested=False)
    save('findings-checks.json',checks)
    lines=['# 私有逐字节证据','',
           '本附件含理光派生字节和反汇编，仅保存在忽略的 local/。','',
           '## 三个候选的覆盖字和重放','',
           '| 地址 | 文件偏移 | 原字节 | GNU objdump | 透传续接 |',
           '|---|---|---|---|---|']
    for c in candidates:
        lines.append(f'| {c["va"]:#010x} | {c["file_offset"]:#x} | {c["original"]["raw"]} | {c["original"]["asm"]} | {c["resume"]:#010x} |')
    lines+=['','## 关键断言','', '| 地址 | 经官方字节核对的指令 |','|---|---|']
    for address in sorted(assertions['words'],key=lambda s:int(s,0)):
        w=by_pc[int(address,0)]
        lines.append(f'| {address} | {w["raw"]}  {w["asm"]} |')
    lines+=['','## 第二列处理器的全部映像指针引用','',
            '| 处理器 | 指针所在 VA | 文件偏移 |','|---|---|---|']
    for f in functions[:2]:
        for r in f['pointers']:
            lines.append(f'| {f["start"]:#010x} | '+','.join(f'{v:#010x}' for v in r['vas'])+f' | {r["offset"]:#x} |')
    (LOCAL/'EVIDENCE.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__': main()
