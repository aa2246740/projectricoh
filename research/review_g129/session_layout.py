"""Read session fields from a target-compiler constant section."""
from pathlib import Path
import hashlib
import json
import runpy
import struct
import subprocess
import os

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

def main():
    local=WORK/'local/session-layout';local.mkdir(parents=True,exist_ok=True)
    gcc=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    product=ROOT/'firmware/engine_v49_knobs/candidate/containers/product'
    command=[str(gcc),'-std=c11','-Os','-ffreestanding','-fno-builtin','-fpic','-m32r','-mmodel=medium',
             '-msdata=none','-G0','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
             '-I',str(product),'-c',str(WORK/'session_layout.c'),'-o',str(local/'fields.o')]
    result=subprocess.run(command,capture_output=True,timeout=4200,env={**os.environ,'TMPDIR':str(WORK/'local/tmp')})
    assert result.returncode==0,('target_layout_compilation',result.returncode,len(result.stderr.splitlines()))
    Elf=runpy.run_path(str(ROOT/'firmware/stage2l_switch/tools/build.py'))['Elf'];elf=Elf(local/'fields.o')
    section=next(value for value in elf.sections if value['name']=='.layout')
    values=struct.unpack('>6I',elf.content(section))
    names=('initialized','active','context','request','work','work_bytes')
    assert values[-1]==2288 and values[-2]+2288<=4864
    output=dict(zip(names,values));output['compiler_sha256']=hashlib.sha256(gcc.read_bytes()).hexdigest()
    (WORK/'session-layout.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'name':'target_session_layout','returncode':0,'fields':len(values),'work_bytes':values[-1]}))

if __name__=='__main__':main()
