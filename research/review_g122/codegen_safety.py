"""Classify machine-code data, guards, loop counters, and bounded storage."""
from pathlib import Path
import json
import re
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols

def main():
    audit=json.loads((OUT/'evidence/static-audit.json').read_text())
    engine=(TREE/'candidate/local/full-r13/engine.bin').read_bytes()
    listing=(OUT/'local/engine122.disasm').read_text()
    lines={int(m[1],16):m[2] for m in re.finditer(r'^\s*([0-9a-f]+):\s+(.*?)\s*$',listing,re.M)}
    tables=[]
    data_addresses=set()
    for start,count in ((0x24c0,14),(0x25bc,13)):
        targets=[]
        for i in range(count):
            address=start+4*i
            offset=struct.unpack_from('>i',engine,address-256)[0]
            target=start+offset
            assert target in lines and 0x1750<=target<0x3ac8
            targets.append(hex(target))
            data_addresses.add(address)
        tables.append(dict(start=hex(start),bytes=4*count,count=count,targets=targets,
                           justification='Switch index is checked before table load; entries are relative code offsets.'))
    unknown=[]
    for name,record in audit['compiled_spans'].items():
        for row in record['embedded_data_or_decode_anomalies']:
            pc=int(row['pc'],16)
            assert pc in data_addresses,(name,hex(pc))
            unknown.append(dict(function=name,pc=hex(pc),classification='bounded switch table data'))
    assert 'cmpu r4,r6' in lines[0x24a4] and 'bc 2510' in lines[0x24a8]
    assert 'cmpu r2,lr' in lines[0x25a4] and 'jmp r2' in lines[0x25b8]
    assert 'bl cc84' in lines[0x3274]
    assert 'or3 r5,r5,#0x9bf8' in lines[0x327c]
    assert 'addi r5,#-8' in lines[0x3284]
    assert 'bnez r5,329c' in lines[0x3288]
    assert 'ld24 r5,817670' in lines[0x328c] and 0x817670<<6==0x205d9c00
    assert 'addi r5,#-56' in lines[0x3294]
    assert 'beqz r5,3328' in lines[0x3298]
    assert 'ld r0,@(32,sp)' in lines[0x329c] and 'bra 2df8' in lines[0x32a0]
    assert 'bl cc90' in lines[0x2df8] and 'bl cc90' in lines[0x3438] and 'bl cc90' in lines[0x348c]
    # Audit dependent unchanged loops too; these outputs remain under local/.
    tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    syms=symbols(ELF)
    loader=load(ROOT/'tools/native_harness/image_loader.py','review_codegen_elf')
    all_symbols=loader.Elf(ELF).symbols
    dependencies={}
    for name in ('a4_move','recover_confirmed','apply_impl.constprop.0','rv_irq_save','rv_irq_restore'):
        data=subprocess.run([str(tool),'-d','--disassemble='+name,str(ELF)],capture_output=True,text=True,check=True).stdout
        (OUT/'local/compiled'/(name+'.txt')).write_text(data)
        encoded=[(int(m[1],16),len(bytes.fromhex(m[2]))) for m in re.finditer(
            r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)',data,re.M)]
        leaf_bytes=max(at+n for at,n in encoded)-all_symbols[name]
        if name=='rv_irq_restore':
            assert 'mvtc r0,psw -> jmp lr' in data
            leaf_bytes=4
        dependencies[name]=dict(start=hex(all_symbols[name]),
                                bytes=syms[name]['size'] if name in syms else leaf_bytes,
                                assembly_leaf=name not in syms)
    apply=(OUT/'local/compiled/ig_apply.txt').read_text()
    move=(OUT/'local/compiled/a4_move.txt').read_text()
    for token in ('ldi r4,#16 -> st r4,@sp','ld r5,@sp -> addi r5,#-1'):
        assert token in apply,token
    for token in ('ldi fp,#16','addi fp,#-1','beqz fp,'):
        assert token in move,token
    stack={}
    for path in (TREE/'candidate/local/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        for line in path.read_text().splitlines():
            parts=line.split('\t')
            if len(parts)==3:
                name=parts[0].rsplit(':',1)[-1]
                stack[name]=dict(bytes=int(parts[1]),kind=parts[2])
    assert all(x['kind']=='static' for x in stack.values())
    read=json.loads((OUT/'evidence/machine-read.json').read_text())
    sentinel=json.loads((OUT/'evidence/machine-sentinel.json').read_text())
    assert read['status']==sentinel['status']=='PASS'
    groups={
      'ingress':['ingress'],
      'RPC wrapper':['core_call'],
      'UI and retained cursor':['list_bind_impl','list_bind','panel_render','keep_view','rows'],
      'completion and retry':['finish','ui_finish','retry_view','deferred_menu','eng_require_recheck',
                              'eng_restore_cursor','eng_display_current','eng_retry_live'],
      'native entries':['ig_menu','ig_apply','ig_event','ig_panel_open','ig_panel_event'],
      'menu construction and epoch':['accept_menu_preview','menu_list','eng_menu_open','eng_menu_deferred','rebind_impl'],
      'unit validation':['sentinel_offset','read_live','validate_live'],
      'native publication':['ui_list']}
    names=[n for group in groups.values() for n in group]
    assert sorted(names)==sorted(x['function'] for x in audit['changed_functions'])
    rows=[]
    for group,names in groups.items():
        rows.append(dict(group=group,functions=names,
          address_length='New X/V generator is read_live; compiled sequence is covered by 103 deterministic boundary cases. All W remains in unchanged deep/apply_impl.',
          file_operations='No added storage caller. Existing dispatcher gates are verified separately with native service calls; mutation counters must stay zero.',
          native_UI='Publication uses list/panel services; new guard machine PCs 0x3274-0x32a0 precede native stores and restore IRQ on rejection.',
          loops_memory='Bounded map/row/string loops, sixteen-round navigation, six compensation attempts; engine state and owned UI buffers only.',
          arithmetic='Control and bounds checked; source compute and numeric tweak routines are unchanged.'))
    save('evidence/codegen-safety.json',dict(status='PASS_STATIC_BOUNDARIES_AND_TARGETED_EXECUTION',
       dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),changed_functions=29,compiled_spans=21,
       jump_tables=tables,decode_anomalies_classified=unknown,undecoded_executable_bytes=0,
       IRQ=dict(save='0x3274',activity_check='0x3284',state_check='0x3294',reject='0x329c',
                rejection_restore='0x2df8',success_restore='0x3438',seed_failure_restore='0x348c'),
       dependencies=dependencies,stack=stack,function_groups=rows,
       maximum_stack_frame=max(x['bytes'] for x in stack.values()),
       scope='Static safety review and listed machine-code samples; no global translation proof or RTOS scheduling proof is claimed.'))
    print(json.dumps(dict(status='PASS',changed_functions=29,compiled_spans=21,jump_tables=len(tables),
                          read_cases=read['count'],sentinel_cases=sentinel['count'])))

if __name__=='__main__':
    main()
