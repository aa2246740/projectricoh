"""Compare small source-level guard shapes under the unchanged linker gate."""
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,module,save
b=module(ROOT/"firmware/resident_v35/resident/build.py","review_size_alternatives")
os.environ["TMPDIR"]=str(HERE/"resident/tmp")
original=(b.HERE/"hooks.c").read_text()
needle='reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));return;}'
variants={
 "f1_only":original.replace(needle,'reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));if(hook==8)f[1]=(uint32_t)(uintptr_t)rv_skip_08;return;}'),
 "shared_exit":original.replace(needle,'reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));if(hook==8){f[7]=0;skip=rv_skip_08;goto write_skip;}return;}').replace('    if(skip)f[1]', 'write_skip:\n    if(skip)f[1]'),
 "shared_exit_f1":original.replace(needle,'reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));if(hook==8){skip=rv_skip_08;goto write_skip;}return;}').replace('    if(skip)f[1]', 'write_skip:\n    if(skip)f[1]'),
}
link=next(x["argv"] for x in json.loads((HERE/"resident/commands.json").read_text()) if x["name"]=="link")
rows=[]
for name,source in variants.items():
 dest=HERE/"fix_alternatives"/name;dest.mkdir(parents=True,exist_ok=True)
 (dest/"hooks.c").write_text(source)
 (dest/"proposal.diff").write_text("".join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile="review-input/hooks.c",tofile=name+"/hooks.c")))
 obj=dest/"hooks.o"
 cmd=[str(b.GCC),*b.FLAGS,"-mmodel=medium","-I",str(b.HERE),"-c",str(dest/"hooks.c"),"-o",str(obj)]
 p=subprocess.run(cmd,capture_output=True,text=True);(dest/"compile.log").write_text(p.stdout+p.stderr);assert not p.returncode
 mapped=[]
 for a in link:
  if a==str(HERE/"resident/build/hooks.o"):a=str(obj)
  elif a.startswith("-Map="):a="-Map="+str(dest/"resident.map")
  elif a==str(HERE/"resident/build/resident.elf"):a=str(dest/"resident.elf")
  mapped.append(a)
 p=subprocess.run(mapped,capture_output=True,text=True);(dest/"link.log").write_text(p.stdout+p.stderr)
 end=int(re.search(r'(0x[0-9a-f]+)\s+__resident_code_end\s*=',(dest/"resident.map").read_text()).group(1),16)
 rows.append(dict(name=name,delta=end-0x20054634,code_end=hex(end),link_exit=p.returncode,excess=max(0,end-0x20054638)))
save("fix-alternatives.json",rows)
print(json.dumps(rows,indent=2))
