"""Read target-compiler offsets without running host layout assumptions."""
from pathlib import Path
import json
import runpy
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,enable,check_inputs

def main():
    enable();check_inputs();out=WORK/'local/layout';out.mkdir(parents=True,exist_ok=True)
    product=ENGINE/'candidate/containers/product'
    gcc=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    command=[str(gcc),'-std=c11','-Os','-ffreestanding','-fno-builtin','-fpic','-m32r','-mmodel=medium',
             '-msdata=none','-G0','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
             '-I',str(product),'-c',str(WORK/'adapter_layout.c'),'-o',str(out/'adapter.o')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=1200)
    (out/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stderr[-4000:])
    Elf=runpy.run_path(str(ROOT/'firmware/stage2l_switch/tools/build.py'))['Elf']
    elf=Elf(out/'adapter.o');section=next(s for s in elf.sections if s['name']=='.layout')
    values=struct.unpack('>28I',elf.content(section))
    names=['bytes','ui','values','failed','context','ui.levels','ui.saved','ui.text','ui.nav','ui.frame',
           'ui.screen','ui.cur','ui.top','ui.physical','ui.count','ui.slot','ui.param','ui.group','ui.armed',
           'ui.applied_user','ui.origin','ui.l1_cur','ui.card_cur','ui.item_cur','ui.entry_cur','ui.confirmed_user','list','failed_text']
    (WORK/'adapter-layout.json').write_text(json.dumps(dict(zip(names,values)),indent=2)+'\n')
    check_inputs();print(json.dumps({'name':'adapter_layout','returncode':0,'fields':len(values)}))

if __name__=='__main__':main()
