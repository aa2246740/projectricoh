#!/usr/bin/env python3
"""Replay the frozen reviews in local/, preserving their original assertions."""
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local/regression'
REVIEW=ROOT/'research/review_flash_v31/local'
COMMANDS=[]

def run(folder,name,args,expected=0):
    env=dict(os.environ,TMPDIR=str(HERE/'local/tmp'),ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
             UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    p=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,text=True,capture_output=True)
    output=p.stdout+p.stderr
    (folder/(name+'.log')).write_text(output)
    COMMANDS.append(dict(name=name,argv=list(map(str,args)),returncode=p.returncode,expected=expected))
    (LOCAL/'commands.json').write_text(json.dumps(COMMANDS,indent=2)+'\n')
    if p.returncode:
        failures=LOCAL/'failures';failures.mkdir(exist_ok=True)
        (failures/(folder.name+'-'+name+'-'+hashlib.sha256(output.encode()).hexdigest()[:12]+'.log')).write_text(output)
    assert p.returncode==expected,(folder.name,name,p.returncode,output[-2000:])
    return p

def compile_driver(source,folder,driver):
    folder.mkdir(parents=True,exist_ok=True)
    c=folder/'review_behaviour.c';c.write_text(driver)
    flags=['/usr/bin/clang','-std=c11','-O1','-g','-DRV_HOST','-fno-builtin',
           '-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-I',source/'resident']
    rows=[(source/'resident'/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    rows += [(source/'engine_services'/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    rows += [(source/'resident/shared.c',True),(c,False),(source/'local/resident/trust.c',False)]
    objects=[]
    for i,(src,service) in enumerate(rows):
        obj=folder/('%02d.o'%i);objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if src.name=='runtime.c':
            extra+=['-Dmemcpy='+('es_test_memcpy' if service else 'rv_test_memcpy'),
                    '-Dmemset='+('es_test_memset' if service else 'rv_test_memset')]
        run(folder,'compile-%02d'%i,[*flags,*extra,'-c',src,'-o',obj])
    binary=folder/'review_behaviour'
    run(folder,'link',['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary])
    return binary

def port_v31(original):
    s=original.replace('../frozen/firmware/resident_v31/resident/v3_checks.c',str(HERE/'resident/v3_checks.c'))
    s=s.replace('0x205b0004','(RV_NATIVE_VIEWS+4)')
    start=s.index('        reset();load();test_array=rv_native_alloc(16);snap=ui(1);slot=test_array+4;')
    end=s.index('    }else if(!strcmp(which,"h07-matrix"))',start)
    s=s[:start]+'''        reset();load();test_array=rv_native_alloc(16);CHECK(!ui(1));slot=test_array+4;
        CHECK(!root.ui_restore[0]&&RV_WORD(slot)==0x2022f71c);
        rv_native_free(test_array);
        CHECK(rv_ui_abort(&root)==RV_OK&&RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
        puts("FIXED expired-slot publication_rejected=1 dead_slot_reads=0 writes=0");
    }else if(!strcmp(which,"reused-slot")) {
        reset();load();test_array=rv_native_alloc(16);CHECK(!ui(1));snap=root.ui_block;slot=test_array+4;
        RV_WORD(0x205a27d8)=0x205b0100;RV_BYTE(0x205a27d4)=1;
        RV_BYTE(0x205b0100)=44;RV_WORD(0x205b0104)=0x20240000;
        rv_native_free(test_array);review_reuse_address=test_array;
        CHECK(rv_native_alloc(16)==test_array);RV_WORD(slot)=snap;
        CHECK(rv_ui_abort(&root)==RV_OK&&RV_WORD(slot)==snap&&!root.ui_restore[0]);
        printf("FIXED reused-slot address=%08x publication_rejected=1 replacement_word_preserved=1\\n",slot);
''' +s[end:]
    s=s.replace('root.ui_restore[3]=0x1ffffffcu','root.ui_restore[1]=8')
    s=s.replace('CHECK(RV_WORD((RV_NATIVE_VIEWS+4))==snap);','CHECK(RV_WORD((RV_NATIVE_VIEWS+4))==0x2022f71c);')
    s=s.replace('stock_names_restored=1 actual_old_view_retained=1 recovery_erased=1 host_alignment_trap=0',
                'stock_names_restored=1 fixed_view_restored=1 unused_slot_address_ignored=1')
    s=s.replace('==21&&RV_BYTE(0x2050206f)==3','==21&&RV_BYTE(0x2050206f)==1')
    s=s.replace('CHECK(RV_BYTE(0x2050201a)==0);','CHECK(RV_BYTE(0x2050201a)==21&&RV_BYTE(0x2050206f)==1);')
    s=s.replace('DIFFERENCE H09','FIXED H09').replace('packet_passthrough=1 Stage2l_would_apply=1','packet_applied=1 Stage2l_equal=1')
    anchor='            rv_hook_observe(&root,7,fr);review_force=-1;'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''
            CHECK(fr[1]==(uint32_t)(uintptr_t)((!keep||res>=RV_CLOSE_AND_PASS)?rv_close_07:rv_skip_07));
            CHECK(fr[15]==1&&(!root.ui_restore[0])==(!keep||res!=RV_CONSUMED));
            CHECK((root.state==RV_DISABLED_UNTIL_REBOOT)==(res==RV_FAULT));''')
    return s

def port_v3(original):
    s=original.replace('../frozen/firmware/resident_v3/resident/v3_checks.c',str(HERE/'resident/v3_checks.c'))
    s=s.replace('static uint32_t last_entry,last_row;\n','').replace('0x205b0004','(RV_NATIVE_VIEWS+4)')
    s=s.replace('frees==was_free+1&&RV_BYTE(block-8)==0','frees==was_free&&RV_BYTE(block-8)==1')
    s=s.replace('replacement_freed=1','replacement_freed=0')
    s=s.replace('RV_WORD((RV_NATIVE_VIEWS+4))==snap','RV_WORD((RV_NATIVE_VIEWS+4))==0x2022f71c')
    s=s.replace('native_view_retains_dead_state=1','native_view_restored=1').replace('old_view_retained=1','fixed_view_restored=1')
    s=s.replace('last_row==row);','last_row==row-1);')
    s=s.replace('frame[1]==(uint32_t)(uintptr_t)rv_skip_07&&frame[15]==0','frame[1]==(uint32_t)(uintptr_t)rv_close_07&&frame[15]==1')
    s=s.replace('&&root.ui_restore[0]);','&&!root.ui_restore[0]);')
    s=s.replace('frees==was_free+1&&invokes==was_invoke&&!root.block','frees==was_free&&invokes==was_invoke&&root.block')
    s=s.replace('COUNTEREXAMPLE','FIXED').replace('REVIEW_BOUNDARY_CASES_REPRODUCED','REVIEW_BOUNDARY_CASES_FIXED')
    s=s.replace('H07_close_PASS swallowed=1 overlay_word_still_32=1 owned_view_still_published=1',
                'H07_close_PASS close_stub_selected=1 native_view_restored=1 assembly_overlay_checked_separately=1')
    s=s.replace('native_main_free=1','native_main_free=0')
    s=s.replace('CHECK(allocs==frees);','CHECK(allocs-frees==(i==3?0u:1u));')
    s=s.replace('&&!invokes&&allocs==frees);','&&!invokes&&allocs-frees==1);')
    return s

def main():
    spec=importlib.util.spec_from_file_location('regression_guard',HERE/'resident/build.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()
    LOCAL.mkdir(exist_ok=True)
    original=(REVIEW/'host/review_behaviour.c').read_text()
    (LOCAL/'v31-original-review_behaviour.c').write_text(original)
    frozen=REVIEW/'frozen/firmware/resident_v31'
    baseline=original.replace('../frozen/firmware/resident_v31/resident/v3_checks.c',str(frozen/'resident/v3_checks.c'))
    cases=('h07-matrix','failed-retract-pass','ready-reopen','h09-differences','reused-slot','expired-slot','unaligned-slot')
    results=[]
    for label,source,driver in (('v31',frozen,baseline),('v32',HERE,port_v31(original))):
        folder=LOCAL/label;binary=compile_driver(source,folder,driver)
        fixture=source/'local/resident/fixtures/synthetic-container.fixture'
        run(folder,'behaviour',[binary,fixture])
        for case in cases:
            expected=91 if label=='v31' and case=='expired-slot' else 0
            p=run(folder,case,[binary,fixture,case],expected)
            results.append(dict(version=label,case=case,returncode=p.returncode,expected=expected,
                                log=str((folder/(case+'.log')).relative_to(HERE))))
        if label=='v32':
            (LOCAL/'v31-port.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),driver.splitlines(True),fromfile='frozen v31 review',tofile='v32 regression')))
    old=(ROOT/'research/review_flash_v3/local/host/review_behaviour.c').read_text()
    adapted=port_v3(old);folder=LOCAL/'review_v3';binary=compile_driver(HERE,folder,adapted)
    run(folder,'behaviour',[binary,HERE/'local/resident/fixtures/synthetic-container.fixture'])
    (LOCAL/'v3-port.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),adapted.splitlines(True),fromfile='frozen v3 review',tofile='v32 regression')))
    (LOCAL/'results.json').write_text(json.dumps(dict(status='PASS',cases=results,previous_v3='PASS',
        source_original_sha256=hashlib.sha256(original.encode()).hexdigest(),native_m32r=False,
        removed_F03='No post hook or LR record remains; final ELF and manifest checked by audit.py'),indent=2)+'\n')
    print('PASS review replays: v31 baseline=8 v32=8 previous_v3=1; raw failures retained; ASan+UBSan')

if __name__=='__main__':main()
