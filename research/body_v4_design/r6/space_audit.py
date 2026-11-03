#!/usr/bin/python3 -I -B
"""Read frozen data and compute conditional R6 budgets; no product build."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE.parents[1]
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r6')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value

def compute():
    audit=module('poweron_read_functions',ROOT/'research/poweron_autoapply/audit.py')
    path=ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT'
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='9180745af84593c24e62da5abe595d8ba6a6a8b078d7d1a6cd89fdbfc39b945a'
    sections=audit.checked_sections(raw);compact=audit.compact_effect_area(raw)
    controls=audit.control_record_domain(raw)
    knob_offset=sections[6][0]+3392;knobs=raw[knob_offset:knob_offset+7904]
    assert len(knobs)==7904 and knob_offset+len(knobs)==len(raw)
    assert len(raw)==90156 and sections[0][1]==63896 and audit.u32(raw,116)==9252
    moved=compact['compact_bytes']+len(knobs)
    package_header=128;package_length=package_header+moved
    assert (package_length,package_header+compact['compact_bytes'])==(11440,3536)
    assert package_length<=16384 and package_length%16==0
    fixed=64+16+7628;ext=12288;limit=108064
    packed=90156+9252-compact['saved_bytes']+2048+192
    original_parent=fixed+ext+packed
    port_code,port_bss=1132,28
    bridge=512;dedup=3072
    dat_file=90156-compact['saved_bytes']-moved+2048+port_code+bridge-dedup
    dat_bss=9252+192+port_bss
    selected=fixed+ext+audit.align4(dat_file+dat_bss)
    code=63896+port_code+2048+bridge-dedup
    heap_only=original_parent+port_code+port_bss-dedup
    assert original_parent==117052 and original_parent-limit==8988
    assert original_parent-(limit-512)==9500 and moved==11312
    assert (dat_file,dat_bss,selected,code)==(74872,9472,104340,64516)
    assert selected<=limit-512 and code<=65536
    # A simultaneous EXT increase is never omitted from the real parent bill.
    assert selected+4096>limit-512
    early=64+32*24;root=512;guard=24
    window_before=8340-root-early-guard-(6440+512)
    window_after=window_before+1536
    uncertainty=audit.align4(((3800+544+512)*30+99)//100)
    assert (early,window_before,window_after,uncertainty)==(832,20,1556,1460)
    assert 0x20054600-early==0x200542c0 and 0x20054600-early-guard==0x200542a8
    diag_before=20480+77824+7628+1024+768
    diag_selected=diag_before-640
    assert (diag_before,diag_selected)==(107724,107084)
    assert diag_selected<=107612-512 and diag_selected+8576>107612
    return dict(classification='read_only_data_audit_and_conditional_budget',input_dat_sha256=digest(path),
        dat=dict(file=90156,code=63896,bss=9252),effect_compaction=compact,controls=controls,
        readonly_bank=dict(compact_effects=3408,knob_bytes=7904,total=moved,
            knob_file_offset=knob_offset,knob_sha256=hashlib.sha256(knobs).hexdigest(),
            effect_entries=10,entry_capacity=32,scope='byte_relationship_only_not_runtime_access_proof'),
        readonly_package_budget=dict(header_and_directory=package_header,effect_offset=128,
            knob_offset=3536,file_length=package_length,er_slot=16384,slot_margin=16384-package_length,
            er_small_data_remaining=61440-16384,package_built=False),
        parent=dict(limit=limit,fixed=fixed,ext_slot=ext,input_parent=original_parent,input_gap=8988,
            input_gap_with_reserve=9500,port_charge=1160,bank_bridge_cap=512,dat_code_reduction_target=3072,
            selected_file=dat_file,selected_bss=dat_bss,selected_code=code,selected_parent=selected,
            parent_margin=limit-selected,after_512_reserve=limit-selected-512,code_margin=65536-code,
            heap_only_after_same_code_target=heap_only,heap_only_additional_cut_with_reserve=heap_only-(limit-512)),
        window=dict(bytes=8340,root_and_pins=512,early_header=64,events=32,event_bytes=24,early_store=early,
            guard=24,old_code_estimate=6440,added_code_cap=512,code_reduction_target=1536,
            before_code_target_margin=window_before,after_code_target_margin=window_after,
            uncertainty_reserve=uncertainty,after_uncertainty=window_after-uncertainty,
            early_begin=0x200542c0,early_end=0x20054600,maximum_code_end=0x200542a8),
        diag=dict(old_file_estimate=20480,old_bss_layout=77824,fixed=7628,new_code_cap=1024,
            new_bss_cap=768,shared_code_reduction_target=640,before_code_target=diag_before,
            selected_file_budget=20864,selected_bss_budget=78592,selected_request=diag_selected,
            strict_limit=107612,margin=528,after_512_reserve=16,
            naive_all_99_rows_request=diag_selected+8576,additional_r5_format_delta='unknown_real_link_required'),
        full_g0_passed=False,er_ownership_proved=False,autoapply_executed=False,product_code_changed=False)

def build_layout():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and SCRATCH.is_dir()
    gcc=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    objdump=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    target=SCRATCH/'r6_layout.o'
    flags=['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-common','-fno-stack-protector',
           '-m32r','-mmodel=medium','-msdata=none','-G0','-Wall','-Wextra','-Werror','-c']
    argv=[str(gcc)]+flags+[str(HERE/'layout_probe.c'),'-o',str(target)]
    env=dict(os.environ,TMPDIR=str(SCRATCH))
    ran=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=60)
    assert ran.returncode==0,(ran.stdout,ran.stderr)
    table=subprocess.run([str(objdump),'-t',str(target)],capture_output=True,text=True,timeout=60)
    assert table.returncode==0,table.stderr
    symbols={name:int(size,16) for size,name in re.findall(r'\bO\s+\S+\s+([0-9a-fA-F]+)\s+(r6_\w+)',table.stdout)}
    expected=dict(r6_early_layout=832,r6_diag_layout=768,r6_permit_layout=64,
                  r6_transaction_layout=128,r6_existing_record_layout=40)
    assert symbols==expected,symbols
    result=dict(classification='m32r_object_layout_only',symbols=symbols,total_measured_data=1832,
        new_window_data=832,new_diag_data=768,new_feature_session_data=192,reused_record=40,
        source_sha256=digest(HERE/'layout_probe.c'),gcc_sha256=digest(gcc),objdump_sha256=digest(objdump),
        object_sha256=digest(target),symbol_output_sha256=hashlib.sha256(table.stdout.encode()).hexdigest(),
        command=argv,compiler_returncode=0,full_firmware_link=False,code_size_measured=False,
        interrupt_or_task_proof=False)
    (HERE/'layout-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build-layout',action='store_true')
    parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    result=compute()
    if args.build_layout:result['layout']=build_layout()
    elif (HERE/'layout-result.json').is_file():result['layout']=json.loads((HERE/'layout-result.json').read_text())
    if args.write_evidence:(HERE/'space-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(classification=result['classification'],moved_data=result['readonly_bank']['total'],
        readonly_package_budget=result['readonly_package_budget']['file_length'],
        conditional_parent=result['parent']['selected_parent'],conditional_dat_code=result['parent']['selected_code'],
        full_g0_passed=False),ensure_ascii=False))

if __name__=='__main__':main()
