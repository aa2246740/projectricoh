"""Read current M32R structure offsets from a compiler-produced data section."""
from pathlib import Path
import struct,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,load,save,sha
folder=OUT/'local/layout';folder.mkdir(parents=True,exist_ok=True)
source=folder/'current_layout.c';obj=folder/'current_layout.o'
fields=['panel','panel.recipe','panel.draft','panel.param_index','panel.list','list','values','lo','hi','failed','watch_view','view_lost','comm_failed']
source.write_text('#define ENG_HOST 1\n#include "'+str(TREE/'candidate/containers/product/adapter.c')+'"\nconst unsigned quality_offsets[] __attribute__((section(".quality_layout"),used))={'+','.join('offsetof(Integrated,'+f+')' for f in fields)+',sizeof(Integrated)};\n')
command=[str(ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'),'-std=c11','-Os','-ffreestanding','-fno-builtin','-m32r','-msdata=none','-G0','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-DACCEPTANCE_ENTRIES_HEADER="'+str(TREE/'candidate/local/product-r13/entries.h')+'"','-c',str(source),'-o',str(obj)]
result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
(folder/'current_layout.stdout').write_text(result.stdout);(folder/'current_layout.stderr').write_text(result.stderr)
assert result.returncode==0,result.stderr
reader=load(ROOT/'tools/native_harness/image_loader.py','quality_layout_elf');elf=reader.Elf(obj)
section=next(s for s in elf.sections if s['name']=='.quality_layout');values=struct.unpack('>'+str(len(fields)+1)+'I',section['data'])
record=dict(zip(fields+['bytes'],values));save('local/layout/current-adapter-layout.json',record)
save('local/layout/current-layout-command.json',dict(command=command,returncode=0,object_sha256=sha(obj.read_bytes())))
print(record,flush=True)
