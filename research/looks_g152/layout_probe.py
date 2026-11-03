"""Read target structure offsets from compiler-generated constants."""
from pathlib import Path
import importlib.util
import json
import subprocess
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152/layout')
PRODUCT=ROOT/'firmware/engine_v60_g152/candidate/containers/product'

def main():
    TMP.mkdir(parents=True,exist_ok=True)
    fields={
        'bytes':'sizeof(Integrated)','ui':'offsetof(Integrated,ui)',
        'values':'offsetof(Integrated,values)','failed':'offsetof(Integrated,failed)',
        'context':'offsetof(Integrated,context)','list':'offsetof(Integrated,list)',
        'failed_text':'offsetof(Integrated,failed_text)',
    }
    for name in ('levels','saved','text','nav','frame','screen','cur','top','physical','count','slot','param',
                 'group','armed','applied_user','origin','l1_cur','card_cur','item_cur','entry_cur','confirmed_user','effect','look_cur'):
        fields['ui.'+name]='offsetof(UvState,'+name+')'
    for name in ('current','confirmed','live','staging','work','tweak','confirmed_tweak','confirmed_valid','committed','s_unwritten','baseline','uncertain','write_started','live_verified','snapshot_fault'):
        fields['g.'+name]='offsetof(Engine,'+name+')'
    fields['ref.bytes']='sizeof(EngRecipeRef)'
    fields['ref.effect']='offsetof(EngRecipeRef,effect)'
    fields['ref.effect_crc']='offsetof(EngRecipeRef,effect_crc)'
    source='#include <stddef.h>\n#include "'+str(PRODUCT/'adapter.c')+'"\n#include "'+str(PRODUCT/'src/firmware/engine/core/eng_core.c')+'"\n'
    source+='const unsigned g152_layout[]={'+','.join(fields.values())+'};\n'
    (TMP/'layout.c').write_text(source)
    compiler=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(compiler),'-std=c11','-Oz','-ffreestanding','-fno-builtin','-fpic','-m32r','-I',str(PRODUCT),
                    '-c',str(TMP/'layout.c'),'-o',str(TMP/'layout.o')],check=True,capture_output=True)
    spec=importlib.util.spec_from_file_location('g152_elf',ROOT/'firmware/stage2l_switch/tools/build.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    elf=mod.Elf(TMP/'layout.o');symbol=elf.symbols['g152_layout'];section=elf.sections[symbol['section']]
    data=elf.content(section)[symbol['value']:symbol['value']+symbol['size']]
    values=struct.unpack('>'+str(len(fields))+'I',data)
    result=dict(zip(fields,values));assert result['ref.bytes']==56
    (HERE/'layout.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
