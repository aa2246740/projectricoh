#!/usr/bin/python3 -I
"""Recalculate target structure sizes and the three retained heap blocks."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import struct
import subprocess

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g151_body/evidence'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g151/heap-budget')
TMP.mkdir(parents=True,exist_ok=True)
signal.alarm(1800)


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


build=load(ROOT/'firmware/resident_v39/resident/build.py','review_sizes_build')
source=(build.HERE/'loader.c').read_text().split('static const char sources',1)[0]
source+='const uint32_t review_sizes[]={sizeof(RvLoadWork),sizeof(RvUiSnapshot),RV_BLOCK_OVERHEAD,RV_MAX_BLOCK_BYTES};\n'
(TMP/'sizes.c').write_text(source)
environment=dict(os.environ,TMPDIR=str(TMP))
commands=[
    [build.GCC,*build.FLAGS,'-mmodel=medium','-I',build.HERE,'-c',TMP/'sizes.c','-o',TMP/'sizes.o'],
    [build.OBJCOPY,'-O','binary','-j','.rodata.review_sizes',TMP/'sizes.o',TMP/'sizes.bin']]
for command in commands:
    subprocess.run([str(x) for x in command],check=True,env=environment,capture_output=True,timeout=600)
work,ui,overhead,format_limit=struct.unpack('>4I',(TMP/'sizes.bin').read_bytes())
assert (work,ui,overhead,format_limit)==(608,1968,7628,122316)
raw=(ROOT/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT').read_bytes()
bss=struct.unpack_from('>I',raw,116)[0]
request=overhead+((len(raw)+bss+3)&~3)
assert request==105404
model=load(ROOT/'research/heap_headroom/budget.py','review_heap_model')
heap,records=model.baseline(request)
summary=heap.summary()
assert summary['live_extent_total']==108016
assert summary['free_extent_total']==summary['largest_free_extent']==154128
assert all(heap.loader_accepts(r['pointer']) for r in records)
edge=model.Heap();pointer=edge.alloc(262104)
assert edge.loader_accepts(pointer)
edge=model.Heap();pointer=edge.alloc(262108)
assert not edge.loader_accepts(pointer)
result=dict(classification='target_size_and_conditional_heap_model',file_bytes=len(raw),bss_bytes=bss,
    block_overhead=overhead,main_request=request,design_budget=108124,reserve_28mm=2000,
    review_limit=106124,margin=106124-request,format_limit=format_limit,
    configured_heap_bytes=model.CAPACITY,raw_request_must_be_less_than=model.CAPACITY,
    maximum_initial_request_accepted_by_loader=262104,
    allocations=records,**summary,free_extent_inside_configured_boundary=154116,
    assumption='Initially one completely free small heap; other native objects and fragmentation are excluded.',
    model_sha256=hashlib.sha256((ROOT/'research/heap_headroom/budget.py').read_bytes()).hexdigest())
(OUT/'heap_budget.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
