"""Size a proposed H08 retire guard; keep the original 200 B assertion."""
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,module,save
b=module(ROOT/"firmware/resident_v35/resident/build.py","review_size_builder")
os.environ["TMPDIR"]=str(HERE/"resident/tmp")
dest=HERE/"fix_size";dest.mkdir(exist_ok=True)
original=(b.HERE/"hooks.c").read_text()
before='reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));return;}'
after='reason=rv_check(r);if(reason){rv_retire(r,reason);early(r,hook,f,(4u<<8)|(reason<<16));if(hook==8){f[7]=0;f[1]=(uint32_t)(uintptr_t)rv_skip_08;}return;}'
assert original.count(before)==1
source=original.replace(before,after)
(dest/"hooks.c").write_text(source)
(dest/"proposal.diff").write_text("".join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile="official-review-input/hooks.c",tofile="proposal-only/hooks.c")))
obj=dest/"hooks.o"
cmd=[str(b.GCC),*b.FLAGS,"-mmodel=medium","-I",str(b.HERE),"-c",str(dest/"hooks.c"),"-o",str(obj)]
p=subprocess.run(cmd,capture_output=True,text=True)
(dest/"compile.stdout.log").write_text(p.stdout);(dest/"compile.stderr.log").write_text(p.stderr)
assert p.returncode==0
commands=json.loads((HERE/"resident/commands.json").read_text())
link=next(x["argv"] for x in commands if x["name"]=="link")
mapped=[]
for a in link:
 if a==str(HERE/"resident/build/hooks.o"):a=str(obj)
 elif a.startswith("-Map="):a="-Map="+str(dest/"resident.map")
 elif a==str(HERE/"resident/build/resident.elf"):a=str(dest/"resident.elf")
 mapped.append(a)
p=subprocess.run(mapped,capture_output=True,text=True)
(dest/"link.stdout.log").write_text(p.stdout);(dest/"link.stderr.log").write_text(p.stderr)
mapping=(dest/"resident.map").read_text()
end=int(re.search(r'(0x[0-9a-f]+)\s+__resident_code_end\s*=',mapping).group(1),16)
result=dict(proposal="suppress only the H08 continuation on the same call that rv_check retires",
 source_patch="fix_size/proposal.diff",compile_argv=cmd,link_argv=mapped,link_exit=p.returncode,
 code_end=hex(end),payload=end-0x2005276c,delta_bytes=end-0x20054634,
 reserve_bytes=0x20054700-end,excess_over_200_byte_assertion=max(0,end-(0x20054700-200)),
 original_linker_script_unchanged=True,review_only=True,shipping_build=False)
save("fix-size.json",result)
print(json.dumps(result,indent=2))
