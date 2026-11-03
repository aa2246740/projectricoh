"""Compile target layout constants, distinguish policy budget from loader caps."""
import json, os, struct, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *
from link_check import Elf

def main():
    guard();raw=dat();old=dat(True);folder=TMP/'size';folder.mkdir(parents=True,exist_ok=True)
    source='#include "resident.h"\nconst unsigned review_layout[]={sizeof(RvSession),RV_BLOCK_OVERHEAD,RV_MAX_FILE,RV_MAX_CODE,RV_MAX_IMAGE,sizeof(RvUiSnapshot),RV_MAX_BLOCK_BYTES};\n'
    (folder/'layout.c').write_text(source)
    gcc=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    args=list(map(str,[gcc,'-m32r','-Os','-ffreestanding','-I'+str(ENGINE/'resident'),'-c',folder/'layout.c','-o',folder/'layout.o']))
    p=subprocess.run(args,capture_output=True,text=True,timeout=10800)
    (HERE/'evidence/size-build.log').write_text(p.stdout+p.stderr);p.check_returncode()
    elf=Elf(folder/'layout.o');s=next(s for s in elf.symbols if s['name']=='review_layout')
    section=elf.sections[s['section']];at=section['offset']+s['value'];values=struct.unpack_from('>7I',elf.raw,at)
    assert values==(1228,7628,98304,65536,114688,1968,122316),values
    (folder/'history.c').write_text('#include "resident.h"\nconst unsigned review_history[]={sizeof(RvSession),RV_BLOCK_OVERHEAD};\n')
    history_args=list(map(str,[gcc,'-m32r','-Os','-ffreestanding','-I'+str(ROOT/'firmware/engine_v54_g137/resident'),'-c',folder/'history.c','-o',folder/'history.o']))
    p=subprocess.run(history_args,capture_output=True,text=True,timeout=10800)
    (HERE/'evidence/size-history-build.log').write_text(p.stdout+p.stderr);p.check_returncode()
    hist=Elf(folder/'history.o');sym=next(s for s in hist.symbols if s['name']=='review_history')
    hs=hist.sections[sym['section']];history_values=struct.unpack_from('>2I',hist.raw,hs['offset']+sym['value'])
    assert history_values==(1104,7504),history_values
    g137=json.loads((ROOT/'firmware/engine_v54_g137/candidate/local/full-r13/layout.json').read_text())
    original_budget=history_values[1]+g137['image_bss_bytes'];assert original_budget==108124
    limit=original_budget-512;assert limit==107612
    bss=struct.unpack_from('>I',raw,116)[0];code=struct.unpack_from('>I',raw,136)[0]
    request=values[1]+((len(raw)+bss+3)&~3)
    oldrequest=values[1]+((len(old)+bss+3)&~3)
    assert (request,oldrequest)==(103644,106532)
    assert request<=limit and len(raw)<=values[2] and code<=values[3]
    result=dict(status='PASS',dat_sha256=sha(raw),target_layout=dict(zip(('session','overhead','file_limit','code_limit','image_limit','ui_snapshot','loader_main_limit'),values)),
                main_request=request,baseline_main_request=oldrequest,DAT_bytes=len(raw),code_bytes=code,BSS_bytes=bss,
                headroom=dict(main=limit-request,DAT=values[2]-len(raw),code=values[3]-code),
                budget_origin=dict(g137_image_bytes=g137['image_bss_bytes'],g137_session_bytes=history_values[0],g137_fixed_overhead=history_values[1],g137_request=original_budget,
                    reserve=512,review_main_limit=limit,reference='research/looks_expansion_design/DESIGN.md:30,53,69,91,502',
                    interpretation='Operational budget derived from historical g137 usage; not an allocator constant or proof of worst-case heap availability'),
                command=args,history_command=history_args)
    save('evidence/size-check.json',result);print(json.dumps(result))

if __name__=='__main__':main()
